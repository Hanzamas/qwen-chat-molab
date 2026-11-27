"""A fake OpenAI-compatible server (vLLM-like) for testing the notebook without a GPU.

It answers chat completions with SSE streaming, tool calls, /tokenize with chat messages, /v1/models and /health.
Replies are chosen from the last message, so every feature of the chat has a predictable answer.
"""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

STATE = {"max_len": 200_000, "log": [], "script": [], "fail_next": False}

NARRATION = "\n\n".join(
    f"Paragraf {i} dimulai ketika Lotte membuka jendela dan udara dingin masuk ke kamar. "
    f"\"Es ist kalt heute.\" (Hari ini dingin.) katanya sambil merapatkan jaket. "
    f"Di luar, trem lewat dengan bunyi besi yang berderit di rel basah. "
    f"Kamu melihat uap napasnya menggantung sebentar sebelum hilang. "
    f"Dia menunggu jawabanmu dengan alis sedikit terangkat."
    for i in range(1, 7)
)


SYNONYMS = {"coffee": "kopi", "kaffee": "kopi", "tea": "teh", "tee": "teh"}


def _embed(text):
    """Bag of words hashed into 64 dims, with a few synonyms folded together, so a paraphrase can match
    where keyword search cannot."""
    import re
    vec = [0.0] * 64
    for w in re.findall(r"\w+", text.split("Query: ")[-1].lower()):
        w = SYNONYMS.get(w, w)
        vec[sum(map(ord, w)) % 64] += 1.0
    return vec


def _last_text(messages):
    last = messages[-1]
    c = last.get("content")
    if isinstance(c, list):
        return " ".join(p.get("text", "") for p in c if p.get("type") == "text")
    return c or ""


def _reply(body):
    msgs = body["messages"]
    if STATE["script"]:
        return STATE["script"].pop(0)
    text = _last_text(msgs)
    last_role = msgs[-1]["role"]
    user_texts = " ".join(_last_text([m]) for m in msgs if m["role"] == "user")
    if "Buat pilihan aksi" in text:
        return {"content": json.dumps({"problems": [
            {"question": "Lotte menatapmu dari ambang pintu sambil menunggu jawaban yang jujur tentang alasanmu datang.",
             "options": ["Kamu bilang terus terang bahwa kamu kesepian dan ingin ngobrol sebentar sebelum tidur.",
                         "Kamu mengalihkan pembicaraan ke buku di rak dan bertanya buku mana yang paling dia sukai.",
                         "Kamu menawarkan membuat teh di dapur supaya suasananya tidak canggung."]}]})}
    if "Ringkas HANYA" in text:
        return {"content": "## Inti\nLotte dan pemain ngobrol di kamar WG.\n## Kronologi\n- Pesan awal: Lotte membuka jendela.\n"
                           "## Kutipan penting\n\"Es ist kalt heute.\""}
    if "Padatkan ringkasan" in text:
        return {"content": "## Inti\nEra pertama di WG."}
    if "akan dipadatkan menjadi ringkasan" in text:
        if last_role == "tool":
            return {"content": "selesai"}
        return {"tool_calls": [{"name": "memory_save", "arguments": json.dumps({"text": "Lotte suka teh.", "scope": "story"})}]}
    if "Daftarkan klaim fakta" in text:
        return {"content": json.dumps({"claims": []})}
    if "Waktu dunia maju" in text:
        if last_role == "tool":
            return {"content": "selesai"}
        return {"tool_calls": [{"name": "world_event", "arguments": json.dumps(
            {"text": "Frau Brunner pulang membawa belanjaan.", "known_to": ["player"], "public": True})}]}
    if "Lanjutkan narasi" in text:
        return {"content": "Paragraf tambahan satu dimulai. Kalimat kedua.\n\nParagraf tambahan dua dimulai. Kalimat kedua."}
    if "Lanjutkan jawaban terakhirmu" in text:
        return {"content": "lalu dia tertawa kecil."}
    if "buat" in text.lower() and "pertanyaan tentang detail" in text:
        return {"content": json.dumps({"qa": [{"q": "Siapa yang membuka jendela?", "a": "Lotte"}]})}
    if "Uji ingatan" in text:
        return {"content": json.dumps({"answers": ["Lotte"]})}
    if "Jelaskan kalimat" in text or "Explain the sentence below" in text:
        return {"content": json.dumps({"translation": "Hari ini dingin.", "grammar": ["es ist = itu adalah"],
                                       "vocab": [{"term": "kalt", "translation": "dingin", "note": "adjektiva"}]})}
    if "draf pesan berikutnya" in text:
        return {"content": "Aku mengangguk pelan dan duduk di kursi meja."}
    if "Permintaan perubahan dari pemain" in text:
        if last_role == "tool":
            return {"content": "Buku cerita diperbarui."}
        return {"tool_calls": [{"name": "canon_set", "arguments": json.dumps({"section": "Catatan", "text": "Sersan lebih tua."})}]}
    if "CARDTEST" in user_texts:
        if last_role == "tool":
            return {"content": "Kartu dibuat."}
        return {"tool_calls": [
            {"name": "card_draft_update", "arguments": json.dumps({"type": "character", "field": "name", "value": "Weber"})},
            {"name": "memory_save", "arguments": json.dumps({"text": f"Catatan uji {user_texts.count('CARDTEST')}", "scope": "user"})},
            {"name": "card_draft_update", "arguments": json.dumps({"type": "world", "field": "stats",
                                                                   "value": f"lapar, Lapar, 0, 100, {20 + user_texts.count('CARDTEST')}, 4"})}]}
    if "THINKTEST" in user_texts and last_role == "user":
        return {"content": "Selesai mikir.", "slow_think": 0.25,
                "reasoning": "\n".join(f"Baris pikiran {i}: menimbang detail adegan dan fakta." for i in range(80))}
    if "SLOWTEST" in text:
        return {"content": NARRATION + "\n\n" + NARRATION, "slow": 0.15}
    if "TOOLTEST" in user_texts and last_role == "user":
        return {"tool_calls": [
            {"name": "world_advance", "arguments": json.dumps({"minutes": 30})},
            {"name": "status_update", "arguments": json.dumps({"subject": "player", "changes": {"lapar": 10, "location": "Dapur"},
                                                               "reason": "masak"})},
            {"name": "roll", "arguments": json.dumps({"event": "terpeleset", "odds": 0.3})}]}
    return {"content": NARRATION, "reasoning": "Aku menyusun 6 paragraf."}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.startswith("/health"):
            return self._json({"status": "ok"})
        if self.path.startswith("/v1/models"):
            return self._json({"data": [{"id": "qwen-chat", "max_model_len": STATE["max_len"]}]})
        self._json({"error": "not found"}, 404)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        if self.path == "/v1/embeddings":
            return self._json({"data": [{"index": i, "embedding": _embed(t)} for i, t in enumerate(body["input"])]})
        if self.path == "/tokenize":
            return self._json({"count": len(json.dumps(body.get("messages", []), ensure_ascii=False)) // 3})
        if self.path != "/v1/chat/completions":
            return self._json({"error": "not found"}, 404)
        STATE["log"].append(body)
        if STATE["fail_next"]:
            STATE["fail_next"] = False
            return self._json({"error": "boom"}, 500)
        r = _reply(body)
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()

        def send(obj):
            line = b"data: " + (obj if isinstance(obj, bytes) else json.dumps(obj).encode()) + b"\n\n"
            self.wfile.write(b"%x\r\n%s\r\n" % (len(line), line))
            self.wfile.flush()

        if r.get("reasoning"):
            parts = [r["reasoning"]] if not r.get("slow_think") else r["reasoning"].split("\n")
            for part in parts:
                send({"choices": [{"index": 0, "delta": {"reasoning_content": part + ("\n" if r.get("slow_think") else "")}}]})
                if r.get("slow_think"):
                    time.sleep(r["slow_think"])
        if r.get("stream_error"):  # vLLM-style error inside the stream, after some text
            send({"choices": [{"index": 0, "delta": {"content": "Awal jawaban. "}}]})
            send({"error": {"message": r["stream_error"], "code": 500}})
            self.wfile.write(b"0\r\n\r\n")
            return
        content = r.get("content", "")
        pieces = 40 if r.get("slow") else 3
        step = max(1, len(content) // pieces + 1)
        for i in range(0, len(content), step):
            send({"choices": [{"index": 0, "delta": {"content": content[i:i + step]}}]})
            if r.get("slow"):
                time.sleep(r["slow"])
        for i, tc in enumerate(r.get("tool_calls") or []):
            send({"choices": [{"index": 0, "delta": {"tool_calls": [
                {"index": i, "id": f"call_{len(STATE['log'])}_{i}", "function": {"name": tc["name"], "arguments": tc["arguments"]}}]}}]})
        finish = "tool_calls" if r.get("tool_calls") else "stop"
        send({"choices": [{"index": 0, "delta": {}, "finish_reason": finish}]})
        prompt = len(json.dumps(body["messages"])) // 3
        send({"choices": [], "usage": {"prompt_tokens": prompt, "completion_tokens": len(content) // 3 + 1,
                                       "total_tokens": prompt + len(content) // 3 + 1}})
        send(b"[DONE]")
        self.wfile.write(b"0\r\n\r\n")


class _Server(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        pass  # the client closing a stream (Stop) is expected here


def start(port=0):
    srv = _Server(("127.0.0.1", port), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv
