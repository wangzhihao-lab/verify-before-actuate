"""Build paper figures from archived result JSON.

    PYTHONPATH=. .venv/bin/python run_figures.py --out ../paper/figures
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from src.exp.fig_theory import active_interval
from src.exp.figures import (cost_ratio_scaling, safety_utility_pareto,
                             selection_vs_risk, tau_scaling)

logger = logging.getLogger("run_figures")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--costbench", default="out/costbench_v3/costbench.json")
    p.add_argument("--selection", default="out/corpus_v2/selection.json")
    p.add_argument("--policies", default="out/policies_v3/policy_analysis.json")
    p.add_argument("--crossover", default="out/crossover_v3/crossover.json")
    p.add_argument("--out", default="../paper/figures")
    p.add_argument("--only", nargs="*", default=None,
                   help="build only these figure names")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                        format="%(levelname)-7s %(message)s")

    out = Path(args.out)
    built, skipped = [], []

    jobs = [
        ("fig_tau_scaling", Path(args.costbench), tau_scaling),
        ("fig_selection_vs_risk", Path(args.selection), selection_vs_risk),
        ("fig_safety_utility", Path(args.policies), safety_utility_pareto),
        ("fig_cost_ratio", Path(args.crossover), cost_ratio_scaling),
        # Analytical illustration of Theorem 2; no data dependency.
        ("fig_active_interval", None, active_interval),
    ]
    for name, src, fn in jobs:
        if args.only is not None and name not in args.only:
            continue
        if src is None:
            info = fn(out / name)
            logger.info("%s: %s", name, info)
            built.append(name)
            continue
        if not src.exists():
            logger.warning("skip %s: %s not found", name, src)
            skipped.append(name)
            continue
        info = fn(src, out / name)
        logger.info("%s: %s", name, info)
        built.append(name)

    print(f"\nbuilt: {built}")
    if skipped:
        print(f"skipped (source missing): {skipped}")
    print(f"-> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
