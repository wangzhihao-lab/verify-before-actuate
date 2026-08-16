"""Topology backends for the verify-before-actuate experiments.

Two registered backends:
  ``synthetic``  the ring+chords generator used by the Phase-1.5 pilot,
                 kept so earlier results stay reproducible;
  ``sndlib``     real ISP topologies with real capacities and real traffic
                 matrices (see :mod:`.sndlib` for exact field provenance).

Both are reached through :func:`build_topology`, which takes one immutable
:class:`TopoSpec` so an experiment cell is fully described by a config value.
"""
from __future__ import annotations

import logging
import random
from dataclasses import dataclass
from typing import Callable, Dict, List

from ..netmodel import NetState, gen_topology
from .sndlib import SndlibConfig, available, load_sndlib

logger = logging.getLogger(__name__)

TOPOLOGY_FACTORY: Dict[str, Callable[["TopoSpec"], NetState]] = {}


@dataclass(frozen=True)
class TopoSpec:
    """Complete, immutable description of one topology instance."""

    backend: str = "sndlib"
    name: str = "abilene"
    seed: int = 42
    max_flows: int = 40
    target_util: float = 0.65
    # Synthetic backend only.
    n_nodes: int = 24
    n_chords: int = 14

    @property
    def label(self) -> str:
        return f"{self.backend}:{self.name}"


def register_topology(name: str) -> Callable[
        [Callable[[TopoSpec], NetState]], Callable[[TopoSpec], NetState]]:
    """Register a topology backend under ``name``."""

    def decorator(fn: Callable[[TopoSpec], NetState]
                  ) -> Callable[[TopoSpec], NetState]:
        TOPOLOGY_FACTORY[name] = fn
        return fn

    return decorator


@register_topology("synthetic")
def _build_synthetic(spec: TopoSpec) -> NetState:
    return gen_topology(random.Random(spec.seed), spec.n_nodes,
                        spec.n_chords, spec.max_flows)


@register_topology("sndlib")
def _build_sndlib(spec: TopoSpec) -> NetState:
    return load_sndlib(SndlibConfig(name=spec.name, seed=spec.seed,
                                    max_flows=spec.max_flows,
                                    target_util=spec.target_util))


def build_topology(spec: TopoSpec) -> NetState:
    """Build the ``NetState`` described by ``spec``.

    Raises:
        KeyError: when ``spec.backend`` names no registered backend.
    """
    try:
        builder = TOPOLOGY_FACTORY[spec.backend]
    except KeyError:
        logger.error("unknown topology backend %r (have: %s)",
                     spec.backend, sorted(TOPOLOGY_FACTORY))
        raise
    return builder(spec)


def available_sndlib() -> List[str]:
    """Names of every locally available SNDlib network."""
    return available()


__all__ = [
    "TOPOLOGY_FACTORY",
    "TopoSpec",
    "available_sndlib",
    "build_topology",
    "register_topology",
]
