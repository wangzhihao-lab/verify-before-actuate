"""Pilot experiment P (injection variant): p(d) on a controlled violation
taxonomy, no LLM needed.

Violation families injected on the base state:
  VI1  capacity overload (I1): raise a flow's bw just above a link cap;
       oversized slice reservation
  VI2  SLA breach (I2): downscale replicas on a slow node used by a flow;
       endpoint-preserving reroute onto a long path
  VI3  conflict/integrity (I3): contradictory ACL; nonexistent entity;
       disable a transit node leaving flows through it
  VI4  TRANSIENT-only: violate mid-plan, clean at the end (e.g. disable
       before rerouting, then reroute; temporary overload) — only
       every-step checking (L4) can catch these.

Depth levels L1..L4 as in run_p.py. Output: detection matrix.

Usage: uv run python run_p_inject.py out/q_YYYYmmdd_HHMMSS
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

from run_p import detect, load_state
from src.netmodel import NetState


def _overload_target(st: NetState) -> Tuple[str, str, float]:
    """(flow, link, bw) such that setting flow bw exceeds link cap."""
    best = None
    for fid, f in st.flows.items():
        for lid in st.path_links(f["path"]) or []:
            spare = st.links[lid]["cap"] - st.link_load(lid)
            need = f["bw"] + spare + 10
            if best is None or need < best[2]:
                best = (fid, lid, need)
    assert best
    return best


def _sla_scale_plan(st: NetState) -> List[dict]:
    """Downscale every node on the tightest flow's path to 1 replica —
    guaranteed-or-bust SLA pressure (post-validated by the caller)."""
    fid = min(st.flows, key=lambda f: st.flows[f]["sla_ms"]
              - st.flow_latency_ms(f))
    return [{"op": "scale_vnf", "node": n, "replicas": 1}
            for n in st.flows[fid]["path"]
            if st.nodes[n]["replicas"] > 1]


def _transit_node(st: NetState) -> str:
    eps = {f["path"][0] for f in st.flows.values()} | {
        f["path"][-1] for f in st.flows.values()}
    for n in st.nodes:
        if n not in eps and any(n in f["path"][1:-1]
                                for f in st.flows.values()):
            return n
    return next(iter(st.nodes))


def build_injections(st: NetState) -> List[Tuple[str, List[dict]]]:
    out: List[Tuple[str, List[dict]]] = []
    fid, lid, bw = _overload_target(st)
    out.append(("VI1_flow_overload",
                [{"op": "set_flow_bw", "flow": fid, "bw_mbps": bw}]))
    out.append(("VI1_slice_overload",
                [{"op": "reserve_slice", "slice": "SX", "links": [lid],
                  "bw_mbps": st.links[lid]["cap"]}]))
    sla_plan = _sla_scale_plan(st)
    if sla_plan:
        out.append(("VI2_scale_down", sla_plan))
    out.append(("VI3_acl_conflict", [
        {"op": "add_acl", "rule_id": "AX1", "src": "10.0.1.0/24",
         "dst": "10.0.2.0/24", "action": "allow"},
        {"op": "add_acl", "rule_id": "AX2", "src": "10.0.1.0/24",
         "dst": "10.0.2.0/24", "action": "deny"}]))
    out.append(("VI3_ghost_entity",
                [{"op": "set_flow_bw", "flow": "F99", "bw_mbps": 10}]))
    tn = _transit_node(st)
    out.append(("VI3_disable_no_reroute",
                [{"op": "disable_node", "node": tn}]))
    # VI4 transient: overload then revert; disable-then-reroute
    f0 = st.flows[fid]["bw"]
    out.append(("VI4_temp_overload", [
        {"op": "set_flow_bw", "flow": fid, "bw_mbps": bw},
        {"op": "set_flow_bw", "flow": fid, "bw_mbps": f0}]))
    affected = [f for f, ff in st.flows.items() if tn in ff["path"][1:-1]]
    reroutes = []
    for f in affected:
        ff = st.flows[f]
        alt = st.shortest_path(ff["path"][0], ff["path"][-1], avoid={tn})
        if alt is None:
            break
        reroutes.append({"op": "reroute_flow", "flow": f, "path": alt})
    else:
        out.append(("VI4_disable_before_reroute",
                    [{"op": "disable_node", "node": tn}] + reroutes))
    return out


def main() -> None:
    run_dir = Path(sys.argv[1])
    base = load_state(run_dir / "base_state.json")
    inj = build_injections(base)
    # pre-validate: every injection must actually violate (ground truth);
    # VI4 transient ones legitimately violate mid-plan only
    from src.invariants import check_plan
    kept = []
    for name, plan in inj:
        if check_plan(base, plan):
            kept.append((name, plan))
        else:
            print(f"  !! injection '{name}' does not violate — dropped")
    inj = kept
    print(f"{'violation':<28} L1 L2 L3 L4")
    matrix: Dict[str, List[bool]] = {}
    for name, plan in inj:
        row = [detect(base, plan, lv) for lv in (1, 2, 3, 4)]
        matrix[name] = row
        print(f"{name:<28} " + "  ".join("Y" if x else "." for x in row))
    n = len(inj)
    print("\np(d) over this taxonomy:")
    for i, lv in enumerate((1, 2, 3, 4)):
        det = sum(matrix[k][i] for k in matrix)
        print(f"  L{lv}: {det}/{n} = {det / n:.2f}")
    (run_dir / "p_inject.json").write_text(json.dumps(
        {k: v for k, v in matrix.items()}, indent=1))
    print(f"-> {run_dir}/p_inject.json")


if __name__ == "__main__":
    main()
