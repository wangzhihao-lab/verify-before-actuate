"""Temporal-order stress suite: generation, labelling, separate reporting.

Kept apart from the natural corpus on purpose. These intents are constructed
so that a correct operation order exists and the natural wrong order produces
a violation that is visible only at an intermediate state. Mixing them into
the natural violation rate would manufacture exactly the prefix advantage the
natural corpus declined to show.

    PYTHONPATH=. .venv/bin/python run_temporal.py --out out/temporal_qwen
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import random
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List

from src.agent import build_prompt, extract_plan, strip_reasoning
from src.backends import (AgentSpec, BackendUnavailable, QuotaExhausted,
                          build_backend)
from src.exp.corpus import DEFAULT_NETWORKS
from src.exp.temporal_intents import TEMPORAL_KINDS, make_temporal_intent
from src.intents import intent_fulfilled
from src.provenance import run_meta, stamp
from src.semantics import BUDGETS, SCOPES, is_common_loss, is_unsafe
from src.topo import TopoSpec, build_topology

logger = logging.getLogger("run_temporal")


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--backend", default="ollama",
                   choices=("ollama", "claude_cli", "lmstudio"))
    p.add_argument("--model", default="qwen2.5:7b-instruct-q8_0")
    p.add_argument("--host", default="http://127.0.0.1:11434")
    p.add_argument("--timeout", type=int, default=900)
    p.add_argument("--networks", nargs="+", default=list(DEFAULT_NETWORKS))
    p.add_argument("--kinds", nargs="+", default=list(TEMPORAL_KINDS))
    p.add_argument("--reps", type=int, default=3)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--max-flows", type=int, default=40)
    p.add_argument("--out", default="")
    return p.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                        format="%(asctime)s %(levelname)-7s %(message)s",
                        datefmt="%H:%M:%S")

    spec = AgentSpec(backend=args.backend, model=args.model, host=args.host,
                     timeout=args.timeout)
    backend = build_backend(spec)
    try:
        backend.healthcheck()
    except BackendUnavailable as exc:
        logger.error("backend unavailable: %s", exc)
        return 4

    out_dir = Path(args.out) if args.out else Path("out") / f"temporal_{stamp()}"
    out_dir.mkdir(parents=True, exist_ok=True)
    records_path = out_dir / "records.jsonl"
    done = set()
    if records_path.exists():
        for line in records_path.read_text().splitlines():
            if line.strip():
                done.add(json.loads(line)["cell_id"])

    states = {n: build_topology(TopoSpec(backend="sndlib", name=n,
                                         seed=args.seed,
                                         max_flows=args.max_flows))
              for n in args.networks}
    (out_dir / "states").mkdir(exist_ok=True)
    for n, st in states.items():
        (out_dir / "states" / f"{n}.json").write_text(st.to_json())

    meta = run_meta({"suite": "temporal", "config": vars(args),
                     "backend_provenance": backend.provenance()})
    (out_dir / "config.json").write_text(json.dumps(meta, indent=1))

    n_ok = n_skip = 0
    with records_path.open("a") as fh:
        for net in args.networks:
            st = states[net]
            for kind in args.kinds:
                for rep in range(args.reps):
                    cell_id = f"{net}|{kind}|{rep}"
                    if cell_id in done:
                        continue
                    for guarded in (True, False):
                        cid = f"{cell_id}|{'guarded' if guarded else 'bare'}"
                        if cid in done:
                            continue
                        rng = random.Random(f"{args.seed}|{net}|{kind}|{rep}")
                        got = make_temporal_intent(st, rng, kind, guarded)
                        if got is None:
                            n_skip += 1
                            continue
                        intent, imeta = got
                        prompt = build_prompt(st, intent["text"], guarded)
                        # SHA-256, not the Python builtin: hash() of a str is
                        # salted per interpreter process, so a rerun without
                        # PYTHONHASHSEED pinned would draw different seeds and
                        # this suite would not be replayable at all.
                        seed = int(hashlib.sha256(
                            f"{args.seed}|{cid}".encode()).hexdigest()[:8], 16)
                        try:
                            res = backend.generate(prompt, seed=seed)
                        except (QuotaExhausted, BackendUnavailable) as exc:
                            logger.error("stopping: %s", exc)
                            return 2
                        plan = extract_plan(strip_reasoning(res.text))
                        rec: Dict[str, Any] = {
                            "cell_id": cid, "network": net, "kind": kind,
                            "rep": rep, "guarded": guarded,
                            "suite": "temporal", "intent": intent,
                            "intent_meta": imeta, "gen_seed": seed,
                            "gen_seconds": round(res.wall_s, 3),
                            "raw_response": res.text,
                            "prompt_tokens": res.prompt_tokens,
                            "gen_tokens": res.gen_tokens,
                            "parse_ok": plan is not None, "plan": plan,
                        }
                        if plan is not None:
                            rec.update({
                                "plan_len": len(plan),
                                "abstained": len(plan) == 0,
                                "fulfilled": intent_fulfilled(st, intent, plan),
                                "common_loss": is_common_loss(st, plan),
                                "unsafe": {
                                    f"{e}_b{b}": is_unsafe(st, plan, e, b)
                                    for e in SCOPES for b in BUDGETS},
                            })
                        fh.write(json.dumps(rec) + "\n")
                        fh.flush()
                        n_ok += 1
                        if n_ok % 10 == 0:
                            logger.info("generated %d (skipped %d)",
                                        n_ok, n_skip)

    logger.info("done: %d records, %d cells skipped (topology admits no "
                "valid instance of that class)", n_ok, n_skip)
    return 0


if __name__ == "__main__":
    sys.exit(main())
