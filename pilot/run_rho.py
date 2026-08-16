"""Pilot experiment RHO: counterexample-guided repair convergence.

Takes violating plans from a run_q results dir, feeds the verifier's
violation report back to the agent (up to K rounds), and measures the
per-round violation rate. This is the empirical analogue of the theory's
repair loop: does q_k decrease across rounds (rho<1), or does the agent
mode-collapse / regenerate the same blind-spot defect (A0 breakdown, §6.5)?

Usage:
  uv run python run_rho.py out/q_<...>  [--model haiku] [--rounds 3]
"""
from __future__ import annotations

import argparse
import json
import random
import subprocess
import time
from pathlib import Path
from typing import List, Optional

from run_p import load_state
from src.agent import (SessionLimit, build_prompt, call_claude, extract_plan)
from src.intents import intent_fulfilled
from src.invariants import check_plan, summarize
from src.netmodel import NetState


REPAIR_TMPL = """Your previous plan for this intent VIOLATED network invariants.

Intent: {intent}

Your previous plan:
{plan}

The verifier found these violations (each with the 0-based step index at
which it occurred):
{viols}

Produce a CORRECTED plan that fulfils the intent AND keeps every invariant
satisfied after every step. Respond with ONLY a JSON array of operations.
"""


def fmt_viols(viols: List[dict]) -> str:
    return "\n".join(f"  - step {v.get('step','?')}: [{v['cls']}] "
                     f"{v.get('kind','')} {v.get('detail','')}".rstrip()
                     for v in viols[:20])


def repair_once(base: NetState, intent_text: str, prev_plan: list,
                viols: List[dict], model: str,
                timeout: int) -> tuple[Optional[list], float, str]:
    prompt = (build_prompt(base, intent_text) + "\n\n"
              + REPAIR_TMPL.format(intent=intent_text,
                                   plan=json.dumps(prev_plan),
                                   viols=fmt_viols(viols)))
    raw, dt = call_claude(prompt, model, timeout)
    return extract_plan(raw), dt, raw


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--model", default="haiku")
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--timeout", type=int, default=180)
    args = ap.parse_args()

    run_dir = Path(args.run_dir)
    base = load_state(run_dir / "base_state.json")
    recs = [json.loads(l) for l in
            (run_dir / "results.jsonl").read_text().splitlines()]
    bad = [r for r in recs if r.get("parse_ok") and r.get("violated")]
    print(f"violating plans to repair: {len(bad)}")
    if not bad:
        print("nothing to repair")
        return

    out = run_dir / f"rho_{args.model}.jsonl"
    fh = out.open("w")
    # round 0 = original; track violation status per round
    round_violated = [0] * (args.rounds + 1)
    round_total = [0] * (args.rounds + 1)
    signatures: List[set] = []  # per-item defect signature history

    for r in bad:
        intent = r["intent"]
        plan_intent = r.get("intent_meta")  # None for pre-fix runs
        plan = r["plan"]
        viols = r["viols"]
        hist = {"i": r["i"], "kind": r["kind"], "rounds": []}
        round_violated[0] += 1
        round_total[0] += 1
        sig_hist = {_sig(viols)}
        try:
            for k in range(1, args.rounds + 1):
                round_total[k] += 1
                try:
                    new_plan, dt, raw = repair_once(
                        base, intent, plan, viols, args.model, args.timeout)
                except subprocess.TimeoutExpired:
                    hist["rounds"].append({"k": k, "timeout": True})
                    round_violated[k] += 1  # timed out = unresolved
                    break
                if new_plan is None:
                    hist["rounds"].append({"k": k, "parse_ok": False})
                    round_violated[k] += 1  # unparseable = unresolved
                    break
                viols = check_plan(base, new_plan)
                # a plan that is empty or a no-op does NOT count as a repair:
                # it must actually fulfil the intent (oracle) AND be clean.
                # fulfilled is None when intent metadata is absent (old runs)
                # -> we then cannot certify a repair, so it is NOT resolved.
                fulfilled = intent_fulfilled(base, plan_intent, new_plan)
                bad_now = (bool(viols) or len(new_plan) == 0
                           or fulfilled is not True)
                if bad_now:
                    round_violated[k] += 1
                hist["rounds"].append(
                    {"k": k, "parse_ok": True, "violated": bool(viols),
                     "fulfilled": fulfilled, "n_ops": len(new_plan),
                     "resolved": not bad_now,
                     "by_class": summarize(viols), "gen_s": round(dt, 2),
                     "sig": _sig(viols), "plan": new_plan,
                     "raw_head": raw[:400]})
                sig_hist.add(_sig(viols))
                plan = new_plan
                if not bad_now:
                    break
        except SessionLimit as e:
            print(f"!! SESSION LIMIT at item {r['i']}: {e}")
            fh.write(json.dumps(hist) + "\n")
            break
        signatures.append(sig_hist)
        fh.write(json.dumps(hist) + "\n")
        fh.flush()
        tail = hist["rounds"][-1] if hist["rounds"] else {}
        print(f"[{r['i']}] {r['kind']:<12} rounds={len(hist['rounds'])} "
              f"final_violated={tail.get('violated', 'NA')}")
    fh.close()

    print("\nper-round violation rate (q_k):")
    for k in range(args.rounds + 1):
        if round_total[k]:
            print(f"  round {k}: {round_violated[k]}/{round_total[k]} "
                  f"= {round_violated[k] / round_total[k]:.2f}")
    # blind-spot persistence: same defect signature recurring across rounds
    persist = sum(1 for s in signatures if len(s) == 1
                  and list(s)[0] != frozenset())
    print(f"same-signature-persistence (A0 breakdown candidates): "
          f"{persist}/{len(signatures)}")
    print(f"-> {out}")


def _sig(viols: List[dict]) -> str:
    return json.dumps(sorted({(v['cls'], v.get('kind', '')) for v in viols}))


if __name__ == "__main__":
    main()
