"""Summarise the temporal-order stress suite into a freezable record.

The suite exists to answer one question the natural corpus cannot: when a
terminal-safe/prefix-unsafe plan is KNOWN to exist in an instance's plan
space, does the agent produce one? Every instance carries a constructive
witness pair -- a right order that is safe at every prefix, and a wrong order
that violates an invariant at an intermediate state and recovers by the end
-- so a zero here is a statement about the agent's error distribution rather
than about the intents.

Reported separately from the natural corpus on purpose. Pooling the two would
manufacture exactly the prefix advantage the natural corpus declined to show.

    PYTHONPATH=. .venv/bin/python run_temporal_analyze.py out/temporal_v2
"""
from __future__ import annotations

import argparse
import collections
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

from src.exp.analyze import load_records, load_states, rule_of_three_upper, usable
from src.provenance import run_meta
from src.semantics import is_unsafe

logger = logging.getLogger("run_temporal_analyze")


def ordering_evidence(rec: Dict[str, Any]) -> str:
    """Did the plan emit both ordered operations, and in which order?

    A plan that drops one of the two operations cannot exhibit a transient
    violation at all: the omission is still present in the final state, so a
    terminal checker sees it. Separating omission from misordering is what
    makes the zero interpretable.
    """
    meta = rec.get("intent_meta") or {}
    right = meta.get("witness_right_order") or []
    if len(right) < 2 or not rec.get("plan"):
        return "n/a"
    # Match on OPERATION TYPE, not on the witness's identifiers: the agent
    # names its own rules and picks its own intermediate paths, so requiring
    # the witness's exact ids would score a correct plan as an omission.
    ops = [op.get("op") for op in rec["plan"]]
    want = [op.get("op") for op in right]
    if len(set(want)) < len(want):        # repeated op type: ids are needed
        return "ambiguous"
    idx = [ops.index(w) if w in ops else -1 for w in want]
    if any(i < 0 for i in idx):
        return "omitted"
    return "correct_order" if idx == sorted(idx) else "wrong_order"


def main(argv: List[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("corpus")
    p.add_argument("--out", default="")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                        format="%(levelname)-7s %(message)s")

    corpus = Path(args.corpus)
    records = load_records(corpus / "records.jsonl")
    states = load_states(corpus / "states")
    ok = [r for r in records if usable(r) and r["network"] in states]

    prefix_only = term_only = 0
    for rec in ok:
        st = states[rec["network"]]
        pre = is_unsafe(st, rec["plan"], "prefix", 3)
        ter = is_unsafe(st, rec["plan"], "term", 3)
        prefix_only += pre and not ter
        term_only += ter and not pre

    order = collections.Counter(ordering_evidence(r) for r in ok)
    by_kind: Dict[str, Dict[str, int]] = {}
    for rec in ok:
        cell = by_kind.setdefault(rec["kind"], collections.Counter())
        cell[ordering_evidence(rec)] += 1

    payload = {
        "meta": run_meta({"corpus": str(corpus)}),
        "n_records": len(records), "n_usable": len(ok),
        "prefix_only_unsafe": prefix_only,
        "terminal_only_unsafe": term_only,
        "prefix_only_upper95": round(rule_of_three_upper(len(ok)), 5)
        if prefix_only == 0 else None,
        "ordering": dict(order),
        "ordering_by_kind": {k: dict(v) for k, v in sorted(by_kind.items())},
        "abstained": sum(1 for r in ok if r.get("abstained")),
        "fulfilled": sum(1 for r in ok if r.get("fulfilled")),
        "note": ("every instance was emitted only after a constructive check "
                 "that a prefix-safe fulfilling order exists AND that the "
                 "natural wrong order violates at an intermediate state while "
                 "ending safe; a prefix-only plan is therefore reachable in "
                 "every instance's plan space"),
    }
    dest = Path(args.out) if args.out else corpus / "summary.json"
    dest.write_text(json.dumps(payload, indent=1))

    print(f"\nusable plans          {len(ok)} of {len(records)}")
    print(f"prefix-only unsafe    {prefix_only}"
          f"   (95% upper {payload['prefix_only_upper95']})")
    print(f"terminal-only unsafe  {term_only}")
    print(f"abstained             {payload['abstained']}")
    print(f"\nordering evidence     {dict(order)}")
    for kind, cell in payload["ordering_by_kind"].items():
        print(f"  {kind:<18}{cell}")
    print(f"\n-> {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
