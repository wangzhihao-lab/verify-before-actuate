"""Compare corpus conclusions across master seeds.

Every headline number so far comes from one master seed. That seed fixes the
synthesized attributes of each topology -- VNF slot counts, SLA bounds,
priority flags, ACL rules, which demands are sampled -- as well as which
objects each intent targets and the generation seed. A conclusion that moves
when the seed moves is a property of one draw, not of the system.

Reported per seed, so the reader can see the spread rather than a single
draw dressed as a population:
  * q conditioned on feasible and fulfilling plans;
  * abstention;
  * the paired terminal/prefix disagreement count;
  * detection at the class-equivalent budgets.

    PYTHONPATH=. .venv/bin/python run_seedcmp.py out/corpus_s42 out/corpus_s43
"""
from __future__ import annotations

import argparse
import json
import logging
import statistics
import sys
from pathlib import Path
from typing import Any, Dict, List

from src.exp.analyze import (feasible, load_records, load_states,
                             usable, wilson_ci)
from src.provenance import run_meta
from src.semantics import BUDGETS, is_common_loss, is_unsafe

logger = logging.getLogger("run_seedcmp")


def summarize(corpus: Path, rep0_only: bool = False) -> Dict[str, Any]:
    """Per-seed summary; ``rep0_only`` restricts to the first repetition.

    The seeds are not run at equal size -- one corpus has five repetitions
    per cell and the others one -- so the raw q values are not comparable.
    Restricting every corpus to repetition zero puts them on the same
    design, which is what a seed-sensitivity claim needs; the difference
    between a corpus's full and repetition-zero value is sampling, not seed.
    """
    records = load_records(corpus / "records.jsonl")
    if rep0_only:
        records = [r for r in records if r.get("rep", 0) == 0]
    states = load_states(corpus / "states")
    ok = [r for r in records if usable(r) and r["network"] in states]

    certified = [r for r in ok if feasible(r)]
    fulfilled = [r for r in certified if r.get("fulfilled") is True]
    q_k = sum(1 for r in fulfilled
              if is_common_loss(states[r["network"]], r["plan"]))
    lo, hi = wilson_ci(q_k, len(fulfilled))

    prefix_only = term_only = 0
    for r in ok:
        st = states[r["network"]]
        p = is_unsafe(st, r["plan"], "prefix", 3)
        t = is_unsafe(st, r["plan"], "term", 3)
        prefix_only += p and not t
        term_only += t and not p

    loss = [(states[r["network"]], r["plan"]) for r in ok
            if is_common_loss(states[r["network"]], r["plan"])]
    det = {}
    for b in BUDGETS:
        k = sum(1 for st, pl in loss if is_unsafe(st, pl, "prefix", b))
        det[f"b{b}"] = round(k / len(loss), 4) if loss else None

    gens = [r["gen_seconds"] for r in ok if r.get("gen_seconds")]
    return {
        "corpus": str(corpus),
        "seed": json.loads((corpus / "config.json").read_text())
        .get("config", {}).get("seed"),
        "n_records": len(records), "n_usable": len(ok),
        "n_feasible": len(certified), "n_fulfilled": len(fulfilled),
        "q_conditioned": round(q_k / len(fulfilled), 4) if fulfilled else None,
        "q_ci95": [round(lo, 4), round(hi, 4)],
        "q_counts": [q_k, len(fulfilled)],
        "abstained": sum(1 for r in ok if r.get("abstained")),
        "prefix_only_unsafe": prefix_only,
        "terminal_only_unsafe": term_only,
        "n_loss": len(loss),
        "detection_by_budget": det,
        "gen_seconds_median": round(statistics.median(gens), 3) if gens else None,
    }


def main(argv: List[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("corpora", nargs="+")
    p.add_argument("--out", default="")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                        format="%(levelname)-7s %(message)s")

    rows = [summarize(Path(c)) for c in args.corpora]
    matched = [summarize(Path(c), rep0_only=True) for c in args.corpora]
    qs = [r["q_conditioned"] for r in matched if r["q_conditioned"] is not None]
    spread = {
        "q_min": min(qs) if qs else None, "q_max": max(qs) if qs else None,
        "q_range": round(max(qs) - min(qs), 4) if len(qs) > 1 else None,
        "prefix_only_total": sum(r["prefix_only_unsafe"] for r in rows),
        "abstained_total": sum(r["abstained"] for r in rows),
        "n_seeds": len(rows),
        "basis": ("q spread is computed on the REPETITION-ZERO subset of "
                  "every corpus, so the seeds share one design; the "
                  "as-run values differ in sample size and are reported "
                  "separately in per_seed"),
    }
    payload = {"meta": run_meta({"corpora": args.corpora}),
               "per_seed": rows, "per_seed_rep0_matched": matched,
               "spread": spread}
    dest = Path(args.out) if args.out else Path("out/seed_comparison.json")
    dest.write_text(json.dumps(payload, indent=1))

    for label, block in (("as run", rows), ("repetition-zero matched",
                                            matched)):
        print(f"\n{label}")
        print(f"{'seed':>6}{'n':>6}{'q':>8}{'q 95% CI':>18}{'abstain':>9}"
              f"{'prefix_only':>13}{'b1':>7}{'b2':>7}{'b3':>7}")
        for r in block:
            d = r["detection_by_budget"]
            print(f"{str(r['seed']):>6}{r['n_usable']:>6}"
                  f"{r['q_conditioned']:>8.3f}"
                  f"   [{r['q_ci95'][0]:.3f},{r['q_ci95'][1]:.3f}]"
                  f"{r['abstained']:>9}{r['prefix_only_unsafe']:>13}"
                  f"{d['b1']:>7.3f}{d['b2']:>7.3f}{d['b3']:>7.3f}")
    print(f"\nq across seeds (matched): {spread['q_min']} .. {spread['q_max']}"
          f"  (range {spread['q_range']})")
    print(f"prefix-only unsafe, all seeds pooled: {spread['prefix_only_total']}")
    print(f"abstentions, all seeds pooled:        {spread['abstained_total']}")
    print(f"\n-> {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
