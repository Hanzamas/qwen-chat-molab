SUMMARY_INSTRUCTION = """Ringkas HANYA pesan {a} sampai {b} di atas untuk dirimu sendiri di masa depan. Bagian sebelumnya sudah ada
di Kronik. Tulis rinci, sekitar {words} kata. Jangan menambah apa pun yang tidak ada di percakapan.

Format wajib:
## Inti
(maksimal 200 kata: hal terpenting dari rentang ini)
## Tujuan dan preferensi
## Tokoh dan status
## Kronologi
(urut, sebut nomor pesan dan jam dunia kalau ada)
## Fakta, angka, nama
## Kutipan penting
(dialog penting disalin persis, termasuk bahasa aslinya)
## Belum selesai

Penanda pesan pengguna di rentang ini (nomor: awal pesan):
{anchors}"""

FLUSH_INSTRUCTION = """Pesan {a} sampai {b} akan dipadatkan menjadi ringkasan. Sebelum itu, simpan yang masih perlu diingat:
perbarui buku cerita (canon_set), simpan atau perbarui memory penting (memory_save / memory_update, lingkup yang tepat), dan catat
status tokoh yang belum tercatat (status_update). Panggil tool yang perlu, lalu jawab "selesai". Jangan menulis cerita."""

ERA_INSTRUCTION = """Padatkan ringkasan-ringkasan kronik lama berikut menjadi SATU ringkasan era, sekitar sepertiga panjangnya.
Pertahankan format (## Inti, ## Tujuan dan preferensi, ## Tokoh dan status, ## Kronologi, ## Fakta, angka, nama,
## Kutipan penting, ## Belum selesai). Jangan menambah apa pun.

{texts}"""


class Compactor:
    COMPACT_AT = 0.90
    TARGET = 0.60
    KEEP_USER_TURNS = 3
    CHUNK_TOKENS = 100_000
    CHRONICLE_SHARE = 0.25

    def __init__(self, store, prompt, llm, memory):
        self.store, self.prompt, self.llm, self.mem = store, prompt, llm, memory
        self.cancel = threading.Event()

    def measure(self, chat_id, tools):
        c = self.prompt.ctx(chat_id)
        msgs, _ = self.prompt.build(chat_id, ephemeral=False)
        return self.llm.tokenize(msgs, tools, self.prompt.kwargs(c))

    def maybe(self, chat_id, tools, toolbox, phase=lambda m: None, force=False, threshold=None, last_used=0,
              pending_estimate=0):
        """Compact when the prompt passes the threshold (or always with force). Returns the token count after."""
        maxc = self.llm.max_context()
        if not maxc:
            return 0
        threshold = threshold or self.COMPACT_AT
        # Tokenizing a long history costs time: skip only when the last count plus what is about to be added
        # (a big attachment, say) is still well below the threshold.
        if not force and last_used and last_used + pending_estimate < 0.7 * maxc:
            return last_used
        used = self.measure(chat_id, tools) + pending_estimate
        if not force and used < threshold * maxc:
            return used
        path = self.store.path(chat_id)
        ids = [m["id"] for m in path]
        users = [i for i, m in enumerate(path) if m["role"] == "user" and not m["ooc"]]
        chat = self.store.chat(chat_id)
        strip_pos = ids.index(chat["strip_node"]) if chat.get("strip_node") in ids else -1
        # Stage 1: drop old thinking, attachments and long tool results (originals stay in the database).
        if users and strip_pos < users[-1] - 1:
            phase("Memadatkan konteks: membuang thinking, lampiran, dan hasil tool lama…")
            self.store.x("UPDATE chats SET strip_node = ? WHERE id = ?", (ids[users[-1] - 1], chat_id))
            used = self.measure(chat_id, tools) + pending_estimate
            if not force and used < self.TARGET * maxc:
                return used
        # Stage 2: flush memory, then summarize in chunks.
        sums = [s for s in self.store.q("SELECT * FROM summaries WHERE chat_id = ? AND level = 'chunk'", (chat_id,))
                if s["node_id"] in ids]
        done_pos = max((ids.index(s["node_id"]) for s in sums), default=-1)
        users_after = [u for u in users if u > done_pos]
        if len(users_after) <= self.KEEP_USER_TURNS:
            return used
        cutoff = users_after[-self.KEEP_USER_TURNS] - 1
        if cutoff <= done_pos:
            return used
        self.cancel.clear()
        phase(f"Menyimpan memory sebelum memadatkan pesan {done_pos + 2}–{cutoff + 1}…")
        self.flush(chat_id, path[:cutoff + 1], toolbox, done_pos + 2, cutoff + 1)
        budget = min(32768, max(4096, maxc // 16))
        think = 12000 if self.prompt.kwargs(self.prompt.ctx(chat_id)).get("enable_thinking", True) else 0
        for a, b in self.chunks(path, done_pos + 1, cutoff):
            if self.cancel.is_set():
                break
            phase(f"Meringkas pesan {a + 1}–{b + 1}…")
            text = self.summarize(chat_id, path, a, b, budget, think, tools)
            if not text:
                raise RuntimeError(f"Ringkasan pesan {a + 1}–{b + 1} kosong. Compaction dihentikan; tidak ada yang dihapus.")
            text = self.entity_check(chat_id, path[a:b + 1], text)
            core = self.core_of(text)
            self.store.x("INSERT INTO summaries (chat_id, node_id, from_id, level, text, core, created) VALUES (?, ?, ?, 'chunk', ?, ?, ?)",
                         (chat_id, ids[b], ids[a], f"[Pesan {a + 1}–{b + 1}]\n{text}", core, time.time()))
            if core:
                mctx = self.mem.ctx_of(chat_id)
                self.mem.save(f"[Inti {chat['title']}, pesan {a + 1}–{b + 1}] {core}",
                              "story" if mctx.get("story_id") else "chat", mctx, kind="summary_core")
        self.condense(chat_id, ids, maxc, tools, phase)
        self.prompt.new_epoch(chat_id)
        return self.measure(chat_id, tools)

    def chunks(self, path, start, end):
        """Split path[start..end] into ~CHUNK_TOKENS pieces that end right before a user message."""
        out, a, size = [], start, 0
        for i in range(start, end + 1):
            size += self.llm.estimate([{"content": path[i]["content"], "reasoning_content": path[i]["reasoning"]}])
            nxt = path[i + 1] if i + 1 < len(path) else None
            if size >= self.CHUNK_TOKENS and nxt is not None and nxt["role"] == "user" and i < end:
                out.append((a, i))
                a, size = i + 1, 0
        if a <= end:
            out.append((a, end))
        return out

    def flush(self, chat_id, path, toolbox, a, b):
        msgs = self.prompt.side(chat_id, FLUSH_INSTRUCTION.format(a=a, b=b), path=path)
        c = self.prompt.ctx(chat_id)
        head = path[-1]["id"] if path else None
        allowed = {"canon_set", "memory_save", "memory_update", "memory_forget", "status_update", "fact_save", "world_event"}
        tools = [t for t in toolbox.specs(c) if t["function"]["name"] in allowed]
        for _ in range(4):
            acc = self.llm.chat(msgs, tools=tools, kwargs=self.prompt.kwargs(c), sampling={"temperature": 0.6},
                                max_tokens=8000)
            calls = [v for _, v in sorted(acc["calls"].items())]
            if not calls:
                self.store.side_log("memory_flush", {"range": [a, b], "answer": acc["content"],
                                                     "transcript": [m for m in msgs if m["role"] in ("assistant", "tool")]},
                                    chat_id, head)
                return
            msgs.append({"role": "assistant", "content": acc["content"],
                         "tool_calls": [{"id": cl["id"] or f"f{i}", "type": "function",
                                         "function": {"name": cl["name"], "arguments": cl["arguments"] or "{}"}}
                                        for i, cl in enumerate(calls)]})
            for i, cl in enumerate(calls):
                res, _, _ = toolbox.call(chat_id, head, cl["name"], cl["arguments"])
                msgs.append({"role": "tool", "tool_call_id": cl["id"] or f"f{i}", "content": res})

    def summarize(self, chat_id, path, a, b, budget, think, tools):
        anchors = "\n".join(f"{i + 1}: {path[i]['content'][:80].replace(chr(10), ' ')}"
                            for i in range(a, b + 1) if path[i]["role"] == "user")
        instr = SUMMARY_INSTRUCTION.format(a=a + 1, b=b + 1, words=int(budget * 0.55), anchors=anchors[:6000])
        msgs = self.prompt.side(chat_id, instr, path=path[:b + 1])
        c = self.prompt.ctx(chat_id)
        acc = self.llm.complete(msgs, kwargs=self.prompt.kwargs(c), sampling={"temperature": 0.6, "top_p": 0.95},
                                max_tokens=budget + think, tools=tools, stop=self.cancel)
        return (acc["content"] or "").strip()

    @staticmethod
    def core_of(text):
        m = re.search(r"##\s*Inti\s*\n(.*?)(?=\n##\s|\Z)", text, re.S)
        return m.group(1).strip()[:2000] if m else ""

    def entity_check(self, chat_id, msgs, summary):
        """Capitalized names that recur in the chunk but appear neither in the summary nor in the story book."""
        c = self.prompt.ctx(chat_id)
        canon = self.prompt.stories.canon_text(c["story"]["id"]) if c["story"] else ""
        have = (summary + "\n" + canon).lower()
        counts = {}
        for m in msgs:
            for w in re.findall(r"(?<![.!?]\s)(?<!^)\b([A-ZÄÖÜ][\wäöüß]{2,})", m["content"] or ""):
                if w.lower() not in TXT.ALL_STOP:
                    counts[w] = counts.get(w, 0) + 1
        missing = [w for w, n in sorted(counts.items(), key=lambda kv: -kv[1]) if n >= 2 and w.lower() not in have][:30]
        if missing:
            summary += "\n## Nama lain yang muncul\n" + ", ".join(missing)
        return summary

    def condense(self, chat_id, ids, maxc, tools, phase):
        sums = [s for s in self.store.q("SELECT * FROM summaries WHERE chat_id = ? AND level IN ('chunk', 'era') ORDER BY id",
                                        (chat_id,)) if s["node_id"] in ids]
        total = sum(len(s["text"]) // 3 for s in sums)
        chunks = [s for s in sums if s["level"] == "chunk"]
        if total <= self.CHRONICLE_SHARE * maxc or len(chunks) < 3:
            return
        old = chunks[:max(2, len(chunks) // 2)]
        phase(f"Memadatkan {len(old)} ringkasan lama menjadi satu era…")
        msgs = self.prompt.side(chat_id, ERA_INSTRUCTION.format(texts="\n\n".join(s["text"] for s in old)))
        c = self.prompt.ctx(chat_id)
        acc = self.llm.complete(msgs, kwargs=self.prompt.kwargs(c), sampling={"temperature": 0.6},
                                max_tokens=min(32768, maxc // 16) + 12000, tools=tools)
        text = (acc["content"] or "").strip()
        if not text:
            return
        self.store.x("INSERT INTO summaries (chat_id, node_id, from_id, level, text, core, created) VALUES (?, ?, ?, 'era', ?, ?, ?)",
                     (chat_id, old[-1]["node_id"], old[0]["from_id"], f"[Era]\n{text}", self.core_of(text), time.time()))
        # Condensed chunks leave the prompt but stay readable with summary_read.
        self.store.x(f"UPDATE summaries SET level = 'chunk_old' WHERE id IN ({','.join(str(s['id']) for s in old)})")
