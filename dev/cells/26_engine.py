CHOICES_INSTRUCTION = """Buat pilihan aksi untuk pemain berdasarkan situasi di akhir jawaban terakhir. Jawab HANYA JSON:
{{"problems": [{{"question": "...", "options": ["...", "..."]}}]}}
Aturan: {np} masalah, tiap masalah {no} pilihan. Setiap pertanyaan {ns} kalimat panjang yang menjelaskan situasi dan
ketegangannya dengan detail konkret. Setiap pilihan {ns} kalimat panjang berisi tindakan dan niat atau caranya, tanpa
membocorkan hasilnya. Kategori pilihan harus beragam: sosial, fisik/aksi, berisiko, memakai barang atau kemampuan, dan yang
memajukan agenda tokoh lain. Spesifik ke situasi saat ini; jangan generik. Bahasa: {lang}.
Jangan mengulang atau meniru pilihan-pilihan ini:
{recent}"""

TICK_INSTRUCTION = """Waktu dunia maju {span} (dari {t0} ke {t1}). {why}
Tentukan apa yang dilakukan tokoh lain di luar layar selama itu dan kejadian dunia yang masuk akal (0-4 kejadian,
sesuai kartu GM; peristiwa garis waktu yang jatuh tempo wajib terjadi). Untuk setiap kejadian panggil world_event dengan
known_to yang tepat ('player' hanya kalau pemain bisa mengetahuinya). Catat perubahan lokasi/rencana tokoh dengan
status_update. Jangan menulis narasi. Setelah selesai jawab "selesai"."""

FACTCHECK_CLAIMS = """Periksa jawaban terakhir. Daftarkan klaim fakta {kind} yang spesifik di dalamnya (tanggal, angka, nama
satuan, senjata, pangkat, tempat, prosedur), bukan hal fiksi cerita. Maksimal 6. Jawab HANYA JSON: {{"claims": ["..."]}}"""

FACTCHECK_VERIFY = """Klaim: "{claim}"
Sumber ({source}):
{text}

Apakah klaim itu benar menurut sumber? Jawab HANYA JSON:
{{"verdict": "benar" | "salah" | "tidak pasti", "correction": "koreksi singkat kalau salah", "fact": "fakta yang benar, satu kalimat"}}"""

LEARN_INSTRUCTION = """Jelaskan kalimat berikut untuk pelajar bahasa {lang}. Jawab HANYA JSON:
{{"translation": "...", "grammar": ["poin tata bahasa singkat", "..."], "vocab": [{{"term": "...", "translation": "...", "note": "..."}}]}}
Kalimat: {text}"""

RECALL_QUESTIONS = """Dari potongan percakapan berikut, buat {n} pertanyaan tentang detail spesifik (nama, angka, kejadian, ucapan)
beserta jawabannya. Jawab HANYA JSON: {{"qa": [{{"q": "...", "a": "..."}}]}}

{text}"""

RECALL_ANSWER = """Uji ingatan (jangan pakai tool, jawab dari yang kamu ingat saja). Jawab setiap pertanyaan singkat; kalau tidak
tahu tulis "tidak tahu". Jawab HANYA JSON: {{"answers": ["...", "..."]}}
{questions}"""


class Engine(EngineView):
    MAX_TOOL_ROUNDS = 12

    def __init__(self, emit=None):
        self.store, self.prompt, self.llm, self.tools = STORE, PROMPT, LLM_CLIENT, TOOLS
        self.compactor = Compactor(STORE, PROMPT, LLM_CLIENT, MEM)
        self.mem, self.world, self.cards, self.stories, self.servers = MEM, WORLD, CARDS, STORIES, SERVERS
        self.emit = emit or (lambda kind, payload=None: None)
        self.lock = threading.RLock()
        self.busy = False
        self.stop = threading.Event()
        self.bg_cancel = threading.Event()
        self.queue = []
        self.last_used = {}
        self.active_chat = 0
        self.last_activity = time.time()
        self.bg_busy = False
        self.fact_jobs = []
        self.backfilled = False
        self.idle_thread = threading.Thread(target=self._idle_loop, daemon=True)
        self.idle_thread.start()

    # ---------- job runner ----------

    def run(self, fn, *args, queue_text=None):
        """Run fn in a worker thread, one job at a time. A send while busy is queued."""
        with self.lock:
            if self.busy:
                if queue_text is not None:
                    self.queue.append((fn, args))
                    self.emit("toast", {"text": f"Masuk antrian ({len(self.queue)})."})
                    self.emit("queue", len(self.queue))
                else:
                    self.emit("toast", {"text": "Tunggu balasan selesai atau klik Stop dulu.", "kind": "warn"})
                return False
            self.busy = True
        self.bg_cancel.set()
        self.compactor.cancel.set()
        self.stop.clear()
        threading.Thread(target=self._job, args=(fn, args), daemon=True).start()
        return True

    def _job(self, fn, args):
        self.emit("busy", True)
        try:
            fn(*args)
        except Exception as e:
            self.emit("toast", {"text": f"{type(e).__name__}: {e}", "kind": "error"})
        finally:
            self.last_activity = time.time()
            nxt = None
            with self.lock:
                if self.queue and not self.stop.is_set():
                    nxt = self.queue.pop(0)
                else:
                    self.queue.clear()
                    self.busy = False
            self.emit("queue", len(self.queue))
            if nxt:
                self._job(*nxt)
            else:
                self.emit("busy", False)

    def stop_now(self):
        self.stop.set()
        self.compactor.cancel.set()
        self.bg_cancel.set()

    # ---------- chats and stories ----------

    def new_chat(self, kind="chat", title=None, story_id=None, settings=None):
        defaults = {"thinking": None, "length": None, "fact_mode": "latar", "group_mode": "narrator"}
        cid = self.store.new_chat(title or {"studio": "Studio", "rp": "Cerita baru", "group": "Grup baru"}.get(kind, "Chat baru"),
                                  kind, story_id, {**defaults, **(settings or {})})
        self.emit("chats")
        return cid

    def start_story(self, card_ids, title=None, greeting_index=0, from_chat=None):
        """New story + RP chat from cards, with the chosen opening as the first message."""
        sc = self.cards.get(card_ids.get("scenario")) if card_ids.get("scenario") else None
        chars = card_ids.get("character") or []
        first_char = self.cards.get(chars[0]) if chars else None
        title = title or (sc["name"] if sc else (first_char["name"] if first_char else "Cerita baru"))
        for role in ("style", "gm"):
            if not card_ids.get(role):
                row = self.store.one("SELECT id FROM cards WHERE type = ? ORDER BY id LIMIT 1", (role,))
                card_ids[role] = row["id"] if row else None
        sid = self.stories.create(title, card_ids)
        kind = "group" if len(chars) > 1 else "rp"
        chat_id = self.new_chat(kind, title, sid)
        self.store.chat_settings(chat_id, world_sync=time.time())
        opening = ""
        if sc and sc["data"].get("opening"):
            opening = sc["data"]["opening"]
        elif first_char:
            greet = first_char["data"].get("greetings") or []
            if greet:
                opening = greet[min(greeting_index, len(greet) - 1)]
        if opening:
            self.store.add_message(chat_id, None, "assistant", opening, meta={"opening": True})
        self.emit("chats")
        return chat_id

    def continue_in_new_chat(self, chat_id):
        """Same story, fresh chat: chronicle + last turns carried over, status replayed as the new base."""
        old = self.store.chat(chat_id)
        path = self.store.path(chat_id)
        ids = [m["id"] for m in path]
        st = self.world.state(chat_id, ids)
        new = self.new_chat(old["kind"], f"{old['title']} (lanjutan)", old.get("story_id"), old["settings"])
        for s in self.prompt.summaries_on_path(chat_id, ids):
            self.store.x("INSERT INTO summaries (chat_id, node_id, from_id, level, text, core, created) VALUES (?, 0, 0, ?, ?, ?, ?)",
                         (new, s["level"], s["text"], s["core"], time.time()))
        users = [i for i, m in enumerate(path) if m["role"] == "user" and not m["ooc"]]
        start = users[-3] if len(users) >= 3 else 0
        recap = []
        for m in path[start:]:
            if m["role"] in ("user", "assistant") and m["content"].strip():
                recap.append(("Pemain" if m["role"] == "user" else "Narator") + ": " + m["content"])
        intro = ("Lanjutan dari chat sebelumnya. Adegan terakhir:\n\n" + "\n\n".join(recap))[:60000]
        root = self.store.add_message(new, None, "assistant", intro, meta={"carry_over": True})
        # Ringkasan dari chat lama dipasang di node akar chat baru.
        self.store.x("UPDATE summaries SET node_id = ? WHERE chat_id = ? AND node_id = 0", (root, new))
        self.world.add_event(new, None, "world", "time", st["time"].strftime("%Y-%m-%d %H:%M"), "set", "lanjutan")
        for s in st["stats"]:
            self.world.add_event(new, None, "player", s["key"], s["value"], "set", "lanjutan")
        for subject, fields in st["status"].items():
            for k, v in fields.items():
                self.world.add_event(new, None, subject, k, v, "set", "lanjutan")
        self.emit("chats")
        return new

    # ---------- sending ----------

    def send(self, chat_id, text, files=None, kind=None):
        parsed = TXT.parse_input(text)
        if not chat_id or not self.store.chat(chat_id):
            chat_id = self.new_chat(kind or "chat", (text or "Chat baru")[:60])
            self.emit("select", chat_id)
        self.active_chat = chat_id
        if parsed["kind"] == "slash":
            return self.slash(chat_id, parsed["cmd"], parsed["arg"])
        m = re.match(r"^\s*ubah\s*:\s*(.+)$", parsed.get("text", ""), re.S | re.I)
        if parsed["kind"] == "ooc" and m and (self.store.chat(chat_id) or {}).get("kind") in ("rp", "group"):
            return self.slash(chat_id, "studio", m.group(1).strip())
        return self.run(self._send, chat_id, parsed, files or [], queue_text=text)

    def slash(self, chat_id, cmd, arg):
        head = (self.store.chat(chat_id) or {}).get("head_id")
        if cmd == "note":
            self.store.chat_settings(chat_id, note=arg)
            self.emit("toast", {"text": "Author's note disimpan." if arg else "Author's note dihapus."})
            self.emit("settings", chat_id)
        elif cmd == "reroll" and head:
            self.reroll(chat_id, head)
        elif cmd == "continue" and head:
            self.continue_msg(chat_id, head)
        elif cmd == "bab":
            if head:
                self.store.x("INSERT INTO chapters (chat_id, message_id, title, created) VALUES (?, ?, ?, ?)",
                             (chat_id, head, arg or "Bab baru", time.time()))
                self.emit("history", chat_id)
        elif cmd == "ingat":
            rows = self.mem.search(arg, self.mem.ctx_of(chat_id), limit=10, kinds=("fact", "summary_core"))
            self.emit("toast", {"text": "\n".join(f"#{r['id']} {r['text'][:160]}" for r in rows) or "Tidak ada memory yang cocok.",
                                "long": True})
        elif cmd == "impersonate":
            self.run(self._impersonate, chat_id, arg)
        elif cmd == "studio":
            self.run(self._studio_change, chat_id, arg)
        elif cmd == "cek" and head:
            self.run(self._fact_check, chat_id, head, True)
        return chat_id

    def _send(self, chat_id, parsed, files):
        blocks, media, notes = Files.process(files)
        text = parsed["text"]
        full = "\n\n".join([text] + blocks).strip()
        chat = self.store.chat(chat_id)
        meta = {"typed": text, "notes": notes,
                "attachments": [{"name": a["name"], "kind": a["kind"]} for a in media]}
        mention = re.match(r"^@(\S+)\s", text or "")
        if mention and chat["kind"] == "group":
            self.store.chat_settings(chat_id, speaker=mention.group(1))
        uid = self.store.add_message(chat_id, chat["head_id"], "user", full, meta=meta, ooc=parsed["kind"] == "ooc", media=media)
        self.emit("history", chat_id)
        extra = []
        if chat["kind"] in ("rp", "group") and parsed["kind"] != "ooc":
            extra += self._catch_up(chat_id, uid)
        pending = len(full) // 3 + 1500 * len(media)
        self._turn(chat_id, extra=extra, pending_estimate=pending)

    def _catch_up(self, chat_id, uid):
        """AFK: advance the world clock by the real time that passed (GM scale) and let the world act."""
        c = self.prompt.ctx(chat_id)
        gm = self.prompt.gm(c)
        try:
            scale = float(gm.get("afk_scale") or 0)
        except ValueError:
            scale = 0
        sync = c["settings"].get("world_sync") or time.time()
        minutes = int((time.time() - sync) / 60 * scale)
        self.store.chat_settings(chat_id, world_sync=time.time())
        if minutes < 30:
            return []
        minutes = min(minutes, 60 * 24 * 30)
        ids = self.store.path_ids(chat_id)
        t0 = self.world.state(chat_id, ids)["time"]
        self.world.advance(chat_id, uid, minutes, "AFK")
        self._tick(chat_id, t0, minutes, "Pemain sedang tidak ada (AFK).", head=uid)
        return [f"Pemain baru kembali setelah {World.fmt_span(minutes)} waktu dunia berlalu. Kejadian selama itu ada di atas."]

    # ---------- the turn ----------

    def _turn(self, chat_id, extra=None, pending_estimate=0, length_override=None):
        if not self.servers.ready():
            raise RuntimeError("Server model belum READY. Klik Start dan tunggu status READY.")
        c = self.prompt.ctx(chat_id)
        tools = self.tools.specs(c)
        live = {"active": True, "content": "", "reasoning": "", "tools": [], "phase": "", "chat_id": chat_id}
        self.emit("live", live)

        def phase(msg):
            live["phase"] = msg
            self.emit("live", live)

        used = self.compactor.maybe(chat_id, tools, self.tools, phase, last_used=self.last_used.get(chat_id, 0),
                                    pending_estimate=pending_estimate)
        if used:
            self.last_used[chat_id] = used
        phase("")
        t0 = time.time()
        totals = {"tokens": 0, "think_s": 0.0, "tools": 0, "gen_s": 0.0}
        usage, final_id, used_info = {}, None, {}
        extra = list(extra or [])
        if c["kind"] == "group":
            extra.append(self._group_note(chat_id, c))
        avoid = c["settings"].get("avoid") or []
        if avoid:
            extra.append("Hindari frasa yang sudah berulang ini: " + "; ".join(f'"{p}"' for p in avoid[:8]))
        error = None
        try:
            for _round in range(self.MAX_TOOL_ROUNDS):
                path = self.store.path(chat_id)
                msgs, used_round = self.prompt.build(chat_id, path, extra=extra if _round == 0 else None)
                if _round == 0:
                    used_info = used_round
                base_c, base_r = live["content"], live["reasoning"]
                state = {"mid": None, "saved": 0.0}

                def on_delta(acc, base_c=base_c, base_r=base_r, state=state):
                    live["content"] = base_c + ("\n\n" if base_c and acc["content"] else "") + acc["content"]
                    live["reasoning"] = base_r + ("\n\n" if base_r and acc["reasoning"] else "") + acc["reasoning"]
                    self.emit("live", live)
                    now = time.time()
                    if now - state["saved"] > 3:
                        state["saved"] = now
                        if state["mid"] is None:
                            head = self.store.chat(chat_id)["head_id"]
                            state["mid"] = self.store.add_message(chat_id, head, "assistant", acc["content"], acc["reasoning"],
                                                                  status="partial")
                        else:
                            self.store.update_message(state["mid"], content=acc["content"], reasoning=acc["reasoning"])

                acc = self.llm.chat(msgs, tools=tools, kwargs=self.prompt.kwargs(c), sampling=self.prompt.sampling(c),
                                    max_tokens=c["settings"].get("max_tokens") or self._default_max_tokens(c),
                                    on_delta=on_delta, stop=self.stop)
                usage = acc["usage"] or usage
                if acc["usage"]:
                    self.last_used[chat_id] = acc["usage"].get("total_tokens") or self.last_used.get(chat_id, 0)
                totals["tokens"] += (acc["usage"] or {}).get("completion_tokens") or 0
                start = acc["t_think"] or acc["t_answer"]
                if start:
                    totals["gen_s"] += time.time() - start
                if acc["t_think"]:
                    totals["think_s"] += (acc["t_answer"] or time.time()) - acc["t_think"]
                calls = [] if self.stop.is_set() else [
                    {"id": cl["id"] or f"call_{int(time.time())}_{i}", "type": "function",
                     "function": {"name": cl["name"], "arguments": cl["arguments"] or "{}"}}
                    for i, cl in sorted(acc["calls"].items())]
                content = TXT.dedupe_parens(acc["content"]) if c["kind"] in ("rp", "group") else acc["content"]
                status = "partial" if acc["finish"] in ("stopped", "length") and not calls else "final"
                if state["mid"] is None:
                    head = self.store.chat(chat_id)["head_id"]
                    if content or acc["reasoning"] or calls:
                        state["mid"] = self.store.add_message(chat_id, head, "assistant", content, acc["reasoning"],
                                                              calls or None, status=status)
                else:
                    self.store.update_message(state["mid"], content=content, reasoning=acc["reasoning"],
                                              tool_calls=calls or None, status=status)
                final_id = state["mid"] or final_id
                if not calls:
                    break
                for tc in calls:
                    if self.stop.is_set():
                        break
                    entry = {"name": tc["function"]["name"], "args": tc["function"]["arguments"], "result": "", "running": True}
                    live["tools"].append(entry)
                    self.emit("live", live)
                    res, failed, media = self.tools.call(chat_id, state["mid"], entry["name"], entry["args"])
                    entry.update(result=res[:4000], running=False, error=failed)
                    totals["tools"] += 1
                    self.emit("live", live)
                    self.store.add_message(chat_id, self.store.chat(chat_id)["head_id"], "tool", res, tool_call_id=tc["id"],
                                           meta={"error": failed}, media=media)
                    if self.last_used.get(chat_id):
                        self.last_used[chat_id] += len(res) // 3 + 1500 * len(media)
                if self.stop.is_set():
                    break
            else:
                error = f"Berhenti setelah {self.MAX_TOOL_ROUNDS} putaran tool."
        except urllib.error.HTTPError as e:
            error = f"Server menolak request (HTTP {e.code}): {e.read().decode('utf-8', 'replace')[:400]}"
        except Exception as e:
            error = f"{type(e).__name__}: {e}"
        stats = {"tokens": totals["tokens"], "tps": totals["tokens"] / totals["gen_s"] if totals["tokens"] and totals["gen_s"] else None,
                 "think_s": totals["think_s"] or None, "tools": totals["tools"] or None, "total_s": time.time() - t0,
                 "stopped": self.stop.is_set(), "model": self.servers.state.get("preset"), "ctx": self.servers.state.get("ctx"),
                 "sampling": self.prompt.sampling(c), "thinking": self.prompt.kwargs(c), "mtp": self.servers.state.get("mtp")}
        live["active"] = False
        self.emit("live", {})
        if final_id is None:
            head = self.store.chat(chat_id)["head_id"]
            final_id = self.store.add_message(chat_id, head, "assistant", "", meta={"stats": stats, "error": error})
        else:
            m = self.store.msg(final_id)
            meta = {**m["meta"], "stats": stats}
            if error:
                meta["error"] = error
            self.store.update_message(final_id, meta=meta)
        if not error and not self.stop.is_set() and c["kind"] in ("rp", "group"):
            self._after_turn(chat_id, final_id, c, used_info)
        self.emit("history", chat_id)
        self.emit("panels", chat_id)
        self.emit("ctx", {"used": self.last_used.get(chat_id, 0), "max": self.llm.max_context()})

    def _default_max_tokens(self, c):
        length = c["settings"].get("length") or "panjang"
        content = {"pendek": 2000, "sedang": 4000}.get(length, 8000)
        thinking = self.prompt.kwargs(c).get("enable_thinking", True)
        return content + (16000 if thinking else 0)

    def _group_note(self, chat_id, c):
        speaker = c["settings"].get("speaker")
        if speaker:
            self.store.chat_settings(chat_id, speaker=None)
            return f"Giliran ini yang bereaksi/bicara: {speaker}. Tandai bagian tiap tokoh dengan **Nama** di awal paragraf."
        if c["settings"].get("group_mode") == "single":
            names = [ch["name"] for ch in c["cards"]["character"]]
            return (f"Mode satu tokoh: tulis balasan hanya sebagai SATU tokoh yang paling wajar bereaksi sekarang "
                    f"({', '.join(names)}), awali dengan **Nama**.")
        return ("Mode narator GM: beberapa tokoh boleh bereaksi dalam satu balasan sesuai agenda dan pengetahuan masing-masing. "
                "Tandai bagian tiap tokoh dengan **Nama** di awal paragraf.")

    # ---------- after the turn ----------

    def _after_turn(self, chat_id, mid, c, used):
        m = self.store.msg(mid)
        if not m or not m["content"].strip():
            return
        path = self.store.path(chat_id)
        ids = [x["id"] for x in path]
        # world: mark events the player has now been told about, fire due timeline entries
        if used.get("events"):
            self.world.mark_shown(used["events"])
        st = self.world.state(chat_id, ids)
        for e in used.get("timeline") or []:
            self.world.add_world_event(chat_id, mid, e["at"], f"{e['title']}. {e['text']}", ["player"], True, f"timeline:{e['id']}")
        flags = []
        # length: continue once if clearly short
        tgt = used.get("length")
        if tgt:
            paras, sents = TXT.shape(m["content"])
            if paras < tgt["paragraphs"] - 1 and not self.stop.is_set():
                add = tgt["paragraphs"] - paras
                self.emit("live", {"active": True, "content": m["content"], "phase": "Menambah paragraf…", "reasoning": "",
                                   "tools": [], "chat_id": chat_id})
                instr = (f"Lanjutkan narasi tepat dari akhir jawaban terakhir dengan {add} paragraf lagi "
                         f"({tgt['sent_lo']}-{tgt['sent_hi']} kalimat per paragraf). Jangan mengulang isi yang sudah ada, jangan "
                         f"menulis ucapan atau keputusan pemain, jangan menulis pengantar. Langsung paragraf berikutnya.")
                acc = self.llm.complete(self.prompt.side(chat_id, instr), kwargs=self.prompt.kwargs(c),
                                        sampling=self.prompt.sampling(c), max_tokens=self._default_max_tokens(c),
                                        tools=self.tools.specs(c), stop=self.stop)
                more = TXT.dedupe_parens((acc["content"] or "").strip())
                if more:
                    self.store.update_message(mid, content=m["content"].rstrip() + "\n\n" + more)
                    m = self.store.msg(mid)
                self.emit("live", {})
            paras, sents = TXT.shape(m["content"])
            m["meta"]["shape"] = {"target": tgt, "paragraphs": paras, "sentences": sents}
        # quality checks
        prev = [x["content"] for x in path if x["role"] == "assistant" and x["id"] != mid and x["content"]][-4:]
        rep = TXT.repeated_phrases(m["content"], prev)
        self.store.chat_settings(chat_id, avoid=rep)
        if rep:
            flags.append({"kind": "repeat", "text": "Frasa berulang: " + "; ".join(rep[:4])})
        banned = TXT.banned_hits(m["content"], self.prompt.style(c).get("banned") or [])
        if banned:
            flags.append({"kind": "banned", "text": "Frasa terlarang: " + ", ".join(banned)})
        lang = (self.prompt.style(c).get("narration_lang") or "Indonesia").lower()
        expected = "id" if lang.startswith(("indo", "id")) else "de" if lang.startswith(("jer", "deu", "ger", "de")) else "en"
        dom, shares = TXT.narration_language(m["content"], expected)
        if dom != expected and shares.get(dom, 0) > 0.5:
            flags.append({"kind": "language", "text": f"Narasi tampaknya berbahasa {dom}, bukan {expected}."})
        if TXT.split_dialogue(m["content"]) >= 3:
            flags.append({"kind": "split", "text": "Dialog tampak terpecah per kata dengan terjemahan pendek."})
        persona = (c["cards"].get("persona") or {}).get("name", "")
        acts = TXT.acts_for_user(m["content"], persona)
        if acts:
            flags.append({"kind": "acts_for_user", "text": "Narasi tampaknya memutuskan ucapan/tindakan pemain: "
                                                           + "; ".join(acts[:3])})
        m["meta"]["flags"] = flags
        self.store.update_message(mid, meta=m["meta"])
        # choices (game format)
        gm = self.prompt.gm(c)
        if gm.get("format") == "game" and gm.get("choices", "kadang") != "tidak" and not self.stop.is_set():
            if gm.get("choices") == "selalu" or random.random() < 0.6:
                self.emit("live", {"active": True, "content": m["content"], "phase": "Membuat pilihan…", "reasoning": "",
                                   "tools": [], "chat_id": chat_id})
                try:
                    choices = self._choices(chat_id, c, path)
                    if choices:
                        m = self.store.msg(mid)
                        m["meta"]["choices"] = choices
                        self.store.update_message(mid, meta=m["meta"])
                except Exception as e:
                    self.emit("toast", {"text": f"Pilihan gagal dibuat: {e}", "kind": "warn"})
                self.emit("live", {})
        # fact check
        mode = c["settings"].get("fact_mode") or "latar"
        if mode == "ketat":
            self._fact_check(chat_id, mid, False)
        elif mode == "latar":
            self.fact_jobs.append((chat_id, mid))

    @staticmethod
    def _range(text, default):
        m = re.match(r"\s*(\d+)\s*-\s*(\d+)", str(text or ""))
        return (int(m.group(1)), int(m.group(2))) if m else default

    def _json(self, text):
        t = (text or "").strip()
        t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
        m = re.search(r"\{.*\}", t, re.S)
        return json.loads(m.group(0)) if m else None

    def _choices(self, chat_id, c, path):
        gm = self.prompt.gm(c)
        np_ = self._range(gm.get("choice_problems"), (1, 3))
        no = self._range(gm.get("choice_options"), (3, 5))
        ns = self._range(gm.get("choice_sentences"), (1, 2))
        recent = []
        for x in path[::-1]:
            for p in (x["meta"].get("choices") or {}).get("problems", []):
                recent += p.get("options", [])
            if len(recent) >= 25:
                break
        lang = self.prompt.style(c).get("narration_lang") or "Indonesia"
        instr = CHOICES_INSTRUCTION.format(np=f"{np_[0]}-{np_[1]}", no=f"{no[0]}-{no[1]}", ns=f"{ns[0]}-{ns[1]}", lang=lang,
                                           recent="\n".join(f"- {o}" for o in recent[:25]) or "-")
        for attempt in range(2):
            acc = self.llm.complete(self.prompt.side(chat_id, instr), kwargs=self.prompt.kwargs(c),
                                    sampling={**self.prompt.sampling(c), "temperature": 1.1}, max_tokens=12000,
                                    tools=self.tools.specs(c), stop=self.stop)
            data = self._json(acc["content"])
            if not data:
                continue
            problems = []
            for p in data.get("problems", [])[:np_[1]]:
                q = str(p.get("question", "")).strip()
                opts = []
                for o in p.get("options", []):
                    o = str(o).strip()
                    n = len(TXT.sentences(o))
                    if not o or n > ns[1] + 1:
                        continue
                    if any(TXT.jaccard(o, r) > 0.5 for r in recent + opts):
                        continue
                    opts.append(o)
                if q and len(opts) >= 2:
                    problems.append({"question": q, "options": opts[:no[1]]})
            if problems:
                return {"problems": problems}
        return None

    # ---------- fact check ----------

    def _fact_check(self, chat_id, mid, announce):
        c = self.prompt.ctx(chat_id)
        world = c["cards"].get("world")
        real = not world or (world["data"].get("realworld") or "ya") == "ya"
        m = self.store.msg(mid)
        if not m or not m["content"].strip():
            return
        path = self.store.path(chat_id, head=mid)
        acc = self.llm.complete(self.prompt.side(chat_id, FACTCHECK_CLAIMS.format(kind="dunia nyata" if real else "tentang dunia cerita"),
                                                 path=path),
                                kwargs=self.prompt.kwargs(c), sampling={"temperature": 0.3}, max_tokens=6000,
                                tools=self.tools.specs(c), stop=self.bg_cancel if not announce else self.stop)
        data = self._json(acc["content"]) or {}
        warnings = []
        for claim in (data.get("claims") or [])[:6]:
            if self.bg_cancel.is_set() and not announce:
                return
            known = self.mem.fact_lookup(claim, world["id"] if world else None, limit=3)
            if any(TXT.jaccard(claim, k["claim"]) >= 0.5 for k in known):
                continue
            if real:
                found = json.loads(WEB.wiki_search(claim, [x.strip() for x in ((world or {}).get("data", {}).get("wiki_lang") or "en").split(",")], 3))
                if not found.get("results"):
                    continue
                top = found["results"][0]
                page = json.loads(WEB.wiki_read(top["title"], top["lang"], 8000))
                source, text = page.get("url", top["url"]), page.get("text", "")
            else:
                source = "lore dan buku cerita"
                text = self.stories.canon_text(c["story"]["id"]) if c["story"] else ""
                text += "\n" + "\n".join(f"{e['title']}: {e['text']}" for e in self.mem.lore_triggered(c["mem"]["card_ids"], claim))
            if not text.strip():
                continue
            v = self.llm.complete(self.prompt.side(chat_id, FACTCHECK_VERIFY.format(claim=claim, source=source, text=text[:8000]),
                                                   path=path),
                                  kwargs=self.prompt.kwargs(c), sampling={"temperature": 0.2}, max_tokens=4000,
                                  tools=self.tools.specs(c))
            verdict = self._json(v["content"]) or {}
            if verdict.get("verdict") == "salah":
                warnings.append({"claim": claim, "correction": verdict.get("correction", ""), "source": source})
            if real and verdict.get("fact") and verdict.get("verdict") in ("benar", "salah"):
                self.mem.fact_save(verdict["fact"], source, "", world["id"] if world else None, 0.8)
        m = self.store.msg(mid)
        m["meta"]["fact_warnings"] = warnings
        m["meta"]["fact_checked"] = True
        self.store.update_message(mid, meta=m["meta"])
        self.emit("history", chat_id)
        if announce:
            self.emit("toast", {"text": f"Cek fakta: {len(warnings)} klaim salah." if warnings else "Cek fakta: tidak ada yang salah."})

    # ---------- tree operations ----------

    def _turn_user(self, chat_id, mid):
        """The user message a bot message answers."""
        cur = self.store.msg(mid)
        while cur and cur["role"] != "user":
            cur = self.store.msg(cur["parent_id"]) if cur["parent_id"] else None
        return cur

    def reroll(self, chat_id, mid):
        u = self._turn_user(chat_id, mid)
        if u is None:
            self.emit("toast", {"text": "Tidak ada pesan pengguna untuk dijawab ulang.", "kind": "warn"})
            return
        self.store.set_head(chat_id, u["id"])
        self.emit("history", chat_id)
        self.run(self._turn, chat_id)

    def swipe(self, chat_id, mid, direction):
        m = self.store.msg(mid)
        if m["role"] == "user":
            sib = [k for k in self.store.children(chat_id, m["parent_id"]) if self.store.msg(k)["role"] == "user"]
            cur = mid
        else:
            u = self._turn_user(chat_id, mid)
            parent = u["id"] if u else None
            sib = [k for k in self.store.children(chat_id, parent) if self.store.msg(k)["role"] == "assistant"]
            path_ids = set(self.store.path_ids(chat_id))
            cur = next((k for k in sib if k in path_ids), sib[0] if sib else mid)
        if len(sib) < 2:
            if m["role"] != "user" and direction > 0:
                self.reroll(chat_id, mid)
            return
        i = (sib.index(cur) + direction) % len(sib)
        self.store.set_head(chat_id, self.store.deepest(chat_id, sib[i]))
        self.emit("history", chat_id)
        self.emit("panels", chat_id)

    def edit(self, chat_id, mid, text):
        m = self.store.msg(mid)
        if m["role"] == "user":
            meta = {**m["meta"], "typed": text}
            nid = self.store.add_message(chat_id, m["parent_id"], "user", text, meta=meta, ooc=bool(m["ooc"]))
            self.emit("history", chat_id)
            self.run(self._turn, chat_id)
        else:
            nid = self.store.add_message(chat_id, m["parent_id"], m["role"], text, m["reasoning"], meta={"edited": True})
            self.emit("history", chat_id)
        return nid

    def continue_msg(self, chat_id, mid):
        self.run(self._continue, chat_id, mid)

    def _continue(self, chat_id, mid):
        c = self.prompt.ctx(chat_id)
        m = self.store.msg(mid)
        self.store.set_head(chat_id, mid)
        live = {"active": True, "content": m["content"], "reasoning": "", "tools": [], "phase": "Melanjutkan…", "chat_id": chat_id}
        self.emit("live", live)
        instr = ("Lanjutkan jawaban terakhirmu tepat dari kata terakhir, tanpa mengulang dan tanpa pengantar. "
                 "Jangan menulis ucapan atau keputusan pemain.")
        base = m["content"].rstrip()

        def on_delta(acc):
            live["content"] = base + ("\n\n" if acc["content"][:1] == "\n" else " ") + acc["content"]
            live["phase"] = ""
            self.emit("live", live)
        acc = self.llm.chat(self.prompt.side(chat_id, instr, path=self.store.path(chat_id, head=mid)), tools=self.tools.specs(c),
                            kwargs=self.prompt.kwargs(c), sampling=self.prompt.sampling(c),
                            max_tokens=self._default_max_tokens(c), on_delta=on_delta, stop=self.stop, tool_choice="none")
        more = (acc["content"] or "").strip()
        if more:
            joiner = "\n\n" if acc["content"].startswith("\n") or base.endswith((".", "!", "?", "”", '"', "»")) else " "
            self.store.update_message(mid, content=TXT.dedupe_parens(base + joiner + more), status="final")
        self.emit("live", {})
        self.emit("history", chat_id)

    def delete_msg(self, chat_id, mid):
        m = self.store.msg(mid)
        if not m:
            return
        sub, frontier = [], [mid]
        while frontier:
            cur = frontier.pop()
            sub.append(cur)
            frontier += self.store.children(chat_id, cur)
        with self.store.lock:
            for i in range(0, len(sub), 500):
                part = sub[i:i + 500]
                marks = ",".join("?" * len(part))
                for t, col in (("attachments", "message_id"), ("status_events", "message_id"), ("world_events", "message_id"),
                               ("dice_log", "message_id"), ("chapters", "message_id"), ("summaries", "node_id"), ("messages", "id")):
                    self.store.conn.execute(f"DELETE FROM {t} WHERE {col} IN ({marks})", part)
            self.store.conn.commit()
        head = (self.store.chat(chat_id) or {}).get("head_id")
        if head in sub or head is None:
            self.store.set_head(chat_id, m["parent_id"])
        self.store._changed()
        self.emit("history", chat_id)
        self.emit("panels", chat_id)

    def branch_here(self, chat_id, mid):
        self.store.set_head(chat_id, mid)
        self.emit("history", chat_id)
        self.emit("toast", {"text": "Cabang baru: pesan berikutnya bercabang dari sini."})

    def pin(self, mid, on):
        self.store.update_message(mid, pinned=int(bool(on)))

    def choose(self, chat_id, text):
        return self.send(chat_id, text)

    # ---------- time skip and world tick ----------

    def time_skip(self, chat_id, label):
        minutes = World.minutes(label)
        if minutes <= 0:
            return
        self.run(self._time_skip, chat_id, label, minutes, queue_text=label)

    def _time_skip(self, chat_id, label, minutes):
        chat = self.store.chat(chat_id)
        uid = self.store.add_message(chat_id, chat["head_id"], "user", f"(Lompat waktu: {label})", meta={"time_skip": label,
                                                                                                         "typed": f"Lompat waktu {label}"})
        ids = self.store.path_ids(chat_id)
        t0 = self.world.state(chat_id, ids)["time"]
        self.world.advance(chat_id, uid, minutes, f"lompat {label}")
        self.emit("history", chat_id)
        self._tick(chat_id, t0, minutes, f"Pemain melompati waktu {label} dan menjalani rutinitas yang wajar.", head=uid)
        self._turn(chat_id, extra=[f"Pemain melompati waktu {label}. Ceritakan transisi singkat (1-3 paragraf): apa yang wajar "
                                   f"dilakukan pemain selama itu dan apa yang berubah, lalu berhenti di situasi baru."])

    def _tick(self, chat_id, t0, minutes, why, head=None, stop=None):
        c = self.prompt.ctx(chat_id)
        allowed = {"world_event", "status_update", "roll"}
        tools = [t for t in self.tools.specs(c) if t["function"]["name"] in allowed]
        t1 = t0 + timedelta(minutes=minutes)
        instr = TICK_INSTRUCTION.format(span=World.fmt_span(minutes), t0=World.fmt_time(t0), t1=World.fmt_time(t1), why=why)
        msgs = self.prompt.side(chat_id, instr)
        head = head or self.store.chat(chat_id)["head_id"]
        for _ in range(3):
            acc = self.llm.chat(msgs, tools=tools, kwargs=self.prompt.kwargs(c), sampling=self.prompt.sampling(c),
                                max_tokens=12000, stop=stop or self.stop)
            calls = [v for _, v in sorted(acc["calls"].items())]
            if not calls or (stop and stop.is_set()):
                break
            msgs.append({"role": "assistant", "content": acc["content"], "tool_calls": [
                {"id": cl["id"] or f"t{i}", "type": "function", "function": {"name": cl["name"], "arguments": cl["arguments"] or "{}"}}
                for i, cl in enumerate(calls)]})
            for i, cl in enumerate(calls):
                res, _, _ = self.tools.call(chat_id, head, cl["name"], cl["arguments"])
                msgs.append({"role": "tool", "tool_call_id": cl["id"] or f"t{i}", "content": res})

    def _idle_loop(self):
        while True:
            time.sleep(30)
            try:
                self._idle_once()
            except Exception:
                pass

    def _idle_once(self):
        if self.busy or self.bg_busy or not self.servers.ready():
            return
        if not self.backfilled and EMB.ready():
            self.backfilled = True
            threading.Thread(target=EMB.backfill, daemon=True).start()
        self.bg_cancel.clear()
        self.bg_busy = True
        try:
            while self.fact_jobs and not self.busy:
                chat_id, mid = self.fact_jobs.pop(0)
                self._fact_check(chat_id, mid, False)
            chat_id = self.active_chat
            chat = self.store.chat(chat_id) if chat_id else None
            if not chat:
                return
            idle = time.time() - self.last_activity
            maxc = self.llm.max_context()
            used = self.last_used.get(chat_id, 0)
            if maxc and used > 0.8 * maxc and idle > 60 and not self.busy:
                self.emit("status", "Compaction saat diam…")
                c = self.prompt.ctx(chat_id)
                self.last_used[chat_id] = self.compactor.maybe(chat_id, self.tools.specs(c), self.tools,
                                                               lambda m: self.emit("status", m), force=False, threshold=0.8)
                self.emit("status", "")
                self.emit("history", chat_id)
            if chat["kind"] in ("rp", "group"):
                c = self.prompt.ctx(chat_id)
                gm = self.prompt.gm(c)
                try:
                    every, scale = float(gm.get("tick_minutes") or 0), float(gm.get("afk_scale") or 0)
                except ValueError:
                    every, scale = 0, 0
                sync = c["settings"].get("world_sync") or time.time()
                if every and scale and idle > every * 60 and time.time() - sync > every * 60 and not self.busy:
                    minutes = int((time.time() - sync) / 60 * scale)
                    ids = self.store.path_ids(chat_id)
                    head = chat["head_id"]
                    t0 = self.world.state(chat_id, ids)["time"]
                    self.world.advance(chat_id, head, minutes, "AFK")
                    self.store.chat_settings(chat_id, world_sync=time.time())
                    self.emit("status", "Dunia berjalan…")
                    self._tick(chat_id, t0, minutes, "Pemain sedang tidak ada (AFK).", head=head, stop=self.bg_cancel)
                    self.emit("status", "")
                    self.emit("panels", chat_id)
        finally:
            self.bg_busy = False

    # ---------- side features ----------

    def _impersonate(self, chat_id, hint):
        c = self.prompt.ctx(chat_id)
        persona = (c["cards"].get("persona") or {}).get("name") or "pemain"
        instr = (f"Tulis draf pesan berikutnya untuk pemain ({persona}) dengan gaya yang sama seperti pesan-pesan pemain sebelumnya. "
                 f"Satu sampai tiga kalimat, sudut pandang pemain, tanpa narasi tokoh lain. {('Arah: ' + hint) if hint else ''} "
                 f"Tulis drafnya saja.")
        acc = self.llm.complete(self.prompt.side(chat_id, instr), kwargs=self.prompt.kwargs(c), sampling=self.prompt.sampling(c),
                                max_tokens=6000, tools=self.tools.specs(c), stop=self.stop)
        self.emit("compose", (acc["content"] or "").strip())

    def _studio_change(self, chat_id, request):
        """'/studio ...' or '((ubah: ...))' during RP: the model edits cards or the story book through tools."""
        c = self.prompt.ctx(chat_id)
        allowed = {"canon_set", "status_update", "memory_save", "memory_update"}
        tools = [t for t in self.tools.specs(c) if t["function"]["name"] in allowed]
        msgs = self.prompt.side(chat_id, f"Permintaan perubahan dari pemain (di luar cerita): {request}\n"
                                         f"Terapkan dengan canon_set / status_update / memory_save. Jawab singkat apa yang diubah.")
        head = self.store.chat(chat_id)["head_id"]
        for _ in range(3):
            acc = self.llm.chat(msgs, tools=tools, kwargs=self.prompt.kwargs(c), sampling=self.prompt.sampling(c), max_tokens=8000,
                                stop=self.stop)
            calls = [v for _, v in sorted(acc["calls"].items())]
            if not calls:
                self.emit("toast", {"text": (acc["content"] or "Selesai.").strip()[:600], "long": True})
                break
            msgs.append({"role": "assistant", "content": acc["content"], "tool_calls": [
                {"id": cl["id"] or f"s{i}", "type": "function", "function": {"name": cl["name"], "arguments": cl["arguments"] or "{}"}}
                for i, cl in enumerate(calls)]})
            for i, cl in enumerate(calls):
                res, _, _ = self.tools.call(chat_id, head, cl["name"], cl["arguments"])
                msgs.append({"role": "tool", "tool_call_id": cl["id"] or f"s{i}", "content": res})
        self.emit("panels", chat_id)

    def learn(self, chat_id, text):
        self.run(self._learn, chat_id, text)

    def _learn(self, chat_id, text):
        c = self.prompt.ctx(chat_id)
        lang = self.prompt.style(c).get("target_lang") or "asing"
        acc = self.llm.complete(self.prompt.side(chat_id, LEARN_INSTRUCTION.format(lang=lang, text=text)),
                                kwargs=self.prompt.kwargs(c), sampling={"temperature": 0.3}, max_tokens=6000,
                                tools=self.tools.specs(c), stop=self.stop)
        data = self._json(acc["content"]) or {"translation": acc["content"]}
        self.emit("learn", {"text": text, "lang": lang, **data})

    def vocab_add(self, term, translation="", note="", example="", lang=""):
        now = time.time()
        if self.store.one("SELECT id FROM vocab WHERE lower(term) = lower(?)", (term,)):
            return False
        self.store.x("INSERT INTO vocab (term, lang, translation, note, example, due, created) VALUES (?, ?, ?, ?, ?, ?, ?)",
                     (term, lang, translation, note, example, now, now))
        return True

    def vocab_due(self, limit=20):
        return self.store.q("SELECT * FROM vocab WHERE due <= ? ORDER BY due LIMIT ?", (time.time(), limit))

    def vocab_review(self, vid, grade):
        """SM-2 style: grade 0 (lupa) .. 3 (mudah)."""
        v = self.store.one("SELECT * FROM vocab WHERE id = ?", (vid,))
        if not v:
            return
        ease = max(1.3, v["ease"] + (0.1 - (3 - grade) * (0.08 + (3 - grade) * 0.02)))
        if grade == 0:
            interval, reps = 0.0, 0
        else:
            reps = v["reps"] + 1
            interval = 1.0 if reps == 1 else 3.0 if reps == 2 else v["interval"] * ease
        self.store.x("UPDATE vocab SET ease = ?, interval = ?, reps = ?, due = ? WHERE id = ?",
                     (ease, interval, reps, time.time() + interval * 86400 + (600 if grade == 0 else 0), vid))

    def recall_test(self, chat_id, n=5):
        self.run(self._recall_test, chat_id, n)

    def _recall_test(self, chat_id, n):
        c = self.prompt.ctx(chat_id)
        path = self.store.path(chat_id)
        sums = self.prompt.summaries_on_path(chat_id, [m["id"] for m in path])
        cut = max(([m["id"] for m in path].index(s["node_id"]) for s in sums if s["level"] == "chunk"), default=len(path) // 2)
        early = [m for m in path[:cut + 1] if m["role"] in ("user", "assistant") and len(m["content"]) > 200]
        if len(early) < 3:
            self.emit("recall", {"error": "Belum cukup riwayat lama untuk diuji."})
            return
        sample = random.sample(early, min(len(early), 6))
        text = "\n\n".join(f"[{m['role']}] {m['content'][:2500]}" for m in sample)
        qa = self._json(self.llm.complete(self.prompt.side(chat_id, RECALL_QUESTIONS.format(n=n, text=text)),
                                          kwargs=self.prompt.kwargs(c), sampling={"temperature": 0.4}, max_tokens=8000,
                                          tools=self.tools.specs(c))["content"]) or {}
        items = (qa.get("qa") or [])[:n]
        if not items:
            self.emit("recall", {"error": "Gagal membuat pertanyaan."})
            return
        ans = self._json(self.llm.complete(self.prompt.side(chat_id, RECALL_ANSWER.format(
            questions="\n".join(f"{i + 1}. {x['q']}" for i, x in enumerate(items)))),
            kwargs=self.prompt.kwargs(c), sampling={"temperature": 0.2}, max_tokens=8000, tools=self.tools.specs(c))["content"]) or {}
        answers = ans.get("answers") or []
        report = []
        for i, x in enumerate(items):
            got = answers[i] if i < len(answers) else ""
            score = TXT.jaccard(got, x["a"])
            ok = score >= 0.35 or (x["a"].strip().lower() in got.lower() and len(x["a"]) > 2)
            report.append({"q": x["q"], "expected": x["a"], "got": got, "ok": ok})
        self.emit("recall", {"items": report, "score": sum(r["ok"] for r in report), "total": len(report)})

    def switch_model(self, preset, ctx, mtp=True, embed=True):
        def job():
            def log(title, text, code):
                self.emit("status", f"{title}: {'selesai' if code == 0 else 'gagal' if code else 'jalan…'}")
            try:
                SERVERS.start(preset, ctx, mtp=mtp, embed=embed, log=log)
                self.emit("toast", {"text": f"{preset} dimulai. Tunggu READY di bar atas."})
            except Exception as e:
                self.emit("toast", {"text": f"Ganti model gagal: {e}", "kind": "error"})
            finally:
                self.emit("status", "")
                self.emit("model", None)
        if self.busy:
            self.emit("toast", {"text": "Tunggu balasan selesai dulu.", "kind": "warn"})
            return
        threading.Thread(target=job, daemon=True).start()
