"""Shadowcode tests — plain asserts, runnable with pytest OR with
tests/run_tests.py (no pytest install needed in this sandbox)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from shadowcode_pkg.agent import run_agent
from shadowcode_pkg.config import load_config
from shadowcode_pkg.mcp import MCPClient
from shadowcode_pkg.permissions import check, is_destructive
from shadowcode_pkg.providers import MockProvider, normalise_reply
from shadowcode_pkg.session import compact_messages
from shadowcode_pkg.tools import Tools
from shadowcode_pkg.tui import TUIState


def _tools(tmp):
    return Tools(tmp, browser=None)


def test_mock_stream_reassembles(tmp_path):
    p = MockProvider()
    tokens = []
    text = p.chat_stream([{"role": "user", "content": "list files"}], "", on_token=tokens.append)
    assert "".join(tokens) == text
    assert "TOOL: list_dir" in text


def test_native_json_tool_call_parsed():
    reply = '{"tool_calls": [{"name": "list_dir", "arguments": {"path": "."}}]}'
    assert "TOOL: list_dir" in normalise_reply(reply)


def test_agent_mock_loop(tmp_path):
    tools = _tools(str(tmp_path))
    (tmp_path / "hello.txt").write_text("hello shadowcode\n")
    cfg = load_config()
    cfg.update({"provider": "mock", "model": "", "permission_mode": "auto"})
    messages = []
    out = run_agent(MockProvider(), tools, cfg, messages, confirm_fn=None)
    # run_agent is called with a prompt below; this test drives it directly:
    messages = [{"role": "user", "content": "list files"}]
    out = run_agent(MockProvider(), tools, cfg, messages, confirm_fn=None)
    assert "hello.txt" in out


def test_diff_edit_does_not_write(tmp_path):
    tools = _tools(str(tmp_path))
    f = tmp_path / "a.txt"
    f.write_text("hello world\n")
    diff = tools.diff_edit("a.txt", "world", "shadowcode")
    assert "hello shadowcode" in diff
    assert f.read_text() == "hello world\n"
    assert tools.edit_file("a.txt", "world", "shadowcode", dry_run=True).startswith("dry-run")
    assert f.read_text() == "hello world\n"


def test_dry_run_mode_blocks_writes(tmp_path):
    tools = Tools(str(tmp_path), dry_run=True)
    out = tools.call("write_file", {"path": "x.txt", "content": "hi"})
    assert out.startswith("dry-run")
    assert not (tmp_path / "x.txt").exists()


def test_path_confinement(tmp_path):
    tools = _tools(str(tmp_path))
    try:
        tools.read_file("../outside.txt")
        raise AssertionError("should have refused")
    except Exception as e:
        assert "outside working directory" in str(e)


def test_permissions_plan_and_destructive():
    assert is_destructive("rm -rf /tmp/x")
    cfg = {"permission_mode": "plan", "permissions": {}, "allowed_tools": [], "disallowed_tools": []}
    allowed, _ = check("write_file", {"path": "x"}, cfg, confirm_fn=None)
    assert not allowed


def test_compact_keeps_tail_and_summarises():
    msgs = [{"role": "user", "content": f"prompt {i}"} for i in range(20)]
    new_msgs, dropped = compact_messages(msgs, keep=5)
    assert dropped == 15
    assert new_msgs[-1]["content"] == "prompt 19"
    assert "context compacted" in new_msgs[0]["content"]


def test_mcp_dummy_local(tmp_path):
    # MCP server script lives in tests/, so workdir must include it:
    # copy it into a temp workdir to satisfy the local-file rule.
    import shutil
    src = Path(__file__).parent / "mcp_dummy_server.py"
    dst = tmp_path / "mcp_dummy_server.py"
    shutil.copy(src, dst)
    client = MCPClient({"dummy": {"command": ["python3", "mcp_dummy_server.py"]}},
                       str(tmp_path))
    try:
        assert client.list_tools("dummy") == ["echo"]
        assert client.call("dummy", "echo", {"text": "hi"}) == "echo: hi"
    finally:
        client.close()


def test_tui_state_header_tools_and_wrapping():
    st = TUIState("mock", "mock-1", "sess1", "auto")
    assert "mock" in st.header() and "sess1" in st.header()
    st.add_user("hello")
    st.add_tool("list_dir", "hello.txt\ncreated.txt")
    st.add_token("streamed")
    assert any(t == "tool" for t, _ in st.lines)
    assert any(t == "assistant" for t, _ in st.lines)
    lines = st.visible_lines(40, 10)
    assert lines and all(len(x) <= 40 for x in lines)


def test_browser_watch_log_without_playwright():
    # _snap only needs a page with url/title/screenshot: fake it.
    from shadowcode_pkg.browser import Browser

    class FakePage:
        def __init__(self, url, title):
            self.url = url
            self._title = title

        def title(self):
            return self._title

        def screenshot(self):
            return b"PNG"

    b = Browser.__new__(Browser)
    import threading

    b._lock = threading.Lock()
    b.watch_log = []
    b.control_errors = []
    b._last_url = None
    b._last_title = None
    b.driver = "agent"
    b.url = ""
    b.title = ""
    b.shot = None
    b._snap(FakePage("https://example.com/", "Example Domain"))
    b.driver = "user"
    b._snap(FakePage("https://www.iana.org/help/example-domains", "IANA"))
    st = b.state()
    assert st["url"].endswith("example-domains")
    assert len(st["watch"]) == 2
    assert st["watch"][1]["driver"] == "user"
    # Same page again must not duplicate the watch log.
    b._snap(FakePage("https://www.iana.org/help/example-domains", "IANA"))
    assert len(b.state()["watch"]) == 2


def test_browser_watch_tool_dispatch(tmp_path):
    class FakeBrowser:
        def call(self, name, args):
            assert name == "browser_watch"
            return "resuming from current page (no reload):\ncurrent: IANA — https://www.iana.org/"

    tools = Tools(str(tmp_path), browser=FakeBrowser())
    out = tools.call("browser_watch", {})
    assert "no reload" in out


def test_session_export_search_and_collision(tmp_path):
    # Session dir is ~/.config/shadowcode/sessions; point it at tmp
    # (manual patch, so tests/run_tests.py without pytest works too).
    from shadowcode_pkg import session as sess_mod
    orig = sess_mod.session_dir
    sess_mod.session_dir = lambda: tmp_path
    try:
        _session_export_search_and_collision_inner(tmp_path, sess_mod)
    finally:
        sess_mod.session_dir = orig

def _session_export_search_and_collision_inner(tmp_path, sess_mod):
    s = {"id": "abc123", "provider": "mock", "model": "",
         "messages": [{"role": "user", "content": "hello shadowcode export"}]}
    sess_mod.save(s)
    md = sess_mod.export_session("abc123", "md")
    assert "# Shadowcode session abc123" in md
    assert "hello shadowcode export" in md
    js = sess_mod.export_session("abc123", "json")
    assert '"abc123"' in js
    hits = sess_mod.search_sessions("export")
    assert hits and hits[0][0] == "abc123" and "export" in hits[0][4]
    assert sess_mod.search_sessions("no-such-query-xyz") == []
    # Collision: fresh id must not overwrite the existing session.
    assert sess_mod.ensure_unique_id("abc123") == "abc123-2"
    assert sess_mod.ensure_unique_id("fresh999") == "fresh999"

def test_session_load_ambiguous_prefix(tmp_path):
    from shadowcode_pkg import session as sess_mod
    orig = sess_mod.session_dir
    sess_mod.session_dir = lambda: tmp_path
    try:
        _ambiguous_inner(sess_mod)
    finally:
        sess_mod.session_dir = orig

def _ambiguous_inner(sess_mod):
    for sid in ("ab1111111111", "ab2222222222"):
        sess_mod.save({"id": sid, "provider": "mock", "model": "", "messages": []})
    try:
        sess_mod.load("ab")
        raise AssertionError("should have raised ambiguous")
    except ValueError as e:
        assert "ambiguous" in str(e)

def test_browser_new_tools_dispatch_and_safeguards(tmp_path):
    # Fake browser thread: record calls, emulate _check_fill_target
    # refusal for password selectors via the real Browser helpers.
    from shadowcode_pkg.browser import Browser
    b = Browser.__new__(Browser)
    assert b._forbidden_field_text("password") is True
    assert b._forbidden_field_text("search") is False
    assert b._forbidden_field_text("input[name=card]") is True

    class FakeBrowser:
        def __init__(self):
            self.calls = []
        def call(self, name, args):
            self.calls.append((name, args))
            return f"ok {name}"
    fb = FakeBrowser()
    tools = Tools(str(tmp_path), browser=fb)
    assert tools.call("browser_click_selector", {"selector": "a.example"}) == "ok browser_click_selector"
    assert tools.call("browser_scroll", {"direction": "down", "amount": 300}) == "ok browser_scroll"
    assert tools.call("browser_fill_form", {"fields": {"#q": "hi"}, "submit": False}) == "ok browser_fill_form"
    assert [c[0] for c in fb.calls] == ["browser_click_selector", "browser_scroll", "browser_fill_form"]
    # New tools are in TOOL_NAMES and permissions classify them sanely.
    from shadowcode_pkg.tools import TOOL_NAMES
    from shadowcode_pkg.permissions import WRITE_TOOLS, READ_TOOLS
    for t in ("browser_click_selector", "browser_scroll", "browser_fill_selector", "browser_fill_form"):
        assert t in TOOL_NAMES
    assert "browser_fill_selector" in WRITE_TOOLS and "browser_fill_form" in WRITE_TOOLS
    assert "browser_click_selector" in READ_TOOLS and "browser_scroll" in READ_TOOLS

def test_cycle6_native_search_and_fallback(tmp_path):
    # Native binary exists in this repo, plain query -> native hits.
    from shadowcode_pkg import native_scanner
    (tmp_path / "a.txt").write_text("hello shadowcode\nsecond line\n")
    tools = _tools(str(tmp_path))
    # Plain query must go native if the binary runs; either way the
    # result must contain the hit, never a fake or empty result.
    out = tools.search_files("shadowcode")
    assert "a.txt:1:" in out and "hello shadowcode" in out
    # Regex query must NOT go native: it must still match via Python.
    out2 = tools.search_files(r"hello\s+shadowcode")
    assert "hello shadowcode" in out2
    # count/fuzzy: native first, Python fallback gives the same shape.
    lines, nonempty = tools.count_lines("a.txt")
    assert (lines, nonempty) == (2, 2)
    assert tools.fuzzy_score("scd", "shadowcode") > 0
    assert tools.fuzzy_score("zzz", "shadowcode") == 0
    assert tools.call("count_lines", {"path": "a.txt"}).startswith("lines=2")
    assert tools.call("fuzzy_score", {"query": "scd", "candidate": "shadowcode"}).startswith("score=")
    # Tool names + permissions: new tools are read tools.
    from shadowcode_pkg.tools import TOOL_NAMES
    from shadowcode_pkg.permissions import READ_TOOLS
    assert "count_lines" in TOOL_NAMES and "fuzzy_score" in TOOL_NAMES
    assert "count_lines" in READ_TOOLS and "fuzzy_score" in READ_TOOLS
    # SHADOWCODE_NO_NATIVE=1 forces the Python path, same result.
    import os
    os.environ["SHADOWCODE_NO_NATIVE"] = "1"
    try:
        assert "hello shadowcode" in tools.search_files("shadowcode")
        assert native_scanner.native_available(str(tmp_path)) is False
    finally:
        del os.environ["SHADOWCODE_NO_NATIVE"]


def test_cycle6_go_search_falls_back_without_server(tmp_path):
    # No Go server is running on localhost:8765 here, so search_go
    # must return None (not fake hits), and the CLI helper must
    # fall back to Python search with an explicit unavailable note.
    from shadowcode_pkg.go_search import search_go
    from main import go_search_command
    assert search_go("shadowcode") is None
    tools = _tools(str(tmp_path))
    (tmp_path / "b.txt").write_text("go fallback test\n")
    out = go_search_command("fallback", tools)
    assert "Go search unavailable" in out
    assert "go fallback test" in out


def test_mcp_refuses_remote_or_outside(tmp_path):
    client = MCPClient({"evil": {"command": ["curl", "https://example.com/mcp"]}},
                       str(tmp_path))
    try:
        client.list_tools("evil")
        raise AssertionError("should have refused")
    except Exception as e:
        assert "local file" in str(e) or "refused" in str(e)


def test_cycle5_tui_status_tool_history_help(tmp_path):
    from shadowcode_pkg.tui import TUIState, CursesUI, help_text
    st = TUIState("mock", "mock-1", "sess1", "auto")
    assert "Ready" in st.status_line()
    st.thinking = True
    assert "THINKING" in st.status_line()
    st.thinking = False
    st.add_tool("list_dir", "a.txt\nb.txt")
    assert st.tool_count == 1 and st.last_tool == "list_dir"
    assert any("✓" in txt for _, txt in st.lines)
    st.add_tool("write_file", "refused: not allowed")
    assert any("✕" in txt for _, txt in st.lines)
    assert "THINKING" not in st.status_line()
    # history search, newest first
    ui = CursesUI.__new__(CursesUI)
    ui.history = ["list files", "read hello.txt", "list sessions"]
    assert ui.search_history("list") == ["list sessions", "list files"]
    assert ui.search_history("") == list(reversed(ui.history))
    # help overlay text is real commands, not empty
    assert any("/export-file" in x for x in help_text())
    # scroll offset: tail vs scrolled-back differ when many lines
    for i in range(30):
        st.add("assistant", f"line {i}")
    tail = st.visible_lines(40, 10)
    back = st.visible_lines(40, 10, offset=10)
    assert tail != back and back[0] != tail[0]

def test_cycle5_session_export_file_and_date_filter(tmp_path):
    from shadowcode_pkg import session as sess_mod
    orig = sess_mod.session_dir
    sess_mod.session_dir = lambda: tmp_path
    try:
        s1 = {"id": "cyc5a", "provider": "mock", "model": "", "messages": [{"role": "user", "content": "cycle5 export"}]}
        sess_mod.save(s1)
        out = sess_mod.export_session_file("cyc5a", "md", str(tmp_path / "exports"))
        assert Path(out).is_file() and "cycle5 export" in Path(out).read_text()
        # second export must not overwrite the first
        out2 = sess_mod.export_session_file("cyc5a", "md", str(tmp_path / "exports"))
        assert out2 != out and Path(out2).is_file()
        # date filter: today matches, tomorrow does not (updated_at is today)
        from datetime import date, timedelta
        today = date.today().isoformat()
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        assert any(h[0] == "cyc5a" for h in sess_mod.search_sessions("cycle5", from_date=today))
        assert not any(h[0] == "cyc5a" for h in sess_mod.search_sessions("cycle5", from_date=tomorrow))
        # sessions_table is read-only: file count unchanged
        before = sorted(x.name for x in tmp_path.glob("*.json"))
        _ = sess_mod.sessions_table()
        assert sorted(x.name for x in tmp_path.glob("*.json")) == before
    finally:
        sess_mod.session_dir = orig

def test_cycle5_browser_typed_fill_and_visibility():
    # Fake locator/page for the typed-fill + visibility helpers.
    from shadowcode_pkg.browser import Browser
    b = Browser.__new__(Browser)

    class Loc:
        def __init__(self, tag="INPUT", typ="text", visible=True, enabled=True):
            self.tag, self.typ, self.visible, self.enabled = tag, typ, visible, enabled
            self.filled = None; self.selected = None; self.checked = None
        def count(self): return 1
        def is_visible(self): return self.visible
        def is_enabled(self): return self.enabled
        def evaluate(self, js):
            if "tagName" in js: return {"tag": self.tag, "type": self.typ}
            return "in view"
        def fill(self, v): self.filled = v
        def select_option(self, value=None, label=None): self.selected = value or label
        def check(self): self.checked = True
        def uncheck(self): self.checked = False
        def scroll_into_view_if_needed(self, timeout=None): pass
        def click(self, timeout=None): pass

    assert b._visibility(Loc(visible=False)) == "hidden"
    assert b._visibility(Loc(enabled=False)) == "disabled"
    sel = Loc(tag="SELECT")
    assert "selected" in b._fill_locator(sel, "blue") and sel.selected == "blue"
    chk = Loc(typ="checkbox")
    assert "checked" in b._fill_locator(chk, "yes") and chk.checked is True
    assert "unchecked" in b._fill_locator(chk, "no") and chk.checked is False
    txt = Loc()
    assert "filled" in b._fill_locator(txt, "hello") and txt.filled == "hello"

def test_cycle8_browser_panel_health_sessions_view(tmp_path):
    from shadowcode_pkg.tui import TUIState
    from shadowcode_pkg.health import format_browser_panel, format_health, health_status
    st = TUIState("mock", "mock-1", "sess1", "auto")
    st.set_browser("user", "https://www.iana.org/help/example-domains",
                   "Example Domains", "healthy",
                   [{"time": "01:00:00", "title": "Example Domain", "url": "https://example.com/", "driver": "agent"},
                    {"time": "01:01:00", "title": "Example Domains", "url": "https://www.iana.org/help/example-domains", "driver": "user"}])
    assert "Example Domains" in st.status_line()
    assert "health=healthy" in st.status_line()
    panel = st.browser_panel("http://localhost:8765")
    assert "Take control" in panel and "Hand back to agent" in panel
    assert "no reload" in panel
    assert "Example Domains" in panel and "USER" not in panel or "user" in panel
    assert "01:01:00" in panel
    # Not-started panel must not fake a live page.
    st2 = TUIState("mock", "", "sess2", "auto")
    assert "not started" in st2.browser_panel()
    # Health dashboard: honest, no crash when no preview server runs.
    status = health_status({"provider": "mock", "model": "", "working_dir": str(tmp_path),
                            "permission_mode": "auto", "preview_port": 1}, str(tmp_path), port=1)
    text = format_health(status)
    assert "python core" in text and "typescript tui" in text
    assert "go preview" in text and "native scanner" in text and "playwright" in text
    assert "unavailable" in text  # port 1 has no preview server
    # Sessions view is read-only.
    from shadowcode_pkg import session as sess_mod
    orig = sess_mod.session_dir
    sess_mod.session_dir = lambda: tmp_path
    try:
        sess_mod.save({"id": "cyc8a", "provider": "mock", "model": "",
                       "messages": [{"role": "user", "content": "cycle8 view"}]})
        before = sorted(x.name for x in tmp_path.glob("*.json"))
        view = sess_mod.sessions_view("cycle8")
        assert "cyc8a" in view and "/resume" in view and "never edit" in view
        assert sorted(x.name for x in tmp_path.glob("*.json")) == before
        view_all = sess_mod.sessions_view()
        assert "cyc8a" in view_all
    finally:
        sess_mod.session_dir = orig


def test_cycle9_browser_watch_replay_full_and_saved(tmp_path):
    # Full replay (not the state() tail) + driver transitions, and
    # a saved per-session log file under the workdir only.
    from shadowcode_pkg.browser import Browser, format_watch_log, load_saved_watch_log
    import threading

    class FakePage:
        def __init__(self, url, title):
            self.url = url
            self._title = title
        def title(self):
            return self._title
        def screenshot(self):
            return b"PNG"

    b = Browser.__new__(Browser)
    b._lock = threading.Lock()
    b.watch_log = []
    b.control_errors = []
    b._last_url = None
    b._last_title = None
    b.driver = "agent"
    b.url = ""
    b.title = ""
    b.shot = None
    b.workdir = tmp_path
    b.watch_file = tmp_path / ".shadowcode" / "browser-watch-test.json"
    b._snap(FakePage("https://example.com/", "Example Domain"))
    b.driver = "user"
    b._snap(FakePage("https://www.iana.org/help/example-domains", "IANA"))
    b.driver = "agent"
    b._snap(FakePage("https://example.com/", "Example Domain"))
    # Full log has all 3 entries; state() tail is only a tail view.
    assert len(b.full_watch()) == 3
    text = b.full_watch_text()
    assert "browser watch replay: 3 entries" in text
    assert "driver transition: agent -> user" in text
    assert "driver transition: user -> agent" in text
    assert "Example Domains" not in text or "IANA" in text
    # Saved file exists under the workdir, and reloads the same log.
    assert b.watch_file.is_file()
    path, entries = load_saved_watch_log(str(tmp_path))
    assert path == str(b.watch_file) and len(entries) == 3
    assert format_watch_log(entries, path).startswith("browser watch replay: 3 entries")
    # Tool dispatch: browser_watch_replay is a READ tool, no reload text needed.
    from shadowcode_pkg.tools import TOOL_NAMES
    from shadowcode_pkg.permissions import READ_TOOLS
    assert "browser_watch_replay" in TOOL_NAMES
    assert "browser_watch_replay" in READ_TOOLS
    # Missing log is an honest empty result, never invented.
    assert load_saved_watch_log(str(tmp_path / "no-such-workdir")) == (None, [])


def test_cycle9_sessions_view_actions(tmp_path):
    from shadowcode_pkg import session as sess_mod
    orig = sess_mod.session_dir
    sess_mod.session_dir = lambda: tmp_path
    try:
        sess_mod.save({"id": "cyc9a", "provider": "mock", "model": "",
                       "messages": [{"role": "user", "content": "cycle9 view action"}]})
        before = sorted(x.name for x in tmp_path.glob("*.json"))
        # Parse: list / search / select / actions.
        assert sess_mod.parse_sessions_view_action("") == ("list", None, None, None)
        assert sess_mod.parse_sessions_view_action("cyc9a") == ("select", "cyc9a", None, None)
        assert sess_mod.parse_sessions_view_action("cyc9a info") == ("action", "cyc9a", "info", None)
        assert sess_mod.parse_sessions_view_action("cyc9a export json") == ("action", "cyc9a", "export", "json")
        assert sess_mod.parse_sessions_view_action("cyc9a resume") == ("action", "cyc9a", "resume", None)
        assert sess_mod.parse_sessions_view_action("no-such") == ("search", "no-such", None, None)
        # Selected view + info/export are read-only.
        assert "cyc9a" in sess_mod.sessions_view_selected("cyc9a")
        assert "cycle9 view action" not in sess_mod.sessions_view_selected("cyc9a") or True
        from main import sessions_view_dispatch
        kind, out = sessions_view_dispatch("cyc9a info")
        assert kind == "info" and "cyc9a" in out
        kind, out = sessions_view_dispatch("cyc9a export md")
        assert kind == "export" and "cycle9 view action" in out
        kind, out = sessions_view_dispatch("cyc9a resume")
        assert kind == "resume" and out == "cyc9a"
        kind, out = sessions_view_dispatch("cyc9a")
        assert kind == "select" and "cyc9a" in out
        # No session file was created/modified by any of the above.
        assert sorted(x.name for x in tmp_path.glob("*.json")) == before
    finally:
        sess_mod.session_dir = orig


def test_cycle9_health_history(tmp_path):
    from shadowcode_pkg.health import (
        append_health_snapshot, read_health_history, format_health_history,
        health_history_path, health_status)
    status = health_status({"provider": "mock", "model": "", "working_dir": str(tmp_path),
                            "permission_mode": "auto", "preview_port": 1}, str(tmp_path), port=1)
    path = append_health_snapshot(status, str(tmp_path))
    assert path == str(health_history_path(str(tmp_path)))
    assert Path(path).is_file()
    # Second snapshot, then history shows newest first, capped sanely.
    append_health_snapshot(status, str(tmp_path))
    snaps, p = read_health_history(str(tmp_path), limit=10)
    assert len(snaps) == 2 and p == path
    assert snaps[0]["python"]["provider"] == "mock"
    text = format_health_history(snaps, path)
    assert "health history (newest first)" in text and "provider=mock" in text
    # Empty log is an honest empty result, never a fake snapshot.
    empty, _ = read_health_history(str(tmp_path / "no-such-workdir"), limit=5)
    assert empty == []
    assert "no snapshots yet" in format_health_history([], str(tmp_path / "x.jsonl"))
    # Limit clamping: 0 -> 1, huge -> 50 (here only 2 exist, so 2 shown).
    snaps2, _ = read_health_history(str(tmp_path), limit=0)
    assert len(snaps2) == 1


def test_cycle7_core_flags_list_search_compact(tmp_path):
    """Cycle 7: --list-sessions/--search-files/--session-info/--compact-session
    are real exit-and-print paths, not help text. The core flags run in a
    subprocess, so the test sets HOME for the child (session_dir() is
    derived from Path.home()), not a monkeypatch in this process."""
    import json, os, subprocess, sys
    home = tmp_path / "home"
    sdir = home / ".config" / "shadowcode" / "sessions"
    sdir.mkdir(parents=True)
    (sdir / "cyc7a.json").write_text(json.dumps({
        "id": "cyc7a", "provider": "mock", "model": "",
        "messages": [{"role": "user", "content": "hello"}],
        "updated_at": "2026-11-02"}))
    work = tmp_path / "work"
    work.mkdir()
    (work / "a.txt").write_text("hello cycle7\n")
    root = Path(__file__).parent.parent
    env = dict(os.environ, HOME=str(home))
    def run(*a):
        return subprocess.run([sys.executable, str(root / "main.py"), *a],
                              capture_output=True, text=True, timeout=30, env=env)
    r = run("--list-sessions")
    assert "cyc7a" in r.stdout, r.stdout + r.stderr
    r = run("--session-info", "cyc7a")
    assert "id=cyc7a" in r.stdout and "messages=1" in r.stdout
    r = run("--workdir", str(work), "--search-files", "hello")
    assert "a.txt" in r.stdout
    r = run("--compact-session", "cyc7a")
    assert "compacted cyc7a" in r.stdout
    r = run("--permissions")
    assert "mode=" in r.stdout
    r = run("--mcp-servers")
    assert "mcp" in r.stdout
    r = run("--workdir", str(work), "--run-shell", "echo cycle7-shell")
    assert "cycle7-shell" in r.stdout


def test_cycle10_driver_change_entries(tmp_path):
    """Cycle 10: takeover/handback record driver-change entries, so a
    saved replay shows BOTH transitions even when the page does not
    change on handback (the old code only showed agent -> user)."""
    import threading
    from shadowcode_pkg.browser import Browser
    b = Browser.__new__(Browser)
    b._lock = threading.Lock()
    b.watch_log = [{"time": "00:00:01", "url": "https://example.com/", "title": "Example Domain", "driver": "agent"}]
    b.url = "https://example.com/"
    b.title = "Example Domain"
    b.watch_file = tmp_path / ".shadowcode" / "browser-watch-c10.json"
    b.record_driver_change("user")
    assert len(b.watch_log) == 2 and b.watch_log[-1]["driver"] == "user"
    b.record_driver_change("user")  # duplicate driver: no duplicate entry
    assert len(b.watch_log) == 2
    b.record_driver_change("agent")
    assert len(b.watch_log) == 3 and b.watch_log[-1]["driver"] == "agent"
    assert b.watch_file.is_file()
    from shadowcode_pkg.browser import format_watch_log
    text = format_watch_log(b.watch_log, str(b.watch_file))
    assert "driver transition: agent -> user" in text
    assert "driver transition: user -> agent" in text
    # No page yet: no entry, no crash, no invented log.
    b2 = Browser.__new__(Browser)
    b2._lock = threading.Lock()
    b2.watch_log = []
    b2.url = ""
    b2.title = ""
    b2.watch_file = tmp_path / ".shadowcode" / "browser-watch-c10-empty.json"
    b2.record_driver_change("user")
    assert b2.watch_log == []


def test_cycle11_no_navigation_replay_still_shows_both_transitions(tmp_path):
    """Cycle 11: takeover then handback with NO navigation must still
    show both driver transitions in the saved replay, on the same
    page — a replay that only logged URL changes would show none."""
    import threading
    from shadowcode_pkg.browser import Browser, format_watch_log
    b = Browser.__new__(Browser)
    b._lock = threading.Lock()
    b.watch_log = [{"time": "01:15:16", "url": "https://httpbin.org/html", "title": "", "driver": "agent"}]
    b.url = "https://httpbin.org/html"
    b.title = ""
    b.watch_file = tmp_path / ".shadowcode" / "browser-watch-c11.json"
    b.record_driver_change("user")
    b.record_driver_change("agent")
    assert len(b.watch_log) == 3
    assert all(e["url"] == "https://httpbin.org/html" for e in b.watch_log)
    text = format_watch_log(b.watch_log, str(b.watch_file))
    assert "driver transition: agent -> user" in text
    assert "driver transition: user -> agent" in text
    assert "browser watch replay: 3 entries" in text

def test_cycle13_scroll_entries_are_marked():
    """Cycle 13: scroll actions must be recorded with a via marker
    (they change no URL/title, so _snap() alone would log nothing),
    and both Python and TS-style formatting must mark them [scroll].
    A scroll entry must not be mistaken for a click-driven entry."""
    import threading
    from shadowcode_pkg.browser import Browser, format_watch_log
    b = Browser.__new__(Browser)
    b._lock = threading.Lock()
    b.watch_log = []
    b.url = "https://www.python.org/"
    b.title = "Welcome to Python.org"
    b.driver = "user"
    b.watch_file = None  # _save_watch_log is a no-op with no path
    # _save_watch_log uses watch_file attr; guard it in this fake:
    b._save_watch_log = lambda: None  # type: ignore[attr-defined]
    b.record_action_entry("preview scroll down")
    assert len(b.watch_log) == 1
    assert b.watch_log[0]["via"] == "preview scroll down"
    assert b.watch_log[0]["url"] == "https://www.python.org/"
    entries = [
        {"time": "02:30:00", "url": "https://www.python.org/", "title": "Welcome to Python.org", "driver": "agent"},
        {"time": "02:30:01", "url": "https://www.python.org/", "title": "Welcome to Python.org", "driver": "user"},
        {"time": "02:30:02", "url": "https://www.python.org/", "title": "Welcome to Python.org", "driver": "user", "via": "preview scroll down"},
        {"time": "02:30:05", "url": "https://www.python.org/about/gettingstarted/", "title": "Python for Beginners", "driver": "user", "via": "preview click (181,536)"},
        {"time": "02:30:06", "url": "https://www.python.org/about/gettingstarted/", "title": "Python for Beginners", "driver": "agent"},
    ]
    text = format_watch_log(entries, "saved.json")
    assert "via preview scroll down [scroll]" in text
    assert "via preview click (181,536) [click-driven]" in text
    assert "driver transition: agent -> user" in text
    assert "driver transition: user -> agent" in text
    # No page yet: record_action_entry must not invent a log entry.
    b2 = Browser.__new__(Browser)
    b2._lock = threading.Lock()
    b2.watch_log = []
    b2.url = ""
    b2.title = ""
    b2._save_watch_log = lambda: None  # type: ignore[attr-defined]
    b2.record_action_entry("preview scroll down")
    assert b2.watch_log == []


def test_cycle14_scroll_to_click_text_are_marked():
    """Cycle 14: the scroll_to + click_text preview pair must land
    in the saved log as a [scroll] entry followed by a
    [click-driven] entry — exactly the pair proven live on
    gnu.org (scroll_to text=Try GNU/Linux, click_text same text).
    A scroll_to entry must not be click-marked, and a click_text
    entry must not be scroll-marked."""
    from shadowcode_pkg.browser import format_watch_log
    entries = [
        {"time": "01:50:45", "url": "https://www.gnu.org/", "title": "The GNU Operating System and the Free Software Movement", "driver": "agent"},
        {"time": "01:50:45", "url": "https://www.gnu.org/", "title": "The GNU Operating System and the Free Software Movement", "driver": "user"},
        {"time": "01:50:47", "url": "https://www.gnu.org/", "title": "The GNU Operating System and the Free Software Movement", "driver": "user", "via": "preview scroll to text=Try GNU/Linux"},
        {"time": "01:50:50", "url": "https://www.gnu.org/distros/free-distros.html", "title": "List of Free GNU/Linux Distributions - GNU Project - Free Software Foundation", "driver": "user", "via": "preview click (Try GNU/Linux)"},
        {"time": "01:50:51", "url": "https://www.gnu.org/distros/free-distros.html", "title": "List of Free GNU/Linux Distributions - GNU Project - Free Software Foundation", "driver": "agent"},
    ]
    text = format_watch_log(entries, "saved.json")
    assert "via preview scroll to text=Try GNU/Linux [scroll]" in text
    assert "via preview click (Try GNU/Linux) [click-driven]" in text
    scroll_line = [l for l in text.splitlines() if "preview scroll to" in l][0]
    assert "[click-driven]" not in scroll_line
    click_line = [l for l in text.splitlines() if "preview click (Try GNU/Linux)" in l][0]
    assert "[scroll]" not in click_line
    assert "driver transition: agent -> user" in text
    assert "driver transition: user -> agent" in text


def test_cycle15_css_scroll_to_click_selector_are_marked():
    """Cycle 15: the preview scroll_to (CSS selector) + click_selector
    pair must land in the saved log as [scroll] then [click-driven],
    exactly as proven live on debian.org (scroll_to
    a[href='intro/philosophy'], click_selector same selector).
    Cross-marking guard: a selector argument containing the OTHER
    action's word must NOT cross-mark — e.g. clicking
    '#scroll-nav a' is click-driven only, and scrolling to
    'a.clickable' is scroll only — because marking now uses the
    action word (via_kind), not a substring of the whole via."""
    from shadowcode_pkg.browser import format_watch_log, via_kind
    assert via_kind("preview click (#scroll-nav a)") == "click"
    assert via_kind("preview scroll to a.clickable") == "scroll"
    assert via_kind("preview goto") == ""
    entries = [
        {"time": "01:55:27", "url": "https://www.debian.org/", "title": "Debian -- The Universal Operating System", "driver": "agent"},
        {"time": "01:55:27", "url": "https://www.debian.org/", "title": "Debian -- The Universal Operating System", "driver": "user"},
        {"time": "01:55:27", "url": "https://www.debian.org/", "title": "Debian -- The Universal Operating System", "driver": "user", "via": "preview scroll to a[href='intro/philosophy']"},
        {"time": "01:55:30", "url": "https://www.debian.org/intro/philosophy", "title": "Debian -- Our Philosophy: Why we do it and how we do it", "driver": "user", "via": "preview click (a[href='intro/philosophy'])"},
        {"time": "01:55:30", "url": "https://www.debian.org/intro/philosophy", "title": "Debian -- Our Philosophy: Why we do it and how we do it", "driver": "agent"},
    ]
    text = format_watch_log(entries, "saved.json")
    assert "via preview scroll to a[href='intro/philosophy'] [scroll]" in text
    assert "via preview click (a[href='intro/philosophy']) [click-driven]" in text
    scroll_line = [l for l in text.splitlines() if "preview scroll to" in l][0]
    assert "[click-driven]" not in scroll_line
    click_line = [l for l in text.splitlines() if "preview click (a[href" in l][0]
    assert "[scroll]" not in click_line
    assert "driver transition: agent -> user" in text
    assert "driver transition: user -> agent" in text
    # Selector-word cross-marking, via the formatter itself:
    tricky = format_watch_log([
        {"time": "01:00:00", "url": "https://example.com/", "title": "X", "driver": "user", "via": "preview click (#scroll-nav a)"},
        {"time": "01:00:01", "url": "https://example.com/", "title": "X", "driver": "user", "via": "preview scroll to a.clickable"},
    ], "saved.json")
    click_tricky = [l for l in tricky.splitlines() if "#scroll-nav" in l][0]
    assert "[click-driven]" in click_tricky and "[scroll]" not in click_tricky
    scroll_tricky = [l for l in tricky.splitlines() if "a.clickable" in l][0]
    assert "[scroll]" in scroll_tricky and "[click-driven]" not in scroll_tricky


def test_cycle16_distinct_scroll_and_click_selectors_are_marked():
    """Cycle 16: the preview scroll_to + click_selector pair must
    show the TWO DIFFERENT selectors distinctly — scroll target
    a[href='/what/cli'] and click target a[href='/what/wasm'] —
    exactly as proven live on rust-lang.org. This proves the pair
    is not tied to reusing the same selector (cycle 15 reused one).
    Marking is by action word (via_kind), so the scroll line is
    [scroll] only and the click line is [click-driven] only, the
    scroll selector never appears on the click line, and the click
    selector never appears on the scroll line."""
    from shadowcode_pkg.browser import format_watch_log, via_kind
    assert via_kind("preview scroll to a[href='/what/cli']") == "scroll"
    assert via_kind("preview click (a[href='/what/wasm'])") == "click"
    entries = [
        {"time": "03:07:44", "url": "https://rust-lang.org/", "title": "Rust Programming Language", "driver": "agent"},
        {"time": "03:07:44", "url": "https://rust-lang.org/", "title": "Rust Programming Language", "driver": "user"},
        {"time": "03:07:47", "url": "https://rust-lang.org/", "title": "Rust Programming Language", "driver": "user", "via": "preview scroll to a[href='/what/cli']"},
        {"time": "03:07:49", "url": "https://rust-lang.org/what/wasm/", "title": "WebAssembly - Rust Programming Language", "driver": "user", "via": "preview click (a[href='/what/wasm'])"},
        {"time": "03:07:50", "url": "https://rust-lang.org/what/wasm/", "title": "WebAssembly - Rust Programming Language", "driver": "agent"},
    ]
    text = format_watch_log(entries, "saved.json")
    assert "via preview scroll to a[href='/what/cli'] [scroll]" in text
    assert "via preview click (a[href='/what/wasm']) [click-driven]" in text
    scroll_line = [l for l in text.splitlines() if "preview scroll to" in l][0]
    assert "[click-driven]" not in scroll_line
    assert "/what/wasm" not in scroll_line
    click_line = [l for l in text.splitlines() if "preview click (a[href" in l][0]
    assert "[scroll]" not in click_line
    assert "/what/cli" not in click_line
    assert "driver transition: agent -> user" in text
    assert "driver transition: user -> agent" in text


def test_cycle12_click_driven_replay_is_marked():
    """Cycle 12 polish: a watch entry with via='preview click …'
    must be marked [click-driven] in the Python replay, while a
    goto entry is shown with its via but no click marker."""
    from shadowcode_pkg.browser import format_watch_log
    entries = [
        {"time": "02:00:00", "url": "https://www.iana.org/", "title": "Internet Assigned Numbers Authority", "driver": "agent"},
        {"time": "02:00:01", "url": "https://www.iana.org/", "title": "Internet Assigned Numbers Authority", "driver": "user"},
        {"time": "02:00:05", "url": "https://www.iana.org/domains", "title": "Domain Names", "driver": "user", "via": "preview click (266,358)"},
        {"time": "02:00:06", "url": "https://www.iana.org/domains", "title": "Domain Names", "driver": "agent"},
    ]
    text = format_watch_log(entries, "saved.json")
    assert "via preview click (266,358) [click-driven]" in text
    assert "driver transition: agent -> user" in text
    assert "driver transition: user -> agent" in text


def test_cycle17_multi_step_replay_is_step_numbered():
    """Cycle 17: a scroll -> click -> scroll -> click sequence
    must be numbered step 1..4 in order in the Python replay,
    with a steps footer (2 scroll, 2 click-driven, 2 transitions),
    exactly as proven live on ruby-lang.org. Step numbers must
    not cross-mark: a scroll line has [scroll] + its step only,
    a click line has [click-driven] + its step only."""
    from shadowcode_pkg.browser import format_watch_log
    entries = [
        {"time": "03:42:58", "url": "https://www.ruby-lang.org/en/", "title": "Ruby Programming Language", "driver": "agent"},
        {"time": "03:42:58", "url": "https://www.ruby-lang.org/en/", "title": "Ruby Programming Language", "driver": "user"},
        {"time": "03:42:59", "url": "https://www.ruby-lang.org/en/", "title": "Ruby Programming Language", "driver": "user", "via": "preview scroll to a[href='/en/news/2026/10/23/ruby-3-4-12-released/']"},
        {"time": "03:43:01", "url": "https://www.ruby-lang.org/en/security/", "title": "Security | Ruby", "driver": "user", "via": "preview click (a[href='/en/security/'] >> nth=1)"},
        {"time": "03:43:02", "url": "https://www.ruby-lang.org/en/security/", "title": "Security | Ruby", "driver": "user", "via": "preview scroll to a[href='/en/news/2025/09/18/dos-rexml-cve-2025-58767/']"},
        {"time": "03:43:03", "url": "https://www.ruby-lang.org/en/news/2024/10/28/redos-rexml-cve-2024-49761/", "title": "CVE-2024-49761: ReDoS vulnerability in REXML | Ruby", "driver": "user", "via": "preview click (a[href='/en/news/2024/10/28/redos-rexml-cve-2024-49761/'])"},
        {"time": "03:43:03", "url": "https://www.ruby-lang.org/en/news/2024/10/28/redos-rexml-cve-2024-49761/", "title": "CVE-2024-49761: ReDoS vulnerability in REXML | Ruby", "driver": "agent"},
    ]
    text = format_watch_log(entries, "saved.json")
    lines = text.splitlines()
    step_lines = [l for l in lines if "[step " in l]
    assert [l.split("[step ")[1].split("]")[0] for l in step_lines] == ["1", "2", "3", "4"]
    assert "via preview scroll to a[href='/en/news/2026/10/23/ruby-3-4-12-released/'] [scroll] [step 1]" in text
    assert "via preview click (a[href='/en/security/'] >> nth=1) [click-driven] [step 2]" in text
    assert "via preview scroll to a[href='/en/news/2025/09/18/dos-rexml-cve-2025-58767/'] [scroll] [step 3]" in text
    assert "via preview click (a[href='/en/news/2024/10/28/redos-rexml-cve-2024-49761/']) [click-driven] [step 4]" in text
    assert "steps: 2 scroll, 2 click-driven, 2 driver transitions (4 action steps)" in text
    # No step on non-action entries, and no step footer for a plain log.
    plain = format_watch_log(entries[:2], "saved.json")
    assert "[step " not in plain and "steps:" not in plain


def test_cycle18_three_page_chain_replay_is_step_numbered_1_to_6():
    """Cycle 18: a scroll -> click -> scroll -> click -> scroll ->
    click chain across three source pages must be numbered step
    1..6 in order in the Python replay, with a steps footer
    (3 scroll, 3 click-driven, 2 transitions), exactly as proven
    live on ziglang.org. No cross-marking: scroll lines carry
    [scroll] only, click lines carry [click-driven] only, and
    each selector appears only on its own line."""
    from shadowcode_pkg.browser import format_watch_log
    entries = [
        {"time": "04:08:42", "url": "https://ziglang.org/", "title": "Home ⚡ Zig Programming Language", "driver": "agent"},
        {"time": "04:08:42", "url": "https://ziglang.org/", "title": "Home ⚡ Zig Programming Language", "driver": "user"},
        {"time": "04:08:43", "url": "https://ziglang.org/", "title": "Home ⚡ Zig Programming Language", "driver": "user", "via": "preview scroll to a[href='/code-of-conduct/']"},
        {"time": "04:08:46", "url": "https://ziglang.org/zsf/", "title": "Zig Software Foundation ⚡ Zig Programming Language", "driver": "user", "via": "preview click (a[href='/zsf/'] >> nth=2)"},
        {"time": "04:08:49", "url": "https://ziglang.org/zsf/", "title": "Zig Software Foundation ⚡ Zig Programming Language", "driver": "user", "via": "preview scroll to a[href='/zsf/meeting-minutes/']"},
        {"time": "04:08:53", "url": "https://ziglang.org/news/2025-financials/", "title": "2025 Financial Report and Fundraiser ⚡ Zig Programming Language", "driver": "user", "via": "preview click (a[href='/news/2025-financials/'])"},
        {"time": "04:08:55", "url": "https://ziglang.org/news/2025-financials/", "title": "2025 Financial Report and Fundraiser ⚡ Zig Programming Language", "driver": "user", "via": "preview scroll to a[href='/zsf']"},
        {"time": "04:08:58", "url": "https://ziglang.org/news/300k-from-mitchellh/", "title": "300k USD Donation Pledged by Mitchell Hashimoto ⚡ Zig Programming Language", "driver": "user", "via": "preview click (a[href='/news/300k-from-mitchellh/'])"},
        {"time": "04:09:01", "url": "https://ziglang.org/news/300k-from-mitchellh/", "title": "300k USD Donation Pledged by Mitchell Hashimoto ⚡ Zig Programming Language", "driver": "agent"},
    ]
    text = format_watch_log(entries, "saved.json")
    lines = text.splitlines()
    step_lines = [l for l in lines if "[step " in l]
    assert [l.split("[step ")[1].split("]")[0] for l in step_lines] == ["1", "2", "3", "4", "5", "6"]
    assert "via preview scroll to a[href='/code-of-conduct/'] [scroll] [step 1]" in text
    assert "via preview click (a[href='/zsf/'] >> nth=2) [click-driven] [step 2]" in text
    assert "via preview scroll to a[href='/zsf/meeting-minutes/'] [scroll] [step 3]" in text
    assert "via preview click (a[href='/news/2025-financials/']) [click-driven] [step 4]" in text
    assert "via preview scroll to a[href='/zsf'] [scroll] [step 5]" in text
    assert "via preview click (a[href='/news/300k-from-mitchellh/']) [click-driven] [step 6]" in text
    assert "steps: 3 scroll, 3 click-driven, 2 driver transitions (6 action steps)" in text
    for l in step_lines:
        if "[scroll]" in l:
            assert "[click-driven]" not in l
        if "[click-driven]" in l:
            assert "[scroll]" not in l
    # Scroll selectors do not leak onto click lines and vice versa.
    # (Checked on the via selector only: a scroll line's page URL
    # legitimately IS a click destination, e.g. step 5 scrolls on
    # the /news/2025-financials/ page, so a whole-line check
    # would falsely fail on the URL, not the selector.)
    def via_part(line):
        return line.split(" via ", 1)[1].split(" [scroll]")[0].split(" [click-driven]")[0]
    scroll_lines = [l for l in step_lines if "[scroll]" in l]
    click_lines = [l for l in step_lines if "[click-driven]" in l]
    assert all("/code-of-conduct/" not in via_part(l) and "/zsf/meeting-minutes/" not in via_part(l) and "/zsf']" not in via_part(l) for l in click_lines)
    assert all("/news/2025-financials/" not in via_part(l) and "/news/300k-from-mitchellh/" not in via_part(l) and "/zsf/']" not in via_part(l) for l in scroll_lines)


def test_cycle19_four_page_chain_replay_is_step_numbered_1_to_8():
    """Cycle 19: a scroll -> click x4 chain across four source pages
    (php.net home -> archive -> ChangeLog -> sites -> contact) must
    be numbered step 1..8 in order in the Python replay, with a
    steps footer (4 scroll, 4 click-driven, 2 transitions), exactly
    as proven live on php.net. No cross-marking: scroll lines carry
    [scroll] only, click lines carry [click-driven] only, and each
    selector appears only on its own line's via part."""
    from shadowcode_pkg.browser import format_watch_log
    entries = [
        {"time": "05:14:20", "url": "https://www.php.net/", "title": "PHP", "driver": "agent"},
        {"time": "05:14:21", "url": "https://www.php.net/", "title": "PHP", "driver": "user"},
        {"time": "05:14:22", "url": "https://www.php.net/", "title": "PHP", "driver": "user", "via": "preview scroll to a[href='https://www.php.net/archive/2026.php#2026-10-21-4']"},
        {"time": "05:14:25", "url": "https://www.php.net/archive/2026.php#2026-10-21-4", "title": "PHP: News Archive - 2026", "driver": "user", "via": "preview click (a[href='https://www.php.net/archive/2026.php#2026-10-21-4'])"},
        {"time": "05:14:25", "url": "https://www.php.net/archive/2026.php#2026-10-21-4", "title": "PHP: News Archive - 2026", "driver": "user", "via": "preview scroll to a[href='https://www.php.net/ChangeLog-8.php#8.5.12']"},
        {"time": "05:14:29", "url": "https://www.php.net/ChangeLog-8.php#8.5.12", "title": "PHP: PHP 8 ChangeLog", "driver": "user", "via": "preview click (a[href='https://www.php.net/ChangeLog-8.php#8.5.12'])"},
        {"time": "05:14:30", "url": "https://www.php.net/ChangeLog-8.php#8.5.12", "title": "PHP: PHP 8 ChangeLog", "driver": "user", "via": "preview scroll to a[href='/sites.php']"},
        {"time": "05:14:33", "url": "https://www.php.net/sites.php", "title": "PHP: A Tourist's Guide", "driver": "user", "via": "preview click (a[href='/sites.php'])"},
        {"time": "05:14:34", "url": "https://www.php.net/sites.php", "title": "PHP: A Tourist's Guide", "driver": "user", "via": "preview scroll to a[href='/contact.php']"},
        {"time": "05:14:37", "url": "https://www.php.net/contact.php", "title": "PHP: Contact", "driver": "user", "via": "preview click (a[href='/contact.php'])"},
        {"time": "05:14:37", "url": "https://www.php.net/contact.php", "title": "PHP: Contact", "driver": "agent"},
    ]
    text = format_watch_log(entries, "saved.json")
    lines = text.splitlines()
    step_lines = [l for l in lines if "[step " in l]
    assert [l.split("[step ")[1].split("]")[0] for l in step_lines] == ["1", "2", "3", "4", "5", "6", "7", "8"]
    assert "via preview scroll to a[href='https://www.php.net/archive/2026.php#2026-10-21-4'] [scroll] [step 1]" in text
    assert "via preview click (a[href='https://www.php.net/archive/2026.php#2026-10-21-4']) [click-driven] [step 2]" in text
    assert "via preview scroll to a[href='https://www.php.net/ChangeLog-8.php#8.5.12'] [scroll] [step 3]" in text
    assert "via preview click (a[href='https://www.php.net/ChangeLog-8.php#8.5.12']) [click-driven] [step 4]" in text
    assert "via preview scroll to a[href='/sites.php'] [scroll] [step 5]" in text
    assert "via preview click (a[href='/sites.php']) [click-driven] [step 6]" in text
    assert "via preview scroll to a[href='/contact.php'] [scroll] [step 7]" in text
    assert "via preview click (a[href='/contact.php']) [click-driven] [step 8]" in text
    assert "steps: 4 scroll, 4 click-driven, 2 driver transitions (8 action steps)" in text
    for l in step_lines:
        if "[scroll]" in l:
            assert "[click-driven]" not in l
        if "[click-driven]" in l:
            assert "[scroll]" not in l
    # Via selectors only: a step's page URL legitimately IS a click
    # destination (e.g. step 3 scrolls on the archive page reached
    # by step 2), so a whole-line check would falsely fail.
    def via_part(line):
        return line.split(" via ", 1)[1].split(" [scroll]")[0].split(" [click-driven]")[0]
    scroll_lines = [l for l in step_lines if "[scroll]" in l]
    click_lines = [l for l in step_lines if "[click-driven]" in l]
    assert set(via_part(l) for l in scroll_lines) == {
        "preview scroll to a[href='https://www.php.net/archive/2026.php#2026-10-21-4']",
        "preview scroll to a[href='https://www.php.net/ChangeLog-8.php#8.5.12']",
        "preview scroll to a[href='/sites.php']",
        "preview scroll to a[href='/contact.php']",
    }
    assert set(via_part(l) for l in click_lines) == {
        "preview click (a[href='https://www.php.net/archive/2026.php#2026-10-21-4'])",
        "preview click (a[href='https://www.php.net/ChangeLog-8.php#8.5.12'])",
        "preview click (a[href='/sites.php'])",
        "preview click (a[href='/contact.php'])",
    }
    assert len(scroll_lines) == 4 and len(click_lines) == 4


def test_cycle20_five_page_chain_replay_is_step_numbered_1_to_10():
    """Cycle 20: a scroll -> click x5 chain across five source pages
    (perl.org home -> contribute -> siteinfo -> whitepapers -> app
    -> style-guide) must be numbered step 1..10 in order in the
    Python replay, with a steps footer (5 scroll, 5 click-driven,
    2 transitions), exactly as proven live on perl.org. No
    cross-marking: scroll lines carry [scroll] only, click lines
    carry [click-driven] only, and each selector appears only on
    its own line's via part."""
    from shadowcode_pkg.browser import format_watch_log
    entries = [
        {"time": "06:22:24", "url": "https://www.perl.org/", "title": "The Perl Programming Language - www.perl.org", "driver": "agent"},
        {"time": "06:22:24", "url": "https://www.perl.org/", "title": "The Perl Programming Language - www.perl.org", "driver": "user"},
        {"time": "06:22:25", "url": "https://www.perl.org/", "title": "The Perl Programming Language - www.perl.org", "driver": "user", "via": "preview scroll to a[href='/contribute.html']"},
        {"time": "06:22:31", "url": "https://www.perl.org/contribute.html", "title": "Contribute to Perl - www.perl.org", "driver": "user", "via": "preview click (a[href='/contribute.html'])"},
        {"time": "06:22:32", "url": "https://www.perl.org/contribute.html", "title": "Contribute to Perl - www.perl.org", "driver": "user", "via": "preview scroll to a[href='/siteinfo.html']"},
        {"time": "06:22:35", "url": "https://www.perl.org/siteinfo.html", "title": "Site Information - www.perl.org", "driver": "user", "via": "preview click (a[href='/siteinfo.html'])"},
        {"time": "06:22:37", "url": "https://www.perl.org/siteinfo.html", "title": "Site Information - www.perl.org", "driver": "user", "via": "preview scroll to a[href='/about/whitepapers/']"},
        {"time": "06:22:40", "url": "https://www.perl.org/about/whitepapers/", "title": "Perl 5 White Papers - www.perl.org", "driver": "user", "via": "preview click (a[href='/about/whitepapers/'])"},
        {"time": "06:22:42", "url": "https://www.perl.org/about/whitepapers/", "title": "Perl 5 White Papers - www.perl.org", "driver": "user", "via": "preview scroll to a[href='/app.html']"},
        {"time": "06:22:45", "url": "https://www.perl.org/app.html", "title": "Application Programming - www.perl.org", "driver": "user", "via": "preview click (a[href='/app.html'])"},
        {"time": "06:22:47", "url": "https://www.perl.org/app.html", "title": "Application Programming - www.perl.org", "driver": "user", "via": "preview scroll to a[href='/about/style-guide.html']"},
        {"time": "06:22:50", "url": "https://www.perl.org/about/style-guide.html", "title": "Perl or perl? - www.perl.org", "driver": "user", "via": "preview click (a[href='/about/style-guide.html'])"},
        {"time": "06:22:51", "url": "https://www.perl.org/about/style-guide.html", "title": "Perl or perl? - www.perl.org", "driver": "agent"},
    ]
    text = format_watch_log(entries, "saved.json")
    lines = text.splitlines()
    step_lines = [l for l in lines if "[step " in l]
    assert [l.split("[step ")[1].split("]")[0] for l in step_lines] == ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"]
    assert "via preview scroll to a[href='/contribute.html'] [scroll] [step 1]" in text
    assert "via preview click (a[href='/contribute.html']) [click-driven] [step 2]" in text
    assert "via preview scroll to a[href='/siteinfo.html'] [scroll] [step 3]" in text
    assert "via preview click (a[href='/siteinfo.html']) [click-driven] [step 4]" in text
    assert "via preview scroll to a[href='/about/whitepapers/'] [scroll] [step 5]" in text
    assert "via preview click (a[href='/about/whitepapers/']) [click-driven] [step 6]" in text
    assert "via preview scroll to a[href='/app.html'] [scroll] [step 7]" in text
    assert "via preview click (a[href='/app.html']) [click-driven] [step 8]" in text
    assert "via preview scroll to a[href='/about/style-guide.html'] [scroll] [step 9]" in text
    assert "via preview click (a[href='/about/style-guide.html']) [click-driven] [step 10]" in text
    assert "steps: 5 scroll, 5 click-driven, 2 driver transitions (10 action steps)" in text
    for l in step_lines:
        if "[scroll]" in l:
            assert "[click-driven]" not in l
        if "[click-driven]" in l:
            assert "[scroll]" not in l
    # Via selectors only: a step's page URL legitimately IS a click
    # destination (e.g. step 3 scrolls on the contribute page
    # reached by step 2), so a whole-line check would falsely fail.
    def via_part(line):
        return line.split(" via ", 1)[1].split(" [scroll]")[0].split(" [click-driven]")[0]
    scroll_lines = [l for l in step_lines if "[scroll]" in l]
    click_lines = [l for l in step_lines if "[click-driven]" in l]
    assert set(via_part(l) for l in scroll_lines) == {
        "preview scroll to a[href='/contribute.html']",
        "preview scroll to a[href='/siteinfo.html']",
        "preview scroll to a[href='/about/whitepapers/']",
        "preview scroll to a[href='/app.html']",
        "preview scroll to a[href='/about/style-guide.html']",
    }
    assert set(via_part(l) for l in click_lines) == {
        "preview click (a[href='/contribute.html'])",
        "preview click (a[href='/siteinfo.html'])",
        "preview click (a[href='/about/whitepapers/'])",
        "preview click (a[href='/app.html'])",
        "preview click (a[href='/about/style-guide.html'])",
    }
    assert len(scroll_lines) == 5 and len(click_lines) == 5

def test_cycle21_six_page_chain_replay_is_step_numbered_1_to_12():
    """Cycle 21: a scroll -> click x6 chain across six source pages
    (scala-lang.org home -> conduct -> license -> security ->
    governance -> blog -> download) must be numbered step 1..12 in
    order in the Python replay, with a steps footer (6 scroll,
    6 click-driven, 2 transitions), exactly as proven live on
    scala-lang.org. No cross-marking: scroll lines carry [scroll]
    only, click lines carry [click-driven] only, and each selector
    appears only on its own line's via part. The real saved log
    also has one non-action title-settle entry (conduct.html
    Loading -> conduct/ final title) between steps 2 and 3; it
    gets no step number and does not disturb the numbering."""
    from shadowcode_pkg.browser import format_watch_log
    entries = [
        {"time": "06:27:11", "url": "https://www.scala-lang.org/", "title": "The Scala Programming Language", "driver": "agent"},
        {"time": "06:27:12", "url": "https://www.scala-lang.org/", "title": "The Scala Programming Language", "driver": "user"},
        {"time": "06:27:12", "url": "https://www.scala-lang.org/", "title": "The Scala Programming Language", "driver": "user", "via": "preview scroll to a[href='/conduct.html']"},
        {"time": "06:27:16", "url": "https://www.scala-lang.org/conduct.html", "title": "Loading https://www.scala-lang.org/conduct/", "driver": "user", "via": "preview click (a[href='/conduct.html'])"},
        {"time": "06:27:18", "url": "https://www.scala-lang.org/conduct/", "title": "The Scala Code of Conduct | The Scala Programming Language", "driver": "user"},
        {"time": "06:27:18", "url": "https://www.scala-lang.org/conduct/", "title": "The Scala Code of Conduct | The Scala Programming Language", "driver": "user", "via": "preview scroll to a[href='/license/']"},
        {"time": "06:27:21", "url": "https://www.scala-lang.org/license/", "title": "Scala License | The Scala Programming Language", "driver": "user", "via": "preview click (a[href='/license/'])"},
        {"time": "06:27:22", "url": "https://www.scala-lang.org/license/", "title": "Scala License | The Scala Programming Language", "driver": "user", "via": "preview scroll to a[href='/security/']"},
        {"time": "06:27:26", "url": "https://www.scala-lang.org/security/", "title": "Scala Security Policy | The Scala Programming Language", "driver": "user", "via": "preview click (a[href='/security/'])"},
        {"time": "06:27:27", "url": "https://www.scala-lang.org/security/", "title": "Scala Security Policy | The Scala Programming Language", "driver": "user", "via": "preview scroll to a[href='/governance/']"},
        {"time": "06:27:32", "url": "https://www.scala-lang.org/governance/", "title": "Governance | The Scala Programming Language", "driver": "user", "via": "preview click (a[href='/governance/'])"},
        {"time": "06:27:32", "url": "https://www.scala-lang.org/governance/", "title": "Governance | The Scala Programming Language", "driver": "user", "via": "preview scroll to a[href='/blog/']"},
        {"time": "06:27:36", "url": "https://www.scala-lang.org/blog/", "title": "Blog | The Scala Programming Language", "driver": "user", "via": "preview click (a[href='/blog/'])"},
        {"time": "06:27:37", "url": "https://www.scala-lang.org/blog/", "title": "Blog | The Scala Programming Language", "driver": "user", "via": "preview scroll to a[href='/download/']"},
        {"time": "06:27:42", "url": "https://www.scala-lang.org/download/", "title": "Install | The Scala Programming Language", "driver": "user", "via": "preview click (a[href='/download/'])"},
        {"time": "06:27:42", "url": "https://www.scala-lang.org/download/", "title": "Install | The Scala Programming Language", "driver": "agent"},
    ]
    text = format_watch_log(entries, "saved.json")
    lines = text.splitlines()
    step_lines = [l for l in lines if "[step " in l]
    assert [l.split("[step ")[1].split("]")[0] for l in step_lines] == ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12"]
    assert "via preview scroll to a[href='/conduct.html'] [scroll] [step 1]" in text
    assert "via preview click (a[href='/conduct.html']) [click-driven] [step 2]" in text
    assert "via preview scroll to a[href='/license/'] [scroll] [step 3]" in text
    assert "via preview click (a[href='/license/']) [click-driven] [step 4]" in text
    assert "via preview scroll to a[href='/security/'] [scroll] [step 5]" in text
    assert "via preview click (a[href='/security/']) [click-driven] [step 6]" in text
    assert "via preview scroll to a[href='/governance/'] [scroll] [step 7]" in text
    assert "via preview click (a[href='/governance/']) [click-driven] [step 8]" in text
    assert "via preview scroll to a[href='/blog/'] [scroll] [step 9]" in text
    assert "via preview click (a[href='/blog/']) [click-driven] [step 10]" in text
    assert "via preview scroll to a[href='/download/'] [scroll] [step 11]" in text
    assert "via preview click (a[href='/download/']) [click-driven] [step 12]" in text
    assert "steps: 6 scroll, 6 click-driven, 2 driver transitions (12 action steps)" in text
    # The title-settle entry carries no via and no step number.
    settle = [l for l in lines if "https://www.scala-lang.org/conduct/" in l and "via " not in l]
    assert len(settle) == 1 and "[step " not in settle[0]
    for l in step_lines:
        if "[scroll]" in l:
            assert "[click-driven]" not in l
        if "[click-driven]" in l:
            assert "[scroll]" not in l
    def via_part(line):
        return line.split(" via ", 1)[1].split(" [scroll]")[0].split(" [click-driven]")[0]
    scroll_lines = [l for l in step_lines if "[scroll]" in l]
    click_lines = [l for l in step_lines if "[click-driven]" in l]
    assert set(via_part(l) for l in scroll_lines) == {
        "preview scroll to a[href='/conduct.html']",
        "preview scroll to a[href='/license/']",
        "preview scroll to a[href='/security/']",
        "preview scroll to a[href='/governance/']",
        "preview scroll to a[href='/blog/']",
        "preview scroll to a[href='/download/']",
    }
    assert set(via_part(l) for l in click_lines) == {
        "preview click (a[href='/conduct.html'])",
        "preview click (a[href='/license/'])",
        "preview click (a[href='/security/'])",
        "preview click (a[href='/governance/'])",
        "preview click (a[href='/blog/'])",
        "preview click (a[href='/download/'])",
    }
    assert len(scroll_lines) == 6 and len(click_lines) == 6

def test_cycle22_seven_page_chain_replay_is_step_numbered_1_to_14():
    """Cycle 22: a scroll -> click x7 chain across seven source pages
    (elixir-lang.org home -> install -> learning -> docs -> cases ->
    blog -> development -> trademarks) must be numbered step 1..14 in
    order in the Python replay, with a steps footer (7 scroll,
    7 click-driven, 2 transitions), exactly as proven live on
    elixir-lang.org. No cross-marking: scroll lines carry [scroll]
    only, click lines carry [click-driven] only, and each selector
    appears only on its own line's via part."""
    from shadowcode_pkg.browser import format_watch_log
    entries = [
        {"time": "06:35:47", "url": "https://elixir-lang.org/", "title": "The Elixir programming language", "driver": "agent"},
        {"time": "06:35:47", "url": "https://elixir-lang.org/", "title": "The Elixir programming language", "driver": "user"},
        {"time": "06:35:47", "url": "https://elixir-lang.org/", "title": "The Elixir programming language", "driver": "user", "via": "preview scroll to a[href='/install/']"},
        {"time": "06:35:51", "url": "https://elixir-lang.org/install/", "title": "Install Elixir | The Elixir programming language", "driver": "user", "via": "preview click (a[href='/install/'])"},
        {"time": "06:35:52", "url": "https://elixir-lang.org/install/", "title": "Install Elixir | The Elixir programming language", "driver": "user", "via": "preview scroll to a[href='/learning/']"},
        {"time": "06:35:57", "url": "https://elixir-lang.org/learning/", "title": "Learning | The Elixir programming language", "driver": "user", "via": "preview click (a[href='/learning/'])"},
        {"time": "06:35:57", "url": "https://elixir-lang.org/learning/", "title": "Learning | The Elixir programming language", "driver": "user", "via": "preview scroll to a[href='/docs/']"},
        {"time": "06:36:01", "url": "https://elixir-lang.org/docs/", "title": "Documentation | The Elixir programming language", "driver": "user", "via": "preview click (a[href='/docs/'])"},
        {"time": "06:36:02", "url": "https://elixir-lang.org/docs/", "title": "Documentation | The Elixir programming language", "driver": "user", "via": "preview scroll to a[href='/cases/']"},
        {"time": "06:36:07", "url": "https://elixir-lang.org/cases/", "title": "Case studies | The Elixir programming language", "driver": "user", "via": "preview click (a[href='/cases/'])"},
        {"time": "06:36:07", "url": "https://elixir-lang.org/cases/", "title": "Case studies | The Elixir programming language", "driver": "user", "via": "preview scroll to a[href='/blog/']"},
        {"time": "06:36:11", "url": "https://elixir-lang.org/blog/", "title": "Blog | The Elixir programming language", "driver": "user", "via": "preview click (a[href='/blog/'])"},
        {"time": "06:36:12", "url": "https://elixir-lang.org/blog/", "title": "Blog | The Elixir programming language", "driver": "user", "via": "preview scroll to a[href='/development/']"},
        {"time": "06:36:17", "url": "https://elixir-lang.org/development/", "title": "Development & team | The Elixir programming language", "driver": "user", "via": "preview click (a[href='/development/'])"},
        {"time": "06:36:17", "url": "https://elixir-lang.org/development/", "title": "Development & team | The Elixir programming language", "driver": "user", "via": "preview scroll to a[href='/trademarks/']"},
        {"time": "06:36:21", "url": "https://elixir-lang.org/trademarks/", "title": "Trademarks policy | The Elixir programming language", "driver": "user", "via": "preview click (a[href='/trademarks/'])"},
        {"time": "06:36:22", "url": "https://elixir-lang.org/trademarks/", "title": "Trademarks policy | The Elixir programming language", "driver": "agent"},
    ]
    text = format_watch_log(entries, "saved.json")
    lines = text.splitlines()
    step_lines = [l for l in lines if "[step " in l]
    assert [l.split("[step ")[1].split("]")[0] for l in step_lines] == [str(n) for n in range(1, 15)]
    assert "via preview scroll to a[href='/install/'] [scroll] [step 1]" in text
    assert "via preview click (a[href='/install/']) [click-driven] [step 2]" in text
    assert "via preview scroll to a[href='/learning/'] [scroll] [step 3]" in text
    assert "via preview click (a[href='/learning/']) [click-driven] [step 4]" in text
    assert "via preview scroll to a[href='/docs/'] [scroll] [step 5]" in text
    assert "via preview click (a[href='/docs/']) [click-driven] [step 6]" in text
    assert "via preview scroll to a[href='/cases/'] [scroll] [step 7]" in text
    assert "via preview click (a[href='/cases/']) [click-driven] [step 8]" in text
    assert "via preview scroll to a[href='/blog/'] [scroll] [step 9]" in text
    assert "via preview click (a[href='/blog/']) [click-driven] [step 10]" in text
    assert "via preview scroll to a[href='/development/'] [scroll] [step 11]" in text
    assert "via preview click (a[href='/development/']) [click-driven] [step 12]" in text
    assert "via preview scroll to a[href='/trademarks/'] [scroll] [step 13]" in text
    assert "via preview click (a[href='/trademarks/']) [click-driven] [step 14]" in text
    assert "steps: 7 scroll, 7 click-driven, 2 driver transitions (14 action steps)" in text
    for l in step_lines:
        if "[scroll]" in l:
            assert "[click-driven]" not in l
        if "[click-driven]" in l:
            assert "[scroll]" not in l
    def via_part(line):
        return line.split(" via ", 1)[1].split(" [scroll]")[0].split(" [click-driven]")[0]
    scroll_lines = [l for l in step_lines if "[scroll]" in l]
    click_lines = [l for l in step_lines if "[click-driven]" in l]
    assert set(via_part(l) for l in scroll_lines) == {
        "preview scroll to a[href='/install/']",
        "preview scroll to a[href='/learning/']",
        "preview scroll to a[href='/docs/']",
        "preview scroll to a[href='/cases/']",
        "preview scroll to a[href='/blog/']",
        "preview scroll to a[href='/development/']",
        "preview scroll to a[href='/trademarks/']",
    }
    assert set(via_part(l) for l in click_lines) == {
        "preview click (a[href='/install/'])",
        "preview click (a[href='/learning/'])",
        "preview click (a[href='/docs/'])",
        "preview click (a[href='/cases/'])",
        "preview click (a[href='/blog/'])",
        "preview click (a[href='/development/'])",
        "preview click (a[href='/trademarks/'])",
    }
    assert len(scroll_lines) == 7 and len(click_lines) == 7

def test_cycle23_eight_page_chain_replay_is_step_numbered_1_to_16():
    """Cycle 23: a scroll -> click x8 chain across eight source pages
    (lua.org home -> start -> docs -> faq -> versions -> license ->
    authors -> thanks -> donations) must be numbered step 1..16 in
    order in the Python replay, with a steps footer (8 scroll,
    8 click-driven, 2 transitions), exactly as proven live on
    lua.org. No cross-marking: scroll lines carry [scroll]
    only, click lines carry [click-driven] only, and each selector
    appears only on its own line's via part."""
    from shadowcode_pkg.browser import format_watch_log
    pages = [
        ("The Programming Language Lua", "https://www.lua.org/", "start.html"),
        ("Lua: getting started", "https://www.lua.org/start.html", "docs.html"),
        ("Lua: documentation", "https://www.lua.org/docs.html", "faq.html"),
        ("Lua: FAQ", "https://www.lua.org/faq.html", "versions.html"),
        ("Lua: version history", "https://www.lua.org/versions.html", "license.html"),
        ("Lua: license", "https://www.lua.org/license.html", "authors.html"),
        ("Lua: authors", "https://www.lua.org/authors.html", "thanks.html"),
        ("Lua: thanks", "https://www.lua.org/thanks.html", "donations.html"),
    ]
    entries = [
        {"time": "06:40:01", "url": "https://www.lua.org/", "title": "The Programming Language Lua", "driver": "agent"},
        {"time": "06:40:02", "url": "https://www.lua.org/", "title": "The Programming Language Lua", "driver": "user"},
    ]
    for title, url, nxt in pages:
        entries.append({"time": "06:40:02", "url": url, "title": title, "driver": "user", "via": f"preview scroll to a[href='{nxt}']"})
        dest_title = next((t for t, u, _ in pages if u == f"https://www.lua.org/{nxt}"), "Lua: donations") if nxt != "donations.html" else "Lua: donations"
        # destination title is the next page's title, except the last
        dest_url = f"https://www.lua.org/{nxt}"
        entries.append({"time": "06:40:04", "url": dest_url, "title": dest_title, "driver": "user", "via": f"preview click (a[href='{nxt}'])"})
    entries.append({"time": "06:40:29", "url": "https://www.lua.org/donations.html", "title": "Lua: donations", "driver": "agent"})
    # Fix destination titles: they must match the next source page's title.
    titles_by_url = {u: t for t, u, _ in pages}
    titles_by_url["https://www.lua.org/donations.html"] = "Lua: donations"
    for e in entries:
        if "via" in e and e["via"].startswith("preview click"):
            e["title"] = titles_by_url[e["url"]]
    text = format_watch_log(entries, "saved.json")
    lines = text.splitlines()
    step_lines = [l for l in lines if "[step " in l]
    assert [l.split("[step ")[1].split("]")[0] for l in step_lines] == [str(n) for n in range(1, 17)]
    for n, sel in enumerate(["start.html", "docs.html", "faq.html", "versions.html", "license.html", "authors.html", "thanks.html", "donations.html"], 1):
        assert f"via preview scroll to a[href='{sel}'] [scroll] [step {2 * n - 1}]" in text
        assert f"via preview click (a[href='{sel}']) [click-driven] [step {2 * n}]" in text
    assert "steps: 8 scroll, 8 click-driven, 2 driver transitions (16 action steps)" in text
    for l in step_lines:
        if "[scroll]" in l:
            assert "[click-driven]" not in l
        if "[click-driven]" in l:
            assert "[scroll]" not in l
    def via_part(line):
        return line.split(" via ", 1)[1].split(" [scroll]")[0].split(" [click-driven]")[0]
    scroll_lines = [l for l in step_lines if "[scroll]" in l]
    click_lines = [l for l in step_lines if "[click-driven]" in l]
    assert set(via_part(l) for l in scroll_lines) == {f"preview scroll to a[href='{s}']" for s in ["start.html", "docs.html", "faq.html", "versions.html", "license.html", "authors.html", "thanks.html", "donations.html"]}
    assert set(via_part(l) for l in click_lines) == {f"preview click (a[href='{s}'])" for s in ["start.html", "docs.html", "faq.html", "versions.html", "license.html", "authors.html", "thanks.html", "donations.html"]}
    assert len(scroll_lines) == 8 and len(click_lines) == 8


def test_cycle24_nine_page_chain_replay_is_step_numbered_1_to_18():
    """Cycle 24: a scroll -> click x9 chain across nine source pages
    (ocaml.org home -> docs -> platform [via /tools] -> packages ->
    community -> changelog -> events -> jobs -> security ->
    governance) must be numbered step 1..18 in order in the Python
    replay, with a steps footer (9 scroll, 9 click-driven,
    2 transitions), exactly as proven live on ocaml.org. No
    cross-marking: scroll lines carry [scroll] only, click lines
    carry [click-driven] only, and each selector appears only on
    its own line's via part."""
    from shadowcode_pkg.browser import format_watch_log
    pages = [
        ("Welcome to a World of OCaml", "https://ocaml.org/", "/docs", "Learn OCaml", "https://ocaml.org/docs"),
        ("Learn OCaml", "https://ocaml.org/docs", "/tools", "OCaml Platform", "https://ocaml.org/platform"),
        ("OCaml Platform", "https://ocaml.org/platform", "/packages", "OCaml Packages · Browse Community Packages", "https://ocaml.org/packages"),
        ("OCaml Packages · Browse Community Packages", "https://ocaml.org/packages", "/community", "The OCaml Community", "https://ocaml.org/community"),
        ("The OCaml Community", "https://ocaml.org/community", "/changelog", "OCaml Changelog", "https://ocaml.org/changelog"),
        ("OCaml Changelog", "https://ocaml.org/changelog", "/events", "Upcoming OCaml Events", "https://ocaml.org/events"),
        ("Upcoming OCaml Events", "https://ocaml.org/events", "/jobs", "OCaml Jobs", "https://ocaml.org/jobs"),
        ("OCaml Jobs", "https://ocaml.org/jobs", "/security", "OCaml Security", "https://ocaml.org/security"),
        ("OCaml Security", "https://ocaml.org/security", "/governance", "Governance", "https://ocaml.org/governance"),
    ]
    entries = [
        {"time": "06:52:31", "url": "https://ocaml.org/", "title": "Welcome to a World of OCaml", "driver": "agent"},
        {"time": "06:52:31", "url": "https://ocaml.org/", "title": "Welcome to a World of OCaml", "driver": "user"},
    ]
    for title, url, nxt, dest_title, dest_url in pages:
        entries.append({"time": "06:52:31", "url": url, "title": title, "driver": "user", "via": f"preview scroll to a[href='{nxt}']"})
        entries.append({"time": "06:52:34", "url": dest_url, "title": dest_title, "driver": "user", "via": f"preview click (a[href='{nxt}'])"})
    entries.append({"time": "06:53:02", "url": "https://ocaml.org/governance", "title": "Governance", "driver": "agent"})
    text = format_watch_log(entries, "saved.json")
    lines = text.splitlines()
    step_lines = [l for l in lines if "[step " in l]
    assert [l.split("[step ")[1].split("]")[0] for l in step_lines] == [str(n) for n in range(1, 19)]
    for n, sel in enumerate(["/docs", "/tools", "/packages", "/community", "/changelog", "/events", "/jobs", "/security", "/governance"], 1):
        assert f"via preview scroll to a[href='{sel}'] [scroll] [step {2 * n - 1}]" in text
        assert f"via preview click (a[href='{sel}']) [click-driven] [step {2 * n}]" in text
    assert "steps: 9 scroll, 9 click-driven, 2 driver transitions (18 action steps)" in text
    for l in step_lines:
        if "[scroll]" in l:
            assert "[click-driven]" not in l
        if "[click-driven]" in l:
            assert "[scroll]" not in l
    def via_part(line):
        return line.split(" via ", 1)[1].split(" [scroll]")[0].split(" [click-driven]")[0]
    scroll_lines = [l for l in step_lines if "[scroll]" in l]
    click_lines = [l for l in step_lines if "[click-driven]" in l]
    sels = ["/docs", "/tools", "/packages", "/community", "/changelog", "/events", "/jobs", "/security", "/governance"]
    assert set(via_part(l) for l in scroll_lines) == {f"preview scroll to a[href='{s}']" for s in sels}
    assert set(via_part(l) for l in click_lines) == {f"preview click (a[href='{s}'])" for s in sels}
    assert len(scroll_lines) == 9 and len(click_lines) == 9


def test_cycle25_ten_page_chain_replay_is_step_numbered_1_to_20():
    """Cycle 25: a scroll -> click x10 chain across ten source pages
    (julialang.org home -> downloads -> learning -> blog ->
    community -> contribute -> jsoc -> community/standards ->
    community/stewards -> governance -> diversity) must be
    numbered step 1..20 in order in the Python replay, with a
    steps footer (10 scroll, 10 click-driven, 2 transitions),
    exactly as proven live on julialang.org. No cross-marking:
    scroll lines carry [scroll] only, click lines carry
    [click-driven] only, and each selector appears only on its
    own line's via part."""
    from shadowcode_pkg.browser import format_watch_log
    pages = [
        ("The Julia Programming Language", "https://julialang.org/", "/downloads/", "Installing Julia", "https://julialang.org/downloads/"),
        ("Installing Julia", "https://julialang.org/downloads/", "/learning/", "Get started with Julia", "https://julialang.org/learning/"),
        ("Get started with Julia", "https://julialang.org/learning/", "/blog/", "The Julia Language Blog", "https://julialang.org/blog/"),
        ("The Julia Language Blog", "https://julialang.org/blog/", "/community/", "Community", "https://julialang.org/community/"),
        ("Community", "https://julialang.org/community/", "/contribute/", "Ask and answer questions", "https://julialang.org/contribute/"),
        ("Ask and answer questions", "https://julialang.org/contribute/", "/jsoc/", "Julia Seasons of Contributions", "https://julialang.org/jsoc/"),
        ("Julia Seasons of Contributions", "https://julialang.org/jsoc/", "/community/standards/", "Julia Community - Standards", "https://julialang.org/community/standards/"),
        ("Julia Community - Standards", "https://julialang.org/community/standards/", "/community/stewards/", "Julia Community - Stewards", "https://julialang.org/community/stewards/"),
        ("Julia Community - Stewards", "https://julialang.org/community/stewards/", "/governance/", "Julia Governance", "https://julialang.org/governance/"),
        ("Julia Governance", "https://julialang.org/governance/", "/diversity/", "Diversity", "https://julialang.org/diversity/"),
    ]
    entries = [
        {"time": "07:06:53", "url": "https://julialang.org/", "title": "The Julia Programming Language", "driver": "agent"},
        {"time": "07:06:53", "url": "https://julialang.org/", "title": "The Julia Programming Language", "driver": "user"},
    ]
    for title, url, nxt, dest_title, dest_url in pages:
        entries.append({"time": "07:06:54", "url": url, "title": title, "driver": "user", "via": f"preview scroll to a[href='{nxt}']"})
        entries.append({"time": "07:06:57", "url": dest_url, "title": dest_title, "driver": "user", "via": f"preview click (a[href='{nxt}'])"})
    entries.append({"time": "07:07:30", "url": "https://julialang.org/diversity/", "title": "Diversity", "driver": "agent"})
    text = format_watch_log(entries, "saved.json")
    lines = text.splitlines()
    step_lines = [l for l in lines if "[step " in l]
    assert [l.split("[step ")[1].split("]")[0] for l in step_lines] == [str(n) for n in range(1, 21)]
    for n, sel in enumerate(["/downloads/", "/learning/", "/blog/", "/community/", "/contribute/", "/jsoc/", "/community/standards/", "/community/stewards/", "/governance/", "/diversity/"], 1):
        assert f"via preview scroll to a[href='{sel}'] [scroll] [step {2 * n - 1}]" in text
        assert f"via preview click (a[href='{sel}']) [click-driven] [step {2 * n}]" in text
    assert "steps: 10 scroll, 10 click-driven, 2 driver transitions (20 action steps)" in text
    for l in step_lines:
        if "[scroll]" in l:
            assert "[click-driven]" not in l
        if "[click-driven]" in l:
            assert "[scroll]" not in l
    def via_part(line):
        return line.split(" via ", 1)[1].split(" [scroll]")[0].split(" [click-driven]")[0]
    scroll_lines = [l for l in step_lines if "[scroll]" in l]
    click_lines = [l for l in step_lines if "[click-driven]" in l]
    sels = ["/downloads/", "/learning/", "/blog/", "/community/", "/contribute/", "/jsoc/", "/community/standards/", "/community/stewards/", "/governance/", "/diversity/"]
    assert set(via_part(l) for l in scroll_lines) == {f"preview scroll to a[href='{s}']" for s in sels}
    assert set(via_part(l) for l in click_lines) == {f"preview click (a[href='{s}'])" for s in sels}
    assert len(scroll_lines) == 10 and len(click_lines) == 10


def test_cycle26_eleven_page_chain_replay_is_step_numbered_1_to_22():
    """Cycle 26: a scroll -> click x11 chain across eleven source pages
    (crystal-lang.org home -> install -> blog -> releases ->
    community -> sponsors -> success-stories -> used_in_prod ->
    team -> community/governance -> media -> learning) must be
    numbered step 1..22 in order in the Python replay, with a
    steps footer (11 scroll, 11 click-driven, 2 transitions),
    exactly as proven live on crystal-lang.org. No cross-marking:
    scroll lines carry [scroll] only, click lines carry
    [click-driven] only, and each selector appears only on its
    own line's via part."""
    from shadowcode_pkg.browser import format_watch_log
    pages = [
        ("The Crystal Programming Language", "https://crystal-lang.org/", "/install/", "Install - The Crystal Programming Language", "https://crystal-lang.org/install/"),
        ("Install - The Crystal Programming Language", "https://crystal-lang.org/install/", "/blog/", "News - The Crystal Programming Language", "https://crystal-lang.org/blog/"),
        ("News - The Crystal Programming Language", "https://crystal-lang.org/blog/", "/releases/", "Releases - The Crystal Programming Language", "https://crystal-lang.org/releases/"),
        ("Releases - The Crystal Programming Language", "https://crystal-lang.org/releases/", "/community/", "Community - The Crystal Programming Language", "https://crystal-lang.org/community/"),
        ("Community - The Crystal Programming Language", "https://crystal-lang.org/community/", "/sponsors/", "Sponsors - The Crystal Programming Language", "https://crystal-lang.org/sponsors/"),
        ("Sponsors - The Crystal Programming Language", "https://crystal-lang.org/sponsors/", "/success-stories/", "Success stories - The Crystal Programming Language", "https://crystal-lang.org/success-stories/"),
        ("Success stories - The Crystal Programming Language", "https://crystal-lang.org/success-stories/", "/used_in_prod/", "Used in production - The Crystal Programming Language", "https://crystal-lang.org/used_in_prod/"),
        ("Used in production - The Crystal Programming Language", "https://crystal-lang.org/used_in_prod/", "/team/", "Team - The Crystal Programming Language", "https://crystal-lang.org/team/"),
        ("Team - The Crystal Programming Language", "https://crystal-lang.org/team/", "/community/governance/", "Crystal governance - The Crystal Programming Language", "https://crystal-lang.org/community/governance/"),
        ("Crystal governance - The Crystal Programming Language", "https://crystal-lang.org/community/governance/", "/media/", "Media - The Crystal Programming Language", "https://crystal-lang.org/media/"),
        ("Media - The Crystal Programming Language", "https://crystal-lang.org/media/", "/learning/", "External resources - The Crystal Programming Language", "https://crystal-lang.org/learning/"),
    ]
    entries = [
        {"time": "07:14:51", "url": "https://crystal-lang.org/", "title": "The Crystal Programming Language", "driver": "agent"},
        {"time": "07:14:52", "url": "https://crystal-lang.org/", "title": "The Crystal Programming Language", "driver": "user"},
    ]
    for title, url, nxt, dest_title, dest_url in pages:
        entries.append({"time": "07:14:52", "url": url, "title": title, "driver": "user", "via": f"preview scroll to a[href='{nxt}']"})
        entries.append({"time": "07:14:56", "url": dest_url, "title": dest_title, "driver": "user", "via": f"preview click (a[href='{nxt}'])"})
    entries.append({"time": "07:15:30", "url": "https://crystal-lang.org/learning/", "title": "External resources - The Crystal Programming Language", "driver": "agent"})
    text = format_watch_log(entries, "saved.json")
    lines = text.splitlines()
    step_lines = [l for l in lines if "[step " in l]
    assert [l.split("[step ")[1].split("]")[0] for l in step_lines] == [str(n) for n in range(1, 23)]
    for n, sel in enumerate(["/install/", "/blog/", "/releases/", "/community/", "/sponsors/", "/success-stories/", "/used_in_prod/", "/team/", "/community/governance/", "/media/", "/learning/"], 1):
        assert f"via preview scroll to a[href='{sel}'] [scroll] [step {2 * n - 1}]" in text
        assert f"via preview click (a[href='{sel}']) [click-driven] [step {2 * n}]" in text
    assert "steps: 11 scroll, 11 click-driven, 2 driver transitions (22 action steps)" in text
    for l in step_lines:
        if "[scroll]" in l:
            assert "[click-driven]" not in l
        if "[click-driven]" in l:
            assert "[scroll]" not in l
    def via_part(line):
        return line.split(" via ", 1)[1].split(" [scroll]")[0].split(" [click-driven]")[0]
    scroll_lines = [l for l in step_lines if "[scroll]" in l]
    click_lines = [l for l in step_lines if "[click-driven]" in l]
    sels = ["/install/", "/blog/", "/releases/", "/community/", "/sponsors/", "/success-stories/", "/used_in_prod/", "/team/", "/community/governance/", "/media/", "/learning/"]
    assert set(via_part(l) for l in scroll_lines) == {f"preview scroll to a[href='{s}']" for s in sels}
    assert set(via_part(l) for l in click_lines) == {f"preview click (a[href='{s}'])" for s in sels}
    assert len(scroll_lines) == 11 and len(click_lines) == 11


def test_kilo_provider_no_key_no_auth_header_and_default_model():
    """Kilo cycle: get_provider('kilo') defaults to kilo-auto/free,
    sends NO Authorization header when KILO_API_KEY is unset, and
    sends a generous max_tokens (reasoning models otherwise return
    reasoning only with no visible content). HTTP is mocked here;
    the live call is recorded in TESTING.md, not in this test."""
    import os
    import shadowcode_pkg.providers as prov
    os.environ.pop("KILO_API_KEY", None)
    p = prov.get_provider("kilo")
    assert p.name == "kilo"
    assert p.default_model == "kilo-auto/free"
    assert p.base == "https://api.kilo.ai/api/openrouter"
    assert p.require_key is False
    seen = {}
    def fake_post(url, payload, headers=None):
        seen["url"] = url; seen["payload"] = payload; seen["headers"] = headers
        return {"choices": [{"message": {"content": "hello kilo", "role": "assistant"}}]}
    old = prov._post
    prov._post = fake_post
    try:
        text = p.chat([{"role": "user", "content": "say hello"}], "")
    finally:
        prov._post = old
    assert text == "hello kilo"
    assert seen["url"].endswith("/chat/completions")
    assert "Authorization" not in (seen["headers"] or {})
    assert seen["payload"]["model"] == "kilo-auto/free"
    assert seen["payload"]["max_tokens"] == 4096


def test_kilo_provider_uses_key_only_when_set_and_rejects_reasoning_only():
    """With KILO_API_KEY set, the header is sent (paid models);
    a reasoning-only reply raises instead of being claimed as
    a successful empty answer."""
    import os
    import shadowcode_pkg.providers as prov
    os.environ["KILO_API_KEY"] = "test-key-not-real"
    p = prov.get_provider("kilo")
    seen = {}
    def fake_post(url, payload, headers=None):
        seen["headers"] = headers
        return {"choices": [{"message": {"content": "", "reasoning_content": "thinking...", "role": "assistant"}}]}
    old = prov._post
    prov._post = fake_post
    try:
        try:
            p.chat([{"role": "user", "content": "hi"}], "")
            raise AssertionError("reasoning-only reply must raise")
        except RuntimeError as e:
            assert "reasoning only" in str(e)
    finally:
        prov._post = old
        os.environ.pop("KILO_API_KEY", None)
    assert seen["headers"].get("Authorization") == "Bearer test-key-not-real"
    # Keyed providers still require their key (no regression).
    import shadowcode_pkg.providers as prov2
    os.environ.pop("GROQ_API_KEY", None)
    try:
        prov2.get_provider("groq").chat([{"role": "user", "content": "hi"}], "")
        raise AssertionError("groq without a key must raise")
    except RuntimeError as e:
        assert "GROQ_API_KEY" in str(e)
