"""CLI runner for the verification cost-scaling sweep (no LLM calls).

Validation pass (fast, a few networks):
    PYTHONPATH=. .venv/bin/python run_costbench.py --networks abilene geant \
        --n-plans 4 --repeats 3

Authoritative pass -- run this ONLY on an otherwise idle machine, since the
whole point is a timing measurement:
    PYTHONPATH=. .venv/bin/python run_costbench.py
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import asdict
from pathlib import Path

from src.exp.costbench import CostBenchConfig, run_costbench
from src.provenance import run_meta, stamp

logger = logging.getLogger("run_costbench")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--networks", nargs="*", default=[],
                   help="SNDlib names (default: all 26)")
    p.add_argument("--n-plans", type=int, default=8)
    p.add_argument("--repeats", type=int, default=5)
    p.add_argument("--max-flows", type=int, default=40)
    p.add_argument("--target-util", type=float, default=0.65)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--out", default="")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.INFO, stream=sys.stdout,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S")

    cfg = CostBenchConfig(
        networks=tuple(args.networks), n_plans=args.n_plans,
        repeats=args.repeats, max_flows=args.max_flows,
        target_util=args.target_util, seed=args.seed)

    out_dir = (Path(args.out) if args.out
               else Path("out") / f"costbench_{stamp()}")
    out_dir.mkdir(parents=True, exist_ok=True)

    result = run_costbench(cfg)
    meta = run_meta({"config": asdict(cfg)})
    payload = {"meta": meta, **result}
    (out_dir / "costbench.json").write_text(json.dumps(payload, indent=1))

    for mode, chk in result["tau_monotone_in_b"].items():
        logger.info("tau non-decreasing in b [%s]: %s "
                    "(%d measured-flat, %d adding no base disjunct, "
                    "%d real decrease(s))", mode, chk["non_decreasing"],
                    len(chk["flat_within_tol"]),
                    len(chk.get("steps_adding_no_base_disjunct") or []),
                    len(chk["decreases"]))
        for d in chk["decreases"]:
            logger.warning("  A2 VIOLATION %s %s b%d->b%d: %.3f -> %.3f ms "
                           "(%.1f%%, %s constraints added)", d["network"],
                           d["e"], d["from_b"], d["to_b"], d["tau_from_ms"],
                           d["tau_to_ms"], d["delta_pct"],
                           d.get("encoded_terms_added"))
    logger.info("elapsed %.1fs | timing stability: worst CV=%.3f, "
                "%d/%d cells above %.2f | loadavg %.2f->%.2f (context only)",
                result["elapsed_s"], result["worst_cv"] or 0,
                result["n_unstable_cells"], result["n_cells"],
                result["cv_threshold"],
                result["loadavg_start"] or -1, result["loadavg_end"] or -1)

    # Compact scaling view: full-coverage prefix SMT, the most expensive cell.
    hdr = f"{'network':<16}{'nodes':>6}{'links':>6}{'smt_ms':>10}{'twin_ms':>10}"
    logger.info("%s", hdr)
    for res in result["results"]:
        if "skipped" in res:
            continue
        def cell(mode: str) -> float:
            return next(r["tau_mean_ms"] for r in res["rows"]
                        if r["mode"] == mode and r["e"] == "prefix"
                        and r["b"] == 3)
        logger.info("%-16s%6d%6d%10.2f%10.2f", res["network"],
                    res["n_nodes"], res["n_links"], cell("smt"), cell("twin"))

    logger.info("-> %s", out_dir)
    if result["contended"]:
        logger.warning("UNSTABLE TIMINGS in %d cell(s): do not cite those "
                       "cells; rerun them on a quieter machine",
                       result["n_unstable_cells"])
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
