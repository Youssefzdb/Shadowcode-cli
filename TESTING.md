# Shadowcode — testing (cycle 1, 2026-11-02)

All tests below were run with the mock provider unless stated.
No Claude Code session, key, or account was used.

## Compile
`python3 -m py_compile main.py shadowcode_pkg/*.py` — OK.

## CLI basics
- `./shadowcode --version` → `shadowcode 0.1.0`
- `./shadowcode --doctor` → provider mock, no config found,
  playwright NOT available under system python3 (expected;
  browser tests used the Playwright venv, see below).

## Mock agent loop (one-shot, --permission-mode auto)
- `list files` → `Done. Tool list_dir returned: hello.txt` (later also created.txt, screenshots/)
- `read file hello.txt` → `Done. Tool read_file returned: hello shadowcode`
- `echo hello from shadowcode` → `exit=0` + `hello from shadowcode`
- `write file created.txt` → wrote created.txt (22 chars), content `hello from Shadowcode`
- `search for shadowcode` → `hello.txt:1: hello shadowcode`
- REPL piped input: list/read/tools/sessions all worked;
  `/sessions` listed saved session IDs with message counts.
- Resume: `./shadowcode --resume bb722c819716 ... "list files"` worked.

## Bug found and fixed during testing
First one-shot runs returned only the mock fallback text and
hid tool output: the agent loop's second turn (after tool
feedback) used the mock's generic fallback. Fixed in
`providers.py`: the mock now returns `Done. <tool feedback>`
on a turn whose prompt starts with `Tool `, so tool results
are visible in the final answer. Re-tested after the fix
(see results above).

## Permissions / safety
- Plan mode: `write file hacked.txt` → `permission denied:
  plan mode is read-only: write_file refused` (shown in output,
  no file written).
- Destructive guard (unit check): `is_destructive('rm -rf /tmp/x')`
  = True; `check()` without `--allow-destructive` → refused;
  with `--allow-destructive` but confirm = No → not confirmed.
- Path confinement: `read_file('../README.md')` from
  test-workspace → `path outside working directory` (correct).
- Edit (direct tool test): dry-run previewed the replacement,
  real edit replaced exactly once, file updated to
  `hello SHADOWCODE` (later restored to `hello shadowcode`).

## Browser + live preview (Playwright Firefox via the venv
python that has Playwright; system python3 lacks Playwright)
- First run failed with `SEC_ERROR_UNKNOWN_ISSUER` (sandbox
  egress proxy MITM). Fixed: browser context created with
  `ignore_https_errors=True` (same reason as cli-ai-agent).
- After fix: `open https://example.com` → HTTP 200,
  title `Example Domain`.
- `browser_read` → title + URL + page text.
- `browser_click "Learn more"` → `https://www.iana.org/help/example-domains`,
  `browser_navigate back` → example.com.
- Preview: `GET /state.json` →
  `{"url": "https://example.com/", "title": "Example Domain",
  "driver": "agent", "has_screenshot": true}`;
  `GET /shot.png` → 81,823-byte PNG.
- Screenshot tool → `test-workspace/screenshots/screenshot.png`
  (82K, 1280×720).
- Takeover: `POST /takeover` → driver `user` in state;
  `POST /control {x:640,y:360}` → `queued: agent thread will
  click on next browser call`; a following `browser_read`
  drained the queue on the agent thread; `POST /handback` →
  driver `agent`. First attempt at direct control from the
  HTTP thread failed with Playwright's "Cannot switch to a
  different thread" error — that is why the queue design
  exists. Takeover clicks are therefore queued, not instant.
  A click on a blank area of example.com correctly changed
  nothing.

## Not tested live in cycle 1
- No cloud provider (Groq/Gemini/OpenRouter): no key was
  available in this environment, so no live cloud test was
  faked. Ollama binary exists in this environment but no
  live Ollama server/model was verified in cycle 1.
- No MCP client (future item, see NEXT.md).
- Streaming output (cycle 1 waits for the full reply).

## Cycle 2 overnight (2026-11-02, mock provider only)
Version: `shadowcode 0.2.0` (`./shadowcode --version` OK).
Compile: `python3 -m py_compile main.py shadowcode_pkg/*.py tests/*.py` — OK.

### pytest suite (no pytest install needed)
`python3 tests/run_tests.py` — **10 passed, 0 failed**:
stream reassembly, native JSON tool-call parsing, mock agent
loop, diff_edit (no write), dry-run mode (no write), path
confinement, plan/destructive permissions, compact, MCP dummy
local, MCP refuses remote/outside.
Bug found and fixed during testing: the MCP local-file rule
first rejected `["python3", "mcp_dummy_server.py"]` because it
only accepted the command itself as a file. Fixed in `mcp.py`:
a plain interpreter running a script inside the workdir is
allowed; curl/URLs/outside paths are still refused. Re-tested:
10/10 pass.

### CLI mock checks
- One-shot `--no-stream "list files"` → `created.txt, hello.txt, screenshots`.
- `--dry-run "write file created.txt"` → `dry-run: would write
  created.txt (22 chars), not written`; file timestamp unchanged
  (not overwritten).
- Streaming one-shot `"read file hello.txt"` → `TOOL: read_file`
  streamed, then `Done. Tool read_file returned: hello shadowcode`
  on its own line (newline fix in `agent.py` after streaming).
- REPL piped `/compact` on an empty history → `0 messages
  removed, 0 kept` (correct, no crash).

### Browser + instant takeover (Playwright Firefox, existing venv)
- `open https://example.com` → 200, title `Example Domain`.
- `GET /state.json` → agent, example.com, `has_screenshot: true`;
  `GET /shot.png` → 81,823 bytes.
- `POST /takeover` → user driving; `POST /control {x:640,y:360}`
  → `accepted: browser thread will act promptly`; state after
  1.5s with NO agent call in between already showed USER DRIVING
  (old queued design would only have acted on the next agent
  call). Click on a blank area of example.com correctly changed
  nothing.
- Agent `browser_open` while USER DRIVING → paused message
  (correct); agent `browser_read` while USER DRIVING still works.
- `POST /handback` → agent driving; agent read works again.
- `browser_screenshot` → `test-workspace/screenshots/screenshot.png`
  (80K, refreshed); `browser_close` → closed, clean exit.
- Screenshot pump: preview `/shot.png` stays current while the
  agent is idle (browser thread snapshots every second).

## Cycle 3 never-stop (mock provider only, no live key)
Version: `shadowcode 0.3.0` (`./shadowcode --version` OK).
Compile: `python3 -m py_compile main.py shadowcode_pkg/*.py tests/*.py` — OK.

### Tests
`python3 tests/run_tests.py` — **13 passed, 0 failed** (previous
10 + TUIState header/tools/wrapping, browser watch log with a
fake page, browser_watch tool dispatch).
Plain REPL still works: `./shadowcode --no-tui --provider mock
--workdir test-workspace "list files"` → created.txt, hello.txt,
screenshots. `--tui` with piped stdin (no TTY) → `TUI unavailable
(setupterm: could not find terminal); falling back to plain
REPL`, then plain REPL exits cleanly — TUI never blocks CLI.
A real interactive curses TUI session was NOT run (no TTY in
this environment); TUIState logic is unit-tested, and the
curses renderer is the only untested-by-hand part — recorded
honestly here.

### Browser — Muse-AI parity sequence (Playwright Firefox, venv)
Test script `/tmp/test_browser_handback.py` (not shipped):
- Agent `browser_open https://example.com` → 200, Example Domain.
- Preview `POST /takeover` → driver `user`.
- User drives via preview URL bar: `POST /control
  {action: "goto", url: "https://www.iana.org/help/example-domains"}`.
  First run looked like a failure after 2s: state was still
  example.com. Diagnosis: goto was not failing, it was slow
  through the sandbox proxy (page load >2s). Re-run with a
  15s wait: state became IANA, title `Example Domains`,
  driver `user`, watch log gained a user-driven IANA entry.
  Fix shipped for this class of bug: `_exec_control` no longer
  swallows exceptions silently; `last_control_error` is in
  `/state.json`.
- Agent `browser_watch` while USER DRIVING → current IANA page
  + watch log (example.com agent, IANA user), no reload.
- Agent `browser_open` while USER DRIVING → paused message
  (correct).
- Preview `POST /handback` → driver `agent`; agent
  `browser_watch` / `browser_read` after handback → still
  IANA (`Example Domains`, IANA page content), NOT reloaded
  to example.com. Handback sequence: **OK**.
- `browser_close` → clean exit.

## Cycle 4 never-stop (mock provider only, no live key)
Version: `shadowcode 0.4.0` (`./shadowcode --version` OK).
Compile: `python3 -m py_compile main.py shadowcode_pkg/*.py tests/*.py` — OK.

### Tests
`python3 tests/run_tests.py` — **16 passed, 0 failed** (previous
13 + session export/search/collision, ambiguous-prefix load,
browser new-tool dispatch/safeguards).
`python3 tests/verify_packaging.py` — **packaging verification: OK**
(all py_compile, name/version, entry point `shadowcode =
"main:main"` callable, package version matches pyproject,
packages exist, README non-empty). It does NOT run
`pip install -e .` — that install is still a morning approval.
Bug caught by the packaging check: `pyproject.toml` still said
0.2.0 while `shadowcode_pkg/__init__.py` said 0.3.0. Fixed by
bumping both to 0.4.0 for cycle 4.
Bug found during manual CLI testing: REPL `/export` with no id
crashed with `list index out of range`. Fixed in both REPL and
TUI: it now prints `usage: /export <id> [md|json]`.

### Browser — cycle 4, live (Playwright Firefox, existing venv)
Test script `/tmp/test_browser_cycle4.py` (not shipped) + local
fixture `test-workspace/form.html` (shipped, non-sign-in form):
- `browser_click_selector "text=Learn more"` on example.com →
  IANA `Example Domains`; `browser_navigate back` → example.com;
  `browser_scroll down 400` → OK.
- Local form: `browser_fill_selector "#q"` → filled;
  `browser_fill_form {"#other": "second"}` (no submit) → filled;
  `browser_fill_form {"#q": "submitted-value"}` with submit →
  page shows `submitted:submitted-value` (form submit works for
  a non-sign-in form).
- Safeguard: `browser_fill_selector "input[type=password]"` →
  `refused: password/payment fields are not filled by Shadowcode`.
- `browser_scroll {"selector": "#bottom"}` → OK; preview
  `/state.json` correct with watch log; `browser_close` clean.

### Session export/search/collision — live CLI checks
- `./shadowcode --export-session cycle4test` → Markdown with
  session id, provider, and all messages; `--export-format json`
  → JSON of the same session.
- `./shadowcode --search-sessions "form.html"` → matching
  sessions with snippets.
- Fresh start `--session-id cycle4test` when that id exists →
  `session id cycle4test already exists, using cycle4test-2
  instead`; the original file was NOT overwritten (both files
  present afterwards).
- REPL: `/sessions hello` (search), `/export cycle4test`,
  `/export` with no id → usage line (fixed, see above).
- Test sessions created for these checks (`cycle4test`,
  `cycle4test-2`) were deleted afterwards, so the user's real
  session list is not polluted.

### Not tested live in cycle 2 (deferred, see MORNING_APPROVALS.md)
- No cloud provider live test (no key, none invented).
- No live Ollama server/model (binary exists, server not started
  overnight — install/download step deferred).
- No real pytest run (pytest not installed; run_tests.py used).
- No `pip install -e .` (install step deferred).
- No MCP HTTP server (refused by design; stdio local only).

## Cycle 5 (never-stop) + polyglot pivot — 2026-11-02

Python core, mock provider only (no live key, no faked live test):
- `python3 tests/run_tests.py` — **19 passed, 0 failed** (was 16;
  +3 cycle-5 tests: TUI status/tool/history/help/scroll, session
  export-file + date filter + read-only list, browser typed-fill
  + visibility). One bug found and fixed during the run: the new
  session test used `pathlib.Path` without importing pathlib;
  fixed to use the file's existing `Path` import.
- `--json-lines` bridge added to `main.py` and verified live:
  `./shadowcode --json-lines --no-tui --provider mock --workdir
  test-workspace "list files"` emits token/tool/final/session
  JSON lines, with the tool result listing the test-workspace files.
- Browser live (Playwright Firefox, existing venv, local
  `test-workspace/form.html` fixture, no sign-in):
  `browser_fill_form {#q: hello, #color: blue, #agree: yes,
  submit: True}` → `submitted:q=hello,color=blue,agree=true`
  (values verified, not just "filled");
  hidden click → "hidden: not clicked, not forced";
  disabled fill → "disabled: not filled, not forced";
  missing selector → "not found: not clicked, not forced";
  scroll to `#bottom` → "in view"; screenshot
  `test-workspace/screenshots/cycle5-form.png` (8.0K).

TypeScript TUI (Ink 8 + React 19, TS 7 strict):
- `npm run build` (tsc) clean, `npm run typecheck` (tsc --noEmit)
  clean, `npm test` (vitest) **4 passed, 0 failed**.
  Two bugs found and fixed: a spawn-stdio type error in
  `agent.ts`, and a final-dedup test expectation (a final after
  a tool call is a *new* assistant turn, not a duplicate).
- Non-TTY run: `./bin/shadowcode-tui` piped → fallback message,
  exit 0, no crash.
- Ink/React were installed inside `tui/` only (`npm install`
  succeeded); no install outside the project was needed for TS.

Go service (`go/`): source is real and stdlib-only, but `go`
is NOT installed in this environment and installing a toolchain
outside the project needs user approval — so `go build` was
NOT run and no Go binary is claimed. See MORNING_APPROVALS.md.
Python preview (`/state.json`, `/shot.png`) remains the working
preview until the Go binary is built.

Native C++ (`native/`): `make` builds `shadowcode-native` +
`libshadowcode_native.so` (g++ 13, C++17); `make test` passes;
ctypes check: `sc_fuzzy_score("scd","shadowcode") = 41`,
`sc_fuzzy_score("xyz","shadowcode") = 0`.

Top-level: `make build-all` / `test-all` orchestrate the above;
`docs/ARCHITECTURE.md` documents language roles and protocols.

## Cycle 6 never-stop (mock provider only, no live key)
Version: `shadowcode 0.5.0` (`./shadowcode --version` OK).
Compile: `python3 -m py_compile main.py shadowcode_pkg/*.py tests/*.py` — OK.

### Python native fast path (cycle 6)
- `shadowcode_pkg/native_scanner.py` (new): CLI-subprocess fast
  path, NOT ctypes — the C library's printf would pollute the
  JSON-lines protocol if loaded in-process. Plain-substring
  queries only (gate: letters/digits/space/_/-/./); regex
  patterns stay in Python. Missing binary, any native error,
  or SHADOWCODE_NO_NATIVE=1 all fall back to Python.
- Live checks: `search_files("shadowcode")` in a temp workdir
  -> native hit `a.txt:1: hello shadowcode`; regex
  `hello\s+shadowcode` -> same hit via Python; `count_lines`
  -> lines=2 nonempty=2; `fuzzy_score("scd","shadowcode") > 0`,
  `fuzzy_score("zzz","shadowcode") == 0`; new tools
  `count_lines`/`fuzzy_score` are READ tools in permissions.py.
- `python3 tests/run_tests.py` — **21 passed, 0 failed** (was 19;
  +2 cycle-6 tests: native search/fallback, Go fallback).

### Go /search wiring (cycle 6) — optional, NOT built
- `go` is still NOT installed in this environment; no toolchain
  was installed, no Go binary was built, none is claimed.
- New `tui/src/lib/goSearch.ts`: `searchGo(port, q)` fetches
  `http://127.0.0.1:port/search`, returns hits or null on any
  failure; `goServerHealthy`, `goBinaryExists`, `formatGoHits`.
- New `tui/src/lib/coreCli.ts`: `--doctor`, `--search-sessions`,
  `--export-session` via the Python core, output verbatim.
- New `shadowcode_pkg/go_search.py`: same Go client in Python;
  `/go-search <q>` added to Python REPL + curses TUI + TS TUI.
- Live check (no server running): `search_go("shadowcode")`
  -> None; REPL `/go-search hello` -> "Go search unavailable
  on localhost:8765 (no Go server running; Go binary was not
  built here — see MORNING_APPROVALS.md). Python fallback:"
  followed by the real Python hits. The manual REPL session
  created for this check was deleted afterwards.
- TS: `npm run build` (tsc) clean; `npm test` (vitest)
  **8 passed, 0 failed** (was 4; +4 cycle-6: Go hit formatting,
  null-on-no-server, binary-absent, core doctor).

### TS/Python TUI parity (cycle 6)
- TS TUI HELP now lists the full Python command set:
  /sessions [query], /search-sessions, /export, /export-file,
  /resume, /compact (honest note: compaction lives in the
  Python core, TUI does not rewrite session files),
  /permissions (mode + subprocess note, no faked prompt),
  /browser (preview URL/driver from tool events),
  /mcp (local stdio note), /doctor, /go-search, /model,
  /provider, /tools, /clear, /exit, !cmd.
- Python REPL/TUI help updated with /go-search.
- PermissionPrompt in TS remains a component for a future
  interactive mode; in subprocess mode it is NOT used to fake
  an approval (same honesty note as PROTOCOL.md).
- `python3 tests/verify_packaging.py` — packaging: OK, after
  bumping pyproject + package to 0.5.0 in sync.

## Cycle 8 never-stop (mock/local only, no live key, no Go toolchain)
Version: `shadowcode 0.7.0` (core + pyproject + TS TUI bumped in sync).
Compile: `python3 -m py_compile main.py shadowcode_pkg/*.py tests/*.py` — OK.

### 1. TUI browser integration
- Python curses: `TUIState.set_browser()` now takes title, health,
  and watch log; `status_line()` shows
  `browser: <driver> <title> <url> health=<health>`; `browser_panel()`
  (via `health.format_browser_panel`) prints fresh state +
  takeover/handback hints + watch tail (last 5). Tool events for
  `browser_*` refresh the TUI browser state from the running
  browser thread.
- TS TUI: Header now shows browser preview URL + driver + health
  + page title; StatusBar shows preview health/port/driver +
  page title/URL (truncated); the 3s poll now also stores the
  watch log and page URL. `/browser` prints
  `formatBrowserPanel()` (same shape as Python, not a different
  summary): state, preview URL, takeover/handback hints, watch
  tail, last_control_error when present.
- Fix found in this cycle: the old TS `fetchPreviewState`
  required /health JSON, so a live Python preview (which serves
  /state.json but HTML for /health) was reported unavailable.
  It now falls back to /state.json when /health fails, and only
  then reports unavailable. Go is still identified only by
  /health JSON `{"ok": true}` — a Python preview is never
  mislabelled as Go.

### 2. Sessions view
- New `session.sessions_view(query)` (read-only): list or search
  rows + action hints (/resume, /export, /export-file,
  /session-info, /compact current-session-only). Unit test
  verifies the file list is unchanged after a view call.
- New commands in REPL, Python TUI, and TS TUI:
  `/sessions-view [query]`, `/session-info <id>`. TS reaches
  them through the existing core flags (--list-sessions,
  --search-sessions, --session-info), so no TS code edits a
  session file. Resume still loads in memory; compact/export
  remain the only approved mutating paths.

### 3. Health dashboard
- New `shadowcode_pkg/health.py`: `health_status()` /
  `format_health()` / `format_browser_panel()` /
  `preview_probe()`. New `--health` flag and `/health` command
  in REPL, Python TUI, and TS TUI (TS calls `--health` via
  coreCli and appends Ink/React + Go-binary notes).
- Live `--health` output in this environment (honest):
  python core OK 0.7.0, TS TUI package 0.7.0 built=yes
  node=available, Go preview binary=no server=unavailable,
  preview server port 8765 unavailable, native scanner
  available, Playwright NOT available under system python3
  (browser tests used the Playwright venv, see below).
- REPL live checks: `/browser` with no browser running prints
  "not started (no live page yet)" + health unavailable +
  the Playwright-missing reason (no fake page, no browser
  started by the command itself); `/health` prints the
  dashboard; `/sessions-view` prints the saved-session list +
  action hints. The test session created by that REPL run was
  deleted afterwards.

### 4. Browser panel — live (Playwright Firefox, existing venv)
- `browser_open https://example.com` → 200, Example Domain,
  preview `http://localhost:8765`.
- `preview_probe(8765)` → preview_server=True, go_server=False
  (correctly distinguishes a Python preview from a Go server).
- `format_browser_panel(state, preview_url, "healthy")` →
  health/title/URL/driver/has_screenshot=True, takeover +
  handback hints, watch log "00:39:34 Example Domain —
  https://example.com/ (agent)".
- `browser_watch` after open → "resuming from current page
  (no reload)" + current IANA-free example.com page content.
- `browser_close` → clean exit.

### Tests — all passing
- `python3 tests/run_tests.py` — **23 passed, 0 failed** (was 22;
  +1 cycle-8: TUI browser panel/status, health dashboard,
  sessions view read-only).
- `python3 tests/verify_packaging.py` — packaging: OK
  (0.7.0 in sync across pyproject, package, and TS TUI).
- TS: `npm run build` (tsc) clean; `npm test` (vitest) —
  **13 passed, 0 failed** (was 11; +2 cycle-8: browser panel
  format + core --health components).

### Not tested live in cycle 8 (deferred, see MORNING_APPROVALS.md)
- No cloud provider live test (no key, none invented).
- No live Ollama server/model, no Go toolchain/binary, no
  `pip install -e .`, no pytest install, no system Playwright.
- No hand-driven curses or Ink TUI session on a real TTY
  (state/fallback only, as in earlier cycles).
- Free AI agents from other CLIs/websites: NOT researched in
  cycle 8, on purpose — deferred to tomorrow by the user.

## Cycle 7 never-stop (mock/local only, no live key, no Go toolchain)
Version: `shadowcode 0.6.0` (core + pyproject + TS TUI all bumped in
sync; TS TUI was 0.2.0 before this cycle — a version mismatch fixed
here, not just in the core).

### 1. TS TUI parity — coreCli doctor/search/export, fully wired
New Python exit-and-print flags (no session written, no provider
touched): `--list-sessions`, `--search-files <pattern>`,
`--compact-session <id>`, `--session-info <id>`,
`--mcp-servers`, `--mcp-tools <server>`, `--permissions`,
`--run-shell <cmd>`. TS `tui/src/lib/coreCli.ts` now wraps all of
them, and `tui/src/App.tsx` calls them for real:
- `/sessions` (no arg) used to be a hint; it now prints
  `--list-sessions`. `/sessions <q>` and `/search-sessions <q>
  [--from D] [--to D]` use `--search-sessions` with date filters.
- `/resume <id>` used to only set the id; it now prints
  `--session-info` (id/provider/model/message count) first.
- `/compact` used to be a note; with a session it now runs
  `--compact-session` on the session file (extractive, keep 10).
- `/permissions` now prints `--permissions` (mode + allow/deny +
  allowed/disallowed tools), instead of a mode-only line.
- `/mcp` / `/mcp <server>` now print `--mcp-servers` /
  `--mcp-tools`, instead of a hint.
- `!cmd` used to be a hint; it now runs `--run-shell` in the
  workdir, exactly like the Python REPL `!cmd`.
- `/go-search <q>` fallback used to say "ask the agent to search";
  it now runs `--search-files` (Python search_files, native fast
  path when present, pure Python otherwise) and prints the hits.
- Python curses TUI `/doctor` used to say "see --doctor output in
  plain mode"; it now captures doctor() output (redirect_stdout)
  and prints it inside the TUI. Python curses `/permissions`
  now shows allow/deny like the REPL.

### Go preview health display (TS TUI)
`fetchPreviewState(port)` in `tui/src/lib/goSearch.ts` polls
`/health` then `/state.json` on 127.0.0.1 only. `App.tsx` polls
every 3s; the StatusBar now shows
`preview localhost:<port> healthy|unavailable driver=<driver>`,
and `/browser` prints health + port + driver + title + URL +
has_screenshot from a fresh fetch. A failed poll is
"unavailable", never a faked healthy state. Go itself is still
unbuilt here (no toolchain, see MORNING_APPROVALS.md), so in this
environment the display honestly reads unavailable; the Python
preview server is the working preview when the browser runs.

### 2. Benchmark — pure Python vs native C++ search
`scripts/benchmark_search.py` (new): generates a temp tree, plants
a plain-substring needle, times pure Python (SHADOWCODE_NO_NATIVE=1)
vs the C++ CLI, reports hit counts alongside times, deletes the
tree afterwards. Mock/local data only, no live provider.
- Bug found by the first run: the script set
  SHADOWCODE_NO_NATIVE=1 and then ran the native timing under the
  same env, so native correctly refused and the comparison was
  empty. Fixed: the flag is popped before the native timing.
- 500 files x 100 lines, planted 50: Python median 41.5 ms,
  native 38.8 ms, hits 50 = 50, speedup 1.07x — on a small tree
  the native subprocess overhead dominates; no big win claimed.
- 2000 files x 200 lines, planted 200, cap 100 hits: Python
  median 250.3 ms, native 23.9 ms, hits 100 = 100, speedup
  10.47x. The cap binds both sides equally, so the comparison
  is fair; the win is real on large trees, negligible on small
  ones. Recorded honestly, not as a blanket "10x faster" claim.

### 3. Help/commands consistency check (all three UIs)
Compared Python REPL /help, Python curses help_text(), and TS
HELP, command by command. Two real mismatches found and fixed:
- Python REPL/curses `/search-sessions` ignored `--from/--to`
  while the TS TUI (and the CLI flag) supported them. Fixed with
  a shared `parse_search_args()` in main.py, used by REPL and
  curses; help strings updated in all three UIs.
- TS HELP said "Ctrl-C twice" while App.tsx exits on a single
  Ctrl-C. Fixed: help now says "Ctrl-C, or /exit, to quit."
- REPL/curses `/search-sessions` printed raw tuple repr while
  the CLI flag printed a formatted line. Fixed: REPL and curses
  now print the same `id provider=… messages=… updated=…
  snippet=…` format as the CLI flag and the TS TUI.
Remaining honest difference (documented, not hidden): TS
`/compact` compacts the saved session file via
`--compact-session`, while Python REPL/curses compact the live
in-memory messages; both are extractive, keep system + last 10.

### Tests — all passing
- `python3 -m py_compile main.py shadowcode_pkg/*.py tests/*.py` OK.
- `python3 tests/run_tests.py` — **22 passed, 0 failed** (was 21;
  +1 cycle-7 test for the new core flags, run in a subprocess
  with HOME pointed at a temp dir, because session_dir() is
  derived from Path.home() — the first version of that test
  monkeypatched session_dir in-process and failed, which was a
  test bug, not a core bug).
- `python3 tests/verify_packaging.py` — packaging: OK.
- TS: `npm run build` (tsc) clean; `npm test` (vitest) —
  **11 passed, 0 failed** (was 8; +3 cycle-7: core list/session-info,
  preview-state unavailable, core search-files).
- `./shadowcode --version` → `shadowcode 0.6.0`.

## Cycle 9 never-stop (mock/local only, no live key, no Go toolchain)
Version: `shadowcode 0.8.0` (core + pyproject + TS TUI bumped in sync).
Compile: `python3 -m py_compile main.py shadowcode_pkg/*.py tests/*.py` — OK.

### 1. Browser watch replay
- New `Browser.full_watch()` / `full_watch_text()` /
  `format_watch_log()` / `load_saved_watch_log()`: full log in
  order, driver transitions (`agent -> user`, `user -> agent`)
  marked, saved per session to
  `<workdir>/.shadowcode/browser-watch-<timestamp>-<pid>.json`
  on every new entry and on close. `/state.json` now also
  carries `watch_count` and `watch_file`.
- New agent tool `browser_watch_replay` (READ, no reload, no
  page body) and `/browser-watch` in REPL, Python TUI, and TS
  TUI (CLI `--browser-watch`, read-only, does not start a
  browser). Live thread first, saved file second, honest
  "no watch log yet" third — never an invented log.
- Unit test with a fake page: 3 entries (agent, user, agent),
  full replay shows both transitions, saved file reloads the
  same 3 entries, missing workdir gives (None, []).
- Live CLI check (no browser running): `--browser-watch`
  prints "no watch log yet" with the saved-log path, correctly
  (no fake page, no browser started).

### 2. Sessions-view actions
- New `session.parse_sessions_view_action()` /
  `sessions_view_selected()` and `main.sessions_view_dispatch()`:
  `/sessions-view <id> info | export [md|json] |
  export-file [md|json] [path] | resume` in REPL, Python TUI,
  and TS TUI (TS via existing core flags, no TS code edits a
  session file). Info/export are read-only; resume loads in
  memory; export-file is the approved export path.
- Unit test: parse list/select/action/search, info/export/
  resume dispatch, and a file-list check proving no session
  file was created or modified by any of them.
- Live REPL check (real saved session bb722c819716, 12
  messages): `/sessions-view <id> info` prints the info line,
  `/sessions-view <id> export md` prints the full Markdown
  export, `/sessions-view <id> resume` prints "resumed … (12
  messages)". Test sessions created by these REPL runs were
  deleted afterwards. Note found during testing: the sessions
  directory contains a pre-existing oddly named file
  (a backslash-n prefix before cycle4test.json, JSON id
  cycle4test) — not created by cycle 9, left untouched.

### 3. Health history
- New `health.append_health_snapshot()` /
  `read_health_history()` / `format_health_history()` /
  `health_history_path()`: every `/health` / `--health`
  appends one snapshot (no keys) to
  `<workdir>/.shadowcode/health-history.jsonl`, capped at the
  last 100; `/health-history [n]` (CLI `--health-history [n]`,
  TS via coreCli) shows the last n, newest first, default 10,
  clamped 1..50. Missing log is "no snapshots yet".
- Unit test: append twice, read newest-first, limit clamping
  (0 -> 1), empty log honest.
- Live CLI checks: `--health` appends a snapshot to
  `test-workspace/.shadowcode/health-history.jsonl`;
  `--health-history` prints it (newest first, provider=mock,
  preview=unavailable); REPL `/health-history 2` prints the
  same file. No key appears in any snapshot.

### Tests — all passing
- `python3 tests/run_tests.py` — **26 passed, 0 failed** (was
  23; +3 cycle-9: browser watch replay + saved log,
  sessions-view actions, health history).
- `python3 tests/verify_packaging.py` — packaging: OK
  (0.8.0 in sync across pyproject, package, and TS TUI).
- TS: `npm run build` (tsc) clean; `npm test` (vitest) —
  **14 passed, 0 failed** (was 13; +1 cycle-9: core
  health-history + browser-watch flags).

### Not tested live in cycle 9 (deferred, see MORNING_APPROVALS.md)
- No live browser replay with a real Playwright page (the
  replay logic is unit-tested with a fake page and via the
  saved-file path; a live takeover -> replay re-check is a
  cycle-10 item).
- No cloud provider live test, no live Ollama, no Go toolchain/
  binary, no `pip install -e .`, no pytest install, no system
  Playwright, no hand-driven TTY session.
- Free AI agents from other CLIs/websites: NOT researched in
  cycle 9, on purpose — deferred to tomorrow by the user.

## Cycle 10 never-stop (mock/local only, no live key, no Go toolchain)
Version: `shadowcode 0.9.0` (core + pyproject + TS TUI bumped in sync).
Compile: `python3 -m py_compile main.py shadowcode_pkg/*.py tests/*.py` — OK.

### 1. Live browser replay with a real Playwright page (NOT faked)
- Script: /tmp/cycle10_live_replay.py (not shipped), run with
  the existing Playwright venv python
  (~/workspace/instagram-auto-signup/.venv/bin/python), NOT
  system Python. Browser workdir: test-workspace, preview
  127.0.0.1:8765, Firefox, ignore_https_errors (sandbox egress MITM).
- Sequence, all observed live: agent `browser_open
  https://example.com` -> 200, "Example Domain"; preview POST
  /takeover -> driver user; preview POST /control goto
  https://www.iana.org/help/example-domains -> IANA (reached
  within the poll, no proxy-slowness retry needed this run);
  agent `browser_watch` while USER DRIVING -> current IANA
  page + watch log, no reload; agent `browser_open` while
  USER DRIVING -> paused message (correct); preview POST
  /handback -> driver agent; agent `browser_watch` /
  `browser_read` after handback -> STILL IANA, "Example
  Domains" content, NOT reloaded to example.com; close clean.
- Honest gap found and FIXED in this cycle: the first live
  run's saved log had only agent + user entries — handback
  changed no URL/title, so no entry was recorded, and the
  replay showed agent -> user but never user -> agent. Fix:
  `Browser.record_driver_change()` in shadowcode_pkg/browser.py,
  called from the preview /takeover and /handback handlers:
  a driver change on an existing page appends its own watch
  entry (same page, new driver), saved immediately; no-op if
  there is no page yet or the driver is unchanged.
- Second live run, after the fix, saved log file:
  test-workspace/.shadowcode/browser-watch-20261102-004908-30363.json
  — 4 entries: (1) agent example.com, (2) user example.com
  (takeover), (3) user IANA (user-driven goto), (4) agent
  IANA (handback). Replay shows BOTH transitions:
  "driver transition: agent -> user" and
  "driver transition: user -> agent". /browser-watch after
  handback still shows the current IANA page.
- The earlier (pre-fix) run's log file
  browser-watch-20261102-004831-30060.json remains in
  test-workspace/.shadowcode/ as evidence of the gap; it was
  NOT edited to hide it.

### 2. TS TUI polish: browser watch panel + health-history panel
- New `tui/src/lib/replay.ts`: `formatReplayEntries()` (same
  shape as Python format_watch_log, transitions marked),
  `countTransitions()`, `readSavedWatchLog()` (most recent
  <workdir>/.shadowcode/browser-watch-*.json by mtime, parsed
  and validated; missing/unreadable -> (null, [])), and
  `healthHistoryLines()` (core output verbatim, split, never
  invented).
- New components `tui/src/components/BrowserWatchPanel.tsx`
  (full replay, cyan border) and
  `tui/src/components/HealthHistoryPanel.tsx` (health-history
  output, green border), wired in `tui/src/App.tsx`:
  `/browser-watch-replay` shows the full saved replay panel
  AND the same lines in the transcript; `/browser-watch-hide`
  hides it; `/health-history [n]` now also shows the
  health-history panel; `/health-history-hide` hides it.
  `/browser-watch` (existing, core flag) is unchanged.
  Note the panel source: the SAVED log, not the live
  /state.json 10-entry tail — the tail must never be
  presented as the full replay.
- TS tests: new `tui/tests/replay.test.ts` (3 tests: both
  transitions formatted + counted, saved-log read + missing
  log honest, health-history lines verbatim).

### Tests — all passing
- `python3 tests/run_tests.py` — **27 passed, 0 failed** (was
  26; +1 cycle-10: driver-change entries, duplicate-driver
  no-op, no-page no-op, both transitions in formatted log).
- `python3 tests/verify_packaging.py` — packaging: OK
  (0.9.0 in sync across pyproject, package, and TS TUI).
- TS: `npm run build` (tsc) clean; `npm test` (vitest) —
  **17 passed, 0 failed** (was 14; +3 cycle-10 replay tests).

### Not tested live in cycle 10 (deferred, see MORNING_APPROVALS.md)
- No cloud provider live test, no live Ollama, no Go toolchain/
  binary, no `pip install -e .`, no pytest install, no system
  Playwright, no hand-driven TTY session (TS Ink TUI and
  Python curses TUI still tested for fallback/state only).
- Free AI agents from other CLIs/websites: NOT researched in
  cycle 10, on purpose — deferred to tomorrow by the user.

## Cycle 11 never-stop (mock/local only, no live key, no Go toolchain)
Version: `shadowcode 0.10.0` (core + pyproject + TS TUI bumped in sync).
Compile: `python3 -m py_compile main.py shadowcode_pkg/*.py tests/*.py` — OK.

### 1. Live browser replay on a second site (NOT faked)
- Script: /tmp/cycle11_live.py (not shipped), run with the existing
  Playwright venv python (~/workspace/instagram-auto-signup/.venv/bin/python),
  NOT system Python. Browser workdir: test-workspace, preview
  127.0.0.1:8765/8766, Firefox, ignore_https_errors (sandbox egress MITM).
- Site choice, honestly: wikipedia.org was tried first and its
  agent goto timed out at 30s with an empty preview state, and a
  probe script showed the same 30s timeout for w3.org and
  neverssl.com through this sandbox proxy, while httpbin.org/html
  opened in 2.9s and example.org in 1.8s. So the second site is
  httpbin.org, not a site that was claimed to load when it did not.
  Probe logs (browser-watch-20261102-010413/010529/010604) remain in
  test-workspace/.shadowcode/ and are probe artefacts, not replay
  evidence; the cycle 11 replay logs below are the evidence.
- Sequence, all observed live: agent `browser_open
  https://httpbin.org/html` -> opened, title '' (httpbin /html has
  no <title>, its heading is Moby-Dick text); preview POST
  /takeover -> driver user; preview POST /control goto
  https://httpbin.org/headers -> headers page, driver user;
  agent `browser_watch` while USER DRIVING -> current headers
  page + watch log, no reload; preview POST /handback -> driver
  agent; agent `browser_watch` / `browser_watch_replay` after
  handback -> STILL headers, NOT reloaded to /html; close clean.
- Saved log: test-workspace/.shadowcode/browser-watch-20261102-011458-34759.json
  — 4 entries: (1) agent /html, (2) user /html (takeover),
  (3) user /headers (user-driven goto), (4) agent /headers
  (handback). Replay shows BOTH transitions.

### 2. Live no-navigation takeover/handback (NOT faked)
- Same script, second run: agent opened https://httpbin.org/html
  (preview 8766, the next free port); preview POST /takeover ->
  driver user; NO navigation (2s wait, state still /html);
  agent `browser_watch` while USER DRIVING -> current /html +
  watch log, no reload; preview POST /handback -> driver agent;
  agent `browser_watch` / `browser_watch_replay` after handback
  -> STILL /html, Moby-Dick content, NOT reloaded to another page.
- Saved log: test-workspace/.shadowcode/browser-watch-20261102-011511-34759.json
  — 3 entries, all https://httpbin.org/html: (1) agent,
  (2) user (takeover), (3) agent (handback). Replay shows BOTH
  transitions on the same page. This is the case cycle 10's
  driver-change fix was for, now proven live with zero navigation.

### 3. TUI replay-panel polish
- TS: `tui/src/components/BrowserWatchPanel.tsx` header now reads
  "Browser watch replay (full) — N entries, M driver transitions"
  via `countTransitions()` (lib/replay.ts); rebuilt with
  `npm run build` (tsc clean) so dist/ matches src/.
- Python: new `/browser-watch-replay` command in BOTH the curses
  TUI loop and the plain REPL loop in main.py (full saved replay
  on demand, same browser_watch_text as /browser-watch), plus the
  command in both /help strings and in the Python TUI help overlay
  (shadowcode_pkg/tui.py). Verified live via piped REPL:
  `/browser-watch-replay` printed the 3-entry no-navigation log
  with both transitions; the throwaway session file created by
  that piped run was deleted afterwards.

### Tests — all passing
- `python3 tests/run_tests.py` — **28 passed, 0 failed** (was 27;
  +1 cycle 11: no-navigation replay, same page, both transitions).
- `python3 tests/verify_packaging.py` — packaging: OK (0.10.0 in sync).
- TS: `npm run build` (tsc) clean; `npm test` (vitest) —
  **18 passed, 0 failed** (was 17; +1 cycle 11: no-navigation
  transition count + same-page check).

### Not tested live in cycle 11 (deferred, see MORNING_APPROVALS.md)
- No cloud provider live test, no live Ollama, no Go toolchain/
  binary, no `pip install -e .`, no pytest install, no system
  Playwright, no hand-driven TTY session.
- Free AI agents from other CLIs/websites: NOT researched in
  cycle 11, on purpose — deferred to tomorrow by the user.

## Cycle 12 never-stop (mock/local only, no live key, no Go toolchain)
Version: `shadowcode 0.11.0` (core + pyproject + TS TUI bumped in sync).
Compile: `python3 -m py_compile main.py shadowcode_pkg/*.py tests/*.py` — OK.

### 1. Live browser replay on a third site — CLICK, not goto (NOT faked)
- Script: /tmp/cycle12_live.py (not shipped), run with the existing
  Playwright venv python (~/workspace/instagram-auto-signup/.venv/bin/python),
  NOT system Python. Browser workdir: test-workspace, preview
  127.0.0.1:8765, Firefox, ignore_https_errors (sandbox egress MITM).
- Third site choice, honestly: https://www.iana.org/ — titled
  ("Internet Assigned Numbers Authority"), with an internal link
  "Domain Names" (href /domains) in the viewport. A separate probe
  of the same page layout gave that link's box x=201..332, y=346..370
  (1280x720 viewport), centre (266,358); the live test clicked that
  centre via the preview screenshot click (POST /control {x:266,
  y:358}), NOT a goto, NOT an agent click_selector.
- Sequence, all observed live: agent `browser_open
  https://www.iana.org/` -> title "Internet Assigned Numbers
  Authority", URL https://www.iana.org/; preview POST /takeover ->
  driver user; preview POST /control click (266,358) -> after a
  load wait, URL https://www.iana.org/domains, title "Domain Name
  Services", driver user; agent `browser_watch` while USER DRIVING
  -> current /domains + watch log, no reload; agent `browser_open`
  while USER DRIVING -> paused message (correct); preview POST
  /handback -> driver agent; agent `browser_watch` /
  `browser_watch_replay` after handback -> STILL /domains, "Domain
  Name Services" content, NOT reloaded to the homepage; close clean.
- Saved log: test-workspace/.shadowcode/browser-watch-20261102-012015-36840.json
  — 5 entries: (1) agent iana.org, (2) user iana.org (takeover),
  (3) user Loading https://www.iana.org/domains on the old URL, via
  preview click (266,358) [click-driven], (4) user /domains, via
  preview click (266,358) [click-driven], (5) agent /domains
  (handback). Replay shows BOTH transitions plus the click marker
  on the destination entry.
- Bug found and fixed during this cycle: the first live run
  marked only the intermediate "Loading …" entry as click-driven,
  because _pending_via was cleared on the first title change, before
  the URL landed. Fixed in shadowcode_pkg/browser.py: via is kept
  until the URL itself changes, then cleared. Re-run after the fix
  produced the 5-entry log above, with the destination marked.
  A second small fix in the same cycle: `Browser.watch()` printed
  a stray "via " for entries with no via; now it prints via only
  when present.
- Piped REPL check: `/browser-watch-replay` printed the same
  5-entry saved log with both transitions and both click-driven
  entries; the throwaway session file from that piped run was
  deleted afterwards.

### 2. Replay polish — /browser-watch-replay shows click-driven entries clearly
- Python: `format_watch_log()` appends " via <via>" and
  " [click-driven]" for click vias; `Browser.watch()` and the
  health browser-panel tail do the same; preview controls set
  `_pending_via` (preview click/goto/back/forward/type/key, plus
  new preview click_text/click_selector actions in _exec_control,
  real element clicks in the browser thread, not gotos).
- TS: `ReplayEntry.via`, `formatReplayEntries()` with the same
  marker, `readSavedWatchLog()` preserves via, new
  `countClickDriven()`, and BrowserWatchPanel header now reads
  "N entries, M transitions, K click-driven" when K > 0.
- Python TUI /browser-watch-replay flows through the same
  format_watch_log, so it shows the marker without a separate
  implementation; the health panel tail shows it too.

### Tests — all passing
- `python3 tests/run_tests.py` — **29 passed, 0 failed** (was 28;
  +1 cycle 12: click-driven replay formatting, goto vs click).
- `python3 tests/verify_packaging.py` — packaging: OK (0.11.0 in sync).
- TS: `npm run build` (tsc) clean; `npm test` (vitest) —
  **19 passed, 0 failed** (was 18; +1 cycle 12: click-driven
  formatting + countClickDriven).

### Not tested live in cycle 12 (deferred, see MORNING_APPROVALS.md)
- No cloud provider live test, no live Ollama, no Go toolchain/
  binary, no `pip install -e .`, no pytest install, no system
  Playwright, no hand-driven TTY session.
- Free AI agents from other CLIs/websites: NOT researched in
  cycle 12, on purpose — deferred to tomorrow by the user.

## Cycle 13 never-stop (mock/local only, no live key, no Go toolchain)
Version: `shadowcode 0.12.0` (core + pyproject + TS TUI bumped in sync).
Compile: `python3 -m py_compile main.py shadowcode_pkg/*.py tests/*.py` — OK.

### 1. Live browser replay on a fourth site — scroll THEN click (NOT faked)
- Script: /tmp/cycle13_live.py (not shipped), run with the existing
  Playwright venv python (~/workspace/instagram-auto-signup/.venv/bin/python),
  NOT system Python. Browser workdir: test-workspace, preview
  127.0.0.1:8765, Firefox, ignore_https_errors (sandbox egress MITM).
- Fourth site choice, honestly: python.org, NOT example.com/IANA,
  httpbin.org, or iana.org. Probes first showed developer.mozilla.org,
  rfc-editor.org, and icann.org timing out at 30s through this sandbox
  proxy, while python.org opened promptly and has a below-the-fold
  internal link — so python.org was used, and the timed-out sites
  were NOT claimed to load. A separate probe of the same page layout
  gave the "Start with our Beginner's Guide" link (href
  /about/gettingstarted/) at top 927, left 84, 194x19 (1280x720
  viewport), i.e. below the fold; after a 600px wheel scroll it was
  at top 327, centre (181,336) — the coordinates the live test used.
- Sequence, all observed live: agent `browser_open
  https://www.python.org/` -> title "Welcome to Python.org";
  preview POST /takeover -> driver user; preview POST /control
  {action: "scroll", direction: "down", amount: 600} -> state still
  python.org, watch_count 3, with a new user entry "via preview
  scroll down" (before cycle 13 a scroll would have logged nothing,
  because it changes no URL/title); preview POST /control click
  (181,336) -> after a load wait, URL
  https://www.python.org/about/gettingstarted/, title "Python For
  Beginners | Python.org", driver user; agent `browser_watch`
  while USER DRIVING -> current /about/gettingstarted/ + watch log
  (scroll + both click-driven entries), no reload; agent
  `browser_open` while USER DRIVING -> paused message (correct);
  preview POST /handback -> driver agent; agent `browser_watch` /
  `browser_watch_replay` after handback -> STILL
  /about/gettingstarted/, "Python For Beginners" content, NOT
  reloaded to the homepage; close clean.
- Saved log: test-workspace/.shadowcode/browser-watch-20261102-013724-40129.json
  — 6 entries: (1) agent python.org, (2) user python.org (takeover),
  (3) user python.org via preview scroll down [scroll],
  (4) user Loading https://www.python.org/about/gettingstarted/ on
  the old URL, via preview click (181,336) [click-driven],
  (5) user /about/gettingstarted/, via preview click (181,336)
  [click-driven], (6) agent /about/gettingstarted/ (handback).
  Replay shows BOTH transitions plus the scroll marker plus the
  click markers.
- Piped REPL check was not re-run for this log in this cycle; the
  saved log itself was reloaded with load_saved_watch_log() in
  the live script and printed in full (6 entries, same content
  as the replay above).

### 2. Scroll polish — Python + TS
- Python: `Browser.record_action_entry(via)` (browser.py) records
  the current page for preview wheel/scroll_to and agent
  browser_scroll; `format_watch_log()`, `Browser.watch()`, and
  the health browser-panel tail mark scroll vias `[scroll]`;
  preview page gains Scroll down / Scroll up buttons and shows
  `via` in its watch list. A scroll entry is never marked
  click-driven.
- TS: `formatReplayEntries()` marks scroll vias `[scroll]`,
  new `countScroll()`, and BrowserWatchPanel header adds
  ", S scroll" when S > 0. Rebuilt with `npm run build` (tsc clean).

### Tests — all passing
- `python3 tests/run_tests.py` — **30 passed, 0 failed** (was 29;
  +1 cycle 13: scroll entries recorded + marked, no-page no-op,
  scroll vs click markers kept apart).
- `python3 tests/verify_packaging.py` — packaging: OK (0.12.0 in sync).
- TS: `npm run build` (tsc) clean; `npm test` (vitest) —
  **20 passed, 0 failed** (was 19; +1 cycle 13: scroll formatting
  + countScroll, scroll not click-marked).

### Not tested live in cycle 13 (deferred, see MORNING_APPROVALS.md)
- No cloud provider live test, no live Ollama, no Go toolchain/
  binary, no `pip install -e .`, no pytest install, no system
  Playwright, no hand-driven TTY session.
- Free AI agents from other CLIs/websites: NOT researched in
  cycle 13, on purpose — deferred to tomorrow by the user.

## Cycle 14 never-stop (mock/local only, no live key, no Go toolchain)
Version: `shadowcode 0.13.0` (core + pyproject + TS TUI bumped in sync).
Compile: `python3 -m py_compile main.py shadowcode_pkg/*.py tests/*.py` — OK.

### 1. Live browser replay on a fifth site — scroll_to THEN click_text (NOT faked)
- Script: /tmp/cycle14_live.py (not shipped), run with the existing
  Playwright venv python (~/workspace/instagram-auto-signup/.venv/bin/python),
  NOT system Python. Browser workdir: test-workspace, preview
  127.0.0.1:8765, Firefox, ignore_https_errors (sandbox egress MITM).
- Fifth site choice, honestly: gnu.org, NOT example.com/IANA,
  httpbin.org, iana.org, or python.org. A probe first showed
  w3.org timing out at 30s through this sandbox proxy, while
  gnu.org, apache.org, pypi.org, and kernel.org all loaded, so
  gnu.org was used and w3.org was NOT claimed to load. A probe
  of the same page layout gave the "Try GNU/Linux" link (href
  /distros/free-distros.html) at top 836, left 77, i.e. below
  the fold in a 1280x720 viewport.
- Sequence, all observed live: agent `browser_open
  https://www.gnu.org/` -> title "The GNU Operating System and
  the Free Software Movement"; preview POST /takeover -> driver
  user; preview POST /control {action: "scroll_to", selector:
  "text=Try GNU/Linux"} -> state still gnu.org, watch entry
  "via preview scroll to text=Try GNU/Linux" [scroll]; preview
  POST /control {action: "click_text", text: "Try GNU/Linux"}
  -> after a load wait, URL
  https://www.gnu.org/distros/free-distros.html, title "List of
  Free GNU/Linux Distributions - GNU Project - Free Software
  Foundation", driver user — NOT a coordinate click, NOT a
  goto; agent `browser_watch` while USER DRIVING -> current
  free-distros page + watch log, no reload; agent
  `browser_open` while USER DRIVING -> paused message (correct);
  preview POST /handback -> driver agent; agent `browser_watch`
  / `browser_watch_replay` after handback -> STILL
  /distros/free-distros.html, "Free GNU/Linux distributions"
  content, NOT reloaded to the homepage; close clean.
- Saved log: test-workspace/.shadowcode/browser-watch-20261102-015032-42148.json
  — 5 entries: (1) agent gnu.org, (2) user gnu.org (takeover),
  (3) user gnu.org via preview scroll to text=Try GNU/Linux
  [scroll], (4) user /distros/free-distros.html via preview
  click (Try GNU/Linux) [click-driven], (5) agent
  /distros/free-distros.html (handback). Replay shows BOTH
  transitions plus the scroll marker plus the click marker.
- The saved log itself was reloaded with load_saved_watch_log()
  in the live script and printed in full (5 entries, same
  content as the replay above).

### 2. Preview + replay polish — Python + TS
- Python: preview page in browser.py gains Scroll-to and
  Click-text controls (same /control queue as the other preview
  controls); `format_watch_log()` already marks scroll vias
  [scroll] and click vias [click-driven], and a new unit test
  pins the exact cycle-14 vias with no cross-marking.
- TS: `formatReplayEntries()` / `countScroll()` already mark
  scroll vias [scroll] and click vias [click-driven]; a new
  vitest case pins the exact cycle-14 vias with no
  cross-marking. Rebuilt with `npm run build` (tsc clean).

### Tests — all passing
- `python3 tests/run_tests.py` — **31 passed, 0 failed** (was 30;
  +1 cycle 14: scroll_to + click_text vias marked, no
  cross-marking, both transitions).
- `python3 tests/verify_packaging.py` — packaging: OK (0.13.0 in sync).
- TS: `npm run build` (tsc) clean; `npm test` (vitest) —
  **21 passed, 0 failed** (was 20; +1 cycle 14: scroll_to +
  click_text formatting, no cross-marking).

### Not tested live in cycle 14 (deferred, see MORNING_APPROVALS.md)
- No cloud provider live test, no live Ollama, no Go toolchain/
  binary, no `pip install -e .`, no pytest install, no system
  Playwright, no hand-driven TTY session.
- Free AI agents from other CLIs/websites: NOT researched in
  cycle 14, on purpose — deferred to tomorrow by the user.

## Cycle 15 never-stop (mock/local only, no live key, no Go toolchain)
Version: `shadowcode 0.14.0` (core + pyproject + TS TUI bumped in sync).
Compile: `python3 -m py_compile main.py shadowcode_pkg/*.py tests/*.py` — OK.

### 1. Live browser replay on a sixth site — CSS scroll_to THEN CSS click_selector (NOT faked)
- Script: /tmp/cycle15_live2.py (not shipped), run with the existing
  Playwright venv python (~/workspace/instagram-auto-signup/.venv/bin/python),
  NOT system Python. Browser workdir: test-workspace, preview
  127.0.0.1:8765, Firefox, ignore_https_errors (sandbox egress MITM).
- Sixth site choice, honestly: debian.org, NOT example.com/IANA,
  httpbin.org, iana.org, python.org, or gnu.org. A probe first showed
  debian.org, kernel.org, apache.org, postgresql.org, nodejs.org, and
  rust-lang.org all loading through this sandbox proxy; debian.org was
  used because its "Our Philosophy" link (href intro/philosophy) sits
  below the fold (top 897 in a 1280x720 viewport) and is uniquely
  addressable by the CSS selector a[href='intro/philosophy'].
- Honest first-run note: the first live run's agent browser_open
  timed out at 30s on the page-load event (proxy slowness, as in
  cycle 3), so no agent watch entry existed yet and takeover
  recorded no agent->user transition. That run was NOT claimed as
  the evidence. The second run opened cleanly, and its log is the
  evidence below.
- Sequence, all observed live: agent `browser_open
  https://www.debian.org/` -> title "Debian -- The Universal
  Operating System"; agent `browser_watch` before takeover ->
  current debian.org (agent entry recorded); preview POST /takeover
  -> driver user; preview POST /control {action: "scroll_to",
  selector: "a[href='intro/philosophy']"} -> state still debian.org,
  watch entry "via preview scroll to a[href='intro/philosophy']"
  [scroll]; preview POST /control {action: "click_selector",
  selector: "a[href='intro/philosophy']"} -> after a load wait, URL
  https://www.debian.org/intro/philosophy, title "Debian -- Our
  Philosophy: Why we do it and how we do it", driver user — NOT
  text, NOT a coordinate click, NOT a goto; agent `browser_watch`
  while USER DRIVING -> current philosophy page + watch log, no
  reload; agent `browser_open` while USER DRIVING -> paused message
  (correct); preview POST /handback -> driver agent; agent
  `browser_watch` / `browser_watch_replay` after handback -> STILL
  /intro/philosophy, "Our Philosophy" content, NOT reloaded to the
  homepage; close clean.
- Saved log: test-workspace/.shadowcode/browser-watch-20261102-015518-43696.json
  — 5 entries: (1) agent debian.org, (2) user debian.org (takeover),
  (3) user debian.org via preview scroll to
  a[href='intro/philosophy'] [scroll], (4) user
  /intro/philosophy via preview click
  (a[href='intro/philosophy']) [click-driven], (5) agent
  /intro/philosophy (handback). Replay shows BOTH transitions
  plus the scroll marker plus the click marker, with no
  cross-marking.

### 2. Preview + replay polish — Python + TS
- Python: preview page in browser.py gains a "Click selector" box
  (CSS selector) next to "Click text", posting
  {action: "click_selector", selector} through the same /control
  queue; the browser thread already handled click_selector as a
  real element click. New `browser.via_kind()` classifies a via by
  its ACTION word (second word after a preview/agent prefix, else
  the first word), and `format_watch_log()`, `Browser.watch()`,
  and the health browser-panel tail all use it — so a selector
  argument containing 'scroll' or 'click' cannot cross-mark.
- TS: new `viaKind()` in tui/src/lib/replay.ts with the same rule;
  `formatReplayEntries()`, `countClickDriven()`, and
  `countScroll()` all use it. Rebuilt with `npm run build`
  (tsc clean).
- New unit tests pin the guard in both languages: clicking
  '#scroll-nav a' is [click-driven] only, scrolling to
  'a.clickable' is [scroll] only, plus the exact cycle-15
  debian.org vias with both transitions.

### Tests — all passing
- `python3 tests/run_tests.py` — **32 passed, 0 failed** (was 31;
  +1 cycle 15: CSS scroll_to + click_selector vias marked, no
  cross-marking, both transitions).
- `python3 tests/verify_packaging.py` — packaging: OK (0.14.0 in sync).
- TS: `npm run build` (tsc) clean; `npm test` (vitest) —
  **22 passed, 0 failed** (was 21; +1 cycle 15: CSS scroll_to +
  click_selector formatting, viaKind, no cross-marking).

### Not tested live in cycle 15 (deferred, see MORNING_APPROVALS.md)
- No cloud provider live test, no live Ollama, no Go toolchain/
  binary, no `pip install -e .`, no pytest install, no system
  Playwright, no hand-driven TTY session.
- Free AI agents from other CLIs/websites: NOT researched in
  cycle 15, on purpose — deferred to tomorrow by the user.

## Cycle 16 never-stop (mock/local only, no live key, no Go toolchain)
Version: `shadowcode 0.15.0` (core + pyproject + TS TUI bumped in sync).
Compile: `python3 -m py_compile main.py shadowcode_pkg/*.py tests/*.py` — OK.

### 1. Live browser replay on a seventh site — scroll_to selector A THEN click_selector DIFFERENT selector B (NOT faked)
- Script: /tmp/cycle16_rust.py (not shipped), run with the existing
  Playwright venv python (~/workspace/instagram-auto-signup/.venv/bin/python),
  NOT system Python. Browser workdir: test-workspace, preview
  127.0.0.1:8765, Firefox, ignore_https_errors (sandbox egress MITM).
- Seventh site choice, honestly: rust-lang.org, NOT example.com/IANA,
  httpbin.org, iana.org, python.org, gnu.org, or debian.org. A probe first showed
  apache.org, postgresql.org, kernel.org, nodejs.org, and rust-lang.org all loading
  through this sandbox proxy; rust-lang.org was used because its two below-fold
  links are uniquely addressable by different CSS selectors in the same row.
- Honest failed attempts, NOT claimed as evidence:
  (a) postgresql.org: scroll_to a[href='/about/featurematrix/'] (top 862) worked and
  was logged [scroll], but click_selector a[href='/about/governance/'] (top 908,
  unique) performed the click yet the navigation hung in the sandbox proxy —
  title stuck at "Loading https://www.postgresql.org/about/governance/", URL never
  landed, even after 90s of polling. The click entry exists, but the destination
  did not load, so this run is NOT the evidence.
  (b) apache.org: scroll_to a[href='https://projects.apache.org/releases'] worked,
  but click_selector a[href='/foundation/members'] timed out with no click entry —
  a direct probe showed the selector's first match is a hidden nav menuitem
  (0x0, not visible), while the visible stats card is match #1. That run is
  NOT the evidence either.
- Sequence, all observed live on rust-lang.org: agent `browser_open
  https://www.rust-lang.org/` -> title "Rust Programming Language"; agent
  `browser_watch` before takeover -> current rust-lang.org (agent entry recorded);
  preview POST /takeover -> driver user; preview POST /control {action: "scroll_to",
  selector: "a[href='/what/cli']"} -> state still rust-lang.org, watch entry
  "via preview scroll to a[href='/what/cli']" [scroll]; preview POST /control
  {action: "click_selector", selector: "a[href='/what/wasm']"} -> on the FIRST poll
  (2s) URL https://rust-lang.org/what/wasm/, title "WebAssembly - Rust Programming
  Language", driver user — NOT the scroll selector, NOT text, NOT a coordinate
  click, NOT a goto; agent `browser_watch` while USER DRIVING -> current wasm page
  + watch log, no reload, and its body text starts with the WebAssembly page;
  agent `browser_open` while USER DRIVING -> paused message (correct); preview
  POST /handback -> driver agent; agent `browser_watch` / `browser_watch_replay`
  after handback -> STILL /what/wasm/, "WebAssembly" content, NOT reloaded to the
  homepage; close clean.
- Saved log: test-workspace/.shadowcode/browser-watch-20261102-030735-52913.json
  — 5 entries: (1) agent rust-lang.org, (2) user rust-lang.org (takeover),
  (3) user rust-lang.org via preview scroll to a[href='/what/cli'] [scroll],
  (4) user /what/wasm/ via preview click (a[href='/what/wasm']) [click-driven],
  (5) agent /what/wasm/ (handback). Replay shows BOTH transitions plus the
  scroll marker plus the click marker, with the two selectors distinct.

### 2. Replay polish — Python + TS, distinct selectors, no cross-marking
- No formatter change was needed: Python `via_kind()` and TS `viaKind()` already
  classify by the ACTION word, and both formatters already print the full via
  string, so each selector appears only on its own line. The cycle-16 polish is
  the pinning test in both languages: the scroll line must contain /what/cli and
  must NOT contain /what/wasm or [click-driven]; the click line must contain
  /what/wasm and must NOT contain /what/cli or [scroll]; counts 1 scroll,
  1 click-driven, 2 transitions.
- TS rebuilt with `npm run build` (tsc clean).

### Tests — all passing
- `python3 tests/run_tests.py` — **33 passed, 0 failed** (was 32;
  +1 cycle 16: distinct scroll/click selectors, no cross-marking, both transitions).
- `python3 tests/verify_packaging.py` — packaging: OK (0.15.0 in sync).
- TS: `npm run build` (tsc) clean; `npm test` (vitest) —
  **23 passed, 0 failed** (was 22; +1 cycle 16: distinct selectors, no cross-marking).

### Not tested live in cycle 16 (deferred, see MORNING_APPROVALS.md)
- No cloud provider live test, no live Ollama, no Go toolchain/
  binary, no `pip install -e .`, no pytest install, no system
  Playwright, no hand-driven TTY session.
- Free AI agents from other CLIs/websites: NOT researched in
  cycle 16, on purpose — deferred to tomorrow by the user.

## Cycle 17 never-stop (mock/local only, no live key, no Go toolchain)
Version: `shadowcode 0.16.0` (core + pyproject + TS TUI bumped in sync).
Compile: `python3 -m py_compile main.py shadowcode_pkg/*.py tests/*.py` — OK.

### 1. Live browser replay on an eighth site — multi-step scroll -> click -> scroll -> click, distinct sections (NOT faked)
- Script: /tmp/cycle17_ruby.py (not shipped), run with the existing
  Playwright venv python (~/workspace/instagram-auto-signup/.venv/bin/python),
  NOT system Python. Browser workdir: test-workspace, preview
  127.0.0.1:8765, Firefox, ignore_https_errors (sandbox egress MITM).
- Eighth site choice, honestly: ruby-lang.org, NOT example.com/IANA,
  httpbin.org, iana.org, python.org, gnu.org, debian.org, or
  rust-lang.org. A probe first showed nodejs.org, go.dev, kernel.org,
  ruby-lang.org, and php.net all loading through this sandbox proxy;
  ruby-lang.org was used because its homepage has a News item and a
  Security column in different sections, and its Security page has a
  long advisory list for a second scroll -> click on a different page.
  Site note: go.dev/learn/ timed out at 30s in the same probe and was
  NOT used and NOT claimed to load; go.dev itself and its
  /solutions/use-cases page did load, but ruby-lang.org gave the
  cleaner two-page sequence.
- Sequence, all observed live on ruby-lang.org: agent `browser_open
  https://www.ruby-lang.org/en/` -> title "Ruby Programming Language";
  agent `browser_watch` before takeover -> current homepage (agent
  entry recorded); preview POST /takeover -> driver user; preview
  POST /control {action: "scroll_to", selector:
  "a[href='/en/news/2026/10/23/ruby-3-4-12-released/']"} -> watch
  entry "via preview scroll to ..." [scroll] [step 1] — a News-section
  item below the fold (top ~3512 in a 1280x720 viewport, per probe);
  preview POST /control {action: "click_selector", selector:
  "a[href='/en/security/'] >> nth=1"} -> URL
  https://www.ruby-lang.org/en/security/, title "Security | Ruby" —
  the Security-column link, a DIFFERENT section from the News item
  scrolled to, NOT the same row, NOT text, NOT a coordinate, NOT a
  goto, [click-driven] [step 2]; agent `browser_watch` while USER
  DRIVING -> current Security page + watch log, no reload, and
  agent `browser_open` while USER DRIVING -> paused message
  (correct); preview POST /control {action: "scroll_to", selector:
  "a[href='/en/news/2025/09/18/dos-rexml-cve-2025-58767/']"} ->
  watch entry [scroll] [step 3] on the Security page; preview POST
  /control {action: "click_selector", selector:
  "a[href='/en/news/2024/10/28/redos-rexml-cve-2024-49761/']"} ->
  URL .../redos-rexml-cve-2024-49761/, title "CVE-2024-49761: ReDoS
  vulnerability in REXML | Ruby" [click-driven] [step 4]; preview
  POST /handback -> driver agent; agent `browser_watch` /
  `browser_watch_replay` after handback -> STILL the ReDoS article,
  "ReDoS vulnerability in REXML" content, NOT reloaded to the
  homepage; close clean.
- Saved log: test-workspace/.shadowcode/browser-watch-20261102-034244-57823.json
  — 7 entries: (1) agent ruby-lang.org, (2) user ruby-lang.org
  (takeover), (3) user ruby-lang.org via preview scroll to the
  3.4.12 news selector [scroll] [step 1], (4) user /en/security/
  via preview click (Security selector, nth=1) [click-driven]
  [step 2], (5) user /en/security/ via preview scroll to the
  dos-rexml advisory selector [scroll] [step 3], (6) user
  /redos-rexml-cve-2024-49761/ via preview click (that advisory
  selector) [click-driven] [step 4], (7) agent same article
  (handback). Replay shows BOTH transitions plus 2 scroll + 2
  click-driven steps, in order, across two pages.

### 2. Replay polish — Python + TS, step numbering for multi-step sequences
- Python `format_watch_log()` (shadowcode_pkg/browser.py) and TS
  `formatReplayEntries()` (tui/src/lib/replay.ts) now number action
  entries in order: `[step 1]`, `[step 2]`, … after the existing
  `[scroll]` / `[click-driven]` marker, and append a footer when
  there is at least one action step, e.g.
  `steps: 2 scroll, 2 click-driven, 2 driver transitions (4 action steps)`.
  Non-action entries get no step, and a plain log gets no footer —
  so old single-pair replays are unchanged except for the new
  suffix/footer on action entries. Marking is still by action word
  (via_kind / viaKind), so no cross-marking.
- TS BrowserWatchPanel header now also shows the action-step count
  ("N action steps") alongside entries/transitions/clicks/scrolls.
- Verified on the REAL saved log, not just unit fixtures: Python
  `format_watch_log(load_saved_watch_log(...))` and TS
  `formatReplayEntries(readSavedWatchLog(...))` both print the
  identical 7-entry replay with steps 1..4 and the steps footer.
- TS rebuilt with `npm run build` (tsc clean).

### Tests — all passing
- `python3 tests/run_tests.py` — **34 passed, 0 failed** (was 33;
  +1 cycle 17: multi-step replay step numbering, steps footer,
  no step on non-action entries, no footer on a plain log).
- `python3 tests/verify_packaging.py` — packaging: OK (0.16.0 in sync).
- TS: `npm run build` (tsc) clean; `npm test` (vitest) —
  **24 passed, 0 failed** (was 23; +1 cycle 17: multi-step replay
  step numbering in TS, same assertions as Python).

### Not tested live in cycle 17 (deferred, see MORNING_APPROVALS.md)
- No cloud provider live test, no live Ollama, no Go toolchain/
  binary, no `pip install -e .`, no pytest install, no system
  Playwright, no hand-driven TTY session.
- Free AI agents from other CLIs/websites: NOT researched in
  cycle 17, on purpose — deferred to tomorrow by the user.

## Cycle 18 never-stop (mock/local only, no live key, no Go toolchain)
Version: `shadowcode 0.17.0` (core + pyproject + TS TUI bumped in sync).
Compile: `python3 -m py_compile main.py shadowcode_pkg/*.py tests/*.py` — OK.

### 1. Live browser replay on a ninth site — three-page chain scroll -> click -> scroll -> click -> scroll -> click, steps 1..6 (NOT faked)
- Script: /tmp/cycle18_zig.py (not shipped), run with the existing Playwright venv python (~/workspace/instagram-auto-signup/.venv/bin/python), NOT system Python. Browser workdir: test-workspace, preview 127.0.0.1:8765, Firefox, ignore_https_errors (sandbox egress MITM).
- Ninth site choice, honestly: ziglang.org, NOT example.com/IANA, httpbin.org, iana.org, python.org, gnu.org, debian.org, rust-lang.org, or ruby-lang.org. A probe first showed php.net, nodejs.org, perl.org, git-scm.com, and ziglang.org loading through this sandbox proxy, while nginx.com and dart.dev both timed out at 30s on goto and were NOT used and NOT claimed to load; ziglang.org was used because its homepage, ZSF page, and news articles give three distinct source pages with below-fold internal links, and selector counts/tops were probed in advance (e.g. homepage `a[href='/code-of-conduct/']` count=1 top=1563, `a[href='/zsf/']` count=3 with nth=2 top=2009; ZSF `a[href='/news/2025-financials/']` count=1 top=1020; article `a[href='/news/300k-from-mitchellh/']` first match top=2679).
- Sequence, all observed live on ziglang.org: agent `browser_open https://ziglang.org/` -> title "Home ⚡ Zig Programming Language"; agent `browser_watch` before takeover -> current homepage (agent entry recorded); preview POST /takeover -> driver user; preview POST /control {action: "scroll_to", selector: "a[href='/code-of-conduct/']"} -> watch entry [scroll] [step 1]; preview POST /control {action: "click_selector", selector: "a[href='/zsf/'] >> nth=2"} -> URL https://ziglang.org/zsf/, title "Zig Software Foundation ⚡ Zig Programming Language" [click-driven] [step 2]; preview POST /control {action: "scroll_to", selector: "a[href='/zsf/meeting-minutes/']"} -> [scroll] [step 3] on the ZSF page; preview POST /control {action: "click_selector", selector: "a[href='/news/2025-financials/']"} -> URL .../news/2025-financials/, title "2025 Financial Report and Fundraiser ⚡ Zig Programming Language" [click-driven] [step 4]; preview POST /control {action: "scroll_to", selector: "a[href='/zsf']"} -> [scroll] [step 5] on that article; preview POST /control {action: "click_selector", selector: "a[href='/news/300k-from-mitchellh/']"} -> URL .../news/300k-from-mitchellh/, title "300k USD Donation Pledged by Mitchell Hashimoto ⚡ Zig Programming Language" [click-driven] [step 6]; agent `browser_watch` while USER DRIVING -> current 300k article + watch log, no reload, and agent `browser_open` while USER DRIVING -> paused message (correct); preview POST /handback -> driver agent; agent `browser_watch` / `browser_watch_replay` after handback -> STILL the 300k article, "300k USD Donation Pledged by Mitchell Hashimoto" content, NOT reloaded to the homepage; close clean. No user-driven step used text, a coordinate, or a goto.
- Saved log: test-workspace/.shadowcode/browser-watch-20261102-040834-61868.json — 9 entries: (1) agent ziglang.org, (2) user ziglang.org (takeover), (3) user ziglang.org via preview scroll to code-of-conduct [scroll] [step 1], (4) user /zsf/ via preview click (zsf nth=2) [click-driven] [step 2], (5) user /zsf/ via preview scroll to meeting-minutes [scroll] [step 3], (6) user /news/2025-financials/ via preview click (2025-financials) [click-driven] [step 4], (7) user /news/2025-financials/ via preview scroll to /zsf [scroll] [step 5], (8) user /news/300k-from-mitchellh/ via preview click (300k) [click-driven] [step 6], (9) agent same article (handback). Replay shows BOTH transitions plus 3 scroll + 3 click-driven steps, in order, across three source pages.

### 2. Replay polish — Python + TS, step numbering 1..6, footer counts, no cross-marking
- No formatter change was needed: Python `format_watch_log()` (shadowcode_pkg/browser.py) and TS `formatReplayEntries()` (tui/src/lib/replay.ts) already number action entries in order, and the TS BrowserWatchPanel header already shows the action-step count. The cycle-18 polish is the pinning tests in both languages (Python `test_cycle18_three_page_chain_replay_is_step_numbered_1_to_6`, TS cycle 18 replay test) plus verification on the REAL saved log in both languages, with identical output (9 entries, steps 1..6, footer `steps: 3 scroll, 3 click-driven, 2 driver transitions (6 action steps)`, counts 3 scroll / 3 click / 2 transitions in TS).
- Cross-marking check, corrected honestly: the first version of the Python pinning test asserted, whole-line, that no scroll line contains a click selector — that failed on step 5, whose page URL is /news/2025-financials/ (a click destination) even though its via selector is /zsf. The test was fixed to check the via selector part only, not the formatter: scroll via selectors are code-of-conduct / meeting-minutes / /zsf, click via selectors are zsf nth=2 / 2025-financials / 300k-from-mitchellh, with no overlap, and scroll lines carry [scroll] only while click lines carry [click-driven] only.
- TS rebuilt with `npm run build` (tsc clean).

### Tests — all passing
- `python3 tests/run_tests.py` — **35 passed, 0 failed** (was 34; +1 cycle 18: three-page chain replay step numbering 1..6, footer counts, no cross-marking).
- `python3 tests/verify_packaging.py` — packaging: OK (0.17.0 in sync).
- TS: `npm run build` (tsc) clean; `npm test` (vitest) — **25 passed, 0 failed** (was 24; +1 cycle 18: three-page chain replay step numbering in TS, same assertions as Python).
- Mock end-to-end still works: `./shadowcode --no-tui --provider mock --workdir test-workspace "list files"` OK; `./shadowcode --workdir test-workspace --browser-watch` prints the identical 9-entry replay with steps 1..6 and the steps footer.

### Not tested live in cycle 18 (deferred, see MORNING_APPROVALS.md)
- No cloud provider live test, no live Ollama, no Go toolchain/binary, no `pip install -e .`, no pytest install, no system Playwright, no hand-driven TTY session.
- Free AI agents from other CLIs/websites: NOT researched in cycle 18, on purpose — deferred to tomorrow by the user.

## Cycle 19 never-stop (mock/local only, no live key, no Go toolchain)
Version: `shadowcode 0.18.0` (core + pyproject + TS TUI bumped in sync).
Compile: `python3 -m py_compile main.py shadowcode_pkg/*.py tests/*.py` — OK.

### 1. Live browser replay on a tenth site — four-page chain scroll -> click x4, steps 1..8 (NOT faked)
- Script: /tmp/cycle19_live.py (not shipped), run with the existing Playwright venv python (~/workspace/instagram-auto-signup/.venv/bin/python), NOT system Python. Browser workdir: test-workspace, preview 127.0.0.1:8765, Firefox, ignore_https_errors (sandbox egress MITM).
- Tenth site choice, honestly: php.net, NOT example.com/IANA, httpbin.org, iana.org, python.org, gnu.org, debian.org, rust-lang.org, ruby-lang.org, or ziglang.org. A probe first showed perl.org, php.net, nodejs.org, lua.org, scala-lang.org, and elixir-lang.org all loading through this sandbox proxy; php.net was used because its home, news archive, ChangeLog, sites, and contact pages give four distinct source pages with internal links, and selector counts/tops/attribute forms were probed in advance (home news links carry absolute href attributes, e.g. `https://www.php.net/archive/2026.php#2026-10-21-4`, while footer links carry relative ones, e.g. `/sites.php` count=1 top=283126 on the very long ChangeLog page, `/contact.php` count=1 top=2232 on the sites page; the first probe guesses of relative archive/ChangeLog selectors returned count=0 and were corrected before the live run, not claimed).
- Sequence, all observed live on php.net: agent `browser_open https://www.php.net/` -> title "PHP"; agent `browser_watch` before takeover -> current homepage (agent entry recorded); preview POST /takeover -> driver user; preview POST /control {action: "scroll_to", selector: "a[href='https://www.php.net/archive/2026.php#2026-10-21-4']"} -> watch entry [scroll] [step 1]; preview POST /control {action: "click_selector", selector: same} -> URL https://www.php.net/archive/2026.php#2026-10-21-4, title "PHP: News Archive - 2026" [click-driven] [step 2]; preview POST /control {action: "scroll_to", selector: "a[href='https://www.php.net/ChangeLog-8.php#8.5.12']"} -> [scroll] [step 3] on the archive page; preview POST /control {action: "click_selector", selector: same} -> URL .../ChangeLog-8.php#8.5.12, title "PHP: PHP 8 ChangeLog" [click-driven] [step 4]; preview POST /control {action: "scroll_to", selector: "a[href='/sites.php']"} -> [scroll] [step 5] on the ChangeLog page; preview POST /control {action: "click_selector", selector: same} -> URL .../sites.php, title "PHP: A Tourist's Guide" [click-driven] [step 6]; preview POST /control {action: "scroll_to", selector: "a[href='/contact.php']"} -> [scroll] [step 7] on the sites page; preview POST /control {action: "click_selector", selector: same} -> URL .../contact.php, title "PHP: Contact" [click-driven] [step 8]; agent `browser_watch` while USER DRIVING -> current Contact page + watch log, no reload, and agent `browser_open` while USER DRIVING -> paused message (correct); preview POST /handback -> driver agent; agent `browser_watch` / `browser_watch_replay` after handback -> STILL the Contact page, NOT reloaded to the homepage; close clean. No user-driven step used text, a coordinate, or a goto.
- Saved log: test-workspace/.shadowcode/browser-watch-20261102-051406-70249.json — 11 entries: (1) agent php.net, (2) user php.net (takeover), (3) user php.net via preview scroll to archive 2026-10-21-4 [scroll] [step 1], (4) user archive via preview click (archive 2026-10-21-4) [click-driven] [step 2], (5) user archive via preview scroll to ChangeLog 8.5.12 [scroll] [step 3], (6) user ChangeLog via preview click (ChangeLog 8.5.12) [click-driven] [step 4], (7) user ChangeLog via preview scroll to /sites.php [scroll] [step 5], (8) user sites via preview click (/sites.php) [click-driven] [step 6], (9) user sites via preview scroll to /contact.php [scroll] [step 7], (10) user contact via preview click (/contact.php) [click-driven] [step 8], (11) agent contact (handback). Replay shows BOTH transitions plus 4 scroll + 4 click-driven steps, in order, across four source pages.

### 2. Replay polish — Python + TS, step numbering 1..8, footer counts, no cross-marking
- No formatter change was needed: Python `format_watch_log()` (shadowcode_pkg/browser.py) and TS `formatReplayEntries()` (tui/src/lib/replay.ts) already number action entries in order, and the TS BrowserWatchPanel header already shows the action-step count. The cycle-19 polish is the pinning tests in both languages (Python `test_cycle19_four_page_chain_replay_is_step_numbered_1_to_8`, TS cycle 19 replay test) plus verification on the REAL saved log in both languages, with identical output (11 entries, steps 1..8, footer `steps: 4 scroll, 4 click-driven, 2 driver transitions (8 action steps)`, counts 4 scroll / 4 click / 2 transitions in TS).
- Script-note honesty: the first live script's saved-log reload called `load_saved_watch_log('test-workspace')` as if it returned entries alone; it returns `(path, entries)`, so that reload line raised AttributeError AFTER the live replay had already printed. That was a bug in the throwaway /tmp script, not in Shadowcode: re-running the reload correctly returns the same 11-entry log (verified: path test-workspace/.shadowcode/browser-watch-20261102-051406-70249.json, 11 entries, identical replay), and the live `browser_watch_replay` output was unaffected. The script was not shipped, and the browser process exited with the script (no Firefox left running).
- TS rebuilt with `npm run build` (tsc clean).

### Tests — all passing
- `python3 tests/run_tests.py` — **36 passed, 0 failed** (was 35; +1 cycle 19: four-page chain replay step numbering 1..8, footer counts, exact via-selector sets, no cross-marking).
- `python3 tests/verify_packaging.py` — packaging: OK (0.18.0 in sync).
- TS: `npm run build` (tsc) clean; `npm test` (vitest) — **26 passed, 0 failed** (was 25; +1 cycle 19: four-page chain replay step numbering in TS, same assertions as Python).
- Mock end-to-end still works: `./shadowcode --no-tui --provider mock --workdir test-workspace "list files"` OK; `./shadowcode --workdir test-workspace --browser-watch` prints the identical 11-entry replay with steps 1..8 and the steps footer.

### Not tested live in cycle 19 (deferred, see MORNING_APPROVALS.md)
- No cloud provider live test, no live Ollama, no Go toolchain/binary, no `pip install -e .`, no pytest install, no system Playwright, no hand-driven TTY session.
- Free AI agents from other CLIs/websites: NOT researched in cycle 19, on purpose — deferred to tomorrow by the user.

## Cycle 20 never-stop (mock/local only, no live key, no Go toolchain)
Version: `shadowcode 0.19.0` (core + pyproject + TS TUI bumped in sync).
Compile: `python3 -m py_compile main.py shadowcode_pkg/*.py tests/*.py` — OK.

### 1. Live browser replay on an eleventh site — five-page chain scroll -> click x5, steps 1..10 (NOT faked)
- Script: /tmp/cycle20_live.py (not shipped), run with the existing Playwright venv python (~/workspace/instagram-auto-signup/.venv/bin/python), NOT system Python. Browser workdir: test-workspace, preview 127.0.0.1:8765, Firefox, ignore_https_errors (sandbox egress MITM).
- Eleventh site choice, honestly: perl.org, NOT example.com/IANA, httpbin.org, iana.org, python.org, gnu.org, debian.org, rust-lang.org, ruby-lang.org, ziglang.org, or php.net. A probe first showed perl.org, lua.org, scala-lang.org, elixir-lang.org, and nodejs.org all loading through this sandbox proxy; perl.org was used because its home, contribute, siteinfo, whitepapers, app, and style-guide pages give five distinct source pages with internal links, and selector counts/tops were probed in advance (home /contribute.html top 700, contribute /siteinfo.html top 930, siteinfo /about/whitepapers/ top 2044, whitepapers /app.html top 903, app /about/style-guide.html top 1208; each selector unique on its page, so the preview's .first click is unambiguous).
- Sequence, all observed live on perl.org: agent `browser_open https://www.perl.org/` -> title "The Perl Programming Language - www.perl.org"; agent `browser_watch` before takeover -> current homepage (agent entry recorded); preview POST /takeover -> driver user; preview POST /control {action: "scroll_to", selector: "a[href='/contribute.html']"} -> watch entry [scroll] [step 1]; preview POST /control {action: "click_selector", selector: same} -> URL https://www.perl.org/contribute.html, title "Contribute to Perl - www.perl.org" [click-driven] [step 2]; preview POST /control {action: "scroll_to", selector: "a[href='/siteinfo.html']"} -> [scroll] [step 3] on the contribute page; preview POST /control {action: "click_selector", selector: same} -> URL .../siteinfo.html, title "Site Information - www.perl.org" [click-driven] [step 4]; preview POST /control {action: "scroll_to", selector: "a[href='/about/whitepapers/']"} -> [scroll] [step 5] on the siteinfo page; preview POST /control {action: "click_selector", selector: same} -> URL .../about/whitepapers/, title "Perl 5 White Papers - www.perl.org" [click-driven] [step 6]; preview POST /control {action: "scroll_to", selector: "a[href='/app.html']"} -> [scroll] [step 7] on the whitepapers page; preview POST /control {action: "click_selector", selector: same} -> URL .../app.html, title "Application Programming - www.perl.org" [click-driven] [step 8]; preview POST /control {action: "scroll_to", selector: "a[href='/about/style-guide.html']"} -> [scroll] [step 9] on the app page; preview POST /control {action: "click_selector", selector: same} -> URL .../about/style-guide.html, title "Perl or perl? - www.perl.org" [click-driven] [step 10]; agent `browser_watch` while USER DRIVING -> current style-guide page + watch log, no reload, and agent `browser_open` while USER DRIVING -> paused message (correct); preview POST /handback -> driver agent; agent `browser_watch` / `browser_watch_replay` after handback -> STILL the style-guide page, NOT reloaded to the homepage; close clean. No user-driven step used text, a coordinate, or a goto. Every page landed on the first attempt in the live run (no 90s polling needed; the click poll returned immediately each time).
- Saved log: test-workspace/.shadowcode/browser-watch-20261102-062215-79224.json — 13 entries: (1) agent perl.org, (2) user perl.org (takeover), (3) user perl.org via preview scroll to /contribute.html [scroll] [step 1], (4) user contribute via preview click (/contribute.html) [click-driven] [step 2], (5) user contribute via preview scroll to /siteinfo.html [scroll] [step 3], (6) user siteinfo via preview click (/siteinfo.html) [click-driven] [step 4], (7) user siteinfo via preview scroll to /about/whitepapers/ [scroll] [step 5], (8) user whitepapers via preview click (/about/whitepapers/) [click-driven] [step 6], (9) user whitepapers via preview scroll to /app.html [scroll] [step 7], (10) user app via preview click (/app.html) [click-driven] [step 8], (11) user app via preview scroll to /about/style-guide.html [scroll] [step 9], (12) user style-guide via preview click (/about/style-guide.html) [click-driven] [step 10], (13) agent style-guide (handback). Replay shows BOTH transitions plus 5 scroll + 5 click-driven steps, in order, across five source pages.
- Probe honesty, recorded not hidden: in the cycle-20 probes, /about/whitepapers/ timed out once at 30s and /app.html once at 60s, then both loaded cleanly on retry; a whitepaper article page (/about/whitepapers/perl-database-orm.html) timed out at 60s and was NOT used; /camel.html timed out at 60s in a probe and was NOT used and NOT claimed to load. None of these timeouts is part of the evidence chain, which used only pages that loaded in the live run.
- Script-note honesty: the live script was run from the home directory, so its relative workdir first wrote the saved log to ~/test-workspace/.shadowcode/browser-watch-20261102-062215-79224.json instead of the project workdir. The file was moved unchanged (same name, same 13 entries, verified by re-reading it after the move and by `./shadowcode --workdir test-workspace --browser-watch` printing the identical 13-entry replay) into test-workspace/.shadowcode/; the stray ~/test-workspace directory was then removed. The live replay printed during the run (from `browser_watch_replay`, before any move) already matched the moved file exactly. The script was not shipped, and the browser process exited with the script (no Firefox left running).

### 2. Replay polish — Python + TS, step numbering 1..10, footer counts, no cross-marking
- No formatter change was needed: Python `format_watch_log()` (shadowcode_pkg/browser.py) and TS `formatReplayEntries()` (tui/src/lib/replay.ts) already number action entries in order, and the TS BrowserWatchPanel header already shows the action-step count. The cycle-20 polish is the pinning tests in both languages (Python `test_cycle20_five_page_chain_replay_is_step_numbered_1_to_10`, TS cycle 20 replay test) plus verification on the REAL saved log in both languages, with identical output (13 entries, steps 1..10, footer `steps: 5 scroll, 5 click-driven, 2 driver transitions (10 action steps)`, counts 5 scroll / 5 click / 2 transitions in TS).
- TS rebuilt with `npm run build` (tsc clean).

### Tests — all passing
- `python3 tests/run_tests.py` — **37 passed, 0 failed** (was 36; +1 cycle 20: five-page chain replay step numbering 1..10, footer counts, exact via-selector sets, no cross-marking).
- `python3 tests/verify_packaging.py` — packaging: OK (0.19.0 in sync).
- TS: `npm run build` (tsc) clean; `npm test` (vitest) — **27 passed, 0 failed** (was 26; +1 cycle 20: five-page chain replay step numbering in TS, same assertions as Python).
- Mock end-to-end still works: `./shadowcode --no-tui --provider mock --workdir test-workspace "list files"` OK; `./shadowcode --workdir test-workspace --browser-watch` prints the identical 13-entry replay with steps 1..10 and the steps footer.

### Not tested live in cycle 20 (deferred, see MORNING_APPROVALS.md)
- No cloud provider live test, no live Ollama, no Go toolchain/binary, no `pip install -e .`, no pytest install, no system Playwright, no hand-driven TTY session.
- Free AI agents from other CLIs/websites: NOT researched in cycle 20, on purpose — deferred to tomorrow by the user.

## Cycle 21 never-stop (mock/local only, no live key, no Go toolchain)
Version: `shadowcode 0.20.0` (core + pyproject + TS TUI bumped in sync).
Compile: `python3 -m py_compile main.py shadowcode_pkg/*.py tests/*.py` — OK.

### 1. Live browser replay on a twelfth site — six-page chain scroll -> click x6, steps 1..12 (NOT faked)
- Script: /tmp/cycle21_live.py (not shipped), run from inside ~/workspace/shadowcode (so the saved log landed directly in test-workspace/.shadowcode/, unlike cycle 20), with the existing Playwright venv python (~/workspace/instagram-auto-signup/.venv/bin/python), NOT system Python. Browser workdir: test-workspace, preview 127.0.0.1:8765, Firefox, ignore_https_errors (sandbox egress MITM).
- Twelfth site choice, honestly: scala-lang.org, NOT example.com/IANA, httpbin.org, iana.org, python.org, gnu.org, debian.org, rust-lang.org, ruby-lang.org, ziglang.org, php.net, or perl.org. A probe first showed lua.org, scala-lang.org, elixir-lang.org, and nodejs.org all loading through this sandbox proxy; scala-lang.org was used because its home, conduct, license, security, governance, blog, and download pages give six distinct source pages with internal links, and selector counts/tops were probed in advance (home /conduct.html top 2537, unique footer link; conduct /license/ top 4408, unique footer link; license /security/ top 887, unique footer link; security /governance/, governance /blog/, blog /download/ each match the nav first, top 39 — the scroll still records an entry and the click is a real element click via page.locator(...).first.click, not a goto).
- Sequence, all observed live on scala-lang.org: agent `browser_open https://www.scala-lang.org/` -> title "The Scala Programming Language"; agent `browser_watch` before takeover -> current homepage (agent entry recorded); preview POST /takeover -> driver user; preview POST /control {action: "scroll_to", selector: "a[href='/conduct.html']"} -> watch entry [scroll] [step 1]; preview POST /control {action: "click_selector", selector: same} -> URL https://www.scala-lang.org/conduct.html, title "Loading https://www.scala-lang.org/conduct/" [click-driven] [step 2], settling moments later to https://www.scala-lang.org/conduct/, title "The Scala Code of Conduct | The Scala Programming Language" (a separate non-action entry in the saved log, no step number); preview POST /control {action: "scroll_to", selector: "a[href='/license/']"} -> [scroll] [step 3] on the conduct page; preview POST /control {action: "click_selector", selector: same} -> URL .../license/, title "Scala License | The Scala Programming Language" [click-driven] [step 4]; preview POST /control {action: "scroll_to", selector: "a[href='/security/']"} -> [scroll] [step 5] on the license page; preview POST /control {action: "click_selector", selector: same} -> URL .../security/, title "Scala Security Policy | The Scala Programming Language" [click-driven] [step 6]; preview POST /control {action: "scroll_to", selector: "a[href='/governance/']"} -> [scroll] [step 7] on the security page; preview POST /control {action: "click_selector", selector: same} -> URL .../governance/, title "Governance | The Scala Programming Language" [click-driven] [step 8]; preview POST /control {action: "scroll_to", selector: "a[href='/blog/']"} -> [scroll] [step 9] on the governance page; preview POST /control {action: "click_selector", selector: same} -> URL .../blog/, title "Blog | The Scala Programming Language" [click-driven] [step 10]; preview POST /control {action: "scroll_to", selector: "a[href='/download/']"} -> [scroll] [step 11] on the blog page; preview POST /control {action: "click_selector", selector: same} -> URL .../download/, title "Install | The Scala Programming Language" [click-driven] [step 12]; agent `browser_watch` while USER DRIVING -> current download page + watch log, no reload, and agent `browser_open` while USER DRIVING -> paused message (correct); preview POST /handback -> driver agent; agent `browser_watch` / `browser_watch_replay` after handback -> STILL the download page, NOT reloaded to the homepage; close clean. No user-driven step used text, a coordinate, or a goto. Every page landed on the first attempt in the live run (no proxy timeout in the live run).
- Saved log: test-workspace/.shadowcode/browser-watch-20261102-062658-81053.json — 16 entries: (1) agent scala-lang.org, (2) user scala-lang.org (takeover), (3) user scala-lang.org via preview scroll to /conduct.html [scroll] [step 1], (4) user conduct.html via preview click (/conduct.html) [click-driven] [step 2], (5) user conduct/ title-settle, no via, no step, (6) user conduct/ via preview scroll to /license/ [scroll] [step 3], (7) user license/ via preview click (/license/) [click-driven] [step 4], (8) user license/ via preview scroll to /security/ [scroll] [step 5], (9) user security/ via preview click (/security/) [click-driven] [step 6], (10) user security/ via preview scroll to /governance/ [scroll] [step 7], (11) user governance/ via preview click (/governance/) [click-driven] [step 8], (12) user governance/ via preview scroll to /blog/ [scroll] [step 9], (13) user blog/ via preview click (/blog/) [click-driven] [step 10], (14) user blog/ via preview scroll to /download/ [scroll] [step 11], (15) user download/ via preview click (/download/) [click-driven] [step 12], (16) agent download/ (handback). Replay shows BOTH transitions plus 6 scroll + 6 click-driven steps, in order, across six source pages.
- Probe honesty, recorded not hidden: lua.org's homepage returned no links under the probe's link selector (its link structure differs), so it was not used as a chain candidate and nothing about lua.org is claimed beyond it loading; elixir-lang.org and nodejs.org loaded but were not chosen. No site in the cycle-21 probe timed out in a way that changes the evidence. The conduct canonicalisation (/conduct.html -> /conduct/) is part of the evidence log, not edited out.
- Script-note honesty: the live script was run from inside ~/workspace/shadowcode, so no log move was needed and no stray directory was created (the cycle-20 move problem does not recur). The script was not shipped, and the browser process exited with the script (no Firefox left running).

### 2. Replay polish — Python + TS, step numbering 1..12, footer counts, no cross-marking
- No formatter change was needed: Python `format_watch_log()` (shadowcode_pkg/browser.py) and TS `formatReplayEntries()` (tui/src/lib/replay.ts) already number action entries in order, and the TS BrowserWatchPanel header already shows the action-step count. The cycle-21 polish is the pinning tests in both languages (Python `test_cycle21_six_page_chain_replay_is_step_numbered_1_to_12`, TS cycle 21 replay test) plus verification on the REAL saved log in both languages, with identical output (16 entries, steps 1..12, footer `steps: 6 scroll, 6 click-driven, 2 driver transitions (12 action steps)`, counts 6 scroll / 6 click / 2 transitions in TS). The Python test additionally asserts the title-settle entry gets no step number and does not disturb the numbering.
- TS rebuilt with `npm run build` (tsc clean).

### Tests — all passing
- `python3 tests/run_tests.py` — **38 passed, 0 failed** (was 37; +1 cycle 21: six-page chain replay step numbering 1..12, footer counts, exact via-selector sets, no cross-marking, title-settle entry unnumbered).
- `python3 tests/verify_packaging.py` — packaging: OK (0.20.0 in sync).
- TS: `npm run build` (tsc) clean; `npm test` (vitest) — **28 passed, 0 failed** (was 27; +1 cycle 21: same assertions as Python in TS).
- Mock end-to-end still works: `./shadowcode --no-tui --provider mock --workdir test-workspace "list files"` OK; `./shadowcode --workdir test-workspace --browser-watch` prints the identical 16-entry replay with steps 1..12 and the steps footer.

### Not tested live in cycle 21 (deferred, see MORNING_APPROVALS.md)
- No cloud provider live test, no live Ollama, no Go toolchain/binary, no `pip install -e .`, no pytest install, no system Playwright, no hand-driven TTY session.
- Free AI agents from other CLIs/websites: NOT researched in cycle 21, on purpose — deferred to tomorrow by the user.

## Cycle 22 never-stop (mock/local only, no live key, no Go toolchain)
Version: `shadowcode 0.21.0` (core + pyproject + TS TUI bumped in sync).
Compile: `python3 -m py_compile main.py shadowcode_pkg/*.py tests/*.py` — OK.

### 1. Live browser replay on a thirteenth site — seven-page chain scroll -> click x7, steps 1..14 (NOT faked)
- Script: /tmp/cycle22_live.py (not shipped), run from inside ~/workspace/shadowcode (so the saved log landed directly in test-workspace/.shadowcode/, unlike cycle 20), with the existing Playwright venv python (~/workspace/instagram-auto-signup/.venv/bin/python), NOT system Python. Browser workdir: test-workspace, preview 127.0.0.1:8765, Firefox, ignore_https_errors (sandbox egress MITM).
- Thirteenth site choice, honestly: elixir-lang.org, NOT example.com/IANA, httpbin.org, iana.org, python.org, gnu.org, debian.org, rust-lang.org, ruby-lang.org, ziglang.org, php.net, perl.org, or scala-lang.org. A probe first showed elixir-lang.org, nodejs.org, julialang.org, kotlinlang.org, swift.org, haskell.org, ocaml.org, crystal-lang.org, and nim-lang.org all loading through this sandbox proxy; elixir-lang.org was used because its home, install, learning, docs, cases, blog, development, and trademarks pages give seven distinct source pages with internal links, and selector counts/tops were probed in advance (home /install/ nav first match top 78, count 4 with one hidden match; install /learning/, learning /docs/, docs /cases/, cases /blog/ nav first matches top 78, count 2 each with one hidden match; blog /development/ footer link; development /trademarks/ top 3191, unique, below the fold).
- Sequence, all observed live on elixir-lang.org: agent `browser_open https://elixir-lang.org/` -> title "The Elixir programming language"; agent `browser_watch` before takeover -> current homepage (agent entry recorded); preview POST /takeover -> driver user; preview POST /control {action: "scroll_to", selector: "a[href='/install/']"} -> watch entry [scroll] [step 1]; preview POST /control {action: "click_selector", selector: same} -> URL https://elixir-lang.org/install/, title "Install Elixir | The Elixir programming language" [click-driven] [step 2]; preview POST /control {action: "scroll_to", selector: "a[href='/learning/']"} -> [scroll] [step 3] on the install page; preview POST /control {action: "click_selector", selector: same} -> URL .../learning/, title "Learning | The Elixir programming language" [click-driven] [step 4]; preview POST /control {action: "scroll_to", selector: "a[href='/docs/']"} -> [scroll] [step 5] on the learning page; preview POST /control {action: "click_selector", selector: same} -> URL .../docs/, title "Documentation | The Elixir programming language" [click-driven] [step 6]; preview POST /control {action: "scroll_to", selector: "a[href='/cases/']"} -> [scroll] [step 7] on the docs page; preview POST /control {action: "click_selector", selector: same} -> URL .../cases/, title "Case studies | The Elixir programming language" [click-driven] [step 8]; preview POST /control {action: "scroll_to", selector: "a[href='/blog/']"} -> [scroll] [step 9] on the cases page; preview POST /control {action: "click_selector", selector: same} -> URL .../blog/, title "Blog | The Elixir programming language" [click-driven] [step 10]; preview POST /control {action: "scroll_to", selector: "a[href='/development/']"} -> [scroll] [step 11] on the blog page; preview POST /control {action: "click_selector", selector: same} -> URL .../development/, title "Development & team | The Elixir programming language" [click-driven] [step 12]; preview POST /control {action: "scroll_to", selector: "a[href='/trademarks/']"} -> [scroll] [step 13] on the development page; preview POST /control {action: "click_selector", selector: same} -> URL .../trademarks/, title "Trademarks policy | The Elixir programming language" [click-driven] [step 14]; agent `browser_watch` while USER DRIVING -> current trademarks page + watch log, no reload, and agent `browser_open` while USER DRIVING -> paused message (correct); preview POST /handback -> driver agent; agent `browser_watch` / `browser_watch_replay` after handback -> STILL the trademarks page, NOT reloaded to the homepage; close clean. No user-driven step used text, a coordinate, or a goto. Every page landed on the first attempt in the live run (no proxy timeout in the live run).
- Saved log: test-workspace/.shadowcode/browser-watch-20261102-063541-83479.json — 17 entries: (1) agent elixir-lang.org, (2) user elixir-lang.org (takeover), (3) user elixir-lang.org via preview scroll to /install/ [scroll] [step 1], (4) user install/ via preview click (/install/) [click-driven] [step 2], (5) user install/ via preview scroll to /learning/ [scroll] [step 3], (6) user learning/ via preview click (/learning/) [click-driven] [step 4], (7) user learning/ via preview scroll to /docs/ [scroll] [step 5], (8) user docs/ via preview click (/docs/) [click-driven] [step 6], (9) user docs/ via preview scroll to /cases/ [scroll] [step 7], (10) user cases/ via preview click (/cases/) [click-driven] [step 8], (11) user cases/ via preview scroll to /blog/ [scroll] [step 9], (12) user blog/ via preview click (/blog/) [click-driven] [step 10], (13) user blog/ via preview scroll to /development/ [scroll] [step 11], (14) user development/ via preview click (/development/) [click-driven] [step 12], (15) user development/ via preview scroll to /trademarks/ [scroll] [step 13], (16) user trademarks/ via preview click (/trademarks/) [click-driven] [step 14], (17) agent trademarks/ (handback). Replay shows BOTH transitions plus 7 scroll + 7 click-driven steps, in order, across seven source pages.
- Probe honesty, recorded not hidden: the blog page carries NO `/stewards/` link (count 0 in probe), so the first-planned blog -> stewards pair was replaced before the live run by blog -> development (footer link on the blog page) and development -> trademarks (top 3191, unique). The chain as run is the chain as logged; nothing about a stewards step is claimed. The live script was run from inside ~/workspace/shadowcode, so no log move was needed and no stray directory was created. The script was not shipped, and the browser process exited with the script (no Firefox left running).

### 2. Replay polish — Python + TS, step numbering 1..14, footer counts, no cross-marking
- No formatter change was needed: Python `format_watch_log()` (shadowcode_pkg/browser.py) and TS `formatReplayEntries()` (tui/src/lib/replay.ts) already number action entries in order, and the TS BrowserWatchPanel header already shows the action-step count. The cycle-22 polish is the pinning tests in both languages (Python `test_cycle22_seven_page_chain_replay_is_step_numbered_1_to_14`, TS cycle 22 replay test) plus verification on the REAL saved log in both languages, with identical output (17 entries, steps 1..14, footer `steps: 7 scroll, 7 click-driven, 2 driver transitions (14 action steps)`, counts 7 scroll / 7 click / 2 transitions in TS). The Python test additionally asserts the scroll via selectors are exactly the seven scroll selectors and the click via selectors exactly the seven click selectors (via part only, since a scroll line's page URL legitimately is a click destination).
- TS rebuilt with `npm run build` (tsc clean).

### Tests — all passing
- `python3 tests/run_tests.py` — **39 passed, 0 failed** (was 38; +1 cycle 22: seven-page chain replay step numbering 1..14, footer counts, exact via-selector sets, no cross-marking).
- `python3 tests/verify_packaging.py` — packaging: OK (0.21.0 in sync).
- TS: `npm run build` (tsc) clean; `npm test` (vitest) — **29 passed, 0 failed** (was 28; +1 cycle 22: same assertions as Python in TS).
- Mock end-to-end still works: `./shadowcode --no-tui --provider mock --workdir test-workspace "list files"` OK; `./shadowcode --workdir test-workspace --browser-watch` prints the identical 17-entry replay with steps 1..14 and the steps footer.

### Not tested live in cycle 22 (deferred, see MORNING_APPROVALS.md)
- No cloud provider live test, no live Ollama, no Go toolchain/binary, no `pip install -e .`, no pytest install, no system Playwright, no hand-driven TTY session.
- Free AI agents from other CLIs/websites: NOT researched in cycle 22, on purpose — deferred to tomorrow by the user, and no free-AI provider was added (user has not chosen from the research options).

## Cycle 23 never-stop (mock/local only, no live key, no Go toolchain)
Version: `shadowcode 0.22.0` (core + pyproject + TS TUI bumped in sync).
Compile: `python3 -m py_compile main.py shadowcode_pkg/*.py tests/*.py` — OK.

### 1. Live browser replay on a fourteenth site — eight-page chain scroll -> click x8, steps 1..16 (NOT faked)
- Script: /tmp/cycle23_live.py (not shipped), run from inside ~/workspace/shadowcode (so the saved log landed directly in test-workspace/.shadowcode/, unlike cycle 20), with the existing Playwright venv python (~/workspace/instagram-auto-signup/.venv/bin/python), NOT system Python. Browser workdir: test-workspace, preview 127.0.0.1:8765, Firefox, ignore_https_errors (sandbox egress MITM).
- Fourteenth site choice, honestly: lua.org, NOT example.com/IANA, httpbin.org, iana.org, python.org, gnu.org, debian.org, rust-lang.org, ruby-lang.org, ziglang.org, php.net, perl.org, scala-lang.org, or elixir-lang.org. A probe first showed lua.org and nodejs.org both loading through this sandbox proxy; lua.org was used because its home, start, docs, faq, versions, license, authors, thanks, and donations pages give eight distinct source pages with internal links, and selector counts/tops were probed in advance (start.html count 1, top 174 on home; docs.html count 1, top 726 on start, below the fold; faq.html count 2, first top 202 on docs; versions.html count 2, first top 1326 on faq, below the fold; license.html count 1, top 1545 on versions, below the fold; authors.html count 1, top 530 on license; thanks.html count 1, top 552 on authors; donations.html count 1 on thanks).
- Sequence, all observed live on lua.org: agent `browser_open https://www.lua.org/` -> title "The Programming Language Lua"; agent `browser_watch` before takeover -> current homepage (agent entry recorded); preview POST /takeover -> driver user; preview POST /control {action: "scroll_to", selector: "a[href='start.html']"} -> watch entry [scroll] [step 1]; preview POST /control {action: "click_selector", selector: same} -> URL https://www.lua.org/start.html, title "Lua: getting started" [click-driven] [step 2]; preview POST /control {action: "scroll_to", selector: "a[href='docs.html']"} -> [scroll] [step 3] on the start page; preview POST /control {action: "click_selector", selector: same} -> URL .../docs.html, title "Lua: documentation" [click-driven] [step 4]; preview POST /control {action: "scroll_to", selector: "a[href='faq.html']"} -> [scroll] [step 5] on the docs page; preview POST /control {action: "click_selector", selector: same} -> URL .../faq.html, title "Lua: FAQ" [click-driven] [step 6]; preview POST /control {action: "scroll_to", selector: "a[href='versions.html']"} -> [scroll] [step 7] on the faq page; preview POST /control {action: "click_selector", selector: same} -> URL .../versions.html, title "Lua: version history" [click-driven] [step 8]; preview POST /control {action: "scroll_to", selector: "a[href='license.html']"} -> [scroll] [step 9] on the versions page; preview POST /control {action: "click_selector", selector: same} -> URL .../license.html, title "Lua: license" [click-driven] [step 10]; preview POST /control {action: "scroll_to", selector: "a[href='authors.html']"} -> [scroll] [step 11] on the license page; preview POST /control {action: "click_selector", selector: same} -> URL .../authors.html, title "Lua: authors" [click-driven] [step 12]; preview POST /control {action: "scroll_to", selector: "a[href='thanks.html']"} -> [scroll] [step 13] on the authors page; preview POST /control {action: "click_selector", selector: same} -> URL .../thanks.html, title "Lua: thanks" [click-driven] [step 14]; preview POST /control {action: "scroll_to", selector: "a[href='donations.html']"} -> [scroll] [step 15] on the thanks page; preview POST /control {action: "click_selector", selector: same} -> URL .../donations.html, title "Lua: donations" [click-driven] [step 16]; agent `browser_watch` while USER DRIVING -> current donations page + watch log, no reload, and agent `browser_open` while USER DRIVING -> paused message (correct); preview POST /handback -> driver agent; agent `browser_watch` / `browser_watch_replay` after handback -> STILL the donations page, NOT reloaded to the homepage; close clean. No user-driven step used text, a coordinate, or a goto. Every page landed on the first attempt in the live run (no proxy timeout in the live run).
- Saved log: test-workspace/.shadowcode/browser-watch-20261102-063954-85151.json — 19 entries: (1) agent lua.org, (2) user lua.org (takeover), (3) user lua.org via preview scroll to start.html [scroll] [step 1], (4) user start.html via preview click (start.html) [click-driven] [step 2], (5) user start.html via preview scroll to docs.html [scroll] [step 3], (6) user docs.html via preview click (docs.html) [click-driven] [step 4], (7) user docs.html via preview scroll to faq.html [scroll] [step 5], (8) user faq.html via preview click (faq.html) [click-driven] [step 6], (9) user faq.html via preview scroll to versions.html [scroll] [step 7], (10) user versions.html via preview click (versions.html) [click-driven] [step 8], (11) user versions.html via preview scroll to license.html [scroll] [step 9], (12) user license.html via preview click (license.html) [click-driven] [step 10], (13) user license.html via preview scroll to authors.html [scroll] [step 11], (14) user authors.html via preview click (authors.html) [click-driven] [step 12], (15) user authors.html via preview scroll to thanks.html [scroll] [step 13], (16) user thanks.html via preview click (thanks.html) [click-driven] [step 14], (17) user thanks.html via preview scroll to donations.html [scroll] [step 15], (18) user donations.html via preview click (donations.html) [click-driven] [step 16], (19) agent donations.html (handback). Replay shows BOTH transitions plus 8 scroll + 8 click-driven steps, in order, across eight source pages.
- Probe honesty, recorded not hidden: the thanks page carries NO `contact.html` link (count 0 in probe), so the first-planned thanks -> contact pair was replaced before the live run by thanks -> donations (count 1 on the thanks page). The chain as run is the chain as logged; nothing about a contact step is claimed. The live script was run from inside ~/workspace/shadowcode, so no log move was needed and no stray directory was created. The script was not shipped, and the browser process exited with the script (no Firefox left running).

### 2. Replay polish — Python + TS, step numbering 1..16, footer counts, no cross-marking
- No formatter change was needed: Python `format_watch_log()` (shadowcode_pkg/browser.py) and TS `formatReplayEntries()` (tui/src/lib/replay.ts) already number action entries in order, and the TS BrowserWatchPanel header already shows the action-step count. The cycle-23 polish is the pinning tests in both languages (Python `test_cycle23_eight_page_chain_replay_is_step_numbered_1_to_16`, TS cycle 23 replay test) plus verification on the REAL saved log in both languages, with identical output (19 entries, steps 1..16, footer `steps: 8 scroll, 8 click-driven, 2 driver transitions (16 action steps)`, counts 8 scroll / 8 click / 2 transitions in TS). The Python test additionally asserts the scroll via selectors are exactly the eight scroll selectors and the click via selectors exactly the eight click selectors (via part only, since a scroll line's page URL legitimately is a click destination).
- TS rebuilt with `npm run build` (tsc clean).

### Tests — all passing
- `python3 tests/run_tests.py` — **40 passed, 0 failed** (was 39; +1 cycle 23: eight-page chain replay step numbering 1..16, footer counts, exact via-selector sets, no cross-marking).
- `python3 tests/verify_packaging.py` — packaging: OK (0.22.0 in sync).
- TS: `npm run build` (tsc) clean; `npm test` (vitest) — **30 passed, 0 failed** (was 29; +1 cycle 23: same assertions as Python in TS).
- Mock end-to-end still works: `./shadowcode --no-tui --provider mock --workdir test-workspace "list files"` OK; `./shadowcode --workdir test-workspace --browser-watch` prints the identical 19-entry replay with steps 1..16 and the steps footer.

### Not tested live in cycle 23 (deferred, see MORNING_APPROVALS.md)
- No cloud provider live test, no live Ollama, no Go toolchain/binary, no `pip install -e .`, no pytest install, no system Playwright, no hand-driven TTY session.
- Free AI agents from other CLIs/websites: NOT researched in cycle 23, on purpose — deferred to tomorrow by the user, and no free-AI provider was added (user has not chosen from the research options).

## Cycle 24 never-stop (mock/local only, no live key, no Go toolchain)
Version: `shadowcode 0.23.0` (core + pyproject + TS TUI bumped in sync).
Compile: `python3 -m py_compile main.py shadowcode_pkg/*.py tests/*.py` — OK.

### 1. Live browser replay on a fifteenth site — nine-page chain scroll -> click x9, steps 1..18 (NOT faked)
- Script: /tmp/cycle24_live.py (not shipped), run from inside ~/workspace/shadowcode (so the saved log landed directly in test-workspace/.shadowcode/), with the existing Playwright venv python (~/workspace/instagram-auto-signup/.venv/bin/python), NOT system Python. Browser workdir: test-workspace, preview 127.0.0.1:8765, Firefox, ignore_https_errors (sandbox egress MITM).
- Fifteenth site choice, honestly: ocaml.org, NOT example.com/IANA, httpbin.org, iana.org, python.org, gnu.org, debian.org, rust-lang.org, ruby-lang.org, ziglang.org, php.net, perl.org, scala-lang.org, elixir-lang.org, or lua.org. A probe first showed nodejs.org, julialang.org, kotlinlang.org, ocaml.org, nim-lang.org, crystal-lang.org, haskell.org, and go.dev all loading through this sandbox proxy; swift.org and www.djangoproject.com both timed out at 30s on goto in that probe and were NOT used and NOT claimed to load. ocaml.org was used because its home, docs, platform, packages, community, changelog, events, jobs, security, and governance pages give nine distinct source pages with internal links, and selector counts/tops were probed in advance (docs count 2, nav first top 16 on home; tools count 2, nav first top 16 on docs; packages count 3, nav first top 16 on platform; community count 3, nav first top 16 on packages; changelog count 3, nav first top 16 on community; events count 1, top 49853 on changelog, footer below the fold; jobs count 2, first top 80 on events; security count 1, top 3020 on jobs; governance count 1, top 2604 on security).
- Sequence, all observed live on ocaml.org: agent `browser_open https://ocaml.org/` -> title "Welcome to a World of OCaml"; agent `browser_watch` before takeover -> current homepage (agent entry recorded); preview POST /takeover -> driver user; preview POST /control {action: "scroll_to", selector: "a[href='/docs']"} -> watch entry [scroll] [step 1]; preview POST /control {action: "click_selector", selector: same} -> URL https://ocaml.org/docs, title "Learn OCaml" [click-driven] [step 2]; preview POST /control {action: "scroll_to", selector: "a[href='/tools']"} -> [scroll] [step 3] on the docs page; preview POST /control {action: "click_selector", selector: same} -> URL https://ocaml.org/platform, title "OCaml Platform" [click-driven] [step 4]; preview POST /control {action: "scroll_to", selector: "a[href='/packages']"} -> [scroll] [step 5] on the platform page; preview POST /control {action: "click_selector", selector: same} -> URL .../packages, title "OCaml Packages · Browse Community Packages" [click-driven] [step 6]; preview POST /control {action: "scroll_to", selector: "a[href='/community']"} -> [scroll] [step 7] on the packages page; preview POST /control {action: "click_selector", selector: same} -> URL .../community, title "The OCaml Community" [click-driven] [step 8]; preview POST /control {action: "scroll_to", selector: "a[href='/changelog']"} -> [scroll] [step 9] on the community page; preview POST /control {action: "click_selector", selector: same} -> URL .../changelog, title "OCaml Changelog" [click-driven] [step 10]; preview POST /control {action: "scroll_to", selector: "a[href='/events']"} -> [scroll] [step 11] on the changelog page; preview POST /control {action: "click_selector", selector: same} -> URL .../events, title "Upcoming OCaml Events" [click-driven] [step 12]; preview POST /control {action: "scroll_to", selector: "a[href='/jobs']"} -> [scroll] [step 13] on the events page; preview POST /control {action: "click_selector", selector: same} -> URL .../jobs, title "OCaml Jobs" [click-driven] [step 14]; preview POST /control {action: "scroll_to", selector: "a[href='/security']"} -> [scroll] [step 15] on the jobs page; preview POST /control {action: "click_selector", selector: same} -> URL .../security, title "OCaml Security" [click-driven] [step 16]; preview POST /control {action: "scroll_to", selector: "a[href='/governance']"} -> [scroll] [step 17] on the security page; preview POST /control {action: "click_selector", selector: same} -> URL .../governance, title "Governance" [click-driven] [step 18]; agent `browser_watch` while USER DRIVING -> current governance page + watch log, no reload, and agent `browser_open` while USER DRIVING -> paused message (correct); preview POST /handback -> driver agent; agent `browser_watch` / `browser_watch_replay` after handback -> STILL the governance page, NOT reloaded to the homepage; close clean. No user-driven step used text, a coordinate, or a goto.
- Saved log: test-workspace/.shadowcode/browser-watch-20261102-065220-88511.json — 21 entries: (1) agent ocaml.org, (2) user ocaml.org (takeover), (3) user ocaml.org via preview scroll to /docs [scroll] [step 1], (4) user docs via preview click (/docs) [click-driven] [step 2], (5) user docs via preview scroll to /tools [scroll] [step 3], (6) user platform via preview click (/tools) [click-driven] [step 4], (7) user platform via preview scroll to /packages [scroll] [step 5], (8) user packages via preview click (/packages) [click-driven] [step 6], (9) user packages via preview scroll to /community [scroll] [step 7], (10) user community via preview click (/community) [click-driven] [step 8], (11) user community via preview scroll to /changelog [scroll] [step 9], (12) user changelog via preview click (/changelog) [click-driven] [step 10], (13) user changelog via preview scroll to /events [scroll] [step 11], (14) user events via preview click (/events) [click-driven] [step 12], (15) user events via preview scroll to /jobs [scroll] [step 13], (16) user jobs via preview click (/jobs) [click-driven] [step 14], (17) user jobs via preview scroll to /security [scroll] [step 15], (18) user security via preview click (/security) [click-driven] [step 16], (19) user security via preview scroll to /governance [scroll] [step 17], (20) user governance via preview click (/governance) [click-driven] [step 18], (21) agent governance (handback). Replay shows BOTH transitions plus 9 scroll + 9 click-driven steps, in order, across nine source pages.
- Probe honesty, recorded not hidden: the /play page carries NO `/events/` link (count 0 in probe), so the first-planned changelog -> play -> events route was replaced before the live run by changelog -> events directly (footer link on the changelog page). The first live run expected /tools to land on https://ocaml.org/tools, but the click canonicalised to https://ocaml.org/platform, so that run's landing check failed and the run was aborted with a partial 7-entry saved log (browser-watch-20261102-065011-87783.json, 2 scroll + 2 click-driven steps, NOT claimed as evidence); the corrected chain, expecting /platform, landed every page on the first attempt in the second live run. The chain as run is the chain as logged; nothing about a /tools landing page is claimed. The live script was run from inside ~/workspace/shadowcode, so no log move was needed and no stray directory was created. The script was not shipped, and the browser process exited with the script (no Firefox left running).

### 2. Replay polish — Python + TS, step numbering 1..18, footer counts, no cross-marking
- No formatter change was needed: Python `format_watch_log()` (shadowcode_pkg/browser.py) and TS `formatReplayEntries()` (tui/src/lib/replay.ts) already number action entries in order, and the TS BrowserWatchPanel header already shows the action-step count. The cycle-24 polish is the pinning tests in both languages (Python `test_cycle24_nine_page_chain_replay_is_step_numbered_1_to_18`, TS cycle 24 replay test) plus verification on the REAL saved log in both languages, with identical output (21 entries, steps 1..18, footer `steps: 9 scroll, 9 click-driven, 2 driver transitions (18 action steps)`, counts 9 scroll / 9 click / 2 transitions in TS). The Python test additionally asserts the scroll via selectors are exactly the nine scroll selectors and the click via selectors exactly the nine click selectors (via part only, since a scroll line's page URL legitimately is a click destination).
- TS rebuilt with `npm run build` (tsc clean).

### Tests — all passing
- `python3 tests/run_tests.py` — **41 passed, 0 failed** (was 40; +1 cycle 24: nine-page chain replay step numbering 1..18, footer counts, exact via-selector sets, no cross-marking).
- `python3 tests/verify_packaging.py` — packaging: OK (0.23.0 in sync).
- TS: `npm run build` (tsc) clean; `npm test` (vitest) — **31 passed, 0 failed** (was 30; +1 cycle 24: same assertions as Python in TS).
- Mock end-to-end still works: `./shadowcode --no-tui --provider mock --workdir test-workspace "list files"` OK; `./shadowcode --workdir test-workspace --browser-watch` prints the identical 21-entry replay with steps 1..18 and the steps footer.

### Not tested live in cycle 24 (deferred, see MORNING_APPROVALS.md)
- No cloud provider live test, no live Ollama, no Go toolchain/binary, no `pip install -e .`, no pytest install, no system Playwright, no hand-driven TTY session.
- Free AI agents from other CLIs/websites: NOT researched in cycle 24, on purpose — deferred to tomorrow by the user, and no free-AI provider was added (user has not chosen from the research options).

## Kilo provider cycle (user-authorised, 2026-11-02) — version 0.24.0
- Provider `kilo` added to `get_provider()` (`shadowcode_pkg/providers.py`):
  OpenAI-compatible Kilo gateway `https://api.kilo.ai/api/openrouter`,
  default model `kilo-auto/free`, `--model` selects any `:free` model.
  `OpenAICompatProvider` gained `require_key=False` (Kilo) and an
  optional `max_tokens`; Kilo uses `max_tokens=4096`. With no
  `KILO_API_KEY` set, NO Authorization header is sent at all (an
  empty "Bearer " header is not the same thing); with the key set,
  it is sent, for paid models only. Keys only via env, never
  hard-coded. `KILO_API_KEY` added to `KEY_ENV` in `config.py`
  (optional — `key_set=no` for Kilo is expected on free use, not
  a block).
- Reasoning handling, honestly recorded: the Kilo gateway returns
  a separate `reasoning` field (and some models use
  `reasoning_content`). A reply with no `content` but reasoning
  present now raises ("provider returned reasoning only, no
  content") instead of being claimed as a successful empty answer.
  This is why the first Kilo CLI tool-loop run printed blank:
  `run_agent` preferred `chat_stream`, the stream carried no
  visible content, and the empty stream was returned as an
  answer. Fixed in `shadowcode_pkg/agent.py`: an empty stream
  now falls back to a non-streaming `chat` call.
- Live tests, no key, no account, only a few small calls (no
  hammering of the free pool):
  - Live catalog (curl, 2026-11-02): 384 models; `kilo-auto/free`
    context 256000. Free `:free` models present at that moment
    included `nvidia/nemotron-3-ultra-550b-a55b:free`,
    `nvidia/nemotron-3.5-lightning:free`,
    `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free`,
    `cohere/north-mini-code:free`, `dots-studio/dots-3-note-preview:free`,
    plus newer names such as `nvidia/nemotron-3.5-super-vl:free`,
    `recursive/flint-v1.0:free`, `liquid/lfm-2.5-2.6b:free`.
    (The printed subset above was filtered for `:free`; free
    models with a `-free` suffix, such as `reflection/beam-free`,
    are in the same catalog with $0 pricing — see the routed
    call below.)
  - Direct gateway call, model `kilo-auto/free`, prompt "Reply
    with exactly: KILO-OK": HTTP 200, routed model
    `reflection/beam-free`, content exactly `KILO-OK`,
    usage prompt 54 / completion 32 / total 86 tokens, of which
    27 reasoning tokens, **cost 0** (`cost_details` all 0,
    `is_byok: false`).
  - CLI: `env -u KILO_API_KEY ./shadowcode --no-tui --provider kilo
    --workdir test-workspace "say hi"` returned a visible greeting.
  - CLI tool loop: `... --provider kilo --workdir test-workspace
    "list files"` drove `TOOL: list_dir {"path": "."}` and listed
    real test-workspace files (`.shadowcode/`, `created.txt`,
    `form.html`, `hello.txt`, `screenshots/`).
- Limits and fallback (no evasion): documented free limit is
  200 requests/hour per IP. **No VPN and no IP rotation was
  added, and none will be**: the user asked for a VPN that
  changes IP when a rate/quota limit hits, and that part was
  declined, because rotating IP to reset the same provider's
  per-IP limit evades the provider's controls. Legitimate
  behaviour on a limit is honest backoff/wait, queueing, and
  fallback to a DIFFERENT free provider/model the user
  legitimately has access to (another Kilo `:free` model, or an
  existing Groq/Gemini/OpenRouter free tier). Kilo warns Auto
  Free prompts may be logged by upstream providers, so Kilo free
  is not suitable for sensitive/production data.
- Tests: `python3 tests/run_tests.py` — 43 passed, 0 failed
  (was 41; +2 Kilo: no-key/no-Auth-header + default model +
  max_tokens, and key-when-set + reasoning-only raises +
  groq-still-requires-key). `python3 tests/verify_packaging.py`
  — packaging OK (0.24.0 in sync). TS suite unchanged by this
  cycle (provider is Python core only).

## Cycle 25 never-stop (mock/local only, no live key, no Go toolchain)
Version: `shadowcode 0.25.0` (core + pyproject + TS TUI bumped in sync).
Compile: `python3 -m py_compile main.py shadowcode_pkg/*.py tests/*.py` — OK.

### 1. Live browser replay on a sixteenth site — ten-page chain scroll -> click x10, steps 1..20 (NOT faked)
- Script: /tmp/cycle25_live.py (not shipped), run from inside ~/workspace/shadowcode (so the saved log landed directly in test-workspace/.shadowcode/), with the existing Playwright venv python (~/workspace/instagram-auto-signup/.venv/bin/python), NOT system Python. Browser workdir: test-workspace, preview 127.0.0.1:8765, Firefox, ignore_https_errors (sandbox egress MITM).
- Sixteenth site choice, honestly: julialang.org, NOT example.com/IANA, httpbin.org, iana.org, python.org, gnu.org, debian.org, rust-lang.org, ruby-lang.org, ziglang.org, php.net, perl.org, scala-lang.org, elixir-lang.org, lua.org, or ocaml.org. A probe first showed nodejs.org, julialang.org, kotlinlang.org, nim-lang.org, crystal-lang.org, haskell.org, and go.dev all loading through this sandbox proxy. julialang.org was used because its home, downloads, learning, blog, community, contribute, jsoc, community/standards, community/stewards, governance, and diversity pages give ten distinct source pages with internal links, and selector counts/tops were probed in advance (downloads count 1, nav top 14 on home; learning count 1, nav top 14 on downloads; blog count 1, nav top 14 on learning; community count 2, nav top 14 on blog; contribute count 1, nav top 14 on community; jsoc count 1, nav top 14 on contribute; community/standards count 1, footer top 2098 on jsoc, below the fold; community/stewards count 3, first top 571 on standards; governance count 1, footer top 1857 on stewards, below the fold; diversity count 1, footer top 2455 on governance, below the fold).
- Sequence, all observed live on julialang.org: agent `browser_open https://julialang.org/` -> title "The Julia Programming Language"; agent `browser_watch` before takeover -> current homepage (agent entry recorded); preview POST /takeover -> driver user; then scroll_to + click_selector pairs in order: /downloads/ [scroll] [step 1] -> Installing Julia [click-driven] [step 2]; /learning/ [scroll] [step 3] -> Get started with Julia [click-driven] [step 4]; /blog/ [scroll] [step 5] -> The Julia Language Blog [click-driven] [step 6]; /community/ [scroll] [step 7] -> Community [click-driven] [step 8]; /contribute/ [scroll] [step 9] -> Ask and answer questions [click-driven] [step 10]; /jsoc/ [scroll] [step 11] -> Julia Seasons of Contributions [click-driven] [step 12]; /community/standards/ [scroll] [step 13] -> Julia Community - Standards [click-driven] [step 14]; /community/stewards/ [scroll] [step 15] -> Julia Community - Stewards [click-driven] [step 16]; /governance/ [scroll] [step 17] -> Julia Governance [click-driven] [step 18]; /diversity/ [scroll] [step 19] -> Diversity [click-driven] [step 20]; agent `browser_watch` while USER DRIVING -> current diversity page + watch log, no reload, and agent `browser_open` while USER DRIVING -> paused message (correct); preview POST /handback -> driver agent; agent `browser_watch` / `browser_watch_replay` after handback -> STILL the diversity page, NOT reloaded to the homepage; close clean. No user-driven step used text, a coordinate, or a goto.
- Saved log: test-workspace/.shadowcode/browser-watch-20261102-070641-91844.json — 23 entries: (1) agent julialang.org, (2) user julialang.org (takeover), (3) scroll /downloads/ [step 1], (4) click to downloads [step 2], (5) scroll /learning/ [step 3], (6) click to learning [step 4], (7) scroll /blog/ [step 5], (8) click to blog [step 6], (9) scroll /community/ [step 7], (10) click to community [step 8], (11) scroll /contribute/ [step 9], (12) click to contribute [step 10], (13) scroll /jsoc/ [step 11], (14) click to jsoc [step 12], (15) scroll /community/standards/ [step 13], (16) click to standards [step 14], (17) scroll /community/stewards/ [step 15], (18) click to stewards [step 16], (19) scroll /governance/ [step 17], (20) click to governance [step 18], (21) scroll /diversity/ [step 19], (22) click to diversity [step 20], (23) agent diversity (handback). Replay shows BOTH transitions plus 10 scroll + 10 click-driven steps, in order, across ten source pages.
- Probe honesty, recorded not hidden: the first-planned tail after jsoc was /install/ -> /benchmarks/ -> /packages/, but /install/ redirects to /downloads, /benchmarks/ carries NO /packages/ link (count 0), and /packages/ redirects to /community/packages, so that tail was replaced before the live run by jsoc -> community/standards -> community/stewards -> governance -> diversity, all verified by probe. The live chain landed every page on the first attempt, with no proxy timeout in the live run. The chain as run is the chain as logged. The live script was run from inside ~/workspace/shadowcode, so no log move was needed and no stray directory was created. The script was not shipped, and the browser process exited with the script (no Firefox left running).

### 2. Replay polish — Python + TS, step numbering 1..20, footer counts, no cross-marking
- No formatter change was needed: Python `format_watch_log()` (shadowcode_pkg/browser.py) and TS `formatReplayEntries()` (tui/src/lib/replay.ts) already number action entries in order, and the TS BrowserWatchPanel header already shows the action-step count. The cycle-25 polish is the pinning tests in both languages (Python `test_cycle25_ten_page_chain_replay_is_step_numbered_1_to_20`, TS cycle 25 replay test) plus verification on the REAL saved log in both languages, with identical output (23 entries, steps 1..20, footer `steps: 10 scroll, 10 click-driven, 2 driver transitions (20 action steps)`, counts 10 scroll / 10 click / 2 transitions in TS). The Python test additionally asserts the scroll via selectors are exactly the ten scroll selectors and the click via selectors exactly the ten click selectors (via part only, since a scroll line's page URL legitimately is a click destination).
- TS rebuilt with `npm run build` (tsc clean).

### Tests — all passing
- `python3 tests/run_tests.py` — **44 passed, 0 failed** (was 43; +1 cycle 25: ten-page chain replay step numbering 1..20, footer counts, exact via-selector sets, no cross-marking).
- `python3 tests/verify_packaging.py` — packaging: OK (0.25.0 in sync).
- TS: `npm run build` (tsc) clean; `npm test` (vitest) — **32 passed, 0 failed** (was 31; +1 cycle 25: same assertions as Python in TS).
- Mock end-to-end still works: `./shadowcode --no-tui --provider mock --workdir test-workspace "list files"` OK; `./shadowcode --workdir test-workspace --browser-watch` prints the identical 23-entry replay with steps 1..20 and the steps footer.

### Not tested live in cycle 25 (deferred, see MORNING_APPROVALS.md)
- No live Groq/Gemini/OpenRouter smoke test, no live Ollama, no Go toolchain/binary, no `pip install -e .`, no pytest install, no system Playwright, no hand-driven TTY session.
- No VPN / IP rotation: declined, unchanged (see MORNING_APPROVALS.md sections 27-28).

## Cycle 26 never-stop (mock/local only, no live key, no Go toolchain)
Version: `shadowcode 0.26.0` (core + pyproject + TS TUI bumped in sync).
Compile: `python3 -m py_compile main.py shadowcode_pkg/*.py tests/*.py` — OK.

### 1. Live browser replay on a seventeenth site — eleven-page chain scroll -> click x11, steps 1..22 (NOT faked)
- Script: /tmp/cycle26_live.py (not shipped), run from inside ~/workspace/shadowcode (so the saved log landed directly in test-workspace/.shadowcode/), with the existing Playwright venv python (~/workspace/instagram-auto-signup/.venv/bin/python), NOT system Python. Browser workdir: test-workspace, preview 127.0.0.1:8765, Firefox, ignore_https_errors (sandbox egress MITM).
- Seventeenth site choice, honestly: crystal-lang.org, NOT example.com/IANA, httpbin.org, iana.org, python.org, gnu.org, debian.org, rust-lang.org, ruby-lang.org, ziglang.org, php.net, perl.org, scala-lang.org, elixir-lang.org, lua.org, ocaml.org, or julialang.org. A probe first showed kotlinlang.org, nodejs.org, nim-lang.org, crystal-lang.org, haskell.org, and go.dev all loading through this sandbox proxy. crystal-lang.org was used because its home, install, blog, releases, community, sponsors, success-stories, used_in_prod, team, community/governance, media, and learning pages give eleven distinct source pages with internal links, and every chain selector's FIRST match is visible (install count 2, top 229 on home; blog count 2, top 38 on install; releases count 2, top 482 on blog; community count 1, top 35 on releases; sponsors count 3, top 53 on community; success-stories count 1, top 26549 on sponsors, below the fold; used_in_prod count 2, top 317 on success-stories; team count 2, top 53 on used_in_prod; governance count 3, top 53 on team; media count 1, top 5068 on governance, below the fold; learning count 1, top 53 on media).
- Sequence, all observed live on crystal-lang.org: agent `browser_open https://crystal-lang.org/` -> title "The Crystal Programming Language"; agent `browser_watch` before takeover -> current homepage (agent entry recorded); preview POST /takeover -> driver user; then scroll_to + click_selector pairs in order: /install/ [scroll] [step 1] -> Install [click-driven] [step 2]; /blog/ [scroll] [step 3] -> News [click-driven] [step 4]; /releases/ [scroll] [step 5] -> Releases [click-driven] [step 6]; /community/ [scroll] [step 7] -> Community [click-driven] [step 8]; /sponsors/ [scroll] [step 9] -> Sponsors [click-driven] [step 10]; /success-stories/ [scroll] [step 11] -> Success stories [click-driven] [step 12]; /used_in_prod/ [scroll] [step 13] -> Used in production [click-driven] [step 14]; /team/ [scroll] [step 15] -> Team [click-driven] [step 16]; /community/governance/ [scroll] [step 17] -> Crystal governance [click-driven] [step 18]; /media/ [scroll] [step 19] -> Media [click-driven] [step 20]; /learning/ [scroll] [step 21] -> External resources [click-driven] [step 22]; mid-chain agent `browser_watch` while USER DRIVING -> current page + watch log, no reload, and agent `browser_open` while USER DRIVING -> paused message (correct); preview POST /handback -> driver agent; agent `browser_watch` / `browser_watch_replay` after handback -> STILL the learning page, NOT reloaded to the homepage; close clean. No user-driven step used text, a coordinate, or a goto.
- Saved log: test-workspace/.shadowcode/browser-watch-20261102-071442-95168.json — 25 entries: (1) agent crystal-lang.org, (2) user crystal-lang.org (takeover), (3) scroll /install/ [step 1], (4) click to install [step 2], (5) scroll /blog/ [step 3], (6) click to blog [step 4], (7) scroll /releases/ [step 5], (8) click to releases [step 6], (9) scroll /community/ [step 7], (10) click to community [step 8], (11) scroll /sponsors/ [step 9], (12) click to sponsors [step 10], (13) scroll /success-stories/ [step 11], (14) click to success-stories [step 12], (15) scroll /used_in_prod/ [step 13], (16) click to used_in_prod [step 14], (17) scroll /team/ [step 15], (18) click to team [step 16], (19) scroll /community/governance/ [step 17], (20) click to governance [step 18], (21) scroll /media/ [step 19], (22) click to media [step 20], (23) scroll /learning/ [step 21], (24) click to learning [step 22], (25) agent learning (handback). Replay shows BOTH transitions plus 11 scroll + 11 click-driven steps, in order, across eleven source pages.
- Probe honesty, recorded not hidden: kotlinlang.org was rejected for the live run because several home-nav first matches are hidden mobile-menu items (e.g. /multiplatform/ first match not visible, /docs/home.html and /docs/api-references.html first matches not visible), and go.dev was rejected because /doc's first match on the learn page is hidden — both would have failed the live `.first.click` (the kotlin walk failed exactly this way at step 1, scroll_into_view timeout). A crystal chain after used_in_prod first planned /reference/, but that page carries NO /reference/ link (count 0), so the tail was replaced before the live run by used_in_prod -> team -> community/governance -> media -> learning, all verified by probe including a separate tail walk. The live chain landed every page on the first attempt, with no proxy timeout in the live run. The chain as run is the chain as logged. The live script was run from inside ~/workspace/shadowcode, so no log move was needed and no stray directory was created. The script was not shipped, and the browser process exited with the script (no Firefox left running).

### 2. Replay polish — Python + TS, step numbering 1..22, footer counts, no cross-marking
- No formatter change was needed: Python `format_watch_log()` (shadowcode_pkg/browser.py) and TS `formatReplayEntries()` (tui/src/lib/replay.ts) already number action entries in order, and the TS BrowserWatchPanel header already shows the action-step count. The cycle-26 polish is the pinning tests in both languages (Python `test_cycle26_eleven_page_chain_replay_is_step_numbered_1_to_22`, TS cycle 26 replay test) plus verification on the REAL saved log in both languages, with identical output (25 entries, steps 1..22, footer `steps: 11 scroll, 11 click-driven, 2 driver transitions (22 action steps)`, counts 11 scroll / 11 click / 2 transitions in TS). The Python test additionally asserts the scroll via selectors are exactly the eleven scroll selectors and the click via selectors exactly the eleven click selectors (via part only, since a scroll line's page URL legitimately is a click destination).
- TS rebuilt with `npm run build` (tsc clean).

### Tests — all passing
- `python3 tests/run_tests.py` — **45 passed, 0 failed** (was 44; +1 cycle 26: eleven-page chain replay step numbering 1..22, footer counts, exact via-selector sets, no cross-marking).
- `python3 tests/verify_packaging.py` — packaging: OK (0.26.0 in sync).
- TS: `npm run build` (tsc) clean; `npm test` (vitest) — **33 passed, 0 failed** (was 32; +1 cycle 26: same assertions as Python in TS).
- Mock end-to-end still works: `./shadowcode --no-tui --provider mock --workdir test-workspace "list files"` OK; `./shadowcode --workdir test-workspace --browser-watch` prints the identical 25-entry replay with steps 1..22 and the steps footer.

### Not tested live in cycle 26 (deferred, see MORNING_APPROVALS.md)
- No live Groq/Gemini/OpenRouter smoke test, no live Ollama, no Go toolchain/binary, no `pip install -e .`, no pytest install, no system Playwright, no hand-driven TTY session.
- No VPN / IP rotation: declined, unchanged (see MORNING_APPROVALS.md sections 27-29).

## Cycle 27 never-stop (mock/local only, no live key, no Go toolchain)
Version: `shadowcode 0.27.0` (core + pyproject + TS TUI bumped in sync).
Compile: `python3 -m py_compile main.py shadowcode_pkg/*.py tests/*.py` — OK.

### 1. Live browser replay on an eighteenth site — twelve-page chain scroll -> click x12, steps 1..24 (NOT faked)
- Script: /tmp/cycle27_live.py (not shipped), run from inside ~/workspace/shadowcode (so the saved log landed directly in test-workspace/.shadowcode/), with the existing Playwright venv python (~/workspace/instagram-auto-signup/.venv/bin/python), NOT system Python. Browser workdir: test-workspace, preview 127.0.0.1:8765, Firefox, ignore_https_errors (sandbox egress MITM).
- Eighteenth site choice, honestly: clojure.org, NOT example.com/IANA, httpbin.org, iana.org, python.org, gnu.org, debian.org, rust-lang.org, ruby-lang.org, ziglang.org, php.net, perl.org, scala-lang.org, elixir-lang.org, lua.org, ocaml.org, julialang.org, or crystal-lang.org. A probe first showed racket-lang.org, clojure.org, elm-lang.org, nodejs.org, nim-lang.org, kotlinlang.org, and go.dev all loading through this sandbox proxy; haskell.org returned no relative internal links usable as CSS selectors, and dlang.org timed out at 30s, so neither was used or claimed. clojure.org was used because its home, about/rationale, reference/reader, api/api, releases/downloads, guides/getting_started, community/success_stories, dev/dev, news/news, community/resources, community/contributing, community/companies, and community/license pages give twelve distinct destinations with internal links, and every chain selector's FIRST match is visible (rationale count 2, nav top 0 on home; reference/documentation count 2, nav top 0 on rationale; api/api count 2, nav top 0 on reader; releases/downloads count 2, nav top 0 on api; guides/guides count 2, nav top 0 on downloads; success_stories count 1, nav top 0 on getting_started; dev/dev count 1, nav top 0 on success_stories; news/news count 2, nav top 0 on dev; resources count 1, footer top 15376 on news, below the fold; contributing count 1, top 3085 on resources, below the fold; companies count 1, top 1965 on contributing, below the fold; license count 1, top 13582 on companies, below the fold).
- Sequence, all observed live on clojure.org: agent `browser_open https://clojure.org/` -> title "Clojure"; agent `browser_watch` before takeover -> current homepage (agent entry recorded); preview POST /takeover -> driver user; then scroll_to + click_selector pairs in order: /about/rationale [scroll] [step 1] -> Rationale [click-driven] [step 2]; /reference/documentation [scroll] [step 3] -> The Reader [click-driven] [step 4]; /api/api [scroll] [step 5] -> API Documentation [click-driven] [step 6]; /releases/downloads [scroll] [step 7] -> Clojure Downloads [click-driven] [step 8]; /guides/guides [scroll] [step 9] -> Getting Started [click-driven] [step 10]; /community/success_stories [scroll] [step 11] -> Success Stories [click-driven] [step 12]; /dev/dev [scroll] [step 13] -> Development [click-driven] [step 14]; /news/news [scroll] [step 15] -> News [click-driven] [step 16]; /community/resources [scroll] [step 17] -> Community Resources [click-driven] [step 18]; /community/contributing [scroll] [step 19] -> Contributing [click-driven] [step 20]; /community/companies [scroll] [step 21] -> Companies [click-driven] [step 22]; /community/license [scroll] [step 23] -> License [click-driven] [step 24]; mid-chain agent `browser_watch` while USER DRIVING -> current page + watch log, no reload, and agent `browser_open` while USER DRIVING -> paused message (correct); preview POST /handback -> driver agent; agent `browser_watch` / `browser_watch_replay` after handback -> STILL the license page, NOT reloaded to the homepage; close clean. No user-driven step used text, a coordinate, or a goto.
- Saved log: test-workspace/.shadowcode/browser-watch-20261102-072155-97897.json — 27 entries: (1) agent clojure.org, (2) user clojure.org (takeover), (3) scroll /about/rationale [step 1], (4) click to rationale [step 2], (5) scroll /reference/documentation [step 3], (6) click to reader [step 4], (7) scroll /api/api [step 5], (8) click to api [step 6], (9) scroll /releases/downloads [step 7], (10) click to downloads [step 8], (11) scroll /guides/guides [step 9], (12) click to getting_started [step 10], (13) scroll /community/success_stories [step 11], (14) click to success_stories [step 12], (15) scroll /dev/dev [step 13], (16) click to dev [step 14], (17) scroll /news/news [step 15], (18) click to news [step 16], (19) scroll /community/resources [step 17], (20) click to resources [step 18], (21) scroll /community/contributing [step 19], (22) click to contributing [step 20], (23) scroll /community/companies [step 21], (24) click to companies [step 22], (25) scroll /community/license [step 23], (26) click to license [step 24], (27) agent license (handback). Replay shows BOTH transitions plus 12 scroll + 12 click-driven steps, in order, across twelve source pages.
- Probe honesty, recorded not hidden: two canonicalisations — /reference/documentation lands on /reference/reader and /guides/guides lands on /guides/getting_started. The live landing check accepted those canonical pages (the log shows the canonical URLs, not the selector URLs), and no other landing differed from its selector. The first live script attempt failed immediately with ModuleNotFoundError because it was run from the home directory (sys.path '.' did not contain shadowcode_pkg); it was fixed by pointing sys.path at ~/workspace/shadowcode and running from inside ~/workspace/shadowcode, and that failed attempt created no browser session and no stray log. The live chain landed every page on the first attempt, with no proxy timeout in the live run. The chain as run is the chain as logged. The script was not shipped, and the browser process exited with the script (no Firefox left running).

### 2. Replay polish — Python + TS, step numbering 1..24, footer counts, no cross-marking
- No formatter change was needed: Python `format_watch_log()` (shadowcode_pkg/browser.py) and TS `formatReplayEntries()` (tui/src/lib/replay.ts) already number action entries in order, and the TS BrowserWatchPanel header already shows the action-step count. The cycle-27 polish is the pinning tests in both languages (Python `test_cycle27_twelve_page_chain_replay_is_step_numbered_1_to_24`, TS cycle 27 replay test) plus verification on the REAL saved log in both languages, with identical output (27 entries, steps 1..24, footer `steps: 12 scroll, 12 click-driven, 2 driver transitions (24 action steps)`, counts 12 scroll / 12 click / 2 transitions in TS). The Python test additionally asserts the scroll via selectors are exactly the twelve scroll selectors and the click via selectors exactly the twelve click selectors (via part only, since a scroll line's page URL legitimately is a click destination).
- TS rebuilt with `npm run build` (tsc clean). No change was made in this cycle to tui/src/App.tsx, tui/src/components/, or tui/src/lib/ (left to the separate TUI-redesign agent); the only TS change in this cycle is tui/tests/replay.test.ts plus the version bump in tui/package.json.

### Tests — all passing
- `python3 tests/run_tests.py` — **46 passed, 0 failed** (was 45; +1 cycle 27: twelve-page chain replay step numbering 1..24, footer counts, exact via-selector sets, no cross-marking).
- `python3 tests/verify_packaging.py` — packaging: OK (0.27.0 in sync).
- TS: `npm run build` (tsc) clean; `npm test` (vitest) — **52 passed, 0 failed across 8 files** (replay file alone: 20 passed, including the new cycle 27 test). The full-suite total is higher than cycle 26's 33 because the separate TUI-redesign agent added tests in other tui/tests files concurrently; this cycle's own TS addition is the single cycle 27 replay test.
- Mock end-to-end still works: `./shadowcode --no-tui --provider mock --workdir test-workspace "list files"` OK; `./shadowcode --workdir test-workspace --browser-watch` prints the identical 27-entry replay with steps 1..24 and the steps footer.

### Not tested live in cycle 27 (deferred, see MORNING_APPROVALS.md)
- No live Groq/Gemini/OpenRouter smoke test, no live Ollama, no Go toolchain/binary, no `pip install -e .`, no pytest install, no system Playwright, no hand-driven TTY session.
- No VPN / IP rotation: declined, unchanged (see MORNING_APPROVALS.md sections 27-30).
