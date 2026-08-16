"""Second local model via the LM Studio OpenAI-compatible endpoint.

Exists so that model-dependent findings can be separated from
model-independent ones. The violation rate, the failure of self-reflection
and the absence of ordering errors are all properties of a particular
generator until a second one is measured on the same intents.

Like the ollama backend this is served locally and accepts a seed, so the
second corpus is reproducible on the same terms as the first.
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


class LMStudioBackend(Backend):
    """Chat-completions client for a locally served LM Studio model."""

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
                f"LM Studio at {self.spec.host}: {exc}") from exc

    def healthcheck(self) -> None:
        try:
            with urllib.request.urlopen(f"{self.spec.host}/v1/models",
                                        timeout=20) as resp:
                data = json.load(resp)
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            raise BackendUnavailable(
                f"LM Studio not reachable at {self.spec.host}: {exc}") from exc
        ids = {m.get("id") for m in data.get("data", [])}
        if self.spec.model not in ids:
            raise BackendUnavailable(
                f"model {self.spec.model!r} not loaded; have {sorted(ids)}")

    def generate(self, prompt: str, seed: int) -> GenResult:
        payload = {
            "model": self.spec.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.spec.temperature,
            "seed": seed,
            "stream": False,
        }
        t0 = time.perf_counter()
        data = self._post("/v1/chat/completions", payload, self.spec.timeout)
        wall = time.perf_counter() - t0
        choices = data.get("choices") or [{}]
        text = (choices[0].get("message") or {}).get("content", "")
        usage = data.get("usage") or {}
        return GenResult(
            text=text, wall_s=wall,
            prompt_tokens=usage.get("prompt_tokens"),
            gen_tokens=usage.get("completion_tokens"),
            meta={"seed": seed, "finish_reason": choices[0].get(
                "finish_reason"), "model_echo": data.get("model")})

    def provenance(self) -> Dict[str, Any]:
        return {"backend": "lmstudio", "model": self.spec.model,
                "temperature": self.spec.temperature,
                "host": self.spec.host,
                "api": "openai chat-completions"}


@register_backend("lmstudio")
def _make(spec: AgentSpec) -> Backend:
    return LMStudioBackend(spec)


__all__ = ["LMStudioBackend"]
