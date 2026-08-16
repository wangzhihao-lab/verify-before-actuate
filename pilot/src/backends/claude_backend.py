"""Hosted frontier-model backend via the claude CLI.

Used only for a small cross-model comparison cell. The CLI exposes no seed,
so ``seed`` cannot make repetitions reproducible here; that asymmetry is
recorded in the provenance block rather than papered over.
"""
from __future__ import annotations

import logging
import subprocess
from typing import Any, Dict

from ..agent import FAST_ARGS, SessionLimit, call_claude
from ..agent import provenance as cli_provenance
from . import (AgentSpec, Backend, BackendUnavailable, GenResult,
               QuotaExhausted, register_backend)

logger = logging.getLogger(__name__)


class ClaudeCliBackend(Backend):
    """Generation through the local ``claude`` CLI in headless print mode."""

    def __init__(self, spec: AgentSpec) -> None:
        self.spec = spec

    def healthcheck(self) -> None:
        try:
            out = subprocess.run(["claude", "--version"], capture_output=True,
                                 text=True, timeout=30)
        except (OSError, subprocess.SubprocessError) as exc:
            raise BackendUnavailable(f"claude CLI unavailable: {exc}") from exc
        if out.returncode != 0:
            raise BackendUnavailable(f"claude --version failed: {out.stderr}")

    def generate(self, prompt: str, seed: int) -> GenResult:
        try:
            text, wall = call_claude(prompt, model=self.spec.model,
                                     timeout=self.spec.timeout,
                                     extra_args=FAST_ARGS)
        except SessionLimit as exc:
            raise QuotaExhausted(str(exc)) from exc
        except (OSError, subprocess.SubprocessError) as exc:
            raise BackendUnavailable(str(exc)) from exc
        # The CLI reports no token counts; leaving them None keeps the
        # overhead analysis honest instead of inventing estimates.
        return GenResult(text=text, wall_s=wall, prompt_tokens=None,
                         gen_tokens=None,
                         meta={"seed_supported": False,
                               "requested_seed": seed})

    def provenance(self) -> Dict[str, Any]:
        info: Dict[str, Any] = {"backend": "claude_cli",
                                "cli_args": list(FAST_ARGS),
                                "seed_supported": False}
        info.update(cli_provenance(self.spec.model))
        return info


@register_backend("claude_cli")
def _make(spec: AgentSpec) -> Backend:
    return ClaudeCliBackend(spec)


__all__ = ["ClaudeCliBackend"]
