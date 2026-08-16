"""LLM agent wrapper: claude CLI in headless print mode.

The agent sees the full network state + op vocabulary and must return a
JSON array of ops. We measure wall-clock generation time (G in the theory).
"""
from __future__ import annotations

import json
import re
import subprocess
import time
from typing import Any, List, Optional, Sequence, Tuple

from .netmodel import NetState

# Guarded doc: op mechanics + explicit invariant constraints ("must stay <=")
OP_DOC = """
Available operations (JSON objects, executed in order):
  {"op":"set_flow_bw","flow":"F3","bw_mbps":80}
  {"op":"reroute_flow","flow":"F3","path":["N1","N4","N7"]}   # consecutive nodes must share a link; no disabled nodes; MUST keep the flow's original source and destination endpoints
  {"op":"add_acl","rule_id":"A9","src":"10.0.1.0/24","dst":"10.0.2.0/24","action":"deny"}  # action: allow|deny
  {"op":"remove_acl","rule_id":"A2"}
  {"op":"scale_vnf","node":"N4","replicas":3}
  {"op":"reserve_slice","slice":"S1","links":["L2","L5"],"bw_mbps":40}
  {"op":"disable_node","node":"N5"}
  {"op":"enable_node","node":"N5"}
Semantics:
  - Link load = sum of bw of flows whose path uses the link + slice reservations on it; must stay <= cap.
  - Flow latency = sum of link lat_ms on its path + sum over path nodes of base_ms/replicas; must stay <= the flow's sla_ms.
  - Priority flows must keep bw >= min_bw. Node replicas must stay <= vnf_slots.
  - Invariants are checked after EVERY step, so operation ORDER matters.
"""

# Bare doc: op mechanics only (how quantities are computed), NO "must stay
# <=" constraints and no "invariants checked every step" hint. The agent
# must infer on its own that overloading links / breaking SLAs is bad.
OP_DOC_BARE = """
Available operations (JSON objects, executed in order):
  {"op":"set_flow_bw","flow":"F3","bw_mbps":80}
  {"op":"reroute_flow","flow":"F3","path":["N1","N4","N7"]}   # consecutive nodes must share a link; keep the flow's source and destination endpoints
  {"op":"add_acl","rule_id":"A9","src":"10.0.1.0/24","dst":"10.0.2.0/24","action":"deny"}
  {"op":"remove_acl","rule_id":"A2"}
  {"op":"scale_vnf","node":"N4","replicas":3}
  {"op":"reserve_slice","slice":"S1","links":["L2","L5"],"bw_mbps":40}
  {"op":"disable_node","node":"N5"}
  {"op":"enable_node","node":"N5"}
How quantities are defined (for your reference):
  - Link load = sum of bw of flows whose path uses the link + slice reservations on it.
  - Flow latency = sum of link lat_ms on its path + sum over path nodes of base_ms/replicas.
  - Each link has a cap; each flow has an sla_ms and a min_bw; each node has vnf_slots.
"""

PROMPT_TMPL = """You are a network operations agent. Current network state (JSON):

{state}

{opdoc}

Operator intent: {intent}

{closing}
Respond with ONLY a JSON array of operation objects, no prose, no markdown fences.
"""

CLOSE_GUARDED = ("Produce a plan that fulfils the intent while keeping ALL "
                 "invariants satisfied after every step.")
CLOSE_BARE = "Produce a plan that fulfils the operator's intent."


def build_prompt(st: NetState, intent_text: str,
                 guardrail: bool = True) -> str:
    return PROMPT_TMPL.format(
        state=st.to_json(),
        opdoc=OP_DOC if guardrail else OP_DOC_BARE,
        intent=intent_text,
        closing=CLOSE_GUARDED if guardrail else CLOSE_BARE)


class SessionLimit(RuntimeError):
    """Raised when the CLI reports the shared subscription quota is exhausted."""


def provenance(model: str) -> dict:
    """Record what we can about the generation setup for reproducibility."""
    import os
    try:
        ver = subprocess.run(["claude", "--version"], capture_output=True,
                             text=True, timeout=20).stdout.strip()
    except Exception:
        ver = "unknown"
    return {"model_alias": model, "cli_version": ver,
            "max_thinking_tokens": os.environ.get("MAX_THINKING_TOKENS",
                                                  "4000"),
            "sampling": "claude CLI defaults (temperature not overridden)"}


# Suppress the user's MCP servers. They are irrelevant to plan generation and
# cost ~3s of CPU per invocation, which serialises parallel workers. Passed
# explicitly by new callers; archived runners keep their original behaviour so
# their recorded numbers stay reproducible.
FAST_ARGS: Tuple[str, ...] = ("--strict-mcp-config", "--mcp-config",
                              '{"mcpServers":{}}')


def call_claude(prompt: str, model: str = "sonnet",
                timeout: int = 180,
                extra_args: Optional[Sequence[str]] = None
                ) -> Tuple[str, float]:
    import os
    env = {**os.environ, "MAX_THINKING_TOKENS": "4000"}
    cmd = ["claude", "-p", prompt, "--model", model, *(extra_args or ())]
    t0 = time.perf_counter()
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                       stdin=subprocess.DEVNULL, env=env)
    dt = time.perf_counter() - t0
    out = (r.stdout or "") + ("\n" + r.stderr if r.returncode else "")
    if "session limit" in out.lower() or "usage limit" in out.lower():
        raise SessionLimit(out.strip()[:120])
    return out, dt


def measure_cli_floor(model: str = "haiku", repeats: int = 5,
                      extra_args: Optional[Sequence[str]] = None
                      ) -> dict:
    """Wall-clock cost of a near-empty request: the CLI's fixed overhead.

    Generation latency G enters the renewal expressions, so leaving process
    startup inside G would understate verification cost RELATIVE to
    generation -- a bias favouring this paper's own thesis. Recording the
    floor lets the analysis report G both raw and net of overhead.
    """
    times: List[float] = []
    for _ in range(repeats):
        try:
            _, dt = call_claude("Reply with exactly: OK", model=model,
                                timeout=120, extra_args=extra_args)
        except (SessionLimit, subprocess.SubprocessError, OSError):
            break
        times.append(dt)
    if not times:
        return {"floor_s": None, "repeats": 0, "raw_s": []}
    times.sort()
    return {"floor_s": round(times[len(times) // 2], 3),
            "min_s": round(times[0], 3), "max_s": round(times[-1], 3),
            "repeats": len(times), "raw_s": [round(t, 3) for t in times]}


def strip_reasoning(text: str) -> str:
    """Remove chain-of-thought blocks before plan extraction.

    Reasoning-distilled models emit their deliberation in <think> tags, and
    that deliberation routinely contains candidate JSON arrays. Extracting
    the first array in the raw text would therefore pick up a draft the model
    went on to reject. The full response is still stored verbatim; only the
    text handed to the parser is trimmed. A no-op for models that emit no
    such block.
    """
    out = re.sub(r"<think>.*?</think>", "", text, flags=re.S | re.I)
    # An unterminated block means the answer never arrived; keep nothing
    # rather than parse the deliberation itself.
    if re.search(r"<think>", out, flags=re.I):
        out = re.sub(r"<think>.*", "", out, flags=re.S | re.I)
    return out.strip()


def extract_plan(text: str) -> Optional[List[Any]]:
    m = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.S)
    cand = m.group(1) if m else None
    if cand is None:
        i = text.find("[")
        if i < 0:
            return None
        depth = 0
        for j in range(i, len(text)):
            if text[j] == "[":
                depth += 1
            elif text[j] == "]":
                depth -= 1
                if depth == 0:
                    cand = text[i:j + 1]
                    break
    if cand is None:
        return None
    try:
        plan = json.loads(cand)
    except json.JSONDecodeError:
        return None
    return plan if isinstance(plan, list) else None
