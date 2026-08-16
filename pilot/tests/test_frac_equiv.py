"""The continuous budget must generalise the three-level one, not replace it.

At the coverage fractions that correspond exactly to whole invariant classes,
the fractional verifier has to return the same verdicts as the class-based
verifier. If it does not, the continuous-budget results are a different
experiment and cannot be compared with anything archived.

Run: PYTHONPATH=. .venv/bin/python tests/test_frac_equiv.py
"""
from __future__ import annotations

import random
import sys

from run_p_inject import build_injections
from microbench_ptau import clean_plans
from src.coverage import coverage_of_classes, predicate_instances
from src.netmodel import gen_topology
from src.smt_verify import smt_verify
from src.twin_verify import twin_verify
from src.verify_frac import frac_verify

CLASS_SETS = {1: ("I1",), 2: ("I1", "I2"), 3: ("I1", "I2", "I3")}


def main() -> int:
    base = gen_topology(random.Random(42), 24, 14, 40)
    plans = [p for _, p in build_injections(base)]
    plans += clean_plans(base, random.Random(42))
    preds = predicate_instances(base)
    print(f"{len(preds)} predicate instances on the reference topology")

    mismatch = []
    checked = 0
    for b, classes in CLASS_SETS.items():
        frac = coverage_of_classes(base, classes, order="class")
        print(f"  b={b} ({','.join(classes)}) -> coverage {frac:.4f}")
        for i, plan in enumerate(plans):
            for e in ("term", "prefix"):
                ref_smt = smt_verify(base, plan, e=e, b=b)[0]
                ref_twin = twin_verify(base, plan, e=e, b=b)[0]
                got_smt = frac_verify(base, plan, e=e, frac=frac,
                                      order="class", mode="smt")[0]
                got_chk = frac_verify(base, plan, e=e, frac=frac,
                                      order="class", mode="checker")[0]
                checked += 2
                if got_smt != ref_smt:
                    mismatch.append((i, e, b, "smt", ref_smt, got_smt))
                if got_chk != ref_twin:
                    mismatch.append((i, e, b, "checker", ref_twin, got_chk))

    if mismatch:
        print(f"\nFAIL: {len(mismatch)} mismatches")
        for m in mismatch[:10]:
            print(f"  plan={m[0]} e={m[1]} b={m[2]} path={m[3]} "
                  f"reference={m[4]} fractional={m[5]}")
        return 1
    print(f"\nPASS: fractional verifier matches the class-based verifiers on "
          f"{checked} comparisons at the class-equivalent fractions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
