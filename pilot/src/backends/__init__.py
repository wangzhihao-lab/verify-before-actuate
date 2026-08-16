"""Plan-generation backends behind one interface.

Two registered backends serve different experimental roles:

``ollama``      a pinned open-weights model run locally. Primary corpus
                backend: unlimited calls, and -- more importantly -- a fixed
                (model, seed, temperature) triple that a reviewer can rerun
                bit-for-bit. Proprietary CLI aliases cannot offer this.
``claude_cli``  the hosted frontier model via the claude CLI. Used for a
                smaller cross-model cell showing the measured effects are not
                an artefact of one small model. Subject to a subscription
                quota, so never the backbone of a large sweep.

Seeding contract: ``generate(prompt, seed)`` must be deterministic in
``seed`` where the backend supports it, so repetitions vary reproducibly
instead of being either identical or irreproducible.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


class BackendUnavailable(RuntimeError):
    """Backend cannot serve requests (server down, model missing, quota)."""


class QuotaExhausted(RuntimeError):
    """Backend refused because a usage/session quota is spent."""


@dataclass(frozen=True)
class GenResult:
    """One generation, with the accounting the overhead analysis needs."""

    text: str
    wall_s: float
    prompt_tokens: Optional[int] = None
    gen_tokens: Optional[int] = None
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentSpec:
    """Immutable description of a generation backend."""

    backend: str = "ollama"
    model: str = "qwen2.5:7b-instruct-q8_0"
    temperature: float = 0.7
    num_ctx: int = 16384
    timeout: int = 300
    host: str = "http://127.0.0.1:11434"

    @property
    def label(self) -> str:
        return f"{self.backend}:{self.model}"


AGENT_FACTORY: Dict[str, Callable[[AgentSpec], "Backend"]] = {}


def register_backend(name: str) -> Callable[
        [Callable[[AgentSpec], "Backend"]],
        Callable[[AgentSpec], "Backend"]]:
    """Register a backend constructor under ``name``."""

    def decorator(fn: Callable[[AgentSpec], "Backend"]
                  ) -> Callable[[AgentSpec], "Backend"]:
        AGENT_FACTORY[name] = fn
        return fn

    return decorator


class Backend:
    """Interface every generation backend implements."""

    spec: AgentSpec

    def generate(self, prompt: str, seed: int) -> GenResult:
        raise NotImplementedError

    def provenance(self) -> Dict[str, Any]:
        raise NotImplementedError

    def healthcheck(self) -> None:
        """Raise :class:`BackendUnavailable` when not ready to serve."""
        raise NotImplementedError


def build_backend(spec: AgentSpec) -> Backend:
    """Construct the backend named by ``spec.backend``."""
    from . import (claude_backend, lmstudio_backend,  # noqa: F401
                   ollama_backend)

    try:
        ctor = AGENT_FACTORY[spec.backend]
    except KeyError:
        logger.error("unknown backend %r (have: %s)", spec.backend,
                     sorted(AGENT_FACTORY))
        raise
    return ctor(spec)


__all__ = [
    "AGENT_FACTORY",
    "AgentSpec",
    "Backend",
    "BackendUnavailable",
    "GenResult",
    "QuotaExhausted",
    "build_backend",
    "register_backend",
]
