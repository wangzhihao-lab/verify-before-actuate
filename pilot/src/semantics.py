"""Shared (e, b) verification semantics: temporal scope and coverage depth.

Single source of truth for how a verification profile ``a = (e, m, b)``
decides whether a plan counts as unsafe, factored out so the corpus runner,
the policy runners and the analysis all agree by construction.

  e  temporal scope
     ``"prefix"``   every intermediate state after every operation counts
                    (transient violations are real in a live network);
     ``"term"``     only the final state counts, plus structural errors,
                    which are terminal-relevant however late they occur.
  b  coverage depth, nested: 1 = {I1}, 2 = {I1,I2}, 3 = {I1,I2,I3}.

``microbench_ptau.py`` contains the archived original of this logic at the
paper's evidence SHA and is deliberately left untouched;
``tests/test_semantics_equiv.py`` asserts the two agree so they cannot drift.

The COMMON LOSS EVENT shared by every profile is ``not Safe_prefix`` at full
coverage -- see :func:`is_common_loss`. Detection rates must always be scored
against that fixed denominator, never against a per-profile one, otherwise a
shallower profile scores well simply by defining harm away.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

from .invariants import Violation, check_plan, check_state
from .netmodel import NetState, Op, apply_op

# Nested coverage classes by budget.
CLASSES: Dict[int, Tuple[str, ...]] = {
    1: ("I1",),
    2: ("I1", "I2"),
    3: ("I1", "I2", "I3"),
}

SCOPES: Tuple[str, ...] = ("term", "prefix")
BUDGETS: Tuple[int, ...] = (1, 2, 3)


def terminal_violations(base: NetState, plan: List[Op]) -> List[Violation]:
    """Violations visible in the FINAL state, plus structural errors.

    Structural errors (hallucinated entities, disconnected paths) are
    included at any step: they are defects of the plan itself, so a terminal
    checker that executed the plan would still surface them.
    """
    st = base.clone()
    structural: List[Violation] = []
    for i, op in enumerate(plan):
        for err in apply_op(st, op):
            structural.append({"cls": "I3", "kind": "structural", "step": i,
                               "detail": err})
    return check_state(st) + structural


def violations_for(base: NetState, plan: List[Op], e: str) -> List[Violation]:
    """Violations relevant under temporal scope ``e``."""
    if e == "prefix":
        return check_plan(base, plan)
    if e == "term":
        return terminal_violations(base, plan)
    raise ValueError(f"unknown temporal scope {e!r}")


def is_unsafe(base: NetState, plan: List[Op], e: str, b: int) -> bool:
    """Would profile ``(e, b)`` consider this plan unsafe (ground truth)?"""
    covered = CLASSES[b]
    return any(v["cls"] in covered for v in violations_for(base, plan, e))


def is_common_loss(base: NetState, plan: List[Op]) -> bool:
    """The loss event shared by ALL profiles: not Safe_prefix at full depth."""
    return is_unsafe(base, plan, "prefix", 3)


def class_counts(viols: List[Violation]) -> Dict[str, int]:
    """Per-class violation counts, always with all three keys present."""
    out = {"I1": 0, "I2": 0, "I3": 0}
    for v in viols:
        out[v["cls"]] = out.get(v["cls"], 0) + 1
    return out


__all__ = [
    "BUDGETS",
    "CLASSES",
    "SCOPES",
    "class_counts",
    "is_common_loss",
    "is_unsafe",
    "terminal_violations",
    "violations_for",
]
