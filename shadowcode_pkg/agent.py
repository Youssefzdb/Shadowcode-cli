import json, re
from .permissions import check
from .providers import normalise_reply
from .tools import ToolError

TOOL_RE = re.compile(r"^TOOL:\s*(\w+)\s+(.*)$", re.M)

def run_agent(provider, tools, cfg, messages, confirm_fn=None, max_steps=10, on_token=None, on_tool=None):
    """messages: list of {role, content}. Returns final text.
    If the provider supports chat_stream, tokens are streamed through
    on_token as they arrive; the full reply is still parsed for tools.
    Native JSON tool calls are normalised to TOOL: lines (see
    providers.normalise_reply) before parsing, so Ollama/Gemini
    function-call style replies work alongside the TOOL: protocol."""
    for step in range(max_steps):
        if hasattr(provider, "chat_stream"):
            try:
                reply = provider.chat_stream(messages, cfg.get("model", ""), on_token=on_token)
                if on_token and reply and not reply.endswith("\n"):
                    on_token("\n")
            except Exception:
                # Streaming is an optimisation, never a blocker: fall back.
                reply = provider.chat(messages, cfg.get("model", ""))
            if not reply.strip():
                # An empty stream is not a successful answer (reasoning
                # models may stream reasoning only, or no content at
                # all). Fall back to a non-streaming call rather than
                # returning a blank reply as if it were an answer.
                reply = provider.chat(messages, cfg.get("model", ""))
        else:
            reply = provider.chat(messages, cfg.get("model", ""))
        reply = normalise_reply(reply)
        messages.append({"role": "assistant", "content": reply})
        tools_called = []
        for m in TOOL_RE.finditer(reply):
            name, raw = m.group(1), m.group(2).strip()
            try:
                args = json.loads(raw) if raw.startswith("{") else {"command": raw} if name == "run_shell" else {"path": raw}
            except Exception:
                args = {}
            allowed, why = check(name, args, cfg, confirm_fn)
            if not allowed:
                result = f"permission denied: {why}"
            else:
                try:
                    result = tools.call(name, args)
                except ToolError as e:
                    result = f"tool error: {e}"
                except Exception as e:
                    result = f"tool error: {e}"
            tools_called.append((name, result))
            if on_tool:
                try:
                    on_tool(name, result)
                except Exception:
                    pass
        if not tools_called:
            return reply
        feedback = "\n".join(f"Tool {n} returned: {r}" for n, r in tools_called)
        messages.append({"role": "user", "content": feedback})
    return messages[-1]["content"] if messages else ""
