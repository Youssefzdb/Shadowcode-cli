import difflib, os, re, subprocess
from pathlib import Path
from shadowcode_pkg import native_scanner

class ToolError(Exception):
    pass

class Tools:
    def __init__(self, workdir, allow_outside=False, add_dirs=None, browser=None, dry_run=False, mcp=None):
        self.workdir = Path(workdir).resolve()
        self.allow_outside = allow_outside
        self.extra = [Path(d).resolve() for d in (add_dirs or [])]
        self.browser = browser
        self.dry_run = dry_run
        self.mcp = mcp

    def _path(self, p):
        cand = (self.workdir / p).resolve() if not Path(p).is_absolute() else Path(p).resolve()
        if not self.allow_outside and not (str(cand).startswith(str(self.workdir)) or any(str(cand).startswith(str(d)) for d in self.extra)):
            raise ToolError(f"path outside working directory: {p}")
        return cand

    def read_file(self, path):
        return self._path(path).read_text(errors="replace")

    def write_file(self, path, content):
        p = self._path(path); p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content); return f"wrote {p} ({len(content)} chars)"

    def edit_file(self, path, old, new, dry_run=False):
        p = self._path(path); text = p.read_text(errors="replace")
        n = text.count(old)
        if n == 0:
            raise ToolError("edit: old text not found")
        if n > 1:
            raise ToolError(f"edit: old text appears {n} times, refusing ambiguous edit")
        out = text.replace(old, new)
        if dry_run or self.dry_run:
            return f"dry-run: would replace in {p}\n--- new content preview ---\n{out[:2000]}"
        p.write_text(out); return f"edited {p}"

    def diff_edit(self, path, old, new):
        """Show a unified diff for an edit without applying it.
        Use this to review before edit_file, or with --dry-run."""
        p = self._path(path); text = p.read_text(errors="replace")
        n = text.count(old)
        if n == 0:
            raise ToolError("diff_edit: old text not found")
        if n > 1:
            raise ToolError(f"diff_edit: old text appears {n} times, refusing ambiguous edit")
        out = text.replace(old, new)
        diff = "".join(difflib.unified_diff(
            text.splitlines(keepends=True), out.splitlines(keepends=True),
            fromfile=f"a/{p.name}", tofile=f"b/{p.name}"))
        return f"diff for {p} (not applied):\n{diff}"

    def count_lines(self, path):
        """(lines, nonempty) — native CLI first, Python fallback."""
        p = self._path(path)
        native = native_scanner.native_count_lines(p)
        if native is not None:
            return native
        lines = nonempty = 0
        for line in p.read_text(errors="ignore").splitlines():
            lines += 1
            if line.strip():
                nonempty += 1
        return lines, nonempty

    def fuzzy_score(self, query, candidate):
        """0..100 — native CLI first, simple Python subsequence fallback."""
        native = native_scanner.native_fuzzy_score(query, candidate)
        if native is not None:
            return native
        q, c = query.lower(), candidate.lower()
        if not q:
            return 0
        qi = score = 0
        for ch in c:
            if qi < len(q) and ch == q[qi]:
                qi += 1
                score += 10
        return min(100, score) if qi == len(q) else 0

    def list_dir(self, path="."):
        p = self._path(path)
        return "\n".join(sorted(x.name for x in p.iterdir())) if p.is_dir() else f"not a directory: {path}"

    def search_files(self, pattern):
        # Cycle 6: optional native fast path, plain-substring only.
        # Regex patterns, a missing binary, or any native error fall
        # back to the Python regex walk below — never a fake result.
        native = native_scanner.native_search(self.workdir, pattern)
        if native is not None:
            return "\n".join(native) if native else "no matches"
        rx = re.compile(pattern); hits = []
        for root, dirs, files in os.walk(self.workdir):
            dirs[:] = [d for d in dirs if d not in {".git", "__pycache__", "node_modules"}]
            for f in files:
                fp = Path(root) / f
                try:
                    txt = fp.read_text(errors="ignore")
                except Exception:
                    continue
                for i, line in enumerate(txt.splitlines(), 1):
                    if rx.search(line):
                        hits.append(f"{fp.relative_to(self.workdir)}:{i}: {line.strip()[:200]}")
                        if len(hits) >= 100:
                            return "\n".join(hits)
        return "\n".join(hits) if hits else "no matches"

    def run_shell(self, command):
        r = subprocess.run(command, shell=True, cwd=self.workdir, capture_output=True,
                           text=True, timeout=30)
        out = (r.stdout + r.stderr)[:4000]
        return f"exit={r.returncode}\n{out}"

    # dispatch used by the agent loop
    def call(self, name, args):
        if name == "read_file": return self.read_file(args.get("path", ""))
        if name == "write_file":
            if self.dry_run:
                return f"dry-run: would write {args.get('path', '')} ({len(args.get('content', ''))} chars), not written"
            return self.write_file(args.get("path", ""), args.get("content", ""))
        if name == "edit_file": return self.edit_file(args.get("path", ""), args.get("old", ""), args.get("new", ""), bool(args.get("dry_run", False)))
        if name == "diff_edit": return self.diff_edit(args.get("path", ""), args.get("old", ""), args.get("new", ""))
        if name == "mcp_call":
            if not self.mcp:
                raise ToolError("mcp not configured (see shadowcode.json mcp.servers, local stdio only)")
            return self.mcp.call(args.get("server", ""), args.get("tool", ""), args.get("arguments", {}) or {})
        if name == "count_lines":
            lines, nonempty = self.count_lines(args.get("path", ""))
            return f"lines={lines} nonempty={nonempty}"
        if name == "fuzzy_score":
            return f"score={self.fuzzy_score(args.get('query', ''), args.get('candidate', ''))}"
        if name == "list_dir": return self.list_dir(args.get("path", "."))
        if name == "search_files": return self.search_files(args.get("pattern", ""))
        if name == "run_shell": return self.run_shell(args.get("command", ""))
        if name.startswith("browser_"):
            if not self.browser:
                raise ToolError("browser not started (Playwright missing? see README)")
            return self.browser.call(name, args)
        raise ToolError(f"unknown tool: {name}")

TOOL_NAMES = ["read_file", "write_file", "edit_file", "diff_edit", "list_dir",
              "search_files", "count_lines", "fuzzy_score",
              "run_shell", "mcp_call", "browser_open", "browser_read",
              "browser_watch", "browser_watch_replay", "browser_click", "browser_click_selector",
              "browser_fill", "browser_fill_selector", "browser_fill_form",
              "browser_scroll", "browser_screenshot",
              "browser_navigate", "browser_close"]
