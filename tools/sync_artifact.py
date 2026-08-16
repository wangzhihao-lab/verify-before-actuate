"""Materialize the public artifact repository from this paper repository.

The artifact repo is a CURATED SUBSET, not a mirror, and the difference
matters legally and editorially:

  * refs/ and plan/ are internal -- competitive gap analysis, submission
    strategy, handoff notes. Publishing them helps nobody and exposes
    working material that was never written to be read.
  * pilot/data/ is the SNDlib dataset. SNDlib sets its own terms of use, the
    artifact README states the dataset is NOT vendored, and fetch_sndlib.py
    pins it by SHA-256 instead. Shipping it would make the README false.
  * paper/*.tex is the unsubmitted manuscript with a placeholder author
    block. Only the frozen table travels.
  * pilot/REPORT.md is a superseded exploratory report describing a plan
    (Mininet main experiment) that was never run.

Source of truth is `git ls-files`, so anything gitignored -- .venv,
__pycache__, build products -- is excluded by construction rather than by a
pattern this script has to keep in sync.

    python tools/sync_artifact.py --dest ../verify-before-actuate
    python tools/sync_artifact.py --dest ../verify-before-actuate --dry-run
"""
from __future__ import annotations

import argparse
import fnmatch
import logging
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple

logger = logging.getLogger("sync_artifact")

# Prefixes never published, with the reason recorded next to the rule so a
# later reader does not have to reconstruct it.
EXCLUDE_PREFIXES: Dict[str, str] = {
    "refs/": "internal strategy and literature notes",
    "plan/": "internal planning documents",
    "pilot/data/": "SNDlib dataset -- not redistributed, see fetch_sndlib.py",
    "pilot/REPORT.md": "superseded exploratory report",
    "CLAUDE.md": "agent instructions for the paper repo",
    # The paper repo's root ignore rules are about the paper repo (refs/*.pdf,
    # build products); the export writes its own. Excluded explicitly so the
    # generated file is chosen, not merely last to be written.
    ".gitignore": "export generates its own",
    "paper/": "manuscript source; only the frozen table is published",
    # Derivation-era working notes: written in Chinese against the earlier
    # notation (d for the budget, a Lemma/Prop numbering the paper does not
    # use) and interleaved with review-process commentary. Publishing them
    # would put a second, contradictory account of the theory next to the
    # supplement. The closed forms are checked in current notation by
    # pilot/src/exp/fig_theory.py, which IS published.
    "theory/": "superseded derivation notes in earlier notation",
}

# Exploratory and smoke runs. pilot/.gitignore states the intent -- "only the
# runs the paper reads are versioned, so that a reader who clones this cannot
# mistake a superseded or exploratory run for evidence" -- but the paper repo
# tracks these anyway because they were committed before that rule existed.
# Ignore rules do not retroactively untrack. The export honours the intent.
EXCLUDE_GLOBS: Tuple[str, ...] = (
    "pilot/out/smoke_*", "pilot/out/calib_*", "pilot/out/microbench_*",
    "pilot/out/mvp_*", "pilot/out/demo_*", "pilot/out/q_*",
)

# Explicit re-inclusions, applied after every exclusion above.
INCLUDE_PATHS: Tuple[str, ...] = (
    "paper/numbers.json",
    "paper/numbers.md",
)

# ...and one whole directory: its base_state.json is what the adversarial
# injection taxonomy is replayed from, backing the paper's only claim that
# prefix checking strictly dominates terminal checking.
INCLUDE_PREFIXES: Tuple[str, ...] = (
    "pilot/out/q_20260723_060529/",
)

# artifact/<name> is published at the repository root: a reader cloning the
# artifact should land on its README, not on a directory named "artifact".
ARTIFACT_TO_ROOT = "artifact/"

ARTIFACT_GITIGNORE = """\
# Build products
*.aux
*.log
*.out
*.toc
supplement.pdf

# Python
__pycache__/
*.py[cod]
.venv/

# SNDlib is fetched, never committed (see fetch_sndlib.py)
data/
pilot/data/
"""


def tracked_files(repo: Path) -> List[str]:
    out = subprocess.run(["git", "-C", str(repo), "ls-files"],
                         capture_output=True, text=True, check=True)
    return [line for line in out.stdout.splitlines() if line]


def classify(path: str) -> Tuple[bool, str]:
    """(publish?, reason). Explicit includes beat every exclusion."""
    if path in INCLUDE_PATHS or path.startswith(INCLUDE_PREFIXES):
        return True, "explicit include"
    for prefix, reason in EXCLUDE_PREFIXES.items():
        if path.startswith(prefix):
            return False, reason
    for pattern in EXCLUDE_GLOBS:
        if fnmatch.fnmatch(path, pattern + "*"):
            return False, "exploratory or superseded run, not read by the paper"
    return True, ""


def destination(path: str) -> str:
    """Map a repo path to its path in the artifact repo."""
    if path.startswith(ARTIFACT_TO_ROOT):
        return path[len(ARTIFACT_TO_ROOT):]
    return path


def sync(repo: Path, dest: Path, dry_run: bool = False) -> Dict[str, int]:
    files = tracked_files(repo)
    publish, skip = [], {}
    for f in files:
        ok, reason = classify(f)
        if ok:
            publish.append(f)
        else:
            skip.setdefault(reason, []).append(f)

    logger.info("publishing %d of %d tracked files", len(publish), len(files))
    for reason, paths in sorted(skip.items()):
        logger.info("  excluded %3d  (%s)", len(paths), reason)

    if dry_run:
        return {"published": len(publish),
                "excluded": sum(len(v) for v in skip.values())}

    dest.mkdir(parents=True, exist_ok=True)
    for f in publish:
        src = repo / f
        if not src.exists():
            logger.warning("tracked but missing on disk: %s", f)
            continue
        target = dest / destination(f)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)

    (dest / ".gitignore").write_text(ARTIFACT_GITIGNORE)
    logger.info("wrote %s", dest / ".gitignore")
    return {"published": len(publish),
            "excluded": sum(len(v) for v in skip.values())}


def main(argv: List[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dest", required=True)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                        format="%(levelname)-7s %(message)s")

    repo = Path(__file__).resolve().parent.parent
    try:
        stats = sync(repo, Path(args.dest).resolve(), args.dry_run)
    except subprocess.CalledProcessError as exc:
        logger.error("git ls-files failed: %s", exc)
        return 1
    print(f"\npublished {stats['published']}, excluded {stats['excluded']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
