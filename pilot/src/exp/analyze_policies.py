"""Aggregate policy traces into the head-to-head comparison table.

Reported per policy, over identical intents:

harm            an unsafe plan actually reached the network. The quantity a
                gate exists to drive down.
interception    an unsafe generation did NOT end in harm, whether by abort or
                by successful repair.
false kill      a generation that was already safe AND fulfilled the intent
                was blocked anyway. Reported beside interception because a
                policy that rejects everything scores perfectly on harm and
                is useless.
repaired        an unsafe generation became a safe, fulfilling actuation --
                the only column where feedback repair, not mere blocking,
                shows value.
cost            agent calls, generation seconds, verification seconds, tokens.

Rates carry Wilson intervals; with a few hundred intents the differences that
matter are often within overlapping intervals, and saying so is the point.
"""
from __future__ import annotations

import json
import logging
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

from .analyze import Rate

logger = logging.getLogger(__name__)

# Outcome labels a trace can end on, so the distribution is always complete.
OUTCOMES = ("ACTUATE", "ACTUATE_UNSOUND", "ABORT_REPAIR_BUDGET",
            "ABORT_STATIC_REJECT", "ACCEPT_UNFULFILLED_NO_ACTUATE",
            "PARSE_FAIL")


def load_traces(path: Path,
                feasibility: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Read a policy traces.jsonl, skipping unusable lines.

    Certified feasibility verdicts are joined by cell id when available, so
    that the group in which an intent is scored is decided by whether a safe
    fulfilling plan provably exists rather than by the label the corpus was
    generated under.
    """
    if not path.exists():
        raise FileNotFoundError(path)
    out: List[Dict[str, Any]] = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            logger.warning("skipping malformed trace line")

    src = feasibility or (path.parent.parent / "corpus_v2" /
                          "feasibility.json")
    if src.exists():
        try:
            verdicts = json.loads(src.read_text()).get("verdict_by_cell") or {}
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("could not read %s: %s", src, exc)
            return out
        hit = 0
        for trace in out:
            verdict = verdicts.get(trace.get("cell_id"))
            if verdict is not None:
                trace["feasibility"] = verdict
                hit += 1
        logger.info("joined feasibility verdicts for %d/%d traces",
                    hit, len(out))
    return out


def _mean(xs: List[float]) -> Optional[float]:
    return round(statistics.mean(xs), 4) if xs else None


def _cluster_ci(traces: List[Dict[str, Any]], hit,
                cluster_key: str = "network", n_boot: int = 3000,
                seed: int = 42) -> Dict[str, Any]:
    """Percentile interval resampling TOPOLOGIES, not individual intents.

    Intents on one topology share a base state and a difficulty level, so a
    marginal interval over all intents understates uncertainty when policies
    are compared across topologies.
    """
    import random as _random
    from collections import defaultdict as _dd

    by: Dict[str, List[Dict[str, Any]]] = _dd(list)
    for t in traces:
        by[t.get(cluster_key, "?")].append(t)
    clusters = sorted(by)
    if len(clusters) < 2:
        return {}
    rng = _random.Random(seed)
    draws = []
    for _ in range(n_boot):
        k = n = 0
        for _ in clusters:
            pool = by[clusters[rng.randrange(len(clusters))]]
            k += sum(1 for t in pool if hit(t))
            n += len(pool)
        if n:
            draws.append(k / n)
    draws.sort()
    return {"ci95_lo": round(draws[int(0.025 * (len(draws) - 1))], 4),
            "ci95_hi": round(draws[int(0.975 * (len(draws) - 1))], 4),
            "n_clusters": len(clusters),
            "method": f"cluster bootstrap by {cluster_key}"}


def summarize_policy(traces: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate one policy's traces."""
    scores = [t["score"] for t in traces if "score" in t]
    n = len(scores)
    if not n:
        return {"n": 0}

    n_unsafe0 = sum(1 for s in scores if s.get("round0_unsafe"))
    n_good0 = sum(1 for s in scores if s.get("round0_good"))

    outcomes: Dict[str, int] = {k: 0 for k in OUTCOMES}
    for s in scores:
        outcomes[s.get("outcome", "PARSE_FAIL")] = outcomes.get(
            s.get("outcome", "PARSE_FAIL"), 0) + 1

    return {
        "n": n,
        # Safety and utility, always side by side: an abort-everything policy
        # drives the first to zero and the second to zero with it.
        "modeled_unsafe_actuation": Rate(
            sum(1 for s in scores if s["modeled_unsafe_actuation"]),
            n).as_dict(),
        "safe_completion": Rate(sum(1 for s in scores if s["safe_completion"]),
                                n).as_dict(),
        # Topology-clustered intervals on the two headline outcomes. Quote
        # the wider of these and the marginal Wilson interval.
        "modeled_unsafe_actuation_clustered": _cluster_ci(
            traces, lambda t: t["score"]["modeled_unsafe_actuation"]),
        "safe_completion_clustered": _cluster_ci(
            traces, lambda t: t["score"]["safe_completion"]),
        "abort": Rate(sum(1 for s in scores if s["aborted"]), n).as_dict(),
        "actuation": Rate(sum(1 for s in scores if s["actuated"]),
                          n).as_dict(),
        # Interception and repair are conditional on there being something to
        # catch, so their denominator is the unsafe generations only.
        "interception_given_unsafe": Rate(
            sum(1 for s in scores if s["intercepted"]), n_unsafe0).as_dict(),
        "repaired_given_unsafe": Rate(
            sum(1 for s in scores if s["repaired_to_safe"]),
            n_unsafe0).as_dict(),
        # False kills are conditional on the generation having been fine.
        "false_kill_given_good": Rate(
            sum(1 for s in scores if s["false_kill"]), n_good0).as_dict(),
        "n_round0_unsafe": n_unsafe0,
        "n_round0_good": n_good0,
        # How often the policy's extra rounds changed anything at all. For
        # self-reflection this separates "reviewed and revised" from
        # "reviewed and reaffirmed", which the outcome columns cannot: a
        # policy whose rounds never alter the plan is paying for rounds that
        # cannot help.
        "n_plan_changed": sum(
            1 for t in traces
            if t.get("final_plan") is not None
            and t.get("round0_plan") != t["final_plan"]),
        "cost": {
            "llm_calls": _mean([s["llm_calls"] for s in scores]),
            "gen_seconds": _mean([s["gen_seconds"] for s in scores]),
            "verify_seconds": _mean([s["verify_seconds"] for s in scores]),
            "prompt_tokens": _mean([float(s["prompt_tokens"])
                                    for s in scores]),
            "gen_tokens": _mean([float(s["gen_tokens"]) for s in scores]),
            "n_rounds": _mean([float(s["n_rounds"]) for s in scores]),
        },
        "outcomes": {k: v for k, v in outcomes.items() if v},
    }


def analyze_policies(traces_path: Path,
                     group: Optional[Callable[[Dict], str]] = None
                     ) -> Dict[str, Any]:
    """Full policy comparison, optionally sliced by an extra grouping key."""
    traces = load_traces(traces_path)
    by_policy: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for t in traces:
        by_policy[t["policy"]].append(t)

    res: Dict[str, Any] = {
        "n_traces": len(traces),
        "policies": {name: summarize_policy(ts)
                     for name, ts in sorted(by_policy.items())},
    }

    if group is not None:
        sliced: Dict[str, Dict[str, Any]] = defaultdict(dict)
        buckets: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for t in traces:
            buckets[f"{group(t)}||{t['policy']}"].append(t)
        for key, ts in sorted(buckets.items()):
            bucket, policy = key.split("||", 1)
            sliced[bucket][policy] = summarize_policy(ts)
        res["by_group"] = dict(sliced)
    return res


def _fmt(d: Dict[str, Any]) -> str:
    if not d or d.get("rate") is None:
        return f"{'n/a':>20}"
    return (f"{d['rate']:.3f}[{d['ci95_lo']:.2f},{d['ci95_hi']:.2f}] "
            f"{d['k']}/{d['n']}")


def report(res: Dict[str, Any]) -> None:
    """Print the head-to-head table: safety and utility side by side."""
    print(f"\n{res['n_traces']} traces")
    print("Safety (unsafe actuation) and utility (safe completion) must be "
          "read together:\nan abort-everything policy scores 0 on both.\n")
    hdr = (f"{'policy':<24}{'n':>4}  {'unsafe_actuation':<24}"
           f"{'safe_completion':<24}{'abort':<24}"
           f"{'calls':>6}{'gen_s':>8}{'verif_s':>9}")
    print(hdr)
    print("-" * len(hdr))
    for name, s in res["policies"].items():
        if not s.get("n"):
            continue
        c = s["cost"]
        print(f"{name:<24}{s['n']:>4}  "
              f"{_fmt(s['modeled_unsafe_actuation']):<24}"
              f"{_fmt(s['safe_completion']):<24}{_fmt(s['abort']):<24}"
              f"{c['llm_calls'] or 0:>6.2f}{c['gen_seconds'] or 0:>8.2f}"
              f"{c['verify_seconds'] or 0:>9.4f}")

    print("\nconditional rates (denominators differ per column):")
    hdr2 = (f"{'policy':<24}{'intercept|unsafe':<26}"
            f"{'repaired|unsafe':<26}{'falsekill|good':<26}")
    print(hdr2)
    print("-" * len(hdr2))
    for name, s in res["policies"].items():
        if not s.get("n"):
            continue
        print(f"{name:<24}{_fmt(s['interception_given_unsafe']):<26}"
              f"{_fmt(s['repaired_given_unsafe']):<26}"
              f"{_fmt(s['false_kill_given_good']):<26}")

    print("\noutcome distributions:")
    for name, s in res["policies"].items():
        if s.get("n"):
            print(f"  {name:<24}{s['outcomes']}")


__all__ = ["OUTCOMES", "analyze_policies", "load_traces", "report",
           "summarize_policy"]
