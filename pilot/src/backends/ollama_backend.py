"""Local open-weights backend via the ollama HTTP API.

Chosen as the primary corpus backend for reproducibility: the model weights
are pinned by digest, and ollama honours an explicit ``seed``, so a reviewer
rerunning the archived config reproduces the exact plan corpus. Token counts
come back with every response, which is what the paper's overhead analysis
needs and what a CLI wrapper cannot supply.
"""
from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from typing import Any, Dict

from . import (AgentSpec, Backend, BackendUnavailable, GenResult,
               register_backend)

logger = logging.getLogger(__name__)


class OllamaBackend(Backend):
    """Generation against a locally served ollama model."""

    def __init__(self, spec: AgentSpec) -> None:
        self.spec = spec

    def _post(self, path: str, payload: Dict[str, Any],
              timeout: int) -> Dict[str, Any]:
        req = urllib.request.Request(
            f"{self.spec.host}{path}",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.load(resp)
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            raise BackendUnavailable(
                f"ollama at {self.spec.host}: {exc}") from exc

    def healthcheck(self) -> None:
        try:
            with urllib.request.urlopen(f"{self.spec.host}/api/tags",
                                        timeout=15) as resp:
                tags = json.load(resp)
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            raise BackendUnavailable(
                f"ollama not reachable at {self.spec.host}: {exc}") from exc
        names = {m.get("name") for m in tags.get("models", [])}
        if self.spec.model not in names:
            raise BackendUnavailable(
                f"model {self.spec.model!r} not pulled; have {sorted(names)}")

    def generate(self, prompt: str, seed: int) -> GenResult:
        payload = {
            "model": self.spec.model,
            "prompt": prompt,
            "stream": False,
            "options": {"seed": seed,
                        "temperature": self.spec.temperature,
                        "num_ctx": self.spec.num_ctx},
        }
        t0 = time.perf_counter()
        data = self._post("/api/generate", payload, self.spec.timeout)
        wall = time.perf_counter() - t0
        return GenResult(
            text=data.get("response", ""),
            wall_s=wall,
            prompt_tokens=data.get("prompt_eval_count"),
            gen_tokens=data.get("eval_count"),
            meta={
                "seed": seed,
                "total_duration_ns": data.get("total_duration"),
                "load_duration_ns": data.get("load_duration"),
                "prompt_eval_duration_ns": data.get("prompt_eval_duration"),
                "eval_duration_ns": data.get("eval_duration"),
                "done_reason": data.get("done_reason"),
            })

    def provenance(self) -> Dict[str, Any]:
        info: Dict[str, Any] = {"backend": "ollama", "model": self.spec.model,
                                "temperature": self.spec.temperature,
                                "num_ctx": self.spec.num_ctx,
                                "host": self.spec.host}
        # Pin the exact weights by digest so the run is reproducible even if
        # the tag is later repointed at different weights.
        try:
            data = self._post("/api/show", {"model": self.spec.model}, 30)
        except BackendUnavailable as exc:
            logger.warning("could not read model digest: %s", exc)
            return info
        details = data.get("details", {})
        info.update({
            "parameter_size": details.get("parameter_size"),
            "quantization_level": details.get("quantization_level"),
            "family": details.get("family"),
            "digest": data.get("digest"),
            "modified_at": data.get("modified_at"),
        })
        # /api/show carries no top-level digest, so the field was silently
        # recording null and the run looked pinned by tag alone. The digest
        # lives in the tag listing; without it a repointed tag is
        # undetectable, which is the whole reason for recording it.
        if not info.get("digest"):
            try:
                with urllib.request.urlopen(f"{self.spec.host}/api/tags",
                                            timeout=30) as resp:
                    tags = json.loads(resp.read().decode())
            except (urllib.error.URLError, OSError, ValueError) as exc:
                logger.warning("could not read model digest from tags: %s", exc)
                return info
            for entry in tags.get("models", []):
                if entry.get("name") == self.spec.model:
                    info["digest"] = entry.get("digest")
                    info.setdefault("size_bytes", entry.get("size"))
                    break
        return info


@register_backend("ollama")
def _make(spec: AgentSpec) -> Backend:
    return OllamaBackend(spec)


__all__ = ["OllamaBackend"]
