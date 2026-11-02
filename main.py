#!/usr/bin/env python3
"""Shadowcode — original CLI AI agent. See SPEC.md."""
import argparse, json, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from shadowcode_pkg import __version__
from shadowcode_pkg.config import load_config, key_set, key_env_name, last_session_file
from shadowcode_pkg.providers import get_provider
from shadowcode_pkg.tools import Tools, TOOL_NAMES
from shadowcode_pkg.agent import run_agent
from shadowcode_pkg import session as sess

def confirm(prompt):
    try:
        return input(prompt).strip().lower() in ("y", "yes")
    except EOFError:
        return False

def doctor(cfg):
    print(f"Shadowcode {__version__}  python={sys.version.split()[0]}")
    print(f"provider={cfg['provider']} model={cfg.get('model') or '(default)'} key_env={key_env_name(cfg['provider'])} key_set={'yes' if key_set(cfg['provider']) else 'no'}")
    print(f"working_dir={cfg['working_dir']} permission_mode={cfg['permission_mode']}")
    for p in ["shadowcode.json", ".shadowcode/settings.json", str(Path.home()/'.config/shadowcode/config.json')]:
        print(f"config {p}: {'found' if Path(p).is_file() else 'not found'}")
    try:
        import playwright; print("playwright: available")
    except Exception:
        print("playwright: NOT available (browser tool disabled until: pip install playwright && playwright install firefox)")
    print(f"sessions: {len(sess.list_sessions())} saved")

def parse_search_args(text):
    """Parse '/search-sessions <q> [--from D] [--to D]' the same way in
    the REPL, the curses TUI, and the TS TUI. Returns (query, from, to)."""
    parts = text.split()
    query, from_date, to_date = [], None, None
    i = 0
    while i < len(parts):
        if parts[i] == "--from" and i + 1 < len(parts):
            from_date = parts[i + 1]; i += 2
        elif parts[i] == "--to" and i + 1 < len(parts):
            to_date = parts[i + 1]; i += 2
        else:
            query.append(parts[i]); i += 1
    return " ".join(query), from_date, to_date


def go_search_command(query, tools):
    """Cycle 6 parity: Go /search first, Python search_files fallback."""
    from shadowcode_pkg.go_search import search_go, go_search_port
    hits = search_go(query)
    if hits is not None:
        if not hits:
            return "no matches (Go search)"
        return "\n".join(f"{p}:{ln}: {t}" for p, ln, t in hits)
    port = go_search_port()
    return (f"Go search unavailable on localhost:{port} (no Go server running; "
            f"Go binary was not built here — see MORNING_APPROVALS.md). "
            f"Python fallback:\n{tools.search_files(query)}")


def browser_panel_text(get_browser, cfg):
    """Cycle 8 /browser: fresh state, takeover/handback hints, watch
    tail — without starting a browser that is not already running.
    get_browser() only creates the Browser object; the thread is
    started by the first browser_* tool call, so a not-yet-started
    browser is reported as 'not started', never faked as live.
    A localhost preview probe (Go or Python server) is shown when
    it answers, even if this process did not start it."""
    from shadowcode_pkg.health import format_browser_panel, preview_probe
    port = 8765
    try:
        port = int(cfg.get("preview_port", 8765))
    except Exception:
        pass
    probe = preview_probe(port)
    # If this process has a running browser thread, its state is freshest.
    try:
        b = get_browser()
        thread_started = getattr(b, "_thread", None) is not None
        if thread_started:
            st = b.state()
            return format_browser_panel(st, getattr(b, "preview_url", ""), "healthy")
    except Exception as e:
        return format_browser_panel(None, "", f"unavailable ({e})")
    if probe["preview_server"] and probe["state"]:
        return format_browser_panel(probe["state"], f"http://localhost:{port}", "healthy")
    return format_browser_panel(None, "", "unavailable")


def health_text(cfg):
    """Cycle 8 /health: the shared health dashboard (see health.py).

    Cycle 9: each health check also appends one snapshot to the
    workspace log file (<workdir>/.shadowcode/health-history.jsonl),
    so /health-history can show recent snapshots. A write failure
    never breaks the dashboard itself.
    """
    from shadowcode_pkg.health import format_health, health_status, append_health_snapshot
    status = health_status(cfg, cfg.get("working_dir"))
    try:
        append_health_snapshot(status, cfg.get("working_dir"))
    except Exception:
        pass
    return format_health(status)


def health_history_text(cfg, limit=10):
    """Cycle 9 /health-history: last snapshots, newest first."""
    from shadowcode_pkg.health import read_health_history, format_health_history
    snaps, path = read_health_history(cfg.get("working_dir"), limit)
    return format_health_history(snaps, path)


def browser_watch_text(get_browser, cfg):
    """Cycle 9 /browser-watch: the FULL watch log, not the tail.

    Live browser thread first (full_watch_text, with driver
    transitions); otherwise the saved per-session log file in
    <workdir>/.shadowcode/; otherwise an honest 'no log yet'.
    Never starts a browser just to replay, and never invents a log.
    """
    from shadowcode_pkg.browser import load_saved_watch_log, format_watch_log
    try:
        b = get_browser()
        if getattr(b, "_thread", None) is not None:
            return b.full_watch_text()
    except Exception:
        pass
    path, entries = load_saved_watch_log(cfg.get("working_dir"))
    if path:
        return format_watch_log(entries, path)
    return ("browser watch replay: no watch log yet "
            "(start the browser first, then /browser-watch; "
            "saved logs live in <workdir>/.shadowcode/browser-watch-*.json)")


def sessions_view_dispatch(text):
    """Cycle 9: resolve a /sessions-view argument to an action.

    Returns (kind, output_or_sid). Kinds: list/search/select/info/
    export/export-file/resume/error. Only 'resume' needs the caller
    to load a session into memory (the approved path); info/export
    are read-only, export-file is the approved export path, and
    list/search/select never edit a session file.
    """
    kind, sid, action, extra = sess.parse_sessions_view_action(text)
    if kind == "list":
        return ("list", sess.sessions_view())
    if kind == "search":
        return ("search", sess.sessions_view(text))
    if kind == "select":
        try:
            return ("select", sess.sessions_view_selected(sid))
        except Exception as e:
            return ("error", f"session view failed: {e}")
    # action
    try:
        if action == "info":
            d = sess.load(sid)
            return ("info", f"id={d.get('id')} provider={d.get('provider')} model={d.get('model') or '(default)'} messages={len(d.get('messages', []))} updated={d.get('updated_at', '')}")
        if action == "export":
            fmt = extra if extra in ("md", "json") else "md"
            return ("export", sess.export_session(sid, fmt))
        if action == "export-file":
            if isinstance(extra, tuple):
                fmt, path = extra
            elif extra in ("md", "json"):
                fmt, path = extra, None
            else:
                fmt, path = "md", None
            return ("export-file", f"exported to {sess.export_session_file(sid, fmt, path)}")
        if action == "resume":
            return ("resume", sid)
    except Exception as e:
        return ("error", f"session view action failed: {e}")
    return ("error", f"unknown sessions-view action: {action}")


def build_parser():
    p = argparse.ArgumentParser(prog="shadowcode", description="Shadowcode — CLI AI agent (original, see SPEC.md)")
    p.add_argument("prompt", nargs="?", help="one-shot prompt")
    p.add_argument("-p", "--print", action="store_true", help="print response and exit")
    p.add_argument("--provider"); p.add_argument("--model"); p.add_argument("--config")
    p.add_argument("--workdir"); p.add_argument("--add-dir", nargs="*", default=[])
    p.add_argument("--allowed-tools", nargs="*", default=[])
    p.add_argument("--disallowed-tools", nargs="*", default=[])
    p.add_argument("--permission-mode", choices=["manual", "auto", "plan"])
    p.add_argument("--allow-destructive", action="store_true")
    p.add_argument("--allow-outside", action="store_true")
    p.add_argument("--dry-run", action="store_true", help="show diffs / would-write, do not write or edit files")
    p.add_argument("--no-stream", action="store_true", help="disable token streaming, wait for full reply")
    p.add_argument("--json-lines", action="store_true", help="emit JSON-lines events (token/tool/final/session) for the TypeScript TUI; implies --no-tui")
    p.add_argument("--tui", action="store_true", help="force the curses TUI (default on a TTY)")
    p.add_argument("--no-tui", action="store_true", help="force the plain REPL instead of the TUI")
    p.add_argument("--yes", action="store_true")
    p.add_argument("--session-id"); p.add_argument("--resume")
    p.add_argument("--export-session", help="export a saved session and exit")
    p.add_argument("--export-format", choices=["md", "json"], default="md")
    p.add_argument("--export-output", help="write the export to this file instead of stdout")
    p.add_argument("--search-sessions", help="search saved sessions and exit")
    p.add_argument("--search-from", help="search sessions updated on/after YYYY-MM-DD")
    p.add_argument("--search-to", help="search sessions updated on/before YYYY-MM-DD")
    p.add_argument("--list-sessions", action="store_true", help="list saved sessions and exit (read-only)")
    p.add_argument("--search-files", help="search files in the workdir and exit (Python search_files; native fast path when available)")
    p.add_argument("--compact-session", help="compact a saved session in place (extractive, keep system + last 10) and exit")
    p.add_argument("--session-info", help="show a saved session's id/provider/model/message count and exit")
    p.add_argument("--mcp-servers", action="store_true", help="list configured MCP servers and exit (local stdio only)")
    p.add_argument("--mcp-tools", help="list tools on an MCP server and exit (local stdio only)")
    p.add_argument("--permissions", action="store_true", help="show permission mode and allow/deny lists and exit")
    p.add_argument("--run-shell", help="run a shell command in the workdir and exit (same as REPL !cmd)")
    p.add_argument("--continue", dest="cont", action="store_true")
    p.add_argument("--health", action="store_true", help="print the health dashboard and exit (python core, TS TUI, Go preview, native scanner, Playwright)")
    p.add_argument("--health-history", nargs="?", const="10", default=None, help="print the last N health snapshots from the workspace log and exit (default 10, read-only)")
    p.add_argument("--browser-watch", action="store_true", help="print the full browser watch-log replay from the saved workspace log and exit (read-only)")
    p.add_argument("--doctor", action="store_true")
    p.add_argument("--version", action="store_true")
    p.add_argument("--verbose", action="store_true")
    return p

def run_tui(cfg, session, messages, tools, provider, get_browser, mcp_client, mcp_servers, doctor_fn):
    """Curses TUI loop. Returns 0 on clean exit, raises on curses failure
    so the caller can fall back to the plain REPL."""
    import curses
    from shadowcode_pkg.tui import TUIState, CursesUI
    from shadowcode_pkg import session as sess
    from shadowcode_pkg.tools import TOOL_NAMES

    state = TUIState(cfg["provider"], cfg.get("model", ""), session["id"], cfg["permission_mode"])
    state.add("system", "Shadowcode TUI — /help for commands, /exit to quit. !cmd = shell.")
    holder = {}

    def inner(stdscr):
        curses.curs_set(1)
        ui = CursesUI(stdscr, state)
        holder["ui"] = ui
        nonlocal_provider = {"provider": provider}

        def confirm(prompt):
            return ui.ask_yes_no(prompt)

        def stream_cb(token):
            state.add_token(token)
            ui.refresh()

        def tool_cb(name, result):
            state.add_tool(name, result)
            if name.startswith("browser_"):
                try:
                    b = get_browser()
                    if getattr(b, "_thread", None) is not None:
                        st = b.state()
                        state.set_browser(st.get("driver", ""), st.get("url", ""),
                                          st.get("title", ""), "healthy", st.get("watch"))
                except Exception:
                    pass
            ui.refresh()

        ui.refresh()
        while True:
            line = ui.input_line()
            if line is None:
                break
            line = line.strip()
            if not line:
                continue
            if line in ("/exit", "/quit"):
                break
            if line == "/help":
                state.add("system", "/help /model /provider /tools /sessions [query] /sessions-view [query] /sessions-view <id> info|export|export-file|resume /session-info <id> /search-sessions <q> [--from D] [--to D] /export <id> [md|json] /export-file <id> [md|json] [path] /resume <id> /clear /compact /permissions /browser /browser-watch /browser-watch-replay /health /health-history [n] /mcp /doctor /go-search <q> /exit — !cmd = shell")
                ui.refresh(); continue
            if line.startswith("/model"):
                parts = line.split(maxsplit=1)
                if len(parts) > 1:
                    cfg["model"] = parts[1]; session["model"] = parts[1]; state.model = parts[1]
                state.add("system", f"model={cfg.get('model') or '(default)'}"); ui.refresh(); continue
            if line.startswith("/provider"):
                parts = line.split(maxsplit=1)
                if len(parts) > 1:
                    cfg["provider"] = parts[1]; session["provider"] = parts[1]
                    nonlocal_provider["provider"] = get_provider(parts[1]); state.provider = parts[1]
                state.add("system", f"provider={cfg['provider']} key_set={'yes' if key_set(cfg['provider']) else 'no'}"); ui.refresh(); continue
            if line == "/tools":
                state.add("system", ", ".join(TOOL_NAMES)); ui.refresh(); continue
            if line == "/sessions":
                for s in sess.sessions_table():
                    state.add("system", s)
                ui.refresh(); continue
            if line.startswith("/sessions ") or line.startswith("/search-sessions "):
                q, fd, td = parse_search_args(line.split(maxsplit=1)[1])
                for h in sess.search_sessions(q, from_date=fd, to_date=td):
                    state.add("system", f"{h[0]} provider={h[1]} messages={h[2]} updated={h[3]} snippet={h[4]}")
                ui.refresh(); continue
            if line.startswith("/export"):
                parts = line.split()
                if len(parts) < 2:
                    state.add("system", "usage: /export <id> [md|json]  /export-file <id> [md|json] [path]")
                elif parts[0] == "/export-file":
                    try:
                        fmt = parts[2] if len(parts) > 2 else "md"
                        path = parts[3] if len(parts) > 3 else None
                        state.add("system", f"exported to {sess.export_session_file(parts[1], fmt, path)}")
                    except Exception as e:
                        state.add("system", f"export failed: {e}")
                else:
                    try:
                        fmt = parts[2] if len(parts) > 2 else "md"
                        state.add("system", sess.export_session(parts[1], fmt)[:2000])
                    except Exception as e:
                        state.add("system", f"export failed: {e}")
                ui.refresh(); continue
            if line.startswith("/resume"):
                try:
                    s = sess.load(line.split(maxsplit=1)[1]); session.update(s); messages[:] = s["messages"]
                    state.add("system", f"resumed {s['id']} ({len(messages)} messages)")
                except Exception as e:
                    state.add("system", f"resume failed: {e}")
                ui.refresh(); continue
            if line == "/clear":
                messages.clear(); state.add("system", "history cleared"); ui.refresh(); continue
            if line == "/compact":
                new_msgs, dropped = sess.compact_messages(messages, keep=10)
                messages[:] = new_msgs
                state.add("system", f"context compacted: {dropped} removed, {len(messages)} kept"); ui.refresh(); continue
            if line == "/permissions":
                perms = cfg.get("permissions", {}) or {}
                state.add("system", f"mode={cfg['permission_mode']} allow={perms.get('allow')} deny={perms.get('deny')}"); ui.refresh(); continue
            if line == "/browser":
                try:
                    panel = browser_panel_text(get_browser, cfg)
                    state.add("system", panel)
                    # Keep the header/status in sync with the fresh state.
                    try:
                        b = get_browser()
                        if getattr(b, "_thread", None) is not None:
                            st = b.state()
                            state.set_browser(st.get("driver", ""), st.get("url", ""),
                                              st.get("title", ""), "healthy", st.get("watch"))
                    except Exception:
                        pass
                except Exception as e:
                    state.add("system", f"browser not started: {e}")
                ui.refresh(); continue
            if line == "/health":
                state.add("system", health_text(cfg)); ui.refresh(); continue
            if line.startswith("/health-history"):
                parts = line.split()
                try:
                    limit = int(parts[1]) if len(parts) > 1 else 10
                except Exception:
                    limit = 10
                state.add("system", health_history_text(cfg, limit)); ui.refresh(); continue
            if line == "/browser-watch" or line.startswith("/browser-watch ") or line == "/browser-watch-replay":
                try:
                    state.add("system", browser_watch_text(get_browser, cfg))
                except Exception as e:
                    state.add("system", f"browser watch replay failed: {e}")
                ui.refresh(); continue
            if line.startswith("/sessions-view"):
                arg = line.split(maxsplit=1)[1] if len(line.split(maxsplit=1)) > 1 else ""
                kind, out = sessions_view_dispatch(arg)
                if kind == "resume":
                    try:
                        s = sess.load(out); session.update(s); messages[:] = s["messages"]
                        state.add("system", f"resumed {s['id']} ({len(messages)} messages)")
                    except Exception as e:
                        state.add("system", f"resume failed: {e}")
                else:
                    state.add("system", out)
                ui.refresh(); continue
            if line.startswith("/session-info"):
                parts = line.split(maxsplit=1)
                if len(parts) < 2:
                    state.add("system", "usage: /session-info <id>")
                else:
                    try:
                        d = sess.load(parts[1])
                        state.add("system", f"id={d.get('id')} provider={d.get('provider')} model={d.get('model') or '(default)'} messages={len(d.get('messages', []))} updated={d.get('updated_at', '')}")
                    except Exception as e:
                        state.add("system", f"session info failed: {e}")
                ui.refresh(); continue
            if line.startswith("/mcp"):
                parts = line.split(maxsplit=1)
                if not mcp_client:
                    state.add("system", "mcp: no servers configured")
                elif len(parts) == 1:
                    state.add("system", f"mcp servers: {', '.join(mcp_servers)}")
                else:
                    try:
                        state.add("system", f"mcp tools on {parts[1]}: {mcp_client.list_tools(parts[1])}")
                    except Exception as e:
                        state.add("system", f"mcp error: {e}")
                ui.refresh(); continue
            if line == "/doctor":
                # Real doctor output, captured (not printed to curses).
                import io, contextlib
                buf = io.StringIO()
                try:
                    with contextlib.redirect_stdout(buf):
                        doctor_fn(cfg)
                    for ln in buf.getvalue().splitlines():
                        state.add("system", ln)
                except Exception as e:
                    state.add("system", f"doctor failed: {e}")
                ui.refresh(); continue
            if line.startswith("/go-search "):
                state.add("system", go_search_command(line.split(maxsplit=1)[1], tools)); ui.refresh(); continue
            if line.startswith("!"):
                state.add_tool("run_shell", tools.run_shell(line[1:])); ui.refresh(); continue
            state.add_user(line)
            messages.append({"role": "user", "content": line})
            state.status = "Thinking…"
            state.thinking = True
            ui.refresh()
            out = run_agent(nonlocal_provider["provider"], tools, cfg, messages,
                            confirm_fn=confirm,
                            on_token=stream_cb if cfg.get("stream", True) else None,
                            on_tool=tool_cb)
            if not cfg.get("stream", True):
                state.add("assistant", out)
            state.status = "Done."
            state.thinking = False
            ui.refresh()
            sess.save(session)
    curses.wrapper(inner)
    return 0


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.version:
        print(f"shadowcode {__version__}"); return 0
    cfg = load_config(args.config)
    for k, v in [("provider", args.provider), ("model", args.model),
                 ("working_dir", args.workdir), ("permission_mode", args.permission_mode)]:
        if v: cfg[k] = v
    if args.allowed_tools: cfg["allowed_tools"] = args.allowed_tools
    if args.disallowed_tools: cfg["disallowed_tools"] = args.disallowed_tools
    cfg["allow_destructive"] = cfg["allow_destructive"] or args.allow_destructive
    cfg["allow_outside"] = cfg["allow_outside"] or args.allow_outside
    cfg["dry_run"] = cfg.get("dry_run", False) or args.dry_run
    cfg["stream"] = not args.no_stream
    cfg["yes"] = cfg["yes"] or args.yes
    cfg["add_dirs"] = list(cfg.get("add_dirs", []) or []) + args.add_dir
    if args.health:
        print(health_text(cfg)); return 0
    if args.health_history is not None:
        try:
            limit = int(args.health_history)
        except Exception:
            limit = 10
        print(health_history_text(cfg, limit)); return 0
    if args.browser_watch:
        # Read-only replay from the saved workspace log: this flag
        # must not start a browser (no Playwright import here).
        from shadowcode_pkg.browser import load_saved_watch_log, format_watch_log
        path, entries = load_saved_watch_log(cfg.get("working_dir"))
        if path:
            print(format_watch_log(entries, path))
        else:
            print("browser watch replay: no watch log yet "
                  "(start the browser first, then --browser-watch; "
                  "saved logs live in <workdir>/.shadowcode/browser-watch-*.json)")
        return 0
    if args.doctor:
        doctor(cfg); return 0
    if args.list_sessions:
        for row in sess.sessions_table():
            print(row)
        return 0
    if args.search_files:
        # Tools only, no provider/session touched. Native fast path is
        # inside search_files; SHADOWCODE_NO_NATIVE=1 forces pure Python.
        tools = Tools(cfg["working_dir"], cfg["allow_outside"], cfg["add_dirs"])
        print(tools.search_files(args.search_files))
        return 0
    if args.session_info:
        try:
            d = sess.load(args.session_info)
        except Exception as e:
            print(f"session info failed: {e}"); return 1
        print(f"id={d.get('id')} provider={d.get('provider')} model={d.get('model') or '(default)'} messages={len(d.get('messages', []))} updated={d.get('updated_at', '')}")
        return 0
    if args.compact_session:
        try:
            d = sess.load(args.compact_session)
            new_msgs, dropped = sess.compact_messages(d.get("messages", []), keep=10)
            d["messages"] = new_msgs
            sess.save(d)
        except Exception as e:
            print(f"compact failed: {e}"); return 1
        print(f"compacted {args.compact_session}: {dropped} removed, {len(new_msgs)} kept")
        return 0
    if args.permissions:
        perms = cfg.get("permissions", {}) or {}
        print(f"mode={cfg['permission_mode']} allow={perms.get('allow')} deny={perms.get('deny')} allowed_tools={cfg.get('allowed_tools')} disallowed_tools={cfg.get('disallowed_tools')} allow_destructive={cfg.get('allow_destructive')}")
        return 0
    if args.run_shell:
        tools = Tools(cfg["working_dir"], cfg["allow_outside"], cfg["add_dirs"])
        print(tools.run_shell(args.run_shell))
        return 0
    if args.mcp_servers or args.mcp_tools:
        servers = (cfg.get("mcp") or {}).get("servers") or {}
        if not servers:
            print("mcp: no servers configured (shadowcode.json mcp.servers, local stdio only)")
            return 0
        if args.mcp_servers:
            print(f"mcp servers: {', '.join(sorted(servers))}")
            return 0
        try:
            from shadowcode_pkg.mcp import MCPClient
            client = MCPClient(servers, cfg["working_dir"])
            print(f"mcp tools on {args.mcp_tools}: {client.list_tools(args.mcp_tools)}")
            client.close()
        except Exception as e:
            print(f"mcp error: {e}"); return 1
        return 0
    if args.search_sessions:
        hits = sess.search_sessions(args.search_sessions, from_date=args.search_from, to_date=args.search_to)
        if not hits:
            print("no sessions match")
        for h in hits:
            print(f"{h[0]} provider={h[1]} messages={h[2]} updated={h[3]} snippet={h[4]}")
        return 0
    if args.export_session:
        try:
            text = sess.export_session(args.export_session, args.export_format)
        except Exception as e:
            print(f"export failed: {e}"); return 1
        if args.export_output:
            Path(args.export_output).write_text(text)
            print(f"exported {args.export_session} -> {args.export_output}")
        else:
            print(text)
        return 0

    # session
    sid = args.session_id or ""
    messages = []
    if args.resume:
        s = sess.load(args.resume); sid = s["id"]; messages = s["messages"]; cfg["provider"] = s.get("provider", cfg["provider"]); cfg["model"] = s.get("model", cfg["model"])
    elif args.cont:
        latest = sess.latest()
        if latest:
            s = sess.load(latest); sid = s["id"]; messages = s["messages"]
    if not sid:
        sid = args.session_id or sess.new_id()
    elif args.session_id and not args.resume and not args.cont:
        # Fresh start with an existing --session-id must not overwrite
        # the old session: bump to a free id instead.
        unique = sess.ensure_unique_id(sid)
        if unique != sid:
            print(f"session id {sid} already exists, using {unique} instead")
            sid = unique
    session = {"id": sid, "provider": cfg["provider"], "model": cfg.get("model", ""), "messages": messages}

    # project instructions (own file)
    proj = Path(cfg["working_dir"]) / "SHADOWCODE.md"
    if proj.is_file() and not any(m.get("role") == "system" for m in messages):
        messages.insert(0, {"role": "system", "content": proj.read_text()[:4000]})

    browser = None
    def get_browser():
        nonlocal browser
        if browser is None:
            from shadowcode_pkg.browser import Browser
            browser = Browser(cfg["working_dir"], int(cfg.get("preview_port", 8765)))
        return browser
    # lazy browser: Tools wrapper that creates browser on first browser_* call
    class LazyBrowser:
        def call(self, name, a):
            return get_browser().call(name, a)
    mcp_client = None
    mcp_servers = (cfg.get("mcp") or {}).get("servers") or {}
    if mcp_servers:
        from shadowcode_pkg.mcp import MCPClient
        mcp_client = MCPClient(mcp_servers, cfg["working_dir"])
    tools = Tools(cfg["working_dir"], cfg["allow_outside"], cfg["add_dirs"],
                  browser=LazyBrowser(), dry_run=cfg["dry_run"], mcp=mcp_client)
    provider = get_provider(cfg["provider"])

    def stream_cb(token):
        if cfg.get("stream", True):
            sys.stdout.write(token)
            sys.stdout.flush()

    def run_one(prompt):
        messages.append({"role": "user", "content": prompt})
        if args.json_lines:
            def json_token(token):
                print(json.dumps({"type": "token", "text": token}), flush=True)
            def json_tool(name, result):
                print(json.dumps({"type": "tool", "name": name, "result": str(result)[:2000]}), flush=True)
            out = run_agent(provider, tools, cfg, messages,
                            confirm_fn=confirm,
                            on_token=json_token if cfg.get("stream", True) else None,
                            on_tool=json_tool)
            print(json.dumps({"type": "final", "text": out}), flush=True)
            print(json.dumps({"type": "session", "id": sid}), flush=True)
            sess.save(session); last_session_file().write_text(sid)
            return out
        # in one-shot, no interactive confirm unless --yes; agent handles it
        out = run_agent(provider, tools, cfg, messages,
                        confirm_fn=None if args.yes is False and not sys.stdin.isatty() else confirm,
                        on_token=stream_cb if cfg.get("stream", True) else None)
        if cfg.get("stream", True):
            print()  # newline after streamed tokens (final reply already streamed)
        else:
            print(out)
        sess.save(session); last_session_file().write_text(sid)
        return out

    if args.prompt or args.print:
        prompt = args.prompt or ""
        if not prompt:
            prompt = sys.stdin.read().strip()
        if not prompt:
            print("no prompt given"); return 2
        run_one(prompt)
        return 0

    # TUI (default on a TTY) with plain-REPL fallback
    use_tui = args.tui or (sys.stdin.isatty() and not args.no_tui)
    if use_tui:
        try:
            run_tui(cfg, session, messages, tools, provider, get_browser, mcp_client, mcp_servers, doctor)
            sess.save(session)
            if browser: browser.close()
            if mcp_client: mcp_client.close()
            print(f"session saved: {sid}  (resume: shadowcode --resume {sid})")
            return 0
        except Exception as e:
            print(f"TUI unavailable ({e}); falling back to plain REPL.")
    # REPL
    print(f"Shadowcode {__version__}  provider={cfg['provider']} model={cfg.get('model') or '(default)'} session={sid}")
    print("Type /help for commands, /exit to quit. !cmd runs a shell command.")
    while True:
        try:
            line = input("shadowcode> ").strip()
        except EOFError:
            print(); break
        if not line: continue
        if line in ("/exit", "/quit"): break
        if line == "/help":
            print("/help /model [name] /provider [name] /tools /sessions [query] /sessions-view [query] /sessions-view <id> info|export|export-file|resume /session-info <id> /search-sessions <q> [--from D] [--to D] /export <id> [md|json] /export-file <id> [md|json] [path] /resume <id> /clear /compact /permissions /browser /browser-watch /browser-watch-replay /health /health-history [n] /mcp [server] /doctor /go-search <q> /exit  —  !cmd = shell")
            continue
        if line.startswith("/model"):
            parts = line.split(maxsplit=1)
            if len(parts) > 1: cfg["model"] = parts[1]; session["model"] = parts[1]
            print(f"model={cfg.get('model') or '(default)'}"); continue
        if line.startswith("/provider"):
            parts = line.split(maxsplit=1)
            if len(parts) > 1:
                cfg["provider"] = parts[1]; session["provider"] = parts[1]; provider = get_provider(parts[1])
            print(f"provider={cfg['provider']} key_set={'yes' if key_set(cfg['provider']) else 'no'}"); continue
        if line == "/tools": print(", ".join(TOOL_NAMES)); continue
        if line == "/sessions":
            for s in sess.sessions_table(): print(s)
            continue
        if line.startswith("/sessions "):
            q, fd, td = parse_search_args(line.split(maxsplit=1)[1])
            for h in sess.search_sessions(q, from_date=fd, to_date=td): print(f"{h[0]} provider={h[1]} messages={h[2]} updated={h[3]} snippet={h[4]}")
            continue
        if line.startswith("/search-sessions "):
            q, fd, td = parse_search_args(line.split(maxsplit=1)[1])
            for h in sess.search_sessions(q, from_date=fd, to_date=td): print(f"{h[0]} provider={h[1]} messages={h[2]} updated={h[3]} snippet={h[4]}")
            continue
        if line.startswith("/export"):
            parts = line.split()
            if len(parts) < 2:
                print("usage: /export <id> [md|json]  /export-file <id> [md|json] [path]")
            elif parts[0] == "/export-file":
                try:
                    fmt = parts[2] if len(parts) > 2 else "md"
                    path = parts[3] if len(parts) > 3 else None
                    print(f"exported to {sess.export_session_file(parts[1], fmt, path)}")
                except Exception as e: print(f"export failed: {e}")
            else:
                try:
                    fmt = parts[2] if len(parts) > 2 else "md"
                    print(sess.export_session(parts[1], fmt))
                except Exception as e: print(f"export failed: {e}")
            continue
        if line.startswith("/resume"):
            try:
                s = sess.load(line.split(maxsplit=1)[1]); session.update(s); messages = s["messages"]; session["messages"] = messages
                print(f"resumed {s['id']} ({len(messages)} messages)")
            except Exception as e: print(f"resume failed: {e}")
            continue
        if line == "/clear": messages.clear(); session["messages"] = messages; print("history cleared"); continue
        if line == "/compact":
            new_msgs, dropped = sess.compact_messages(messages, keep=10)
            messages[:] = new_msgs; session["messages"] = messages
            print(f"context compacted: {dropped} messages removed, {len(messages)} kept"); continue
        if line.startswith("/mcp"):
            parts = line.split(maxsplit=1)
            if not mcp_client:
                print("mcp: no servers configured (shadowcode.json mcp.servers, local stdio only)")
            elif len(parts) == 1:
                print(f"mcp servers: {', '.join(mcp_servers)}")
            else:
                try:
                    print(f"mcp tools on {parts[1]}: {mcp_client.list_tools(parts[1])}")
                except Exception as e:
                    print(f"mcp error: {e}")
            continue
        if line == "/permissions": print(f"mode={cfg['permission_mode']} allow={cfg.get('permissions',{}).get('allow')} deny={cfg.get('permissions',{}).get('deny')}"); continue
        if line == "/browser":
            print(browser_panel_text(get_browser, cfg)); continue
        if line == "/browser-watch" or line.startswith("/browser-watch ") or line == "/browser-watch-replay":
            try:
                print(browser_watch_text(get_browser, cfg))
            except Exception as e:
                print(f"browser watch replay failed: {e}")
            continue
        if line == "/health":
            print(health_text(cfg)); continue
        if line.startswith("/health-history"):
            parts = line.split()
            try:
                limit = int(parts[1]) if len(parts) > 1 else 10
            except Exception:
                limit = 10
            print(health_history_text(cfg, limit)); continue
        if line.startswith("/sessions-view"):
            arg = line.split(maxsplit=1)[1] if len(line.split(maxsplit=1)) > 1 else ""
            kind, out = sessions_view_dispatch(arg)
            if kind == "resume":
                try:
                    s = sess.load(out); session.update(s); messages = s["messages"]; session["messages"] = messages
                    print(f"resumed {s['id']} ({len(messages)} messages)")
                except Exception as e:
                    print(f"resume failed: {e}")
            else:
                print(out)
            continue
        if line.startswith("/session-info"):
            parts = line.split(maxsplit=1)
            if len(parts) < 2:
                print("usage: /session-info <id>")
            else:
                try:
                    d = sess.load(parts[1])
                    print(f"id={d.get('id')} provider={d.get('provider')} model={d.get('model') or '(default)'} messages={len(d.get('messages', []))} updated={d.get('updated_at', '')}")
                except Exception as e:
                    print(f"session info failed: {e}")
            continue
        if line == "/doctor": doctor(cfg); continue
        if line.startswith("/go-search "):
            print(go_search_command(line.split(maxsplit=1)[1], tools)); continue
        if line.startswith("!"):
            print(tools.run_shell(line[1:])); continue
        # normal prompt
        messages.append({"role": "user", "content": line})
        out = run_agent(provider, tools, cfg, messages, confirm_fn=confirm,
                        on_token=stream_cb if cfg.get("stream", True) else None)
        if cfg.get("stream", True):
            print()
        else:
            print(out)
        sess.save(session); last_session_file().write_text(sid)
    sess.save(session)
    if browser: browser.close()
    if mcp_client: mcp_client.close()
    print(f"session saved: {sid}  (resume: shadowcode --resume {sid})")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
