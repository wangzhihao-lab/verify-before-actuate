"""Detection and cost curves over a continuous coverage budget.

Produces the p(b) and tau(b) curves the renewal model assumes: many budget
points rather than three, so a technology family can be fitted and tested
instead of asserted. No agent calls -- the archived corpus is rescored.

    PYTHONPATH=. .venv/bin/python run_pcurve.py --corpus out/corpus_v2
"""
from __future__ import annotations

import argparse
import json
import logging
import statistics
import sys
from pathlib import Path
from typing import Any, Dict, List

from src.coverage import budget_count, coverage_of_classes, predicate_instances
from src.exp.analyze import conditioned, load_records, load_states, usable
from src.provenance import run_meta
from src.semantics import is_common_loss
from src.verify_frac import frac_verify

logger = logging.getLogger("run_pcurve")


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--corpus", default="out/corpus_v2")
    p.add_argument("--order", default="interleaved",
                   choices=("class", "interleaved"))
    p.add_argument("--points", type=int, default=21,
                   help="budget points in (0,1]")
    p.add_argument("--e", default="prefix", choices=("prefix", "term"))
    p.add_argument("--timing-plans", type=int, default=6,
                   help="clean plans per network used for tau timing")
    p.add_argument("--repeats", type=int, default=3)
    p.add_argument("--out", default="")
    return p.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                        format="%(levelname)-7s %(message)s")

    corpus = Path(args.corpus)
    records = load_records(corpus / "records.jsonl")
    states = load_states(corpus / "states")
    # Conditioned exactly as q and the selector are: feasible intent,
    # fulfilling plan. p and q must share a denominator to be combined.
    ok = [r for r in records if conditioned(r) and r["network"] in states]

    # The fixed denominator: the common loss event at full coverage.
    loss = [(states[r["network"]], r["plan"]) for r in ok
            if is_common_loss(states[r["network"]], r["plan"])]
    safe_recs = [r for r in ok
                 if not is_common_loss(states[r["network"]], r["plan"])]
    safe = [(states[r["network"]], r["plan"]) for r in safe_recs]
    logger.info("loss events %d, safe plans %d, order=%s",
                len(loss), len(safe), args.order)

    # Timing plans are drawn round-robin over topologies. Taking a prefix of
    # the corpus order instead put 23 of 24 timing plans on one topology, so
    # a "cost of coverage" slope was really one network's slope.
    by_net: Dict[str, List[Any]] = {}
    for rec, pair in zip(safe_recs, safe):
        by_net.setdefault(rec["network"], []).append(pair)
    timing: List[Any] = []
    for i in range(args.timing_plans):
        for net in sorted(by_net):
            if i < len(by_net[net]):
                timing.append(by_net[net][i])
    logger.info("timing plans %d over %d topologies",
                len(timing), len(by_net))

    fracs = [round(i / args.points, 4)
             for i in range(1, args.points + 1)]
    rows: List[Dict[str, Any]] = []
    for frac in fracs:
        det = sum(1 for st, pl in loss
                  if frac_verify(st, pl, e=args.e, frac=frac,
                                 order=args.order, mode="checker")[0]
                  == "REJECT")
        fp = sum(1 for st, pl in safe
                 if frac_verify(st, pl, e=args.e, frac=frac,
                                order=args.order, mode="checker")[0]
                 == "REJECT")
        # Cost on the same budget axis, full traversal so budgets compare.
        taus = []
        for st, pl in timing:
            reps = [frac_verify(st, pl, e=args.e, frac=frac,
                                order=args.order, mode="smt",
                                full_traversal=True)[2]
                    for _ in range(args.repeats)]
            taus.append(1e3 * statistics.median(reps))
        rows.append({
            "frac": frac,
            "p_detect": round(det / len(loss), 6) if loss else None,
            "n_detected": det, "n_loss": len(loss),
            "false_reject": round(fp / len(safe), 6) if safe else None,
            "tau_mean_ms": round(statistics.mean(taus), 4) if taus else None,
        })
        logger.info("frac=%.4f  p=%.4f  fp=%.4f  tau=%.2fms", frac,
                    rows[-1]["p_detect"] or 0, rows[-1]["false_reject"] or 0,
                    rows[-1]["tau_mean_ms"] or 0)

    ref = next(iter(states.values()))
    payload = {
        "meta": run_meta({"corpus": str(corpus), "order": args.order,
                          "e": args.e, "points": args.points}),
        "n_predicates_reference": len(predicate_instances(ref)),
        "class_equivalent_fracs": {
            "I1": coverage_of_classes(ref, ("I1",)),
            "I1_I2": coverage_of_classes(ref, ("I1", "I2")),
            "all": 1.0},
        "n_predicate_instances_per_topology": {
            net: len(predicate_instances(st))
            for net, st in sorted(states.items())},
        "n_timing_plans": len(timing),
        "n_timing_topologies": len(by_net),
        "rows": rows,
        "note": ("p is scored against the common full-coverage loss event "
                 "over FEASIBLE, FULFILLING plans -- the same conditioning "
                 "as q and the selector. Within one verification the budget "
                 "is an absolute count of predicate evaluations fixed from "
                 "the base state; the SWEEP AXIS below is a fraction of each "
                 "topology's own base count, so one row pools different "
                 "absolute budgets across topologies."),
    }
    dest = Path(args.out) if args.out else corpus / f"pcurve_{args.order}.json"
    dest.write_text(json.dumps(payload, indent=1))

    print(f"\n{'frac':>8}{'p_detect':>11}{'false_rej':>11}{'tau_ms':>10}")
    for r in rows:
        print(f"{r['frac']:>8.4f}{r['p_detect']:>11.4f}"
              f"{r['false_reject']:>11.4f}{r['tau_mean_ms']:>10.2f}")
    print(f"\n-> {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
