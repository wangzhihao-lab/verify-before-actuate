"""Continuous coverage budget over predicate instances.

The system model assumes the budget set is a compact interval with
\\(p\\in C^1\\), \\(p(0)=0\\), \\(p'(b)>0\\) and \\(p(b)\\le\\bar p<1\\). The
three-level instantiation ``b in {1,2,3}`` satisfies none of that: it is
discrete, and its deepest level detects every loss event in the corpus, which
contradicts \\(p(b)<1\\) outright. Any attempt to fit the assumed
exponential family to three points, one of which sits at 1, measures nothing.

This module supplies the budget the model actually assumes. A verification
profile at coverage \\(b\\in(0,1]\\) checks the first \\(\\lceil b|P|\\rceil\\)
predicate INSTANCES of a state under a fixed, declared priority order, where
an instance is one predicate applied to one object -- the capacity of one
link, the SLA of one flow. Coverage is therefore a real number and detection
grows with it in small steps rather than in three jumps.

Two priority orders are provided because they answer different questions and
mixing them would be silently misleading:

``class``        group by invariant class, then by identifier. Recovers the
                 nested instantiation at b = 1/3, 2/3, 1, so archived
                 three-level results remain comparable.
``interleaved``  a fixed deterministic permutation across all classes.
                 Coverage then grows evenly over the whole predicate set,
                 which is the order that yields a smooth curve suitable for
                 fitting a technology family.

Structural validity is a property of the transition, not of a state, so it
enters as a single instance in the I3 group rather than one per object.
"""
from __future__ import annotations

import hashlib
import logging
import math
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .netmodel import NetState

logger = logging.getLogger(__name__)

# (class, kind, object-id). The object id is "*" for the single structural
# instance, whose scope is the whole plan.
Pred = Tuple[str, str, str]

CLASS_RANK = {"I1": 0, "I2": 1, "I3": 2}
ORDERS = ("class", "interleaved")


def predicate_instances(st: NetState) -> List[Pred]:
    """Every predicate instance a full-coverage checker would evaluate."""
    preds: List[Pred] = []
    for link_id in sorted(st.links):
        preds.append(("I1", "link_overload", link_id))
    for node_id in sorted(st.nodes):
        preds.append(("I1", "vnf_slots", node_id))
    for flow_id in sorted(st.flows):
        preds.append(("I2", "sla_latency", flow_id))
    for flow_id in sorted(st.flows):
        if st.flows[flow_id].get("priority"):
            preds.append(("I2", "priority_bw", flow_id))
    pairs = sorted({(r["src"], r["dst"]) for r in st.acls.values()})
    for src, dst in pairs:
        preds.append(("I3", "acl_conflict", f"{src}->{dst}"))
    for flow_id in sorted(st.flows):
        preds.append(("I3", "flow_via_disabled", flow_id))
    preds.append(("I3", "structural", "*"))
    return preds


def _stable_hash(pred: Pred, salt: str) -> int:
    raw = f"{salt}|{pred[0]}|{pred[1]}|{pred[2]}".encode()
    return int(hashlib.sha256(raw).hexdigest()[:12], 16)


def priority_order(preds: Sequence[Pred], order: str = "class",
                   salt: str = "coverage-v1") -> List[Pred]:
    """Declared evaluation order. Deterministic and independent of input order."""
    if order == "class":
        return sorted(preds, key=lambda p: (CLASS_RANK[p[0]], p[1], p[2]))
    if order == "interleaved":
        # A fixed permutation, not a random one: the salt is part of the
        # published configuration so the order is reproducible.
        return sorted(preds, key=lambda p: _stable_hash(p, salt))
    raise ValueError(f"unknown order {order!r}")


def budget_count(n_base: int, frac: float) -> int:
    """Absolute number of predicate evaluations a budget buys."""
    if not 0.0 <= frac <= 1.0:
        raise ValueError(f"coverage fraction out of range: {frac}")
    if frac <= 0.0:
        return 0
    return max(1, math.ceil(frac * n_base - 1e-9))


def select_k(preds: Sequence[Pred], k: int,
             order: str = "class") -> List[Pred]:
    """The first ``k`` instances of THIS state under ``order``.

    The budget is an absolute count rather than a fraction of the current
    population. A plan can create objects, and if the budget were a fraction
    it would silently grow as the plan added them -- which is how a budget of
    "resource plus SLA" ended up detecting an access-control conflict that
    the same nominal depth is defined not to look at. With a fixed count, new
    objects compete for the same evaluations under the declared order, which
    is what a resource-bounded checker actually does.
    """
    ordered = priority_order(preds, order)
    return ordered[:max(0, min(k, len(ordered)))]


def select(preds: Sequence[Pred], frac: float,
           order: str = "class") -> List[Pred]:
    """Convenience: budget derived from this state's own instance count."""
    return select_k(preds, budget_count(len(preds), frac), order)


def check_selected(st: NetState, selected: Iterable[Pred]
                   ) -> List[Dict[str, Any]]:
    """Evaluate only the selected predicate instances on one state.

    Mirrors the reference checker predicate for predicate; the difference is
    that each object is looked up individually instead of scanning a class.
    """
    out: List[Dict[str, Any]] = []
    for cls, kind, obj in selected:
        if kind == "link_overload":
            if obj not in st.links:
                continue
            load = st.link_load(obj)
            cap = st.links[obj]["cap"]
            if load > cap + 1e-9:
                out.append({"cls": cls, "kind": kind, "link": obj,
                            "load": round(load, 1), "cap": cap})
        elif kind == "vnf_slots":
            node = st.nodes.get(obj)
            if node and node["replicas"] > node["vnf_slots"]:
                out.append({"cls": cls, "kind": kind, "node": obj,
                            "replicas": node["replicas"],
                            "slots": node["vnf_slots"]})
        elif kind == "sla_latency":
            flow = st.flows.get(obj)
            if flow is None:
                continue
            lat = st.flow_latency_ms(obj)
            if lat > flow["sla_ms"] + 1e-9:
                out.append({"cls": cls, "kind": kind, "flow": obj,
                            "lat": round(lat, 2), "sla": flow["sla_ms"]})
        elif kind == "priority_bw":
            flow = st.flows.get(obj)
            if flow and flow.get("priority") and \
                    flow["bw"] < flow["min_bw"] - 1e-9:
                out.append({"cls": cls, "kind": kind, "flow": obj,
                            "bw": flow["bw"], "min_bw": flow["min_bw"]})
        elif kind == "acl_conflict":
            src, _, dst = obj.partition("->")
            acts = {r["action"] for r in st.acls.values()
                    if r["src"] == src and r["dst"] == dst}
            if len(acts) > 1:
                out.append({"cls": cls, "kind": kind, "pair": [src, dst]})
        elif kind == "flow_via_disabled":
            flow = st.flows.get(obj)
            if flow and any(not st.nodes[n]["enabled"] for n in flow["path"]
                            if n in st.nodes):
                out.append({"cls": cls, "kind": kind, "flow": obj})
    return out


def coverage_of_classes(st: NetState, classes: Sequence[str],
                        order: str = "class") -> float:
    """The coverage fraction equivalent to checking whole classes.

    Lets the archived three-level results be placed on the continuous axis
    instead of being compared against it by assertion.
    """
    preds = predicate_instances(st)
    n_sel = sum(1 for p in preds if p[0] in set(classes))
    return n_sel / len(preds) if preds else 0.0


def structural_selected(selected: Iterable[Pred]) -> bool:
    return any(k == "structural" for _, k, _ in selected)


__all__ = ["ORDERS", "Pred", "budget_count", "check_selected",
           "coverage_of_classes", "predicate_instances", "priority_order",
           "select", "select_k", "structural_selected"]
