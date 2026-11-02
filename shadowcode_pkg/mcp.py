"""Minimal MCP client — local stdio only, approval-gated, deny by default.

Shadowcode does NOT connect to remote MCP servers by default.
A server is only used when it is explicitly listed in config
(mcp.servers in shadowcode.json / .shadowcode/settings.json) AND
its command is a local executable / script inside the working
directory tree (or an absolute path the user configured).
Each mcp_call goes through the normal permission check in
agent.py (mcp_call is a WRITE tool: manual mode asks, plan mode
refuses), so a configured server is still not auto-run.

Protocol: JSON-RPC 2.0 over stdio, newline-delimited:
initialize -> notifications/initialized -> tools/list -> tools/call.
HTTP/SSE servers are NOT supported in this client on purpose:
use a local stdio wrapper if you need one, and log that decision.
"""
import json, subprocess, threading
from pathlib import Path


class MCPError(Exception):
    pass


class MCPClient:
    def __init__(self, servers, workdir):
        """servers: {name: {"command": [...], "args": [...]}} from config."""
        self.workdir = Path(workdir).resolve()
        self.servers = servers or {}
        self._procs = {}
        self._locks = {}
        self._next_id = 1

    def _is_local(self, command):
        """Local only: either the command itself is a file inside the
        working directory, or it is a plain interpreter (python3/node)
        running a script file inside the working directory. Anything
        else (curl, a URL, an absolute path outside the workdir) is
        refused — that is how remote servers stay out by default."""
        if not command:
            return False
        exe = command[0]
        p = Path(exe)
        if p.is_absolute():
            return p.is_file()
        cand = (self.workdir / exe).resolve()
        if str(cand).startswith(str(self.workdir)) and cand.is_file():
            return True
        if exe in ("python3", "python", "node") and len(command) > 1:
            script = Path(command[1])
            if not script.is_absolute():
                script = (self.workdir / script).resolve()
            return str(script).startswith(str(self.workdir)) and script.is_file()
        return False

    def _start(self, name):
        if name in self._procs:
            return self._procs[name]
        spec = self.servers.get(name)
        if not spec:
            raise MCPError(f"mcp server not configured: {name}")
        command = list(spec.get("command", []))
        if not self._is_local(command):
            raise MCPError(
                f"mcp server {name} refused: command must be a local file "
                "inside the working directory (no remote/HTTP servers by default)"
            )
        try:
            proc = subprocess.Popen(
                command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True, cwd=str(self.workdir),
            )
        except Exception as e:
            raise MCPError(f"failed to start mcp server {name}: {e}")
        self._procs[name] = proc
        self._locks[name] = threading.Lock()
        # initialize handshake
        self._rpc(name, "initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "shadowcode", "version": "0.2.0"},
        })
        try:
            proc.stdin.write(json.dumps({
                "jsonrpc": "2.0", "method": "notifications/initialized",
            }) + "\n")
            proc.stdin.flush()
        except Exception:
            pass
        return proc

    def _rpc(self, name, method, params=None):
        proc = self._start(name)
        rid = self._next_id
        self._next_id += 1
        msg = {"jsonrpc": "2.0", "id": rid, "method": method}
        if params is not None:
            msg["params"] = params
        with self._locks[name]:
            proc.stdin.write(json.dumps(msg) + "\n")
            proc.stdin.flush()
            line = proc.stdout.readline()
        if not line:
            raise MCPError(f"mcp server {name} closed the connection")
        try:
            resp = json.loads(line)
        except Exception as e:
            raise MCPError(f"mcp server {name} returned invalid JSON: {e}")
        if "error" in resp:
            raise MCPError(f"mcp server {name} error: {resp['error']}")
        return resp.get("result")

    def list_tools(self, name):
        result = self._rpc(name, "tools/list") or {}
        return [t.get("name") for t in result.get("tools", [])]

    def call(self, server, tool, arguments):
        # tools/list first: refuse tools the server does not advertise.
        advertised = self.list_tools(server)
        if tool not in advertised:
            raise MCPError(f"mcp tool not advertised by {server}: {tool}")
        result = self._rpc(name=server, method="tools/call", params={
            "name": tool, "arguments": arguments or {},
        }) or {}
        parts = []
        for c in result.get("content", []):
            if isinstance(c, dict) and "text" in c:
                parts.append(c["text"])
        if result.get("isError"):
            raise MCPError("mcp tool error: " + "\n".join(parts))
        return "\n".join(parts) if parts else json.dumps(result)

    def close(self):
        for proc in self._procs.values():
            try:
                proc.terminate()
            except Exception:
                pass
        self._procs.clear()
