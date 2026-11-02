#!/usr/bin/env python3
"""Dummy local MCP server for Shadowcode tests only.
JSON-RPC 2.0 over stdio, newline-delimited. No network, no accounts.
Tools: echo (returns its text argument)."""
import json, sys

for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        msg = json.loads(line)
    except Exception:
        continue
    if "method" not in msg:
        continue
    method = msg["method"]
    if method == "initialize":
        result = {"protocolVersion": "2024-11-05", "capabilities": {},
                  "serverInfo": {"name": "dummy", "version": "0.1"}}
    elif method == "tools/list":
        result = {"tools": [{"name": "echo", "description": "echo text",
                             "inputSchema": {"type": "object"}}]}
    elif method == "tools/call":
        params = msg.get("params", {})
        text = (params.get("arguments") or {}).get("text", "")
        result = {"content": [{"type": "text", "text": f"echo: {text}"}]}
    elif method.startswith("notifications/"):
        continue
    else:
        result = {}
    if "id" in msg:
        sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": msg["id"], "result": result}) + "\n")
        sys.stdout.flush()
