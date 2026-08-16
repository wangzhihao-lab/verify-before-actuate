"""Where verification cost stops being negligible next to generation cost.

At the sizes used in the main evaluation the direct check accounts for well
under a percent of a round, so the risk-latency trade-off there is carried
almost entirely by rejection-induced regeneration. That is a statement about
a size regime, not about verification in general, and the way to find out
where it stops holding is to measure both terms on the same rungs of a
scaling ladder.

Design constraints this runner exists to respect:

SAME ROUND, SAME BOUNDARY  tau and G are measured in the same run, on the
    same topology, through the same interfaces. Dividing a solver timing from
    one experiment by a generation latency from another is how a crossover
    gets manufactured.
G IS NOT CONSTANT  a larger topology means a larger state in the prompt, so
    generation slows down too. Holding G fixed at its small-topology value
    would overstate the crossover.
STRESS RUNGS ARE LABELLED  synthetic rungs beyond the largest published
    instance are a scalability probe, not a sample from any deployed network,
    and are reported as such.
REPORT THE CURVE  the ratio is reported across the ladder rather than at one
    flattering point.

    PYTHONPATH=. .venv/bin/python run_crossover.py
"""
from __future__ import annotations

import argparse
import json
import logging
import random
import statistics
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.agent import build_prompt, extract_plan, strip_reasoning
from src.backends import AgentSpec, BackendUnavailable, build_backend
from src.coverage import predicate_instances
from src.exp.costbench import make_clean_plans, CostBenchConfig
from src.exp.intent_gen import make_intent
from src.provenance import run_meta, stamp
from src.topo import TopoSpec, build_topology, available_sndlib
from src.verify_frac import frac_verify

logger = logging.getLogger("run_crossover")

# Published instances, ascending, then synthetic stress rungs.
REAL_LADDER = ("abilene", "atlanta", "geant", "france", "norway",
               "india35", "germany50", "ta2", "brain")
STRESS_NODES = (250, 400, 600)


def _synthetic(n_nodes: int, seed: int):
    """A stress rung. Not drawn from any published topology distribution."""
    return build_topology(TopoSpec(backend="synthetic", name=f"synth{n_nodes}",
                                   seed=seed, n_nodes=n_nodes,
                                   n_chords=n_nodes // 2,
                                   max_flows=40))


def measure_tau(st, cfg: CostBenchConfig, repeats: int) -> Dict[str, float]:
    """Full-traversal verification time at full coverage, both backends."""
    rng = random.Random("crossover")
    plans = make_clean_plans(st, rng, cfg)
    if not plans:
        return {}
    out: Dict[str, float] = {}
    for mode in ("smt", "checker"):
        per_plan = []
        for plan in plans:
            reps = [frac_verify(st, plan, e="prefix", frac=1.0,
                                order="class", mode=mode,
                                full_traversal=True)[2]
                    for _ in range(repeats)]
            per_plan.append(1e3 * statistics.median(reps))
        out[f"tau_{mode}_ms"] = round(statistics.mean(per_plan), 4)
    return out


def measure_G(st, backend, seed: int, timeout_note: List[str],
              repeats: int = 3, warmup: bool = True) -> Dict[str, Any]:
    """Generation latency on THIS topology, in the same run as tau.

    Repeated, and preceded by a discarded warm-up call. A single timing on a
    freshly started model server measures weight loading rather than
    generation: an earlier version of this experiment reported 29.8 s for a
    topology whose repeated median is 5.3 s, which understated the cost ratio
    by roughly fivefold at the small end of the ladder.
    """
    rng = random.Random(f"crossover|{seed}")
    intent, _ = make_intent(st, rng, "bandwidth", guarded=True)
    prompt = build_prompt(st, intent["text"], guardrail=True)

    if warmup:
        try:
            backend.generate(prompt, seed=seed)
        except BackendUnavailable as exc:
            timeout_note.append(f"warmup: {str(exc)[:100]}")
            return {"G_s": None, "prompt_chars": len(prompt),
                    "gen_failed": str(exc)[:120]}

    walls: List[float] = []
    tokens: List[int] = []
    parse_ok = None
    for i in range(repeats):
        try:
            res = backend.generate(prompt, seed=seed + i)
        except BackendUnavailable as exc:
            # A topology whose serialized state no longer fits the model's
            # context is itself a scaling result: the agent stops being able
            # to plan over the network before the verifier stops being able
            # to check it. Recorded, not silently dropped.
            timeout_note.append(str(exc)[:120])
            break
        walls.append(res.wall_s)
        if res.gen_tokens:
            tokens.append(res.gen_tokens)
        if parse_ok is None:
            parse_ok = extract_plan(strip_reasoning(res.text)) is not None
    if not walls:
        return {"G_s": None, "prompt_chars": len(prompt),
                "gen_failed": "no successful generation"}
    return {"G_s": round(statistics.median(walls), 3),
            "G_min_s": round(min(walls), 3), "G_max_s": round(max(walls), 3),
            "G_repeats": len(walls),
            "prompt_chars": len(prompt),
            "gen_tokens_median": (statistics.median(tokens)
                                  if tokens else None),
            "parse_ok": parse_ok}


def main(argv: List[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--backend", default="ollama")
    p.add_argument("--model", default="qwen2.5:7b-instruct-q8_0")
    p.add_argument("--host", default="http://127.0.0.1:11434")
    p.add_argument("--timeout", type=int, default=900)
    p.add_argument("--n-plans", type=int, default=4)
    p.add_argument("--repeats", type=int, default=3)
    p.add_argument("--g-repeats", type=int, default=3,
                   help="generation timings per rung, after a "
                        "discarded warm-up")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--out", default="")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                        format="%(levelname)-7s %(message)s")

    spec = AgentSpec(backend=args.backend, model=args.model, host=args.host,
                     timeout=args.timeout, num_ctx=16384)
    backend = build_backend(spec)
    backend.healthcheck()

    cfg = CostBenchConfig(n_plans=args.n_plans, repeats=args.repeats)
    have = set(available_sndlib())
    rungs: List[Tuple[str, str, Any]] = []
    for name in REAL_LADDER:
        if name in have:
            rungs.append((name, "published",
                          build_topology(TopoSpec(backend="sndlib", name=name,
                                                  seed=args.seed,
                                                  max_flows=40))))
    for n in STRESS_NODES:
        rungs.append((f"synth{n}", "stress", _synthetic(n, args.seed)))

    notes: List[str] = []
    rows: List[Dict[str, Any]] = []
    for name, kind, st in rungs:
        row: Dict[str, Any] = {
            "topology": name, "class": kind,
            "n_nodes": len(st.nodes), "n_links": len(st.links),
            "n_flows": len(st.flows),
            "n_predicates": len(predicate_instances(st)),
        }
        row.update(measure_tau(st, cfg, args.repeats))
        row.update(measure_G(st, backend, args.seed, notes,
                             repeats=args.g_repeats))
        g = row.get("G_s")
        for mode in ("smt", "checker"):
            tau = row.get(f"tau_{mode}_ms")
            row[f"ratio_{mode}"] = (round(tau / 1e3 / g, 5)
                                    if (tau and g) else None)
        rows.append(row)
        logger.info("%-12s %-10s nodes=%-4d links=%-5d tau_smt=%8.1fms "
                    "G=%s ratio=%s", name, kind, row["n_nodes"],
                    row["n_links"], row.get("tau_smt_ms") or -1,
                    f"{g:.1f}s" if g else "n/a", row.get("ratio_smt"))

    payload = {"meta": run_meta({"backend": spec.label,
                                 "n_plans": args.n_plans,
                                 "repeats": args.repeats}),
               "rows": rows, "generation_failures": notes,
               "note": ("tau and G measured in the same run on the same "
                        "topology; synthetic rungs are a scalability probe, "
                        "not a published-topology sample")}
    out_dir = Path(args.out) if args.out else Path("out") / f"crossover_{stamp()}"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "crossover.json").write_text(json.dumps(payload, indent=1))

    print(f"\n{'topology':<12}{'class':<11}{'nodes':>6}{'links':>7}"
          f"{'preds':>7}{'tau_smt_ms':>12}{'G_s':>8}{'tau/G':>10}")
    for r in rows:
        print(f"{r['topology']:<12}{r['class']:<11}{r['n_nodes']:>6}"
              f"{r['n_links']:>7}{r['n_predicates']:>7}"
              f"{(r.get('tau_smt_ms') or 0):>12.1f}"
              f"{(r.get('G_s') or 0):>8.1f}"
              f"{(r.get('ratio_smt') or 0):>10.4f}")
    print(f"\n-> {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
