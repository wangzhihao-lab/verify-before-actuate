"""End-to-end verify-before-actuate MVP.

Full closed loop per intent:
  generate -> freeze(sigma) -> SMT-verify(e,m,b) -> [REJECT: counterexample
  -> repair] -> re-verify -> ACCEPT & intent-fulfilled -> actuate, else ABORT.

Produces a complete, saved trace (arXiv-gate: >=1 end-to-end repair trace with
intent fulfillment). Verification uses the SMT mode (m=SMT); switch VERIFY to
twin_verify for the twin path.

Usage: uv run python mvp.py [--n 6] [--model haiku] [--rounds 3] [--bare]
"""
from __future__ import annotations

import argparse
import json
import random
import subprocess
import time
from pathlib import Path

from run_q import DIFF
from src.agent import (SessionLimit, build_prompt, call_claude, extract_plan)
from src.intents import KINDS, gen_intent, intent_fulfilled
from src.invariants import check_plan
from src.smt_verify import smt_verify
from src.netmodel import apply_op, gen_topology

REPAIR = """Your previous plan was REJECTED by the pre-execution verifier.

Intent: {intent}

Previous plan:
{plan}

Verifier counterexample: at step {step}, invariant class {cls} is violated
({detail}). Invariants are checked after every step; fix the ORDER or the
values. Respond with ONLY a corrected JSON array of operations.
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=6)
    ap.add_argument("--model", default="haiku")
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--bare", action="store_true")
    ap.add_argument("--e", default="prefix")
    ap.add_argument("--b", type=int, default=3)
    ap.add_argument("--seed_bad", action="store_true",
                    help="seed round 0 with a plausible-but-violating plan "
                         "(overload the target) so the repair leg is "
                         "exercised deterministically with a real agent fix")
    args = ap.parse_args()
    guarded = not args.bare

    base = gen_topology(random.Random(42), **DIFF["hard"])
    rng = random.Random(42)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    out_dir = Path("out") / f"mvp_{args.model}_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "base_state.json").write_text(base.to_json())
    try:
        sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True,
                             cwd=Path(__file__).resolve().parent.parent
                             ).stdout.strip() or "nogit"
    except Exception:
        sha = "nogit"
    from src.agent import provenance
    (out_dir / "run_meta.json").write_text(json.dumps(
        {"model": args.model, "commit_sha": sha, "e": args.e, "b": args.b,
         "rounds": args.rounds, "seed_bad": args.seed_bad,
         "bare": args.bare, "n": args.n,
         "provenance": provenance(args.model)}, indent=1))

    traces = []
    fh = (out_dir / "traces.jsonl").open("w")
    for i in range(args.n):
        if args.seed_bad:
            # deterministic repair-leg demo: build a maintenance intent by
            # hand (gen_intent's maintenance filter is too strict for dense
            # topologies). Pick a node that transits >=1 flow mid-path AND
            # whose transit flows are all reroutable avoiding it. The naive
            # seed plan disables it first (WRONG ORDER) -> prefix verify
            # REJECTS (I3 flow_via_disabled); the fix (reroute-then-disable)
            # is feasible by construction.
            kind = "maintenance"
            # pick the feasibly-reroutable transit node with the FEWEST
            # affected flows (easiest repair -> a clean converging demo).
            feas = []
            for n in sorted(base.nodes):
                aff = [f for f, ff in base.flows.items()
                       if n in ff["path"][1:-1]]
                if aff and all(base.shortest_path(
                        base.flows[f]["path"][0], base.flows[f]["path"][-1],
                        avoid={n}) for f in aff):
                    feas.append((len(aff), n))
            if not feas:
                print("no feasible maintenance node"); continue
            nid = min(feas)[1]
            intent = {"kind": "maintenance", "node": nid, "tight": True,
                      "text": (f"Take node {nid} out of service for "
                               f"maintenance (disable it). "
                               + ("" if not guarded else "No flow may "
                                  "traverse a disabled node at any point, and "
                                  "every flow's SLA must still hold; reroute "
                                  "affected flows BEFORE disabling."))}
        else:
            kind = KINDS[i % len(KINDS)]
            intent = gen_intent(base, rng, kind, guarded=guarded)
        trace = {"i": i, "kind": kind, "intent": intent["text"],
                 "rounds": [], "outcome": None}
        ce = None
        prev_plan = None
        try:
            for k in range(args.rounds + 1):
                # optional deterministic seeding of a violating first plan:
                # a naive "just set the target bandwidth" that overloads a
                # link (a realistic agent mistake) — forces the repair leg.
                seed = (k == 0 and args.seed_bad and kind == "maintenance"
                        and "node" in intent)
                if seed:
                    # wrong order: disable first (flows still traverse it)
                    plan = [{"op": "disable_node", "node": intent["node"]}]
                    gen_s = 0.0
                    trace["seeded_bad_round0"] = True
                else:
                    if k == 0:
                        prompt = build_prompt(base, intent["text"],
                                              guardrail=guarded)
                    else:
                        prompt = (build_prompt(base, intent["text"],
                                               guardrail=guarded) + "\n\n"
                                  + REPAIR.format(intent=intent["text"],
                                                  plan=json.dumps(prev_plan),
                                                  step=ce.get("step"),
                                                  cls=ce.get("cls"),
                                                  detail=ce.get("detail", "")))
                    raw, gen_s = call_claude(prompt, args.model)
                    plan = extract_plan(raw)
                if plan is None:
                    trace["rounds"].append(
                        {"k": k, "parse_ok": False, "gen_s": round(gen_s, 2)})
                    trace["outcome"] = "PARSE_FAIL"
                    break
                outcome, ce, tau = smt_verify(base, plan, e=args.e, b=args.b)
                fulfilled = intent_fulfilled(base, intent, plan)
                trace["rounds"].append(
                    {"k": k, "n_ops": len(plan), "gen_s": round(gen_s, 2),
                     "verify": outcome, "tau_ms": round(tau * 1e3, 2),
                     "ce": ce, "fulfilled": fulfilled, "plan": plan,
                     "raw_head": (raw[:500] if not seed else "SEEDED_BAD")})
                prev_plan = plan
                if outcome == "ACCEPT":
                    # gate: actuate ONLY when fulfillment is certain (True).
                    # None (unknown, missing intent meta) or False must NOT
                    # actuate.
                    if fulfilled is True:
                        # ACTUATE FOR REAL: apply sigma to a clone, collecting
                        # apply_op errors + per-prefix realized-state
                        # violations ON THE ACTUAL post object during the same
                        # execution loop (not a separate re-simulation).
                        import hashlib
                        from src.invariants import check_state
                        post = base.clone()
                        realized_viols = []
                        for j, op in enumerate(plan):
                            errs = apply_op(post, op)
                            for e_ in errs:
                                realized_viols.append(
                                    {"cls": "I3", "kind": "structural",
                                     "step": j, "detail": e_})
                            for v in check_state(post):
                                realized_viols.append({**v, "step": j})
                        pre_h = hashlib.sha256(
                            base.to_json().encode()).hexdigest()[:12]
                        post_h = hashlib.sha256(
                            post.to_json().encode()).hexdigest()[:12]
                        post_fulfilled = intent_fulfilled(base, intent, plan)
                        trace["actuation"] = {
                            "applied": True, "pre_hash": pre_h,
                            "post_hash": post_h,
                            "realized_violations": realized_viols,
                            "post_fulfilled": post_fulfilled,
                            "sound": (len(realized_viols) == 0
                                      and post_fulfilled is True)}
                        trace["outcome"] = ("ACTUATE"
                                            if not realized_viols
                                            else "ACTUATE_UNSOUND")
                    else:
                        trace["outcome"] = "ACCEPT_UNFULFILLED_NO_ACTUATE"
                    break
            else:
                trace["outcome"] = "ABORT_REPAIR_BUDGET"  # repair-count, not
                #                     a real deadline (see D4 §III deadline ext)
        except SessionLimit as e:
            print(f"!! session limit at intent {i}"); trace["outcome"] = "QUOTA"
            traces.append(trace); fh.write(json.dumps(trace) + "\n"); break
        except subprocess.TimeoutExpired:
            trace["outcome"] = "TIMEOUT"
        traces.append(trace)
        fh.write(json.dumps(trace) + "\n"); fh.flush()
        nr = len(trace["rounds"])
        print(f"[{i}] {kind:<11} rounds={nr} outcome={trace['outcome']}")
    fh.close()

    outc = {}
    for t in traces:
        outc[t["outcome"]] = outc.get(t["outcome"], 0) + 1
    repaired = sum(1 for t in traces if any(
        r.get("verify") == "REJECT" for r in t["rounds"])
        and t["outcome"] == "ACTUATE")
    summary = (f"n={len(traces)} outcomes={outc} "
               f"repaired_then_actuated={repaired}")
    (out_dir / "summary.txt").write_text(summary + "\n")
    print("\n" + summary + f"\n-> {out_dir}")


if __name__ == "__main__":
    main()
