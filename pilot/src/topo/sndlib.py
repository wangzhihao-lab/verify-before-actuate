"""SNDlib native-format loader: real ISP topologies into ``NetState``.

Source: SNDlib, http://sndlib.zib.de -- Orlowski, Pioro, Tomaszewski and
Wessaely, "SNDlib 1.0--Survivable Network Design Library", Networks 55(3),
2010.  A local copy lives under ``pilot/data/sndlib/`` together with the
download URL and its SHA256.

Provenance of every field, so the paper can state it exactly:

REAL (taken verbatim from the dataset)
  - node set and geographic coordinates (longitude, latitude);
  - link set (undirected adjacency) and installed link capacity;
  - the origin-destination traffic matrix (demand values).

DERIVED (physically grounded, computed here)
  - link propagation latency = great-circle distance / (2c/3), the usual
    signal speed in fibre (~200 km/ms).

SYNTHESIZED (no counterpart in SNDlib; seeded, and disclosed as such)
  - per-node VNF slot count, replica count, base processing delay;
  - per-flow SLA bound, priority flag, minimum bandwidth;
  - ACL rules over synthetic subnets.

The raw SNDlib matrices are capacity-*design* inputs: routed on shortest
paths they overload the installed capacities by design.  We therefore scale
the whole matrix by one scalar so that peak link utilisation meets
``target_util``.  This preserves the relative shape of the real traffic
matrix while yielding a violation-free base state with headroom, which is
the precondition every intent generator in this project assumes.
"""
from __future__ import annotations

import logging
import math
import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..netmodel import NetState

logger = logging.getLogger(__name__)

# Signal speed in optical fibre, km/ms (~2/3 of c).
FIBRE_KM_PER_MS = 200.0
EARTH_RADIUS_KM = 6371.0
# Latency assigned to a link when the dataset carries no usable coordinates.
FALLBACK_LINK_MS = 2.0

DATA_DIR = (Path(__file__).resolve().parents[2]
            / "data" / "sndlib" / "extracted" / "sndlib-networks-native")

_NODE_RE = re.compile(
    r"^\s*(\S+)\s*\(\s*([-\d.eE+]+)\s+([-\d.eE+]+)\s*\)\s*$")
_NODE_BARE_RE = re.compile(r"^\s*(\S+)\s*(?:\(\s*\))?\s*$")
_LINK_RE = re.compile(
    r"^\s*(\S+)\s*\(\s*(\S+)\s+(\S+)\s*\)"
    r"\s+([-\d.eE+]+)\s+([-\d.eE+]+)\s+([-\d.eE+]+)\s+([-\d.eE+]+)"
    r"\s*\((?P<mods>[^)]*)\)\s*$")
_DEMAND_RE = re.compile(
    r"^\s*(\S+)\s*\(\s*(\S+)\s+(\S+)\s*\)\s+(\S+)\s+([-\d.eE+]+)\s+(\S+)\s*$")


@dataclass(frozen=True)
class SndlibConfig:
    """Immutable build configuration for one topology instance."""

    name: str
    seed: int = 42
    max_flows: int = 40
    target_util: float = 0.65
    sla_slack_lo: float = 1.3
    sla_slack_hi: float = 2.0
    priority_frac: float = 0.3
    n_acls: int = 3


@dataclass(frozen=True)
class ParsedNetwork:
    """Raw dataset content, before any modelling choice is applied."""

    name: str
    coords: Dict[str, Optional[Tuple[float, float]]]
    links: List[Tuple[str, str, str, float]]  # (id, a, b, capacity)
    demands: List[Tuple[str, str, str, float]]  # (id, src, dst, value)

    @property
    def has_coords(self) -> bool:
        return all(v is not None for v in self.coords.values())


def _section_body(text: str, name: str) -> List[str]:
    """Body lines of a top-level ``NAME ( ... )`` block, comments stripped."""
    out: List[str] = []
    inside = False
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not inside:
            if re.match(rf"^{name}\s*\(\s*$", line.strip()):
                inside = True
            continue
        if line.strip() == ")":
            break
        if line.strip():
            out.append(line)
    return out


def parse_native(text: str, name: str) -> ParsedNetwork:
    """Parse one SNDlib native-format network file."""
    coords: Dict[str, Optional[Tuple[float, float]]] = {}
    for line in _section_body(text, "NODES"):
        m = _NODE_RE.match(line)
        if m:
            coords[m.group(1)] = (float(m.group(2)), float(m.group(3)))
            continue
        m = _NODE_BARE_RE.match(line)
        if m:
            coords[m.group(1)] = None
        else:
            raise ValueError(f"{name}: unparsable NODES line: {line!r}")

    links: List[Tuple[str, str, str, float]] = []
    for line in _section_body(text, "LINKS"):
        m = _LINK_RE.match(line)
        if not m:
            raise ValueError(f"{name}: unparsable LINKS line: {line!r}")
        pre_cap = float(m.group(4))
        mods = [float(x) for x in m.group("mods").split()]
        # Module list is (capacity, cost) pairs; capacities are the evens.
        mod_caps = mods[0::2] if mods else []
        cap = pre_cap if pre_cap > 0 else (max(mod_caps) if mod_caps else 0.0)
        links.append((m.group(1), m.group(2), m.group(3), cap))

    demands: List[Tuple[str, str, str, float]] = []
    for line in _section_body(text, "DEMANDS"):
        m = _DEMAND_RE.match(line)
        if not m:
            raise ValueError(f"{name}: unparsable DEMANDS line: {line!r}")
        demands.append((m.group(1), m.group(2), m.group(3),
                        float(m.group(5))))

    return ParsedNetwork(name=name, coords=coords, links=links,
                         demands=demands)


def load_parsed(name: str, data_dir: Optional[Path] = None) -> ParsedNetwork:
    """Read and parse a named network from the local SNDlib copy."""
    root = data_dir or DATA_DIR
    path = root / f"{name}.txt"
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        logger.error("SNDlib network not found: %s", path)
        raise
    return parse_native(text, name)


def available(data_dir: Optional[Path] = None) -> List[str]:
    """Names of every locally available SNDlib network, sorted."""
    root = data_dir or DATA_DIR
    return sorted(p.stem for p in root.glob("*.txt"))


def _haversine_km(p: Tuple[float, float], q: Tuple[float, float]) -> float:
    lon1, lat1 = math.radians(p[0]), math.radians(p[1])
    lon2, lat2 = math.radians(q[0]), math.radians(q[1])
    dlon, dlat = lon2 - lon1, lat2 - lat1
    h = (math.sin(dlat / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2)
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(min(1.0, h)))


def _link_latency_ms(pn: ParsedNetwork, a: str, b: str) -> float:
    pa, pb = pn.coords.get(a), pn.coords.get(b)
    if pa is None or pb is None:
        return FALLBACK_LINK_MS
    return max(0.05, round(_haversine_km(pa, pb) / FIBRE_KM_PER_MS, 3))


def build_state(pn: ParsedNetwork, cfg: SndlibConfig) -> NetState:
    """Turn a parsed network into a violation-free ``NetState``."""
    rng = random.Random(cfg.seed)
    st = NetState()

    for nid in pn.coords:
        st.nodes[nid] = {"vnf_slots": rng.randint(4, 8),
                         "replicas": rng.randint(1, 3),
                         "base_ms": round(rng.uniform(2.0, 8.0), 2),
                         "enabled": True}

    dropped = 0
    for lid, a, b, cap in pn.links:
        if a not in st.nodes or b not in st.nodes:
            logger.warning("%s: link %s references unknown node", pn.name, lid)
            continue
        if st.link_between(a, b) is not None:
            dropped += 1  # parallel edge: our model keeps one link per pair
            continue
        st.links[lid] = {"a": a, "b": b,
                         "cap": cap if cap > 0 else 1000.0,
                         "lat_ms": _link_latency_ms(pn, a, b)}
    if dropped:
        logger.info("%s: merged %d parallel link entries into %d node pairs",
                    pn.name, dropped, len(st.links))

    # Route a seeded sample of the real traffic matrix on shortest paths.
    routable = [d for d in pn.demands
                if d[1] in st.nodes and d[2] in st.nodes and d[1] != d[2]]
    rng.shuffle(routable)
    chosen: List[Tuple[str, List[str], float]] = []
    for _, src, dst, value in routable:
        if len(chosen) >= cfg.max_flows:
            break
        path = st.shortest_path(src, dst)
        if path is None or len(path) < 2:
            continue
        chosen.append((f"F{len(chosen) + 1}", path, value))

    if not chosen:
        raise ValueError(f"{pn.name}: no routable demand could be placed")

    for fid, path, value in chosen:
        st.flows[fid] = {"path": path, "bw": value, "sla_ms": 0.0,
                         "priority": False, "min_bw": value}

    # One global scalar putting peak utilisation exactly at target_util. The
    # real matrix's *shape* is preserved; its absolute level is set by us,
    # both because SNDlib matrices are capacity-design inputs (infeasible on
    # shortest paths) and because a sampled sub-matrix would otherwise leave
    # each topology at an arbitrary, incomparable load. Fixing the operating
    # point makes topologies comparable and makes load a sweepable factor.
    peak = max((st.link_load(lid) / st.links[lid]["cap"] for lid in st.links),
               default=0.0)
    scale = (cfg.target_util / peak) if peak > 0 else 1.0
    for fid in st.flows:
        # Floor, never round up: rounding up can push peak past the target.
        bw = max(0.01, math.floor(st.flows[fid]["bw"] * scale * 100) / 100)
        st.flows[fid]["bw"] = bw
        st.flows[fid]["min_bw"] = bw

    for fid in st.flows:
        st.flows[fid]["priority"] = rng.random() < cfg.priority_frac
        st.flows[fid]["sla_ms"] = round(
            st.flow_latency_ms(fid)
            * rng.uniform(cfg.sla_slack_lo, cfg.sla_slack_hi), 2)

    subnets = [f"10.0.{k}.0/24" for k in range(1, 9)]
    for i in range(cfg.n_acls):
        a, b = rng.sample(subnets, 2)
        st.acls[f"A{i + 1}"] = {"src": a, "dst": b, "action": "allow"}

    return st


def load_sndlib(cfg: SndlibConfig,
                data_dir: Optional[Path] = None) -> NetState:
    """Load a real SNDlib topology as a ready-to-use ``NetState``."""
    return build_state(load_parsed(cfg.name, data_dir), cfg)
