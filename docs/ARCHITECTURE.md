# Shadowcode architecture — polyglot monorepo

Shadowcode is one product, several languages, each chosen for what
it is genuinely best at. Nothing here is a placeholder: every
component below is real code with real tests (except the Go
binary build, which is deferred only because no Go toolchain is
installed in this environment — see MORNING_APPROVALS.md).

## Layout

```
main.py, shadowcode_pkg/   Python — agent core (see below)
tui/                       TypeScript/JavaScript — Ink/React TUI
web/index.html             TypeScript/JavaScript (plain JS) — preview frontend
go/                        Go — localhost preview + search service
native/                    C/C++ — native scanner / counter / fuzzy matcher
docs/ARCHITECTURE.md       this file
Makefile                   build-all / build-tui / build-go / build-native / test-all
```

## Which language does what, and why

| Area | Language | Why this language |
|---|---|---|
| Agent core: providers, tool loop, permissions, sessions, MCP, browser orchestration | Python | Existing, battle-tested core; rich stdlib; Playwright for the browser; fastest to iterate on agent logic |
| Terminal UI | TypeScript + Ink/React | Claude Code-style TUI needs a real component model (Header, Transcript, ToolPanel, StatusBar, Input, PermissionPrompt); Ink gives that in a terminal, with React state |
| Web preview frontend | TypeScript/JavaScript (plain JS in `web/index.html`) | The preview page is a browser page; JS polling `/state.json` + `/shot.png` is the native way to render it live |
| Shared types | TypeScript (`tui/src/lib/protocol.ts`) | The JSON-lines event types are the contract between TUI and core; TS types catch shape drift at build time |
| Localhost preview server + fast file search | Go | Go's stdlib HTTP server + goroutines handle many concurrent preview/search requests with low overhead; no external deps |
| Fast file scanner / line counter / fuzzy matcher | C++ | Block-wise I/O and tight loops beat interpreted code for large trees; a C ABI lets Python (ctypes), Go (cgo), and TS (CLI) all call the same code |

## How the components talk to each other

1. **TS TUI ↔ Python core: subprocess + JSON-lines.**
   `tui/src/lib/agent.ts` spawns
   `python3 main.py --json-lines --no-tui --provider … --workdir …`
   per turn (first turn `--session-id <new>`, later turns
   `--resume <id>`). Events on stdout, one JSON object per line:
   `token`, `tool`, `final`, `session`. Full contract in
   `tui/PROTOCOL.md`. Keys are never passed on the command line;
   the core reads them from env vars only.

2. **Browser preview: HTTP localhost, 127.0.0.1 only.**
   The Python browser thread serves `/state.json` + `/shot.png`
   today. The Go server (`go/cmd/shadowcode-preview`) serves the
   *same* shapes, plus `/search`, `/takeover`, `/handback`, and
   the `web/` frontend — so the TS TUI and the preview page work
   with either server. The browser owner (Python/Playwright) posts
   screenshots/state; the preview page polls every second.
   User takeover: the preview posts to `/control` (Python) or
   `/takeover` (Go); the agent pauses while USER DRIVING, watches
   the watch log, and resumes from the *current* page on handback
   — no reload, no reset.

3. **Native scanner: CLI stdout + C ABI (cycle 6 wiring).**
   Python uses the CLI, not ctypes, by design: the C library's
   printf would pollute the JSON-lines TUI protocol in-process.
   `shadowcode_pkg/native_scanner.py` routes plain-substring
   search/count/fuzzy through the CLI with a Python fallback.
   - CLI: `native/shadowcode-native search <dir> <query> [cap]`
     prints `path:line: text` lines, the same shape as the Python
     search tool, so any caller can parse it.
   - Library: `libshadowcode_native.so` exposes
     `sc_count_lines`, `sc_fuzzy_score`, `sc_search_dir` (see
     `native/include/shadowcode_native.h`). Python uses ctypes,
     Go can use cgo, TS can spawn the CLI.

4. **Search: three implementations, one contract.**
   Python `Tools.search_files`, Go `internal/search.Search`, and
   C++ `sc_search_dir` all skip `.git`/`node_modules`/`__pycache__`
   (Go/C++ also skip `dist`), cap at 100 hits, and return
   path/line/text. They are interchangeable for the same query;
   the Go/C++ versions exist for speed on large trees.

## Build / test (top level)

```bash
make build-all   # tui (tsc) + native (make); Go skipped gracefully if absent
make build-tui   # cd tui && npm run build
make build-go    # cd go && go build -o shadowcode-preview ./cmd/shadowcode-preview
make build-native # cd native && make
make test-all    # Python (19 tests) + TS vitest (4 tests) + native (sh script)
make clean
```

## Safeguards (all languages)

- No sign-in, no password/payment fields, no CAPTCHA solving,
  no bypass of a site block or login wall — in Python, Go, and
  TS alike. A blocked/hidden/disabled element is *reported*,
  never forced.
- Preview servers bind to 127.0.0.1 only.
- File tools are confined to the workdir by default; the Go
  search service is confined to its `--workdir` flag.
- No API keys in code, logs, or command lines (env vars only).
- No external accounts touched; no Claude Code source copied.

## Cycle 7 additions
- New core flags are the TS TUI's interface to sessions, MCP,
  permissions, and shell: `--list-sessions`, `--search-files`,
  `--compact-session`, `--session-info`, `--mcp-servers`,
  `--mcp-tools`, `--permissions`, `--run-shell` (see SPEC.md).
- Preview health is a TS TUI display concern only: it polls the
  existing `/health` + `/state.json` shapes, it does not change
  the Python or Go preview servers.
- Benchmark: `scripts/benchmark_search.py` compares the pure
  Python walk (SHADOWCODE_NO_NATIVE=1) with the C++ CLI on the
  same generated tree and the same hit cap; see TESTING.md for
  the honest small-tree vs large-tree numbers.

## Cycle 10 additions
- Live browser replay is now verified, not unit-only: agent
  opens example.com, preview takeover, user drives to IANA,
  agent watches while USER DRIVING, handback, agent resumes
  from IANA with no reload. The saved log (4 entries, both
  driver transitions) is in
  `test-workspace/.shadowcode/browser-watch-20261102-004908-30363.json`.
  A gap found in the first live run — handback recorded no
  entry because it changes no URL/title — was fixed by
  `Browser.record_driver_change()` (browser.py, called from
  preview /takeover and /handback), so driver changes are
  first-class watch entries, saved immediately.
- TS TUI replay/health panels are display concerns, not new
  browsers: `tui/src/lib/replay.ts` reads the SAVED workspace
  watch log (never the live /state.json 10-entry tail) and
  formats it with driver transitions; `BrowserWatchPanel`
  renders the full replay on `/browser-watch-replay`,
  `HealthHistoryPanel` renders `/health-history` output.
  Both panels are hideable (`/browser-watch-hide`,
  `/health-history-hide`) and never invent entries.

## Cycle 9 additions
- Browser watch replay is a read concern, not a new browser:
  the browser thread already appends every URL/title change to
  `watch_log`; cycle 9 adds a full-log view (`full_watch()` /
  `full_watch_text()` / `format_watch_log()`, with driver
  transitions) and a per-session persisted copy under
  `<workdir>/.shadowcode/browser-watch-*.json`, written on every
  new entry and on close. `/browser-watch` (REPL, Python TUI,
  TS TUI via `--browser-watch`, agent tool
  `browser_watch_replay`) reads the live log first, the saved
  file second, and never starts a browser just to replay.
- Sessions-view actions are a dispatch concern, not new session
  storage: `session.parse_sessions_view_action()` resolves
  list/search/select/action, and `main.sessions_view_dispatch()`
  maps them to the existing read-only (info/export) or approved
  (resume in memory, export-file) paths. The TS TUI reaches the
  same actions through existing core flags, so no TS code edits
  a session file.
- Health history is a workspace log, not a session or config
  file: `health.append_health_snapshot()` writes one JSON line
  per `/health` / `--health` check to
  `<workdir>/.shadowcode/health-history.jsonl` (last 100 kept,
  no keys), and `/health-history` reads it newest-first. The
  log lives in the workdir the health check ran in, so a
  different workdir has a different history — by design.

## Cycle 8 additions
- Browser integration is a display concern in both TUIs, not a
  new browser: Python `TUIState` (title/health/watch) and TS
  Header/StatusBar both render the live preview state, and
  `/browser` in all three UIs prints one shared panel shape
  (state + takeover/handback hints + watch tail) via
  `shadowcode_pkg/health.py` (Python) and
  `tui/src/lib/goSearch.ts:formatBrowserPanel` (TS).
- Sessions view is read-only by construction:
  `session.sessions_view()` only lists/searches and prints
  action hints; the TS TUI reaches it through the existing
  `--list-sessions` / `--search-sessions` / `--session-info`
  flags, so no TS code edits a session file.
- Health dashboard is a new Python module
  (`shadowcode_pkg/health.py`) with one TS caller: the TS TUI
  `/health` prints `--health` output verbatim plus its own
  Ink/React + Go-binary notes. Go vs Python preview are
  distinguished by /health JSON, never guessed.

## Cycle 11 additions
- Live replay evidence is now two-site: cycle 10 (example.com ->
  IANA) plus cycle 11 (httpbin.org/html -> httpbin.org/headers, and
  a no-navigation takeover/handback on httpbin.org/html). Both
  saved logs live under test-workspace/.shadowcode/ and are the
  replay source of truth for both TUIs; neither TUI invents a log.
- Replay-panel rendering: TS panel header = entry count +
  transition count (lib/replay.ts countTransitions); Python
  /browser-watch-replay = full saved log via browser_watch_text,
  in both the curses TUI and the plain REPL.

## Cycle 12 additions
- Live replay evidence is now three-site: cycle 10 (example.com ->
  IANA, goto), cycle 11 (httpbin.org, goto + no-navigation), cycle 12
  (iana.org -> iana.org/domains, preview screenshot click on the
  internal Domain Names link, NOT a goto). Saved log
  test-workspace/.shadowcode/browser-watch-20261102-012015-36840.json.
- Watch entries now carry `via` (user action that caused the change);
  both TUIs render it and mark click vias `[click-driven]`, and the
  TS panel header adds a click-driven count. Python browser.py keeps
  `via` until the URL changes, so the destination entry — not only
  the intermediate Loading title — is marked.

## Cycle 14 additions
- Live replay evidence is now five-site: cycle 14 adds
  gnu.org -> gnu.org/distros/free-distros.html, where the
  "Try GNU/Linux" link starts below the fold (top 836 in a
  1280x720 viewport). A preview scroll_to
  (`text=Try GNU/Linux`) brings it into view, a preview
  click_text on the same text navigates — NOT a screenshot
  coordinate click, NOT a goto — and handback resumes from
  /distros/free-distros.html with no reload. Saved log
  test-workspace/.shadowcode/browser-watch-20261102-015032-42148.json
  (5 entries: agent homepage, user homepage, user scroll_to
  [scroll], user destination via preview click (Try GNU/Linux)
  [click-driven], agent destination on handback).
- Preview controls for that pair are now in the preview page
  itself: a "Scroll to" box (CSS selector, or `text=…`) and a
  "Click text" box (visible text), both via the same /control
  queue. Python `format_watch_log()` and TS
  `formatReplayEntries()` both mark scroll_to `[scroll]` and
  click_text `[click-driven]`, with no cross-marking
  (unit-tested in both languages in cycle 14).

## Cycle 13 additions
- Live replay evidence is now four-site: cycle 13 adds
  python.org -> python.org/about/gettingstarted/, where the
  "Start with our Beginner's Guide" link starts below the fold
  (top 927 in a 1280x720 viewport). A preview wheel scroll down
  600px brings it to top 327 (in view), a preview screenshot
  click at its centre (181,336) navigates, and handback resumes
  from /about/gettingstarted/ with no reload. Saved log
  test-workspace/.shadowcode/browser-watch-20261102-013724-40129.json
  (6 entries: agent homepage, user homepage, user scroll, user
  Loading + user destination, both click-driven, agent
  destination on handback).
- Scrolls are first-class watch entries: `Browser.record_action_entry(via)`
  in browser.py records the current page for actions that change
  no URL/title (preview wheel/scroll_to, agent browser_scroll),
  so a scroll-then-click replay shows the scroll. Both TUIs
  render scroll vias with a `[scroll]` marker, and the TS panel
  header adds a scroll count; scroll entries are never marked
  click-driven.

## Cycle 15 additions
- Live replay evidence is now six-site: cycle 15 adds
  debian.org -> debian.org/intro/philosophy, where the
  "Our Philosophy" link starts below the fold (top 897 in a
  1280x720 viewport). A preview scroll_to on the CSS selector
  a[href='intro/philosophy'] brings it into view, a preview
  click_selector on the same selector navigates — NOT text,
  NOT a coordinate click, NOT a goto — and handback resumes
  from /intro/philosophy with no reload. Saved log
  test-workspace/.shadowcode/browser-watch-20261102-015518-43696.json
  (5 entries: agent homepage, user homepage, user scroll_to
  [scroll], user destination via preview click (selector)
  [click-driven], agent destination on handback).
- Replay marking is now action-based, not substring-based:
  Python `browser.via_kind()` and TS `replay.viaKind()` read
  the action word from the via string, so a CSS selector that
  itself contains 'scroll' or 'click' cannot cross-mark an
  entry. Preview controls for that pair are now in the preview
  page itself: a "Scroll to" box (CSS selector, or `text=…`)
  and a "Click selector" box (CSS selector), both via the same
  /control queue.

## Cycle 16 additions
- Live replay evidence is now seven-site: cycle 16 adds
  rust-lang.org -> rust-lang.org/what/wasm/, where the pair
  uses TWO DIFFERENT selectors — preview scroll_to
  a[href='/what/cli'] (top 1500, below the fold) then preview
  click_selector a[href='/what/wasm'] (a different element in
  the same below-fold row) — NOT the same selector reused,
  NOT text, NOT a coordinate click, NOT a goto. Handback
  resumes from /what/wasm/ with no reload. Saved log
  test-workspace/.shadowcode/browser-watch-20261102-030735-52913.json
  (5 entries, both driver transitions, 1 [scroll], 1
  [click-driven]). Replay formatting in Python
  (`format_watch_log`) and TS (`formatReplayEntries`) shows
  each selector on its own line only: the scroll line never
  contains /what/wasm and never carries [click-driven]; the
  click line never contains /what/cli and never carries
  [scroll] — pinned by new unit tests in both languages.
  Failed-site notes, honestly recorded: postgresql.org
  governance navigation hung in the sandbox proxy, and
  apache.org's members selector first matched a hidden nav
  item; neither was used as evidence.

- Live replay evidence is now eight-site, and multi-step:
  cycle 17 adds ruby-lang.org (homepage -> Security page ->
  ReDoS advisory article) via scroll -> click -> scroll ->
  click, with the first click in a different section (Security
  column) from the scroll target (News item), saved at
  test-workspace/.shadowcode/browser-watch-20261102-034244-57823.json.
  Both TUIs' replay formatters now number action entries in
  order ([step 1] … [step 4]) and append a steps footer
  (scroll count, click-driven count, transition count), so a
  multi-step sequence reads as a sequence in both TUIs.

- Live replay evidence is now nine-site, and three-page: cycle 18 adds ziglang.org (home -> ZSF page -> 2025 Financial Report article -> 300k Donation article) via scroll -> click -> scroll -> click -> scroll -> click, saved at test-workspace/.shadowcode/browser-watch-20261102-040834-61868.json. Both TUIs' replay formatters number the action entries [step 1] … [step 6] and append a steps footer (3 scroll, 3 click-driven, 2 transitions, 6 action steps), with no cross-marking, verified identically on the real saved log in both languages.

- Live replay evidence is now ten-site, and four-page: cycle 19 adds php.net (home -> 2026 news archive -> PHP 8 ChangeLog -> sites guide -> contact page) via scroll -> click x4, saved at test-workspace/.shadowcode/browser-watch-20261102-051406-70249.json. Both TUIs' replay formatters number the action entries [step 1] … [step 8] and append a steps footer (4 scroll, 4 click-driven, 2 transitions, 8 action steps), with no cross-marking, verified identically on the real saved log in both languages.

- Live replay evidence is now eleven-site, and five-page: cycle 20 adds perl.org (home -> contribute -> siteinfo -> whitepapers -> app -> style-guide) via scroll -> click x5, saved at test-workspace/.shadowcode/browser-watch-20261102-062215-79224.json. Both TUIs' replay formatters number the action entries [step 1] … [step 10] and append a steps footer (5 scroll, 5 click-driven, 2 transitions, 10 action steps), with no cross-marking, verified identically on the real saved log in both languages.

- Live replay evidence is now twelve-site, and six-page: cycle 21 adds scala-lang.org (home -> conduct -> license -> security -> governance -> blog -> download) via scroll -> click x6, saved at test-workspace/.shadowcode/browser-watch-20261102-062658-81053.json. Both TUIs' replay formatters number the action entries [step 1] … [step 12] and append a steps footer (6 scroll, 6 click-driven, 2 transitions, 12 action steps), with no cross-marking, verified identically on the real saved log in both languages. The saved log also carries one non-action title-settle entry (conduct.html Loading -> conduct/ final title) that gets no step number.

- Live replay evidence is now thirteen-site, and seven-page: cycle 22 adds elixir-lang.org (home -> install -> learning -> docs -> cases -> blog -> development -> trademarks) via scroll -> click x7, saved at test-workspace/.shadowcode/browser-watch-20261102-063541-83479.json. Both TUIs' replay formatters number the action entries [step 1] … [step 14] and append a steps footer (7 scroll, 7 click-driven, 2 transitions, 14 action steps), with no cross-marking, verified identically on the real saved log in both languages.

- Live replay evidence is now fourteen-site, and eight-page: cycle 23 adds lua.org (home -> start -> docs -> faq -> versions -> license -> authors -> thanks -> donations) via scroll -> click x8, saved at test-workspace/.shadowcode/browser-watch-20261102-063954-85151.json. Both TUIs' replay formatters number the action entries [step 1] … [step 16] and append a steps footer (8 scroll, 8 click-driven, 2 transitions, 16 action steps), with no cross-marking, verified identically on the real saved log in both languages.

- Live replay evidence is now fifteen-site, and nine-page: cycle 24 adds ocaml.org (home -> docs -> platform [via /tools] -> packages -> community -> changelog -> events -> jobs -> security -> governance) via scroll -> click x9, saved at test-workspace/.shadowcode/browser-watch-20261102-065220-88511.json. Both TUIs' replay formatters number the action entries [step 1] … [step 18] and append a steps footer (9 scroll, 9 click-driven, 2 transitions, 18 action steps), with no cross-marking, verified identically on the real saved log in both languages.

## Kilo provider (0.24.0)
- Python core provider `kilo` (OpenAI-compatible Kilo gateway,
  `https://api.kilo.ai/api/openrouter`, default `kilo-auto/free`).
  No Authorization header without a key; `KILO_API_KEY` optional
  for paid models only. Generous `max_tokens=4096`; reasoning-only
  replies raise rather than being claimed as success; an empty
  stream falls back to a non-streaming call in `run_agent`.
- Limit: 200 requests/hour per IP. No VPN / IP rotation (declined
  as limit evasion); legitimate fallback is backoff/wait or a
  different legitimately accessible free provider/model.
