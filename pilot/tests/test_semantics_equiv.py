"""Pin src/semantics.py to the archived microbench semantics.

microbench_ptau.py holds the (e, b) ground-truth logic used to produce the
paper's evidence at its clean SHA, and is intentionally never edited.
src/semantics.py is the shared re-export new experiment code builds on.
If the two ever disagree, previously published numbers stop being comparable
with new ones -- so this test fails loudly instead.

Run: PYTHONPATH=. .venv/bin/python tests/test_semantics_equiv.py
"""
from __future__ import annotations

import random
import sys

from microbench_ptau import CLASSES as MB_CLASSES
from microbench_ptau import clean_plans, is_unsafe_e
from run_p_inject import build_injections
from src.netmodel import gen_topology
from src.semantics import BUDGETS, CLASSES, SCOPES, is_unsafe

SEED = 42


def test_classes_match() -> None:
    assert CLASSES == MB_CLASSES, (CLASSES, MB_CLASSES)


def test_is_unsafe_matches_microbench() -> None:
    base = gen_topology(random.Random(SEED), 24, 14, 40)
    rng = random.Random(SEED)
    plans = [p for _, p in build_injections(base)]
    plans += clean_plans(base, rng)
    assert plans, "no plans to compare"

    mismatches = []
    for i, plan in enumerate(plans):
        for e in SCOPES:
            for b in BUDGETS:
                mine = is_unsafe(base, plan, e, b)
                theirs = is_unsafe_e(base, plan, e, b)
                if mine != theirs:
                    mismatches.append((i, e, b, mine, theirs))
    assert not mismatches, f"{len(mismatches)} disagreements: {mismatches[:5]}"
    return len(plans) * len(SCOPES) * len(BUDGETS)


def main() -> int:
    test_classes_match()
    n = test_is_unsafe_matches_microbench()
    print(f"PASS: semantics.is_unsafe agrees with microbench on {n} "
          f"(plan, e, b) combinations")
    return 0


if __name__ == "__main__":
    sys.exit(main())
