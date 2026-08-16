"""Run provenance: the metadata every archived result must carry.

The paper's release checklist requires each result to identify the exact
source revision, machine and interpreter that produced it. Centralised here
so no runner can quietly omit it.
"""
from __future__ import annotations

import logging
import platform
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]


def git_sha(short: bool = True) -> str:
    """Current HEAD revision, or ``"nogit"`` when unavailable."""
    cmd = ["git", "rev-parse"] + (["--short"] if short else []) + ["HEAD"]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=20,
                             cwd=REPO_ROOT)
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning("git sha unavailable: %s", exc)
        return "nogit"
    return out.stdout.strip() or "nogit"


# Paths that hold generated results rather than source. A runner writing its
# own output must not be able to make the next runner in the same batch look
# unreproducible, which is what happens once these directories are tracked:
# the first write dirties the tree and every later run records it.
ARTIFACT_PREFIXES = ("pilot/out/", "paper/figures/", "paper/numbers.")


def _status_paths() -> Optional[List[str]]:
    """Repo-relative paths reported by ``git status --porcelain``."""
    try:
        out = subprocess.run(["git", "status", "--porcelain"],
                             capture_output=True, text=True, timeout=20,
                             cwd=REPO_ROOT)
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning("git status unavailable: %s", exc)
        return None
    paths = []
    for line in out.stdout.splitlines():
        entry = line[3:].strip()
        # Renames are reported as "old -> new"; the destination is what counts.
        if " -> " in entry:
            entry = entry.split(" -> ", 1)[1]
        if entry:
            paths.append(entry.strip('"'))
    return paths


def git_dirty() -> Optional[bool]:
    """True when anything at all is uncommitted; None if unknown.

    The broad measure, kept because it is the one a reader can reproduce with
    a single ``git status``. For the question the release checklist actually
    asks -- does the recorded SHA describe the code that ran -- use
    :func:`source_dirty`.
    """
    paths = _status_paths()
    return None if paths is None else bool(paths)


def source_dirty() -> Optional[bool]:
    """True when uncommitted changes touch SOURCE; None if unknown.

    This is the flag that decides whether a result is reproducible from the
    recorded revision. Regenerated artifacts are excluded: a batch of runners
    writing into a tracked output directory would otherwise mark everything
    after the first one dirty, which says nothing about the code.
    """
    paths = _status_paths()
    if paths is None:
        return None
    return any(not p.startswith(ARTIFACT_PREFIXES) for p in paths)


def run_meta(extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Standard provenance block to embed in every result file."""
    meta: Dict[str, Any] = {
        "commit_sha": git_sha(),
        "git_dirty": git_dirty(),
        "source_dirty": source_dirty(),
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor() or platform.machine(),
    }
    if extra:
        meta.update(extra)
    return meta


def stamp() -> str:
    """Local timestamp used for output directory names."""
    return time.strftime("%Y%m%d_%H%M%S")


__all__ = ["git_dirty", "git_sha", "run_meta", "source_dirty", "stamp"]
