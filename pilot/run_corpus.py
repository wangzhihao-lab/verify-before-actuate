"""CLI runner for the agent plan corpus over real SNDlib topologies.

Primary corpus on the pinned local open-weights model (reproducible, no quota):
    PYTHONPATH=. .venv/bin/python run_corpus.py --reps 5 --out out/corpus_qwen

Cross-model comparison cell on the hosted frontier model (quota-limited, so
keep it small and expect to resume):
    PYTHONPATH=. .venv/bin/python run_corpus.py --backend claude_cli \
        --model haiku --networks abilene geant --reps 2 --out out/corpus_claude

Reruns of the SAME --out resume: finished cells are skipped, so a quota or
crash interruption never loses work.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import asdict
from pathlib import Path

from src.backends import AgentSpec, BackendUnavailable
from src.exp.corpus import (DEFAULT_NETWORKS, CorpusConfig, enumerate_cells,
                            run_corpus)
from src.intents import KINDS
from src.provenance import run_meta, stamp

logger = logging.getLogger("run_corpus")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--backend", default="ollama",
                   choices=("ollama", "claude_cli", "lmstudio"))
    p.add_argument("--model", default="qwen2.5:7b-instruct-q8_0")
    p.add_argument("--temperature", type=float, default=0.7)
    p.add_argument("--num-ctx", type=int, default=16384)
    p.add_argument("--host", default="http://127.0.0.1:11434")
    p.add_argument("--timeout", type=int, default=300)
    p.add_argument("--networks", nargs="+", default=list(DEFAULT_NETWORKS))
    p.add_argument("--kinds", nargs="+", default=list(KINDS))
    p.add_argument("--reps", type=int, default=5)
    p.add_argument("--workers", type=int, default=1,
                   help="concurrent generations; keep at 1 for a local model "
                        "so per-call latency stays measurable")
    p.add_argument("--max-flows", type=int, default=40)
    p.add_argument("--target-util", type=float, default=0.65)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--limit", type=int, default=0,
                   help="run at most N cells (0 = all); for smoke tests")
    p.add_argument("--out", default="",
                   help="output dir; reuse an existing one to RESUME")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.INFO, stream=sys.stdout,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S")

    agent = AgentSpec(backend=args.backend, model=args.model,
                      temperature=args.temperature, num_ctx=args.num_ctx,
                      timeout=args.timeout, host=args.host)
    cfg = CorpusConfig(
        networks=tuple(args.networks), kinds=tuple(args.kinds),
        reps=args.reps, agent=agent, workers=args.workers,
        max_flows=args.max_flows, target_util=args.target_util,
        seed=args.seed)

    # A smoke test is a strict PREFIX of the full corpus, so its records are
    # reused rather than discarded when the full run follows.
    cells = enumerate_cells(cfg)
    if args.limit:
        cells = cells[:args.limit]
        logger.info("limit=%d -> %d cells", args.limit, len(cells))

    out_dir = Path(args.out) if args.out else Path("out") / f"corpus_{stamp()}"
    out_dir.mkdir(parents=True, exist_ok=True)

    meta = run_meta({"config": asdict(cfg), "n_cells_planned": len(cells)})
    (out_dir / "config.json").write_text(json.dumps(meta, indent=1))
    logger.info("output -> %s  (sha=%s dirty=%s)", out_dir,
                meta["commit_sha"], meta["git_dirty"])

    try:
        summary = run_corpus(cfg, out_dir, cells=cells)
    except BackendUnavailable as exc:
        logger.error("backend unavailable: %s", exc)
        return 4

    (out_dir / "summary.json").write_text(json.dumps(summary, indent=1))
    logger.info("summary: recorded=%d ok=%d err=%d interrupted=%s",
                summary["cells_recorded"], summary["ran_ok"],
                summary["ran_err"], summary["interrupted"])
    if summary["interrupted"]:
        logger.warning("interrupted; rerun with --out %s to resume", out_dir)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
