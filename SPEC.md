# Shadowcode — behaviour specification (cycle 1)

Shadowcode is an original CLI AI agent, inspired at concept level by
Claude Code (see REVERSE_ENGINEERING.md). No Claude Code code,
prompts, or schemas are used.

## 1. Entry points
- `shadowcode` — interactive REPL when run with no prompt.
- `shadowcode "do X"` — one-shot: run one prompt, print answer, exit.
- `shadowcode -p "do X"` / `--print` — same as one-shot, pipe-friendly.
- `shadowcode --version`, `shadowcode --help`, `shadowcode --doctor`
  (health check: Python version, config files found, provider
  configured, browser availability).
- `shadowcode --continue` — resume the most recent session.
- `shadowcode --resume <id>` — resume a saved session by ID.
- `shadowcode --session-id <id>` — start with a given session ID.

## 2. TUI and REPL (cycle 3: TUI is the default on a TTY)
- TUI: stdlib-curses only (`shadowcode_pkg/tui.py`, no rich /
  textual install). Header (provider/model/session/permission),
  transcript pane (user / streaming assistant / `[tool name]`
  lines), status line (hints + browser driver/URL), input row
  with history and Esc-to-clear. Permission prompts are inline
  (`y`/`n`) in the TUI. Agent callbacks: `on_token` streams
  into the transcript, `on_tool` appends a tool event line.
  `TUIState` is pure and unit-tested without a terminal.
- Flags: `--tui` forces the TUI, `--no-tui` forces the plain
  REPL. On a non-TTY, or if curses cannot start, Shadowcode
  falls back to the plain REPL and continues — the TUI never
  blocks the CLI.
- Plain REPL below stays as the fallback.

## 2b. REPL
Prompt: `shadowcode> `. Slash commands (session commands, never
sent to the model as a task):
- `/help` — list REPL commands and flags
- `/model [name]` — show/switch model
- `/provider [name]` — show/switch provider
- `/tools` — list tools
- `/sessions` — list saved sessions
- `/resume <id>` — load a session into the current REPL
- `/clear` — clear conversation history (keeps session ID)
- `/compact` — extractive context management (cycle 2): keep system
  messages + the last 10 messages, replace the dropped middle with
  a summary line (count + earlier user topics, truncated). No model
  call, no invented summary.
- `/permissions` — show permission mode and allow/deny lists
- `/browser` — show browser status and live-preview URL
- `/doctor` — health check
- `/exit` / Ctrl-D — save session and exit
- `!command` — run a literal shell command in the working directory
  (same guard as `run_shell`), output shown directly.
- Anything else is a user prompt to the agent.

## 3. Agent loop
User prompt -> provider -> model reply -> parse tool calls ->
run tools (permission-checked) -> feed results back as a new
turn -> repeat, max 10 steps -> final answer printed.
Streaming (cycle 2): if a provider supports `chat_stream`,
tokens are printed as they arrive (`--no-stream` disables this);
streaming is an optimisation only — on any streaming error the
loop falls back to the full reply. The streamed final reply is
not printed a second time.

Tool-call protocol (Shadowcode's own, plain text, easy to debug):
a model reply may contain lines of the form
`TOOL: <tool_name> <json-or-plain-args>`
e.g. `TOOL: read_file {"path": "README.md"}`.
Native JSON tool calls are also accepted (cycle 2): a reply
containing `{"tool_calls": [{"name": ..., "arguments": {...}}]}`
or `{"tool": ..., "args": {...}}`, and Ollama/Gemini native
function-call structures, are converted to `TOOL:` lines before
parsing (see `providers.normalise_reply` / `_tool_calls_to_lines`).
The mock provider emits these lines deterministically from
keywords in the prompt (read/list/write/echo/open). Real providers
are instructed with the same protocol in the system prompt.
Tool results are fed back as:
`Tool <name> returned: <output>` and the loop continues.
No tool output is ever claimed as model output.

## 4. Tools
- `read_file(path)` — read a file, confined to working directory
  (plus `--add-dir` dirs) unless `--allow-outside`.
- `write_file(path, content)` — create/overwrite, parent dirs created.
- `edit_file(path, old, new, dry_run?)` — replace exact text once;
  fails cleanly if `old` is not found or appears more than once.
  With `dry_run=true` it shows the would-be result without writing.
- `diff_edit(path, old, new)` (cycle 2) — unified diff for an edit,
  never writes. CLI `--dry-run` forces all writes/edits into
  dry-run mode (write_file reports would-write, edit_file shows
  the preview).
- `mcp_call(server, tool, arguments)` (cycle 2) — call a tool on a
  configured local stdio MCP server; see §9.
- `list_dir(path=".")` — list a directory.
- `search_files(pattern)` — regex search under working directory,
  skips binary files, reports file:line matches (capped).
- `run_shell(command)` — run in working directory, timeout 30s,
  stdout+stderr capped. Destructive patterns refused (see §6).
- Browser tools (opt-in, Playwright, Firefox default in this
  sandbox because Chromium proxy CONNECT fails here):
  `browser_open(url)`, `browser_read()`, `browser_click(text)`,
  `browser_fill(field, value)`, `browser_screenshot(name)`,
  `browser_navigate(back|forward)`, `browser_close()`,
  `browser_watch()` (cycle 3) — current URL/title + watch log,
  no reload.
  Cycle 4 additions: `browser_click_selector(selector)` —
  CSS locator, or `text=…` / `css:…` prefixes, falling back to
  visible text; `browser_scroll(direction|amount|selector)` —
  down/up/top/bottom or scroll an element into view;
  `browser_fill_selector(selector, value)` — fill by CSS
  selector, refusing password/payment targets by selector
  string AND by the element's type/name/id/aria-label;
  `browser_fill_form(fields, submit?)` — fill several fields
  (one forbidden field refuses the whole form); submit only
  for non-sign-in forms (refused if the page has a password
  input or the submit button says sign/log in).
  `browser_fill` refuses password/payment/card fields.

## 5. Providers (plugin interface)
One interface: `chat(messages, model) -> text`.
- `mock` — deterministic stub, no key, no network. For tests.
- `ollama` — local, `http://localhost:11434/api/chat`, no key.
- `groq` — OpenAI-compatible chat completions, `GROQ_API_KEY`.
- `gemini` — Google Generative Language API, `GEMINI_API_KEY`.
- `openrouter` — OpenAI-compatible, `OPENROUTER_API_KEY`,
  free `:free` models supported by naming them in `--model`.
Keys: environment variables only. Never hard-coded, never written
to a file, never printed (CLI prints only `key_set=yes/no`).
Adding a provider = one small class + one registration line.

## 6. Permissions
Modes: `manual` (ask before every write/shell/browser_fill),
`auto` (allow non-destructive, ask destructive), `plan`
(read-only: refuse write/edit/shell/browser_fill, allow read/list/
search/browser_open/browser_read).
Allow/deny: `--allowed-tools`, `--disallowed-tools`,
config `permissions.allow` / `permissions.deny`; deny always wins.
Destructive shell patterns (refused without `--allow-destructive`,
and even then requiring `--yes` in one-shot / explicit `y` in REPL):
`rm -rf`, `mkfs`, `dd ... of=/dev/`, `shutdown`, `reboot`,
`curl|wget ... | sh`, `chmod -R 777 /`, `> /dev/`, fork bombs.
Files are confined to the working directory by default.

## 7. Sessions and config
Sessions: `~/.config/shadowcode/sessions/<id>.json`
`{id, provider, model, messages: [{role, content}], updated_at}`.
Never store API keys in session files.
Cycle 4: session export/search and collision handling.
`--export-session <id> [--export-format md|json]
[--export-output <file>]` prints (or writes) a session;
`--search-sessions <query>` searches id/provider/model/message
text and prints a snippet per hit; REPL/TUI commands
`/sessions [query]`, `/search-sessions <query>`, `/export <id>
[md|json]`. A fresh start with an existing `--session-id`
never overwrites it: it bumps to `<id>-2`, `<id>-3`, … and
prints the new id. A prefix `--resume`/load that matches
several sessions raises "ambiguous" instead of picking one.
Config search order: `--config` > `$SHADOWCODE_CONFIG` >
`./shadowcode.json` > `.shadowcode/settings.json` >
`~/.config/shadowcode/config.json`.
Env overrides: `SHADOWCODE_PROVIDER`, `SHADOWCODE_MODEL`,
`SHADOWCODE_BASE_URL`, `SHADOWCODE_WORKDIR`.
Project instructions: `SHADOWCODE.md` in the working directory,
if present, is prepended to the system prompt (own file, not
Claude's CLAUDE.md content).

## 8. Browser + localhost live preview
Ported as an *idea* from `~/workspace/cli-ai-agent/` (README.md,
NEXT.md), re-implemented from scratch here:
- When the browser starts, a localhost-only HTTP server starts
  (default port 8765, next free port above it, or
  `SHADOWCODE_PREVIEW_PORT`).
- Preview page polls `/state.json` every second: current URL,
  title, driver (agent/user), latest screenshot.
- `/shot.png` serves the latest viewport screenshot.
- Cycle 2 takeover (instant): a dedicated browser thread owns the
  Playwright page; agent and preview threads send commands into
  queues, the browser thread drains user controls first and pumps
  a screenshot every second while idle. Preview clicks therefore
  act promptly, not only on the next agent browser call. The
  preview also has a "Send keys" box (`POST /control
  {action: "type", text: ...}`). While user is driving, clicks on
  the screenshot image are sent to `POST /control {x, y}`
  (coordinates scaled to the viewport) and performed in the browser;
  the agent's own browser actions are paused while user is driving,
  and the page shows "USER DRIVING" vs "AGENT DRIVING". Hand-back
  returns control to the agent. No sign-in, no password/payment
  entry, no CAPTCHA solving, no bypass of a block/login wall — a
  blocked page is reported as such.
- Cycle 3, Muse-AI parity — watch + handback:
  * Watch: the browser thread's screenshot pump records every
    URL/title change (agent or user) in a watch log
    (`state()["watch"]`, `/state.json` `watch`, preview watch
    list). The agent reads it with `browser_watch` while the
    user drives; agent actions stay paused, reads/watch work.
  * Preview controls: Take control / Hand back, URL bar (Go),
    Back/Forward, Send keys, screenshot click. A failed user
    control is recorded as `last_control_error` in
    `/state.json`, never swallowed silently.
  * Handback: flips driver back to `agent` ONLY. No reload, no
    reset, no restart. The agent resumes with
    `browser_watch` / `browser_read` from the exact current
    page (current URL, title, content) and continues its task.
- Server binds to `127.0.0.1` only and stops on
  `browser_close()` / CLI exit.

## 9. MCP / plugins (cycle 2: minimal, local stdio only)
As in Claude Code's public `mcp` command concept, external servers
add tools — but Shadowcode's client is deliberately narrower:
- Config only: `mcp.servers` in shadowcode.json /
  .shadowcode/settings.json, e.g.
  `{"dummy": {"command": ["python3", "mcp_dummy_server.py"]}}`.
- Local only: command must be a file inside the working directory,
  or a plain interpreter running a script inside it. Remote/HTTP
  servers are refused by default. No MCP code was copied.
- Approval-gated: `mcp_call` is a WRITE tool (manual asks, plan
  refuses), and only tools advertised via `tools/list` are callable.
- Protocol: JSON-RPC 2.0 over stdio (initialize, tools/list,
  tools/call). REPL: `/mcp [server]` lists a server's tools.

## 10. What is out of scope in cycle 1
Background daemons, git worktrees, cloud sessions, IDE
integration, Chrome integration, hooks, skills, streaming
(except where a provider returns it — cycle 1 waits for the
full reply), token counting, and any sign-in/payment flow.


## Cycle 6 additions
- Tools: `count_lines`, `fuzzy_score` (READ). `search_files`: native CLI
  fast path for plain substrings only, Python regex fallback otherwise.
- `/go-search <query>`: Go /search (localhost, 127.0.0.1 only) first,
  explicit unavailable note + Python fallback if no Go server is running.
- TS TUI slash parity: /sessions, /search-sessions, /export, /export-file,
  /resume, /permissions, /browser, /mcp, /doctor, /go-search (see
  tui/src/lib/coreCli.ts and tui/src/lib/goSearch.ts).

## Cycle 7 additions
- Core exit-and-print flags (no session written):
  `--list-sessions`, `--search-files`, `--compact-session`,
  `--session-info`, `--mcp-servers`, `--mcp-tools`,
  `--permissions`, `--run-shell`. The TS TUI calls these via
  `tui/src/lib/coreCli.ts`; it does not reimplement them.
- Preview health: TS TUI polls `http://127.0.0.1:<port>/health`
  and `/state.json` every 3s and displays
  healthy/unavailable + port + driver in the StatusBar and
  `/browser`. Unavailable is reported, never faked.
- Help consistency: `/search-sessions` date filters
  (`--from/--to`) are parsed by one shared `parse_search_args()`
  in main.py, used by the REPL and the curses TUI, matching the
  TS TUI and the CLI flag; search results print in the same
  formatted shape in all three UIs.

## Cycle 10 additions
- Live browser replay (verified, not unit-only): agent opens
  example.com, preview takeover, user drives to IANA, agent
  watches while USER DRIVING, handback, agent resumes from
  IANA with no reload. Saved log (4 entries, both driver
  transitions) is in
  `test-workspace/.shadowcode/browser-watch-20261102-004908-30363.json`.
- Driver-change entries: `Browser.record_driver_change()` in
  `browser.py`, called from preview /takeover and /handback,
  appends a watch entry (same page, new driver) and saves it
  immediately, so a handback that changes no URL/title still
  appears in the replay as user -> agent. No-op with no page
  yet or an unchanged driver.
- TS TUI panels: `/browser-watch-replay` (full saved replay
  panel, `BrowserWatchPanel`, via `tui/src/lib/replay.ts`:
  `readSavedWatchLog()` + `formatReplayEntries()`) and
  `/browser-watch-hide`; `/health-history [n]` also shows a
  `HealthHistoryPanel`, `/health-history-hide` hides it.
  The replay panel source is the SAVED log, never the live
  /state.json 10-entry tail.

## Cycle 9 additions
- Browser watch replay: `browser_watch_replay` tool (READ, no
  reload, no page body) and `/browser-watch` command in REPL,
  Python TUI, and TS TUI (CLI `--browser-watch`, read-only):
  the full watch log in order, with driver transitions marked
  (`agent -> user`, `user -> agent`). The log is persisted per
  browser session to `<workdir>/.shadowcode/browser-watch-<timestamp>-<pid>.json`
  on every new entry and on close; a replay after the browser
  closed reads that saved file. `/state.json` now also carries
  `watch_count` and `watch_file`; `/browser` still shows only
  the tail, and points to `/browser-watch` for the full log.
- Sessions-view actions: `/sessions-view <id> info | export
  [md|json] | export-file [md|json] [path] | resume`, in all
  three UIs. `session.parse_sessions_view_action()` resolves
  list/search/select/action; `sessions_view_selected()` is
  read-only detail. Info/export never edit a session file;
  resume loads in memory (approved path); export-file is the
  approved export path (never overwrites).
- Health history: `health.append_health_snapshot()` /
  `read_health_history()` / `format_health_history()` in
  `health.py`; every `/health` / `--health` appends one
  snapshot (no keys) to `<workdir>/.shadowcode/health-history.jsonl`
  (last 100 kept); `/health-history [n]` (CLI
  `--health-history [n]`, TS via coreCli) shows the last n,
  newest first, default 10, clamped 1..50. A missing log is
  "no snapshots yet", never a fabricated snapshot.

## Cycle 8 additions
- Browser integration in both TUIs: Python curses header/status
  and TS Header/StatusBar show browser URL, title, driver, and
  preview health (healthy/unavailable/unknown). `/browser` in
  the REPL, Python TUI, and TS TUI prints the same panel:
  fresh state, preview URL, takeover/handback hints, and the
  watch-log tail (last 5). A not-started browser is reported
  as "not started", never as a live page. Python
  `browser_panel_text()` in main.py does not start a browser
  that is not already running; it falls back to a localhost
  preview probe (see `shadowcode_pkg/health.py`).
- Sessions view: `/sessions-view [query]` in the REPL, Python
  TUI, and TS TUI (list/search + info + action hints), and
  `/session-info <id>` in all three UIs. `session.sessions_view()`
  is read-only: it never creates, modifies, or deletes a
  session file. Resume loads in memory; compact (current
  session only, or `--compact-session`) and export are the only
  approved mutating paths, as before.
- Health dashboard: `--health` flag and `/health` command in
  all three UIs, backed by `shadowcode_pkg/health.py`:
  Python core, TS TUI (package.json version, dist/ built,
  node), Go preview (binary, server via /health), preview
  server (via /state.json), native scanner, Playwright.
  A Go server is identified only by JSON `{"ok": true}` on
  /health; a Python preview answers /state.json but not
  /health, so the two are never conflated, and an absent
  server is "unavailable", never "healthy". No health check
  creates a session file or prints a key.

## Cycle 11 additions
- Browser replay must hold on a second site, not only the
  example.com -> IANA pair: a user-driven move on another public
  site appears in the saved log as a user entry, with both driver
  transitions, and handback resumes from that page (no reload).
- A takeover with NO navigation must still produce both driver
  transitions in the saved log (takeover entry + handback entry on
  the same page); a replay that only logged URL changes would show
  none, so driver-change entries are part of the spec, not a
  display trick.
- Replay panels: TS BrowserWatchPanel shows entry + transition
  counts in its header; Python TUI/REPL offer /browser-watch-replay
  for the full saved replay on demand.

## Cycle 12 additions
- Browser replay must hold on a third site with a CLICK, not a
  goto: a user-driven preview screenshot click on an internal
  link appears in the saved log as a user entry whose destination
  is marked click-driven, with both driver transitions, and
  handback resumes from the clicked page (no reload).
- Watch entries carry a `via` field for user actions (preview
  click/goto/back/forward/type/key). Replay renderers in both
  TUIs must show `via` and mark click vias `[click-driven]`;
  a `via` is kept until the URL itself changes, because a click
  first changes the title to "Loading …" on the old URL.
- Preview controls include click_text/click_selector actions
  (real element clicks in the browser thread, not gotos), in
  addition to the existing screenshot-coordinate click.

## Cycle 13 additions
- Browser replay must hold on a fourth site with a click-driven
  navigation that requires a scroll into view first: the link
  starts below the fold, a preview scroll brings it into view,
  and only then a preview click navigates. The saved log must
  show the scroll, the click-driven navigation, and both driver
  transitions, and handback must resume from the clicked page.
- Scrolls are first-class watch entries, not invisible: a scroll
  changes no URL/title, so `_snap()` alone would log nothing.
  `Browser.record_action_entry(via)` records the current page
  with a via (`preview scroll down`, `agent scroll to <sel>`,
  …), capped and persisted like any other entry. Preview
  controls include scroll down/up (wheel) and scroll_to.
- Replay renderers in both TUIs must show `via` and mark scroll
  vias `[scroll]`, alongside the existing `[click-driven]`
  marker; the TS BrowserWatchPanel header adds a scroll count.
  A scroll entry must never be marked click-driven, and vice
  versa.

## Cycle 17 additions
- Multi-step browser replay (verified, not unit-only): agent
  opens ruby-lang.org, preview takeover, user scrolls to a News
  item, clicks a different-section Security link, scrolls to an
  advisory on the Security page, clicks a different advisory,
  handback, agent resumes from that advisory article with no
  reload. Saved log (7 entries, 2 scroll, 2 click-driven, 2
  transitions) is in
  `test-workspace/.shadowcode/browser-watch-20261102-034244-57823.json`.
- Replay step numbering: Python `format_watch_log()` and TS
  `formatReplayEntries()` number action entries in order
  (`[step N]` after the [scroll] / [click-driven] marker) and
  append a steps footer (`steps: N scroll, M click-driven, T
  driver transitions (K action steps)`) when there is at least
  one action step. Non-action entries get no step; a plain log
  gets no footer. Marking remains by action word, so no
  cross-marking.

## Cycle 18 additions
- Three-page browser chain (verified live, not unit-only): agent opens ziglang.org, preview takeover, user scrolls + clicks across three source pages (home -> ZSF page -> 2025 Financial Report article -> 300k Donation article), handback, agent resumes from the final article with no reload. Saved log (9 entries, 3 scroll, 3 click-driven, 2 transitions, 6 action steps) is in `test-workspace/.shadowcode/browser-watch-20261102-040834-61868.json`.
- Replay step numbering continues 1..6 across the chain in both Python `format_watch_log()` and TS `formatReplayEntries()`, with the steps footer and no cross-marking, pinned by new tests in both languages. No formatter change was needed in cycle 18; the polish is the pinning tests and the real-log verification in both languages.

## Cycle 19 additions
- Four-page browser chain (verified live, not unit-only): agent opens php.net, preview takeover, user scrolls + clicks across four source pages (home -> 2026 news archive -> PHP 8 ChangeLog -> sites guide -> contact page), handback, agent resumes from the Contact page with no reload. Saved log (11 entries, 4 scroll, 4 click-driven, 2 transitions, 8 action steps) is in `test-workspace/.shadowcode/browser-watch-20261102-051406-70249.json`.
- Replay step numbering continues 1..8 across the chain in both Python `format_watch_log()` and TS `formatReplayEntries()`, with the steps footer and no cross-marking, pinned by new tests in both languages and verified identically on the real saved log in both languages. No formatter change was needed in cycle 19; the polish is the pinning tests and the real-log verification in both languages.

## Cycle 20 additions
- Five-page browser chain (verified live, not unit-only): agent opens perl.org, preview takeover, user scrolls + clicks across five source pages (home -> contribute -> siteinfo -> whitepapers -> app -> style-guide), handback, agent resumes from the style-guide page with no reload. Saved log (13 entries, 5 scroll, 5 click-driven, 2 transitions, 10 action steps) is in `test-workspace/.shadowcode/browser-watch-20261102-062215-79224.json`.
- Replay step numbering continues 1..10 across the chain in both Python `format_watch_log()` and TS `formatReplayEntries()`, with the steps footer and no cross-marking, pinned by new tests in both languages and verified identically on the real saved log in both languages. No formatter change was needed in cycle 20; the polish is the pinning tests and the real-log verification in both languages.

## Cycle 21 additions
- Six-page browser chain (verified live, not unit-only): agent opens scala-lang.org, preview takeover, user scrolls + clicks across six source pages (home -> conduct -> license -> security -> governance -> blog -> download), handback, agent resumes from the download page with no reload. Saved log (16 entries, 6 scroll, 6 click-driven, 2 transitions, 12 action steps, plus one non-action title-settle entry for the conduct.html -> conduct/ canonicalisation) is in `test-workspace/.shadowcode/browser-watch-20261102-062658-81053.json`.
- Replay step numbering continues 1..12 across the chain in both Python `format_watch_log()` and TS `formatReplayEntries()`, with the steps footer and no cross-marking, pinned by new tests in both languages and verified identically on the real saved log in both languages. No formatter change was needed in cycle 21; the polish is the pinning tests (including the assertion that the title-settle entry gets no step number) and the real-log verification in both languages.

## Cycle 22 additions
- Seven-page browser chain (verified live, not unit-only): agent opens elixir-lang.org, preview takeover, user scrolls + clicks across seven source pages (home -> install -> learning -> docs -> cases -> blog -> development -> trademarks), handback, agent resumes from the trademarks page with no reload. Saved log (17 entries, 7 scroll, 7 click-driven, 2 transitions, 14 action steps) is in `test-workspace/.shadowcode/browser-watch-20261102-063541-83479.json`.
- Replay step numbering continues 1..14 across the chain in both Python `format_watch_log()` and TS `formatReplayEntries()`, with the steps footer and no cross-marking, pinned by new tests in both languages and verified identically on the real saved log in both languages. No formatter change was needed in cycle 22; the polish is the pinning tests and the real-log verification in both languages.

## Cycle 23 additions
- Eight-page browser chain (verified live, not unit-only): agent opens lua.org, preview takeover, user scrolls + clicks across eight source pages (home -> start -> docs -> faq -> versions -> license -> authors -> thanks -> donations), handback, agent resumes from the donations page with no reload. Saved log (19 entries, 8 scroll, 8 click-driven, 2 transitions, 16 action steps) is in `test-workspace/.shadowcode/browser-watch-20261102-063954-85151.json`.
- Replay step numbering continues 1..16 across the chain in both Python `format_watch_log()` and TS `formatReplayEntries()`, with the steps footer and no cross-marking, pinned by new tests in both languages and verified identically on the real saved log in both languages. No formatter change was needed in cycle 23; the polish is the pinning tests and the real-log verification in both languages.

## Cycle 24 additions
- Nine-page browser chain (verified live, not unit-only): agent opens ocaml.org, preview takeover, user scrolls + clicks across nine source pages (home -> docs -> platform [via /tools] -> packages -> community -> changelog -> events -> jobs -> security -> governance), handback, agent resumes from the governance page with no reload. Saved log (21 entries, 9 scroll, 9 click-driven, 2 transitions, 18 action steps) is in `test-workspace/.shadowcode/browser-watch-20261102-065220-88511.json`.
- Replay step numbering continues 1..18 across the chain in both Python `format_watch_log()` and TS `formatReplayEntries()`, with the steps footer and no cross-marking, pinned by new tests in both languages and verified identically on the real saved log in both languages. No formatter change was needed in cycle 24; the polish is the pinning tests and the real-log verification in both languages.

## Kilo provider additions
- Provider `kilo`: Kilo gateway, OpenAI-compatible, base
  `https://api.kilo.ai/api/openrouter`, default model
  `kilo-auto/free`, `--model` selects a `:free` model.
  `OpenAICompatProvider` supports `require_key=False` and an
  optional `max_tokens` (Kilo: 4096, to avoid reasoning-only
  empty replies). No Authorization header is sent when no key
  is set; `KILO_API_KEY` is optional, for paid models only.
- A reply with no content but reasoning (`reasoning` or
  `reasoning_content`) raises instead of being claimed as a
  success. An empty streamed reply in `run_agent` falls back
  to a non-streaming call instead of returning blank.
- Limits: 200 requests/hour per IP (documented). No VPN and
  no IP rotation: on a limit, back off/wait or fall back to a
  different legitimately accessible free provider/model
  (another Kilo `:free` model, or Groq/Gemini/OpenRouter free
  tier). Auto Free prompts may be logged upstream; not for
  sensitive/production data.

## Cycle 25 additions
- Ten-page browser chain (verified live, not unit-only): agent opens julialang.org, preview takeover, user scrolls + clicks across ten source pages (home -> downloads -> learning -> blog -> community -> contribute -> jsoc -> community/standards -> community/stewards -> governance -> diversity), handback, agent resumes from the diversity page with no reload. Saved log (23 entries, 10 scroll, 10 click-driven, 2 transitions, 20 action steps) is in `test-workspace/.shadowcode/browser-watch-20261102-070641-91844.json`.
- Replay step numbering continues 1..20 across the chain in both Python `format_watch_log()` and TS `formatReplayEntries()`, with the steps footer and no cross-marking, pinned by new tests in both languages and verified identically on the real saved log in both languages. No formatter change was needed in cycle 25; the polish is the pinning tests and the real-log verification in both languages.
