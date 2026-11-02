"""Optional Go /search client for the Python REPL/TUI (cycle 6).

Mirrors tui/src/lib/goSearch.ts: if a Go preview server is
running on 127.0.0.1:port (default 8765, SHADOWCODE_PREVIEW_PORT),
GET /search?q=... returns JSON hits. If no server is running —
the usual case here, because no Go binary was built (no Go
toolchain, see MORNING_APPROVALS.md) — this returns None and
the caller falls back to Tools.search_files, never fake hits.
Stdlib only, 5s timeout, localhost only.
"""
import json
import os
import urllib.request


def go_search_port():
    try:
        return int(os.environ.get("SHADOWCODE_PREVIEW_PORT", "8765"))
    except ValueError:
        return 8765


def search_go(query, port=None):
    """List of (path, line, text) hits, or None if Go is unavailable."""
    if not query.strip():
        return None
    port = port or go_search_port()
    try:
        with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/search?q={urllib.parse.quote(query)}",
                timeout=5) as resp:
            if resp.status != 200:
                return None
            hits = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None
    if not isinstance(hits, list):
        return None
    out = []
    for h in hits:
        try:
            out.append((str(h["path"]), int(h["line"]), str(h["text"])[:200]))
        except Exception:
            continue
    return out
