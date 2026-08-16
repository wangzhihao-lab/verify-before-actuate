"""Leave-one-topology-out profile selection: calibrate, choose, evaluate.

The paper's distinctive claim is not that maximal verification is safest --
that is nearly tautological -- but that the verification profile should be
CHOSEN from the operating regime, trading residual risk against completion
time. Testing that claim requires selecting a profile from one set of data
and measuring it on another; selecting and evaluating on the same corpus
would report the in-sample optimum and prove nothing.

Protocol, per held-out topology:
  1. estimate q, p(e,b), tau(e,b) and G on the OTHER topologies;
  2. pick the profile minimising the renewal objective at a given risk price;
  3. score that profile using the HELD-OUT topology's own parameters.

Estimation and evaluation therefore never share a topology. The comparison
baselines are fixed profiles (always-deepest, always-shallowest), which is
what a system without a selection rule would do.

Objective, from the renewal model, normalised by the time cost so only the
risk-to-time price R matters:

    V(a)    = q(1-p) / (1 - q p)          residual risk per intent
    E[T](a) = (G + tau) / (1 - q p)       expected completion time
    J(a)    = R * V(a) + E[T](a)

No LLM calls: every profile is rescored offline over plans already generated.
"""
from __future__ import annotations

import logging
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .analyze import feasible
from ..netmodel import NetState
from ..semantics import BUDGETS, SCOPES, is_common_loss
from ..smt_verify import smt_verify
from ..twin_verify import twin_verify
from .analyze import load_records, load_states, usable

logger = logging.getLogger(__name__)

VERIFIERS = {"smt": smt_verify, "twin": twin_verify}


@dataclass(frozen=True)
class Profile:
    """A verification profile a = (e, m, b)."""

    mode: str
    e: str
    b: int

    @property
    def label(self) -> str:
        return f"{self.mode}/{self.e}/b{self.b}"


def all_profiles(modes: Sequence[str] = ("smt", "twin")) -> List[Profile]:
    return [Profile(mode=m, e=e, b=b)
            for m in modes for e in SCOPES for b in BUDGETS]


@dataclass(frozen=True)
class TopoParams:
    """Empirical primitives estimated on ONE topology."""

    network: str
    q: float                      # unsafe rate among fulfilled candidates
    n_q: int
    G: float                      # mean generation seconds
    p: Dict[str, float]           # profile label -> detection rate
    n_loss: int
    tau: Dict[str, float]         # profile label -> verification seconds


def estimate_topology(network: str, records: List[Dict[str, Any]],
                      state: NetState, tau_by_profile: Dict[str, float],
                      profiles: Sequence[Profile]) -> Optional[TopoParams]:
    """Estimate q, p and G for one topology from its own records."""
    recs = [r for r in records
            if r["network"] == network and usable(r)
            and feasible(r)
            and r.get("fulfilled") is True]
    if not recs:
        logger.warning("%s: no fulfilled feasible records", network)
        return None

    loss = [r for r in recs if is_common_loss(state, r["plan"])]
    q = len(loss) / len(recs)
    gens = [r["gen_seconds"] for r in recs if r.get("gen_seconds") is not None]
    G = statistics.mean(gens) if gens else 0.0

    p: Dict[str, float] = {}
    for prof in profiles:
        if not loss:
            p[prof.label] = 0.0
            continue
        verify = VERIFIERS[prof.mode]
        hit = sum(1 for r in loss
                  if verify(state, r["plan"], e=prof.e,
                            b=prof.b)[0] == "REJECT")
        p[prof.label] = hit / len(loss)

    return TopoParams(network=network, q=q, n_q=len(recs), G=G, p=p,
                      n_loss=len(loss), tau=tau_by_profile)


def load_tau(costbench_path: Path) -> Dict[str, Dict[str, float]]:
    """Per-network, per-profile verification seconds from the cost sweep."""
    import json

    data = json.loads(costbench_path.read_text())
    out: Dict[str, Dict[str, float]] = {}
    for row in data["rows"]:
        prof = f"{row['mode']}/{row['e']}/b{row['b']}"
        # Envelope: the deterministic reservation the cost model should use.
        ms = row.get("tau_envelope_ms")
        if ms is None:
            continue
        out.setdefault(row["network"], {})[prof] = ms / 1000.0
    return out


def objective(q: float, p: float, tau: float, G: float, R: float
              ) -> Tuple[float, float, float]:
    """Return (J, V, E[T]) for one profile at risk price R."""
    denom = 1.0 - q * p
    if denom <= 1e-9:  # degenerate: detection never lets an intent through
        return float("inf"), float("inf"), float("inf")
    V = q * (1.0 - p) / denom
    ET = (G + tau) / denom
    return R * V + ET, V, ET


def pool(params: Sequence[TopoParams],
         profiles: Sequence[Profile]) -> Dict[str, Any]:
    """Pool calibration topologies into one parameter set."""
    n = sum(pp.n_q for pp in params)
    q = (sum(pp.q * pp.n_q for pp in params) / n) if n else 0.0
    G = statistics.mean([pp.G for pp in params]) if params else 0.0
    p: Dict[str, float] = {}
    tau: Dict[str, float] = {}
    for prof in profiles:
        w = sum(pp.n_loss for pp in params)
        p[prof.label] = ((sum(pp.p[prof.label] * pp.n_loss for pp in params)
                          / w) if w else 0.0)
        taus = [pp.tau[prof.label] for pp in params if prof.label in pp.tau]
        tau[prof.label] = statistics.mean(taus) if taus else 0.0
    return {"q": q, "G": G, "p": p, "tau": tau, "n": n}


def select(cal: Dict[str, Any], profiles: Sequence[Profile],
           R: float) -> Profile:
    """Profile minimising the calibrated objective."""
    best, best_J = profiles[0], float("inf")
    for prof in profiles:
        J, _, _ = objective(cal["q"], cal["p"][prof.label],
                            cal["tau"][prof.label], cal["G"], R)
        if J < best_J:
            best, best_J = prof, J
    return best


def evaluate(prof: Profile, test: TopoParams, R: float) -> Dict[str, Any]:
    """Score a profile with the held-out topology's own parameters."""
    J, V, ET = objective(test.q, test.p[prof.label],
                         test.tau.get(prof.label, 0.0), test.G, R)
    return {"profile": prof.label, "J": J, "V": V, "E_T": ET,
            "q_test": test.q, "p_test": test.p[prof.label],
            "tau_test": test.tau.get(prof.label, 0.0)}


def loto(records: List[Dict[str, Any]], states: Dict[str, NetState],
         tau: Dict[str, Dict[str, float]], R_values: Sequence[float],
         modes: Sequence[str] = ("smt",)) -> Dict[str, Any]:
    """Leave-one-topology-out selection across a sweep of risk prices."""
    profiles = all_profiles(modes)
    networks = sorted({r["network"] for r in records
                       if r["network"] in states and r["network"] in tau})
    params: Dict[str, TopoParams] = {}
    for net in networks:
        pp = estimate_topology(net, records, states[net], tau[net], profiles)
        if pp is not None:
            params[net] = pp
    networks = sorted(params)
    if len(networks) < 3:
        raise ValueError(f"need >=3 topologies, have {len(networks)}")

    # Fixed-profile baselines: what a system without a selection rule does.
    deepest = Profile(modes[0], "prefix", max(BUDGETS))
    shallowest = Profile(modes[0], "prefix", min(BUDGETS))

    rows: List[Dict[str, Any]] = []
    for R in R_values:
        for held in networks:
            cal = pool([params[n] for n in networks if n != held], profiles)
            chosen = select(cal, profiles, R)
            rows.append({
                "R": R, "held_out": held,
                "selected": chosen.label,
                "selected_eval": evaluate(chosen, params[held], R),
                "always_deepest": evaluate(deepest, params[held], R),
                "always_shallowest": evaluate(shallowest, params[held], R),
                "oracle": min(
                    (evaluate(p_, params[held], R) for p_ in profiles),
                    key=lambda d: d["J"]),
            })

    summary: List[Dict[str, Any]] = []
    for R in R_values:
        sub = [r for r in rows if r["R"] == R]
        def mean(key: str) -> float:
            return statistics.mean(r[key]["J"] for r in sub)
        sel, deep = mean("selected_eval"), mean("always_deepest")

        # Regret is the quantity that survives an easy profile space. A high
        # oracle-match count on twelve candidates says little; the held-out
        # loss relative to the best achievable choice says how much the rule
        # actually costs when it is wrong.
        regrets = [r["selected_eval"]["J"] - r["oracle"]["J"] for r in sub]
        rel = [100 * (r["selected_eval"]["J"] - r["oracle"]["J"])
               / r["oracle"]["J"] for r in sub if r["oracle"]["J"] > 0]
        summary.append({
            "R": R,
            "J_selected": round(sel, 5),
            "J_always_deepest": round(deep, 5),
            "J_always_shallowest": round(mean("always_shallowest"), 5),
            "J_oracle": round(mean("oracle"), 5),
            # Positive means selection beat the fixed deepest profile.
            "gain_vs_deepest_pct": round(100 * (deep - sel) / deep, 3)
            if deep else None,
            "regret_mean": round(statistics.mean(regrets), 6),
            "regret_max": round(max(regrets), 6),
            "regret_rel_mean_pct": round(statistics.mean(rel), 4) if rel else None,
            "regret_ci95": _fold_ci(regrets),
            "selected_profiles": sorted({r["selected"] for r in sub}),
            "matches_oracle": sum(1 for r in sub
                                  if r["selected"] == r["oracle"]["profile"]),
            "n_folds": len(sub),
        })

    return {"networks": networks, "rows": rows, "summary": summary,
            "switch": switch_points(rows, networks),
            "params": {n: {"q": round(p_.q, 4), "G": round(p_.G, 3),
                           "n_q": p_.n_q, "n_loss": p_.n_loss}
                       for n, p_ in params.items()}}


def _fold_ci(values: Sequence[float], n_boot: int = 4000,
             seed: int = 42) -> List[float]:
    """Percentile interval resampling FOLDS, which are the independent unit."""
    import random as _random

    vals = list(values)
    if len(vals) < 2:
        return [round(vals[0], 6), round(vals[0], 6)] if vals else [0.0, 0.0]
    rng = _random.Random(seed)
    draws = sorted(statistics.mean(rng.choice(vals) for _ in vals)
                   for _ in range(n_boot))
    lo = draws[int(0.025 * (len(draws) - 1))]
    hi = draws[int(0.975 * (len(draws) - 1))]
    return [round(lo, 6), round(hi, 6)]


def switch_points(rows: List[Dict[str, Any]],
                  networks: Sequence[str]) -> Dict[str, Any]:
    """Where each fold's chosen profile changes as the risk price rises.

    A selection rule that is worth anything must move its choice with the
    regime, and it should move at a similar place for every held-out
    topology. Scatter in the switch point is the honest uncertainty on the
    threshold, which a single pooled curve hides.
    """
    per_fold: Dict[str, List[Dict[str, Any]]] = {}
    for net in networks:
        seq = sorted((r for r in rows if r["held_out"] == net),
                     key=lambda r: r["R"])
        changes = []
        for prev, cur in zip(seq, seq[1:]):
            if prev["selected"] != cur["selected"]:
                changes.append({"from_R": prev["R"], "to_R": cur["R"],
                                "from": prev["selected"],
                                "to": cur["selected"]})
        per_fold[net] = changes
    firsts = [c[0]["to_R"] for c in per_fold.values() if c]
    return {
        "per_fold": per_fold,
        "n_folds_with_switch": len(firsts),
        "n_folds": len(networks),
        "first_switch_R_min": min(firsts) if firsts else None,
        "first_switch_R_max": max(firsts) if firsts else None,
        "unanimous": len(set(firsts)) == 1 and len(firsts) == len(networks),
    }


__all__ = ["Profile", "TopoParams", "all_profiles", "estimate_topology",
           "evaluate", "load_tau", "loto", "objective", "pool", "select"]
