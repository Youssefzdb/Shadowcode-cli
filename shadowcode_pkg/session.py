import json, uuid
from datetime import datetime, timezone
from .config import session_dir

def new_id():
    return uuid.uuid4().hex[:12]

def save(session):
    p = session_dir() / f"{session['id']}.json"
    session["updated_at"] = datetime.now(timezone.utc).isoformat()
    p.write_text(json.dumps(session, indent=2))
    return p

def load(sid):
    p = session_dir() / f"{sid}.json"
    if not p.is_file():
        # allow prefix match, but only when it is unambiguous
        cands = sorted(session_dir().glob(f"{sid}*.json"))
        if not cands:
            raise FileNotFoundError(f"session not found: {sid}")
        if len(cands) > 1:
            ids = ", ".join(c.stem for c in cands)
            raise ValueError(f"ambiguous session prefix {sid!r}: matches {ids} — use a full id")
        return json.loads(cands[0].read_text())
    return json.loads(p.read_text())

def ensure_unique_id(sid):
    """Collision handling for --session-id: if a session file with
    that id already exists, append -2, -3, … until free. Never
    overwrites an existing session on a fresh (non-resume) start."""
    if not (session_dir() / f"{sid}.json").is_file():
        return sid
    n = 2
    while (session_dir() / f"{sid}-{n}.json").is_file():
        n += 1
    return f"{sid}-{n}"

def _parse_date(value):
    """Parse YYYY-MM-DD or an ISO datetime to a date, or None."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value)).date()
    except Exception:
        return None


def search_sessions(query, from_date=None, to_date=None):
    """Search sessions by id, provider, model, or message text.
    Returns [(id, provider, n_messages, updated_at, snippet)].
    from_date/to_date (YYYY-MM-DD or ISO) filter by updated_at date,
    inclusive. This is read-only: it never creates or modifies a
    session file.
    """
    q = str(query or "").lower()
    d_from = _parse_date(from_date)
    d_to = _parse_date(to_date)
    out = []
    for p in sorted(session_dir().glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            d = json.loads(p.read_text())
        except Exception:
            continue
        if d_from or d_to:
            upd = _parse_date(d.get("updated_at", ""))
            if upd is None:
                continue
            if d_from and upd < d_from:
                continue
            if d_to and upd > d_to:
                continue
        hay = " ".join([
            str(d.get("id", "")), str(d.get("provider", "")), str(d.get("model", "")),
            *[str(m.get("content", "")) for m in d.get("messages", [])],
        ])
        if q in hay.lower():
            snippet = ""
            for m in d.get("messages", []):
                c = str(m.get("content", ""))
                if q in c.lower():
                    i = c.lower().find(q)
                    snippet = c[max(0, i - 40):i + 120].replace("\n", " ")
                    break
            out.append((d.get("id"), d.get("provider"), len(d.get("messages", [])),
                        d.get("updated_at", ""), snippet))
    return out

def export_session(sid, fmt="md"):
    """Export a session to Markdown or JSON text (no file written
    here; the caller decides whether to print or save it)."""
    d = load(sid)
    if fmt == "json":
        return json.dumps(d, indent=2)
    lines = [f"# Shadowcode session {d.get('id')}",
             f"- provider: {d.get('provider')}  model: {d.get('model')}",
             f"- updated: {d.get('updated_at', '')}", ""]
    for m in d.get("messages", []):
        role = m.get("role", "?")
        lines.append(f"## {role}")
        lines.append(str(m.get("content", "")))
        lines.append("")
    return "\n".join(lines)

def list_sessions():
    out = []
    for p in sorted(session_dir().glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            d = json.loads(p.read_text())
            out.append((d.get("id"), d.get("provider"), len(d.get("messages", [])), d.get("updated_at", "")))
        except Exception:
            pass
    return out


def sessions_table():
    """Read-only sessions list, formatted for display.

    Deliberately does NOT create, save, or touch any session file:
    listing must not pollute real sessions (no last-session bump,
    no new id, no updated_at change).
    """
    rows = list_sessions()
    if not rows:
        return ["no saved sessions"]
    return [f"{sid} provider={prov} messages={n} updated={upd}"
            for sid, prov, n, upd in rows]


def export_session_file(sid, fmt="md", output=None):
    """Export a session to a FILE and return its path (as a string).

    output may be a file path, or a directory (then the file is
    session-<id>.md/.json inside it). An existing file is never
    overwritten: -2, -3, … are appended. The session itself is
    never modified.
    """
    from pathlib import Path
    text = export_session(sid, fmt)
    ext = "json" if fmt == "json" else "md"
    if output:
        out = Path(output)
        if out.is_dir() or str(output).endswith("/"):
            out = out / f"session-{sid}.{ext}"
    else:
        out = Path(f"session-{sid}.{ext}")
    if out.suffix != f".{ext}":
        out = out.with_suffix(f".{ext}")
    if out.exists():
        n = 2
        while True:
            cand = out.with_name(f"{out.stem}-{n}{out.suffix}")
            if not cand.exists():
                out = cand
                break
            n += 1
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text)
    return str(out)

def sessions_view(query=None):
    """Sessions view (cycle 8): read-only list + per-session info +
    the commands that act on a session. This function never creates,
    modifies, or deletes a session file: list/search/info/export
    are read-only, and resume/compact are callers' approved paths
    (resume loads in memory; compact is the approved extractive
    path in main.py / --compact-session). Use it for /sessions-view
    in the Python REPL/TUI and, via --list-sessions/--search-sessions
    /--session-info, in the TS TUI."""
    rows = search_sessions(query) if query else list_sessions()
    lines = ["sessions view:"]
    if not rows:
        lines.append("  no saved sessions" + (f" matching {query!r}" if query else ""))
    else:
        for row in rows:
            if len(row) == 5:  # search hit: (id, provider, n, updated, snippet)
                sid, prov, n, upd, snippet = row
                lines.append(f"  {sid} provider={prov} messages={n} updated={upd} snippet={snippet}")
            else:  # list row: (id, provider, n, updated)
                sid, prov, n, upd = row
                lines.append(f"  {sid} provider={prov} messages={n} updated={upd}")
    lines.append("  actions: /resume <id> (load in memory)  /export <id> [md|json]  /export-file <id> [md|json] [path]")
    lines.append("           /session-info <id>  /search-sessions <query>  /compact (current session only, approved path)")
    lines.append("  from this view: /sessions-view <id> info | export [md|json] | export-file [md|json] [path] | resume")
    lines.append("           (info/export are read-only; resume loads in memory; export-file is the approved export path)")
    lines.append("  note: listing/searching/info/export never edit a session file.")
    return "\n".join(lines)


def session_exists(sid):
    """True if a session file with exactly this id exists."""
    try:
        return (session_dir() / f"{sid}.json").is_file()
    except Exception:
        return False


def sessions_view_selected(sid):
    """Read-only detail for one selected session + its actions.

    Never creates, modifies, or deletes a session file. Resume,
    compact, and export-file are callers' approved paths (see
    sessions_view()): this function only describes them.
    """
    d = load(sid)
    lines = [f"session selected: {d.get('id')}",
             f"  provider={d.get('provider')} model={d.get('model') or '(default)'} "
             f"messages={len(d.get('messages', []))} updated={d.get('updated_at', '')}",
             "  actions: /sessions-view <id> info | export [md|json] | export-file [md|json] [path] | resume",
             "  note: info/export are read-only; resume loads in memory; "
             "export-file writes an export file (never overwrites); "
             "compact is the approved path for shrinking a session."]
    return "\n".join(lines)


def parse_sessions_view_action(text):
    """Parse a /sessions-view argument into an action.

    Returns (kind, sid, action, extra):
    - ("list", None, None, None): no argument — list all.
    - ("search", query, None, None): no exact session id matches.
    - ("select", sid, None, None): "<id>" exactly matches a session.
    - ("action", sid, "info"|"export"|"export-file"|"resume", fmt_or_path):
        "<id> info", "<id> export [md|json]",
        "<id> export-file [md|json] [path]", "<id> resume".
    Anything else is a search query, never an error.
    """
    text = (text or "").strip()
    if not text:
        return ("list", None, None, None)
    parts = text.split()
    if len(parts) >= 2 and session_exists(parts[0]) and parts[1] in ("info", "export", "export-file", "resume"):
        action = parts[1]
        extra = parts[2] if len(parts) > 2 else None
        if action == "export-file" and len(parts) > 3:
            extra = (parts[2], parts[3])
        return ("action", parts[0], action, extra)
    if len(parts) == 1 and session_exists(parts[0]):
        return ("select", parts[0], None, None)
    return ("search", text, None, None)


def latest():
    s = list_sessions()
    return s[0][0] if s else None

def compact_messages(messages, keep=10):
    """Extractive context management (no model call, no invented summary):
    keep system messages + the last `keep` messages, and replace the
    dropped middle with one summary line listing how many messages were
    dropped and the first line of each dropped user prompt (truncated).
    Returns (new_messages, dropped_count)."""
    if len(messages) <= keep:
        return messages, 0
    system = [m for m in messages if m.get("role") == "system"]
    rest = [m for m in messages if m.get("role") != "system"]
    dropped = rest[:-keep] if len(rest) > keep else []
    kept = rest[-keep:] if keep else []
    topics = []
    for m in dropped:
        if m.get("role") == "user":
            topics.append(str(m.get("content", ""))[:80].replace("\n", " "))
    summary = {
        "role": "user",
        "content": (
            f"[context compacted: {len(dropped)} earlier messages removed; "
            f"earlier user topics: {'; '.join(topics) if topics else 'none'}]"
        ),
    }
    return system + [summary] + kept, len(dropped)
