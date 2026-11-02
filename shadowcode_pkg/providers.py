import json, os, re, urllib.request

SYSTEM = """You are Shadowcode, a CLI coding agent. Use tools by writing lines:
TOOL: <tool_name> <json args>
Tools: read_file, write_file, edit_file, list_dir, search_files, run_shell,
browser_open, browser_read, browser_click, browser_fill, browser_screenshot,
browser_navigate, browser_close. After tool results, answer the user briefly.
Do not invent file contents; read files first.
You may also return native JSON tool calls, which Shadowcode converts to
TOOL: lines: {"tool_calls": [{"name": "<tool>", "arguments": {...}}]}"""

def _post(url, payload, headers=None):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json", **(headers or {})})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())

def _tool_calls_to_lines(tool_calls):
    """Convert native tool-call structures to Shadowcode TOOL: lines."""
    lines = []
    for tc in tool_calls or []:
        if isinstance(tc, dict):
            fn = tc.get("function") or {}
            name = tc.get("name") or fn.get("name")
            args = tc.get("arguments") or tc.get("args") or fn.get("arguments") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    args = {"raw": args}
            if name:
                lines.append(f"TOOL: {name} {json.dumps(args)}")
    return lines

def _extract_native_json(text):
    """If a reply is pure JSON with tool_calls, return (lines, rest_text)."""
    if not text:
        return [], text
    stripped = text.strip()
    # A JSON object anywhere in the reply that carries tool_calls.
    for m in re.finditer(r"\{[^{}]*\"tool_calls\"\s*:[^\]]*\][^}]*\}", stripped, re.S):
        try:
            obj = json.loads(m.group(0))
        except Exception:
            continue
        lines = _tool_calls_to_lines(obj.get("tool_calls"))
        if lines:
            rest = (stripped[:m.start()] + stripped[m.end():]).strip()
            return lines, rest
    # Whole-reply JSON: {"tool": "...", "args": {...}}
    try:
        obj = json.loads(stripped)
        if isinstance(obj, dict) and obj.get("tool"):
            return [f"TOOL: {obj['tool']} {json.dumps(obj.get('args', {}))}"], ""
    except Exception:
        pass
    return [], text

def normalise_reply(text):
    """Append TOOL: lines for any native JSON tool calls in a reply,
    so the agent loop (which parses TOOL: lines) handles them."""
    if not text:
        return text
    lines, rest = _extract_native_json(text)
    if lines:
        return (rest + "\n" if rest else "") + "\n".join(lines)
    return text

def _stream_post(url, payload, headers, on_token):
    """POST with stream=True; yields chunks to on_token; returns full text.
    Used by Ollama / OpenAI-compatible providers. Falls back to a
    non-streaming request if the server does not stream."""
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json", **(headers or {})})
    full = []
    with urllib.request.urlopen(req, timeout=120) as r:
        for raw in r:
            line = raw.decode(errors="replace").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                obj = json.loads(data)
            except Exception:
                continue
            delta = ""
            try:
                delta = obj["choices"][0]["delta"].get("content") or ""
            except Exception:
                delta = obj.get("message", {}).get("content") or ""
            if delta:
                full.append(delta)
                if on_token:
                    on_token(delta)
    return "".join(full)

class MockProvider:
    name = "mock"
    def chat(self, messages, model):
        prompt = messages[-1]["content"] if messages else ""
        if prompt.startswith("Tool "):
            # second turn after a tool call: summarise the tool result visibly
            return "Done. " + prompt
        low = prompt.lower()
        m = re.search(r"read file (\S+)", low)
        if m: return f'TOOL: read_file {{"path": "{m.group(1)}"}}'
        if "list files" in low or "list dir" in low: return 'TOOL: list_dir {"path": "."}'
        m = re.search(r"search for (\S+)", low)
        if m: return f'TOOL: search_files {{"pattern": "{m.group(1)}"}}'
        m = re.search(r"open (https?://\S+)", low)
        if m: return f'TOOL: browser_open {{"url": "{m.group(1)}"}}'
        if "read page" in low: return 'TOOL: browser_read {}'
        if "screenshot" in low: return 'TOOL: browser_screenshot {"name": "screenshot.png"}'
        if low.startswith("echo ") or "echo " in low:
            cmd = prompt.strip()
            return f'TOOL: run_shell {{"command": {json.dumps(cmd)}}}'
        if "write file" in low or "create file" in low:
            return 'TOOL: write_file {"path": "created.txt", "content": "hello from Shadowcode\\n"}'
        return "Shadowcode (mock): I understand your request, but the mock provider only demonstrates the tool loop. Try: list files, read file README.md, echo hello, open https://example.com"
    def chat_stream(self, messages, model, on_token=None):
        text = self.chat(messages, model)
        # Deterministic chunking: word-sized chunks, so streaming tests
        # can verify tokens arrive in order and reassemble exactly.
        for word in re.findall(r"\S+\s*|\S+", text):
            if on_token:
                on_token(word)
        return text

class OllamaProvider:
    name = "ollama"
    def chat(self, messages, model):
        base = os.environ.get("SHADOWCODE_BASE_URL", "http://localhost:11434")
        try:
            d = _post(f"{base}/api/chat", {"model": model or "llama3.2",
                "messages": [{"role": "system", "content": SYSTEM}] + messages, "stream": False})
            msg = d.get("message", {})
            content = msg.get("content", "")
            lines = _tool_calls_to_lines(msg.get("tool_calls"))
            if lines:
                content = (content + "\n" if content else "") + "\n".join(lines)
            return normalise_reply(content)
        except Exception as e:
            raise RuntimeError(f"ollama request failed: {e}")
    def chat_stream(self, messages, model, on_token=None):
        base = os.environ.get("SHADOWCODE_BASE_URL", "http://localhost:11434")
        req = urllib.request.Request(f"{base}/api/chat",
            data=json.dumps({"model": model or "llama3.2",
                "messages": [{"role": "system", "content": SYSTEM}] + messages, "stream": True}).encode(),
            headers={"Content-Type": "application/json"})
        full, tool_lines = [], []
        with urllib.request.urlopen(req, timeout=120) as r:
            for raw in r:
                try:
                    obj = json.loads(raw.decode())
                except Exception:
                    continue
                msg = obj.get("message", {})
                delta = msg.get("content") or ""
                if delta:
                    full.append(delta)
                    if on_token:
                        on_token(delta)
                tool_lines.extend(_tool_calls_to_lines(msg.get("tool_calls")))
                if obj.get("done"):
                    break
        text = "".join(full)
        if tool_lines:
            text = (text + "\n" if text else "") + "\n".join(tool_lines)
        return normalise_reply(text)

class OpenAICompatProvider:
    def __init__(self, name, base, key_env, default_model, require_key=True, max_tokens=None):
        self.name = name; self.base = base; self.key_env = key_env; self.default_model = default_model
        self.require_key = require_key; self.max_tokens = max_tokens
    def _headers(self):
        key = os.environ.get(self.key_env, "") if self.key_env else ""
        if not key and self.require_key:
            raise RuntimeError(f"{self.key_env} is not set")
        # No-key providers (e.g. Kilo free models) send NO Authorization
        # header at all: an empty "Bearer " header is not the same thing.
        return {"Authorization": f"Bearer {key}"} if key else {}
    def _payload(self, messages, model, stream=False):
        payload = {"model": model or self.default_model,
                   "messages": [{"role": "system", "content": SYSTEM}] + messages}
        if stream:
            payload["stream"] = True
        if self.max_tokens:
            payload["max_tokens"] = self.max_tokens
        return payload
    def chat(self, messages, model):
        d = _post(f"{self.base}/chat/completions", self._payload(messages, model), self._headers())
        msg = d["choices"][0]["message"]
        content = msg.get("content") or ""
        if not content and (msg.get("reasoning_content") or msg.get("reasoning")):
            # Reasoning-only reply: the model spent its budget thinking
            # and produced no visible answer. Do NOT present reasoning
            # as the answer and do NOT claim success from an empty reply.
            raise RuntimeError("provider returned reasoning only, no content; retry with a larger max_tokens")
        lines = _tool_calls_to_lines(msg.get("tool_calls"))
        if lines:
            content = (content + "\n" if content else "") + "\n".join(lines)
        return normalise_reply(content)
    def chat_stream(self, messages, model, on_token=None):
        return _stream_post(f"{self.base}/chat/completions",
            self._payload(messages, model, stream=True), self._headers(), on_token)

class GeminiProvider:
    name = "gemini"
    def chat(self, messages, model):
        key = os.environ.get("GEMINI_API_KEY", "")
        if not key: raise RuntimeError("GEMINI_API_KEY is not set")
        m = model or "gemini-2.0-flash"
        parts = [{"text": SYSTEM}] + [{"text": x["content"]} for x in messages]
        d = _post(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={key}",
                  {"contents": [{"parts": parts}]})
        cand = d["candidates"][0]["content"]["parts"]
        texts, lines = [], []
        for part in cand:
            if "text" in part:
                texts.append(part["text"])
            if "functionCall" in part:
                fc = part["functionCall"]
                lines.append(f"TOOL: {fc.get('name')} {json.dumps(fc.get('args', {}))}")
        content = "".join(texts)
        if lines:
            content = (content + "\n" if content else "") + "\n".join(lines)
        return normalise_reply(content)

def get_provider(name):
    if name == "mock": return MockProvider()
    if name == "ollama": return OllamaProvider()
    if name == "groq": return OpenAICompatProvider("groq", "https://api.groq.com/openai/v1", "GROQ_API_KEY", "openai/gpt-oss-20b")
    if name == "openrouter": return OpenAICompatProvider("openrouter", "https://openrouter.ai/api/v1", "OPENROUTER_API_KEY", "google/gemma-3-27b-it:free")
    if name == "kilo":
        # Kilo gateway, OpenAI-compatible. Free models need NO key and
        # NO Authorization header; KILO_API_KEY is optional and only
        # used for paid models if the user sets it. Default routes
        # free models automatically (256k context per live catalog).
        # max_tokens is generous on purpose: reasoning models can
        # otherwise spend a small budget thinking and return no
        # visible content at all.
        return OpenAICompatProvider("kilo", "https://api.kilo.ai/api/openrouter", "KILO_API_KEY", "kilo-auto/free", require_key=False, max_tokens=4096)
    if name == "gemini": return GeminiProvider()
    raise ValueError(f"unknown provider: {name}")
