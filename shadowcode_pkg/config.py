import json, os
from pathlib import Path

DEFAULTS = {
    "provider": "mock", "model": "", "working_dir": ".",
    "permission_mode": "manual", "allow_destructive": False,
    "allow_outside": False, "yes": False,
    "permissions": {"allow": [], "deny": []},
    "allowed_tools": [], "disallowed_tools": [],
    "add_dirs": [], "preview_port": 8765, "session_id": "",
    "dry_run": False, "mcp": {"servers": {}},
}

KEY_ENV = {"groq": "GROQ_API_KEY", "gemini": "GEMINI_API_KEY",
           "openrouter": "OPENROUTER_API_KEY", "kilo": "KILO_API_KEY",
           "ollama": "", "mock": ""}

def _load_json(path):
    try:
        p = Path(path)
        if p.is_file():
            return json.loads(p.read_text())
    except Exception:
        pass
    return {}

def load_config(cli_config=None):
    cfg = dict(DEFAULTS)
    # user, project, local — own names, not Claude's
    for path in [Path.home() / ".config" / "shadowcode" / "config.json",
                 Path(".shadowcode") / "settings.json",
                 Path("shadowcode.json")]:
        cfg.update(_load_json(path))
    if os.environ.get("SHADOWCODE_CONFIG"):
        cfg.update(_load_json(os.environ["SHADOWCODE_CONFIG"]))
    if cli_config:
        cfg.update(_load_json(cli_config))
    for env, key in [("SHADOWCODE_PROVIDER", "provider"),
                     ("SHADOWCODE_MODEL", "model"),
                     ("SHADOWCODE_BASE_URL", "base_url"),
                     ("SHADOWCODE_WORKDIR", "working_dir")]:
        if os.environ.get(env):
            cfg[key] = os.environ[env]
    return cfg

def key_set(provider):
    env = KEY_ENV.get(provider, "")
    return bool(env and os.environ.get(env))

def key_env_name(provider):
    return KEY_ENV.get(provider, "")

def session_dir():
    d = Path.home() / ".config" / "shadowcode" / "sessions"
    d.mkdir(parents=True, exist_ok=True)
    return d

def last_session_file():
    return Path.home() / ".config" / "shadowcode" / "last_session.txt"
