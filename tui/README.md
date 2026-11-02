# Shadowcode TUI — TypeScript (Ink + React)

Professional terminal UI for Shadowcode. The Python core in
`~/workspace/shadowcode/` remains the agent (providers, tools,
sessions, MCP, browser orchestration); this package is only the
UI, talking to it over the JSON-lines protocol in PROTOCOL.md.

## Run

```bash
cd ~/workspace/shadowcode/tui
npm install          # Ink + React + dev tools (inside this dir only)
npm run build        # tsc -> dist/
./bin/shadowcode-tui --provider mock --workdir ../test-workspace
# or: node dist/cli.js --provider mock --workdir ../test-workspace
```

Non-TTY runs (piped stdin, CI) do **not** crash: `src/cli.tsx`
prints a fallback message and exits 0, pointing at the Python CLI.

## Layout

```
src/cli.tsx                 entry, TTY check, arg parsing
src/App.tsx                 Ink app: state, slash commands, history
src/components/Header.tsx   provider/model/session/permission/browser
src/components/Transcript.tsx  user/assistant/tool/system lines
src/components/ToolPanel.tsx   last 5 tool calls
src/components/StatusBar.tsx   thinking, counts, last tool
src/components/Input.tsx       input row
src/components/PermissionPrompt.tsx  permission UI (see PROTOCOL.md)
src/lib/protocol.ts         JSON-lines parsing + transcript folding
src/lib/agent.ts            subprocess spawn, args, event stream
tests/protocol.test.ts      vitest unit tests
```

## Slash commands (local, in the TUI)

`/help /model [name] /provider [name] /tools /sessions /clear /exit`,
`!cmd` is noted (shell runs through the agent, not faked locally).

## Permission model in subprocess mode

The TUI spawns the Python core per turn with
`--permission-mode auto` by default. Non-destructive tools run;
destructive tools are denied unless the TUI was started with
`--allow-destructive true` (which also passes `--yes` to the core).
No interactive permission prompt is faked: `PermissionPrompt` is
kept for a future interactive (non-subprocess) agent mode.

## Browser preview

When the agent opens the browser, the Python core prints a
localhost preview URL (127.0.0.1 only). The TUI shows it in the
header when a browser tool result mentions `localhost:<port>`.
The preview itself is served by the Python browser thread (and,
in the polyglot layout, by the Go preview server in `../go/`).
