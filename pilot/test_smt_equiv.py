"""Equivalence test: SMT verdict == ground-truth checker on covered fragments.

For random states, injected violations, and real agent plans, the SMT
verifier at (e=prefix, b=3) must ACCEPT exactly when check_plan finds no
violation, and REJECT otherwise. At lower b it must match the checker
restricted to the covered invariant classes.
"""
from __future__ import annotations

import random
import sys

from run_p_inject import build_injections
from src.invariants import check_plan
from src.netmodel import gen_topology
from src.smt_verify import smt_verify

CLASSES = {1: ("I1",), 2: ("I1", "I2"), 3: ("I1", "I2", "I3")}


def checker_says_bad(base, plan, e, b):
    """Ground truth restricted to (e, covered classes)."""
    covered = CLASSES[b]
    if e == "prefix":
        viols = check_plan(base, plan)
    else:  # terminal: only final-state violations (re-simulate, check last)
        full = check_plan(base, plan)
        last = len(plan) - 1
        viols = [v for v in full
                 if v.get("step") == last or v["kind"] == "structural"]
    return any(v["cls"] in covered for v in viols)


def make_random_plans(base, rng, n=40):
    ops = []
    flows = list(base.flows)
    nodes = list(base.nodes)
    links = list(base.links)
    for _ in range(n):
        plan = []
        for _ in range(rng.randint(1, 5)):
            k = rng.choice(["set_flow_bw", "reroute_flow", "scale_vnf",
                            "reserve_slice", "disable_node", "add_acl"])
            if k == "set_flow_bw":
                plan.append({"op": k, "flow": rng.choice(flows),
                             "bw_mbps": rng.choice([5, 50, 200, 500])})
            elif k == "reroute_flow":
                f = rng.choice(flows)
                p = base.flows[f]["path"]
                plan.append({"op": k, "flow": f, "path": p})  # identity-ish
            elif k == "scale_vnf":
                plan.append({"op": k, "node": rng.choice(nodes),
                             "replicas": rng.choice([1, 5, 20])})
            elif k == "reserve_slice":
                plan.append({"op": k, "slice": "SX",
                             "links": [rng.choice(links)],
                             "bw_mbps": rng.choice([10, 200, 400])})
            elif k == "disable_node":
                plan.append({"op": k, "node": rng.choice(nodes)})
            elif k == "add_acl":
                plan.append({"op": k, "rule_id": "AX",
                             "src": "10.0.1.0/24", "dst": "10.0.2.0/24",
                             "action": rng.choice(["allow", "deny"])})
        ops.append(plan)
    return ops


def main() -> int:
    rng = random.Random(123)
    total, mism = 0, 0
    for seed in range(1, 9):
        base = gen_topology(random.Random(seed), 24, 14, 40)
        plans = make_random_plans(base, rng, 40)
        plans += [p for _, p in build_injections(base)]
        for plan in plans:
            for e in ("prefix", "term"):
                for b in (1, 2, 3):
                    outcome, ce, _ = smt_verify(base, plan, e=e, b=b)
                    smt_bad = outcome == "REJECT"
                    gt_bad = checker_says_bad(base, plan, e, b)
                    total += 1
                    if smt_bad != gt_bad:
                        mism += 1
                        if mism <= 5:
                            print(f"  MISMATCH seed{seed} e={e} b={b}: "
                                  f"smt={outcome} gt_bad={gt_bad} "
                                  f"plan={plan}")
    print(f"\nchecked {total} (state,e,b) verdicts, mismatches={mism}")
    print("PASS" if mism == 0 else "FAIL")
    return 0 if mism == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
