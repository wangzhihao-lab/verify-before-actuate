"""Resumable agent plan corpus over real topologies.

One LLM call per cell, where a cell is
``(network, intent kind, guarded/bare, repetition)``. Every generated plan is
stored with its ground-truth safety label, so detection rate ``p(e,b)`` and
verification cost ``tau(e,b)`` for ALL profiles are recomputed offline from
the same corpus without spending further LLM calls.

Two properties this module must guarantee:

RESUMABLE  results are appended per cell; a rerun pointed at an existing
           directory skips finished cells. The shared subscription quota can
           interrupt a long run at any point without losing work.
DETERMINISTIC  a cell's intent is seeded from its own identity, not from
           execution order, so results do not depend on worker scheduling.
"""
from __future__ import annotations

import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

from ..agent import build_prompt, extract_plan, strip_reasoning
from ..backends import (AgentSpec, Backend, BackendUnavailable, QuotaExhausted,
                        build_backend)
from ..intents import KINDS, intent_fulfilled
from ..netmodel import NetState
from ..semantics import (BUDGETS, SCOPES, class_counts, is_common_loss,
                         is_unsafe, violations_for)
from ..topo import TopoSpec, build_topology
from .intent_gen import make_intent

logger = logging.getLogger(__name__)

# Mid-size real topologies: large enough to be non-trivial, small enough that
# the full state fits in a prompt without truncation.
DEFAULT_NETWORKS: Tuple[str, ...] = (
    "abilene", "polska", "nobel-us", "atlanta", "nobel-germany",
    "geant", "ta1", "france", "janos-us", "norway",
)


@dataclass(frozen=True)
class CorpusConfig:
    """Immutable description of a whole corpus run."""

    networks: Tuple[str, ...] = DEFAULT_NETWORKS
    kinds: Tuple[str, ...] = tuple(KINDS)
    guards: Tuple[bool, ...] = (True, False)
    reps: int = 5
    agent: AgentSpec = AgentSpec()
    max_flows: int = 40
    target_util: float = 0.65
    seed: int = 42
    workers: int = 4

    @property
    def n_cells(self) -> int:
        return (len(self.networks) * len(self.kinds) * len(self.guards)
                * self.reps)


@dataclass(frozen=True)
class CellSpec:
    """One LLM call's worth of work."""

    network: str
    kind: str
    guarded: bool
    rep: int

    @property
    def cell_id(self) -> str:
        return (f"{self.network}|{self.kind}|"
                f"{'guarded' if self.guarded else 'bare'}|{self.rep}")


def enumerate_cells(cfg: CorpusConfig) -> List[CellSpec]:
    """All cells of a corpus, in a stable order."""
    return [CellSpec(network=n, kind=k, guarded=g, rep=r)
            for n in cfg.networks
            for k in cfg.kinds
            for g in cfg.guards
            for r in range(cfg.reps)]


def build_base_states(cfg: CorpusConfig) -> Dict[str, NetState]:
    """Base state per network, built once and shared read-only by workers."""
    states: Dict[str, NetState] = {}
    for name in cfg.networks:
        spec = TopoSpec(backend="sndlib", name=name, seed=cfg.seed,
                        max_flows=cfg.max_flows,
                        target_util=cfg.target_util)
        states[name] = build_topology(spec)
        logger.info("built %s: %d nodes, %d links, %d flows", name,
                    len(states[name].nodes), len(states[name].links),
                    len(states[name].flows))
    return states


def _cell_rng(cfg: CorpusConfig, cell: CellSpec):
    """Seeded from cell identity so scheduling cannot change the intent."""
    import random
    return random.Random(f"{cfg.seed}|{cell.network}|{cell.kind}|{cell.rep}")


def label_plan(base: NetState, intent: Dict[str, Any],
               plan: List[Any]) -> Dict[str, Any]:
    """Ground-truth safety and goal labels for one generated plan."""
    v_prefix = violations_for(base, plan, "prefix")
    v_term = violations_for(base, plan, "term")
    out: Dict[str, Any] = {
        "n_viol_prefix": len(v_prefix),
        "n_viol_terminal": len(v_term),
        "cls_prefix": class_counts(v_prefix),
        "cls_terminal": class_counts(v_term),
        "common_loss": is_common_loss(base, plan),
        "viol_prefix": v_prefix[:20],
        "fulfilled": intent_fulfilled(base, intent, plan),
        "plan_len": len(plan),
        # An empty plan is trivially safe but achieves nothing. Counting it
        # as a "safe generation" would let an agent score perfectly by
        # refusing to act, so abstention is tracked as its own outcome.
        "abstained": len(plan) == 0,
    }
    # Ground-truth unsafety per profile, for offline p(e,b) scoring.
    out["unsafe"] = {f"{e}_b{b}": is_unsafe(base, plan, e, b)
                     for e in SCOPES for b in BUDGETS}
    return out


def cell_seed(cfg: CorpusConfig, cell: CellSpec) -> int:
    """Generation seed for a cell: varies per repetition, reproducible."""
    import hashlib
    digest = hashlib.sha256(f"{cfg.seed}|{cell.cell_id}".encode()).hexdigest()
    return int(digest[:8], 16)


def run_cell(cfg: CorpusConfig, base: NetState, cell: CellSpec,
             backend: Backend) -> Dict[str, Any]:
    """Generate one plan and label it. Raises QuotaExhausted to abort a run."""
    import hashlib

    rng = _cell_rng(cfg, cell)
    intent, intent_meta = make_intent(base, rng, cell.kind,
                                      guarded=cell.guarded)
    prompt = build_prompt(base, intent["text"], guardrail=cell.guarded)
    seed = cell_seed(cfg, cell)

    rec: Dict[str, Any] = {
        "cell_id": cell.cell_id,
        **asdict(cell),
        "intent": intent,
        "intent_meta": intent_meta,
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "prompt_chars": len(prompt),
        "backend": cfg.agent.backend,
        "model": cfg.agent.model,
        "gen_seed": seed,
    }

    res = backend.generate(prompt, seed=seed)
    raw = res.text
    rec["gen_seconds"] = round(res.wall_s, 3)
    rec["raw_response"] = raw
    rec["response_chars"] = len(raw)
    rec["prompt_tokens"] = res.prompt_tokens
    rec["gen_tokens"] = res.gen_tokens
    rec["gen_meta"] = res.meta

    plan = extract_plan(strip_reasoning(raw))
    rec["parse_ok"] = plan is not None
    rec["plan"] = plan
    if plan is None:
        logger.warning("%s: unparsable response", cell.cell_id)
        return rec

    try:
        rec.update(label_plan(base, intent, plan))
    except (KeyError, TypeError, ValueError) as exc:
        # A malformed op can trip the model before apply_op sees it; keep the
        # record so the failure is counted rather than silently dropped.
        logger.warning("%s: labelling failed: %s", cell.cell_id, exc)
        rec["label_error"] = f"{type(exc).__name__}: {exc}"
    return rec


def load_done(records_path: Path) -> Dict[str, Dict[str, Any]]:
    """Cells already recorded in a previous run, keyed by cell id."""
    done: Dict[str, Dict[str, Any]] = {}
    if not records_path.exists():
        return done
    with records_path.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                logger.warning("skipping malformed record line")
                continue
            done[rec["cell_id"]] = rec
    return done


def run_corpus(cfg: CorpusConfig, out_dir: Path,
               cells: Optional[List[CellSpec]] = None) -> Dict[str, Any]:
    """Run (or resume) a corpus into ``out_dir``. Returns a summary dict.

    Args:
        cfg: corpus configuration.
        out_dir: output directory; an existing one is RESUMED, not overwritten.
        cells: explicit cell list, defaulting to the full cross product. Used
            to run a strict prefix of the full corpus as a smoke test.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    records_path = out_dir / "records.jsonl"

    planned = cells if cells is not None else enumerate_cells(cfg)
    done = load_done(records_path)
    cells = [c for c in planned if c.cell_id not in done]
    logger.info("corpus: %d cells planned, %d done, %d to run",
                len(planned), len(done), len(cells))

    states = build_base_states(cfg)
    states_dir = out_dir / "states"
    states_dir.mkdir(exist_ok=True)
    for name, st in states.items():
        (states_dir / f"{name}.json").write_text(st.to_json())

    backend = build_backend(cfg.agent)
    backend.healthcheck()
    logger.info("backend ready: %s", cfg.agent.label)

    write_lock = threading.Lock()
    stop = threading.Event()
    n_ok = n_err = 0

    def work(cell: CellSpec) -> Optional[Dict[str, Any]]:
        if stop.is_set():
            return None
        try:
            return run_cell(cfg, states[cell.network], cell, backend)
        except QuotaExhausted as exc:
            logger.error("QUOTA EXHAUSTED at %s: %s -- stopping, progress "
                         "kept; rerun the same --out to resume",
                         cell.cell_id, exc)
            stop.set()
            return None
        except BackendUnavailable as exc:
            logger.error("BACKEND DOWN at %s: %s -- stopping, progress kept",
                         cell.cell_id, exc)
            stop.set()
            return None
        except (OSError, ValueError, RuntimeError) as exc:
            logger.warning("%s failed: %s: %s", cell.cell_id,
                           type(exc).__name__, exc)
            return {"cell_id": cell.cell_id, "error":
                    f"{type(exc).__name__}: {exc}"}

    with ThreadPoolExecutor(max_workers=cfg.workers) as pool:
        futures = {pool.submit(work, c): c for c in cells}
        for i, fut in enumerate(as_completed(futures), 1):
            rec = fut.result()
            if rec is None:
                continue
            with write_lock:
                with records_path.open("a") as fh:
                    fh.write(json.dumps(rec) + "\n")
            if "error" in rec:
                n_err += 1
            else:
                n_ok += 1
            if i % 10 == 0 or i == len(futures):
                logger.info("progress %d/%d (ok=%d err=%d)",
                            i, len(futures), n_ok, n_err)

    total = load_done(records_path)
    return {"cells_planned": len(planned), "cells_recorded": len(total),
            "ran_ok": n_ok, "ran_err": n_err,
            "interrupted": stop.is_set(),
            "backend_provenance": backend.provenance()}


__all__ = [
    "CellSpec",
    "CorpusConfig",
    "DEFAULT_NETWORKS",
    "build_base_states",
    "enumerate_cells",
    "label_plan",
    "load_done",
    "run_cell",
    "run_corpus",
]
