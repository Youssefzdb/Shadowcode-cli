# Shadowcode — CLI AI agent, rebuilt from scratch (polyglot monorepo)

An original CLI AI agent, inspired at concept level by
Claude Code (REPL + one-shot, tools, permissions, sessions,
config). See [REVERSE_ENGINEERING.md](sandbox://workspace/shadowcode/REVERSE_ENGINEERING.md)
for what was observed from Claude Code's public surface — and what
was deliberately NOT copied (no source, no decompilation, no
prompts/schemas, no licence/login/subscription bypass).

Cycle 5 made Shadowcode polyglot — Python is no longer the only
language. See [docs/ARCHITECTURE.md](sandbox://workspace/shadowcode/docs/ARCHITECTURE.md)
for the full layout, and the top-level `Makefile`
(`build-all`, `build-tui`, `build-go`, `build-native`, `test-all`):

- **Python** (`main.py`, `shadowcode_pkg/`): agent core, providers,
  tools, sessions, MCP, browser orchestration.
- **TypeScript/JavaScript** (`tui/`, `web/`): Ink/React TUI +
  preview frontend + shared JSON-lines types.
- **Go** (`go/`): localhost preview + fast file-search service
  (stdlib only; binary build deferred — no Go toolchain here).
- **C++** (`native/`): fast scanner / line counter / fuzzy matcher,
  as a CLI binary and a shared library (C ABI, ctypes-tested).

## Quick start

```bash
cd ~/workspace/shadowcode
chmod +x shadowcode
./shadowcode --provider mock --workdir test-workspace "list files"
./shadowcode --provider mock --workdir test-workspace   # REPL
./shadowcode --version
./shadowcode --doctor
```

## TUI (cycle 3, stdlib curses — no install needed)

On a terminal, the interactive mode opens the TUI by default:

```bash
./shadowcode --provider mock --workdir test-workspace   # TUI
./shadowcode --no-tui --provider mock                  # plain REPL fallback
./shadowcode --tui                                     # force TUI
```

TUI layout (original code, `shadowcode_pkg/tui.py`):
header (Shadowcode, provider/model, session, permission mode),
transcript pane (user / assistant streaming / `[tool name]`
lines), status line (hints + browser driver/URL), and an input
row with history (Up/Down) and Esc to clear. Permission prompts
appear inline in the TUI (`y`/`n`) instead of a plain `input()`.
Slash commands in the TUI are the same as the REPL below, plus
streaming tokens and tool events render live as they arrive.
If curses cannot start (no TTY, no terminal), Shadowcode
prints `TUI unavailable …; falling back to plain REPL` and
continues in the plain REPL — the TUI never blocks the CLI.

Cycle 5 TUI polish (Python curses): richer status line
(thinking state, message/tool counts, last tool, browser
driver/URL), clearer tool rendering (✓/✕ mark + indented,
capped body instead of a flattened blob), history search
(Ctrl-R, newest-first matches), help overlay (F1), and
transcript scrolling (PgUp/PgDn). Plain REPL fallback kept.

## TypeScript TUI (cycle 5, Ink + React — professional project)

```bash
cd ~/workspace/shadowcode/tui
npm install   # inside tui/ only
npm run build # tsc -> dist/
./bin/shadowcode-tui --provider mock --workdir ../test-workspace
```

Components in `tui/src/components/`: Header, Transcript,
ToolPanel, StatusBar, Input, PermissionPrompt. The TS TUI talks
to the Python core over JSON-lines (see `tui/PROTOCOL.md`):
one subprocess per turn, `--session-id` on turn 1, `--resume`
afterwards; permission mode is `auto` in subprocess mode, so
destructive tools are denied unless `--allow-destructive` was
passed — no prompt is faked. Non-TTY runs fall back gracefully
instead of crashing (exit 0 + a pointer to the Python CLI).

REPL: `/help /model /provider /tools /sessions [query]
/sessions-view [query] /session-info <id>
/search-sessions <query> /export <id> [md|json] /resume <id>
/clear /compact /permissions /browser /health /mcp [server] /doctor /exit`,
and `!cmd` runs a shell command (same guard as `run_shell`).
Session export/search (cycle 4, polished in cycle 5, also as CLI flags):
`./shadowcode --export-session <id> [--export-format md|json]
[--export-output <file>]` and
`./shadowcode --search-sessions <query> [--search-from YYYY-MM-DD]
[--search-to YYYY-MM-DD]`. In the REPL/TUI: `/export-file <id>
[md|json] [path]` writes to a file without ever overwriting an
existing one (`-2`, `-3`, …), and `/sessions` uses a read-only
list that never creates or touches a session file. A fresh
`--session-id` that already exists is bumped to `<id>-2`
instead of overwriting the old session, and an ambiguous
session prefix is refused with a list of matches.
One-shot / print mode: `./shadowcode -p "do X"` (same as passing
a prompt). Resume: `./shadowcode --resume <id>`,
continue latest: `./shadowcode --continue`.
Streaming: model tokens are printed as they arrive by default
(`--no-stream` disables this). Native JSON tool calls from
Ollama/Gemini (`{"tool_calls": [...]}` / functionCall) are
converted to Shadowcode `TOOL:` lines. `--dry-run` shows diffs
and would-write messages without writing/editing any file.
`/compact` now uses extractive context management: it keeps
system messages + the last 10 messages and replaces the dropped
middle with a summary line (no model call, no invented summary).

## Providers

Keys only via environment variables, never hard-coded, never
printed (only `key_set=yes/no` is shown).

| Provider | Use | Key |
|---|---|---|
| `mock` (default) | tests the loop + tools, no key/network | — |
| `ollama` | local, `http://localhost:11434/api/chat` | — |
| `groq` | OpenAI-compatible free tier | `GROQ_API_KEY` |
| `gemini` | Google Generative Language API | `GEMINI_API_KEY` |
| `openrouter` | OpenAI-compatible, `:free` models via `--model` | `OPENROUTER_API_KEY` |
| `kilo` | Kilo gateway, OpenAI-compatible, free models need **no key** | `KILO_API_KEY` optional, paid models only |

Kilo notes (live-verified 2026-11-02, free lineup rotates — re-check
`/models` before relying on a specific name): base
`https://api.kilo.ai/api/openrouter`, default model `kilo-auto/free`
(256k context per live catalog), no Authorization header when no key
is set, generous `max_tokens=4096` because reasoning models can
otherwise return reasoning only with no visible content — such a
reply now raises instead of being claimed as a success. Free limit
documented by the task brief: **200 requests/hour per IP**. On a
limit, Shadowcode does NOT rotate IP or use a VPN to reset it (that
was explicitly declined): the honest behaviour is backoff/wait, or
fall back to a different free provider/model the user legitimately
has access to (another Kilo `:free` model, or Groq/Gemini/OpenRouter
free tier). Auto Free prompts may be logged by upstream providers,
so Kilo free is not suitable for sensitive/production data.

Examples:
```bash
./shadowcode --provider ollama --model llama3.2 "explain main.py"
GROQ_API_KEY=... ./shadowcode --provider groq "write hello.py, then run it"
./shadowcode --provider openrouter --model google/gemma-3-27b-it:free "list files"
./shadowcode --provider kilo "list files"   # no key needed for free models
./shadowcode --provider kilo --model nvidia/nemotron-3-ultra-550b-a55b:free "list files"
```

## Cycle 6 — native fast path + Go /search wiring (optional backends)

- **C++ native scanner as a Python fast path** (`shadowcode_pkg/native_scanner.py`):
  plain-substring `search_files` uses `native/shadowcode-native search` when the
  binary exists; regex patterns, a missing binary, any native error, or
  `SHADOWCODE_NO_NATIVE=1` fall back to the Python regex walk. New tools
  `count_lines` and `fuzzy_score` (READ tools) use the native CLI first, Python
  fallback second. Deliberately NOT ctypes: the C library prints to stdout,
  which would pollute the JSON-lines TUI protocol if loaded in-process.
- **Go /search wired into both TUIs, optional:** `tui/src/lib/goSearch.ts`
  and `shadowcode_pkg/go_search.py` fetch `http://127.0.0.1:PORT/search`
  (default 8765, `SHADOWCODE_PREVIEW_PORT`). `/go-search <query>` in the
  Python REPL/TUI and the TS TUI tries Go first, then prints an explicit
  "Go search unavailable" note and falls back to Python search — never fake
  Go hits. **Go is still not built here** (no Go toolchain, see
  MORNING_APPROVALS.md); the wiring is tested against the no-server case.
- **TS/Python TUI parity:** the TS TUI now handles the full Python command
  set — /sessions, /search-sessions, /export, /export-file, /resume,
  /permissions, /browser, /mcp, /doctor, /go-search — via `tui/src/lib/coreCli.ts`
  (core `--doctor`/`--search-sessions`/`--export-session` flags, output verbatim).
  /compact in the TS TUI is an honest note (compaction lives in the Python
  core); no permission prompt is faked in subprocess mode.

## Tools and permissions

Tools: `read_file`, `write_file`, `edit_file` (exact-match, with
`dry_run`), `diff_edit` (unified diff, never writes), `list_dir`,
`search_files`, `run_shell`, `mcp_call` (local stdio MCP servers
only, see below), and `browser_*` (below, including
`browser_watch` for the current page + watch log, no reload, and
`browser_watch_replay` for the full watch log, cycle 9),
plus cycle 4: `browser_click_selector`, `browser_scroll`,
`browser_fill_selector`, `browser_fill_form`).

Permission modes: `manual` (ask before writes/shell),
`auto` (allow non-destructive, ask destructive),
`plan` (read-only — writes/shell refused).
Flags: `--permission-mode`, `--allowed-tools`,
`--disallowed-tools`, `--allow-destructive` (still needs `--yes`
in one-shot or an explicit `y` in REPL), `--allow-outside`,
`--add-dir`. Files are confined to the working directory by
default. Config: `--config` > `$SHADOWCODE_CONFIG` >
`./shadowcode.json` > `.shadowcode/settings.json` >
`~/.config/shadowcode/config.json`. Project instructions:
`SHADOWCODE.md` in the working directory, if present.
Sessions: `~/.config/shadowcode/sessions/<id>.json` — no keys
stored in session files.

## Browser + localhost live preview

Playwright is required for the browser tool (system Python here
does not have it; the venv used in testing does):

```bash
pip install playwright && playwright install firefox
# in the REPL:
./shadowcode --provider mock
> open https://example.com
> read page
> screenshot
```

When the browser starts, Shadowcode prints e.g.
`Live preview: http://localhost:8765`.
Open it in your own browser: it polls `/state.json` every
second and shows URL, title, driver (AGENT/USER DRIVING), and
the latest screenshot (`/shot.png`). Server binds to
`127.0.0.1` only, port 8765 by default (next free port above it,
or `SHADOWCODE_PREVIEW_PORT`), and stops on
`browser_close()` / CLI exit.

**Takeover (cycle 2: instant, dedicated browser thread;
cycle 3: Muse-AI parity — watch + handback).**
The preview page has "Take control" and "Hand back to agent"
buttons, a URL bar (Go), Back/Forward, plus a "Send keys" box.
A dedicated browser thread owns the Playwright page; the agent
thread and the preview HTTP thread never touch the page
directly — they send commands into queues, and the browser
thread drains user controls first and pumps a fresh screenshot
every second while idle. So a preview click now acts promptly
(within the browser thread's ~0.2s loop), not only on the next
agent browser call, and the preview stays live even when the
agent is idle. While USER is driving, the agent's own browser
actions pause (reads/watch/close still work).
**Agent watches while you drive:** every URL/title change the
browser thread observes — agent-driven or user-driven — is
appended to a watch log, shown in the preview and in
`/state.json` (`watch`), and readable by the agent with the
new `browser_watch` tool (no reload).
**Handback resumes exactly:** clicking "Hand back to agent"
only flips the driver back to `agent`; it does NOT reload,
reset, or restart the browser. The agent then uses
`browser_watch` / `browser_read` on the *current* page and
continues its task from there. A failed user control is no
longer silent: `last_control_error` appears in `/state.json`.
Note: a preview URL navigation can take a few seconds through
a proxy (the goto itself is prompt; page load is not instant).
Safeguards kept: no sign-in, no password/payment fields, no
CAPTCHA solving, no bypass of a block/login wall.
Cycle 4 browser additions: `browser_click_selector` (CSS or
`text=…`), `browser_scroll` (down/up/top/bottom or scroll an
element into view), `browser_fill_selector` (refuses
password/payment by selector AND by element attributes), and
`browser_fill_form` (several fields at once; submit only for
non-sign-in forms — refused if the page has a password input
or a sign/log-in submit button). Tested live on a local
non-sign-in form (`test-workspace/form.html`): selector click
to IANA, scroll, fill, and submit all worked, and a password
selector was refused.
Cycle 14 preview controls: the preview page now also has a
"Scroll to" box (a CSS selector, or `text=…` for visible text)
and a "Click text" box (visible link text) — both go through
the same `/control` queue as the other preview controls, so
they act promptly in the browser thread, are recorded in the
watch log as `preview scroll to …` ([scroll]) and
`preview click (…)` ([click-driven]), and are NOT coordinate
clicks and NOT gotos. Proven live on a fifth site (see Cycle 14
below): scroll_to brought "Try GNU/Linux" into view, then
click_text clicked it.
Cycle 15 preview controls: the preview page now also has a
"Click selector" box (a CSS selector, e.g.
`a[href='intro/philosophy']`) next to "Click text" — same
`/control` queue, same prompt action, recorded as
`preview click (<selector>)` ([click-driven]). Proven live on
a sixth site (see Cycle 15 below): CSS scroll_to brought
"Our Philosophy" into view, then CSS click_selector clicked
it — NOT text, NOT a coordinate, NOT a goto. Replay marking
in Python (`via_kind`) and TS (`viaKind`) now classifies by
the ACTION word, not by a substring of the whole via, so a
selector containing 'scroll' or 'click' cannot cross-mark an
entry (a click on `#scroll-nav a` is click-driven only; a
scroll to `a.clickable` is scroll only).
Cycle 16 preview proof, seventh site: rust-lang.org — a
preview scroll_to on ONE CSS selector,
`a[href='/what/cli']` ("BUILDING TOOLS", top 1500, below the
fold), followed by a preview click_selector on a DIFFERENT
selector, `a[href='/what/wasm']` ("WRITING WEB APPS") — NOT
the same selector reused, NOT text, NOT a coordinate, NOT a
goto. Saved log
test-workspace/.shadowcode/browser-watch-20261102-030735-52913.json
(5 entries: agent homepage, user homepage, user scroll_to
`a[href='/what/cli']` [scroll], user destination
/rust-lang.org/what/wasm/ via preview click
(`a[href='/what/wasm']`) [click-driven], agent destination on
handback). The two selectors are shown distinctly in both
TUIs' replay, with no cross-marking (unit-tested in Python
and TS). Honest site notes: postgresql.org was tried first
— its /about/governance/ navigation hung in the sandbox
proxy (click performed, title stuck at "Loading …", URL
never landed, even after 90s) — and apache.org second —
its `a[href='/foundation/members']` first match is a hidden
nav menuitem, so the click timed out with no click entry;
neither was claimed as the evidence site, and rust-lang.org
was the site that actually loaded and navigated.

## MCP (cycle 2, minimal, local only)

Configure in `shadowcode.json` (or `.shadowcode/settings.json`):

```json
{"mcp": {"servers": {"dummy": {"command": ["python3", "mcp_dummy_server.py"]}}}}
```

Rules: the command must be a local file inside the working
directory, or a plain interpreter (`python3`/`node`) running a
script inside the working directory. Remote/HTTP servers are
refused by default. `mcp_call` is a WRITE tool, so manual mode
asks before it runs and plan mode refuses it, and only tools
advertised by the server via `tools/list` can be called.
`/mcp [server]` in the REPL lists a server's tools.
A dummy server for tests is in `tests/mcp_dummy_server.py`.

## Tests and packaging (cycle 2–4)

```bash
python3 tests/run_tests.py        # 26 tests, no pytest install needed
python3 tests/verify_packaging.py # offline packaging check, NO install
pytest tests/                     # same suite, needs pytest (see MORNING_APPROVALS.md)
pip install -e .                  # deferred to the morning; pyproject.toml is ready
```

`verify_packaging.py` (cycle 4) compiles all sources, parses
`pyproject.toml`, checks the `shadowcode = "main:main"` entry
point is callable, checks the pyproject version matches
`shadowcode_pkg.__version__` (this caught the old 0.2.0 vs
0.3.0 mismatch — both are now 0.4.0), and checks the declared
packages exist. It deliberately does NOT run `pip install -e .`.

## Layout

```
main.py                  # entry point (REPL + one-shot + flags)
shadowcode               # thin wrapper: ./shadowcode ...
pyproject.toml           # packaging (pip install -e ., deferred)
MORNING_APPROVALS.md     # everything deferred for the morning
shadowcode_pkg/
  config.py  providers.py  tools.py  permissions.py
  agent.py   session.py    browser.py  mcp.py
SPEC.md                  # behaviour spec
REVERSE_ENGINEERING.md   # clean-room notes on Claude Code
TESTING.md               # end-to-end test results
NEXT.md                  # next cycle
tests/                   # pytest suite + run_tests.py + dummy MCP server
test-workspace/          # test fixtures (hello.txt, created.txt, screenshots/)
```

## What was NOT copied
No Claude Code source, binary, prompt, schema, or transcript.
No Anthropic account, key, or subscription was used. The
reference install lives separately in
`~/workspace/claude-code-reference/` and is not part of
Shadowcode. See REVERSE_ENGINEERING.md for the full list.

## Cycle 8 (TUI browser integration + sessions view + health dashboard)
- `/browser` in the Python REPL, Python curses TUI, and TS TUI
  now prints the same panel: fresh preview state (URL, title,
  driver, health, has_screenshot), takeover/handback hints
  (Take control pauses the agent and it watches; Hand back
  resumes from the current page exactly, no reload), and the
  watch-log tail (last 5). Python header/status and TS
  Header/StatusBar show browser URL + title + driver + health
  at a glance. A not-started browser is "not started", never
  faked as live, and `/browser` does not start a browser that
  is not already running (it falls back to a localhost probe).
- Sessions view: `/sessions-view [query]` and `/session-info
  <id>` in all three UIs, backed by
  `session.sessions_view()` (read-only — listing, searching,
  info, and export never edit a session file; resume loads in
  memory; compact/export are the approved paths).
- Health dashboard: `--health` flag and `/health` command in
  all three UIs (`shadowcode_pkg/health.py`): Python core, TS
  TUI (version, dist/ built, node), Go preview (binary +
  /health server), preview server (/state.json), native C++
  scanner, Playwright — each honestly healthy/unavailable.
  A Python preview is never mislabelled as Go: Go is identified
  only by JSON `{"ok": true}` on /health.

## Cycle 10 (live browser replay + TS watch/health panels)
- Live browser replay, verified with a real Playwright page
  (existing Playwright venv, Firefox): agent opens example.com,
  preview takeover, user drives via preview control to IANA,
  agent `browser_watch` while USER DRIVING shows IANA with no
  reload, agent open while user driving is paused, handback,
  then agent read/watch still show IANA — not reloaded to
  example.com. Saved log:
  `test-workspace/.shadowcode/browser-watch-20261102-004908-30363.json`
  (4 entries). Fix in this cycle: handback previously recorded
  no entry (no URL/title change), so the replay showed only
  agent -> user; `Browser.record_driver_change()` now records
  a driver-change entry on takeover AND handback, so the saved
  replay shows BOTH transitions.
- TS TUI: `/browser-watch-replay` shows the FULL saved replay
  as a panel (`BrowserWatchPanel`, from the saved workspace
  log, not the live 10-entry tail), `/browser-watch-hide`
  hides it; `/health-history [n]` now also shows a
  health-history panel (`HealthHistoryPanel`),
  `/health-history-hide` hides it. `/browser-watch` (core
  flag) is unchanged.
- Version 0.9.0 in sync across core, pyproject, and TS TUI.

## Cycle 9 (browser watch replay + sessions-view actions + health history)
- `/browser-watch` in the Python REPL, Python curses TUI, and TS TUI
  (plus CLI `--browser-watch`, read-only, and agent tool
  `browser_watch_replay`): the FULL watch log, not the tail in
  `/browser` — every entry in order, with driver transitions
  (`agent -> user` on takeover, `user -> agent` on handback)
  marked. Live browser first; otherwise the saved per-session
  log file `<workdir>/.shadowcode/browser-watch-<timestamp>-<pid>.json`
  (written on every new watch entry and on close, workspace-only);
  otherwise an honest "no watch log yet", never an invented log.
  `/browser` panel now also reports the full watch count and
  points to `/browser-watch`.
- Sessions-view actions: `/sessions-view <id> info | export
  [md|json] | export-file [md|json] [path] | resume` in all three
  UIs (TS via the existing core flags). Info/export are
  read-only; resume loads in memory (the approved path);
  export-file is the approved export path (never overwrites).
  `/sessions-view <id>` alone shows that session's detail +
  action hints. Listing/searching/selecting never edit a
  session file.
- Health history: every `/health` / `--health` check appends one
  snapshot to `<workdir>/.shadowcode/health-history.jsonl`
  (capped at the last 100, no keys), and `/health-history [n]`
  (CLI `--health-history [n]`, TS via coreCli) shows the last
  snapshots, newest first. A missing log is "no snapshots yet",
  never a fake snapshot.

## Cycle 7 (TS TUI parity + Go preview health + benchmark)
- TS TUI commands are now real core calls, not help text:
  `/sessions` (list), `/search-sessions [--from D] [--to D]`,
  `/resume` (shows session info), `/compact` (compacts the saved
  session file), `/permissions`, `/mcp [server]`, `!cmd`
  (runs in the workdir), and `/go-search` with a real Python
  `--search-files` fallback when no Go server runs.
- TS StatusBar + `/browser` show Go/Python preview health:
  `preview localhost:<port> healthy|unavailable driver=<driver>`,
  polled every 3s from `/health` + `/state.json` on 127.0.0.1.
- New core flags: `--list-sessions`, `--search-files`,
  `--compact-session`, `--session-info`, `--mcp-servers`,
  `--mcp-tools`, `--permissions`, `--run-shell`.
- Benchmark: `python3 scripts/benchmark_search.py` — pure Python
  vs C++ native search on a generated tree. Honest result:
  ~1.07x on 500x100 files, ~10.47x on 2000x200 files (cap 100
  hits, same hit count both sides). See TESTING.md, cycle 7.

## Cycle 11 (live replay, second site + no-navigation + replay-panel polish)
- Live replay on a second site, NOT example.com/IANA: agent opened
  https://httpbin.org/html, user took over via the preview and drove
  to https://httpbin.org/headers, handback, and /browser-watch showed
  both driver transitions plus the user-driven entry. Saved log:
  test-workspace/.shadowcode/browser-watch-20261102-011458-34759.json
  (4 entries). Site note: wikipedia.org and w3.org were probed first
  and timed out on the 30s goto through this sandbox proxy, so they
  were NOT used and no result was faked for them.
- No-navigation replay: agent opened https://httpbin.org/html, user
  took over, did NOT navigate, handed back. Saved log:
  test-workspace/.shadowcode/browser-watch-20261102-011511-34759.json
  (3 entries, same page, 2 transitions: agent -> user, user -> agent),
  and the agent resumed from the same page.
- TUI replay-panel polish: TS BrowserWatchPanel header now shows
  "N entries, M driver transitions" (countTransitions), so a
  same-page replay reads correctly at a glance. Python TUI/REPL
  gained /browser-watch-replay (full saved replay on demand,
  alongside the existing /browser-watch); help text updated in both.

## Cycle 12 (live replay, third site — click-driven, not a goto + replay polish)
- Live replay on a third site, NOT example.com/IANA and NOT httpbin.org:
  agent opened https://www.iana.org/ (title "Internet Assigned Numbers
  Authority"), user took over via the preview and CLICKED the internal
  "Domain Names" link (href /domains) via the preview screenshot click
  at (266,358) — the centre of that link's box in the 1280x720 viewport,
  found by a separate probe of the same page layout — NOT a goto.
  Handback, and /browser-watch-replay showed both driver transitions
  plus the click-driven entry. Saved log:
  test-workspace/.shadowcode/browser-watch-20261102-012015-36840.json
  (5 entries: agent iana.org, user iana.org, user Loading… via preview
  click [click-driven], user /domains via preview click [click-driven],
  agent /domains). The agent resumed from /domains ("Domain Name
  Services"), NOT reloaded to the homepage.
- Replay polish (Python + TS): watch entries now carry a `via` field
  for user actions (preview click/goto/back/forward/type/key). Python
  `format_watch_log()`, `Browser.watch()`, and the health browser panel
  tail, plus TS `formatReplayEntries()` / `readSavedWatchLog()` and the
  BrowserWatchPanel header ("N entries, M transitions, K click-driven"),
  all mark click entries `[click-driven]`. A click first changes the
  title to "Loading …" on the old URL, so `via` is kept until the URL
  itself changes — otherwise the destination entry would lose the
  marker (bug found and fixed during this cycle's live run). An empty
  `via` is no longer printed as a stray "via " in `browser_watch`.
- Version 0.11.0 in sync across core, pyproject, and TS TUI.

## Cycle 14 (live replay, fifth site — scroll_to + click_text, no coordinates, no goto)
- Live replay on a fifth site, NOT example.com/IANA,
  httpbin.org, iana.org, or python.org: agent opened
  https://www.gnu.org/ ("The GNU Operating System and the Free
  Software Movement"), user took over via the preview, used the
  new preview "Scroll to" control with `text=Try GNU/Linux`
  (that link was below the fold — top 836 in a 1280x720
  viewport, verified by a probe of the same page layout), then
  used the new preview "Click text" control with
  `Try GNU/Linux` — NOT a screenshot-coordinate click, NOT a
  goto. The agent watched while USER DRIVING, its own open
  correctly paused, and after handback it resumed from
  https://www.gnu.org/distros/free-distros.html ("List of Free
  GNU/Linux Distributions"), NOT reloaded to the homepage.
  Saved log:
  test-workspace/.shadowcode/browser-watch-20261102-015032-42148.json
  (5 entries: agent gnu.org, user gnu.org, user gnu.org via
  preview scroll to text=Try GNU/Linux [scroll], user
  /distros/free-distros.html via preview click (Try GNU/Linux)
  [click-driven], agent /distros/free-distros.html). Replay
  shows BOTH driver transitions plus the scroll and click
  markers. Site note: w3.org timed out at 30s in the same
  probe and was NOT claimed to load; gnu.org, apache.org,
  pypi.org, and kernel.org all loaded.
- Preview + replay polish (Python + TS): preview page gains
  Scroll-to and Click-text controls; Python
  `format_watch_log()` and TS `formatReplayEntries()` both
  mark scroll_to `[scroll]` and click_text `[click-driven]`,
  with no cross-marking (unit-tested in both languages).
- Version 0.13.0 in sync across core, pyproject, and TS TUI.

## Cycle 13 (live replay, fourth site — scroll-then-click + scroll entries)
- Live replay on a fourth site, NOT example.com/IANA, httpbin.org,
  or iana.org: agent opened https://www.python.org/ ("Welcome to
  Python.org"), user took over via the preview, scrolled down
  600px via the preview Scroll down button (the "Start with our
  Beginner's Guide" link was at top 927, below the fold, and at
  top 327 after the scroll — verified by a separate probe of the
  same page layout), then clicked that link via the preview
  screenshot click at (181,336) — NOT a goto. Handback, and
  /browser-watch-replay showed the scroll, both driver transitions,
  plus the click-driven entries. Saved log:
  test-workspace/.shadowcode/browser-watch-20261102-013724-40129.json
  (6 entries: agent python.org, user python.org, user python.org
  via preview scroll down [scroll], user Loading + user
  /about/gettingstarted/ via preview click (181,336)
  [click-driven], agent /about/gettingstarted/). The agent
  resumed from /about/gettingstarted/ ("Python For Beginners"),
  NOT reloaded to the homepage.
- Scroll polish (Python + TS): scrolls are now first-class watch
  entries (`Browser.record_action_entry(via)` for preview wheel /
  scroll_to and agent `browser_scroll`, since a scroll changes no
  URL/title and `_snap()` alone would log nothing). Python
  `format_watch_log()` / `Browser.watch()` / health panel tail,
  plus TS `formatReplayEntries()` / `countScroll()` and the
  BrowserWatchPanel header ("N entries, M transitions, K
  click-driven, S scroll"), all mark scroll entries `[scroll]`.
  Preview page now has Scroll down / Scroll up buttons and shows
  `via` in its watch list.
- Version 0.12.0 in sync across core, pyproject, and TS TUI.

## Cycle 17 (live replay, eighth site — multi-step scroll -> click -> scroll -> click + step-numbered replay)
- Live replay on an eighth site, NOT example.com/IANA,
  httpbin.org, iana.org, python.org, gnu.org, debian.org, or
  rust-lang.org: agent opened https://www.ruby-lang.org/en/
  ("Ruby Programming Language"), user took over via the preview,
  scrolled to a News-section item
  (`a[href='/en/news/2026/10/23/ruby-3-4-12-released/']`, below
  the fold), then clicked a DIFFERENT-section link
  (`a[href='/en/security/'] >> nth=1`, the Security column) —
  NOT the same row, NOT text, NOT a coordinate, NOT a goto —
  then on the Security page scrolled to another advisory
  (`a[href='/en/news/2025/09/18/dos-rexml-cve-2025-58767/']`)
  and clicked a different advisory
  (`a[href='/en/news/2024/10/28/redos-rexml-cve-2024-49761/']`).
  Handback, and /browser-watch-replay showed the full
  scroll -> click -> scroll -> click sequence, both driver
  transitions, and the agent resuming from the ReDoS article,
  NOT reloaded to the homepage. Saved log:
  test-workspace/.shadowcode/browser-watch-20261102-034244-57823.json
  (7 entries: 2 scroll, 2 click-driven, 2 transitions).
- Replay polish (Python + TS): action entries are now numbered
  in order (`[step 1]` … `[step 4]` after the [scroll] /
  [click-driven] marker), with a footer line
  (`steps: 2 scroll, 2 click-driven, 2 driver transitions
  (4 action steps)`) when there is at least one action step;
  non-action entries get no step and a plain log gets no
  footer. The TS BrowserWatchPanel header also shows the
  action-step count. Verified on the real saved log in both
  languages, with identical output.

## Cycle 18 (live replay, ninth site — three-page chain scroll -> click -> scroll -> click -> scroll -> click, steps 1..6)
- Live replay on a ninth site, NOT example.com/IANA, httpbin.org, iana.org, python.org, gnu.org, debian.org, rust-lang.org, or ruby-lang.org: agent opened https://ziglang.org/ ("Home ⚡ Zig Programming Language"), user took over via the preview, then across three source pages: (1) scrolled to `a[href='/code-of-conduct/']` [scroll] [step 1] and clicked `a[href='/zsf/'] >> nth=2` [click-driven] [step 2] -> https://ziglang.org/zsf/; (2) scrolled to `a[href='/zsf/meeting-minutes/']` [scroll] [step 3] and clicked `a[href='/news/2025-financials/']` [click-driven] [step 4] -> the 2025 Financial Report article; (3) scrolled to `a[href='/zsf']` [scroll] [step 5] and clicked `a[href='/news/300k-from-mitchellh/']` [click-driven] [step 6] -> the 300k USD Donation article. NOT text, NOT a coordinate, NOT a goto for any user-driven step. Agent `browser_watch` while USER DRIVING showed the final article with no reload, agent `browser_open` while USER DRIVING returned the paused message (correct), and after handback `browser_watch`/`browser_watch_replay` still showed the 300k article, NOT reloaded to the homepage. Saved log: test-workspace/.shadowcode/browser-watch-20261102-040834-61868.json (9 entries: 3 scroll, 3 click-driven, 2 transitions, 6 action steps).
- Replay polish (Python + TS): no formatter change was needed — step numbering already continues 1..6, and both formatters print the identical 9-entry replay with the steps footer on the REAL saved log, not just unit fixtures. New pinning tests in both languages (Python `test_cycle18_three_page_chain_replay_is_step_numbered_1_to_6`, TS cycle 18 replay test) assert steps 1..6 in order, the footer `steps: 3 scroll, 3 click-driven, 2 driver transitions (6 action steps)`, and no cross-marking (scroll lines carry [scroll] only, click lines carry [click-driven] only; the via-selector check is on the via part only, since a scroll line's page URL legitimately is a click destination — a whole-line check on step 5 would falsely fail on its /news/2025-financials/ page URL, and that flawed first assertion was fixed in the test, not in the formatter). The TS BrowserWatchPanel header already shows the action-step count alongside entries/transitions/clicks/scrolls.
- Failed-site notes, honestly recorded: nginx.com and dart.dev both timed out at 30s on goto through this sandbox proxy in the cycle-18 probe and were NOT used and NOT claimed to load; ziglang.org was the ninth site that actually loaded and navigated for the full chain.
- Version 0.17.0 in sync across core, pyproject, and TS TUI.

## Cycle 19 (live replay, tenth site — four-page chain scroll -> click x4, steps 1..8)
- Live replay on a tenth site, NOT example.com/IANA, httpbin.org, iana.org, python.org, gnu.org, debian.org, rust-lang.org, ruby-lang.org, or ziglang.org: agent opened https://www.php.net/ ("PHP"), user took over via the preview, then across four source pages: (1) scrolled to `a[href='https://www.php.net/archive/2026.php#2026-10-21-4']` [scroll] [step 1] and clicked it [click-driven] [step 2] -> https://www.php.net/archive/2026.php#2026-10-21-4 ("PHP: News Archive - 2026"); (2) scrolled to `a[href='https://www.php.net/ChangeLog-8.php#8.5.12']` [scroll] [step 3] and clicked it [click-driven] [step 4] -> https://www.php.net/ChangeLog-8.php#8.5.12 ("PHP: PHP 8 ChangeLog"); (3) scrolled to `a[href='/sites.php']` [scroll] [step 5] and clicked it [click-driven] [step 6] -> https://www.php.net/sites.php ("PHP: A Tourist's Guide"); (4) scrolled to `a[href='/contact.php']` [scroll] [step 7] and clicked it [click-driven] [step 8] -> https://www.php.net/contact.php ("PHP: Contact"). NOT text, NOT a coordinate, NOT a goto for any user-driven step. Agent `browser_watch` while USER DRIVING showed the Contact page with no reload, agent `browser_open` while USER DRIVING returned the paused message (correct), and after handback `browser_watch`/`browser_watch_replay` still showed the Contact page, NOT reloaded to the homepage. Saved log: test-workspace/.shadowcode/browser-watch-20261102-051406-70249.json (11 entries: 4 scroll, 4 click-driven, 2 transitions, 8 action steps).
- Replay polish (Python + TS): no formatter change was needed — step numbering already continues 1..8, and both formatters print the identical 11-entry replay with the steps footer on the REAL saved log, not just unit fixtures. New pinning tests in both languages (Python `test_cycle19_four_page_chain_replay_is_step_numbered_1_to_8`, TS cycle 19 replay test) assert steps 1..8 in order, the footer `steps: 4 scroll, 4 click-driven, 2 driver transitions (8 action steps)`, no cross-marking, and that the scroll via selectors are exactly the four scroll selectors and the click via selectors exactly the four click selectors (checked on the via part only, since a scroll line's page URL legitimately is a click destination).
- Probe honesty: php.net home/archive news links carry absolute href attributes (`https://www.php.net/archive/2026.php#...`, `https://www.php.net/ChangeLog-8.php#...`) while footer links carry relative ones (`/sites.php`, `/contact.php`) — the chain's selectors use each page's actual attribute form, verified by probe before the live run, not guessed. No site in the cycle-19 probe failed in a way that changes the evidence: perl.org, php.net, nodejs.org, lua.org, scala-lang.org, and elixir-lang.org all loaded; php.net was chosen for its four-page internal-link chain.
- Script-note honesty: the first live script's saved-log reload used `load_saved_watch_log()` as if it returned entries alone; it returns `(path, entries)`, so that reload line raised AttributeError after the replay had already printed. That was a bug in the throwaway /tmp script, not in Shadowcode: re-running the reload correctly returns the same 11-entry log, and the live replay itself (from `browser_watch_replay`) was unaffected. The script was not shipped.
- Version 0.18.0 in sync across core, pyproject, and TS TUI.

## Cycle 20 (live replay, eleventh site — five-page chain scroll -> click x5, steps 1..10)
- Live replay on an eleventh site, NOT example.com/IANA, httpbin.org, iana.org, python.org, gnu.org, debian.org, rust-lang.org, ruby-lang.org, ziglang.org, or php.net: agent opened https://www.perl.org/ ("The Perl Programming Language - www.perl.org"), user took over via the preview, then across five source pages: (1) scrolled to `a[href='/contribute.html']` [scroll] [step 1] and clicked it [click-driven] [step 2] -> https://www.perl.org/contribute.html ("Contribute to Perl - www.perl.org"); (2) scrolled to `a[href='/siteinfo.html']` [scroll] [step 3] and clicked it [click-driven] [step 4] -> https://www.perl.org/siteinfo.html ("Site Information - www.perl.org"); (3) scrolled to `a[href='/about/whitepapers/']` [scroll] [step 5] and clicked it [click-driven] [step 6] -> https://www.perl.org/about/whitepapers/ ("Perl 5 White Papers - www.perl.org"); (4) scrolled to `a[href='/app.html']` [scroll] [step 7] and clicked it [click-driven] [step 8] -> https://www.perl.org/app.html ("Application Programming - www.perl.org"); (5) scrolled to `a[href='/about/style-guide.html']` [scroll] [step 9] and clicked it [click-driven] [step 10] -> https://www.perl.org/about/style-guide.html ("Perl or perl? - www.perl.org"). NOT text, NOT a coordinate, NOT a goto for any user-driven step. Agent `browser_watch` while USER DRIVING showed the style-guide page with no reload, agent `browser_open` while USER DRIVING returned the paused message (correct), and after handback `browser_watch`/`browser_watch_replay` still showed the style-guide page, NOT reloaded to the homepage. Saved log: test-workspace/.shadowcode/browser-watch-20261102-062215-79224.json (13 entries: 5 scroll, 5 click-driven, 2 transitions, 10 action steps).
- Replay polish (Python + TS): no formatter change was needed — step numbering already continues 1..10, and both formatters print the identical 13-entry replay with the steps footer on the REAL saved log, not just unit fixtures. New pinning tests in both languages (Python `test_cycle20_five_page_chain_replay_is_step_numbered_1_to_10`, TS cycle 20 replay test) assert steps 1..10 in order, the footer `steps: 5 scroll, 5 click-driven, 2 driver transitions (10 action steps)`, no cross-marking, and that the scroll via selectors are exactly the five scroll selectors and the click via selectors exactly the five click selectors (checked on the via part only, since a scroll line's page URL legitimately is a click destination).
- Probe honesty: perl.org, lua.org, scala-lang.org, elixir-lang.org, and nodejs.org all loaded in the cycle-20 probe; perl.org was chosen for its five-page internal-link chain, with each selector's count/top verified by probe before the live run (contribute top 700 on home, siteinfo top 930 on contribute, whitepapers top 2044 on siteinfo, app top 903 on whitepapers, style-guide top 1208 on app). Intermittent sandbox-proxy slowness was observed honestly and did NOT become evidence: /about/whitepapers/ and /app.html each timed out once at 30–60s in probes and then loaded cleanly on retry, and /camel.html timed out at 60s in a probe and was NOT used; the live chain itself landed every page on the first attempt.
- Script-note honesty: the live script was run from the home directory, so its relative workdir first wrote the saved log to ~/test-workspace/.shadowcode/ instead of the project workdir. The file itself was NOT edited: it was moved unchanged (same name, same 13 entries, same content) into test-workspace/.shadowcode/, after which `./shadowcode --workdir test-workspace --browser-watch` prints the identical 13-entry replay. The stray ~/test-workspace directory was removed.
- Version 0.19.0 in sync across core, pyproject, and TS TUI.

## Cycle 21 (live replay, twelfth site — six-page chain scroll -> click x6, steps 1..12)
- Live replay on a twelfth site, NOT example.com/IANA, httpbin.org, iana.org, python.org, gnu.org, debian.org, rust-lang.org, ruby-lang.org, ziglang.org, php.net, or perl.org: agent opened https://www.scala-lang.org/ ("The Scala Programming Language"), user took over via the preview, then across six source pages: (1) scrolled to `a[href='/conduct.html']` [scroll] [step 1] and clicked it [click-driven] [step 2] -> https://www.scala-lang.org/conduct.html ("Loading https://www.scala-lang.org/conduct/", settling to https://www.scala-lang.org/conduct/, "The Scala Code of Conduct | The Scala Programming Language"); (2) scrolled to `a[href='/license/']` [scroll] [step 3] and clicked it [click-driven] [step 4] -> https://www.scala-lang.org/license/ ("Scala License | The Scala Programming Language"); (3) scrolled to `a[href='/security/']` [scroll] [step 5] and clicked it [click-driven] [step 6] -> https://www.scala-lang.org/security/ ("Scala Security Policy | The Scala Programming Language"); (4) scrolled to `a[href='/governance/']` [scroll] [step 7] and clicked it [click-driven] [step 8] -> https://www.scala-lang.org/governance/ ("Governance | The Scala Programming Language"); (5) scrolled to `a[href='/blog/']` [scroll] [step 9] and clicked it [click-driven] [step 10] -> https://www.scala-lang.org/blog/ ("Blog | The Scala Programming Language"); (6) scrolled to `a[href='/download/']` [scroll] [step 11] and clicked it [click-driven] [step 12] -> https://www.scala-lang.org/download/ ("Install | The Scala Programming Language"). NOT text, NOT a coordinate, NOT a goto for any user-driven step. Agent `browser_watch` while USER DRIVING showed the download page with no reload, agent `browser_open` while USER DRIVING returned the paused message (correct), and after handback `browser_watch`/`browser_watch_replay` still showed the download page, NOT reloaded to the homepage. Saved log: test-workspace/.shadowcode/browser-watch-20261102-062658-81053.json (16 entries: 6 scroll, 6 click-driven, 2 transitions, 12 action steps, plus one non-action title-settle entry).
- Replay polish (Python + TS): no formatter change was needed — step numbering already continues 1..12, and both formatters print the identical 16-entry replay with the steps footer on the REAL saved log, not just unit fixtures. New pinning tests in both languages (Python `test_cycle21_six_page_chain_replay_is_step_numbered_1_to_12`, TS cycle 21 replay test) assert steps 1..12 in order, the footer `steps: 6 scroll, 6 click-driven, 2 driver transitions (12 action steps)`, no cross-marking, that the scroll via selectors are exactly the six scroll selectors and the click via selectors exactly the six click selectors (checked on the via part only, since a scroll line's page URL legitimately is a click destination), and that the title-settle entry gets no step number.
- Probe honesty: lua.org, scala-lang.org, elixir-lang.org, and nodejs.org all loaded in the cycle-21 probe; scala-lang.org was chosen for its six-page internal-link chain, with each selector verified by probe before the live run (conduct top 2537 on home, license top 4408 on conduct, security top 887 on license; governance/blog/download selectors match the nav first, top 39, on their source pages — the scroll still records an entry and the click is a real element click, not a goto). The live chain landed every page on the first attempt, with no proxy timeout in the live run. The conduct link canonicalises: the click first landed on /conduct.html (title "Loading...") and settled to /conduct/ with the final title, recorded as a separate non-action entry in the saved log — not hidden, and it does not disturb step numbering.
- Script-note honesty: unlike cycle 20, the live script was run from inside ~/workspace/shadowcode, so its saved log landed directly in test-workspace/.shadowcode/ with no move and no stray directory. The script was not shipped, and the browser process exited with the script (no Firefox left running).
- Version 0.20.0 in sync across core, pyproject, and TS TUI.

## Cycle 22 (live replay, thirteenth site — seven-page chain scroll -> click x7, steps 1..14)
- Live replay on a thirteenth site, NOT example.com/IANA, httpbin.org, iana.org, python.org, gnu.org, debian.org, rust-lang.org, ruby-lang.org, ziglang.org, php.net, perl.org, or scala-lang.org: agent opened https://elixir-lang.org/ ("The Elixir programming language"), user took over via the preview, then across seven source pages: (1) scrolled to `a[href='/install/']` [scroll] [step 1] and clicked it [click-driven] [step 2] -> https://elixir-lang.org/install/ ("Install Elixir | The Elixir programming language"); (2) scrolled to `a[href='/learning/']` [scroll] [step 3] and clicked it [click-driven] [step 4] -> https://elixir-lang.org/learning/ ("Learning | The Elixir programming language"); (3) scrolled to `a[href='/docs/']` [scroll] [step 5] and clicked it [click-driven] [step 6] -> https://elixir-lang.org/docs/ ("Documentation | The Elixir programming language"); (4) scrolled to `a[href='/cases/']` [scroll] [step 7] and clicked it [click-driven] [step 8] -> https://elixir-lang.org/cases/ ("Case studies | The Elixir programming language"); (5) scrolled to `a[href='/blog/']` [scroll] [step 9] and clicked it [click-driven] [step 10] -> https://elixir-lang.org/blog/ ("Blog | The Elixir programming language"); (6) scrolled to `a[href='/development/']` [scroll] [step 11] and clicked it [click-driven] [step 12] -> https://elixir-lang.org/development/ ("Development & team | The Elixir programming language"); (7) scrolled to `a[href='/trademarks/']` [scroll] [step 13] and clicked it [click-driven] [step 14] -> https://elixir-lang.org/trademarks/ ("Trademarks policy | The Elixir programming language"). NOT text, NOT a coordinate, NOT a goto for any user-driven step. Agent `browser_watch` while USER DRIVING showed the trademarks page with no reload, agent `browser_open` while USER DRIVING returned the paused message (correct), and after handback `browser_watch`/`browser_watch_replay` still showed the trademarks page, NOT reloaded to the homepage. Saved log: test-workspace/.shadowcode/browser-watch-20261102-063541-83479.json (17 entries: 7 scroll, 7 click-driven, 2 transitions, 14 action steps).
- Replay polish (Python + TS): no formatter change was needed — step numbering already continues 1..14, and both formatters print the identical 17-entry replay with the steps footer on the REAL saved log, not just unit fixtures. New pinning tests in both languages (Python `test_cycle22_seven_page_chain_replay_is_step_numbered_1_to_14`, TS cycle 22 replay test) assert steps 1..14 in order, the footer `steps: 7 scroll, 7 click-driven, 2 driver transitions (14 action steps)`, no cross-marking, and that the scroll via selectors are exactly the seven scroll selectors and the click via selectors exactly the seven click selectors (checked on the via part only, since a scroll line's page URL legitimately is a click destination).
- Probe honesty: elixir-lang.org, nodejs.org, julialang.org, kotlinlang.org, swift.org, haskell.org, ocaml.org, crystal-lang.org, and nim-lang.org all loaded in the cycle-22 probe; elixir-lang.org was chosen for its seven-page internal-link chain, with each selector verified by probe before the live run (install nav first match top 78 on home; learning/docs/cases/blog nav first matches top 78 on their source pages; development footer link on the blog page; trademarks top 3191 on the development page). One probe correction, recorded not hidden: the blog page carries NO `/stewards/` link, so the planned blog -> stewards pair was replaced before the live run by blog -> development (footer link) and development -> trademarks — the chain as run is the chain as logged. The live chain landed every page on the first attempt, with no proxy timeout in the live run.
- Script-note honesty: the live script was run from inside ~/workspace/shadowcode, so its saved log landed directly in test-workspace/.shadowcode/ with no move and no stray directory. The script was not shipped, and the browser process exited with the script (no Firefox left running).
- Version 0.21.0 in sync across core, pyproject, and TS TUI.

## Cycle 23 (live replay, fourteenth site — eight-page chain scroll -> click x8, steps 1..16)
- Live replay on a fourteenth site, NOT example.com/IANA, httpbin.org, iana.org, python.org, gnu.org, debian.org, rust-lang.org, ruby-lang.org, ziglang.org, php.net, perl.org, scala-lang.org, or elixir-lang.org: agent opened https://www.lua.org/ ("The Programming Language Lua"), user took over via the preview, then across eight source pages: (1) scrolled to `a[href='start.html']` [scroll] [step 1] and clicked it [click-driven] [step 2] -> https://www.lua.org/start.html ("Lua: getting started"); (2) scrolled to `a[href='docs.html']` [scroll] [step 3] and clicked it [click-driven] [step 4] -> https://www.lua.org/docs.html ("Lua: documentation"); (3) scrolled to `a[href='faq.html']` [scroll] [step 5] and clicked it [click-driven] [step 6] -> https://www.lua.org/faq.html ("Lua: FAQ"); (4) scrolled to `a[href='versions.html']` [scroll] [step 7] and clicked it [click-driven] [step 8] -> https://www.lua.org/versions.html ("Lua: version history"); (5) scrolled to `a[href='license.html']` [scroll] [step 9] and clicked it [click-driven] [step 10] -> https://www.lua.org/license.html ("Lua: license"); (6) scrolled to `a[href='authors.html']` [scroll] [step 11] and clicked it [click-driven] [step 12] -> https://www.lua.org/authors.html ("Lua: authors"); (7) scrolled to `a[href='thanks.html']` [scroll] [step 13] and clicked it [click-driven] [step 14] -> https://www.lua.org/thanks.html ("Lua: thanks"); (8) scrolled to `a[href='donations.html']` [scroll] [step 15] and clicked it [click-driven] [step 16] -> https://www.lua.org/donations.html ("Lua: donations"). NOT text, NOT a coordinate, NOT a goto for any user-driven step. Agent `browser_watch` while USER DRIVING showed the donations page with no reload, agent `browser_open` while USER DRIVING returned the paused message (correct), and after handback `browser_watch`/`browser_watch_replay` still showed the donations page, NOT reloaded to the homepage. Saved log: test-workspace/.shadowcode/browser-watch-20261102-063954-85151.json (19 entries: 8 scroll, 8 click-driven, 2 transitions, 16 action steps).
- Replay polish (Python + TS): no formatter change was needed — step numbering already continues 1..16, and both formatters print the identical 19-entry replay with the steps footer on the REAL saved log, not just unit fixtures. New pinning tests in both languages (Python `test_cycle23_eight_page_chain_replay_is_step_numbered_1_to_16`, TS cycle 23 replay test) assert steps 1..16 in order, the footer `steps: 8 scroll, 8 click-driven, 2 driver transitions (16 action steps)`, no cross-marking, and that the scroll via selectors are exactly the eight scroll selectors and the click via selectors exactly the eight click selectors (checked on the via part only, since a scroll line's page URL legitimately is a click destination).
- Probe honesty: lua.org and nodejs.org both loaded in the cycle-23 probe; lua.org was chosen for its eight-page internal-link chain, with each selector verified by probe before the live run (start.html count 1, top 174 on home; docs.html count 1, top 726 on start — below the fold; faq.html count 2, first top 202 on docs; versions.html count 2, first top 1326 on faq — below the fold; license.html count 1, top 1545 on versions — below the fold; authors.html count 1, top 530 on license; thanks.html count 1, top 552 on authors; donations.html count 1 on thanks). One probe correction, recorded not hidden: the thanks page carries NO `contact.html` link (count 0), so the planned thanks -> contact pair was replaced before the live run by thanks -> donations — the chain as run is the chain as logged. The live chain landed every page on the first attempt, with no proxy timeout in the live run.
- Script-note honesty: the live script was run from inside ~/workspace/shadowcode, so its saved log landed directly in test-workspace/.shadowcode/ with no move and no stray directory. The script was not shipped, and the browser process exited with the script (no Firefox left running).
- Version 0.22.0 in sync across core, pyproject, and TS TUI.

## Cycle 24 (live replay, fifteenth site — nine-page chain scroll -> click x9, steps 1..18)
- Live replay on a fifteenth site, NOT example.com/IANA, httpbin.org, iana.org, python.org, gnu.org, debian.org, rust-lang.org, ruby-lang.org, ziglang.org, php.net, perl.org, scala-lang.org, elixir-lang.org, or lua.org: agent opened https://ocaml.org/ ("Welcome to a World of OCaml"), user took over via the preview, then across nine source pages: (1) scrolled to `a[href='/docs']` [scroll] [step 1] and clicked it [click-driven] [step 2] -> https://ocaml.org/docs ("Learn OCaml"); (2) scrolled to `a[href='/tools']` [scroll] [step 3] and clicked it [click-driven] [step 4] -> https://ocaml.org/platform ("OCaml Platform"); (3) scrolled to `a[href='/packages']` [scroll] [step 5] and clicked it [click-driven] [step 6] -> https://ocaml.org/packages ("OCaml Packages · Browse Community Packages"); (4) scrolled to `a[href='/community']` [scroll] [step 7] and clicked it [click-driven] [step 8] -> https://ocaml.org/community ("The OCaml Community"); (5) scrolled to `a[href='/changelog']` [scroll] [step 9] and clicked it [click-driven] [step 10] -> https://ocaml.org/changelog ("OCaml Changelog"); (6) scrolled to `a[href='/events']` [scroll] [step 11] and clicked it [click-driven] [step 12] -> https://ocaml.org/events ("Upcoming OCaml Events"); (7) scrolled to `a[href='/jobs']` [scroll] [step 13] and clicked it [click-driven] [step 14] -> https://ocaml.org/jobs ("OCaml Jobs"); (8) scrolled to `a[href='/security']` [scroll] [step 15] and clicked it [click-driven] [step 16] -> https://ocaml.org/security ("OCaml Security"); (9) scrolled to `a[href='/governance']` [scroll] [step 17] and clicked it [click-driven] [step 18] -> https://ocaml.org/governance ("Governance"). NOT text, NOT a coordinate, NOT a goto for any user-driven step. Agent `browser_watch` while USER DRIVING showed the governance page with no reload, agent `browser_open` while USER DRIVING returned the paused message (correct), and after handback `browser_watch`/`browser_watch_replay` still showed the governance page, NOT reloaded to the homepage. Saved log: test-workspace/.shadowcode/browser-watch-20261102-065220-88511.json (21 entries: 9 scroll, 9 click-driven, 2 transitions, 18 action steps).
- Replay polish (Python + TS): no formatter change was needed — step numbering already continues 1..18, and both formatters print the identical 21-entry replay with the steps footer on the REAL saved log, not just unit fixtures. New pinning tests in both languages (Python `test_cycle24_nine_page_chain_replay_is_step_numbered_1_to_18`, TS cycle 24 replay test) assert steps 1..18 in order, the footer `steps: 9 scroll, 9 click-driven, 2 driver transitions (18 action steps)`, no cross-marking, and that the scroll via selectors are exactly the nine scroll selectors and the click via selectors exactly the nine click selectors (checked on the via part only, since a scroll line's page URL legitimately is a click destination).
- Probe honesty: nodejs.org, julialang.org, kotlinlang.org, ocaml.org, nim-lang.org, crystal-lang.org, haskell.org, and go.dev loaded in the cycle-24 probe; swift.org and djangoproject.com (www.djangoproject.com) timed out at 30s on goto in that probe and were NOT used and NOT claimed to load. ocaml.org was chosen for its nine-page internal-link chain, with each selector verified by probe before the live run (docs count 2, nav first top 16 on home; tools count 2, nav first top 16 on docs; packages count 3, nav first top 16 on platform; community count 3, nav first top 16 on packages; changelog count 3, nav first top 16 on community; events count 1, top 49853 on changelog — footer, below the fold; jobs count 2, first top 80 on events; security count 1, top 3020 on jobs; governance count 1, top 2604 on security). Two probe corrections, recorded not hidden: the /play page carries NO /events link, so the planned changelog -> play -> events route was replaced before the live run by changelog -> events directly (footer link on the changelog page); and /tools canonicalises to /platform, so the first live run's expected /tools URL failed its landing check and was aborted (partial 7-entry log browser-watch-20261102-065011-87783.json, NOT claimed as evidence) and the corrected chain, expecting /platform, landed every page on the first attempt in the second live run. The chain as run is the chain as logged.
- Script-note honesty: the live script was run from inside ~/workspace/shadowcode, so its saved log landed directly in test-workspace/.shadowcode/ with no move and no stray directory. The script was not shipped, and the browser process exited with the script (no Firefox left running).
- Version 0.23.0 in sync across core, pyproject, and TS TUI.

## Cycle 25 (live replay, sixteenth site — ten-page chain scroll -> click x10, steps 1..20)
- Live replay on a sixteenth site, NOT example.com/IANA, httpbin.org, iana.org, python.org, gnu.org, debian.org, rust-lang.org, ruby-lang.org, ziglang.org, php.net, perl.org, scala-lang.org, elixir-lang.org, lua.org, or ocaml.org: agent opened https://julialang.org/ ("The Julia Programming Language"), user took over via the preview, then across ten source pages: (1) scrolled to `a[href='/downloads/']` [scroll] [step 1] and clicked it [click-driven] [step 2] -> https://julialang.org/downloads/ ("Installing Julia"); (2) scrolled to `a[href='/learning/']` [scroll] [step 3] and clicked it [click-driven] [step 4] -> https://julialang.org/learning/ ("Get started with Julia"); (3) scrolled to `a[href='/blog/']` [scroll] [step 5] and clicked it [click-driven] [step 6] -> https://julialang.org/blog/ ("The Julia Language Blog"); (4) scrolled to `a[href='/community/']` [scroll] [step 7] and clicked it [click-driven] [step 8] -> https://julialang.org/community/ ("Community"); (5) scrolled to `a[href='/contribute/']` [scroll] [step 9] and clicked it [click-driven] [step 10] -> https://julialang.org/contribute/ ("Ask and answer questions"); (6) scrolled to `a[href='/jsoc/']` [scroll] [step 11] and clicked it [click-driven] [step 12] -> https://julialang.org/jsoc/ ("Julia Seasons of Contributions"); (7) scrolled to `a[href='/community/standards/']` [scroll] [step 13] and clicked it [click-driven] [step 14] -> https://julialang.org/community/standards/ ("Julia Community - Standards"); (8) scrolled to `a[href='/community/stewards/']` [scroll] [step 15] and clicked it [click-driven] [step 16] -> https://julialang.org/community/stewards/ ("Julia Community - Stewards"); (9) scrolled to `a[href='/governance/']` [scroll] [step 17] and clicked it [click-driven] [step 18] -> https://julialang.org/governance/ ("Julia Governance"); (10) scrolled to `a[href='/diversity/']` [scroll] [step 19] and clicked it [click-driven] [step 20] -> https://julialang.org/diversity/ ("Diversity"). NOT text, NOT a coordinate, NOT a goto for any user-driven step. Agent `browser_watch` while USER DRIVING showed the diversity page with no reload, agent `browser_open` while USER DRIVING returned the paused message (correct), and after handback `browser_watch`/`browser_watch_replay` still showed the diversity page, NOT reloaded to the homepage. Saved log: test-workspace/.shadowcode/browser-watch-20261102-070641-91844.json (23 entries: 10 scroll, 10 click-driven, 2 transitions, 20 action steps).
- Replay polish (Python + TS): no formatter change was needed — step numbering already continues 1..20, and both formatters print the identical 23-entry replay with the steps footer on the REAL saved log, not just unit fixtures. New pinning tests in both languages (Python `test_cycle25_ten_page_chain_replay_is_step_numbered_1_to_20`, TS cycle 25 replay test) assert steps 1..20 in order, the footer `steps: 10 scroll, 10 click-driven, 2 driver transitions (20 action steps)`, no cross-marking, and that the scroll via selectors are exactly the ten scroll selectors and the click via selectors exactly the ten click selectors (checked on the via part only, since a scroll line's page URL legitimately is a click destination).
- Probe honesty: nodejs.org, julialang.org, kotlinlang.org, nim-lang.org, crystal-lang.org, haskell.org, and go.dev loaded in the cycle-25 probe; julialang.org was chosen for its ten-page internal-link chain, with each selector verified by probe before the live run (downloads count 1, nav top 14 on home; learning count 1, nav top 14 on downloads; blog count 1, nav top 14 on learning; community count 2, nav top 14 on blog; contribute count 1, nav top 14 on community; jsoc count 1, nav top 14 on contribute; community/standards count 1, footer top 2098 on jsoc — below the fold; community/stewards count 3, first top 571 on standards; governance count 1, footer top 1857 on stewards — below the fold; diversity count 1, footer top 2455 on governance — below the fold). Two probe corrections, recorded not hidden: the first-planned chain after jsoc used /install/ -> /benchmarks/ -> /packages/, but /install/ redirects to /downloads, /benchmarks/ has no /packages/ link (count 0), and /packages/ redirects to /community/packages, so that tail was replaced before the live run by jsoc -> community/standards -> community/stewards -> governance -> diversity, all verified by probe. The live chain landed every page on the first attempt, with no proxy timeout in the live run. The chain as run is the chain as logged.
- Script-note honesty: the live script was run from inside ~/workspace/shadowcode, so its saved log landed directly in test-workspace/.shadowcode/ with no move and no stray directory. The script was not shipped, and the browser process exited with the script (no Firefox left running).
- Version 0.25.0 in sync across core, pyproject, and TS TUI.

## Cycle 26 (live replay, seventeenth site — eleven-page chain scroll -> click x11, steps 1..22)
- Live replay on a seventeenth site, NOT example.com/IANA, httpbin.org, iana.org, python.org, gnu.org, debian.org, rust-lang.org, ruby-lang.org, ziglang.org, php.net, perl.org, scala-lang.org, elixir-lang.org, lua.org, ocaml.org, or julialang.org: agent opened https://crystal-lang.org/ ("The Crystal Programming Language"), user took over via the preview, then across eleven source pages: (1) scrolled to `a[href='/install/']` [scroll] [step 1] and clicked it [click-driven] [step 2] -> https://crystal-lang.org/install/ ("Install"); (2) scrolled to `a[href='/blog/']` [scroll] [step 3] and clicked it [click-driven] [step 4] -> https://crystal-lang.org/blog/ ("News"); (3) scrolled to `a[href='/releases/']` [scroll] [step 5] and clicked it [click-driven] [step 6] -> https://crystal-lang.org/releases/ ("Releases"); (4) scrolled to `a[href='/community/']` [scroll] [step 7] and clicked it [click-driven] [step 8] -> https://crystal-lang.org/community/ ("Community"); (5) scrolled to `a[href='/sponsors/']` [scroll] [step 9] and clicked it [click-driven] [step 10] -> https://crystal-lang.org/sponsors/ ("Sponsors"); (6) scrolled to `a[href='/success-stories/']` [scroll] [step 11] and clicked it [click-driven] [step 12] -> https://crystal-lang.org/success-stories/ ("Success stories"); (7) scrolled to `a[href='/used_in_prod/']` [scroll] [step 13] and clicked it [click-driven] [step 14] -> https://crystal-lang.org/used_in_prod/ ("Used in production"); (8) scrolled to `a[href='/team/']` [scroll] [step 15] and clicked it [click-driven] [step 16] -> https://crystal-lang.org/team/ ("Team"); (9) scrolled to `a[href='/community/governance/']` [scroll] [step 17] and clicked it [click-driven] [step 18] -> https://crystal-lang.org/community/governance/ ("Crystal governance"); (10) scrolled to `a[href='/media/']` [scroll] [step 19] and clicked it [click-driven] [step 20] -> https://crystal-lang.org/media/ ("Media"); (11) scrolled to `a[href='/learning/']` [scroll] [step 21] and clicked it [click-driven] [step 22] -> https://crystal-lang.org/learning/ ("External resources"). NOT text, NOT a coordinate, NOT a goto for any user-driven step. Mid-chain agent `browser_watch` while USER DRIVING showed the current page with no reload, agent `browser_open` while USER DRIVING returned the paused message (correct), and after handback `browser_watch`/`browser_watch_replay` still showed the learning page, NOT reloaded to the homepage. Saved log: test-workspace/.shadowcode/browser-watch-20261102-071442-95168.json (25 entries: 11 scroll, 11 click-driven, 2 transitions, 22 action steps).
- Replay polish (Python + TS): no formatter change was needed — step numbering already continues 1..22, and both formatters print the identical 25-entry replay with the steps footer on the REAL saved log, not just unit fixtures. New pinning tests in both languages (Python `test_cycle26_eleven_page_chain_replay_is_step_numbered_1_to_22`, TS cycle 26 replay test) assert steps 1..22 in order, the footer `steps: 11 scroll, 11 click-driven, 2 driver transitions (22 action steps)`, no cross-marking, and that the scroll via selectors are exactly the eleven scroll selectors and the click via selectors exactly the eleven click selectors (checked on the via part only, since a scroll line's page URL legitimately is a click destination).
- Probe honesty: kotlinlang.org, nodejs.org, nim-lang.org, crystal-lang.org, haskell.org, and go.dev loaded in the cycle-26 probe; crystal-lang.org was chosen because its chain selectors all have a VISIBLE first match (unlike kotlinlang.org, where several home-nav first matches are hidden mobile-menu items, and go.dev, where /doc's first match on the learn page is hidden — both would have failed the live `.first.click`). Each selector was verified by probe before the live run (install count 2, top 229 on home; blog count 2, top 38 on install; releases count 2, top 482 on blog; community count 1, top 35 on releases; sponsors count 3, top 53 on community; success-stories count 1, top 26549 on sponsors — below the fold; used_in_prod count 2, top 317 on success-stories; team count 2, top 53 on used_in_prod; governance count 3, top 53 on team; media count 1, top 5068 on governance — below the fold; learning count 1, top 53 on media). One probe correction, recorded not hidden: the first-planned chain after used_in_prod used /reference/, but that page carries NO /reference/ link (count 0), so the tail was replaced before the live run by used_in_prod -> team -> community/governance -> media -> learning, all verified by probe (including a separate tail walk used_in_prod -> team -> governance -> media -> learning). The live chain landed every page on the first attempt, with no proxy timeout in the live run. The chain as run is the chain as logged.
- Script-note honesty: the live script was run from inside ~/workspace/shadowcode, so its saved log landed directly in test-workspace/.shadowcode/ with no move and no stray directory. The script was not shipped, and the browser process exited with the script (no Firefox left running).
- Version 0.26.0 in sync across core, pyproject, and TS TUI.

## Cycle 27 (live replay, eighteenth site — twelve-page chain scroll -> click x12, steps 1..24)
- Live replay on an eighteenth site, NOT example.com/IANA, httpbin.org, iana.org, python.org, gnu.org, debian.org, rust-lang.org, ruby-lang.org, ziglang.org, php.net, perl.org, scala-lang.org, elixir-lang.org, lua.org, ocaml.org, julialang.org, or crystal-lang.org: agent opened https://clojure.org/ ("Clojure"), user took over via the preview, then across twelve source pages: (1) scrolled to `a[href='/about/rationale']` [scroll] [step 1] and clicked it [click-driven] [step 2] -> https://clojure.org/about/rationale ("Clojure - Rationale"); (2) scrolled to `a[href='/reference/documentation']` [scroll] [step 3] and clicked it [click-driven] [step 4] -> https://clojure.org/reference/reader ("Clojure - The Reader", canonicalised from /reference/documentation); (3) scrolled to `a[href='/api/api']` [scroll] [step 5] and clicked it [click-driven] [step 6] -> https://clojure.org/api/api ("Clojure - API Documentation"); (4) scrolled to `a[href='/releases/downloads']` [scroll] [step 7] and clicked it [click-driven] [step 8] -> https://clojure.org/releases/downloads ("Clojure - Clojure Downloads"); (5) scrolled to `a[href='/guides/guides']` [scroll] [step 9] and clicked it [click-driven] [step 10] -> https://clojure.org/guides/getting_started ("Clojure - Getting Started", canonicalised from /guides/guides); (6) scrolled to `a[href='/community/success_stories']` [scroll] [step 11] and clicked it [click-driven] [step 12] -> https://clojure.org/community/success_stories ("Clojure - Success Stories"); (7) scrolled to `a[href='/dev/dev']` [scroll] [step 13] and clicked it [click-driven] [step 14] -> https://clojure.org/dev/dev ("Clojure - Development"); (8) scrolled to `a[href='/news/news']` [scroll] [step 15] and clicked it [click-driven] [step 16] -> https://clojure.org/news/news ("Clojure - News"); (9) scrolled to `a[href='/community/resources']` [scroll] [step 17] and clicked it [click-driven] [step 18] -> https://clojure.org/community/resources ("Clojure - Community Resources"); (10) scrolled to `a[href='/community/contributing']` [scroll] [step 19] and clicked it [click-driven] [step 20] -> https://clojure.org/community/contributing ("Clojure - Contributing"); (11) scrolled to `a[href='/community/companies']` [scroll] [step 21] and clicked it [click-driven] [step 22] -> https://clojure.org/community/companies ("Clojure - Companies"); (12) scrolled to `a[href='/community/license']` [scroll] [step 23] and clicked it [click-driven] [step 24] -> https://clojure.org/community/license ("Clojure - License"). NOT text, NOT a coordinate, NOT a goto for any user-driven step. Mid-chain agent `browser_watch` while USER DRIVING showed the current page with no reload, agent `browser_open` while USER DRIVING returned the paused message (correct), and after handback `browser_watch`/`browser_watch_replay` still showed the license page, NOT reloaded to the homepage. Saved log: test-workspace/.shadowcode/browser-watch-20261102-072155-97897.json (27 entries: 12 scroll, 12 click-driven, 2 transitions, 24 action steps).
- Replay polish (Python + TS): no formatter change was needed — step numbering already continues 1..24, and both formatters print the identical 27-entry replay with the steps footer on the REAL saved log, not just unit fixtures. New pinning tests in both languages (Python `test_cycle27_twelve_page_chain_replay_is_step_numbered_1_to_24`, TS cycle 27 replay test) assert steps 1..24 in order, the footer `steps: 12 scroll, 12 click-driven, 2 driver transitions (24 action steps)`, no cross-marking, and that the scroll via selectors are exactly the twelve scroll selectors and the click via selectors exactly the twelve click selectors (checked on the via part only, since a scroll line's page URL legitimately is a click destination).
- Probe honesty: haskell.org returned no relative internal links in the probe (its homepage links are not usable CSS selectors here) and dlang.org timed out at 30s, so neither was used or claimed; racket-lang.org, clojure.org, elm-lang.org, nodejs.org, nim-lang.org, kotlinlang.org, and go.dev loaded. clojure.org was chosen because every chain selector's FIRST match is visible (rationale count 2, nav top 0 on home; reference/documentation count 2, nav top 0 on rationale; api/api count 2, nav top 0 on reader; releases/downloads count 2, nav top 0 on api; guides/guides count 2, nav top 0 on downloads; success_stories count 1, nav top 0 on getting_started; dev/dev count 1, nav top 0 on success_stories; news/news count 2, nav top 0 on dev; resources count 1, footer top 15376 on news — below the fold; contributing count 1, top 3085 on resources — below the fold; companies count 1, top 1965 on contributing — below the fold; license count 1, top 13582 on companies — below the fold). Two canonicalisations, recorded not hidden: /reference/documentation lands on /reference/reader and /guides/guides lands on /guides/getting_started; the live landing check accepted those canonical pages, and the log shows them. The live chain landed every page on the first attempt, with no proxy timeout in the live run. The chain as run is the chain as logged.
- Script-note honesty: the live script was run from inside ~/workspace/shadowcode, so its saved log landed directly in test-workspace/.shadowcode/ with no move and no stray directory. The script was not shipped, and the browser process exited with the script (no Firefox left running).
- Version 0.27.0 in sync across core, pyproject, and TS TUI.

## Cycle 28 (live replay, nineteenth site — thirteen-page chain scroll -> click x13, steps 1..26)
- Live replay on a nineteenth site, NOT example.com/IANA, httpbin.org, iana.org, python.org, gnu.org, debian.org, rust-lang.org, ruby-lang.org, ziglang.org, php.net, perl.org, scala-lang.org, elixir-lang.org, lua.org, ocaml.org, julialang.org, crystal-lang.org, or clojure.org: agent opened https://www.erlang.org/ ("Index - Erlang/OTP"), user took over via the preview, then across thirteen source pages: (1) scrolled to `a[href='/downloads']` [scroll] [step 1] and clicked it [click-driven] [step 2] -> https://www.erlang.org/downloads ("Downloads - Erlang/OTP"); (2) scrolled to `a[href='/downloads/29']` [scroll] [step 3] and clicked it [click-driven] [step 4] -> https://www.erlang.org/downloads/29 ("29 - Erlang/OTP"); (3) scrolled to `a[href='/eeps/eep-0079']` [scroll] [step 5] and clicked it [click-driven] [step 6] -> https://www.erlang.org/eeps/eep-0079 ("Eep 0079 - Erlang/OTP"); (4) scrolled to `a[href='/docs']` [scroll] [step 7] and clicked it [click-driven] [step 8] -> https://www.erlang.org/docs.html ("Documentation - Erlang/OTP"); (5) scrolled to `a[href='/community']` [scroll] [step 9] and clicked it [click-driven] [step 10] -> https://www.erlang.org/community ("Community - Erlang/OTP"); (6) scrolled to `a[href='/news']` [scroll] [step 11] and clicked it [click-driven] [step 12] -> https://www.erlang.org/news ("News - Erlang/OTP"); (7) scrolled to `a[href='/news/191']` [scroll] [step 13] and clicked it [click-driven] [step 14] -> https://www.erlang.org/news/191 ("Erlang/OTP 29.1 Release - Erlang/OTP"); (8) scrolled to `a[href='/blog']` [scroll] [step 15] and clicked it [click-driven] [step 16] -> https://www.erlang.org/blog ("Blog - Erlang/OTP"); (9) scrolled to `a[href='/blog/highlights-otp-29/']` [scroll] [step 17] and clicked it [click-driven] [step 18] -> https://www.erlang.org/blog/highlights-otp-29/ ("Erlang/OTP 29 Highlights - Erlang/OTP"); (10) scrolled to `a[href='/security']` [scroll] [step 19] and clicked it [click-driven] [step 20] -> https://www.erlang.org/security ("Security - Erlang/OTP"); (11) scrolled to `a[href='/eep']` [scroll] [step 21] and clicked it [click-driven] [step 22] -> https://www.erlang.org/eep ("Erlang Enhancement Process - Erlang/OTP"); (12) scrolled to `a[href='/eeps/eep-0001']` [scroll] [step 23] and clicked it [click-driven] [step 24] -> https://www.erlang.org/eeps/eep-0001 ("Eep 0001 - Erlang/OTP"); (13) scrolled to `a[href='/about']` [scroll] [step 25] and clicked it [click-driven] [step 26] -> https://www.erlang.org/about ("About - Erlang/OTP"). NOT text, NOT a coordinate, NOT a goto for any user-driven step. Agent `browser_watch` while USER DRIVING showed the current page with no reload, agent `browser_open` while USER DRIVING returned the paused message (correct), and after handback `browser_watch`/`browser_watch_replay` still showed the about page, NOT reloaded to the homepage. Saved log: test-workspace/.shadowcode/browser-watch-20261102-074111-106335.json (29 entries: 13 scroll, 13 click-driven, 2 transitions, 26 action steps).
- Replay polish (Python + TS): no formatter change was needed — step numbering already continues 1..26, and both formatters print the identical 29-entry replay with the steps footer on the REAL saved log, not just unit fixtures. New pinning tests in both languages (Python `test_cycle28_thirteen_page_chain_replay_is_step_numbered_1_to_26`, TS cycle 28 replay test) assert steps 1..26 in order, the footer `steps: 13 scroll, 13 click-driven, 2 driver transitions (26 action steps)`, no cross-marking, and that the scroll via selectors are exactly the thirteen scroll selectors and the click via selectors exactly the thirteen click selectors (checked on the via part only, since a scroll line's page URL legitimately is a click destination).
- Probe honesty: racket-lang.org, elm-lang.org, nim-lang.org, go.dev, nodejs.org, haskell.org (no relative internal links usable as CSS selectors), fsharp.org, and erlang.org loaded in the cycle-28 probe; go.dev was REJECTED after a live failure, not just a probe doubt — the first live run landed /learn/ but pair 2 (`a[href='/doc'] >> nth=1`) failed: that match is a dropdown menu item ("Go User Manual") that Playwright reports visible/stable yet "outside of the viewport" on click, so the go.dev chain was abandoned and that partial run is NOT claimed as evidence. elm-lang.org was rejected because most pages link only back to the nav hubs, so no thirteen distinct destinations compose; fsharp.org was rejected because its nav links are 0x0 hidden-sidebar elements (not clickable). erlang.org was chosen because every chain selector's FIRST match is visible (downloads nav top 27 on home; downloads/29 first top 245 on downloads; eep-0079 top 465 on downloads/29; docs nav top 27 on eep-0079; community nav top 27 on docs; news nav top 27 on community; news/191 first top 126 on news; blog nav top 27 on news/191; highlights-otp-29 first top 126 on blog; security nav top 27 on highlights; eep nav top 27 on security; eep-0001 first top 642 on eep — below the fold; about nav top 27 on eep-0001). The live chain landed every page on the first attempt, with no proxy timeout in the live run. The chain as run is the chain as logged.
- Script-note honesty: the live script was run from inside ~/workspace/shadowcode, so its saved log landed directly in test-workspace/.shadowcode/ with no move and no stray directory. The script was not shipped, and the browser process exited with the script (no Firefox left running).
- Version 0.28.0 in sync across core, pyproject, and TS TUI.
