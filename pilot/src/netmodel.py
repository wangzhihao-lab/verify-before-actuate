"""Toy-but-honest network state model for the calibration pilot.

State: nodes (VNF slots/replicas/processing delay), links (capacity/latency),
flows (path/bandwidth/SLA), ACL rules, slice reservations.
Plan = JSON list of typed ops; semantics in apply_op().
"""
from __future__ import annotations

import copy
import json
import random
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

Op = Dict[str, Any]


@dataclass
class NetState:
    nodes: Dict[str, dict] = field(default_factory=dict)
    links: Dict[str, dict] = field(default_factory=dict)
    flows: Dict[str, dict] = field(default_factory=dict)
    acls: Dict[str, dict] = field(default_factory=dict)
    slices: Dict[str, dict] = field(default_factory=dict)

    def clone(self) -> "NetState":
        return copy.deepcopy(self)

    def to_json(self) -> str:
        return json.dumps(
            {"nodes": self.nodes, "links": self.links, "flows": self.flows,
             "acls": self.acls, "slices": self.slices},
            indent=1, sort_keys=True)

    # -- topology helpers -------------------------------------------------
    def link_between(self, a: str, b: str) -> Optional[str]:
        for lid, l in self.links.items():
            if {l["a"], l["b"]} == {a, b}:
                return lid
        return None

    def path_links(self, path: List[str]) -> Optional[List[str]]:
        """Link ids along a node path; None if some hop is not a link."""
        out = []
        for a, b in zip(path, path[1:]):
            lid = self.link_between(a, b)
            if lid is None:
                return None
            out.append(lid)
        return out

    def flow_latency_ms(self, fid: str) -> float:
        f = self.flows[fid]
        lids = self.path_links(f["path"]) or []
        lat = sum(self.links[l]["lat_ms"] for l in lids)
        for nid in f["path"]:
            n = self.nodes[nid]
            lat += n["base_ms"] / max(1, n["replicas"])
        return lat

    def link_load(self, lid: str) -> float:
        load = sum(f["bw"] for f in self.flows.values()
                   if lid in (self.path_links(f["path"]) or []))
        load += sum(s["bw"] for s in self.slices.values()
                    if lid in s["links"])
        return load

    def shortest_path(self, src: str, dst: str,
                      avoid: Optional[set] = None) -> Optional[List[str]]:
        avoid = avoid or set()
        adj: Dict[str, List[str]] = {n: [] for n in self.nodes}
        for l in self.links.values():
            adj[l["a"]].append(l["b"])
            adj[l["b"]].append(l["a"])
        prev: Dict[str, Optional[str]] = {src: None}
        dq = deque([src])
        while dq:
            u = dq.popleft()
            if u == dst:
                path = [u]
                while prev[u] is not None:
                    u = prev[u]
                    path.append(u)
                return path[::-1]
            for v in adj[u]:
                if v not in prev and v not in avoid:
                    prev[v] = u
                    dq.append(v)
        return None


def apply_op(st: NetState, op: Op) -> List[str]:
    """Mutate state; return structural/entity error strings (I3 material)."""
    errs: List[str] = []
    kind = op.get("op")

    def need(entity: dict, key: str, label: str) -> bool:
        if key not in entity:
            errs.append(f"unknown {label} '{key}'")
            return False
        return True

    if kind == "set_flow_bw":
        fid = str(op.get("flow"))
        if need(st.flows, fid, "flow"):
            bw = float(op.get("bw_mbps", -1))
            if bw <= 0:
                errs.append(f"invalid bw {bw}")
            else:
                st.flows[fid]["bw"] = bw
    elif kind == "reroute_flow":
        fid = str(op.get("flow"))
        path = [str(x) for x in op.get("path", [])]
        if need(st.flows, fid, "flow"):
            old = st.flows[fid]["path"]
            if not path or any(n not in st.nodes for n in path):
                errs.append(f"path references unknown node: {path}")
            elif path[0] != old[0] or path[-1] != old[-1]:
                errs.append(
                    f"reroute must keep endpoints {old[0]}->{old[-1]}, "
                    f"got {path[0]}->{path[-1]}")
            elif st.path_links(path) is None:
                errs.append(f"path not connected by links: {path}")
            elif any(not st.nodes[n]["enabled"] for n in path):
                errs.append(f"path uses disabled node: {path}")
            else:
                st.flows[fid]["path"] = path
    elif kind == "add_acl":
        rid = str(op.get("rule_id", f"A{len(st.acls) + 1}"))
        act = op.get("action")
        if act not in ("allow", "deny"):
            errs.append(f"invalid acl action {act}")
        else:
            st.acls[rid] = {"src": str(op.get("src")),
                            "dst": str(op.get("dst")), "action": act}
    elif kind == "remove_acl":
        rid = str(op.get("rule_id"))
        if need(st.acls, rid, "acl rule"):
            del st.acls[rid]
    elif kind == "scale_vnf":
        nid = str(op.get("node"))
        if need(st.nodes, nid, "node"):
            rep = int(op.get("replicas", -1))
            if rep < 1:
                errs.append(f"invalid replicas {rep}")
            else:
                st.nodes[nid]["replicas"] = rep
    elif kind == "reserve_slice":
        sid = str(op.get("slice", f"S{len(st.slices) + 1}"))
        lids = [str(x) for x in op.get("links", [])]
        bw = float(op.get("bw_mbps", -1))
        if any(l not in st.links for l in lids):
            errs.append(f"slice references unknown link: {lids}")
        elif bw <= 0 or not lids:
            errs.append("invalid slice reservation")
        else:
            st.slices[sid] = {"links": lids, "bw": bw}
    elif kind == "disable_node":
        nid = str(op.get("node"))
        if need(st.nodes, nid, "node"):
            st.nodes[nid]["enabled"] = False
    elif kind == "enable_node":
        nid = str(op.get("node"))
        if need(st.nodes, nid, "node"):
            st.nodes[nid]["enabled"] = True
    else:
        errs.append(f"unknown op '{kind}'")
    return errs


def gen_topology(rng: random.Random, n_nodes: int = 12, n_chords: int = 6,
                 n_flows: int = 15) -> NetState:
    """Ring + random chords; flows on BFS shortest paths."""
    st = NetState()
    names = [f"N{i + 1}" for i in range(n_nodes)]
    for n in names:
        st.nodes[n] = {"vnf_slots": rng.randint(4, 8),
                       "replicas": rng.randint(1, 3),
                       "base_ms": round(rng.uniform(2.0, 8.0), 2),
                       "enabled": True}
    lid = 0

    def add_link(a: str, b: str) -> None:
        nonlocal lid
        if st.link_between(a, b):
            return
        lid += 1
        st.links[f"L{lid}"] = {"a": a, "b": b,
                               "cap": rng.choice([100, 150, 200, 300]),
                               "lat_ms": round(rng.uniform(1.0, 5.0), 2)}

    for i in range(n_nodes):
        add_link(names[i], names[(i + 1) % n_nodes])
    for _ in range(n_chords):
        a, b = rng.sample(names, 2)
        add_link(a, b)

    for i in range(n_flows):
        src, dst = rng.sample(names, 2)
        path = st.shortest_path(src, dst)
        assert path is not None
        fid = f"F{i + 1}"
        bw = rng.choice([5, 10, 15, 20, 30, 40])
        st.flows[fid] = {"path": path, "bw": bw, "sla_ms": 0.0,
                         "priority": rng.random() < 0.3, "min_bw": bw}
        st.flows[fid]["sla_ms"] = round(
            st.flow_latency_ms(fid) * rng.uniform(1.3, 2.0), 2)
    for i in range(3):
        a, b = rng.sample([f"10.0.{k}.0/24" for k in range(1, 9)], 2)
        st.acls[f"A{i + 1}"] = {"src": a, "dst": b, "action": "allow"}

    # normalize: base state must be violation-free with headroom
    # (target utilization <= 70% so intents have room to operate)
    for lid, l in st.links.items():
        load = st.link_load(lid)
        if load > 0.7 * l["cap"]:
            l["cap"] = int(-(-load // 0.7 // 10) * 10 + 10)  # ceil to 10s
    return st
