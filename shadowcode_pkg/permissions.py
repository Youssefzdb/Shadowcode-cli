import re

DESTRUCTIVE = [
    r"\brm\s+-[^\s]*r", r"\bmkfs\b", r"\bdd\b.*\bof=/dev/",
    r"\bshutdown\b", r"\breboot\b", r"\|\s*(ba)?sh\b",
    r"chmod\s+-R\s+777\s+/", r">\s*/dev/", r":\(\)\{.*\}.*&",
]
WRITE_TOOLS = {"write_file", "edit_file", "run_shell", "browser_fill",
               "browser_fill_selector", "browser_fill_form", "mcp_call"}
READ_TOOLS = {"read_file", "diff_edit", "list_dir", "search_files", "count_lines", "fuzzy_score", "browser_open",
              "browser_read", "browser_watch", "browser_watch_replay", "browser_navigate", "browser_screenshot", "browser_close",
              "browser_click_selector", "browser_scroll"}

def is_destructive(command):
    return any(re.search(p, command or "") for p in DESTRUCTIVE)

def check(tool, args, cfg, confirm_fn=None):
    """Return (allowed, message). confirm_fn(prompt) -> bool, for interactive asks."""
    deny = set(cfg.get("permissions", {}).get("deny", []) or []) | set(cfg.get("disallowed_tools", []) or [])
    allow = set(cfg.get("permissions", {}).get("allow", []) or []) | set(cfg.get("allowed_tools", []) or [])
    if tool in deny:
        return False, f"denied by config: {tool}"
    mode = cfg.get("permission_mode", "manual")
    if mode == "plan" and tool in WRITE_TOOLS:
        return False, f"plan mode is read-only: {tool} refused"
    if tool == "run_shell" and is_destructive(args.get("command", "")):
        if not cfg.get("allow_destructive"):
            return False, "destructive command refused (use --allow-destructive and confirm)"
        if not cfg.get("yes") and confirm_fn:
            if not confirm_fn(f"Run destructive command? {args.get('command')} [y/N] "):
                return False, "destructive command not confirmed"
        if not cfg.get("yes") and not confirm_fn:
            return False, "destructive command needs --yes in one-shot mode"
    if tool in allow:
        return True, "allowed by config"
    if mode == "auto" and tool in READ_TOOLS:
        return True, "auto mode: read tool allowed"
    if mode == "auto" and tool not in WRITE_TOOLS:
        return True, "auto mode"
    if confirm_fn and tool in WRITE_TOOLS:
        if confirm_fn(f"Allow tool {tool} {args}? [y/N] "):
            return True, "confirmed"
        return False, "not confirmed by user"
    if not confirm_fn and mode == "manual" and tool in WRITE_TOOLS:
        return False, "manual mode: write/shell tool needs confirmation (use REPL or --yes/--permission-mode auto)"
    return True, "allowed"
