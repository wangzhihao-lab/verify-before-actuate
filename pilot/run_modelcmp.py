"""Paired comparison of two agents on one identical set of intents.

A cross-model claim has to name its estimand. Two quantities get confused
here and they answer different questions:

  * each model's own conditioned violation rate, over ITS OWN feasible and
    fulfilling plans -- two different denominators, so the difference
    between them is not a paired quantity and no paired test applies to it;
  * the paired difference on the intents BOTH models fulfilled, which is
    what an exact McNemar test is a test of.

Reporting the first pair of numbers and the second's p-value together would
attach a significance statement to a comparison that never produced it. This
runner emits both, each with its own denominator, and computes the test only
on the paired set.

Conditioning matches ``analyze.conditioned`` and the profile selector: the
intent is a-priori feasible and the plan fulfils it.

    PYTHONPATH=. .venv/bin/python run_modelcmp.py \
        --a out/corpus_v2 --b out/corpus_qwen3vl
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

from src.exp.analyze import conditioned, load_records, load_states, usable
from src.provenance import run_meta
from src.semantics import is_common_loss, is_unsafe

logger = logging.getLogger("run_modelcmp")


def exact_mcnemar(n01: int, n10: int) -> float:
    """Two-sided exact binomial test on the discordant pairs."""
    n = n01 + n10
    if n == 0:
        return 1.0
    k = min(n01, n10)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def model_of(records: List[Dict[str, Any]]) -> str:
    for rec in records:
        if rec.get("model"):
            return str(rec["model"])
    return "unknown"


def marginal(records: List[Dict[str, Any]], states) -> Dict[str, Any]:
    """A model's own conditioned violation rate, on its own denominator."""
    cond = [r for r in records if conditioned(r) and r["network"] in states]
    k = sum(1 for r in cond
            if is_common_loss(states[r["network"]], r["plan"]))
    ok = [r for r in records if usable(r) and r["network"] in states]
    prefix_only = sum(1 for r in ok
                      if is_unsafe(states[r["network"]], r["plan"], "prefix", 3)
                      and not is_unsafe(states[r["network"]], r["plan"],
                                        "term", 3))
    return {"model": model_of(records), "q_conditioned": round(k / len(cond), 4)
            if cond else None, "q_counts": [k, len(cond)],
            "n_records": len(records),
            "n_usable": len(ok),
            "abstained": sum(1 for r in ok if r.get("abstained")),
            "prefix_only_unsafe": prefix_only}


def main(argv: List[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--a", required=True, help="reference corpus")
    p.add_argument("--b", required=True, help="second-model corpus")
    p.add_argument("--rep", type=int, default=0,
                   help="repetition index to compare on")
    p.add_argument("--out", default="out/model_comparison.json")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                        format="%(levelname)-7s %(message)s")

    ca, cb = Path(args.a), Path(args.b)
    states = load_states(ca / "states")
    ra = [r for r in load_records(ca / "records.jsonl")
          if r.get("rep", 0) == args.rep]
    rb = [r for r in load_records(cb / "records.jsonl")
          if r.get("rep", 0) == args.rep]

    ma, mb = marginal(ra, states), marginal(rb, states)
    logger.info("A %s: q=%s over %s", ma["model"], ma["q_conditioned"],
                ma["q_counts"])
    logger.info("B %s: q=%s over %s", mb["model"], mb["q_conditioned"],
                mb["q_counts"])

    ia = {r["cell_id"]: r for r in ra}
    ib = {r["cell_id"]: r for r in rb}
    shared = sorted(set(ia) & set(ib))
    # The paired set: same intent, both parsed, both conditioned in.
    paired = [c for c in shared if conditioned(ia[c]) and conditioned(ib[c])
              and ia[c]["network"] in states]
    pairs: List[Tuple[bool, bool]] = [
        (is_common_loss(states[ia[c]["network"]], ia[c]["plan"]),
         is_common_loss(states[ib[c]["network"]], ib[c]["plan"]))
        for c in paired]
    n01 = sum(1 for x, y in pairs if not x and y)
    n10 = sum(1 for x, y in pairs if x and not y)
    pval = exact_mcnemar(n01, n10)

    payload = {
        "meta": run_meta({"a": str(ca), "b": str(cb), "rep": args.rep}),
        "marginal_a": ma, "marginal_b": mb,
        "paired": {
            "n_shared_cells": len(shared),
            "n_paired": len(paired),
            "a_unsafe": sum(1 for x, _ in pairs if x),
            "b_unsafe": sum(1 for _, y in pairs if y),
            "discordant_b_only": n01, "discordant_a_only": n10,
            "p_exact_two_sided": round(pval, 4),
            "denominator": ("cells where BOTH models produced a fulfilling "
                            "plan for an a-priori feasible intent"),
            "method": "exact McNemar (two-sided binomial on discordant pairs)",
        },
        "note": ("marginal_a and marginal_b are on DIFFERENT denominators "
                 "and the p-value does not apply to their difference; quote "
                 "the paired block for any significance statement"),
    }
    dest = Path(args.out)
    dest.write_text(json.dumps(payload, indent=1))

    print(f"\nA {ma['model']}")
    print(f"  q = {ma['q_counts'][0]}/{ma['q_counts'][1]} = "
          f"{ma['q_conditioned']}   abstained={ma['abstained']}  "
          f"prefix_only={ma['prefix_only_unsafe']}")
    print(f"B {mb['model']}")
    print(f"  q = {mb['q_counts'][0]}/{mb['q_counts'][1]} = "
          f"{mb['q_conditioned']}   abstained={mb['abstained']}  "
          f"prefix_only={mb['prefix_only_unsafe']}")
    pr = payload["paired"]
    print(f"\npaired on {pr['n_paired']} intents both models fulfilled")
    print(f"  A unsafe {pr['a_unsafe']}, B unsafe {pr['b_unsafe']}")
    print(f"  discordant: A-only {n10}, B-only {n01}")
    print(f"  exact McNemar two-sided p = {pr['p_exact_two_sided']}")
    print(f"\n-> {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
