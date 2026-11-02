"""Optional C++ native scanner fast path (cycle 6).

The native binary is real code (native/shadowcode-native, built from
native/src/*.cpp), but it is OPTIONAL by design:

- If the binary is absent, every function here returns None and the
  caller falls back to the pure-Python implementation. Nothing
  crashes, nothing is faked.
- If the binary is present, search uses it ONLY for plain
  substring queries. The native searcher is case-insensitive
  substring, while Tools.search_files is a Python regex search,
  so a regex pattern must never be routed to the native binary.
  is_plain_query() is the gate: letters, digits, space, _, -, .,
  / only. Anything else (.*, +, ?, [, ], (, ), ^, $, |, \\) stays
  in Python.
- The native CLI prints absolute paths (sc_search_dir prints
  e.path()), so search() relativises them to the workdir and
  truncates lines to 200 chars, matching the Python tool shape
  "relpath:line: text", capped at 100 hits.
- count_lines / fuzzy_score use the same CLI (count/fuzzy), so
  no ctypes stdout-capture problem: the C library's printf
  output would pollute the JSON-lines protocol if loaded via
  ctypes in-process, hence the subprocess CLI, not CDLL, here.
- Disabled entirely when SHADOWCODE_NO_NATIVE=1.
"""
import os
import re
import subprocess
from pathlib import Path

_PLAIN = re.compile(r"^[A-Za-z0-9 _\-./]+$")
_SKIP_DIRS = {".git", "node_modules", "__pycache__", "dist"}


def is_plain_query(pattern: str) -> bool:
    return bool(pattern) and bool(_PLAIN.match(pattern))


def find_binary(workdir=None):
    """Return the native CLI path if it exists and is executable."""
    if os.environ.get("SHADOWCODE_NO_NATIVE") == "1":
        return None
    here = Path(__file__).resolve().parent.parent
    candidates = [here / "native" / "shadowcode-native"]
    if workdir:
        candidates.append(Path(workdir).resolve() / "native" / "shadowcode-native")
    for cand in candidates:
        if cand.is_file() and os.access(cand, os.X_OK):
            return cand
    return None


def native_available(workdir=None) -> bool:
    return find_binary(workdir) is not None


def native_search(workdir, pattern, cap=100):
    """Plain-substring search via the native CLI, or None to fall back."""
    if not is_plain_query(pattern):
        return None
    binary = find_binary(workdir)
    if binary is None:
        return None
    try:
        r = subprocess.run(
            [str(binary), "search", str(Path(workdir).resolve()), pattern, str(cap)],
            capture_output=True, text=True, timeout=30)
    except Exception:
        return None
    if r.returncode != 0:
        return None
    root = Path(workdir).resolve()
    hits = []
    for line in r.stdout.splitlines():
        # native prints "abs/path:line: text"; path may contain ':' only
        # in the drive/absolute prefix, so split from the right of the
        # line-number field: find ":<digits>: " after the path.
        m = re.match(r"^(.*):(\d+): (.*)$", line)
        if not m:
            continue
        try:
            rel = Path(m.group(1)).resolve().relative_to(root)
        except Exception:
            rel = Path(m.group(1))
        # Skip the same dirs the Python walk skips, by path part.
        if any(part in _SKIP_DIRS for part in rel.parts):
            continue
        hits.append(f"{rel}:{m.group(2)}: {m.group(3)[:200]}")
        if len(hits) >= cap:
            break
    return hits


def native_count_lines(path):
    """(lines, nonempty) via the native CLI, or None to fall back."""
    binary = find_binary()
    if binary is None:
        return None
    try:
        r = subprocess.run([str(binary), "count", str(path)],
                           capture_output=True, text=True, timeout=30)
    except Exception:
        return None
    m = re.search(r"lines=(\d+) nonempty=(\d+)", r.stdout)
    return (int(m.group(1)), int(m.group(2))) if m else None


def native_fuzzy_score(query, candidate):
    """0..100 fuzzy score via the native CLI, or None to fall back."""
    binary = find_binary()
    if binary is None:
        return None
    try:
        r = subprocess.run([str(binary), "fuzzy", query, candidate],
                           capture_output=True, text=True, timeout=30)
    except Exception:
        return None
    m = re.search(r"score=(\d+)", r.stdout)
    return int(m.group(1)) if m else None
