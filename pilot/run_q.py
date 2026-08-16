"""Pilot experiment Q: raw-agent violation rate q (+ generation time G).

Usage:
  uv run python run_q.py --smoke     # 2 intents, sanity
  uv run python run_q.py             # full batch (config below)
"""
from __future__ import annotations

import argparse
import json
import platform
import random
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from src.agent import SessionLimit, build_prompt, call_claude, extract_plan
from src.intents import KINDS, gen_intent
from src.invariants import check_plan, summarize
from src.netmodel import gen_topology


@dataclass(frozen=True)
class Config:
    seed: int = 42
    n_intents: int = 40
    model: str = "sonnet"
    n_nodes: int = 12
    n_chords: int = 6
    n_flows: int = 15
    timeout_s: int = 180
    difficulty: str = "easy"


DIFF = {
    "easy": dict(n_nodes=12, n_chords=6, n_flows=15),
    "hard": dict(n_nodes=24, n_chords=14, n_flows=40),
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--model", default="sonnet")
    ap.add_argument("--difficulty", choices=list(DIFF), default="easy")
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--bare", action="store_true",
                    help="omit invariant hand-holding from intent + prompt")
    args = ap.parse_args()

    top = DIFF[args.difficulty]
    cfg = Config(seed=args.seed, n_intents=2 if args.smoke else args.n,
                 model=args.model, difficulty=args.difficulty, **top)
    guarded = not args.bare
    rng = random.Random(cfg.seed)
    base = gen_topology(rng, cfg.n_nodes, cfg.n_chords, cfg.n_flows)

    stamp = time.strftime("%Y%m%d_%H%M%S")
    tag = "bare" if args.bare else "guard"
    out_dir = Path("out") / f"q_{cfg.model}_{cfg.difficulty}_{tag}_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "config.json").write_text(json.dumps(
        {**asdict(cfg), "python": platform.python_version(),
         "platform": platform.platform()}, indent=1))
    (out_dir / "base_state.json").write_text(base.to_json())

    results = []
    fh = (out_dir / "results.jsonl").open("w")
    for i in range(cfg.n_intents):
        kind = KINDS[i % len(KINDS)]
        intent = gen_intent(base, rng, kind, guarded=guarded)
        prompt = build_prompt(base, intent["text"], guardrail=guarded)
        try:
            raw, gen_s = call_claude(prompt, cfg.model, cfg.timeout_s)
        except SessionLimit as e:
            print(f"\n!! SESSION LIMIT hit at intent {i}: {e}")
            print(f"   stopping early; {len(results)} usable records saved.")
            break
        except Exception as e:  # timeout etc.
            raw, gen_s = f"__CALL_ERROR__ {e}", float(cfg.timeout_s)
        plan = extract_plan(raw)
        rec = {"i": i, "kind": kind, "tight": intent.get("tight"),
               "intent": intent["text"], "intent_meta": intent,
               "gen_s": round(gen_s, 2),
               "parse_ok": plan is not None, "plan": plan}
        if plan is None:
            rec["raw_head"] = raw[:600]
        if plan is not None:
            viols = check_plan(base, plan)
            rec["viols"] = viols
            rec["by_class"] = summarize(viols)
            rec["violated"] = bool(viols)
        fh.write(json.dumps(rec) + "\n")
        fh.flush()
        results.append(rec)
        status = ("PARSE_FAIL" if plan is None
                  else ("VIOLATED " + str(rec["by_class"])
                        if rec["violated"] else "clean"))
        print(f"[{i + 1}/{cfg.n_intents}] {kind:<12} G={gen_s:6.1f}s "
              f"{status}", flush=True)
    fh.close()

    parsed = [r for r in results if r["parse_ok"]]
    violated = [r for r in parsed if r.get("violated")]
    lines = [
        f"n_intents={cfg.n_intents} model={cfg.model} seed={cfg.seed}",
        f"parse_fail={cfg.n_intents - len(parsed)}/{cfg.n_intents}",
        f"q (violated / parsed) = {len(violated)}/{len(parsed)}"
        + (f" = {len(violated) / len(parsed):.2f}" if parsed else ""),
        "by kind: " + json.dumps({
            k: [sum(1 for r in parsed if r['kind'] == k and r['violated']),
                sum(1 for r in parsed if r['kind'] == k)]
            for k in KINDS}),
        "class totals: " + json.dumps({
            c: sum(r["by_class"][c] for r in parsed if r.get("by_class"))
            for c in ("I1", "I2", "I3")}),
        "mean G = {:.1f}s".format(
            sum(r["gen_s"] for r in results) / max(1, len(results))),
    ]
    summary = "\n".join(lines)
    (out_dir / "summary.txt").write_text(summary + "\n")
    print("\n" + summary)
    print(f"\nresults -> {out_dir}")


if __name__ == "__main__":
    sys.exit(main())
