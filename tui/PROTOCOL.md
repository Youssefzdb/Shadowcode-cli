# PROTOCOL.md — TS TUI ↔ Python core (JSON-lines)

## Why a subprocess, not a rewrite

The Python core already owns providers, tools, permissions,
sessions, MCP, and browser orchestration. Rewriting it in TS
would duplicate that logic and drift. So the TUI spawns the core
per user turn and renders its events. History lives in the
Python session file, not in the TUI process.

## Invocation

First turn (no session yet):

```
python3 main.py --json-lines --no-tui --provider mock \
  --workdir <dir> --permission-mode auto \
  --session-id <12-hex-id> "<prompt>"
```

Later turns (same session, history preserved):

```
python3 main.py --json-lines --no-tui --provider mock \
  --workdir <dir> --permission-mode auto \
  --resume <id> "<prompt>"
```

Notes:
- `--session-id` must be a *new* id; passing an existing id makes
  the core bump it (`<id>-2`), which would break the TUI's session
  tracking. The TUI therefore generates a fresh id for turn 1 and
  uses `--resume` afterwards. The core also emits a `session` event.
- `--permission-mode auto` in subprocess mode: non-destructive
  tools run, destructive tools are denied unless
  `--allow-destructive --yes` are also passed. There is no
  interactive stdin permission prompt in this mode, by design.
- Keys are never passed on the command line; the core reads them
  from environment variables only (see the main README).

## Events (one JSON object per line, stdout)

| type | fields | meaning |
|---|---|---|
| `token` | `text` | streamed model token; append to the current assistant line |
| `tool` | `name`, `result` | a tool call finished; render in Transcript + ToolPanel |
| `final` | `text` | final reply; the TUI does NOT duplicate it if it equals the streamed assistant text |
| `session` | `id` | session id for the next turn (`--resume <id>`) |
| (stderr) | — | surfaced as a system/error line, never hidden |

Non-JSON stdout lines are surfaced as error lines, never
silently dropped (see `parseEventLine` in `src/lib/protocol.ts`).

## What the TUI does NOT do

- It does not call providers directly, does not hold API keys,
  does not write session files, and does not drive the browser
  directly. Browser control stays in the Python core / Go preview
  server; the TUI only displays the preview URL.
- It does not fake permission prompts. `PermissionPrompt` exists
  as a component for a future interactive mode, not as a prompt
  that approves anything in subprocess mode.
