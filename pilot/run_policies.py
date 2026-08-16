"""Head-to-head policy comparison: baselines vs. verify-before-actuate.

Every policy sees the same intents, the same topologies and the same agent,
so differences are attributable to the gate alone.

    PYTHONPATH=. .venv/bin/python run_policies.py --reps 2 --out out/policies

Reruns of the same --out resume; each (cell, policy) pair is recorded once.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List

from src.backends import (AgentSpec, BackendUnavailable, QuotaExhausted,
                          build_backend)
from src.exp.corpus import (DEFAULT_NETWORKS, CorpusConfig, _cell_rng,
                            build_base_states, cell_seed, enumerate_cells)
from src.exp.intent_gen import make_intent
from src.exp.policies import PolicyConfig, run_policy
from src.intents import KINDS
from src.provenance import run_meta, stamp

logger = logging.getLogger("run_policies")

def build_policies(max_rounds: int) -> List[PolicyConfig]:
    """Baselines plus this paper's gate at three profiles.

    Self-reflection appears twice on purpose: once at a single round, the
    usual form of the baseline, and once at the SAME round budget as the
    repair loop. Without the budget-matched variant, any advantage of the
    gate could be an artefact of it simply being allowed more agent calls.
    """
    return [
        PolicyConfig(name="no_verify"),
        PolicyConfig(name="static_rules"),
        PolicyConfig(name="reflect", max_rounds=1),
        PolicyConfig(name="reflect", max_rounds=max_rounds),
        # Scope comparison: identical coverage, differing temporal scope.
        PolicyConfig(name="verify", mode="smt", e="prefix", b=3,
                     max_rounds=max_rounds),
        PolicyConfig(name="verify", mode="smt", e="term", b=3,
                     max_rounds=max_rounds),
        # Coverage-depth ablation.
        PolicyConfig(name="verify", mode="smt", e="prefix", b=1,
                     max_rounds=max_rounds),
        # Feedback-content ablation: same gate, same rounds, but the
        # rejection names only the failing step instead of the failing
        # predicate. Isolates how much of repair's value comes from the
        # counterexample rather than from being rejected at all.
        PolicyConfig(name="verify", mode="smt", e="prefix", b=3,
                     max_rounds=max_rounds, witness=False),
    ]


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--backend", default="ollama",
                   choices=("ollama", "claude_cli", "lmstudio"))
    p.add_argument("--model", default="qwen2.5:7b-instruct-q8_0")
    p.add_argument("--host", default="http://127.0.0.1:11434")
    p.add_argument("--timeout", type=int, default=300)
    p.add_argument("--networks", nargs="+",
                   default=list(DEFAULT_NETWORKS[:5]))
    p.add_argument("--kinds", nargs="+", default=list(KINDS))
    p.add_argument("--guards", nargs="+", default=["bare", "guarded"])
    p.add_argument("--reps", type=int, default=2)
    p.add_argument("--max-rounds", type=int, default=3)
    p.add_argument("--max-flows", type=int, default=40)
    p.add_argument("--target-util", type=float, default=0.65)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--out", default="")
    return p.parse_args(argv)


def load_done(path: Path) -> set:
    done = set()
    if not path.exists():
        return done
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        done.add((rec["cell_id"], rec["policy"]))
    return done


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.INFO, stream=sys.stdout,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S")

    agent = AgentSpec(backend=args.backend, model=args.model,
                      host=args.host, timeout=args.timeout)
    guards = tuple(g == "guarded" for g in args.guards)
    cfg = CorpusConfig(networks=tuple(args.networks), kinds=tuple(args.kinds),
                       guards=guards, reps=args.reps, agent=agent,
                       max_flows=args.max_flows,
                       target_util=args.target_util, seed=args.seed)
    policies = build_policies(args.max_rounds)

    cells = enumerate_cells(cfg)
    if args.limit:
        cells = cells[:args.limit]

    out_dir = (Path(args.out) if args.out
               else Path("out") / f"policies_{stamp()}")
    out_dir.mkdir(parents=True, exist_ok=True)
    traces_path = out_dir / "traces.jsonl"
    done = load_done(traces_path)

    backend = build_backend(agent)
    try:
        backend.healthcheck()
    except BackendUnavailable as exc:
        logger.error("backend unavailable: %s", exc)
        return 4

    states = build_base_states(cfg)
    meta = run_meta({"config": asdict(cfg),
                     "policies": [asdict(p) for p in policies],
                     "n_cells": len(cells),
                     "backend_provenance": backend.provenance()})
    (out_dir / "config.json").write_text(json.dumps(meta, indent=1))
    logger.info("%d cells x %d policies -> %d runs (%d already done)",
                len(cells), len(policies), len(cells) * len(policies),
                len(done))

    n_run = 0
    interrupted = False
    with traces_path.open("a") as fh:
        for ci, cell in enumerate(cells, 1):
            base = states[cell.network]
            rng = _cell_rng(cfg, cell)
            intent, intent_meta = make_intent(base, rng, cell.kind,
                                              guarded=cell.guarded)
            seed = cell_seed(cfg, cell)
            for pol in policies:
                if (cell.cell_id, pol.label) in done:
                    continue
                try:
                    trace = run_policy(pol, base, intent, backend, seed,
                                       cell.guarded)
                except QuotaExhausted as exc:
                    logger.error("QUOTA EXHAUSTED: %s -- stopping, resume "
                                 "with --out %s", exc, out_dir)
                    interrupted = True
                    break
                except BackendUnavailable as exc:
                    logger.error("BACKEND DOWN: %s -- stopping", exc)
                    interrupted = True
                    break
                except (OSError, ValueError, RuntimeError) as exc:
                    logger.warning("%s/%s failed: %s", cell.cell_id,
                                   pol.label, exc)
                    continue
                trace.update({"cell_id": cell.cell_id, "network": cell.network,
                              "kind": cell.kind, "guarded": cell.guarded,
                              "rep": cell.rep, "intent": intent,
                              "intent_meta": intent_meta})
                fh.write(json.dumps(trace) + "\n")
                fh.flush()
                n_run += 1
            if interrupted:
                break
            if ci % 5 == 0:
                logger.info("cell %d/%d (%d runs written)", ci, len(cells),
                            n_run)

    logger.info("done: %d runs written -> %s", n_run, out_dir)
    return 2 if interrupted else 0


if __name__ == "__main__":
    sys.exit(main())
