"""Shadowcode TUI — original stdlib-curses terminal UI.

No rich, no textual, no install: only Python's stdlib curses.
The plain REPL in main.py stays as the fallback (--no-tui, or
when stdin is not a TTY, or when curses cannot start).

Layout (like a Claude Code-style TUI, in our own code):
  line 0   header: Shadowcode | provider/model | session | permission
  lines 1..h-3  transcript: user / assistant / [tool name] lines
  line h-2 status: hints + browser driver, if any
  line h-1 input: "> " + current input (or a permission prompt)

TUIState is pure (no curses) so it is unit-testable without a
terminal. CursesUI renders a TUIState and reads input keys.
Token streaming and tool events arrive through callbacks that
the agent loop calls synchronously, on the same thread, so a
refresh inside the callback is safe.
"""
import textwrap


def help_text():
    """Help overlay text (also shown by /help in the plain REPL)."""
    return [
        "Shadowcode TUI — commands",
        "/help  /model [name]  /provider [name]  /tools",
        "/sessions [query]  /sessions-view [query]  /session-info <id>",
        "/search-sessions <q> [--from D] [--to D]",
        "/export-file <id> [md|json] [path]  /resume <id>",
        "/clear  /compact  /permissions  /browser  /browser-watch-replay  /health  /mcp [server]  /doctor",
        "/go-search <q>  (Go /search first, Python search fallback)",
        "/exit  —  !cmd runs a shell command",
        "Keys: Up/Down = history, Ctrl-R = history search,",
        "PgUp/PgDn = scroll transcript, F1 = this help, Esc = clear input",
    ]


class TUIState:
    def __init__(self, provider="", model="", session_id="", permission_mode="manual"):
        self.provider = provider
        self.model = model or "(default)"
        self.session_id = session_id
        self.permission_mode = permission_mode
        self.browser_driver = ""
        self.browser_url = ""
        self.browser_title = ""
        self.browser_health = "unknown"
        self.browser_watch = []
        self.lines = []  # (tag, text): tag in user/assistant/tool/system
        self.tool_events = []  # (name, result summary)
        self.status = "Ready. Type /help for commands."
        self.thinking = False
        self.tool_count = 0
        self.last_tool = ""

    def header(self):
        # Cycle 5: status line is richer, header stays one short line.
        # Thinking + last tool + message count live in status_line().
        return (
            f"Shadowcode  provider={self.provider} model={self.model} "
            f"session={self.session_id} perm={self.permission_mode}"
        )

    def add(self, tag, text):
        for part in str(text).splitlines() or [""]:
            self.lines.append((tag, part))

    def add_user(self, text):
        self.add("user", f"> {text}")

    def add_token(self, token):
        # Streaming: append to the last assistant line, or start one.
        if self.lines and self.lines[-1][0] == "assistant" and not self.lines[-1][1].endswith("\n"):
            tag, prev = self.lines[-1]
            self.lines[-1] = (tag, prev + token)
        else:
            self.lines.append(("assistant", token))

    def add_tool(self, name, result):
        # Cycle 5: clearer rendering. First line carries a status mark
        # (✓ ok, ✕ error/refused, … running) and the tool name; the
        # result body is kept, wrapped, indented, and capped — not
        # flattened to a single 200-char blob, so multi-line tool
        # output (diffs, file listings) stays readable.
        text = str(result)
        lowered = text.lower()
        mark = "✕" if ("tool error" in lowered or lowered.startswith("refused")
                        or "refused:" in lowered) else "✓"
        self.tool_count += 1
        self.last_tool = name
        summary = text.replace("\n", " ")[:200]
        self.tool_events.append((name, summary))
        self.add("tool", f"[tool {name}] {mark}")
        for line in text.splitlines()[:8] or [""]:
            self.add("tool", f"  {line[:200]}")

    def set_browser(self, driver, url, title="", health="unknown", watch=None):
        self.browser_driver = driver
        self.browser_url = url
        self.browser_title = title
        self.browser_health = health
        self.browser_watch = list(watch or [])

    def browser_panel(self, preview_url=""):
        """Cycle 8 browser panel: fresh state + takeover/handback
        hints + watch-log tail, for /browser. Delegates formatting
        to health.format_browser_panel so REPL and TUI agree."""
        from .health import format_browser_panel
        state = None
        if self.browser_url or self.browser_title:
            state = {
                "url": self.browser_url, "title": self.browser_title,
                "driver": self.browser_driver, "has_screenshot": False,
                "watch": self.browser_watch, "last_control_error": "",
            }
        return format_browser_panel(state, preview_url, self.browser_health)

    def status_line(self):
        # Cycle 5: better status line — thinking state, tool count,
        # last tool, message count, and browser driver/URL (truncated),
        # so the user can tell at a glance what the agent is doing.
        # Cycle 8: + browser title and preview health.
        state = "THINKING…" if self.thinking else self.status
        b = ""
        if self.browser_driver or self.browser_url or self.browser_title:
            url = self.browser_url[:40]
            title = self.browser_title[:30]
            b = f" | browser: {self.browser_driver} {title} {url} health={self.browser_health}"
        return (
            f"/help  /exit  !cmd = shell{b} | msgs={len(self.lines)} "
            f"tools={self.tool_count}" + (f" last={self.last_tool}" if self.last_tool else "") +
            f" | {state}"
        )

    def visible_lines(self, width, height, offset=0):
        """Wrapped transcript lines that fit the transcript pane.

        offset = lines scrolled back (PgUp/PgDn in CursesUI); 0 shows
        the live tail, as before.
        """
        wrapped = []
        for tag, text in self.lines:
            prefix = {"user": "YOU ", "assistant": "AI  ", "tool": "TOO ", "system": "SYS "}.get(tag, "    ")
            body_width = max(20, width - len(prefix))
            for chunk in textwrap.wrap(text, body_width) or [""]:
                wrapped.append(f"{prefix}{chunk}")
        if height <= 3:
            return wrapped
        pane = height - 3
        if offset <= 0:
            return wrapped[-pane:]
        return wrapped[max(0, len(wrapped) - pane - offset):max(0, len(wrapped) - offset)]


class CursesUI:
    def __init__(self, stdscr, state):
        self.stdscr = stdscr
        self.state = state
        self.input_buf = ""
        self.history = []
        self.hist_idx = None
        self.scroll_offset = 0
        self.search_mode = False
        self.search_buf = ""
        self.search_matches = []
        self.search_idx = None

    def search_history(self, query):
        """Pure history search: newest-first matches, case-insensitive.

        Returns the matching history lines (newest first) so the UI
        and unit tests share one implementation. Empty query = all.
        """
        q = str(query or "").lower()
        if not q:
            return list(reversed(self.history))
        return [h for h in reversed(self.history) if q in h.lower()]

    def show_help_overlay(self):
        """Help overlay: draws a box over the transcript, waits for
        any key, then restores the transcript. Plain-REPL fallback
        is unaffected (this only runs inside curses)."""
        try:
            scr = self.stdscr
            h, w = scr.getmaxyx()
            lines = help_text()
            box_w = min(w - 4, max(len(x) for x in lines) + 4) if w > 8 else w
            box_h = min(h - 2, len(lines) + 2)
            top = max(0, (h - box_h) // 2)
            left = max(0, (w - box_w) // 2)
            for r in range(box_h):
                scr.addstr(top + r, left, " " * box_w)
            for i, line in enumerate(lines[: box_h - 2]):
                scr.addstr(top + 1 + i, left + 2, line[: box_w - 4])
            scr.addstr(top + box_h - 1, left + 2, "(any key to close)")
            scr.refresh()
            scr.getch()
        except Exception:
            pass
        self.refresh()

    def refresh(self):
        try:
            scr = self.stdscr
            h, w = scr.getmaxyx()
            scr.erase()
            scr.addstr(0, 0, self.state.header()[: w - 1])
            for i, line in enumerate(self.state.visible_lines(w, h, offset=self.scroll_offset)):
                if 1 + i < h - 2:
                    scr.addstr(1 + i, 0, line[: w - 1])
            scr.addstr(h - 2, 0, self.state.status_line()[: w - 1])
            prompt = "search: " + self.search_buf if self.search_mode else "> " + self.input_buf
            buf = self.search_buf if self.search_mode else self.input_buf
            scr.addstr(h - 1, 0, prompt[-w + 1 :] if w > 1 else "")
            scr.move(h - 1, min(w - 1, len("search: " if self.search_mode else "> ") + len(buf)))
            scr.refresh()
        except Exception:
            pass

    def input_line(self):
        """Read one line in the curses input row. Returns None on Ctrl-C."""
        self.input_buf = ""
        self.refresh()
        while True:
            try:
                ch = self.stdscr.getch()
            except Exception:
                return None
            if ch in (10, 13):  # Enter
                line = self.input_buf
                self.input_buf = ""
                if line:
                    self.history.append(line)
                self.hist_idx = None
                return line
            if ch in (3,):  # Ctrl-C
                return None
            if ch == 265:  # F1: help overlay
                self.show_help_overlay()
            elif ch == 18:  # Ctrl-R: history search mode
                self.search_mode = True
                self.search_buf = ""
                self.search_matches = self.search_history("")
                self.search_idx = None
            elif self.search_mode:
                if ch in (10, 13):  # Enter: pick match, or keep typed text
                    if self.search_matches:
                        self.input_buf = self.search_matches[0] if self.search_idx is None else self.search_matches[self.search_idx]
                    else:
                        self.input_buf = self.search_buf
                    self.search_mode = False
                    line = self.input_buf
                    self.input_buf = ""
                    if line:
                        self.history.append(line)
                    self.hist_idx = None
                    return line
                if ch in (27,):  # Esc: cancel search, keep input
                    self.search_mode = False
                elif ch in (263, 127, 8):
                    self.search_buf = self.search_buf[:-1]
                    self.search_matches = self.search_history(self.search_buf)
                    self.search_idx = None
                elif ch == 259 and self.search_matches:  # Up: older match
                    self.search_idx = 0 if self.search_idx is None else min(len(self.search_matches) - 1, self.search_idx + 1)
                    self.input_buf = self.search_matches[self.search_idx]
                elif ch == 258 and self.search_matches and self.search_idx is not None:
                    self.search_idx = max(0, self.search_idx - 1)
                    self.input_buf = self.search_matches[self.search_idx]
                elif 32 <= ch < 0x110000:
                    try:
                        self.search_buf += chr(ch)
                    except Exception:
                        pass
                    self.search_matches = self.search_history(self.search_buf)
                    self.search_idx = None
            elif ch in (27,):  # Esc clears the input line
                self.input_buf = ""
            elif ch in (263, 127, 8):  # Backspace
                self.input_buf = self.input_buf[:-1]
            elif ch == 338:  # PgUp: scroll transcript back
                self.scroll_offset += 10
            elif ch == 339:  # PgDn: scroll forward, back to live tail
                self.scroll_offset = max(0, self.scroll_offset - 10)
            elif ch == 259 and self.history:  # Up: history
                self.scroll_offset = 0
                self.hist_idx = len(self.history) - 1 if self.hist_idx is None else max(0, self.hist_idx - 1)
                self.input_buf = self.history[self.hist_idx]
            elif ch == 258 and self.history and self.hist_idx is not None:  # Down
                self.hist_idx = min(len(self.history) - 1, self.hist_idx + 1)
                self.input_buf = self.history[self.hist_idx]
            elif 32 <= ch < 0x110000:
                try:
                    self.input_buf += chr(ch)
                except Exception:
                    pass
            self.refresh()

    def ask_yes_no(self, prompt):
        """Inline permission prompt in the input row. Returns True on y."""
        self.state.add("system", prompt)
        self.state.status = "Permission prompt: press y or n"
        self.refresh()
        while True:
            ch = self.stdscr.getch()
            if ch in (ord("y"), ord("Y")):
                self.state.status = "Allowed."
                return True
            if ch in (ord("n"), ord("N"), 27, 3):
                self.state.status = "Denied."
                return False
