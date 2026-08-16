"""Ground-truth invariant checkers (full depth) for the pilot.

Three classes (paper §II):
  I1 resource conservation — link capacity (flows + slice reservations),
     node VNF slots.
  I2 SLA — per-flow latency bound; priority flows keep min bandwidth.
  I3 config conflict / integrity — entity hallucination, invalid paths,
     contradictory ACL pairs, flows traversing disabled nodes.

check_plan() simulates step by step; a violation at ANY intermediate state
counts (transient violations are real in live networks).
"""
from __future__ import annotations

from typing import Any, Dict, List

from .netmodel import NetState, Op, apply_op

Violation = Dict[str, Any]


def check_state(st: NetState) -> List[Violation]:
    out: List[Violation] = []
    for lid in st.links:
        load = st.link_load(lid)
        if load > st.links[lid]["cap"] + 1e-9:
            out.append({"cls": "I1", "kind": "link_overload", "link": lid,
                        "load": round(load, 1), "cap": st.links[lid]["cap"]})
    for nid, n in st.nodes.items():
        if n["replicas"] > n["vnf_slots"]:
            out.append({"cls": "I1", "kind": "vnf_slots", "node": nid,
                        "replicas": n["replicas"], "slots": n["vnf_slots"]})
    for fid, f in st.flows.items():
        lat = st.flow_latency_ms(fid)
        if lat > f["sla_ms"] + 1e-9:
            out.append({"cls": "I2", "kind": "sla_latency", "flow": fid,
                        "lat": round(lat, 2), "sla": f["sla_ms"]})
        if f["priority"] and f["bw"] < f["min_bw"] - 1e-9:
            out.append({"cls": "I2", "kind": "priority_bw", "flow": fid,
                        "bw": f["bw"], "min_bw": f["min_bw"]})
    seen: Dict[tuple, str] = {}
    for rid, r in st.acls.items():
        key = (r["src"], r["dst"])
        if key in seen and seen[key] != r["action"]:
            out.append({"cls": "I3", "kind": "acl_conflict",
                        "pair": list(key)})
        seen[key] = r["action"]
    for fid, f in st.flows.items():
        if any(not st.nodes[n]["enabled"] for n in f["path"]
               if n in st.nodes):
            out.append({"cls": "I3", "kind": "flow_via_disabled",
                        "flow": fid})
    return out


def check_plan(base: NetState, plan: List[Op]) -> List[Violation]:
    """Simulate; return violations tagged with the step index (0-based)."""
    st = base.clone()
    out: List[Violation] = []
    for i, op in enumerate(plan):
        errs = apply_op(st, op)
        for e in errs:
            out.append({"cls": "I3", "kind": "structural", "step": i,
                        "detail": e})
        for v in check_state(st):
            out.append({**v, "step": i})
    return out


def summarize(viols: List[Violation]) -> Dict[str, int]:
    s = {"I1": 0, "I2": 0, "I3": 0}
    for v in viols:
        s[v["cls"]] += 1
    return s
