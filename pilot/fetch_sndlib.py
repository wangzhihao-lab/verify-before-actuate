"""Fetch the SNDlib native-format topology archive.

SNDlib sets its own terms of use, so this repository does not vendor the
dataset; it pins it instead.  The URL is the weak part of that pin --- hosts
move, and SNDlib has already moved once --- so the SHA-256 is what actually
identifies the data.  A download that does not match the digest is rejected
rather than used, because a silently different topology set would change
every measured number while every runner still succeeded.

    python fetch_sndlib.py            # download, verify, extract
    python fetch_sndlib.py --check    # verify an existing copy only

Cite: S. Orlowski, R. Wessaly, M. Pioro, A. Tomaszewski, "SNDlib 1.0 --
Survivable Network Design Library," Networks 55(3):276--286, 2010.
"""
from __future__ import annotations

import argparse
import hashlib
import logging
import sys
import urllib.request
import zipfile
from pathlib import Path
from typing import Optional, Sequence

logger = logging.getLogger("fetch_sndlib")

ARCHIVE_SHA256 = ("14b59d9c0d00d566b21c29d845a0199e"
                  "ee25dbaae536f7b853c1cbb50863797b")
ARCHIVE_NAME = "sndlib-networks-native.zip"
DEST = Path("data/sndlib")

# Tried in order.  Both have hosted the archive; the digest decides whether
# whatever comes back is usable.
MIRRORS: Sequence[str] = (
    "https://sndlib.put.poznan.pl/download/sndlib-networks-native.zip",
    "http://sndlib.zib.de/download/sndlib-networks-native.zip",
)


def digest(path: Path) -> str:
    """SHA-256 of a file, read in chunks so a large archive stays cheap."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def download(dest: Path, mirrors: Sequence[str] = MIRRORS) -> Path:
    """Try each mirror; return the first that yields bytes."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    errors = []
    for url in mirrors:
        try:
            logger.info("fetching %s", url)
            with urllib.request.urlopen(url, timeout=60) as resp:
                dest.write_bytes(resp.read())
            return dest
        except (OSError, ValueError) as exc:
            logger.warning("mirror failed: %s (%s)", url, exc)
            errors.append(f"{url}: {exc}")
    raise RuntimeError(
        "every mirror failed; download the archive by hand and place it at "
        f"{dest}\n  " + "\n  ".join(errors))


def verify(path: Path, expected: str = ARCHIVE_SHA256) -> None:
    """Raise unless the archive is byte-identical to the pinned copy."""
    if not path.exists():
        raise FileNotFoundError(f"{path} not present; run without --check")
    got = digest(path)
    if got != expected:
        raise ValueError(
            f"SHA-256 mismatch for {path}\n  expected {expected}\n  "
            f"got      {got}\nRefusing to use it: a different topology set "
            "changes every measured number while every runner still "
            "succeeds.")
    logger.info("digest OK: %s", got)


def extract(archive: Path, into: Path) -> int:
    """Extract, refusing any member that would escape the target directory."""
    into.mkdir(parents=True, exist_ok=True)
    n = 0
    with zipfile.ZipFile(archive) as zf:
        for member in zf.namelist():
            target = (into / member).resolve()
            if not str(target).startswith(str(into.resolve())):
                raise ValueError(f"unsafe path in archive: {member}")
        zf.extractall(into)
        n = len(zf.namelist())
    logger.info("extracted %d members -> %s", n, into)
    return n


def main(argv: Optional[list[str]] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--check", action="store_true",
                   help="verify an existing archive without downloading")
    p.add_argument("--dest", default=str(DEST))
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                        format="%(levelname)-7s %(message)s")

    dest = Path(args.dest)
    archive = dest / ARCHIVE_NAME
    try:
        if not args.check and not archive.exists():
            download(archive)
        verify(archive)
        if not args.check:
            extract(archive, dest / "extracted")
    except (RuntimeError, ValueError, FileNotFoundError) as exc:
        logger.error("%s", exc)
        return 1
    print("SNDlib archive present and verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
