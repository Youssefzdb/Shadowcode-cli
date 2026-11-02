"""Browser tool + localhost live preview, original implementation.

Cycle 2: instant takeover via a DEDICATED browser thread.
Playwright's sync API is bound to the thread that created the page,
so that thread — and only that thread — owns the page. The agent
thread and the preview HTTP thread never touch the page directly:
they send commands into queues, and the browser thread executes
them promptly (controls are drained before every agent command,
and a screenshot pump runs every second while idle).

Safeguards: no sign-in, no password/payment fields, no CAPTCHA
solving, no bypass of a block/login wall (reported as such).
Preview binds to 127.0.0.1 only.
"""
import json, os, queue, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def load_saved_watch_log(workdir):
    """Read the most recent saved browser watch log in a workdir.

    Returns (path_str_or_None, entries_list). Workspace-only: it
    only looks under <workdir>/.shadowcode/browser-watch-*.json,
    never under the home directory or anywhere else. A missing or
    unreadable log is (None, []), never an invented log.
    """
    try:
        d = Path(workdir) / ".shadowcode"
        files = sorted(d.glob("browser-watch-*.json"),
                       key=lambda p: p.stat().st_mtime, reverse=True)
        if not files:
            return None, []
        entries = json.loads(files[0].read_text())
        return str(files[0]), entries if isinstance(entries, list) else []
    except Exception:
        return None, []


def via_kind(via):
    """Classify a watch entry's action, without cross-marking.

    Cycle 15: marking must come from the ACTION word, not from a
    substring anywhere in the via string. A CSS selector can
    legitimately contain 'scroll' or 'click' (e.g. '#scroll-nav a'
    clicked, or 'a.clickable' scrolled to); substring matching
    would then mark a click as [scroll] or a scroll as
    [click-driven]. Via strings are '<driver> <action> <argument>'
    ('preview scroll to #x', 'preview click (#x)', 'agent scroll
    down'), so the action is the second word (or the first word
    for a bare via). Anything else has no marker.
    """
    parts = str(via or "").strip().lower().split()
    if not parts:
        return ""
    if len(parts) >= 2 and parts[0] in ("preview", "agent"):
        action = parts[1]
    else:
        action = parts[0]
    return action if action in ("scroll", "click") else ""


def format_watch_log(entries, watch_file=""):
    """Full watch-log replay, with driver transitions marked.

    Unlike state()["watch"] (a tail), this prints EVERY entry in
    the log, in order, and inserts a transition line whenever the
    driver changes (agent -> user on takeover, user -> agent on
    handback), so a replay shows who was driving each move.
    """
    lines = [f"browser watch replay: {len(entries)} entries"
             + (f" (saved: {watch_file})" if watch_file else "")]
    if not entries:
        lines.append("  (no page changes observed yet)")
        return "\n".join(lines)
    prev_driver = None
    # Cycle 17: step numbering for multi-step sequences. Action
    # entries (scroll/click) are numbered in the order they
    # happened — step 1, step 2, … — so a scroll -> click ->
    # scroll -> click sequence reads as a sequence, not as
    # unrelated marked lines. Non-action entries get no step.
    step = 0
    transitions = 0
    n_scroll = 0
    n_click = 0
    for i, e in enumerate(entries, 1):
        driver = e.get("driver", "")
        if prev_driver is not None and driver != prev_driver:
            lines.append(f"  ↳ driver transition: {prev_driver} -> {driver}")
            transitions += 1
        # Cycle 12 polish: click-driven entries are marked clearly,
        # so a replay reader can tell a preview click apart from a
        # goto/agent open at a glance, without guessing from URLs.
        # Cycle 13: scroll entries get the same treatment, so a
        # scroll-then-click sequence is visible as scroll + click.
        via = e.get("via", "")
        suffix = f" via {via}" if via else ""
        kind = via_kind(via)
        if kind == "click":
            suffix += " [click-driven]"
            n_click += 1
            step += 1
            suffix += f" [step {step}]"
        if kind == "scroll":
            suffix += " [scroll]"
            n_scroll += 1
            step += 1
            suffix += f" [step {step}]"
        lines.append(f"  {i}. {e.get('time', '')} {e.get('title', '')} — {e.get('url', '')} ({driver}){suffix}")
        prev_driver = driver
    if step:
        lines.append(f"  steps: {n_scroll} scroll, {n_click} click-driven, {transitions} driver transition{'s' if transitions != 1 else ''} ({step} action step{'s' if step != 1 else ''})")
    return "\n".join(lines)


class Browser:
    def __init__(self, workdir, preview_port=8765):
        self.workdir = Path(workdir)
        # Per-session watch-log file, workspace-only: one file per
        # browser session, under <workdir>/.shadowcode/, so a replay
        # survives the browser closing and a CLI restart.
        self.watch_session_id = time.strftime("%Y%m%d-%H%M%S") + f"-{os.getpid()}"
        self.watch_file = self.workdir / ".shadowcode" / f"browser-watch-{self.watch_session_id}.json"
        self.driver = "agent"  # agent | user
        self.url = ""
        self.title = ""
        self.shot = None
        # Watch log: every URL/title change observed by the browser
        # thread, whoever drove it (agent or user). This is how the
        # agent WATCHES while the user drives: it reads this log /
        # state() instead of reloading anything.
        self.watch_log = []
        self.control_errors = []
        # Cycle 12: the user action that caused the NEXT page change,
        # so a click-driven navigation is recorded as click-driven
        # (not silently as if it were a goto/agent open).
        self._pending_via = None
        self._last_url = None
        self._last_title = None
        # Kept for cycle-1 compatibility: the browser thread now drains
        # this queue itself, so drain_controls() is a no-op.
        self.control_queue = []
        self._lock = threading.Lock()
        self._agent_q = queue.Queue()
        self._control_q = queue.Queue()
        self._ready = threading.Event()
        self._stop = threading.Event()
        self._thread = None
        self._start_error = None
        self.server = None
        self.port = preview_port
        self.preview_url = ""
        self.page = None  # intentionally None outside the browser thread
        try:
            from playwright.sync_api import sync_playwright
            self._sync_playwright = sync_playwright
        except Exception as e:
            raise RuntimeError(
                f"Playwright not available: {e}. "
                "Install: pip install playwright && playwright install firefox"
            )

    # ---------- public API used by Tools / main ----------
    def start(self):
        if self._thread is not None:
            return self.preview_url
        self._thread = threading.Thread(target=self._browser_loop, daemon=True)
        self._thread.start()
        if not self._ready.wait(timeout=30):
            raise RuntimeError(f"browser thread did not start: {self._start_error}")
        if self._start_error:
            raise RuntimeError(str(self._start_error))
        return self.preview_url

    def drain_controls(self):
        """Cycle-1 compatibility: controls are now drained by the browser
        thread itself, promptly, so there is nothing left to drain here."""
        return ""

    def _save_watch_log(self):
        """Persist the full watch log to this session's file.

        Best-effort only: a write failure must never break browsing
        or the preview. The file is workspace-only (under the
        browser workdir), one per browser session.
        """
        try:
            path = getattr(self, "watch_file", None)
            if path is None:
                return
            path.parent.mkdir(parents=True, exist_ok=True)
            with self._lock:
                entries = list(self.watch_log)
            path.write_text(json.dumps(entries, indent=2))
        except Exception:
            pass

    def record_driver_change(self, driver):
        """Record a driver change as its own watch entry (cycle 10).

        A handback changes no URL/title, so without this the saved
        log would show agent -> user but never user -> agent: the
        replay would be missing its second transition. Recording
        the change (same page, new driver) makes the full replay
        show BOTH transitions. No-op if there is no page yet, or
        if the last entry already has this driver.
        """
        with self._lock:
            if not self.url:
                return
            if self.watch_log and self.watch_log[-1].get("driver") == driver:
                return
            self.watch_log.append({
                "time": time.strftime("%H:%M:%S"),
                "url": self.url,
                "title": self.title,
                "driver": driver,
            })
            self.watch_log = self.watch_log[-100:]
        self._save_watch_log()

    def record_action_entry(self, via):
        """Append a watch entry for an action that changes no URL/title.

        Cycle 13: a scroll changes neither, so _snap() alone would
        never log it — yet a scroll-then-click replay must show the
        scroll. This records the CURRENT page with the given via
        (e.g. 'preview scroll down', 'agent scroll to #x'), capped
        and persisted like any other watch entry. No-op with no page.
        """
        with self._lock:
            if not self.url:
                return
            self.watch_log.append({
                "time": time.strftime("%H:%M:%S"),
                "url": self.url,
                "title": self.title,
                "driver": self.driver,
                "via": via,
            })
            self.watch_log = self.watch_log[-100:]
        self._save_watch_log()

    def full_watch(self):
        """Full watch log (all entries, not the state() tail)."""
        with self._lock:
            return list(getattr(self, "watch_log", []) or [])

    def full_watch_text(self):
        """Full replay text, with driver transitions, no reload."""
        return format_watch_log(self.full_watch(),
                                str(getattr(self, "watch_file", "") or ""))

    def state(self):
        """Current browser state, as the agent sees it on handback.

        No reload, no reset, no restart: just the live page the
        browser thread is currently on, plus the watch log of
        changes made while the user was driving."""
        with self._lock:
            return {
                "url": self.url,
                "title": self.title,
                "driver": self.driver,
                "has_screenshot": self.shot is not None,
                "watch": list(self.watch_log[-10:]),
                "watch_count": len(self.watch_log),
                "watch_file": str(getattr(self, "watch_file", "") or ""),
                "last_control_error": self.control_errors[-1] if self.control_errors else "",
            }

    def watch(self):
        """Agent tool implementation: read current state, never reload."""
        st = self.state()
        lines = [f"current: {st['title']} — {st['url']} (driver: {st['driver']})"]
        for e in st["watch"]:
            via = e.get("via", "")
            marker = ""
            if via_kind(via) == "click":
                marker += " [click-driven]"
            if via_kind(via) == "scroll":
                marker += " [scroll]"
            suffix = (f" via {via}" + marker) if via else ""
            lines.append(f"watched: {e['title']} — {e['url']} (driver: {e['driver']}){suffix}")
        return "\n".join(lines)

    def call(self, name, args):
        if self._thread is None:
            self.start()
            print(f"Live preview: {self.preview_url} (takeover: Take control button, Hand back to agent)")
        result_q = queue.Queue()
        self._agent_q.put((name, args or {}, result_q))
        try:
            return result_q.get(timeout=40)
        except queue.Empty:
            return "tool error: browser command timed out"

    def close(self):
        # Final persist of this session's watch log, so /browser-watch
        # can replay it after the browser has closed.
        try:
            self._save_watch_log()
        except Exception:
            pass
        try:
            if self._thread is not None:
                # Ask the browser thread to close; fall back to a hard stop.
                result_q = queue.Queue()
                self._agent_q.put(("browser_close", {}, result_q))
                try:
                    result_q.get(timeout=5)
                except queue.Empty:
                    pass
                self._stop.set()
                self._thread.join(timeout=5)
                self._thread = None
            if self.server:
                try:
                    self.server.shutdown()
                except Exception:
                    pass
        except Exception:
            pass
        self.page = None

    # ---------- browser thread ----------
    def _browser_loop(self):
        page = None
        browser = None
        playwright = None
        context = None
        try:
            playwright = self._sync_playwright().start()
            engine = os.environ.get("SHADOWCODE_BROWSER_ENGINE", "firefox")
            launcher = getattr(playwright, engine)
            browser = launcher.launch()
            # ignore_https_errors: this sandbox's egress proxy MITM-signs TLS.
            context = browser.new_context(
                viewport={"width": 1280, "height": 720}, ignore_https_errors=True
            )
            page = context.new_page()
            self._start_preview()
            self._ready.set()
        except Exception as e:
            self._start_error = e
            self._ready.set()
            return

        last_snap = 0.0
        try:
            while not self._stop.is_set():
                # 1. User takeover controls first, promptly.
                while True:
                    try:
                        ctl = self._control_q.get_nowait()
                    except queue.Empty:
                        break
                    self._exec_control(page, ctl)
                # 2. One agent command, if any.
                try:
                    name, args, result_q = self._agent_q.get(timeout=0.2)
                except queue.Empty:
                    name = None
                if name is not None:
                    # Controls that arrived while we were busy go first.
                    while True:
                        try:
                            ctl = self._control_q.get_nowait()
                        except queue.Empty:
                            break
                        self._exec_control(page, ctl)
                    result_q.put(self._exec_agent(page, name, args))
                    if name == "browser_close":
                        break
                # 3. Screenshot pump while idle, so the preview stays live.
                now = time.time()
                if page and now - last_snap >= 1.0:
                    self._snap(page)
                    last_snap = now
        finally:
            try:
                if self.server:
                    self.server.shutdown()
            except Exception:
                pass
            try:
                if browser:
                    browser.close()
            except Exception:
                pass
            try:
                if playwright:
                    playwright.stop()
            except Exception:
                pass

    def _exec_control(self, page, ctl):
        """ctl: (x, y) click, or {'action': ...} dict.

        Actions: type, key, goto (user URL bar), back, forward.
        Every action is followed by a snap, so the watch log and
        the preview see the user's move immediately."""
        try:
            if isinstance(ctl, dict):
                act = ctl.get("action")
                if act == "type":
                    self._pending_via = "preview type"
                    page.keyboard.type(str(ctl.get("text", "")))
                elif act == "key":
                    self._pending_via = "preview key"
                    page.keyboard.press(str(ctl.get("key", "Enter")))
                elif act == "goto":
                    self._pending_via = "preview goto"
                    page.goto(str(ctl.get("url", "")), timeout=30000)
                elif act == "back":
                    self._pending_via = "preview back"
                    page.go_back()
                elif act == "forward":
                    self._pending_via = "preview forward"
                    page.go_forward()
                elif act == "scroll":
                    # Cycle 13 preview scroll: wheel scrolls do not
                    # change URL/title, so _snap() alone logs nothing.
                    # Record the scroll explicitly, then snap.
                    direction = str(ctl.get("direction", "down")).lower()
                    amount = int(ctl.get("amount", 600))
                    if direction == "top":
                        page.evaluate("window.scrollTo(0, 0)")
                    elif direction == "bottom":
                        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    elif direction == "up":
                        page.mouse.wheel(0, -abs(amount))
                    else:
                        page.mouse.wheel(0, abs(amount))
                    self._snap(page)
                    self.record_action_entry(f"preview scroll {direction}")
                elif act == "scroll_to":
                    # Cycle 13 preview scroll-to: scroll a selector
                    # into view, then record it (same no-URL-change
                    # reason as wheel scrolls).
                    sel = str(ctl.get("selector", "") or ctl.get("text", ""))
                    if sel.startswith("text="):
                        page.get_by_text(sel[5:], exact=False).first.scroll_into_view_if_needed(timeout=10000)
                    else:
                        page.locator(sel).first.scroll_into_view_if_needed(timeout=10000)
                    self._snap(page)
                    self.record_action_entry(f"preview scroll to {sel}")
                elif act in ("click_text", "click_selector"):
                    # Cycle 12 preview click (not a goto): a real
                    # element click in the browser thread, driven
                    # by the user through the preview control queue.
                    txt = str(ctl.get("text", "") or ctl.get("selector", ""))
                    self._pending_via = f"preview click ({txt})"
                    if act == "click_text":
                        page.get_by_text(txt, exact=False).first.click(timeout=10000)
                    else:
                        page.locator(txt).first.click(timeout=10000)
                else:
                    self._pending_via = f"preview control ({act})"
            else:
                x, y = ctl
                self._pending_via = f"preview click ({x},{y})"
                page.mouse.click(float(x), float(y))
            self._snap(page)
        except Exception as e:
            # Never swallow a user control silently: the preview
            # state shows the last error, so a failed click/goto
            # is visible instead of looking like nothing happened.
            self.control_errors.append(str(e))

    def _snap(self, page):
        changed = False
        try:
            shot = page.screenshot()
            with self._lock:
                self.shot = shot
                self.url = page.url
                self.title = page.title()
                if self.url != self._last_url or self.title != self._last_title:
                    entry = {
                        "time": time.strftime("%H:%M:%S"),
                        "url": self.url,
                        "title": self.title,
                        "driver": self.driver,
                    }
                    # Cycle 12: attach the pending user action to
                    # this change. Clear it only once the URL itself
                    # has changed: a click first changes the title
                    # to "Loading …" on the old URL, and only then
                    # lands on the new URL — clearing on the title
                    # change would leave the destination entry
                    # unmarked, which is exactly the entry a replay
                    # reader needs to see as click-driven.
                    if getattr(self, "_pending_via", None):
                        entry["via"] = self._pending_via
                        if self.url != self._last_url:
                            self._pending_via = None
                    self.watch_log.append(entry)
                    self.watch_log = self.watch_log[-100:]
                    self._last_url = self.url
                    self._last_title = self.title
                    changed = True
        except Exception:
            pass
        if changed:
            # Persist the new entry immediately, so a replay
            # survives a crash/restart, not just a clean close.
            self._save_watch_log()

    # ---------- cycle 4: selector / scroll / form helpers ----------
    def _forbidden_field_text(self, text):
        t = str(text or "").lower()
        return any(w in t for w in ["password", "passwd", "card", "cvv", "cvc", "payment", "credit", "ssn"])

    def _locator(self, page, selector):
        """Resolve a selector: 'text=…' or 'css:…' prefixes, else a CSS
        locator, falling back to get_by_text for plain visible text."""
        sel = str(selector or "")
        if sel.startswith("text="):
            return page.get_by_text(sel[5:], exact=False).first
        if sel.startswith("css:"):
            sel = sel[4:]
        try:
            return page.locator(sel).first
        except Exception:
            return page.get_by_text(sel, exact=False).first

    def _visibility(self, loc):
        """Return '' if the locator looks usable, else a clear report.

        Never forces a click/fill on a hidden or disabled element:
        the caller reports the reason instead of pretending success.
        """
        try:
            if loc.count() == 0:
                return "not found"
        except Exception:
            pass
        try:
            if not loc.is_visible():
                return "hidden"
        except Exception:
            pass
        try:
            if not loc.is_enabled():
                return "disabled"
        except Exception:
            pass
        return ""

    def _element_kind(self, loc):
        """(tag, type) for a locator, via evaluate when available."""
        try:
            info = loc.evaluate("el => ({tag: el.tagName, type: el.type || ''})")
            if isinstance(info, dict):
                return str(info.get("tag", "")).upper(), str(info.get("type", "")).lower()
        except Exception:
            pass
        for attr, fallback in (("type", ""),):
            try:
                v = loc.get_attribute(attr)
            except Exception:
                v = None
            if v:
                return "INPUT", str(v).lower()
        return "INPUT", ""

    def _fill_locator(self, loc, value):
        """Fill by field type: select -> select_option, checkbox/radio
        -> check/uncheck, anything else -> fill. Returns a report."""
        tag, typ = self._element_kind(loc)
        val = str(value)
        if tag == "SELECT":
            try:
                loc.select_option(value=val)
                return f"selected option {val!r}"
            except Exception:
                loc.select_option(label=val)
                return f"selected option (label) {val!r}"
        if typ in ("checkbox", "radio"):
            wanted = val.strip().lower() in ("1", "true", "yes", "on", "checked")
            if wanted:
                loc.check()
            else:
                loc.uncheck()
            return f"{'checked' if wanted else 'unchecked'} {typ}"
        loc.fill(val)
        return f"filled {val[:80]!r}"

    def _check_fill_target(self, page, selector, label=""):
        """Refuse password/payment targets, by selector/label string AND
        by the element's own type/name/id/aria-label when inspectable."""
        if self._forbidden_field_text(selector) or self._forbidden_field_text(label):
            return "refused: password/payment fields are not filled by Shadowcode"
        try:
            loc = self._locator(page, selector)
            for attr in ("type", "name", "id", "aria-label", "placeholder"):
                try:
                    v = loc.get_attribute(attr)
                except Exception:
                    v = None
                if v and self._forbidden_field_text(v):
                    return "refused: password/payment fields are not filled by Shadowcode"
        except Exception:
            pass
        return ""

    def _exec_agent(self, page, name, args):
        # Agent actions pause while the user is driving, except reads/close.
        if self.driver == "user" and name not in ("browser_read", "browser_watch", "browser_watch_replay", "browser_state", "browser_close"):
            return (
                "browser is user-driven right now (preview: USER DRIVING). "
                "Use Hand back to agent in the preview, or browser_close."
            )
        try:
            if name == "browser_open":
                page.goto(args.get("url", ""), timeout=30000)
                self._snap(page)
                return f"opened {self.url} title={self.title!r}"
            if name == "browser_read":
                self._snap(page)
                txt = page.inner_text("body")[:4000] if page else ""
                return f"title: {self.title}\nurl: {self.url}\n{txt}"
            if name in ("browser_watch", "browser_state"):
                # Handback resume point: read the CURRENT page, do
                # NOT reload, reset, or restart the browser.
                self._snap(page)
                txt = page.inner_text("body")[:2000] if page else ""
                return (
                    f"resuming from current page (no reload):\n{self.watch()}\n{txt}"
                )
            if name == "browser_watch_replay":
                # Full replay, no reload, no page body: every watch
                # entry, with driver transitions, plus the saved file.
                self._snap(page)
                return self.full_watch_text()
            if name == "browser_click":
                page.get_by_text(args.get("text", ""), exact=False).first.click(timeout=10000)
                self._snap(page)
                return f"clicked, now {self.url} title={self.title!r}"
            if name == "browser_click_selector":
                sel = args.get("selector", "") or args.get("text", "")
                loc = self._locator(page, sel)
                bad = self._visibility(loc)
                if bad:
                    return f"selector {sel!r} {bad}: not clicked, not forced (report only)"
                loc.click(timeout=10000)
                self._snap(page)
                return f"clicked selector {sel!r}, now {self.url} title={self.title!r}"
            if name == "browser_scroll":
                # direction: down/up/top/bottom; amount in px; or
                # selector: scroll that element into view.
                sel = args.get("selector", "")
                if sel:
                    loc = self._locator(page, sel)
                    bad = self._visibility(loc)
                    if bad == "not found":
                        return f"scroll target {sel!r} not found: not scrolled, not forced"
                    try:
                        loc.scroll_into_view_if_needed(timeout=10000)
                    except Exception:
                        pass
                    # Reliability check: is it in the viewport now?
                    in_view = ""
                    try:
                        in_view = loc.evaluate(
                            "el => { const r = el.getBoundingClientRect(); "
                            "return (r.top >= 0 && r.bottom <= window.innerHeight) ? 'in view' : 'not in viewport'; }")
                    except Exception:
                        in_view = "viewport check unavailable"
                    self._snap(page)
                    # Cycle 13: scrolls change no URL/title, so log
                    # them explicitly, otherwise a replay would show
                    # no trace of the scroll at all.
                    self.record_action_entry(f"agent scroll to {sel}")
                    return f"scrolled to {sel!r}: {in_view}, now {self.url}"
                else:
                    direction = str(args.get("direction", "down")).lower()
                    amount = int(args.get("amount", 600))
                    if direction == "top":
                        page.evaluate("window.scrollTo(0, 0)")
                    elif direction == "bottom":
                        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    elif direction == "up":
                        page.mouse.wheel(0, -abs(amount))
                    else:
                        page.mouse.wheel(0, abs(amount))
                self._snap(page)
                # Cycle 13: see the selector branch — log the scroll
                # explicitly, since _snap() logs only URL/title changes.
                self.record_action_entry(f"agent scroll {direction}")
                return f"scrolled, now {self.url}"
            if name == "browser_fill":
                field = str(args.get("field", "")).lower()
                if any(w in field for w in ["password", "card", "cvv", "payment", "credit"]):
                    return "refused: password/payment fields are not filled by Shadowcode"
                page.get_by_label(args.get("field", ""), exact=False).first.fill(args.get("value", ""))
                self._snap(page)
                return "filled"
            if name == "browser_fill_selector":
                sel = args.get("selector", "") or args.get("field", "")
                refused = self._check_fill_target(page, sel)
                if refused:
                    return refused
                loc = self._locator(page, sel)
                bad = self._visibility(loc)
                if bad:
                    return f"selector {sel!r} {bad}: not filled, not forced (report only)"
                report = self._fill_locator(loc, args.get("value", ""))
                self._snap(page)
                return f"selector {sel!r}: {report}"
            if name == "browser_fill_form":
                # fields: {selector-or-label: value}. All fields are
                # checked first; one forbidden field refuses the whole
                # form. submit=True only for non-sign-in forms: it is
                # refused if the page has a password input, or the
                # submit button text mentions sign/log-in.
                fields = args.get("fields", {}) or {}
                if not isinstance(fields, dict) or not fields:
                    return "tool error: browser_fill_form needs fields={selector: value}"
                for sel in fields:
                    refused = self._check_fill_target(page, sel)
                    if refused:
                        return refused + " (whole form refused)"
                for sel, val in fields.items():
                    loc = self._locator(page, sel)
                    bad = self._visibility(loc)
                    if bad:
                        return f"field {sel!r} {bad}: whole form not filled, not forced"
                    try:
                        self._fill_locator(loc, val)
                    except Exception:
                        page.get_by_label(sel, exact=False).first.fill(str(val), timeout=10000)
                filled = list(fields)
                if args.get("submit"):
                    try:
                        if page.locator("input[type=password]").count():
                            return f"filled {filled} (submit refused: page has a password field)"
                        btn = page.locator("button[type=submit], input[type=submit]").first
                        txt = ""
                        try:
                            txt = (btn.inner_text() or "") + " " + (btn.get_attribute("value") or "")
                        except Exception:
                            pass
                        if any(w in txt.lower() for w in ["sign in", "sign-in", "log in", "login"]):
                            return f"filled {filled} (submit refused: sign-in button)"
                        btn.click(timeout=10000)
                    except Exception as e:
                        return f"filled {filled} (submit failed: {e})"
                    self._snap(page)
                    return f"filled and submitted {filled}, now {self.url}"
                self._snap(page)
                return f"filled {filled} (no submit)"
            if name == "browser_screenshot":
                out = self.workdir / "screenshots" / (args.get("name", "screenshot.png"))
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(page.screenshot())
                self._snap(page)
                return f"screenshot saved: {out}"
            if name == "browser_navigate":
                if args.get("direction") == "back":
                    page.go_back()
                else:
                    page.go_forward()
                self._snap(page)
                return f"now {self.url}"
            if name == "browser_close":
                return "browser closed"
            return f"unknown browser tool: {name}"
        except Exception as e:
            return f"tool error: {e}"

    # ---------- preview HTTP server (127.0.0.1 only) ----------
    def _start_preview(self):
        b = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                if self.path == "/state.json":
                    self._send(200, "application/json", json.dumps(b.state()).encode())
                elif self.path == "/shot.png":
                    with b._lock:
                        shot = b.shot
                    if shot:
                        self._send(200, "image/png", shot)
                    else:
                        self._send(404, "text/plain", b"no screenshot yet")
                else:
                    html = """<html><head><title>Shadowcode live preview</title></head><body>
<h2 id='drv'>AGENT DRIVING</h2><p id='info'></p>
<button onclick="fetch('/takeover',{method:'POST'})">Take control</button>
<button onclick="fetch('/handback',{method:'POST'})">Hand back to agent</button>
<button onclick="nav('back')">Back</button><button onclick="nav('forward')">Forward</button>
<button onclick="post({action:'scroll',direction:'down',amount:600})">Scroll down</button>
<button onclick="post({action:'scroll',direction:'up',amount:600})">Scroll up</button><br>
<input id='url' placeholder='https://…' style='width:60%'><button onclick="goUrl()">Go</button><br>
<input id='keys' placeholder='type text here'><button onclick="sendKeys()">Send keys</button><br>
<input id='scrollto' placeholder='scroll to: selector or text=…' style='width:40%'><button onclick="scrollToEl()">Scroll to</button>
<input id='clicktext' placeholder='click text: visible link text' style='width:40%'><button onclick="clickText()">Click text</button>
<input id='clickselector' placeholder='click selector: CSS selector' style='width:40%'><button onclick="clickSelector()">Click selector</button><br>
<img id='shot' src='/shot.png' style='max-width:100%;border:1px solid #888' onclick="clickShot(event)">
<p>Watch log (what the agent sees while you drive):</p><ul id='watch'></ul>
<p><small>Hand back to agent resumes from the current page exactly — no reload, no reset.</small></p>
<script>
async function tick(){let r=await fetch('/state.json');let s=await r.json();
document.getElementById('info').textContent=s.title+' — '+s.url;
document.getElementById('drv').textContent=s.driver==='user'?'USER DRIVING':'AGENT DRIVING';
document.getElementById('watch').innerHTML=(s.watch||[]).map(e=>'<li>'+e.time+' '+e.title+' — '+e.url+' ('+e.driver+')'+(e.via?' via '+e.via:'')+'</li>').join('');
let img=document.getElementById('shot'); img.src='/shot.png?'+Date.now();}
function post(o){fetch('/control',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(o)});}
function clickShot(e){let img=e.target;let x=e.offsetX/img.clientWidth*1280;let y=e.offsetY/img.clientHeight*720;post({x:x,y:y});}
function sendKeys(){post({action:'type',text:document.getElementById('keys').value});}
function scrollToEl(){post({action:'scroll_to',selector:document.getElementById('scrollto').value});}
function clickText(){post({action:'click_text',text:document.getElementById('clicktext').value});}
function clickSelector(){post({action:'click_selector',selector:document.getElementById('clickselector').value});}
function goUrl(){post({action:'goto',url:document.getElementById('url').value});}
function nav(d){post({action:d});}
setInterval(tick,1000); tick();
</script></body></html>"""
                    self._send(200, "text/html", html.encode())

            def do_POST(self):
                if self.path == "/takeover":
                    b.driver = "user"
                    b.record_driver_change("user")
                    self._send(200, "text/plain", b"user driving")
                elif self.path == "/handback":
                    b.driver = "agent"
                    b.record_driver_change("agent")
                    self._send(200, "text/plain", b"agent driving")
                elif self.path == "/control":
                    n = int(self.headers.get("Content-Length", 0) or 0)
                    try:
                        d = json.loads(self.rfile.read(n) or b"{}")
                    except Exception:
                        d = {}
                    b.driver = "user"
                    if isinstance(d, dict) and d.get("action"):
                        b._control_q.put(d)
                    else:
                        b._control_q.put((d.get("x", 0), d.get("y", 0)))
                    self._send(200, "text/plain", b"accepted: browser thread will act promptly")
                else:
                    self._send(404, "text/plain", b"not found")

            def _send(self, code, ctype, body):
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        for port in range(self.port, self.port + 20):
            try:
                self.server = ThreadingHTTPServer(("127.0.0.1", port), H)
                self.port = port
                break
            except OSError:
                continue
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.preview_url = f"http://localhost:{self.port}"
