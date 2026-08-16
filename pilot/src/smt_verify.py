"""SMT verification mode (m=SMT) for verify-before-actuate.

Encodes a frozen serial schedule sigma + the three invariant classes over
the chosen execution semantics (e in {term, prefix}) into Z3, at a budget b
that selects which invariant fragments are checked. Returns ACCEPT or
REJECT(counterexample) and the solve time tau.

Design contract (§II-E): SMT verification MUST agree with the ground-truth
checker `invariants.check_plan` on the fragments it covers. We verify this
equivalence in test_smt_equiv.py. The value of the SMT route is that at full
coverage it is a *decision procedure* (proves absence of violation), and its
solve time is the tau(b) the theory needs — it is not meant to beat the
Python checker on this toy model, but to be the formal, budget-tunable mode
whose cost curve drives d*.

Budget b selects fragment coverage (monotone chain, matching the pilot p(d)
levels):
  b>=1 : I1 (resource)
  b>=2 : I1+I2 (resource+SLA)
  b>=3 : I1+I2+I3 (all)
Execution semantics e: 'term' checks only final state S_K; 'prefix' checks
every intermediate state S_1..S_K.
"""
from __future__ import annotations

import time
from typing import Dict, List, Optional, Tuple

import z3

from .netmodel import NetState, Op, apply_op

Violation = Dict[str, object]


def _states(base: NetState, plan: List[Op]) -> List[NetState]:
    """Concrete intermediate states S_1..S_K (deterministic transitions)."""
    st = base.clone()
    out = []
    for op in plan:
        apply_op(st, op)
        out.append(st.clone())
    return out


def _encode_state(s: z3.Solver, st: NetState, classes: int,
                  tag: str) -> None:
    """Assert that state `st` VIOLATES some checked invariant.

    We build the invariant quantities as Z3 reals from the concrete state
    (the plan is already applied deterministically, so loads/latencies are
    numbers) and assert the negation of the conjunction of checked invariants
    for THIS state. If the disjunction-of-violations is SAT, a violation
    exists. Encoding the concrete arithmetic in Z3 (rather than just doing
    the comparison in Python) is what makes this a symbolic decision
    procedure and gives a meaningful, budget-scaled solve time; it also
    extends directly to the symbolic-plan case (future work) where op
    parameters become variables.
    """
    viol = []
    if classes >= 1:  # I1 resource
        for lid in st.links:
            load = st.link_load(lid)
            cap = st.links[lid]["cap"]
            x = z3.Real(f"{tag}_load_{lid}")
            s.add(x == load)
            viol.append(x > cap)
        for nid, n in st.nodes.items():
            y = z3.Int(f"{tag}_rep_{nid}")
            s.add(y == n["replicas"])
            viol.append(y > n["vnf_slots"])
    if classes >= 2:  # I2 SLA
        for fid, f in st.flows.items():
            lat = st.flow_latency_ms(fid)
            z = z3.Real(f"{tag}_lat_{fid}")
            s.add(z == lat)
            viol.append(z > f["sla_ms"])
            if f["priority"]:
                w = z3.Real(f"{tag}_bw_{fid}")
                s.add(w == f["bw"])
                viol.append(w < f["min_bw"])
    if classes >= 3:  # I3 conflict/integrity
        seen: Dict[tuple, str] = {}
        for rid, r in st.acls.items():
            key = (r["src"], r["dst"])
            if key in seen and seen[key] != r["action"]:
                viol.append(z3.BoolVal(True))  # concrete conflict present
            seen[key] = r["action"]
        for fid, f in st.flows.items():
            if any(not st.nodes[n]["enabled"] for n in f["path"]
                   if n in st.nodes):
                viol.append(z3.BoolVal(True))
    if viol:
        s.add(z3.Or(viol))
    else:
        s.add(z3.BoolVal(False))


def encoded_terms(st: NetState, classes: int) -> int:
    """How many violation disjuncts the encoder emits for this state.

    Context, and a correction. The integrity layer emits a disjunct only
    where a conflict is CONCRETELY present, so on a CLEAN state it
    contributes nothing and the solver receives the problem it received one
    level shallower. It is tempting to conclude the deepest budget step is
    therefore flat by construction and to settle monotonicity by counting
    instead of timing. That conclusion does NOT hold, for two reasons: the
    deterministic cost envelope is the maximum over clean and violating
    plans, and on a violating state this layer does emit (measured: +1 on
    both the ACL-conflict and disabled-transit injections); and depth three
    additionally runs a structural pass over the whole plan that shallower
    depths skip.

    So this count is context for the timing, not a substitute for it. The
    paper reports the monotonicity assumption as held to the measurement
    rather than closed by the encoding.
    """
    probe = z3.Solver()
    before = len(probe.assertions())
    _encode_state(probe, st, classes, tag="count")
    added = probe.assertions()[before:]
    # The encoder finishes with a single Or(...) of the violation disjuncts,
    # or with BoolVal(False) when there are none.
    tail = added[-1] if added else None
    if tail is None:
        return 0
    if z3.is_or(tail):
        return tail.num_args()
    return 0 if z3.is_false(tail) else 1


def _budget_classes(b: int) -> int:
    return max(1, min(3, b))


CLASS_NAMES = ("I1", "I2", "I3")


def _witness_for(st: NetState, classes: int, step: int) -> Violation:
    """Name the predicate that actually fails in this concrete state.

    A bare 'SAT at step k' tells a repairing agent only that something is
    wrong somewhere. The encoding is built from concrete quantities, so the
    satisfying assignment corresponds to a specific violated predicate on a
    specific object -- which link, its load, its capacity. Recovering it
    costs one pass over the state and turns the feedback into an actual
    counterexample rather than a rejection notice.
    """
    from .invariants import check_state

    covered = CLASS_NAMES[:classes]
    for v in check_state(st):
        if v["cls"] in covered:
            return {**v, "step": step}
    return {"cls": "smt", "step": step,
            "detail": "invariant violated (SMT sat)"}


def smt_verify(base: NetState, plan: List[Op], e: str = "prefix",
               b: int = 3, structural_first: bool = True,
               full_traversal: bool = False, witness: bool = False
               ) -> Tuple[str, Optional[Violation], float]:
    """Return (outcome, counterexample|None, solve_time_s).

    outcome ∈ {'ACCEPT','REJECT'}. structural_first: op-application errors
    (ghost entities / bad paths, an I3 concern) are caught pre-encoding, as
    they make the state ill-defined.

    witness: return the concrete violated predicate instead of a bare
    'SAT at step k'. Off by default so archived runs reproduce; the
    difference between the two is itself measurable, since feedback content
    is what a repairing agent has to work with.

    full_traversal: do not stop at the first violation. The verdict and
    counterexample are unchanged; only the timing differs. Needed because
    cost measured on plans that reject early is a detection property, not a
    cost property, and because the I3 fragment only instantiates constraints
    where a conflict concretely exists -- so timing depth-3 solely on clean
    plans systematically understates what it costs on risky ones. The
    default is False, preserving the archived behaviour exactly.
    """
    t0 = time.perf_counter()
    classes = _budget_classes(b)
    first: Optional[Violation] = None

    # structural errors (I3) surface during deterministic application
    if structural_first and classes >= 3:
        stc = base.clone()
        for j, op in enumerate(plan):
            errs = apply_op(stc, op)
            if errs:
                first = {"cls": "I3", "kind": "structural", "step": j,
                         "detail": errs[0]}
                if not full_traversal:
                    return "REJECT", first, time.perf_counter() - t0
                break

    states = _states(base, plan)
    if not states:
        return "ACCEPT", None, time.perf_counter() - t0
    targets = states if e == "prefix" else states[-1:]
    offset = 0 if e == "prefix" else len(states) - 1

    # One solver per checked state; ACCEPT iff none is SAT-violating.
    for idx, st in enumerate(targets):
        s = z3.Solver()
        _encode_state(s, st, classes, tag=f"s{idx}")
        if s.check() == z3.sat:
            if first is None:
                step = offset + idx
                first = (_witness_for(st, classes, step) if witness
                         else {"cls": "smt", "step": step,
                               "detail": "invariant violated (SMT sat)"})
            if not full_traversal:
                return "REJECT", first, time.perf_counter() - t0
    outcome = "REJECT" if first is not None else "ACCEPT"
    return outcome, first, time.perf_counter() - t0
