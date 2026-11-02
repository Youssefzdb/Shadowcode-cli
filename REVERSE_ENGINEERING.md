# Shadowcode — clean-room reverse engineering notes on Claude Code

Status: black-box, public surface only. Date observed: 2026-11-02.
Reference install: `~/workspace/claude-code-reference/` (separate directory,
NOT inside `~/workspace/shadowcode/`).

## What was done — and what was NOT done

DONE:
- Installed the official public npm package `@anthropic-ai/claude-code`
  version **2.1.316** with `npm install @anthropic-ai/claude-code` in
  `~/workspace/claude-code-reference/`.
- Ran only public, no-auth commands: `--help`, `--version`,
  `doctor --help`, `mcp --help`. No sign-in, no API key, no credential,
  no paid account, no interactive session, no prompt was sent to any
  model through Claude Code.
- Read its public README (install instructions, homepage link) and
  public web documentation summaries for slash commands, settings
  locations, and permission rules.

NOT DONE (deliberately):
- No source code was copied, decompiled, extracted, or read from the
  installed binary package beyond its public `package.json` metadata
  (name/version/bin) and its public README. The binary itself
  (`bin/claude.exe`, platform native binary) was not decompiled.
- No licence, login, subscription, or paywall was bypassed.
- No Claude Code prompt, system prompt, internal tool schema, or
  conversation transcript was reused. Shadowcode's tool protocol,
  prompts, and code are written from scratch.
- No Anthropic trademark is used as Shadowcode's own name; "Claude
  Code" is mentioned here only to identify the reference product.

## Observed public CLI surface (from `--help`, 313 lines, saved as
`~/workspace/claude-code-reference/claude-help.txt`)

Usage line (verbatim):
```
Usage: claude [options] [command] [prompt]

Claude Code - starts an interactive session by default, use -p/--print for
non-interactive output
```

Version observed: `2.1.316 (Claude Code)`.

### Two modes
- Interactive REPL by default (no arguments).
- One-shot / print mode: `-p, --print` — "Print response and exit
  (useful for pipes)".

### Selected flags observed (verbatim wording, abridged)
- `--add-dir <directories...>` — additional directories to allow tool access to
- `--agent <agent>` / `--agents <json-or-file>` — custom agents
- `--allowedTools, --allowed-tools <tools...>` — e.g. "Bash(git *) Edit"
- `--disallowedTools, --disallowed-tools <tools...>`
- `--append-system-prompt <prompt>` / `--system-prompt <prompt>`
- `--model <model>` — model for the current session
- `--fallback-model <model>`
- `--permission-mode <mode>` — choices observed: "acceptEdits", "auto",
  "bypassPermissions", "manual", "dontAsk", "plan"
- `--dangerously-skip-permissions` / `--allow-dangerously-skip-permissions`
  — bypass all permission checks, "Recommended only for sandboxes"
- `--restricted` — removes code-running tools unless named, confines
  file tools to working directories, refuses bypassPermissions
- `-c, --continue` — continue the most recent conversation
- `-r, --resume [value]` — resume by session ID/name, or picker
- `--session-id <uuid>` — use a specific session ID
- `--no-session-persistence` — disable session persistence
- `--output-format <format>` (with --print), `--input-format <format>`
- `--mcp-config <configs...>` / `--strict-mcp-config`
- `--plugin-dir <path>` / `--plugin-url <url>`
- `--max-budget-usd <amount>`
- `--verbose`, `-d, --debug [filter]`, `--debug-file <path>`
- `--chrome` / `--no-chrome` — Claude in Chrome integration
- `--worktree [name]`, `--tmux` — git worktree sessions
- `-v, --version`, `-h, --help`

### Subcommands observed (from --help, Commands section)
- `agents` — manage background agents
- `attach <id|name>`, `logs <id|name>`, `stop|kill <id>`, `rm <id>`,
  `respawn [id]` — background sessions
- `auth` — manage authentication
- `auto-mode`, `doctor` — health check; doctor help says: "Reads
  settings files in the current directory without a trust prompt"
- `gateway`, `import`, `install`, `purge`, `setup-token`
  (setup-token help notes it requires a Claude subscription — not used)
- `mcp` — configure and manage MCP servers
- `plugin|plugins` — manage plugins
- `update|upgrade`, `ultrareview`

### MCP concept (from `claude mcp --help`, public)
MCP = Model Context Protocol servers that add external tools.
Observed subcommands: `add`, `add-from-claude-desktop`,
`add-json`, `get`, `list`, `login`, `logout`, `remove`,
`reset-project-choices`, `serve`.
Examples observed in help: HTTP transport
(`claude mcp add --transport http sentry https://mcp.sentry.dev/mcp`),
stdio with env vars, and JSON config. Unapproved `.mcp.json`
servers are shown as pending approval and not connected to.

Shadowcode does NOT implement MCP in cycle 1; its provider/tool
system is a simpler plugin interface, and MCP is listed as a
future cycle item. No MCP server code was copied.

### Settings / config locations (public documentation summaries)
- User scope: `~/.claude/settings.json`
- Project scope: `.claude/settings.json` (shareable)
- Local scope: `.claude/settings.local.json` (personal, gitignored)
- Managed policy settings (organisation) override others; permission
  allow/deny rules merge across scopes.
- Project instructions file: `CLAUDE.md` (and `CLAUDE.local.md`).
- Custom slash commands: `.claude/commands/*.md`,
  personal `~/.claude/commands/`; skills in `.claude/skills/`.

Shadowcode uses its OWN names, deliberately different:
`shadowcode.json`, `.shadowcode/settings.json`,
`~/.config/shadowcode/config.json`, `SHADOWCODE.md` — same idea
(user/project/local precedence), different files, no copied content.

### Permission model (public surface)
- Rules shaped `Tool(pattern)`, e.g. `Bash(npm run test *)`,
  `Read(~/.zshrc)`; deny always wins over allow; more specific
  pattern overrides a general one.
- Interactive prompt options reported in public guides: allow once,
  allow and don't ask again, deny (with optional reason).
- Permission modes cycled in the UI: Normal (prompt), Auto-Accept,
  Plan (read-only), Bypass (containers only).

Shadowcode's model is its own simpler version: modes
`manual` (ask every write/shell), `auto` (allow non-destructive,
ask destructive), `plan` (read-only, refuse writes/shell), plus
allow/deny lists in its own config and `--allowed-tools` /
`--disallowed-tools` flags. It has NO bypass-all flag that
silently skips destructive checks: `--allow-destructive` still
requires `--yes` in one-shot mode and an explicit `y` in REPL.

### Slash commands (public documentation summaries)
Common built-ins reported: `/help`, `/clear`, `/compact`,
`/config`, `/init`, `/model`, `/context`, `/permissions`,
`/agents`, `/usage`, `/status`, `/doctor`, `/resume`.
`!` prefix runs a literal shell command; `@file` references a file.
`/init` generates a starter CLAUDE.md by summarising the codebase.

Shadowcode implements its own subset: `/help`, `/model`,
`/provider`, `/tools`, `/sessions`, `/resume`, `/clear`,
`/compact` (history truncation, not a model summarisation claim),
`/permissions`, `/browser`, `/doctor`, `/exit`, plus `!` shell
escape. No command text was copied.

### Tool categories (public surface, concept level only)
File reading/editing/writing, shell execution, search, web fetch,
background agents/subagents, and MCP tools. Exact internal tool
names/schemas were NOT copied; Shadowcode's tool names
(`read_file`, `write_file`, `edit_file`, `list_dir`,
`search_files`, `run_shell`, `browser_*`) are its own.

### Session handling (public surface)
Sessions persist locally, are resumed by ID (`--resume`,
`--continue`), and can run in the background (`--bg`, attach/logs/
stop/rm). Shadowcode cycle 1 implements only foreground
save/load/resume of a JSON session file — no background daemon,
no worktree, no cloud session.

## Conclusion
Everything Shadowcode borrows from Claude Code is the *idea* of a
terminal agent: REPL + one-shot, tools + permissions, sessions +
config, plugins/MCP as a concept. All code, prompts, protocols,
and file formats in `~/workspace/shadowcode/` are original.
