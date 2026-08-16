"""Verification at a continuous coverage budget, in both backends.

Same contract as the class-based verifiers -- ``(outcome, counterexample,
seconds)`` over a frozen schedule and a temporal scope -- but the budget is a
coverage fraction over predicate instances rather than one of three nested
class sets. Needed because the renewal model assumes a continuous budget with
detection strictly below one, which three nested levels cannot provide.

At the fractions that correspond exactly to whole classes this must agree
with the class-based implementation, and ``tests/test_frac_equiv.py`` asserts
it. Without that check a continuous budget would be a different experiment
wearing the same name.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

import z3

from .coverage import (Pred, budget_count, check_selected,
                       predicate_instances, select_k, structural_selected)
from .netmodel import NetState, Op, apply_op

logger = logging.getLogger(__name__)

Violation = Dict[str, Any]


def _states(base: NetState, plan: List[Op]) -> Tuple[List[NetState],
                                                     List[Violation]]:
    """Concrete intermediate states plus any structural errors seen."""
    st = base.clone()
    states: List[NetState] = []
    structural: List[Violation] = []
    for i, op in enumerate(plan):
        for err in apply_op(st, op):
            structural.append({"cls": "I3", "kind": "structural", "step": i,
                               "detail": err})
        states.append(st.clone())
    return states, structural


def _encode_selected(solver: z3.Solver, st: NetState,
                     selected: Sequence[Pred], tag: str) -> None:
    """Assert that the state violates at least one SELECTED predicate.

    Quantities are bound as concrete reals, exactly as in the class-based
    encoder; the only difference is which instances get encoded at all.
    """
    viol = []
    for cls, kind, obj in selected:
        if kind == "link_overload" and obj in st.links:
            x = z3.Real(f"{tag}_load_{obj}")
            solver.add(x == st.link_load(obj))
            viol.append(x > st.links[obj]["cap"])
        elif kind == "vnf_slots" and obj in st.nodes:
            y = z3.Int(f"{tag}_rep_{obj}")
            solver.add(y == st.nodes[obj]["replicas"])
            viol.append(y > st.nodes[obj]["vnf_slots"])
        elif kind == "sla_latency" and obj in st.flows:
            z = z3.Real(f"{tag}_lat_{obj}")
            solver.add(z == st.flow_latency_ms(obj))
            viol.append(z > st.flows[obj]["sla_ms"])
        elif kind == "priority_bw" and obj in st.flows:
            flow = st.flows[obj]
            if flow.get("priority"):
                w = z3.Real(f"{tag}_bw_{obj}")
                solver.add(w == flow["bw"])
                viol.append(w < flow["min_bw"])
        elif kind == "acl_conflict":
            src, _, dst = obj.partition("->")
            acts = {r["action"] for r in st.acls.values()
                    if r["src"] == src and r["dst"] == dst}
            if len(acts) > 1:
                viol.append(z3.BoolVal(True))
        elif kind == "flow_via_disabled" and obj in st.flows:
            path = st.flows[obj]["path"]
            if any(not st.nodes[n]["enabled"] for n in path if n in st.nodes):
                viol.append(z3.BoolVal(True))
    solver.add(z3.Or(viol) if viol else z3.BoolVal(False))


def frac_verify(base: NetState, plan: List[Op], e: str = "prefix",
                frac: float = 1.0, order: str = "class", mode: str = "smt",
                full_traversal: bool = False, witness: bool = True
                ) -> Tuple[str, Optional[Violation], float]:
    """Verify at coverage fraction ``frac``.

    Args:
        e: temporal scope, ``"prefix"`` or ``"term"``.
        frac: coverage in (0, 1]; selects predicate instances by ``order``.
        mode: ``"smt"`` for the Z3 path, ``"checker"`` for the direct path.
        full_traversal: keep going past the first violation, for cost
            measurement that is comparable across budgets.
    """
    t0 = time.perf_counter()
    # The budget is an absolute count of predicate evaluations, fixed from
    # the base state, but the instances it is spent on are re-enumerated at
    # every state. A plan can create objects -- a new ACL pair, a new slice
    # reservation -- so a checker holding a precomputed instance list would be
    # structurally blind to anything the plan brought into existence, while a
    # checker taking a fixed FRACTION of the current population would silently
    # gain evaluations as the plan grew the state. Neither is a budget.
    base_preds = predicate_instances(base)
    k = budget_count(len(base_preds), frac)
    check_structural = structural_selected(select_k(base_preds, k, order))

    states, structural = _states(base, plan)
    first: Optional[Violation] = None

    if check_structural and structural:
        first = structural[0]
        if not full_traversal:
            return "REJECT", first, time.perf_counter() - t0

    if not states:
        return "ACCEPT", first, time.perf_counter() - t0
    targets = states if e == "prefix" else states[-1:]
    offset = 0 if e == "prefix" else len(states) - 1

    for idx, st in enumerate(targets):
        step = offset + idx
        sel = select_k(predicate_instances(st), k, order)
        if mode == "checker":
            found = check_selected(st, sel)
            if found and first is None:
                first = {**found[0], "step": step}
            if found and not full_traversal:
                return "REJECT", first, time.perf_counter() - t0
        else:
            solver = z3.Solver()
            _encode_selected(solver, st, sel, tag=f"s{idx}")
            if solver.check() == z3.sat:
                if first is None:
                    found = check_selected(st, sel) if witness else []
                    first = ({**found[0], "step": step} if found else
                             {"cls": "smt", "step": step,
                              "detail": "selected predicate violated"})
                if not full_traversal:
                    return "REJECT", first, time.perf_counter() - t0

    outcome = "REJECT" if first is not None else "ACCEPT"
    return outcome, first, time.perf_counter() - t0


def n_predicates(base: NetState) -> int:
    return len(predicate_instances(base))


__all__ = ["frac_verify", "n_predicates"]
