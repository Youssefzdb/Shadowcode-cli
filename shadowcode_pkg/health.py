"""Shadowcode health dashboard (cycle 8) — honest, local-only checks.

Every check reports what it actually found; nothing is faked.
- Python core: version + interpreter, always available (we are it).
- TypeScript TUI: package.json version + dist/ build presence + node
  availability. dist/ absent means "not built", not "broken".
- Go preview: binary presence + a live localhost check. /health with
  JSON {"ok": true} identifies a Go server; /state.json identifies a
  preview server of either kind (Python or Go). If neither answers,
  the server is "unavailable" — never "healthy".
- Native scanner: binary presence/executable (see native_scanner.py).
- Playwright: import availability only; a browser is not started
  by a health check.

No session file is created or modified by any health check, and no
key is read or printed (only key_set yes/no, via config.key_set).
"""
import json
import os
import shutil
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _http_json(url, timeout=1.0):
    """GET url, return parsed JSON or None on any failure."""
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                return None
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def preview_probe(port, timeout=1.0):
    """Probe localhost preview on port.

    Returns dict: go_server (bool), preview_server (bool),
    state (dict or None), error (str). A Go server answers /health
    with {"ok": true}; the Python preview answers /state.json but
    not /health (it serves HTML for unknown paths). Both are
    reported separately so a Python preview is never mislabelled
    as Go, and an absent server is never mislabelled healthy.
    """
    try:
        port = int(port)
    except Exception:
        port = 8765
    health = _http_json(f"http://127.0.0.1:{port}/health", timeout=timeout)
    go_server = isinstance(health, dict) and health.get("ok") is True
    state = _http_json(f"http://127.0.0.1:{port}/state.json", timeout=timeout)
    preview_server = isinstance(state, dict) and "url" in state
    return {
        "port": port,
        "go_server": go_server,
        "preview_server": preview_server,
        "state": state if preview_server else None,
        "error": "" if (go_server or preview_server) else "no preview server on localhost",
    }


def _ts_tui_info():
    tui = ROOT / "tui"
    pkg = tui / "package.json"
    version = ""
    if pkg.is_file():
        try:
            version = str(json.loads(pkg.read_text()).get("version", ""))
        except Exception:
            version = ""
    dist = tui / "dist"
    built = dist.is_dir() and any(dist.iterdir()) if dist.is_dir() else False
    return {
        "package_json": pkg.is_file(),
        "version": version,
        "built": built,
        "node": shutil.which("node") is not None,
    }


def _go_info(workdir=None):
    from .native_scanner import find_binary as _unused  # noqa: F401 (kept for symmetry)
    binary = ROOT / "go" / "shadowcode-preview"
    return {
        "binary": binary.is_file(),
        "executable": bool(binary.is_file() and os.access(binary, os.X_OK)),
        "path": str(binary),
    }


def _native_info(workdir=None):
    from .native_scanner import native_available
    return {"available": native_available(workdir)}


def _playwright_info():
    try:
        import playwright  # noqa: F401
        return {"available": True}
    except Exception:
        return {"available": False}


def health_status(cfg=None, workdir=None, port=None):
    """Full health dict. cfg may be a config dict; all fields optional."""
    cfg = cfg or {}
    if port is None:
        try:
            port = int(cfg.get("preview_port", 8765))
        except Exception:
            port = 8765
    try:
        from . import __version__ as core_version
    except Exception:
        core_version = ""
    probe = preview_probe(port)
    ts = _ts_tui_info()
    return {
        "python_core": {
            "version": core_version,
            "python": sys.version.split()[0],
            "provider": cfg.get("provider", "mock"),
            "model": cfg.get("model", "") or "(default)",
            "working_dir": str(cfg.get("working_dir", workdir or ".")),
            "permission_mode": cfg.get("permission_mode", "manual"),
        },
        "ts_tui": ts,
        "go_preview": {**_go_info(workdir), **{"server_healthy": probe["go_server"]}},
        "preview": {
            "port": probe["port"],
            "healthy": probe["preview_server"],
            "go_server": probe["go_server"],
            "state": probe["state"],
            "error": probe["error"],
        },
        "native_scanner": _native_info(workdir),
        "playwright": _playwright_info(),
    }


def health_history_path(workdir):
    """Workspace-only health-history file: <workdir>/.shadowcode/.

    Never under the home directory, never a session file, and
    never containing a key (health_status has no key values).
    """
    return Path(workdir or ".") / ".shadowcode" / "health-history.jsonl"


def append_health_snapshot(status, workdir, log_path=None):
    """Append one health snapshot to the workspace log file.

    Returns the log path (str). The file is capped at the last
    100 snapshots so it cannot grow without bound. Best-effort:
    a write failure raises, and callers that must not fail (the
    /health display) catch it and keep showing the dashboard.
    """
    path = Path(log_path) if log_path else health_history_path(workdir)
    snap = {
        "time": datetime.now(timezone.utc).isoformat(),
        "python": status["python_core"],
        "ts_tui_built": status["ts_tui"]["built"],
        "ts_tui_node": status["ts_tui"]["node"],
        "go_preview_binary": status["go_preview"]["binary"],
        "go_server_healthy": status["go_preview"]["server_healthy"],
        "preview": {
            "port": status["preview"]["port"],
            "healthy": status["preview"]["healthy"],
            "go_server": status["preview"]["go_server"],
            "driver": (status["preview"]["state"] or {}).get("driver", ""),
            "url": (status["preview"]["state"] or {}).get("url", ""),
            "title": (status["preview"]["state"] or {}).get("title", ""),
        },
        "native_scanner": status["native_scanner"]["available"],
        "playwright": status["playwright"]["available"],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    if path.is_file():
        lines = [ln for ln in path.read_text(errors="replace").splitlines() if ln.strip()]
    lines.append(json.dumps(snap))
    path.write_text("\n".join(lines[-100:]) + "\n")
    return str(path)


def read_health_history(workdir, limit=10, log_path=None):
    """Last `limit` snapshots, newest first. Missing/unreadable
    log, or a bad line, yields [] / skipped lines — never a fake
    snapshot. limit is clamped to 1..50."""
    try:
        limit = max(1, min(50, int(limit)))
    except Exception:
        limit = 10
    path = Path(log_path) if log_path else health_history_path(workdir)
    if not path.is_file():
        return [], str(path)
    snaps = []
    for ln in path.read_text(errors="replace").splitlines():
        try:
            snaps.append(json.loads(ln))
        except Exception:
            continue
    return list(reversed(snaps[-limit:])), str(path)


def format_health_history(snapshots, path=""):
    """Human-readable last snapshots, newest first."""
    lines = ["health history (newest first):"]
    if path:
        lines[0] += f"  [saved: {path}]"
    if not snapshots:
        lines.append("  no snapshots yet — run /health (or --health) first;")
        lines.append("  each health check appends one snapshot to the log file.")
        return "\n".join(lines)
    for s in snapshots:
        pv = s.get("preview", {})
        lines.append(
            f"  {s.get('time', '')} python={s.get('python', {}).get('version', '')} "
            f"provider={s.get('python', {}).get('provider', '')} "
            f"preview={'healthy' if pv.get('healthy') else 'unavailable'} port={pv.get('port', '')} "
            f"driver={pv.get('driver', '')} url={pv.get('url', '')} "
            f"go_binary={'yes' if s.get('go_preview_binary') else 'no'} "
            f"native={'yes' if s.get('native_scanner') else 'no'} "
            f"playwright={'yes' if s.get('playwright') else 'no'} "
            f"ts_built={'yes' if s.get('ts_tui_built') else 'no'}")
    return "\n".join(lines)


def format_health(status):
    """Human-readable health dashboard, one line per component."""
    py = status["python_core"]
    ts = status["ts_tui"]
    go = status["go_preview"]
    pv = status["preview"]
    nat = status["native_scanner"]
    pw = status["playwright"]
    st = pv["state"] or {}
    lines = [
        "Shadowcode health dashboard",
        f"python core: OK  version={py['version']} python={py['python']} provider={py['provider']} model={py['model']} perm={py['permission_mode']} workdir={py['working_dir']}",
        f"typescript tui: package_json={'yes' if ts['package_json'] else 'no'} version={ts['version'] or '—'} built={'yes' if ts['built'] else 'no (run: cd tui && npm run build)'} node={'available' if ts['node'] else 'not found'}",
        f"go preview: binary={'yes' if go['binary'] else 'no (not built here; see MORNING_APPROVALS.md)'} executable={'yes' if go['executable'] else 'no'} server={'healthy (Go /health)' if go['server_healthy'] else 'unavailable'}",
        f"preview server: port={pv['port']} {'healthy' if pv['healthy'] else 'unavailable'}"
        + (f" driver={st.get('driver', '')} title={st.get('title', '')} url={st.get('url', '')} has_screenshot={st.get('has_screenshot', False)}" if pv["healthy"] else f" ({pv['error']})"),
        f"native scanner (C++): {'available' if nat['available'] else 'unavailable (Python fallback)'}",
        f"playwright: {'available' if pw['available'] else 'NOT available (browser tool disabled until: pip install playwright && playwright install firefox)'}",
    ]
    return "\n".join(lines)


def format_browser_panel(state, preview_url="", health="unknown"):
    """Browser panel for /browser: fresh state + takeover/handback
    hints + watch-log tail. state is Browser.state() or a probe
    state dict; an empty/None state means 'not started'."""
    lines = ["browser preview:"]
    if not state or (not state.get("url") and not state.get("title")):
        lines.append("  not started (no live page yet)")
        lines.append(f"  health: {health}")
        if preview_url:
            lines.append(f"  preview url: {preview_url}")
        lines.append("  start it via the agent, e.g. ask it to: open https://example.com")
        lines.append("  then open the preview URL in your own browser to watch live.")
        return "\n".join(lines)
    lines.append(f"  health: {health}")
    if preview_url:
        lines.append(f"  preview url: {preview_url}")
    lines.append(f"  title: {state.get('title', '')}")
    lines.append(f"  url: {state.get('url', '')}")
    lines.append(f"  driver: {state.get('driver', '')}")
    lines.append(f"  has_screenshot: {state.get('has_screenshot', False)}")
    if state.get("last_control_error"):
        lines.append(f"  last_control_error: {state['last_control_error']}")
    lines.append("  takeover: in the preview, click 'Take control' to drive it yourself;")
    lines.append("    the agent pauses and WATCHES (watch log below) while you drive.")
    lines.append("  handback: click 'Hand back to agent' in the preview; the agent")
    lines.append("    resumes from THIS page exactly — no reload, no reset —")
    lines.append("    via browser_watch / browser_read on the current page.")
    watch = state.get("watch") or []
    total = state.get("watch_count", len(watch))
    lines.append(f"  full replay: /browser-watch prints all {total} watch entries (this panel shows only the tail)")
    lines.append(f"  watch log (last {min(5, len(watch))} of {total} shown):")
    if not watch:
        lines.append("    (no page changes observed yet)")
    for e in watch[-5:]:
        via = e.get("via", "")
        suffix = f" via {via}"
        # Cycle 15: same action-prefix classification as
        # browser.via_kind (local import to avoid a top-level
        # cycle); a selector containing 'scroll'/'click' must
        # not cross-mark the entry.
        try:
            from .browser import via_kind
            kind = via_kind(via)
        except Exception:
            kind = ""
        if kind == "click":
            suffix += " [click-driven]"
        if kind == "scroll":
            suffix += " [scroll]"
        lines.append(f"    {e.get('time', '')} {e.get('title', '')} — {e.get('url', '')} ({e.get('driver', '')}){suffix}")
    return "\n".join(lines)
