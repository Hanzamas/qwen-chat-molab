import http.client as _http_client
import socket as _socket


class LLM:
    """OpenAI-compatible client for the running server (vLLM, or llama.cpp behind the proxy)."""

    def __init__(self, servers):
        self.servers = servers
        self._ctx_cache = {}

    def _hdr(self):
        return {"Content-Type": "application/json", "Authorization": f"Bearer {CFG.API_KEY}"}

    def info(self):
        cur = self.servers.current()
        return cur

    def max_context(self):
        """Read max_model_len from the server. Cached per server start, so switching models never keeps
        an old limit (the bug in the previous notebook)."""
        cur = self.servers.current()
        key = (cur["preset_name"], cur["ctx"], self.servers.state.get("started"), cur["base_url"])
        if key not in self._ctx_cache:
            status, body = Sys.http("GET", cur["base_url"] + "/models", headers=self._hdr(), timeout=5)
            try:
                val = int(json.loads(body)["data"][0]["max_model_len"]) if status == 200 else 0
            except (KeyError, IndexError, ValueError, TypeError):
                val = 0
            if not val:
                return cur["ctx"] or 0
            self._ctx_cache = {key: val}
            return val
        return self._ctx_cache.get(key) or cur["ctx"] or 0

    def tokenize(self, messages, tools=None, kwargs=None):
        cur = self.servers.current()
        body = {"model": CFG.SERVED_NAME, "messages": messages, "add_generation_prompt": True,
                "chat_template_kwargs": kwargs or {}}
        if tools:
            body["tools"] = tools
        status, text = Sys.http("POST", cur["root_url"] + "/tokenize", body, self._hdr(), timeout=600)
        try:
            d = json.loads(text)
            return int(d.get("count") or len(d.get("tokens") or [])) if status == 200 else self.estimate(messages)
        except (ValueError, TypeError):
            return self.estimate(messages)

    @staticmethod
    def estimate(messages):
        """About 3 characters per token; images count 1500 each."""
        n = 0
        for m in messages:
            c = m.get("content")
            if isinstance(c, list):
                for part in c:
                    n += 1500 if part.get("type") in ("image_url", "video_url") else len(part.get("text", "")) // 3
            else:
                n += len(c or "") // 3
            n += len(m.get("reasoning_content") or "") // 3
        return n

    def chat(self, messages, tools=None, kwargs=None, sampling=None, max_tokens=None, on_delta=None, stop=None,
             tool_choice=None, timeout=7200):
        """Streamed chat completion. Returns {content, reasoning, calls, usage, finish, t_think, t_answer}."""
        cur = self.servers.current()
        body = {"model": CFG.SERVED_NAME, "messages": messages, "stream": True, "stream_options": {"include_usage": True},
                **(sampling or {}), "chat_template_kwargs": kwargs or {}}
        if max_tokens:
            body["max_tokens"] = int(max_tokens)
        if tools:
            body["tools"] = tools
            body["tool_choice"] = tool_choice or "auto"
        LLM.spec_safe(body, cur, self.servers.state.get("mtp"))
        req = urllib.request.Request(cur["base_url"] + "/chat/completions", data=json.dumps(body).encode(), headers=self._hdr())
        acc = {"content": "", "reasoning": "", "calls": {}, "usage": None, "finish": None, "t_think": None, "t_answer": None}
        resp = urllib.request.urlopen(req, timeout=timeout)
        done = threading.Event()
        if stop is not None:
            # Stop must also work while the server is still reading a long prompt and sends nothing:
            # shutting the socket down ends the blocked read, and the server aborts the request.
            def watch():
                while not done.wait(0.25):
                    if stop.is_set():
                        LLM._abort(resp)
                        return
            threading.Thread(target=watch, daemon=True).start()
        try:
            for raw in resp:
                if stop is not None and stop.is_set():
                    acc["finish"] = "stopped"
                    break
                line = raw.decode("utf-8", "replace").strip()
                if line.startswith("error:"):  # llama.cpp reports some failures as an SSE error line
                    raise RuntimeError("Server error: " + line[6:].strip()[:500])
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                chunk = json.loads(data)
                if isinstance(chunk, dict) and chunk.get("error"):  # vLLM sends errors inside the stream
                    err = chunk["error"]
                    raise RuntimeError("Server error: " + str(err.get("message") if isinstance(err, dict) else err)[:500])
                if chunk.get("usage"):
                    acc["usage"] = chunk["usage"]
                for choice in chunk.get("choices") or []:
                    delta = choice.get("delta") or {}
                    r = delta.get("reasoning") or delta.get("reasoning_content")
                    if r:
                        acc["t_think"] = acc["t_think"] or time.time()
                        acc["reasoning"] += r
                    if delta.get("content"):
                        acc["t_answer"] = acc["t_answer"] or time.time()
                        acc["content"] += delta["content"]
                    for tc in delta.get("tool_calls") or []:
                        slot = acc["calls"].setdefault(tc.get("index", 0), {"id": "", "name": "", "arguments": ""})
                        slot["id"] = tc.get("id") or slot["id"]
                        fn = tc.get("function") or {}
                        slot["name"] += fn.get("name") or ""
                        slot["arguments"] += fn.get("arguments") or ""
                    if choice.get("finish_reason"):
                        acc["finish"] = choice["finish_reason"]
                    if (r or delta.get("content")) and on_delta:
                        on_delta(acc)
        except (OSError, ValueError, AttributeError, _http_client.HTTPException):
            if stop is not None and stop.is_set():
                acc["finish"] = "stopped"
            else:
                raise
        finally:
            done.set()
            # Closing the stream makes the server abort the request when Stop is pressed.
            resp.close()
        return acc

    @staticmethod
    def _abort(resp):
        try:
            resp.fp.raw._sock.shutdown(_socket.SHUT_RDWR)
        except Exception:
            pass
        try:
            resp.close()
        except Exception:
            pass

    @staticmethod
    def spec_safe(body, cur, mtp):
        """vLLM's speculative decoding (MTP heads or a drafter) refuses min_p and logit_bias ("not yet supported with
        speculative decoding"). Drop them there; when no top_k is set, a top_k of 64 cuts the tail min_p would have."""
        p = (cur or {}).get("preset") or {}
        if not mtp or p.get("backend") != "vllm":
            return body
        try:
            had_min_p = float(body.get("min_p") or 0) > 0
            no_top_k = int(body.get("top_k") or 0) <= 0
        except (TypeError, ValueError):
            had_min_p, no_top_k = True, True
        if had_min_p and no_top_k:
            body["top_k"] = 64
        body.pop("min_p", None)
        body.pop("logit_bias", None)
        return body

    def complete(self, messages, kwargs=None, sampling=None, max_tokens=4000, tools=None, timeout=7200, stop=None,
                 on_delta=None):
        """Like chat(); tools are sent (for an identical prompt prefix) but not used."""
        return self.chat(messages, tools=tools, kwargs=kwargs, sampling=sampling, max_tokens=max_tokens,
                         tool_choice="none" if tools else None, timeout=timeout, stop=stop, on_delta=on_delta)


LLM_CLIENT = LLM(SERVERS)
