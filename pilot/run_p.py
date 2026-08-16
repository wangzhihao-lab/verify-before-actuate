"""Pilot experiment P: detection probability p(d) vs verification depth.

Depth levels (monotone coverage chain, mirroring the theory's p(d)):
  L1  final-state only, I1
  L2  final-state only, I1+I2
  L3  final-state only, I1+I2+I3 (incl. structural errors)
  L4  every-step, I1+I2+I3  (= ground truth used for q)

Violating plans come from a run_q results.jsonl (real agent mistakes),
so p(d) is measured on the actual violation distribution.

Usage: uv run python run_p.py out/q_YYYYmmdd_HHMMSS/results.jsonl
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path
from typing import List

from src.invariants import check_state
from src.netmodel import NetState, apply_op


def load_state(path: Path) -> NetState:
    d = json.loads(path.read_text())
    return NetState(nodes=d["nodes"], links=d["links"], flows=d["flows"],
                    acls=d["acls"], slices=d["slices"])


def detect(base: NetState, plan: List[dict], level: int) -> bool:
    """True iff verification at this depth level flags the plan."""
    st = base.clone()
    classes = {1: ("I1",), 2: ("I1", "I2"), 3: ("I1", "I2", "I3"),
               4: ("I1", "I2", "I3")}[level]
    per_step = level >= 4
    for op in plan:
        errs = apply_op(st, op)
        if errs and "I3" in classes:
            return True
        if per_step and any(v["cls"] in classes for v in check_state(st)):
            return True
    return any(v["cls"] in classes for v in check_state(st))


def main() -> None:
    res_path = Path(sys.argv[1])
    base = load_state(res_path.parent / "base_state.json")
    recs = [json.loads(l) for l in res_path.read_text().splitlines()]
    bad = [r for r in recs if r.get("parse_ok") and r.get("violated")]
    clean = [r for r in recs if r.get("parse_ok") and not r.get("violated")]
    print(f"violating plans: {len(bad)}, clean plans: {len(clean)}")
    if not bad:
        print("no violating plans; nothing to measure")
        return

    print(f"{'level':>6} {'p(d) det/total':>16} {'false-flag on clean':>20}")
    rows = []
    for lv in (1, 2, 3, 4):
        det = sum(detect(base, r["plan"], lv) for r in bad)
        ff = sum(detect(base, r["plan"], lv) for r in clean)
        rows.append({"level": lv, "detected": det, "total": len(bad),
                     "false_flag": ff, "clean_total": len(clean)})
        print(f"{lv:>6} {det:>7}/{len(bad):<8} {ff:>10}/{len(clean):<9}")
    out = res_path.parent / "p_of_d.json"
    out.write_text(json.dumps(rows, indent=1))
    print(f"-> {out}")


if __name__ == "__main__":
    main()
