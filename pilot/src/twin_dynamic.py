"""A digital twin with its own execution semantics, not a second checker.

The stub twin used elsewhere shares the reference transition function and
predicate code, so it can only ever agree; its role was to provide a second
cost curve, and it contributes nothing to detection. This module is what the
backend dimension is supposed to be: an executor whose semantics differ from
the static model in a way that lets it observe events the static model cannot
express.

The difference modelled here is that reconfiguration is not atomic. Moving a
flow to a new path is make-before-break in normal operational practice: the
new path is brought up while the old one is still carrying traffic, and for
the duration of convergence BOTH paths hold the flow's demand. A move that is
safe in the state before it and in the state after it can therefore
double-book a shared link while it is happening. The static per-operation
model checks only the states between operations and has no term for that
interval, so no amount of coverage or temporal scope inside that model can
see it.

What this does and does not claim. It is a model of convergence, not a packet
simulator: no queueing, loss, control-plane messaging or timer behaviour. Its
value is that its transition semantics are genuinely different, so agreement
with the static checker is informative and disagreement is explainable rather
than a bug. Violations are reported against the SAME external loss event used
everywhere else, so the two are comparable.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

logger = logging.getLogger(__name__)

Violation = Dict[str, Any]
TOL = 1e-9


@dataclass(frozen=True)
class TwinConfig:
    """Convergence behaviour of the modelled control plane."""

    # Sub-steps sampled inside one reconfiguration interval.
    substeps: int = 4
    # Fraction of the interval during which the old path still carries the
    # flow after the new one is installed. 0 disables overlap and recovers
    # atomic behaviour.
    overlap: float = 0.75
    # Whether a node being disabled drains immediately or after convergence.
    drain_after_converge: bool = True


class DynamicTwin:
    """Executes a schedule with non-atomic reconfiguration.

    Keeps its own state as plain dictionaries and its own load accounting; it
    does not import NetState, apply_op or the reference predicates.
    """

    def __init__(self, state: Dict[str, Any], cfg: TwinConfig) -> None:
        self.cfg = cfg
        self.nodes = {k: dict(v) for k, v in state["nodes"].items()}
        self.links = {k: dict(v) for k, v in state["links"].items()}
        self.flows = {k: dict(v) for k, v in state["flows"].items()}
        self.acls = {k: dict(v) for k, v in state["acls"].items()}
        self.slices = {k: dict(v) for k, v in state.get("slices", {}).items()}
        self._adj: Dict[Tuple[str, str], str] = {}
        for lid, link in self.links.items():
            self._adj[(link["a"], link["b"])] = lid
            self._adj[(link["b"], link["a"])] = lid

    # -- topology helpers -------------------------------------------------
    def _edges(self, path: Sequence[str]) -> Optional[List[str]]:
        out = []
        for u, v in zip(path, path[1:]):
            lid = self._adj.get((u, v))
            if lid is None:
                return None
            out.append(lid)
        return out

    def _loads(self, occupancy: Dict[str, List[Sequence[str]]]
               ) -> Dict[str, float]:
        """Link loads given which paths each flow currently occupies."""
        load = {lid: 0.0 for lid in self.links}
        for fid, paths in occupancy.items():
            bw = float(self.flows[fid]["bw"])
            for path in paths:
                edges = self._edges(path)
                if edges is None:
                    continue
                for lid in edges:
                    load[lid] += bw
        for sl in self.slices.values():
            for lid in sl["links"]:
                if lid in load:
                    load[lid] += float(sl["bw"])
        return load

    def _latency(self, path: Sequence[str]) -> Optional[float]:
        edges = self._edges(path)
        if edges is None:
            return None
        total = sum(self.links[l]["lat_ms"] for l in edges)
        for nid in path:
            node = self.nodes.get(nid)
            if node:
                total += node["base_ms"] / max(1, node["replicas"])
        return total

    # -- invariant evaluation at one instant -------------------------------
    def _violations(self, occupancy: Dict[str, List[Sequence[str]]],
                    disabled: Set[str], instant: str) -> List[Violation]:
        out: List[Violation] = []
        for lid, load in self._loads(occupancy).items():
            cap = float(self.links[lid]["cap"])
            if load > cap + TOL:
                out.append({"cls": "I1", "kind": "link_overload",
                            "link": lid, "load": round(load, 2), "cap": cap,
                            "instant": instant})
        for nid, node in self.nodes.items():
            if node["replicas"] > node["vnf_slots"]:
                out.append({"cls": "I1", "kind": "vnf_slots", "node": nid,
                            "instant": instant})
        for fid, paths in occupancy.items():
            flow = self.flows[fid]
            for path in paths:
                lat = self._latency(path)
                if lat is not None and lat > float(flow["sla_ms"]) + TOL:
                    out.append({"cls": "I2", "kind": "sla_latency",
                                "flow": fid, "lat": round(lat, 2),
                                "sla": flow["sla_ms"], "instant": instant})
                    break
            if flow.get("priority") and \
                    float(flow["bw"]) < float(flow["min_bw"]) - TOL:
                out.append({"cls": "I2", "kind": "priority_bw", "flow": fid,
                            "instant": instant})
        seen: Dict[Tuple[str, str], Set[str]] = {}
        for rule in self.acls.values():
            seen.setdefault((rule["src"], rule["dst"]), set()).add(
                rule["action"])
        for pair, acts in seen.items():
            if len(acts) > 1:
                out.append({"cls": "I3", "kind": "acl_conflict",
                            "pair": list(pair), "instant": instant})
        for fid, paths in occupancy.items():
            for path in paths:
                if disabled.intersection(path):
                    out.append({"cls": "I3", "kind": "flow_via_disabled",
                                "flow": fid, "instant": instant})
                    break
        return out

    # -- execution ---------------------------------------------------------
    def run(self, plan: Sequence[Dict[str, Any]]
            ) -> Tuple[List[Violation], List[Violation]]:
        """Execute the schedule; return (all violations, convergence-only).

        The second list holds violations observed only strictly inside a
        reconfiguration interval, never at a settled state. Those are exactly
        the events the static model has no term for.
        """
        occupancy: Dict[str, List[Sequence[str]]] = {
            fid: [list(f["path"])] for fid, f in self.flows.items()}
        disabled: Set[str] = {n for n, nd in self.nodes.items()
                              if not nd["enabled"]}
        all_v: List[Violation] = []
        transient_v: List[Violation] = []

        for step, op in enumerate(plan):
            kind = op.get("op")

            if kind == "reroute_flow":
                fid = str(op.get("flow"))
                new_path = [str(x) for x in op.get("path", [])]
                if fid not in self.flows or self._edges(new_path) is None:
                    continue
                old_path = list(occupancy[fid][0])
                n_overlap = max(1, int(round(self.cfg.overlap
                                             * self.cfg.substeps)))
                for s in range(self.cfg.substeps):
                    occupancy[fid] = ([old_path, new_path] if s < n_overlap
                                      else [new_path])
                    found = self._violations(occupancy, disabled,
                                             f"step{step}.sub{s}")
                    all_v.extend(found)
                    if s < n_overlap:
                        transient_v.extend(found)
                occupancy[fid] = [new_path]
                self.flows[fid]["path"] = new_path

            elif kind == "set_flow_bw":
                fid = str(op.get("flow"))
                if fid in self.flows:
                    self.flows[fid]["bw"] = float(op.get("bw_mbps", 0))

            elif kind == "disable_node":
                nid = str(op.get("node"))
                if nid in self.nodes:
                    if self.cfg.drain_after_converge:
                        for s in range(self.cfg.substeps):
                            found = self._violations(
                                occupancy, disabled | {nid},
                                f"step{step}.sub{s}")
                            all_v.extend(found)
                    disabled.add(nid)
                    self.nodes[nid]["enabled"] = False

            elif kind == "enable_node":
                nid = str(op.get("node"))
                if nid in self.nodes:
                    disabled.discard(nid)
                    self.nodes[nid]["enabled"] = True

            elif kind == "scale_vnf":
                nid = str(op.get("node"))
                if nid in self.nodes:
                    self.nodes[nid]["replicas"] = int(op.get("replicas", 1))

            elif kind == "add_acl":
                rid = str(op.get("rule_id", f"A{len(self.acls) + 1}"))
                self.acls[rid] = {"src": str(op.get("src")),
                                  "dst": str(op.get("dst")),
                                  "action": op.get("action")}

            elif kind == "remove_acl":
                self.acls.pop(str(op.get("rule_id")), None)

            elif kind == "reserve_slice":
                sid = str(op.get("slice", f"S{len(self.slices) + 1}"))
                self.slices[sid] = {"links": [str(x) for x
                                              in op.get("links", [])],
                                    "bw": float(op.get("bw_mbps", 0))}

            settled = self._violations(occupancy, disabled, f"step{step}")
            all_v.extend(settled)

        return all_v, transient_v


def twin_dynamic_verify(state: Dict[str, Any], plan: Sequence[Dict[str, Any]],
                        cfg: Optional[TwinConfig] = None
                        ) -> Tuple[str, Optional[Violation], float,
                                   List[Violation]]:
    """Run the dynamic twin. Returns (outcome, first, seconds, transient)."""
    t0 = time.perf_counter()
    twin = DynamicTwin(state, cfg or TwinConfig())
    all_v, transient = twin.run(plan)
    dt = time.perf_counter() - t0
    outcome = "REJECT" if all_v else "ACCEPT"
    return outcome, (all_v[0] if all_v else None), dt, transient


__all__ = ["DynamicTwin", "TwinConfig", "twin_dynamic_verify"]
