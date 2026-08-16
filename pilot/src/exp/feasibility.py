"""Constructive feasibility certificates for intents.

The corpus previously labelled an intent feasible by construction for three
kinds and by assumption for the other two, and the assumption was wrong: a
bandwidth target can exceed every path's capacity, and a slice reservation
can exceed the capacity of a link it names. Neither admits any plan, yet both
entered the population the renewal model conditions on.

An a-priori label is not worth trusting when the same code can decide the
question. This module answers it per intent, with one of three verdicts:

FEASIBLE      a witness plan was constructed and verified: it fulfils the
              intent AND satisfies every modelled invariant at every prefix.
              The certificate is the plan itself, stored with the verdict.
INFEASIBLE    a necessary condition fails, so no plan exists. Deliberately
              the weakest available test, since everything it rejects must
              be rejected under any search.
UNKNOWN       neither the search found a witness nor a necessary condition
              failed. Reported separately and never silently pooled with
              either side: an exhausted search is evidence about the search.

The witness search is intentionally simple -- reroute onto a widest-bottleneck
path, free capacity by trimming non-priority flows, then act. It is a
sufficiency oracle, not a planner, and its failures are reported as UNKNOWN
rather than dressed up as infeasibility.
"""
from __future__ import annotations

import heapq
import logging
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..invariants import check_plan
from ..intents import intent_fulfilled
from ..netmodel import NetState, Op

logger = logging.getLogger(__name__)

FEASIBLE = "feasible"
INFEASIBLE = "infeasible"
UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# necessary conditions: anything failing these admits no plan at all
# ---------------------------------------------------------------------------

def widest_paths(st: NetState, src: str, dst: str,
                 k: int = 6) -> List[List[str]]:
    """Paths from src to dst ordered by decreasing bottleneck capacity.

    Capacity, not spare capacity: a necessary condition must allow every
    other flow to be moved out of the way, so only the physical width of the
    narrowest link on a path can rule a target out.
    """
    adj: Dict[str, List[Tuple[str, float]]] = {n: [] for n in st.nodes}
    for link in st.links.values():
        adj[link["a"]].append((link["b"], link["cap"]))
        adj[link["b"]].append((link["a"], link["cap"]))

    # Max-min widening search, keeping several distinct routes rather than
    # one, so the witness stage has alternatives when the widest path is
    # unusable for a reason capacity alone does not express.
    out: List[List[str]] = []
    seen_paths = set()
    heap: List[Tuple[float, int, List[str]]] = [(-float("inf"), 0, [src])]
    counter = 0
    while heap and len(out) < k:
        negw, _, path = heapq.heappop(heap)
        node = path[-1]
        if node == dst:
            key = tuple(path)
            if key not in seen_paths:
                seen_paths.add(key)
                out.append(path)
            continue
        for nxt, cap in adj.get(node, []):
            if nxt in path:
                continue
            counter += 1
            heapq.heappush(heap, (max(negw, -cap), counter, path + [nxt]))
    return out


def path_width(st: NetState, path: Sequence[str]) -> float:
    lids = st.path_links(list(path))
    if not lids:
        return 0.0
    return min(st.links[l]["cap"] for l in lids)


def _connected_without(st: NetState, src: str, dst: str, drop: str) -> bool:
    """Is dst reachable from src in the graph with ``drop`` removed?"""
    adj: Dict[str, List[str]] = {n: [] for n in st.nodes}
    for link in st.links.values():
        if drop in (link["a"], link["b"]):
            continue
        adj[link["a"]].append(link["b"])
        adj[link["b"]].append(link["a"])
    stack, seen = [src], {src}
    while stack:
        node = stack.pop()
        if node == dst:
            return True
        for nxt in adj.get(node, []):
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return dst in seen


def necessary_failure(st: NetState, intent: Dict[str, Any]) -> Optional[str]:
    """Reason this intent admits no plan, or None if none is provable."""
    kind = intent.get("kind")
    if kind == "bandwidth":
        fid = intent["flow"]
        if fid not in st.flows:
            return f"flow {fid} does not exist"
        target = float(intent["target"])
        path = st.flows[fid]["path"]
        best = max((path_width(st, p)
                    for p in widest_paths(st, path[0], path[-1])),
                   default=0.0)
        if target > best + 1e-9:
            return (f"target {target:g} exceeds the widest bottleneck "
                    f"{best:g} between {path[0]} and {path[-1]}")
    elif kind == "slice":
        bw = float(intent["bw"])
        for lid in intent.get("links", []):
            if lid not in st.links:
                return f"slice names unknown link {lid}"
            if bw > st.links[lid]["cap"] + 1e-9:
                return (f"reservation {bw:g} exceeds capacity "
                        f"{st.links[lid]['cap']:g} of link {lid}")
    elif kind == "scaling":
        nid = intent["node"]
        if nid not in st.nodes:
            return f"node {nid} does not exist"
        if int(intent["replicas"]) > st.nodes[nid]["vnf_slots"]:
            return (f"{intent['replicas']} replicas exceed "
                    f"{st.nodes[nid]['vnf_slots']} slots at {nid}")
    elif kind == "maintenance":
        nid = intent["node"]
        if nid not in st.nodes:
            return f"node {nid} does not exist"
        for fid, flow in st.flows.items():
            if nid in (flow["path"][0], flow["path"][-1]):
                return f"{nid} is an endpoint of flow {fid}"
            # A flow whose endpoints are separated by removing this node has
            # nowhere to go, whatever the capacities: the node is a cut
            # vertex for that pair, so no plan can drain and disable it.
            if nid in flow["path"] and not _connected_without(
                    st, flow["path"][0], flow["path"][-1], nid):
                return (f"{nid} is a cut vertex for flow {fid} between "
                        f"{flow['path'][0]} and {flow['path'][-1]}")
    return None


# ---------------------------------------------------------------------------
# witness construction
# ---------------------------------------------------------------------------

def free_capacity(st: NetState, lids: Sequence[str], need: float,
                  protect: Sequence[str] = ()) -> List[Op]:
    """Ops making room for ``need`` Mbps on every link in ``lids``.

    Two levers, cheapest first: move a competing flow off the link entirely,
    or shrink it toward its floor. Rerouting is tried first because it frees
    the whole flow rather than part of it and costs the moved flow nothing.

    Priority flows are never shrunk -- their minimum bandwidth is itself an
    invariant, so buying room by starving one yields a plan the checker
    rejects. They may still be rerouted, which preserves their bandwidth.
    """
    ops: List[Op] = []
    work = st.clone()
    protected = set(protect)
    for lid in lids:
        for _ in range(len(work.flows) + 1):
            slack = work.links[lid]["cap"] - work.link_load(lid)
            if slack >= need - 1e-9:
                break
            riders = sorted(
                (f for f, fl in work.flows.items()
                 if f not in protected
                 and lid in (work.path_links(fl["path"]) or [])),
                key=lambda f: -work.flows[f]["bw"])
            if not riders:
                break
            moved = False
            for fid in riders:
                flow = work.flows[fid]
                for alt in widest_paths(work, flow["path"][0],
                                        flow["path"][-1]):
                    alt_lids = work.path_links(list(alt)) or []
                    if lid in alt_lids or list(alt) == list(flow["path"]):
                        continue
                    if any(work.links[l]["cap"] - work.link_load(l)
                           < flow["bw"] - 1e-9 for l in alt_lids):
                        continue
                    ops.append({"op": "reroute_flow", "flow": fid,
                                "path": list(alt)})
                    flow["path"] = list(alt)
                    moved = True
                    break
                if moved:
                    break
            if moved:
                continue
            shrinkable = [f for f in riders
                          if not work.flows[f].get("priority")]
            if not shrinkable:
                break
            fid = shrinkable[0]
            flow = work.flows[fid]
            floor = float(flow.get("min_bw") or 1.0)
            reduce_to = max(floor, flow["bw"] - (need - slack))
            if reduce_to >= flow["bw"] - 1e-9:
                break
            ops.append({"op": "set_flow_bw", "flow": fid,
                        "bw_mbps": round(reduce_to, 2)})
            flow["bw"] = reduce_to
    return ops


def candidate_plans(st: NetState, intent: Dict[str, Any]) -> List[List[Op]]:
    """Plans worth testing as witnesses, cheapest and most direct first."""
    kind = intent.get("kind")
    plans: List[List[Op]] = []

    if kind == "bandwidth":
        fid, target = intent["flow"], float(intent["target"])
        setop: Op = {"op": "set_flow_bw", "flow": fid, "bw_mbps": target}
        plans.append([setop])
        path = st.flows[fid]["path"]
        # Room must be made for the INCREMENT on the current path, but for
        # the whole target on a path the flow is moving onto.
        here = free_capacity(st, st.path_links(path) or [],
                             max(0.0, target - st.flows[fid]["bw"]),
                             protect=[fid])
        if here:
            plans.append(here + [setop])
        for alt in widest_paths(st, path[0], path[-1]):
            if list(alt) == list(path) or path_width(st, alt) < target:
                continue
            reroute: Op = {"op": "reroute_flow", "flow": fid,
                           "path": list(alt)}
            plans.append([reroute, setop])
            lids = st.path_links(list(alt)) or []
            room = free_capacity(st, lids, target, protect=[fid])
            if room:
                plans.append(room + [reroute, setop])

    elif kind == "slice":
        bw, lids = float(intent["bw"]), list(intent["links"])
        reserve: Op = {"op": "reserve_slice", "slice": "SW",
                       "links": lids, "bw_mbps": bw}
        plans.append([reserve])
        room = free_capacity(st, lids, bw)
        if room:
            plans.append(room + [reserve])

    elif kind == "maintenance":
        nid = intent["node"]
        moves: List[Op] = []
        work = st.clone()
        stuck = False
        for fid, flow in sorted(work.flows.items()):
            if nid not in flow["path"]:
                continue
            placed = False
            for alt in widest_paths(work, flow["path"][0], flow["path"][-1]):
                if nid in alt:
                    continue
                alt_lids = work.path_links(list(alt)) or []
                if any(work.links[l]["cap"] - work.link_load(l)
                       < flow["bw"] - 1e-9 for l in alt_lids):
                    continue
                moves.append({"op": "reroute_flow", "flow": fid,
                              "path": list(alt)})
                work.flows[fid]["path"] = list(alt)
                placed = True
                break
            if not placed:
                # Leaving a flow on the node guarantees the disable step
                # violates; emit the plan anyway so the failure is visible
                # as an unmet witness rather than a silently short plan.
                stuck = True
        plans.append(moves + [{"op": "disable_node", "node": nid}])
        if stuck:
            logger.debug("maintenance %s: a flow could not be moved off",
                         nid)

    elif kind == "acl":
        src, dst = intent["src"], intent["dst"]
        drops: List[Op] = [{"op": "remove_acl", "rule_id": rid}
                           for rid, r in sorted(st.acls.items())
                           if r["src"] == src and r["dst"] == dst]
        add: Op = {"op": "add_acl", "rule_id": "AW", "src": src,
                   "dst": dst, "action": "deny"}
        plans.append(drops + [add])

    elif kind == "scaling":
        plans.append([{"op": "scale_vnf", "node": intent["node"],
                       "replicas": int(intent["replicas"])}])

    return plans


def certify(st: NetState, intent: Dict[str, Any]) -> Dict[str, Any]:
    """Decide one intent. Returns the verdict, the reason and any witness."""
    why = necessary_failure(st, intent)
    if why:
        return {"verdict": INFEASIBLE, "reason": why, "witness": None}

    for plan in candidate_plans(st, intent):
        if intent_fulfilled(st, intent, plan) is not True:
            continue
        # Prefix safety, not just a safe end state: check_plan evaluates the
        # invariants after EVERY operation, so an empty violation list is
        # exactly the contract the gate enforces.
        if check_plan(st, plan):
            continue
        return {"verdict": FEASIBLE, "reason": "witness verified",
                "witness": plan}

    return {"verdict": UNKNOWN,
            "reason": "no necessary condition failed and the witness search "
                      "found no prefix-safe fulfilling plan",
            "witness": None}


__all__ = ["FEASIBLE", "INFEASIBLE", "UNKNOWN", "candidate_plans",
           "certify", "free_capacity", "necessary_failure", "path_width",
           "widest_paths"]
