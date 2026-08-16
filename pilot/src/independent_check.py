"""A second, structurally separate implementation of the invariant checker.

Why this exists. The gate decides with the Z3 encoding and the evaluation
scores with the reference predicate checker. Those are two code paths, but
they were built together and are conformance-equivalent by design, so a
report of zero unsafe actuation partly reflects that shared lineage. This
module re-derives the same three invariant classes from their definitions in
the system model, using different data structures and a different traversal
order, and consumes only the SERIALIZED state -- it never imports NetState,
apply_op, or anything in :mod:`invariants`.

What this does and does not buy. Two implementations of one specification
can disagree on implementation mistakes, and that is what a cross-check
detects. It cannot detect an error in the specification itself, and it is
not a network emulator: agreement here says the modelled predicates were
computed correctly, not that the modelled predicates capture what a real
network would do.

Deliberate differences from the reference implementation:
  * topology is a networkx graph; link load accumulates onto edge attributes
    while walking each flow once, instead of scanning all links per flow;
  * flow latency is summed from edge and node attributes gathered along the
    path via graph lookups rather than an index rebuilt per query;
  * ACL conflicts are found by grouping rules into a mapping from ordered
    pair to the set of actions, rather than by first-wins comparison;
  * disabled-node traversal is a set intersection between the path and the
    disabled set.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

import networkx as nx

logger = logging.getLogger(__name__)

Violation = Dict[str, Any]
TOL = 1e-9


def build_graph(state: Dict[str, Any]) -> nx.Graph:
    """Serialized state -> annotated graph. No project types involved."""
    g = nx.Graph()
    for node_id, node in state["nodes"].items():
        g.add_node(node_id,
                   slots=node["vnf_slots"], replicas=node["replicas"],
                   base_ms=node["base_ms"], enabled=bool(node["enabled"]))
    for link_id, link in state["links"].items():
        # One edge per node pair, carrying its identifier and capacity.
        g.add_edge(link["a"], link["b"], link_id=link_id,
                   cap=float(link["cap"]), lat_ms=float(link["lat_ms"]),
                   load=0.0)
    return g


def _walk(g: nx.Graph, path: List[str]) -> Optional[List[Tuple[str, str]]]:
    """Edge sequence for a node path, or None if some hop is not an edge."""
    hops = list(zip(path, path[1:]))
    for u, v in hops:
        if not g.has_edge(u, v):
            return None
    return hops


def accumulate_load(g: nx.Graph, state: Dict[str, Any]) -> Optional[str]:
    """Push every flow's demand and every slice reservation onto edges."""
    for flow_id, flow in state["flows"].items():
        hops = _walk(g, flow["path"])
        if hops is None:
            return f"flow {flow_id} has a path that is not a walk in the graph"
        for u, v in hops:
            g[u][v]["load"] += float(flow["bw"])
    by_id = {d["link_id"]: (u, v) for u, v, d in g.edges(data=True)}
    for slice_id, sl in state.get("slices", {}).items():
        for link_id in sl["links"]:
            edge = by_id.get(link_id)
            if edge is None:
                return f"slice {slice_id} reserves unknown link {link_id}"
            g[edge[0]][edge[1]]["load"] += float(sl["bw"])
    return None


def flow_latency(g: nx.Graph, flow: Dict[str, Any]) -> Optional[float]:
    hops = _walk(g, flow["path"])
    if hops is None:
        return None
    total = sum(g[u][v]["lat_ms"] for u, v in hops)
    for node_id in flow["path"]:
        nd = g.nodes[node_id]
        total += nd["base_ms"] / max(1, nd["replicas"])
    return total


def check_state(state: Dict[str, Any],
                classes: Iterable[str] = ("I1", "I2", "I3")
                ) -> List[Violation]:
    """Violations of the selected invariant classes in a serialized state."""
    wanted = set(classes)
    out: List[Violation] = []
    g = build_graph(state)

    err = accumulate_load(g, state)
    if err and "I3" in wanted:
        out.append({"cls": "I3", "kind": "structural", "detail": err})

    if "I1" in wanted:
        for u, v, d in g.edges(data=True):
            if d["load"] > d["cap"] + TOL:
                out.append({"cls": "I1", "kind": "link_overload",
                            "link": d["link_id"], "load": round(d["load"], 6),
                            "cap": d["cap"]})
        for node_id, nd in g.nodes(data=True):
            if nd["replicas"] > nd["slots"]:
                out.append({"cls": "I1", "kind": "vnf_slots",
                            "node": node_id, "replicas": nd["replicas"],
                            "slots": nd["slots"]})

    if "I2" in wanted:
        for flow_id, flow in state["flows"].items():
            lat = flow_latency(g, flow)
            if lat is not None and lat > float(flow["sla_ms"]) + TOL:
                out.append({"cls": "I2", "kind": "sla_latency",
                            "flow": flow_id, "lat": round(lat, 6),
                            "sla": float(flow["sla_ms"])})
            if flow.get("priority") and \
                    float(flow["bw"]) < float(flow["min_bw"]) - TOL:
                out.append({"cls": "I2", "kind": "priority_bw",
                            "flow": flow_id, "bw": float(flow["bw"]),
                            "min_bw": float(flow["min_bw"])})

    if "I3" in wanted:
        actions: Dict[Tuple[str, str], Set[str]] = defaultdict(set)
        for rule in state["acls"].values():
            actions[(rule["src"], rule["dst"])].add(rule["action"])
        for pair, acts in actions.items():
            if len(acts) > 1:
                out.append({"cls": "I3", "kind": "acl_conflict",
                            "pair": list(pair)})
        disabled = {n for n, nd in g.nodes(data=True) if not nd["enabled"]}
        for flow_id, flow in state["flows"].items():
            if disabled.intersection(flow["path"]):
                out.append({"cls": "I3", "kind": "flow_via_disabled",
                            "flow": flow_id})
    return out


def summarize(viols: List[Violation]) -> Dict[str, int]:
    counts = {"I1": 0, "I2": 0, "I3": 0}
    for v in viols:
        counts[v["cls"]] = counts.get(v["cls"], 0) + 1
    return counts


def is_unsafe(state: Dict[str, Any],
              classes: Iterable[str] = ("I1", "I2", "I3")) -> bool:
    return bool(check_state(state, classes))


__all__ = ["accumulate_load", "build_graph", "check_state", "flow_latency",
           "is_unsafe", "summarize"]
