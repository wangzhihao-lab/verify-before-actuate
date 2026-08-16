"""Intents whose only safe plans require a particular operation ORDER.

Reported as a separate suite, never pooled with the natural corpus. The
natural corpus produced no plan that is terminal-safe but prefix-unsafe, so
prefix checking bought nothing there. That is a statement about one error
distribution, not about the semantics. This suite constructs the error
distribution in which the distinction is reachable, so the temporal knob can
be evaluated on its own terms instead of being argued for or dismissed on
the basis of a corpus that never exercises it.

Pooling these into the natural violation rate would manufacture the very
advantage the natural corpus failed to show, which is why they are generated,
stored and analysed separately.

Each class has the same shape: a goal that is achievable, a correct order
that keeps every intermediate state safe, and a natural wrong order whose
intermediate state violates an invariant that the final state does not.

``acl_replace``      block a currently allowed pair. Adding the deny before
                     removing the allow leaves both rules present for one
                     step.
``bandwidth_move``   move a flow to a new path AND raise its bandwidth.
                     Raising first overloads the old path for one step.
``drain_node``       take a transited node out of service. Disabling before
                     rerouting strands flows on it for one step.
``scale_after_move`` reduce a node's replicas. Scaling down before moving the
                     latency-sensitive flows away breaks their SLA for one
                     step.
"""
from __future__ import annotations

import logging
import random
from typing import Any, Dict, List, Optional, Tuple

from ..netmodel import NetState
from .intent_gen import endpoint_candidates, transit_candidates

logger = logging.getLogger(__name__)

Intent = Dict[str, Any]

TEMPORAL_KINDS: Tuple[str, ...] = (
    "acl_replace", "bandwidth_move", "drain_node", "scale_after_move")


def _meta(kind: str, feasible: bool, stresses: str,
          reason: Optional[str] = None, **extra: Any) -> Dict[str, Any]:
    meta = {"requested_kind": kind, "actual_kind": kind,
            "kind_fallback": False, "expected_feasible": feasible,
            "infeasibility_reason": reason, "stresses": stresses,
            "requires_ordering": True, "suite": "temporal"}
    meta.update(extra)
    return meta


def _acl_replace(st: NetState, rng: random.Random,
                 guarded: bool) -> Optional[Tuple[Intent, Dict[str, Any]]]:
    allow = [(rid, r["src"], r["dst"]) for rid, r in st.acls.items()
             if r["action"] == "allow"]
    if not allow:
        return None
    rid, src, dst = rng.choice(allow)
    clause = ("Remove the existing permit BEFORE adding the deny; the two "
              "rules must never both be present. ") if guarded else ""
    text = (f"Traffic from {src} to {dst} is currently permitted by rule "
            f"{rid}. Block it. " + clause).strip()
    return ({"kind": "acl", "src": src, "dst": dst, "text": text,
             "tight": True},
            _meta("acl_replace", True, "I3-acl-conflict",
                  existing_allow_rule=rid))


def _bandwidth_move(st: NetState, rng: random.Random,
                    guarded: bool) -> Optional[Tuple[Intent, Dict[str, Any]]]:
    """Raise a flow's bandwidth past what its CURRENT path can absorb."""
    for fid in rng.sample(sorted(st.flows), min(12, len(st.flows))):
        flow = st.flows[fid]
        lids = st.path_links(flow["path"]) or []
        if not lids:
            continue
        spare = min(st.links[l]["cap"] - st.link_load(l) for l in lids)
        alt = st.shortest_path(flow["path"][0], flow["path"][-1],
                               avoid=set(flow["path"][1:-1]))
        if alt is None or alt == flow["path"]:
            continue
        alt_l = st.path_links(alt) or []
        if not alt_l:
            continue
        alt_spare = min(st.links[l]["cap"] - st.link_load(l) for l in alt_l)
        target = round(flow["bw"] + spare + 1.0, 2)
        # Reachable on the alternate path, not on the current one: the order
        # of "move" and "raise" is what decides whether a step overloads.
        if alt_spare <= spare + 1.0:
            continue
        clause = ("Move the flow to a path with room BEFORE raising its "
                  "bandwidth; no link may be over capacity at any step. "
                  ) if guarded else ""
        text = (f"Increase the bandwidth of flow {fid} to {target} Mb/s, "
                f"keeping its endpoints. " + clause).strip()
        return ({"kind": "bandwidth", "flow": fid, "target": target,
                 "text": text, "tight": True},
                _meta("bandwidth_move", True, "I1-link-capacity",
                      alt_path=alt))
    return None


def _drain_node(st: NetState, rng: random.Random,
                guarded: bool) -> Optional[Tuple[Intent, Dict[str, Any]]]:
    cands = transit_candidates(st)
    if not cands:
        return None
    nid = rng.choice(cands)
    clause = ("Reroute every affected flow off the node BEFORE disabling it; "
              "no flow may traverse a disabled node at any step. "
              ) if guarded else ""
    text = (f"Node {nid} must be taken out of service for maintenance. "
            f"Disable it. " + clause).strip()
    return ({"kind": "maintenance", "node": nid, "text": text, "tight": True},
            _meta("drain_node", True, "I3-flow-via-disabled"))


def _scale_after_move(st: NetState, rng: random.Random,
                      guarded: bool) -> Optional[Tuple[Intent, Dict[str, Any]]]:
    """Scale a node down far enough to break an SLA unless flows move first."""
    for nid in rng.sample(sorted(st.nodes), min(15, len(st.nodes))):
        if st.nodes[nid]["replicas"] <= 1:
            continue
        probe = st.clone()
        probe.nodes[nid]["replicas"] = 1
        broken = [f for f in st.flows
                  if probe.flow_latency_ms(f) > st.flows[f]["sla_ms"] + 1e-9]
        if not broken:
            continue
        # Only useful if the broken flows can be routed off the node.
        movable = all(
            st.shortest_path(st.flows[f]["path"][0], st.flows[f]["path"][-1],
                             avoid={nid}) is not None
            for f in broken if nid in st.flows[f]["path"][1:-1])
        if not movable:
            continue
        clause = ("Move latency-sensitive flows off the node BEFORE reducing "
                  "its replicas; every flow's SLA must hold at each step. "
                  ) if guarded else ""
        text = (f"Reduce the VNF at node {nid} to 1 replica to free capacity. "
                + clause).strip()
        return ({"kind": "scaling", "node": nid, "replicas": 1, "text": text,
                 "tight": True},
                _meta("scale_after_move", True, "I2-sla-latency",
                      n_flows_at_risk=len(broken)))
    return None


_BUILDERS = {
    "acl_replace": _acl_replace,
    "bandwidth_move": _bandwidth_move,
    "drain_node": _drain_node,
    "scale_after_move": _scale_after_move,
}


def order_witnesses(st: NetState, kind: str, intent: Intent,
                    meta: Dict[str, Any]
                    ) -> Tuple[Optional[List[Dict[str, Any]]],
                               Optional[List[Dict[str, Any]]]]:
    """The (wrong-order, right-order) plans this class is built around."""
    if kind == "acl_replace":
        add = {"op": "add_acl", "rule_id": "AX", "src": intent["src"],
               "dst": intent["dst"], "action": "deny"}
        rem = {"op": "remove_acl", "rule_id": meta["existing_allow_rule"]}
        return [add, rem], [rem, add]

    if kind == "bandwidth_move":
        fid, alt = intent["flow"], meta["alt_path"]
        setb = {"op": "set_flow_bw", "flow": fid, "bw_mbps": intent["target"]}
        move = {"op": "reroute_flow", "flow": fid, "path": alt}
        return [setb, move], [move, setb]

    if kind == "drain_node":
        nid = intent["node"]
        moves = []
        for fid, flow in st.flows.items():
            if nid not in flow["path"][1:-1]:
                continue
            alt = st.shortest_path(flow["path"][0], flow["path"][-1],
                                   avoid={nid})
            if alt is None:
                return None, None
            moves.append({"op": "reroute_flow", "flow": fid, "path": alt})
        disable = {"op": "disable_node", "node": nid}
        return [disable] + moves, moves + [disable]

    if kind == "scale_after_move":
        nid = intent["node"]
        probe = st.clone()
        probe.nodes[nid]["replicas"] = 1
        moves = []
        for fid, flow in st.flows.items():
            if probe.flow_latency_ms(fid) <= flow["sla_ms"] + 1e-9:
                continue
            # A flow that terminates at the node cannot be routed off it, so
            # no ordering saves it; such a topology is dropped, not patched.
            if nid not in flow["path"][1:-1]:
                return None, None
            alt = st.shortest_path(flow["path"][0], flow["path"][-1],
                                   avoid={nid})
            if alt is None:
                return None, None
            moves.append({"op": "reroute_flow", "flow": fid, "path": alt})
        scale = {"op": "scale_vnf", "node": nid, "replicas": 1}
        return [scale] + moves, moves + [scale]

    return None, None


def make_temporal_intent(st: NetState, rng: random.Random, kind: str,
                         guarded: bool
                         ) -> Optional[Tuple[Intent, Dict[str, Any]]]:
    """Build a temporal-stress intent, or None if this topology admits none.

    An intent is emitted only when the class's defining property actually
    holds on this topology: a correct order exists that is safe at every
    prefix and fulfils the goal, and the natural wrong order violates an
    invariant at some prefix while ending in a safe final state. Emitting an
    intent without checking would put cases in the suite that do not
    discriminate between temporal scopes, which is precisely what the suite
    is for.
    """
    from ..intents import intent_fulfilled
    from ..semantics import is_unsafe

    builder = _BUILDERS.get(kind)
    if builder is None:
        raise ValueError(f"unknown temporal kind {kind!r}")
    got = builder(st, rng, guarded)
    if got is None:
        return None
    intent, meta = got

    wrong, right = order_witnesses(st, kind, intent, meta)
    if not wrong or not right:
        return None
    if is_unsafe(st, right, "prefix", 3):
        return None                      # no safe ordering exists
    if intent_fulfilled(st, intent, right) is not True:
        return None                      # the safe ordering misses the goal
    if not is_unsafe(st, wrong, "prefix", 3):
        return None                      # order does not matter here
    if is_unsafe(st, wrong, "term", 3):
        return None                      # wrong order is not transient-only

    meta = {**meta, "witness_wrong_order": wrong, "witness_right_order": right,
            "verified_transient": True}
    return intent, meta


__all__ = ["TEMPORAL_KINDS", "make_temporal_intent"]
