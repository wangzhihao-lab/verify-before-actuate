"""Aggregate a policy sweep into the head-to-head table.

    PYTHONPATH=. .venv/bin/python run_analyze_policies.py out/policies
    PYTHONPATH=. .venv/bin/python run_analyze_policies.py out/policies \
        --group kind
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from src.exp.analyze_policies import analyze_policies, report
from src.provenance import run_meta

logger = logging.getLogger("run_analyze_policies")

GROUPERS = {
    "none": None,
    "kind": lambda t: t.get("kind", "?"),
    "guard": lambda t: "guarded" if t.get("guarded") else "bare",
    "network": lambda t: t.get("network", "?"),
    # Three groups. The certified verdict decides it where one exists,
    # because the a-priori label put requests admitting no safe plan into the
    # group where completing the intent is the right outcome.
    "feasible": lambda t: t.get("feasibility") or (
        "feasible" if (t.get("intent_meta") or {}).get(
            "expected_feasible", True) else "infeasible"),
}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("policy_dir")
    p.add_argument("--group", default="none", choices=sorted(GROUPERS))
    p.add_argument("--out", default="")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                        format="%(levelname)-7s %(message)s")

    pdir = Path(args.policy_dir)
    res = analyze_policies(pdir / "traces.jsonl", GROUPERS[args.group])
    res["meta"] = run_meta({"policy_dir": str(pdir), "group": args.group})

    dest = Path(args.out) if args.out else pdir / "policy_analysis.json"
    dest.write_text(json.dumps(res, indent=1))
    report(res)

    if "by_group" in res:
        for bucket, policies in sorted(res["by_group"].items()):
            print(f"\n=== group: {bucket}")
            report({"n_traces": sum(s.get("n", 0)
                                    for s in policies.values()),
                    "policies": policies})
    print(f"\n-> {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
