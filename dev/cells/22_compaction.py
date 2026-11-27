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
perbarui buku cerita (canon_set), simpan atau perbarui memory penting (memory_save / memory_update, lingkup yang tepat), catat
status tokoh yang belum tercatat (status_update), dan catat siapa tahu apa yang belum tercatat: apa yang disaksikan, diceritakan,
atau disalahpahami tiap tokoh (knowledge_add / tell), serta janji, utang, misteri, dan janji temu yang masih terbuka
(thread_open; thread_close untuk yang sudah selesai). Panggil tool yang perlu, lalu jawab "selesai". Jangan menulis cerita."""

ERA_INSTRUCTION = """Padatkan ringkasan-ringkasan kronik lama berikut menjadi SATU ringkasan era, sekitar sepertiga panjangnya.
Pertahankan format (## Inti, ## Tujuan dan preferensi, ## Tokoh dan status, ## Kronologi, ## Fakta, angka, nama,
## Kutipan penting, ## Belum selesai). Jangan menambah apa pun.

{texts}"""


class Compactor:
    COMPACT_AT = 0.80
    FULL_AT = 0.95  # prompt plus the room the reply needs (thinking + text) must stay under this share of the window
    TARGET = 0.60
    KEEP_USER_TURNS = 3
    KEEP_TAIL = 0.25  # share of the context window kept as verbatim recent turns
    CHUNK_TOKENS = 100_000
    CHRONICLE_SHARE = 0.25

    def __init__(self, store, prompt, llm, memory):
        self.store, self.prompt, self.llm, self.mem = store, prompt, llm, memory
        self.cancel = threading.Event()
        # One compaction at a time: the idle one and a turn's own must never write summaries side by side.
        self.lock = threading.Lock()

    @staticmethod
    def progress(phase, label, limit=None):
        """on_delta callback that shows how much the model has written so far (about 3.5 characters per token)."""
        state = {"t": 0.0}

        def on_delta(acc):
            now = time.time()
            if now - state["t"] < 1.0:
                return
            state["t"] = now
            think, out = len(acc["reasoning"]) * 2 // 7, len(acc["content"]) * 2 // 7
            bits = ([f"thinking ≈{think:,}".replace(",", ".")] if think else []) + \
                   [f"writing ≈{out:,}".replace(",", ".") + (f" / {limit:,}".replace(",", ".") if limit else "") + " tokens"]
            phase(f"{label} {' · '.join(bits)}")
        return on_delta

    def measure(self, chat_id, tools):
        c = self.prompt.ctx(chat_id)
        msgs, _ = self.prompt.build(chat_id, ephemeral=False)
        return self.llm.tokenize(msgs, tools, self.prompt.kwargs(c))

    def maybe(self, chat_id, tools, toolbox, phase=lambda m: None, force=False, threshold=None, last_used=0,
              pending_estimate=0, clear_cancel=True, reserve=0):
        """Compact when the prompt passes the threshold (or always with force). Returns the token count after.
        clear_cancel: a run started by the player resets the cancel flag once it holds the lock; the idle run
        leaves it alone, so a message sent meanwhile still stops it."""
        maxc = self.llm.max_context()
        if not maxc:
            return 0
        threshold = threshold or self.COMPACT_AT
        # Tokenizing a long history costs time: skip only when the last count plus what is about to be added
        # (a big attachment, say) is still well below the threshold.
        self.last_note = ""
        if not force and last_used and last_used + pending_estimate + reserve < min(0.7, threshold - 0.05) * maxc:
            return last_used
        used = self.measure(chat_id, tools) + pending_estimate
        # Fire at the threshold, or earlier when the reply (thinking + text) would not fit next to the prompt.
        if not force and used < threshold * maxc and used + reserve <= self.FULL_AT * maxc:
            return used
        with self.lock:
            if clear_cancel:
                self.cancel.clear()
            elif self.cancel.is_set():
                return used
            return self._compact(chat_id, tools, toolbox, phase, force, maxc, pending_estimate, used)

    def _compact(self, chat_id, tools, toolbox, phase, force, maxc, pending_estimate, used):
        path = self.store.path(chat_id)
        ids = [m["id"] for m in path]
        users = [i for i, m in enumerate(path) if m["role"] == "user" and not m["ooc"]]
        chat = self.store.chat(chat_id)
        strip_pos = ids.index(chat["strip_node"]) if chat.get("strip_node") in ids else -1
        # Stage 1: drop old thinking, attachments and long tool results (originals stay in the database).
        if users and strip_pos < users[-1] - 1:
            phase("Compacting context: dropping old thinking, attachments and tool results…")
            self.store.x("UPDATE chats SET strip_node = ? WHERE id = ?", (ids[users[-1] - 1], chat_id))
            used = self.measure(chat_id, tools) + pending_estimate
            if not force and used < self.TARGET * maxc:
                return used
        # Stage 2: flush memory, then summarize in chunks.
        sums = [s for s in self.store.q("SELECT * FROM summaries WHERE chat_id = ? AND level = 'chunk'", (chat_id,))
                if s["node_id"] in ids]
        done_pos = max((ids.index(s["node_id"]) for s in sums), default=-1)
        users_after = [u for u in users if u > done_pos]
        # A group chat answers one player message with many replies: keeping one player turn whole is enough there.
        keep = 1 if (chat or {}).get("kind") == "group" else self.KEEP_USER_TURNS
        if len(users_after) <= keep:
            self.last_note = (f"Compaction skipped: only {len(users_after)} player message(s) since the last summary; "
                              f"it runs after {keep + 1}.")
            return used
        # Verbatim tail: at least KEEP_USER_TURNS turns and about KEEP_TAIL of the window, so voices, language and
        # rhythm carry over (only older turns become summaries). Never so much that nothing can be summarized.
        size = lambda i: self.llm.estimate([{"content": path[i]["content"], "reasoning_content": ""}])
        k = keep
        tail = sum(size(i) for i in range(users_after[-k], len(path)))
        while k + 1 < len(users_after) and tail < self.KEEP_TAIL * maxc:
            k += 1
            tail += sum(size(i) for i in range(users_after[-k], users_after[-k + 1]))
        cutoff = users_after[-k] - 1
        if cutoff <= done_pos:
            self.last_note = "Compaction skipped: everything older is already summarized; the recent turns stay whole."
            return used
        label = f"Saving memory before compacting messages {done_pos + 2}–{cutoff + 1}…"
        phase(label)
        self.flush(chat_id, path[:cutoff + 1], toolbox, done_pos + 2, cutoff + 1, self.progress(phase, label))
        if self.cancel.is_set():
            return used
        budget = min(32768, max(4096, maxc // 16))
        think = 12000 if self.prompt.kwargs(self.prompt.ctx(chat_id)).get("enable_thinking", True) else 0
        done_any = False
        chapters = [r["message_id"] for r in self.store.q("SELECT message_id FROM chapters WHERE chat_id = ?", (chat_id,))]
        try:
            done_any = self._summarize_chunks(chat_id, path, ids, chat, done_pos, cutoff, chapters, budget, think, tools, phase)
            if not self.cancel.is_set():
                self.condense(chat_id, ids, maxc, tools, phase)
        finally:
            if done_any or getattr(self, "_partial", False):
                self.prompt.new_epoch(chat_id)  # summaries written before a failure go into the prompt too
            self._partial = False
        return self.measure(chat_id, tools)

    def _summarize_chunks(self, chat_id, path, ids, chat, done_pos, cutoff, chapters, budget, think, tools, phase):
        done_any = False
        for a, b in self.chunks(path, done_pos + 1, cutoff, chapters):
            if self.cancel.is_set():
                break
            label = f"Summarizing messages {a + 1}–{b + 1}…"
            phase(label)
            text = self.summarize(chat_id, path, a, b, budget, think, tools, self.progress(phase, label, budget))
            if text is None:  # cancelled: what is already summarized stays, this piece is redone next time
                break
            if not text:
                raise RuntimeError(f"Summary of messages {a + 1}–{b + 1} is empty ({getattr(self, 'last_error', '')}). "
                                   f"Compaction stopped; nothing was deleted.")
            text = self.entity_check(chat_id, path[a:b + 1], text)
            core = self.core_of(text)
            self.store.x("INSERT INTO summaries (chat_id, node_id, from_id, level, text, core, created) VALUES (?, ?, ?, 'chunk', ?, ?, ?)",
                         (chat_id, ids[b], ids[a], f"[Pesan {a + 1}–{b + 1}]\n{text}", core, time.time()))
            if core:
                mctx = self.mem.ctx_of(chat_id)
                self.mem.save(f"[Inti {chat['title']}, pesan {a + 1}–{b + 1}] {core}",
                              "story" if mctx.get("story_id") else "chat", mctx, kind="summary_core", message_id=ids[b])
            done_any = True
            self._partial = True
        return done_any

    def chunks(self, path, start, end, chapters=()):
        """Split path[start..end] into ~CHUNK_TOKENS pieces that end right before a user message. A chapter mark on the
        next turn ends a piece early (once it has a third of the size), so a summary does not straddle two chapters."""
        out, a, size = [], start, 0
        chapters = set(chapters)
        for i in range(start, end + 1):
            size += self.llm.estimate([{"content": path[i]["content"], "reasoning_content": path[i]["reasoning"]}])
            nxt = path[i + 1] if i + 1 < len(path) else None
            if nxt is None or nxt["role"] != "user" or i >= end:
                continue
            turn, j = [path[i + 1]["id"]], i + 2  # the whole next turn: its user message and every reply before the next one
            while j < len(path) and path[j]["role"] != "user":
                turn.append(path[j]["id"])
                j += 1
            new_chapter = any(t in chapters for t in turn)
            if size >= self.CHUNK_TOKENS or (new_chapter and size >= self.CHUNK_TOKENS / 3):
                out.append((a, i))
                a, size = i + 1, 0
        if a <= end:
            out.append((a, end))
        return out

    def flush(self, chat_id, path, toolbox, a, b, on_delta=None):
        narr = self.prompt.narration_lang(self.prompt.ctx(chat_id))
        msgs = self.prompt.side(chat_id, FLUSH_INSTRUCTION.format(a=a, b=b) + (f"\nTulis isi catatan dalam bahasa {narr}." if narr else ""),
                                path=path)
        c = self.prompt.ctx(chat_id)
        head = path[-1]["id"] if path else None
        allowed = {"canon_set", "memory_save", "memory_update", "memory_forget", "status_update", "fact_save", "world_event",
                   "knowledge_add", "tell", "thread_open", "thread_close"}
        tools = toolbox.specs(c)  # the chat's full list: same prompt prefix as the turns (cache); allowed limits what runs
        for _ in range(4):
            acc = self.llm.chat(msgs, tools=tools, kwargs=self.prompt.kwargs(c), sampling={"temperature": 0.6},
                                max_tokens=8000, stop=self.cancel, on_delta=on_delta)
            if self.cancel.is_set():
                return
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
                res, _, _ = toolbox.call(chat_id, head, cl["name"], cl["arguments"], allowed=allowed)
                msgs.append({"role": "tool", "tool_call_id": cl["id"] or f"f{i}", "content": res})

    def summarize(self, chat_id, path, a, b, budget, think, tools, on_delta=None):
        """The summary text; None when cancelled (a cut-off summary must never be stored as complete)."""
        anchors = "\n".join(f"{i + 1}: {path[i]['content'][:80].replace(chr(10), ' ')}"
                            for i in range(a, b + 1) if path[i]["role"] == "user")
        instr = SUMMARY_INSTRUCTION.format(a=a + 1, b=b + 1, words=int(budget * 0.55), anchors=anchors[:6000])
        narr = self.prompt.narration_lang(self.prompt.ctx(chat_id))
        if narr:
            instr += f"\nTulis ringkasan dalam bahasa {narr}; kutipan dialog tetap persis dalam bahasa aslinya."
        c = self.prompt.ctx(chat_id)
        maxc = self.llm.max_context() or 0
        # Same prefix as the chat (cache hits). If history + the answer would not fit, only the piece goes in.
        msgs = self.prompt.side(chat_id, instr, path=path[:b + 1])
        want = budget + think
        used = self.llm.estimate(msgs)
        if maxc and used + want > maxc - 1024:
            msgs = self.prompt.side(chat_id, instr, path=path[a:b + 1])
            used = self.llm.estimate(msgs)
        max_tokens = max(2048, min(want, maxc - used - 1024)) if maxc else want
        # Long thinking can eat the whole budget and leave no summary: think less here, and if the answer is
        # still empty, write it again with thinking off.
        kw = self.prompt.side_kwargs(c)
        text, acc = "", None
        for attempt in range(2):
            acc = self.llm.complete(msgs, kwargs=kw, sampling={"temperature": 0.6, "top_p": 0.95},
                                    max_tokens=max_tokens, tools=tools, stop=self.cancel, on_delta=on_delta)
            if acc["finish"] == "stopped" or self.cancel.is_set():
                return None
            text = (acc["content"] or "").strip()
            if text:
                break
            kw = self.prompt.side_kwargs(c, retry=True)
        if not text:
            self.last_error = (f"empty answer (finish={acc['finish']}, thinking {len(acc['reasoning'])} characters, "
                               f"max_tokens {max_tokens}, prompt ≈{used} tokens)")
        if text and acc["finish"] == "length":
            text += "\n\n(Ringkasan ini terpotong karena batas token; detail akhir potongan ada di summary_read/history_read.)"
        return text

    @staticmethod
    def core_of(text):
        m = re.search(r"##\s*Inti\s*\n(.*?)(?=\n##\s|\Z)", text, re.S)
        return m.group(1).strip()[:2000] if m else ""

    def entity_check(self, chat_id, msgs, summary):
        """Capitalized names that recur in the chunk but appear neither in the summary nor in the story book."""
        c = self.prompt.ctx(chat_id)
        canon = self.prompt.stories.canon_text(c["story"]["id"], visible=self.store.visible_ids(chat_id), chat_id=chat_id) if c["story"] else ""
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
        label = f"Condensing {len(old)} old summaries into one era…"
        phase(label)
        instr = ERA_INSTRUCTION.format(texts="\n\n".join(s["text"] for s in old))
        msgs = self.prompt.side(chat_id, instr)
        c = self.prompt.ctx(chat_id)
        limit = min(32768, maxc // 16)
        if self.llm.estimate(msgs) + limit + 12000 > maxc - 1024:
            msgs = self.prompt.side(chat_id, instr, path=[])  # the summaries alone, without the chat history
        kw = self.prompt.side_kwargs(c)
        acc = self.llm.complete(msgs, kwargs=kw, sampling={"temperature": 0.6},
                                max_tokens=max(2048, min(limit + 12000, maxc - self.llm.estimate(msgs) - 1024)),
                                tools=tools, stop=self.cancel, on_delta=self.progress(phase, label, limit))
        text = (acc["content"] or "").strip()
        if not text or acc["finish"] == "stopped" or self.cancel.is_set():
            return
        self.store.x("INSERT INTO summaries (chat_id, node_id, from_id, level, text, core, created) VALUES (?, ?, ?, 'era', ?, ?, ?)",
                     (chat_id, old[-1]["node_id"], old[0]["from_id"], f"[Era]\n{text}", self.core_of(text), time.time()))
        # Condensed chunks leave the prompt but stay readable with summary_read.
        self.store.x(f"UPDATE summaries SET level = 'chunk_old' WHERE id IN ({','.join(str(s['id']) for s in old)})")
