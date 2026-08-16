"""Verification cost tau(e, m, b) as a function of real network size.

Replaces the single 24-node synthetic measurement with a scaling curve over
every SNDlib topology (10 to 161 nodes), for both verification modes and all
six (e, b) profiles.

Two methodological rules, inherited from the archived microbenchmark:

CLEAN PLANS ONLY  tau is the cost of a COMPLETE traversal. Timing a plan that
    gets rejected early would credit a profile for bailing out sooner, which
    is a detection property, not a cost property, and produces the
    non-monotone tau curves seen in an earlier round.
MEDIAN OF REPEATS  per plan, then aggregate across plans, so one scheduler
    hiccup cannot move a cell.

Timings are only meaningful on an otherwise idle machine; load average is
recorded before and after so a contended run can be identified and discarded
rather than silently believed.
"""
from __future__ import annotations

import logging
import os
import random
import statistics
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from ..netmodel import NetState, Op
from ..semantics import BUDGETS, SCOPES
from ..smt_verify import encoded_terms, smt_verify
from ..topo import TopoSpec, build_topology, available_sndlib
from ..twin_verify import twin_verify

logger = logging.getLogger(__name__)

VERIFIERS: Dict[str, Callable[..., Tuple[str, Any, float]]] = {
    "smt": smt_verify,
    "twin": twin_verify,
}

# Repeat-to-repeat coefficient of variation above which a timing cell is
# treated as disturbed rather than measured...
CV_UNSTABLE = 0.25
# ...but only where the absolute time is large enough for relative variation
# to mean anything. Sub-millisecond solves show tens of percent CV from
# scheduler jitter alone, while the absolute wobble is microseconds and
# irrelevant to a cost curve denominated in milliseconds.
CV_MIN_MS = 5.0


@dataclass(frozen=True)
class CostBenchConfig:
    """Immutable configuration for one cost-scaling sweep."""

    networks: Tuple[str, ...] = ()
    n_plans: int = 8
    repeats: int = 5
    max_flows: int = 40
    target_util: float = 0.65
    seed: int = 42
    plan_len_lo: int = 2
    plan_len_hi: int = 8

    def resolved_networks(self) -> Tuple[str, ...]:
        return self.networks or tuple(available_sndlib())


def make_clean_plans(base: NetState, rng: random.Random,
                     cfg: CostBenchConfig) -> List[List[Op]]:
    """Plans that are genuinely violation-free, so every check runs to the end.

    Built only from invariant-preserving operations: rewriting a flow's
    bandwidth to its current value, rescaling a node to its current replica
    count, enabling an already-enabled node. Any candidate that is not
    provably clean is discarded rather than repaired.
    """
    from ..invariants import check_plan

    flows, nodes = list(base.flows), list(base.nodes)
    if not flows or not nodes:
        return []
    out: List[List[Op]] = []
    attempts = 0
    while len(out) < cfg.n_plans and attempts < cfg.n_plans * 10:
        attempts += 1
        plan: List[Op] = []
        for _ in range(rng.randint(cfg.plan_len_lo, cfg.plan_len_hi)):
            choice = rng.choice(("noop_bw", "scale_ok", "enable"))
            if choice == "noop_bw":
                fid = rng.choice(flows)
                plan.append({"op": "set_flow_bw", "flow": fid,
                             "bw_mbps": base.flows[fid]["bw"]})
            elif choice == "scale_ok":
                nid = rng.choice(nodes)
                plan.append({"op": "scale_vnf", "node": nid,
                             "replicas": base.nodes[nid]["replicas"]})
            else:
                plan.append({"op": "enable_node", "node": rng.choice(nodes)})
        if not check_plan(base, plan):
            out.append(plan)
    if len(out) < cfg.n_plans:
        logger.warning("only %d/%d clean plans generated", len(out),
                       cfg.n_plans)
    return out


def make_unsafe_plans(base: NetState, rng: random.Random,
                      cfg: CostBenchConfig) -> List[List[Op]]:
    """Plans that genuinely violate, one per invariant class where possible.

    Needed because the depth-3 SMT fragment only instantiates constraints
    where a conflict concretely exists: timing depth 3 on clean plans alone
    measures an encoding that happens to be identical to depth 2, and so
    understates its cost on exactly the plans a deployment cares about.
    """
    from ..invariants import check_plan

    out: List[List[Op]] = []
    flows, nodes = list(base.flows), list(base.nodes)
    if not flows or not nodes:
        return out

    # I1: drive a flow far past the capacity of its own path.
    for fid in flows[:max(1, cfg.n_plans // 2)]:
        cap = max((base.links[lid]["cap"]
                   for lid in (base.path_links(base.flows[fid]["path"]) or [])),
                  default=1000.0)
        out.append([{"op": "set_flow_bw", "flow": fid, "bw_mbps": cap * 10}])

    # I3: disable a node that flows traverse.
    transited = sorted({n for f in base.flows.values() for n in f["path"]})
    for nid in transited[:max(1, cfg.n_plans // 4)]:
        out.append([{"op": "disable_node", "node": nid}])

    # I3: introduce a rule contradicting an existing one.
    for rid, rule in list(base.acls.items())[:2]:
        out.append([{"op": "add_acl", "rule_id": f"{rid}_x",
                     "src": rule["src"], "dst": rule["dst"],
                     "action": "deny" if rule["action"] == "allow"
                               else "allow"}])

    # Keep only plans that really do violate, so the label is earned.
    out = [p for p in out if check_plan(base, p)]
    rng.shuffle(out)
    return out[:cfg.n_plans]


def _loadavg() -> Optional[float]:
    try:
        return round(os.getloadavg()[0], 2)
    except (OSError, AttributeError):
        return None


def bench_network(name: str, cfg: CostBenchConfig) -> Dict[str, Any]:
    """Measure every (mode, e, b) cell for one network."""
    spec = TopoSpec(backend="sndlib", name=name, seed=cfg.seed,
                    max_flows=cfg.max_flows, target_util=cfg.target_util)
    base = build_topology(spec)
    rng = random.Random(f"{cfg.seed}|costbench|{name}")
    plans = make_clean_plans(base, rng, cfg)
    if not plans:
        logger.warning("%s: no clean plans, skipping", name)
        return {"network": name, "skipped": "no clean plans"}

    unsafe = make_unsafe_plans(base, rng, cfg)

    def measure(verify: Callable, plan_set: List[List[Op]], e: str, b: int,
                **kw: Any) -> Tuple[Optional[float], Optional[float]]:
        """Mean over plans of the per-plan median (ms), and worst per-plan CV.

        The coefficient of variation across repeats is the honest contention
        signal: a timing whose repeats agree closely was not disturbed,
        whatever the load average happened to be. Load average alone is a
        poor proxy on a desktop, where the idle baseline already sits near
        the threshold and the measurement's own core counts toward it.
        """
        if not plan_set:
            return None, None
        per_plan: List[float] = []
        worst_cv = 0.0
        for plan in plan_set:
            reps = [verify(base, plan, e=e, b=b, **kw)[2]
                    for _ in range(cfg.repeats)]
            per_plan.append(1e3 * statistics.median(reps))
            mean_t = statistics.mean(reps)
            if mean_t > 0 and len(reps) > 1:
                worst_cv = max(worst_cv,
                               statistics.stdev(reps) / mean_t)
        return round(statistics.mean(per_plan), 4), round(worst_cv, 4)

    rows: List[Dict[str, Any]] = []
    for mode, verify in VERIFIERS.items():
        for e in SCOPES:
            for b in BUDGETS:
                clean_ms, cv_c = measure(verify, plans, e, b)
                unsafe_obs, cv_o = measure(verify, unsafe, e, b)
                unsafe_full, cv_f = measure(verify, unsafe, e, b,
                                            full_traversal=True)
                cvs = [c for c in (cv_c, cv_o, cv_f) if c is not None]
                rows.append({
                    # Worst repeat-to-repeat variation in this cell. Small
                    # values mean the timing is trustworthy.
                    "max_cv": round(max(cvs), 4) if cvs else None,
                    "network": name, "mode": mode, "e": e, "b": b,
                    # Full traversal by nature: nothing to reject early.
                    "tau_mean_ms": clean_ms,
                    "tau_clean_full_ms": clean_ms,
                    # What a deployment actually pays on a bad plan: the
                    # check stops at the first violation.
                    "tau_unsafe_observed_ms": unsafe_obs,
                    # Cost with early exit disabled: the quantity that must
                    # be monotone in b, since it is the only one measuring
                    # the same work across budgets.
                    "tau_unsafe_full_ms": unsafe_full,
                    # Deterministic reservation for the theory's cost model.
                    "tau_envelope_ms": max(
                        [x for x in (clean_ms, unsafe_full) if x is not None],
                        default=None),
                    "n_clean": len(plans), "n_unsafe": len(unsafe),
                })

    return {
        "network": name,
        "n_nodes": len(base.nodes), "n_links": len(base.links),
        "n_flows": len(base.flows),
        "mean_plan_len": round(statistics.mean(len(p) for p in plans), 2),
        # Disjuncts the SMT encoder emits at each budget on the clean base
        # state. Decides A2 structurally where a stopwatch only reports which
        # way the noise fell.
        "encoded_terms": {b: encoded_terms(base, min(3, max(1, b)))
                          for b in BUDGETS},
        "rows": rows,
    }


# A cell counts as flat, not decreasing, when the drop is within this
# fraction of the previous value. Timing noise on repeated Z3 solves is a few
# percent, so a strict `<` on sample means reports spurious violations.
MONOTONE_REL_TOL = 0.05
MONOTONE_ABS_TOL_MS = 0.5


def check_monotone_in_b(rows: List[Dict[str, Any]], mode: str,
                        metric: str = "tau_envelope_ms",
                        terms: Optional[Dict[Tuple[str, int], int]] = None
                        ) -> Dict[str, Any]:
    """Assumption A2: tau must be NON-DECREASING in coverage depth b.

    Judged on the measurement, with a tolerance, and effect sizes returned so
    a marginal call is never silently resolved in the theory's favour.

    ``terms`` -- the disjunct count the SMT encoder emits per (network,
    budget) on the BASE state -- is recorded for context only. An earlier
    version of this check treated a step adding no disjuncts there as flat by
    construction and excluded it from the verdict. That was wrong twice over:
    the envelope is the maximum over clean and violating measurements, and on
    a violating state the integrity layer does emit disjuncts, so the two
    budgets are not handed the same problem; and depth three additionally
    runs a structural prepass over the whole plan that shallower depths skip.
    A2 is an assumption of the theory, held here to the measurement.
    """
    decreases: List[Dict[str, Any]] = []
    flats: List[Dict[str, Any]] = []
    by_construction: List[Dict[str, Any]] = []
    networks = sorted({r["network"] for r in rows})
    for network in networks:
        for e in SCOPES:
            # Compare budgets WITHIN one (network, mode, scope) series. A flat
            # walk over concatenated rows would compare the deepest budget of
            # one topology against the shallowest of the next and report the
            # topology-size jump as a budget violation.
            series = sorted(
                ((r["b"], r[metric]) for r in rows
                 if r["network"] == network and r["mode"] == mode
                 and r["e"] == e and r.get(metric) is not None),
                key=lambda t: t[0])
            for (b0, v0), (b1, v1) in zip(series, series[1:]):
                added = None
                if terms is not None:
                    t0, t1 = terms.get((network, b0)), terms.get((network, b1))
                    if t0 is not None and t1 is not None:
                        added = t1 - t0
                entry = {"network": network, "e": e, "from_b": b0,
                         "to_b": b1, "tau_from_ms": v0, "tau_to_ms": v1,
                         "delta_ms": round(v1 - v0, 4),
                         "delta_pct": (round(100 * (v1 - v0) / v0, 2)
                                       if v0 else None),
                         "encoded_terms_added": added}
                if added == 0:
                    # Recorded, but NOT excused: the base-state count says
                    # nothing about the violating states this envelope also
                    # covers, nor about the structural prepass depth three
                    # runs. The step still has to earn its verdict below.
                    by_construction.append(entry)
                delta = v1 - v0
                if delta >= 0:
                    continue
                tol = max(MONOTONE_REL_TOL * v0, MONOTONE_ABS_TOL_MS)
                (flats if -delta <= tol else decreases).append(entry)
    return {"non_decreasing": not decreases, "decreases": decreases,
            "flat_within_tol": flats,
            "steps_adding_no_base_disjunct": by_construction,
            "terms_available": terms is not None,
            "n_series": len(networks) * len(SCOPES)}


def monotone_in_b(rows: List[Dict[str, Any]], mode: str) -> bool:
    """Boolean form of :func:`check_monotone_in_b`."""
    return bool(check_monotone_in_b(rows, mode)["non_decreasing"])


def run_costbench(cfg: CostBenchConfig) -> Dict[str, Any]:
    """Sweep every configured network; returns results plus load context."""
    names = cfg.resolved_networks()
    load_start = _loadavg()
    t0 = time.perf_counter()

    results: List[Dict[str, Any]] = []
    all_rows: List[Dict[str, Any]] = []
    for i, name in enumerate(names, 1):
        res = bench_network(name, cfg)
        results.append(res)
        all_rows.extend(res.get("rows", []))
        logger.info("[%d/%d] %s: %s", i, len(names), name,
                    "skipped" if "skipped" in res
                    else f"{res['n_nodes']}n/{res['n_links']}l")

    load_end = _loadavg()
    terms_by_network = {r["network"]: r["encoded_terms"]
                        for r in results if "encoded_terms" in r}
    terms = {(net, int(b)): n
             for net, per_b in terms_by_network.items()
             for b, n in per_b.items()}
    # Judge the measurement by its own stability, not by the machine's load
    # average: on a desktop the idle baseline already exceeds any useful
    # absolute threshold, and this process's own core counts toward it.
    cvs = [r["max_cv"] for r in all_rows if r.get("max_cv") is not None]
    worst_cv = max(cvs) if cvs else None
    unstable = [r for r in all_rows
                if (r.get("max_cv") or 0) > CV_UNSTABLE
                and (r.get("tau_envelope_ms") or 0) > CV_MIN_MS]
    contended = bool(unstable)
    if contended:
        logger.warning("%d/%d cells exceed CV %.2f (worst %.3f) -- those "
                       "timings are unstable and must not be cited",
                       len(unstable), len(all_rows), CV_UNSTABLE,
                       worst_cv or 0)

    return {
        "results": results,
        "rows": all_rows,
        "elapsed_s": round(time.perf_counter() - t0, 1),
        # Load average is recorded as context only; it does not gate the run.
        "loadavg_start": load_start, "loadavg_end": load_end,
        "contended": contended,
        "worst_cv": worst_cv, "cv_threshold": CV_UNSTABLE,
        "n_unstable_cells": len(unstable), "n_cells": len(all_rows),
        # A2 is asserted on the envelope, the only series measuring the same
        # work at every budget. The clean-plan series is reported alongside
        # because it is what an earlier round used, and it can be flat where
        # the envelope rises.
        "encoded_terms_by_network": terms_by_network,
        "tau_monotone_in_b": {
            m: check_monotone_in_b(all_rows, m, "tau_envelope_ms",
                                   terms if m == "smt" else None)
            for m in VERIFIERS},
        "tau_monotone_in_b_clean_only": {
            m: check_monotone_in_b(all_rows, m, "tau_clean_full_ms",
                                   terms if m == "smt" else None)
            for m in VERIFIERS},
    }


__all__ = [
    "CostBenchConfig",
    "VERIFIERS",
    "bench_network",
    "check_monotone_in_b",
    "make_clean_plans",
    "monotone_in_b",
    "run_costbench",
]
