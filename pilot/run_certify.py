"""Certify the feasibility of every intent in a corpus.

Replaces an a-priori label with a decided one. The label the corpus was
generated under was asserted for two of the five intent kinds rather than
established, and the assertion was false often enough to move the headline
rate: a bandwidth target can exceed the capacity of every path between its
endpoints, and a slice can reserve more than a link physically has.

Output is per cell and offline -- feasibility is a property of (state,
intent), so deciding it needs no agent and no regeneration.

    PYTHONPATH=. .venv/bin/python run_certify.py --corpus out/corpus_v2
"""
from __future__ import annotations

import argparse
import collections
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

from src.exp.analyze import load_records, load_states
from src.exp.feasibility import FEASIBLE, INFEASIBLE, UNKNOWN, certify
from src.provenance import run_meta

logger = logging.getLogger("run_certify")


def main(argv: List[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--corpus", default="out/corpus_v2")
    p.add_argument("--out", default="")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                        format="%(levelname)-7s %(message)s")

    corpus = Path(args.corpus)
    records = load_records(corpus / "records.jsonl")
    states = load_states(corpus / "states")

    # One verdict per distinct (network, intent), not per record: the same
    # intent appears under both prompt variants and every repetition, and
    # feasibility does not depend on either.
    verdicts: Dict[str, Dict[str, Any]] = {}
    by_cell: Dict[str, str] = {}
    agree = collections.Counter()
    per_kind: Dict[str, collections.Counter] = collections.defaultdict(
        collections.Counter)

    for rec in records:
        st = states.get(rec["network"])
        if st is None:
            continue
        intent = rec.get("intent") or {}
        key = f"{rec['network']}|{json.dumps(intent, sort_keys=True)}"
        if key not in verdicts:
            verdicts[key] = certify(st, intent)
        res = verdicts[key]
        by_cell[rec["cell_id"]] = res["verdict"]
        kind = intent.get("kind", "?")
        per_kind[kind][res["verdict"]] += 1
        prior = bool((rec.get("intent_meta") or {}).get("expected_feasible"))
        agree[(prior, res["verdict"])] += 1

    disagreements = [
        {"cell_id": cid, "prior": bool((r.get("intent_meta") or {})
                                       .get("expected_feasible")),
         "verdict": by_cell[cid],
         "reason": verdicts[f"{r['network']}|"
                            f"{json.dumps(r.get('intent') or {}, sort_keys=True)}"]
         ["reason"]}
        for r in records
        for cid in [r["cell_id"]]
        if cid in by_cell
        and bool((r.get("intent_meta") or {}).get("expected_feasible"))
        != (by_cell[cid] == FEASIBLE)]

    payload = {
        "meta": run_meta({"corpus": str(corpus)}),
        "n_records": len(records),
        "n_distinct_intents": len(verdicts),
        "verdict_by_cell": by_cell,
        "counts": collections.Counter(by_cell.values()),
        "counts_by_kind": {k: dict(v) for k, v in sorted(per_kind.items())},
        "n_disagreeing_with_prior_label": len(disagreements),
        "disagreements": disagreements,
        "note": ("a FEASIBLE verdict carries a witness plan that fulfils the "
                 "intent and satisfies every modelled invariant at every "
                 "prefix; INFEASIBLE means a necessary condition fails; "
                 "UNKNOWN means neither, and must not be pooled with either"),
    }
    dest = Path(args.out) if args.out else corpus / "feasibility.json"
    dest.write_text(json.dumps(payload, indent=1, default=dict))

    print(f"\ndistinct intents certified: {len(verdicts)}")
    print(f"{'kind':14}{'feasible':>10}{'infeasible':>12}{'unknown':>9}")
    for kind, c in sorted(per_kind.items()):
        print(f"{kind:14}{c[FEASIBLE]:>10}{c[INFEASIBLE]:>12}{c[UNKNOWN]:>9}")
    tot = collections.Counter(by_cell.values())
    print(f"{'TOTAL':14}{tot[FEASIBLE]:>10}{tot[INFEASIBLE]:>12}"
          f"{tot[UNKNOWN]:>9}")
    print(f"\ncells whose prior label disagrees: {len(disagreements)}")
    seen = set()
    for d in disagreements:
        if d["reason"] in seen:
            continue
        seen.add(d["reason"])
        print(f"  {d['cell_id']:40} prior={d['prior']} -> {d['verdict']}")
        print(f"      {d['reason']}")
    print(f"\n-> {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
