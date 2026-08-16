"""Digital-twin verification mode (m=TWIN) for verify-before-actuate.

Executes the frozen schedule sigma on a concrete network twin (here the
deterministic step-simulator of `netmodel`/`invariants`, i.e. a low-fidelity
emulator) and measures the three invariant classes on the *realized* state.

Honest scope for the toy model: on the three encodable invariants, TWIN and
SMT are COVERAGE-EQUIVALENT (both are sound decision procedures for the same
predicates) — verified by test_smt_equiv (checker == SMT) plus twin==checker
by construction. The DIFFERENTIAL value of dual-mode (twin catches dynamic /
timing / routing-convergence effects that a static SMT encoding cannot
express) is a Phase-3 demonstration, not claimed here. What TWIN provides now
is the SECOND runnable verification path with its OWN cost curve tau_TWIN(b)
(simulation-horizon proportional), so the outer profile selection (§III-F) and
the matched (p, tau) calibration have two real modes.

Budget b for TWIN indexes a simulation fidelity/horizon:
  b>=1 : coarse pass (I1 only, terminal)   -- cheapest
  b>=2 : I1+I2, all-prefix
  b>=3 : I1+I2+I3, all-prefix, plus a per-step re-measurement cost that
         models higher-fidelity emulation (repeated measurement passes).
"""
from __future__ import annotations

import time
from typing import Dict, List, Optional, Tuple

from .invariants import check_state
from .netmodel import NetState, Op, apply_op

Violation = Dict[str, object]

# fidelity -> number of measurement passes per state (models emulator cost)
_PASSES = {1: 1, 2: 2, 3: 4}


def twin_verify(base: NetState, plan: List[Op], e: str = "prefix",
                b: int = 3, full_traversal: bool = False
                ) -> Tuple[str, Optional[Violation], float]:
    """Verify by executing the schedule on the deterministic twin.

    full_traversal: keep simulating past the first violation. Verdict and
    counterexample are unchanged; only the measured cost differs. See
    :func:`smt_verify.smt_verify` for why early-reject timings cannot be used
    as a cost curve. Default False preserves the archived behaviour.
    """
    t0 = time.perf_counter()
    classes = {1: ("I1",), 2: ("I1", "I2"), 3: ("I1", "I2", "I3")}[
        max(1, min(3, b))]
    # execution semantics e (prefix vs terminal) is INDEPENDENT of budget b
    # (b = coverage + fidelity only). Conflating them made twin disagree with
    # the spec/SMT at b=1,prefix — caught by calibrate/equivalence.
    per_step = e == "prefix"
    passes = _PASSES[max(1, min(3, b))]

    st = base.clone()
    first_bad: Optional[Violation] = None
    for j, op in enumerate(plan):
        errs = apply_op(st, op)
        if "I3" in classes and errs:
            if first_bad is None:  # keep the FIRST violation as the witness
                first_bad = {"cls": "I3", "kind": "structural", "step": j,
                             "detail": errs[0]}
            if not full_traversal:
                break
        if per_step:
            # higher fidelity = repeated measurement passes (cost model)
            found = None
            for _ in range(passes):
                found = [v for v in check_state(st) if v["cls"] in classes]
            if found:
                if first_bad is None:
                    first_bad = {**found[0], "step": j}
                if not full_traversal:
                    break
    if first_bad is None:  # terminal (or prefix that never tripped): final
        found = None
        for _ in range(passes):
            found = [v for v in check_state(st) if v["cls"] in classes]
        if found:
            first_bad = {**found[0], "step": len(plan) - 1}

    dt = time.perf_counter() - t0
    return ("REJECT", first_bad, dt) if first_bad else ("ACCEPT", None, dt)
