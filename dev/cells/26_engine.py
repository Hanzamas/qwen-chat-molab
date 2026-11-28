FAME_SUGGEST = """Tentukan pamor tiap tokoh di bawah di lingkungan ceritanya (misalnya kampus): seberapa dikenal orang banyak.
Tingkat: "bintang" (semua orang kenal; paling banyak 5 orang dari {n} tokoh cerita ini), "terkenal" (dikenal luas; paling
banyak 10), "dikenal di lingkungannya" (dikenal di kelas, jurusan, atau kelompoknya), "biasa".
Dasarkan pada peran, jabatan, prestasi, penampilan, dan sifat di kartu; jangan mengarang hal yang tidak ada di kartu.
Jawab HANYA JSON: {{"items": [{{"name": "nama persis seperti di kartu", "fame": "bintang|terkenal|dikenal di lingkungannya|biasa",
"fame_for": "dikenal karena apa, maksimal 12 kata", "reason": "alasan singkat"}}]}}

{cards}"""

CHOICES_INSTRUCTION = """Buat pilihan aksi untuk pemain berdasarkan situasi di akhir jawaban terakhir. Jawab HANYA JSON:
{{"problems": [{{"question": "...", "options": ["...", "..."]}}]}}
Aturan: {np} masalah, tiap masalah {no} pilihan. Setiap pertanyaan {ns} kalimat panjang yang menjelaskan situasi dan
ketegangannya dengan detail konkret. Setiap pilihan {ns} kalimat panjang berisi tindakan dan niat atau caranya, tanpa
membocorkan hasilnya. Kategori pilihan harus beragam: sosial, fisik/aksi, berisiko, memakai barang atau kemampuan, dan yang
memajukan agenda tokoh lain. Spesifik ke situasi saat ini; jangan generik. Bahasa: {lang}. Tulis setiap pilihan sebagai
pesan pemain sendiri, orang pertama ("Aku ...").
Jangan mengulang atau meniru pilihan-pilihan ini:
{recent}"""

TICK_INSTRUCTION = """Waktu dunia maju {span} (dari {t0} ke {t1}). {why}
Tentukan apa yang dilakukan tokoh lain di luar layar selama itu dan kejadian dunia yang masuk akal (0-4 kejadian,
sesuai kartu GM; peristiwa garis waktu yang jatuh tempo wajib terjadi). Untuk setiap kejadian panggil world_event dengan
known_to yang tepat ('player' hanya kalau pemain bisa mengetahuinya). Catat perubahan lokasi/rencana tokoh dengan
status_update; luka ringan membaik atau sembuh dan suasana hati mereda seiring waktu (status_update, injuries
{{"remove": ...}}). Tokoh yang berada di tempat yang sama bisa saling bercerita atau bergosip: catat dengan tell (isinya bisa
melenceng atau bohong; truthful=false). Jangan menulis narasi. Setelah selesai jawab "selesai"."""

STATE_CHECK = """Pemeriksa keadaan. Baca narasi jawaban terakhir. Catat HANYA yang terjadi di narasi tetapi belum tercatat
di giliran ini:
- waktu yang berlalu (world_advance), kalau belum dicatat atau jelas kurang;
- perubahan status pemain dan tokoh: makan/minum/tidur (statistik), luka, barang berpindah tangan, lokasi, pakaian,
  keadaan (status_update);
- apa yang disaksikan atau didengar tokoh yang hadir, termasuk tokoh pemain (knowledge_add), dan apa yang diceritakan
  antar tokoh (tell);
- janji, janji temu, utang, atau misteri baru (thread_open), dan benang yang selesai (thread_close);
- mood, rencana, atau kegiatan tokoh yang sudah berubah atau mereda dibanding status tercatat (status_update);
- perubahan perasaan antar tokoh atau terhadap pemain karena kejadian di narasi (relationship).
Pakai hanya tool yang disebut di atas.
Sudah tercatat di giliran ini:
{done}
Keadaan tercatat sekarang (jangan dicatat ulang; benang yang sudah ada jangan dibuka lagi):
{now}
Jangan mengulang yang sudah tercatat dan jangan menebak hal yang tidak ada di narasi. Kalau tidak ada yang perlu dicatat,
jawab "selesai" tanpa memanggil tool."""

CONTINUITY_CHECK = """Cek kontinuitas jawaban terakhir terhadap data di bawah. Tandai HANYA pertentangan yang jelas:
- pengetahuan: tokoh mengatakan atau memakai hal yang tidak ada di kartunya, ingatannya, atau pengetahuan umum
  tempatnya (dan tidak ia saksikan di jawaban ini);
- lokasi: tokoh muncul atau bicara di tempat pemain padahal sedang di tempat lain dan tidak diceritakan datang;
- keadaan: tokoh yang mati, pergi, pingsan, atau ditahan bertindak seolah tidak;
- dadu: narasi tidak mengikuti hasil dadu giliran ini;
- suara: gaya bicara tokoh jauh dari contoh ucapannya.
Jangan menandai hal yang masuk akal atau tidak pasti. Jawab HANYA JSON:
{{"issues": [{{"kind": "pengetahuan|lokasi|keadaan|dadu|suara", "who": "nama", "text": "apa yang salah", "fix": "seharusnya"}}]}}

{data}"""

CARD_PROPOSALS = """Bandingkan kartu tokoh di system prompt dengan perkembangan cerita sejauh ini. Usulkan perubahan kartu
untuk hal yang sudah benar-benar berubah dan menetap: hubungan, sifat yang bergeser, penampilan, tujuan, rahasia yang sudah
terbongkar, umur. Bukan keadaan sesaat (itu status). Maksimal 6 usulan. Jawab HANYA JSON:
{{"proposals": [{{"card": "nama tokoh", "field": "kunci field di skema", "value": "isi baru lengkap", "reason": "kenapa"}}]}}
Skema kartu tokoh: {fields}"""

NEXT_SPEAKER = """Siapa tokoh yang paling wajar bereaksi berikutnya terhadap giliran ini, sesuai agenda, posisi, dan apa yang
ia tahu? Pilihan: {names}. Sudah bereaksi di giliran ini: {spoken}. Kalau sebaiknya giliran kembali ke pemain, jawab null.
Jawab HANYA JSON: {{"next": "nama" atau null}}"""

FACTCHECK_CLAIMS = """Periksa jawaban terakhir. Daftarkan klaim fakta {kind} yang spesifik di dalamnya (tanggal, angka, nama
satuan, senjata, pangkat, tempat, prosedur), bukan hal fiksi cerita. Maksimal 6. Jawab HANYA JSON: {{"claims": ["..."]}}"""

FACTCHECK_VERIFY = """Klaim: "{claim}"
Sumber ({source}):
{text}

Apakah klaim itu benar menurut sumber? Jawab HANYA JSON:
{{"verdict": "benar" | "salah" | "tidak pasti", "correction": "koreksi singkat kalau salah", "fact": "fakta yang benar, satu kalimat"}}"""

LEARN_INSTRUCTION = """Explain the sentence below for a learner of {lang}. Write everything in English. Answer ONLY JSON:
{{"translation": "English translation", "grammar": ["short grammar point in English", "..."],
"vocab": [{{"term": "...", "translation": "English", "note": "short note in English"}}]}}
Sentence: {text}"""

RECALL_QUESTIONS = """Dari potongan percakapan berikut, buat {n} pertanyaan tentang detail spesifik (nama, angka, kejadian, ucapan)
beserta jawabannya. Jawab HANYA JSON: {{"qa": [{{"q": "...", "a": "..."}}]}}

{text}"""

RECALL_ANSWER = """Uji ingatan (jangan pakai tool, jawab dari yang kamu ingat saja). Jawab setiap pertanyaan singkat; kalau tidak
tahu tulis "tidak tahu". Jawab HANYA JSON: {{"answers": ["...", "..."]}}
{questions}"""


TIME_SKIP_NOTE = ("Pemain melompati waktu {label}. Ceritakan transisi singkat (1-3 paragraf): apa yang wajar dilakukan pemain "
                  "selama itu dan apa yang berubah, lalu berhenti di situasi baru. Waktu sudah dimajukan sistem; jangan "
                  "panggil world_advance lagi.")


class Engine(EngineView):
    IDLE_COMPACT_AT = 0.75
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
        self.continuity_jobs = []
        self.offscreen_jobs = []  # chats whose off-screen world is due to move (world time passed in play)
        self.compact_backoff = {}  # chat id -> time before which idle compaction is not retried
        self.afk_lock = threading.Lock()
        self.backfilled = False
        self.dead = False
        self.importing = False
        # Re-running a cell makes a new Engine; the old one's idle loop and hooks must not keep working on the
        # same database next to it. The registry lives in sys.modules, which survives cell re-runs.
        reg = sys.modules.setdefault("_qchat_runtime", SimpleNamespace(engines=[]))
        for old in list(reg.engines):
            old.shutdown()
        reg.engines = [self]
        self.store.import_guards.append(self._import_guard)
        self.store.import_hooks.append(self._after_import)
        # QCHAT_IDLE=0 turns the background loop off (tests run several engines against one fake server).
        if os.environ.get("QCHAT_IDLE", "1") != "0":
            self.idle_thread = threading.Thread(target=self._idle_loop, daemon=True)
            self.idle_thread.start()

    # ---------- job runner ----------

    def run(self, fn, *args, queue_text=None):
        """Run fn in a worker thread, one job at a time. A send while busy is queued."""
        with self.lock:
            if self.busy:
                if queue_text is not None:
                    self.queue.append((fn, args, queue_text))
                    self.emit("toast", {"text": f"Queued ({len(self.queue)})."})
                    self.emit("queue", len(self.queue))
                else:
                    self.emit("toast", {"text": "Wait for the reply to finish or click Stop first.", "kind": "warn"})
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
            nxt, dropped = None, []
            with self.lock:
                if self.queue and not self.stop.is_set():
                    nxt = self.queue.pop(0)
                else:
                    dropped = [q[2] for q in self.queue if q[2]]
                    self.queue.clear()
                    self.busy = False
            self.emit("queue", len(self.queue))
            if dropped:  # Stop cancels the queue, but the typed text goes back to the composer
                self.emit("compose", "\n\n".join(dropped))
                self.emit("toast", {"text": f"{len(dropped)} queued message(s) cancelled; the text is back in the message box.",
                                    "kind": "warn"})
            if nxt:
                self._job(nxt[0], nxt[1])
            else:
                self.emit("busy", False)

    def forget_chat(self, chat_id):
        """A chat is being deleted: stop background work and drop everything queued for it. Returns False when
        background work did not stop in time."""
        self.bg_cancel.set()
        self.compactor.cancel.set()
        for _ in range(150):
            if not self.bg_busy:
                break
            time.sleep(0.1)
        self.fact_jobs[:] = [j for j in self.fact_jobs if j[0] != chat_id]
        self.continuity_jobs[:] = [j for j in self.continuity_jobs if j[0] != chat_id]
        self.offscreen_jobs[:] = [j for j in self.offscreen_jobs if j != chat_id]
        for d in (self.compact_backoff, self.last_used):
            d.pop(chat_id, None)
        if self.active_chat == chat_id:
            self.active_chat = 0
        return not self.bg_busy

    def stop_now(self):
        self.stop.set()
        self.compactor.cancel.set()
        self.bg_cancel.set()

    def shutdown(self):
        """Retire this engine (a newer one took over): stop its work and its background loop."""
        self.dead = True
        self.stop_now()
        for lst, fn in ((self.store.import_guards, self._import_guard), (self.store.import_hooks, self._after_import)):
            if fn in lst:
                lst.remove(fn)

    def _import_guard(self):
        """Loading or restoring a database while a reply is written would put it into another chat of the new file."""
        if self.busy:
            raise RuntimeError("Wait for the reply to finish (or click Stop) before loading a database.")
        self.importing = True
        self.bg_cancel.set()
        self.compactor.cancel.set()
        for _ in range(150):
            if not self.bg_busy:
                return
            time.sleep(0.1)
        self.importing = False
        raise RuntimeError("A background task is still running. Try again in a moment.")

    def _after_import(self, ok):
        if ok:
            with self.lock:
                self.queue.clear()
            self.fact_jobs.clear()
            self.continuity_jobs.clear()
            self.last_used.clear()
            self.active_chat = 0
            EMB.reset()
            EMB._model = None      # the loaded database may have been embedded by another model
            self.backfilled = False  # and its rows have no vectors yet: backfill on the next idle tick
        self.importing = False

    # ---------- chats and stories ----------

    def new_chat(self, kind="chat", title=None, story_id=None, settings=None):
        defaults = {"thinking": None, "length": None, "fact_mode": "latar", "group_mode": "narrator"}
        cid = self.store.new_chat(title or {"studio": "Studio", "rp": "New story", "group": "New group"}.get(kind, "New chat"),
                                  kind, story_id, {**defaults, **(settings or {})})
        self.emit("chats")
        return cid

    def start_story(self, card_ids, title=None, greeting_index=0, from_chat=None):  # noqa: C901
        """New story + RP chat from cards, with the chosen opening as the first message."""
        sc = self.cards.get(card_ids.get("scenario")) if card_ids.get("scenario") else None
        chars = card_ids.get("character") or []
        first_char = self.cards.get(chars[0]) if chars else None
        title = title or (sc["name"] if sc else (first_char["name"] if first_char else "New story"))
        for role in ("style", "gm"):
            if not card_ids.get(role):
                row = self.store.one("SELECT id FROM cards WHERE type = ? ORDER BY id LIMIT 1", (role,))
                card_ids[role] = row["id"] if row else None
        sid = self.stories.create(title, card_ids)
        kind = "group" if len(chars) > 1 else "rp"
        chat_id = self.new_chat(kind, title, sid)
        self.store.chat_settings(chat_id, world_sync=time.time())
        if sc and str(sc["data"].get("start_location") or "").strip():
            self.world.add_event(chat_id, None, "player", "location", sc["data"]["start_location"].strip(), "set", "awal skenario")
        opening = ""
        if sc and sc["data"].get("opening"):
            opening = sc["data"]["opening"]
        elif first_char:
            greet = first_char["data"].get("greetings") or []
            if greet:
                opening = greet[min(greeting_index, len(greet) - 1)]
        if opening:
            persona = self.cards.get(card_ids["persona"]) if card_ids.get("persona") else None
            opening = TXT.macros(opening, char=(first_char or {}).get("name", ""), user=(persona or {}).get("name") or "kamu")
            self.store.add_message(chat_id, None, "assistant", opening, meta={"opening": True})
        self.emit("chats")
        return chat_id

    def continue_in_new_chat(self, chat_id):
        """Same story, fresh chat: chronicle + last turns carried over, status replayed as the new base."""
        old = self.store.chat(chat_id)
        path = self.store.path(chat_id)
        ids = [m["id"] for m in path]
        st = self.world.state(chat_id, ids)
        new = self.new_chat(old["kind"], f"{old['title']} (continued)", old.get("story_id"),
                            {**old["settings"], "continued_from": chat_id, "continued_head": old["head_id"]})
        for s in self.prompt.summaries_on_path(chat_id, ids):
            self.store.x("INSERT INTO summaries (chat_id, node_id, from_id, level, text, core, created) VALUES (?, 0, 0, ?, ?, ?, ?)",
                         (new, s["level"], s["text"], s["core"], time.time()))
        users = [i for i, m in enumerate(path) if m["role"] == "user" and not m["ooc"]]
        start = users[-3] if len(users) >= 3 else 0
        recap = []
        for m in path[start:]:
            if m["role"] in ("user", "assistant") and m["content"].strip():
                recap.append(("Pemain" if m["role"] == "user" else "Narator") + ": " + m["content"])
        intro = ("Adegan terakhir dari chat sebelumnya:\n\n" + "\n\n".join(recap))[:60000]
        # The chronicle hangs on a root node; the recap follows it, so the recap stays in the history.
        root = self.store.add_message(new, None, "assistant", f"(Lanjutan dari chat \"{old['title']}\".)",
                                      meta={"carry_over": True})
        self.store.x("UPDATE summaries SET node_id = ?, from_id = ? WHERE chat_id = ? AND node_id = 0", (root, root, new))
        self.store.add_message(new, root, "assistant", intro, meta={"carry_over": True})
        self._carry_state(chat_id, new, root, set(ids), old.get("story_id"))
        self.world.add_event(new, None, "world", "time", st["time"].strftime("%Y-%m-%d %H:%M"), "set", "lanjutan")
        for s in st["stats"]:
            self.world.add_event(new, None, "player", s["key"], s["value"], "set", "lanjutan")
        for subject, fields in st["status"].items():
            for k, v in fields.items():
                self.world.add_event(new, None, subject, k, v, "set", "lanjutan")
        self.emit("chats")
        return new

    def _carry_state(self, old_id, new_id, root, vis, story_id):
        """Copy the old chat's state onto the new chat's root message: story book changes, what the characters know,
        open threads, relationships, memories made in that chat. The new chat then no longer depends on the old one
        (deleting or rerolling it changes nothing here)."""
        s, now = self.store, time.time()
        story = self.stories.get(story_id) if story_id else None
        if story:
            base = story["data"]["canon"]
            cur = self.stories.canon(story_id, vis, old_id)
            for sec in set(base) | set(cur):
                if base.get(sec) != cur.get(sec):
                    s.x("INSERT INTO canon_log (story_id, chat_id, message_id, section, text, created) VALUES (?, ?, ?, ?, ?, ?)",
                        (story_id, new_id, root, sec, cur.get(sec, ""), now))
        for r in KNOW._rows(old_id):
            kid = s.x("INSERT INTO knowledge (chat_id, message_id, holder, text, kind, source, source_who, truth, importance, "
                      "world_time, created) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                      (new_id, root, r["holder"], r["text"], r["kind"], r["source"], r["source_who"], r["truth"],
                       r["importance"], r["world_time"], r["created"]))
            EMB.enqueue("know", kid, r["text"])
        for t in THREADS.list(old_id):
            s.x("INSERT INTO threads (story_id, chat_id, message_id, kind, title, text, who, due, opened_at, created) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (t["story_id"], new_id, root, t["kind"], t["title"], t["text"], t["who"],
                                                          t["due"], t["opened_at"], t["created"]))
        for (a, b), v in RELATIONS.scores(old_id).items():
            if v["score"]:
                s.x("INSERT INTO relations_log (chat_id, message_id, a, b, delta, reason, world_time, created) "
                    "VALUES (?, ?, ?, ?, ?, ?, '', ?)", (new_id, root, a, b, v["score"], v["last"], now))
        ctx = {"visible": vis, "chat_id": old_id, "story_id": story_id}
        rows = s.q("SELECT * FROM memories WHERE kind != 'summary_core' AND ((scope = 'story' AND story_id = ?) "
                   "OR (scope = 'chat' AND chat_id = ?))", (story_id or -1, old_id))
        shown = {r["id"] for r in self.mem._resolve(rows, ctx)}
        for r in self.mem._resolve(rows, ctx):
            if r["scope"] == "story" and not r["message_id"]:
                continue  # made outside any turn: already counts in every chat of the story
            mid = s.x("INSERT INTO memories (scope, card_id, story_id, chat_id, kind, text, created, updated, message_id, importance) "
                      "VALUES (?, NULL, ?, ?, ?, ?, ?, ?, ?, ?)",
                      (r["scope"], r["story_id"], new_id if r["scope"] == "chat" else None, r["kind"], r["text"], r["created"],
                       now, root, r.get("importance", 0.5)))
            self.mem.emb.enqueue("mem", mid, r["text"])
        for r in rows:  # story memories the old chat forgot stay forgotten here
            if r["scope"] == "story" and not r["message_id"] and r["id"] not in shown:
                s.x("INSERT INTO memory_log (memory_id, action, before, chat_id, created, message_id) VALUES (?, 'hide', ?, ?, ?, ?)",
                    (r["id"], json.dumps(dict(r)), new_id, now, root))
                s.x("UPDATE memories SET forgotten_at = ? WHERE id = ? AND forgotten_at IS NULL", (root, r["id"]))

    # ---------- sending ----------

    def send(self, chat_id, text, files=None, kind=None):
        parsed = TXT.parse_input(text)
        if not chat_id or not self.store.chat(chat_id):
            chat_id = self.new_chat(kind or "chat", (text or "New chat")[:60])
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
            self.emit("toast", {"text": "Author's note saved." if arg else "Author's note removed."})
            self.emit("settings", chat_id)
        elif cmd == "reroll" and head:
            self.reroll(chat_id, head)
        elif cmd == "continue" and head:
            self.continue_msg(chat_id, head)
        elif cmd in ("bab", "chapter"):
            if head:
                self.store.x("INSERT INTO chapters (chat_id, message_id, title, created) VALUES (?, ?, ?, ?)",
                             (chat_id, head, arg or "New chapter", time.time()))
                self.emit("history", chat_id)
        elif cmd in ("ingat", "remember"):
            rows = self.mem.search(arg, self.mem.ctx_of(chat_id), limit=10, kinds=("fact", "summary_core"))
            self.emit("toast", {"text": "\n".join(f"#{r['id']} {r['text'][:160]}" for r in rows) or "No matching memory.",
                                "long": True})
        elif cmd == "impersonate":
            self.run(self._impersonate, chat_id, arg)
        elif cmd == "studio":
            self.run(self._studio_change, chat_id, arg)
        elif cmd in ("cek", "check") and head:
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
            if self.stop.is_set():
                return
        pending = len(full) // 3 + 1500 * len(media)
        self._respond(chat_id, extra=extra, pending_estimate=pending)

    def _catch_up(self, chat_id, uid):
        """AFK: advance the world clock by the real time that passed (GM scale) and let the world act."""
        c = self.prompt.ctx(chat_id)
        gm = self.prompt.gm(c)
        try:
            scale = float(gm.get("afk_scale") or 0)
        except ValueError:
            scale = 0
        with self.afk_lock:  # the idle tick advances AFK time too: one of them takes each span
            sync = (self.store.chat(chat_id) or {}).get("settings", {}).get("world_sync") or time.time()
            minutes = int((time.time() - sync) / 60 * scale)
            self.store.chat_settings(chat_id, world_sync=time.time())
            if minutes < 30:
                return []
            minutes = min(minutes, 60 * 24 * 30)
            ids = self.store.path_ids(chat_id)
            t0 = self.world.state(chat_id, ids)["time"]
            before = self.world.last_event_id(chat_id)
            self.world.advance(chat_id, uid, minutes, "AFK")
        self._tick(chat_id, t0, minutes, "Pemain sedang tidak ada (AFK). Tokoh yang sedang satu adegan dengan pemain tetap di "
                                         "tempat dan menunggu, kecuali waktunya sangat lama.", head=uid, stop=self.stop)
        self._offscreen_done(chat_id, t0 + timedelta(minutes=minutes))
        self._away_notice(chat_id, before, minutes)
        return [f"Pemain baru kembali setelah {World.fmt_span(minutes)} waktu dunia berlalu. Kejadian selama itu ada di atas."]

    def _away_notice(self, chat_id, before_id, minutes):
        events = self.world.events_after(chat_id, before_id)
        text = f"While you were away ({World.fmt_span(minutes)} of world time): " + (
            " · ".join(e["text"] for e in events[:6]) if events else "no news reached you.")
        self.emit("notice", {"chat_id": chat_id, "text": text})

    # ---------- the turn ----------

    def _turn(self, chat_id, extra=None, pending_estimate=0, length_override=None, group_note=True, also=None,
              seg_after=False, speaker=None, no_time=False):
        """One reply. also: lines for every round of this turn, not stored (a group speaker, a correction).
        seg_after: a group round's later speaker; its checks cover only its own part. Returns the error, if any."""
        if not self.servers.ready():
            raise RuntimeError("The model server is not READY yet. Click Start and wait for READY.")
        c = self.prompt.ctx(chat_id)
        tools = self.tools.specs(c)
        allowed = {t["function"]["name"] for t in tools}
        # The turn writes under its own head. Re-reading chats.head_id would follow the UI to another branch.
        turn = {"head": (self.store.chat(chat_id) or {}).get("head_id"), "ooc": False}
        seg = turn["head"] if seg_after else None
        hm = self.store.msg(turn["head"]) if turn["head"] else None
        if hm and hm["role"] == "user":
            turn["ooc"] = bool(hm["ooc"]) and c["kind"] in ("rp", "group")
            skip = (hm["meta"] or {}).get("time_skip")
            if skip:  # also on a reroll of a time skip
                also = list(also or []) + [TIME_SKIP_NOTE.format(label=skip)]
                length_override, no_time = False, True
        live = {"active": True, "content": "", "reasoning": "", "tools": [], "phase": "", "chat_id": chat_id,
                "thinking": False}
        self.emit("live", live)

        def phase(msg):
            live["phase"] = msg
            self.emit("live", live)

        def add(role, *args, **kw):
            if role == "assistant" and turn["ooc"]:
                kw.setdefault("ooc", True)  # an OOC answer is never read back as narration
            mid = self.store.add_message(chat_id, turn["head"], role, *args, **kw)
            turn["head"] = mid
            return mid

        t0 = time.time()
        totals = {"tokens": 0, "think_s": 0.0, "tools": 0, "gen_s": 0.0}
        usage, final_id, used_info = {}, None, {}
        extra = list(extra or [])
        if c["kind"] == "group" and group_note and not turn["ooc"]:
            extra.append(self._group_note(chat_id, c))
        avoid = c["settings"].get("avoid") or []
        if avoid and not turn["ooc"]:
            extra.append("Hindari frasa yang sudah berulang ini: " + "; ".join(f'"{p}"' for p in avoid[:8]))
        fix = c["settings"].get("lang_fix") or {}
        if fix.get("text") and not turn["ooc"]:
            extra.append(fix["text"])
        openers = c["settings"].get("openers") or []
        if openers and not turn["ooc"]:
            extra.append("Variasikan pembuka balasan. Balasan terakhir dimulai dengan pola yang sama seperti sebelumnya ("
                         + ", ".join(f'"{o["text"]}…"' for o in openers[-3:]) + "). Mulai giliran ini dengan cara lain.")
        error, state = None, None
        seen_calls, fails_in_row = {}, 0
        try:
            reserve = self._default_max_tokens(c)
            used = self.compactor.maybe(chat_id, tools, self.tools, phase, last_used=self.last_used.get(chat_id, 0),
                                        pending_estimate=pending_estimate, clear_cancel=not self.stop.is_set(), reserve=reserve)
            if used:
                self.last_used[chat_id] = used
            self._compaction_note(chat_id)
            phase("")
            _round = -1
            while True:
                _round += 1
                if _round:
                    # Many rounds of tool results can fill the context: compact older history between rounds too.
                    used = self.compactor.maybe(chat_id, tools, self.tools, phase, last_used=self.last_used.get(chat_id, 0),
                                                clear_cancel=not self.stop.is_set(), reserve=reserve)
                    if used:
                        self.last_used[chat_id] = used
                    phase("")
                path = self.store.path(chat_id, head=turn["head"])
                msgs, used_round = self.prompt.build(chat_id, path, extra=extra if _round == 0 else None, also=also,
                                                     length=length_override)
                if _round == 0:
                    used_info = {**used_round, "no_time": no_time}
                    # keep the exact temporary block of this turn with the user message (later rounds resend it)
                    if used_round.get("note") and path and path[-1]["role"] == "user":
                        um = path[-1]
                        self.store.update_message(um["id"], meta={**um["meta"], "ephemeral": used_round["note"]})
                base_c, base_r = live["content"], live["reasoning"]
                state = {"mid": None, "saved": 0.0}

                def on_delta(acc, base_c=base_c, base_r=base_r, state=state):
                    live["content"] = base_c + ("\n\n" if base_c and acc["content"] else "") + acc["content"]
                    live["reasoning"] = base_r + ("\n\n" if base_r and acc["reasoning"] else "") + acc["reasoning"]
                    live["thinking"] = bool(acc["reasoning"]) and not acc["content"] and not acc["calls"]
                    self.emit("live", live)
                    now = time.time()
                    if now - state["saved"] > 3:
                        state["saved"] = now
                        if state["mid"] is None:
                            state["mid"] = add("assistant", acc["content"], acc["reasoning"], status="partial")
                        else:
                            self.store.update_message(state["mid"], content=acc["content"], reasoning=acc["reasoning"])

                # After many failed tool calls in a row the model must answer with what it has.
                force_answer = fails_in_row >= 6
                acc = self.llm.chat(msgs, tools=tools, kwargs=self.prompt.kwargs(c), sampling=self.prompt.sampling(c),
                                    max_tokens=c["settings"].get("max_tokens") or self._default_max_tokens(c),
                                    on_delta=on_delta, stop=self.stop, tool_choice="none" if force_answer else None)
                live["thinking"] = False
                usage = acc["usage"] or usage
                if acc["usage"]:
                    self.last_used[chat_id] = acc["usage"].get("total_tokens") or self.last_used.get(chat_id, 0)
                totals["tokens"] += (acc["usage"] or {}).get("completion_tokens") or 0
                start = acc["t_think"] or acc["t_answer"]
                if start:
                    totals["gen_s"] += time.time() - start
                if acc["t_think"]:
                    totals["think_s"] += (acc["t_answer"] or time.time()) - acc["t_think"]
                calls = [] if self.stop.is_set() or force_answer else [
                    {"id": cl["id"] or f"call_{int(time.time())}_{i}", "type": "function",
                     "function": {"name": cl["name"], "arguments": cl["arguments"] or "{}"}}
                    for i, cl in sorted(acc["calls"].items())]
                if force_answer:
                    fails_in_row = 0
                content = TXT.dedupe_parens(acc["content"]) if c["kind"] in ("rp", "group") else acc["content"]
                status = "partial" if acc["finish"] in ("stopped", "length") and not calls else "final"
                if state["mid"] is None:
                    if content or acc["reasoning"] or calls:
                        state["mid"] = add("assistant", content, acc["reasoning"], calls or None, status=status)
                else:
                    self.store.update_message(state["mid"], content=content, reasoning=acc["reasoning"],
                                              tool_calls=calls or None, status=status)
                final_id = state["mid"] or final_id
                if not calls:
                    break
                for tc in calls:
                    name, args = tc["function"]["name"], tc["function"]["arguments"]
                    if self.stop.is_set():
                        # every tool call needs a result, or the next request has an unanswered call
                        res, failed, media = json.dumps({"error": "dibatalkan (Stop)"}), True, []
                    else:
                        key = (name, re.sub(r"\s+", "", args or ""))
                        seen_calls[key] = seen_calls.get(key, 0) + 1
                        entry = {"name": name, "args": args, "result": "", "running": True}
                        live["tools"].append(entry)
                        self.emit("live", live)
                        if seen_calls[key] > 2:
                            res, failed, media = json.dumps({"error": "Panggilan ini sudah dilakukan 2 kali dengan argumen yang "
                                                                      "sama. Jangan diulang; pakai hasil sebelumnya dan lanjutkan."}), True, []
                        else:
                            res, failed, media = self.tools.call(chat_id, state["mid"], name, args, allowed=allowed)
                        entry.update(result=res[:4000], running=False, error=failed)
                        totals["tools"] += 1
                        self.emit("live", live)
                        fails_in_row = fails_in_row + 1 if failed else 0
                    add("tool", res, tool_call_id=tc["id"], meta={"error": failed}, media=media)
                    if self.last_used.get(chat_id):
                        self.last_used[chat_id] += len(res) // 3 + 1500 * len(media)
                if self.stop.is_set():
                    break
        except urllib.error.HTTPError as e:
            error = f"The server rejected the request (HTTP {e.code}): {e.read().decode('utf-8', 'replace')[:400]}"
        except Exception as e:
            error = f"{type(e).__name__}: {e}"
        if final_id is None and state and state.get("mid"):
            final_id = state["mid"]  # the error came mid-stream: keep what was written as one cut-off reply
            self.store.update_message(final_id, status="partial")
        stats = {"tokens": totals["tokens"], "tps": totals["tokens"] / totals["gen_s"] if totals["tokens"] and totals["gen_s"] else None,
                 "think_s": totals["think_s"] or None, "tools": totals["tools"] or None, "total_s": time.time() - t0,
                 "stopped": self.stop.is_set(), "model": self.servers.state.get("preset"), "ctx": self.servers.state.get("ctx"),
                 "quant": quant_of(c["preset"]), "yarn": bool((self.servers.state.get("ctx") or 0) > c["preset"]["max_ctx"]),
                 "seed": (c["settings"].get("sampling") or {}).get("seed"),
                 "sampling": self.prompt.sampling(c), "thinking": self.prompt.kwargs(c), "mtp": self.servers.state.get("mtp")}
        live["active"] = False
        self.emit("live", {})
        if final_id is None:
            final_id = add("assistant", "", meta={"stats": stats, "error": error})
        else:
            m = self.store.msg(final_id)
            meta = {**m["meta"], "stats": stats}
            if error:
                meta["error"] = error
            if seg:
                meta["seg_after"] = seg
            if speaker:
                meta["speaker"] = speaker
            self.store.update_message(final_id, meta=meta)
        if not error and not self.stop.is_set() and c["kind"] in ("rp", "group") and not turn["ooc"]:
            try:
                self._after_turn(chat_id, final_id, c, used_info)
            except Exception as e:
                self.emit("live", {})
                self.emit("toast", {"text": f"Post-turn checks failed: {type(e).__name__}: {e}", "kind": "warn"})
            try:
                self._queue_offscreen(chat_id, c)
            except Exception:
                pass
        # What the next request will hold: the server's total also counted the thinking just written, which the next
        # prompt drops; the screen and the compaction trigger use the same number.
        try:
            self.last_used[chat_id] = self.compactor.measure(chat_id, tools)
        except Exception:
            pass
        self.emit("history", chat_id)
        self.emit("panels", chat_id)
        self.emit("ctx", {"used": self.last_used.get(chat_id, 0), "max": self.llm.max_context(),
                          "reserve": self._default_max_tokens(c), "at": self.compactor.COMPACT_AT})
        return error

    def _lang_points(self, chat_id, mid, c, lv):
        """Points for the target language: the player wrote in it this turn (+1, once per player message). A level-up
        (from points, rolls or weeks of world time) is announced once."""
        m = self.store.msg(mid) or {}
        if not (m.get("meta") or {}).get("seg_after"):  # a group round: only the first reply to the message counts
            u = self._turn_user(chat_id, mid) or {}
            text = u.get("content") or ""
            mine = TXT.dialogue_lines(text, lv["code"])
            if any(n >= 3 for n, _ in mine) or (TXT.lang_of(text) == lv["code"] and len(TXT.words(text)) >= 4):
                Lang.gain(self.world, chat_id, mid, self.world.state(chat_id, self.store.path_ids(chat_id)), 1,
                          "menulis bahasa target")
        st = self.world.state(chat_id, self.store.path_ids(chat_id))
        now = Lang.of(c["cards"], st, self.world.start_time(c["cards"]))
        before = (self.store.chat(chat_id) or {}).get("settings", {}).get("lang_band") or lv["band"]  # lv: this turn's start
        if now and before != now["band"]:
            self.store.chat_settings(chat_id, lang_band=now["band"])
            order = [b[1] for b in Lang.BANDS]
            if before in order and order.index(now["band"]) > order.index(before):
                self.emit("notice", {"chat_id": chat_id, "text": f"Your {now['label']} improved to {now['band']} "
                                                                 f"({now['value']}/100)."})

    def _compaction_note(self, chat_id):
        """Say once why compaction could not run (instead of a full context with no word)."""
        note = getattr(self.compactor, "last_note", "")
        seen = getattr(self, "_compact_notes", {})
        self._compact_notes = seen
        if note and seen.get(chat_id) != note:
            self.emit("toast", {"text": note, "kind": "warn", "long": True})
        seen[chat_id] = note

    def _default_max_tokens(self, c):
        """Room for the answer plus the thinking budget of the chat's level (max_tokens covers both)."""
        length = c["settings"].get("length") or "panjang"
        content = {"pendek": 2000, "sedang": 4000}.get(length, 8000)
        kw = self.prompt.kwargs(c)
        if not kw.get("enable_thinking", True):
            return content
        return content + {"low": 4000, "medium": 8000, "high": 16000, "xhigh": 32000}.get(kw.get("reasoning_effort"), 16000)

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

    @staticmethod
    def _turn_start(path, mid):
        """(start, end) indexes of the turn that ends at mid: after the user message, or in a group round after the
        previous speaker's reply (meta seg_after)."""
        ids = [x["id"] for x in path]
        end = ids.index(mid) if mid in ids else len(path) - 1
        after = ((path[end].get("meta") or {}).get("seg_after")) if path else None
        start = end
        while start > 0 and path[start - 1]["role"] != "user" and path[start - 1]["id"] != after:
            start -= 1
        return start, end

    @staticmethod
    def _openings(path, start, k=4):
        """First words of the last k turns before `start`: each turn's first narration (a group round counts each
        speaker's reply as a turn), OOC answers left out."""
        out, fresh = [], True  # the story opening counts as a turn
        for x in path[:start]:
            if x["role"] == "user":
                fresh = True
                continue
            if fresh and x["role"] == "assistant" and not x.get("ooc") and (x["content"] or "").strip():
                out.append(TXT.opening(x["content"]))
                fresh = False
            if (x.get("meta") or {}).get("speaker"):
                fresh = True
        return out[-k:]

    @classmethod
    def _turn_text(cls, path, mid):
        """All narration of the turn that ends at mid (rounds before and after tool calls), and the earlier replies."""
        start, end = cls._turn_start(path, mid)
        text = "\n\n".join(x["content"] for x in path[start:end + 1] if x["role"] == "assistant" and x["content"].strip())
        before = [x["content"] for x in path[:start] if x["role"] == "assistant" and x["content"]]
        return text, before

    def _after_turn(self, chat_id, mid, c, used):
        m = self.store.msg(mid)
        path = self.store.path(chat_id, head=mid)
        full, before = self._turn_text(path, mid)
        if not m or not full.strip():
            return
        # world: mark events the player has now been told about (by this reply), fire due timeline entries
        # News the note offered counts as told only when the reply tells it (or after three offers), else the player
        # never learns it. A timeline entry that fired but was not narrated waits as news the same way.
        offered = {}
        if used.get("events"):
            prev = (self.store.chat(chat_id) or {}).get("settings", {}).get("offered") or {}
            told = []
            for r in self.store.q(f"SELECT id, text FROM world_events WHERE id IN ({','.join('?' * len(used['events']))})",
                                  list(used["events"])):
                n = int(prev.get(str(r["id"]), 0)) + 1
                if TXT.mentions(full, r["text"]) or n >= 3:
                    told.append(r["id"])
                else:
                    offered[str(r["id"])] = n
            self.world.mark_shown(told, mid)
        self.store.chat_settings(chat_id, offered=offered)
        for e in used.get("timeline") or []:
            text = f"{e['title']}. {e['text']}"
            eid = self.world.add_world_event(chat_id, mid, e["at"], text, ["player"], True, f"timeline:{e['id']}")
            if TXT.mentions(full, text):
                self.world.mark_shown([eid], mid)
        flags = []
        # length: continue once if clearly short
        tgt = used.get("length")
        if tgt:
            paras, sents = TXT.shape(full)
            # A reply that hands over (a question, or a character speaking last and waiting) is complete: more text would
            # run past that point. Only a clearly short reply (under half the target's sentences) is continued.
            last = full.rstrip().split("\n\n")[-1]
            handed_over = re.search(r"\?\s*[\"”“»«']?\s*$", last) or re.search(r"[\"“”„«»]", last)
            short = paras < tgt["paragraphs"] - 1 and sum(sents) * 2 < tgt["paragraphs"] * tgt["sent_lo"]
            if short and not self.stop.is_set() and not handed_over:
                add = max(1, tgt["paragraphs"] - paras)
                self.emit("live", {"active": True, "content": m["content"], "phase": "Adding paragraphs…", "reasoning": "",
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
                    full = full.rstrip() + "\n\n" + more
                self.emit("live", {})
            paras, sents = TXT.shape(full)
            m["meta"]["shape"] = {"target": tgt, "paragraphs": paras, "sentences": sents}
        # state: fill in what the model forgot to record (time, status, who saw what)
        if (self.prompt.gm(c).get("state_check") or "ya") == "ya" and os.environ.get("QCHAT_STATE_CHECK", "1") != "0" \
                and not self.stop.is_set():
            self.emit("live", {"active": True, "content": m["content"], "phase": "Checking state…", "reasoning": "",
                               "tools": [], "chat_id": chat_id})
            try:
                m["meta"]["state_check"] = self._state_check(chat_id, mid, c, self.store.path(chat_id, head=mid), full,
                                                             auto_time=not used.get("no_time"), unmet=used.get("unmet"))
            finally:
                self.emit("live", {})
        # quality checks over the whole turn
        prev = before[-4:]
        rep = TXT.repeated_phrases(full, prev)
        # catchphrases from the cards are meant to come back
        samples = " ".join(str(x) for ch in c["cards"]["character"] for x in (ch["data"].get("speech_samples") or [])).lower()
        rep = [p for p in rep if p.lower() not in samples]
        old = [p for p in (self.store.chat(chat_id) or {}).get("settings", {}).get("avoid") or [] if p not in rep]
        self.store.chat_settings(chat_id, avoid=(rep + old)[:8])  # rolling: a phrase stays avoided for a while
        if rep:
            flags.append({"kind": "repeat", "text": "Repeated phrases: " + "; ".join(rep[:4])})
        # openings: a reply that starts like the recent ones; the next turns are told to start differently (3 turns)
        mine = TXT.opening(full)
        openers = [dict(o, left=o["left"] - 1) for o in (self.store.chat(chat_id) or {}).get("settings", {}).get("openers") or []
                   if o.get("left", 0) > 1]
        if TXT.repeats_opening(mine, self._openings(path, self._turn_start(path, mid)[0])):
            text = " ".join(mine[:4])
            openers = [o for o in openers if o["text"] != text] + [{"text": text, "left": 3}]
            flags.append({"kind": "opening", "text": f"Opening like the earlier replies: \"{text}…\""})
        self.store.chat_settings(chat_id, openers=openers[-4:])
        banned = TXT.banned_hits(full, self.prompt.style(c).get("banned") or [])
        if banned:
            flags.append({"kind": "banned", "text": "Banned phrases: " + ", ".join(banned)})
        narr = self.prompt.narration_lang(c) or "Indonesia"
        lang = narr.lower()
        expected = "id" if lang.startswith(("indo", "id")) else "de" if lang.startswith(("jer", "deu", "ger", "de")) else "en"
        dom, shares = TXT.narration_language(full, expected)
        rewrite_lang = None
        fixes = []
        if dom != expected and shares.get(dom, 0) > 0.5:
            flags.append({"kind": "language", "text": f"Narration seems to be in {dom}, not {expected}."})
            fixes.append(f"Narasi giliran sebelumnya tidak dalam bahasa {narr}. Tulis narasi dalam bahasa {narr}.")
            counted = sum(1 for x in TXT.words(full) if any(x in s for s in TXT.STOP.values()))
            if counted >= 15:
                rewrite_lang = (f"Jawaban sebelumnya tidak ditulis dalam bahasa {narr}. Tulis ulang giliran ini: narasi dalam "
                                f"bahasa {narr}; ucapan tokoh dalam bahasa asing tetap dalam bahasanya, dengan terjemahan {narr}.")
        lv = used.get("lang")
        if lv:
            lines_ = TXT.dialogue_lines(full, lv["code"])
            if len(lines_) >= 2 and sum(n for n, _ in lines_) / len(lines_) < lv["lo"] * 0.8:
                avg = sum(n for n, _ in lines_) / len(lines_)
                flags.append({"kind": "lang_short", "text": f"{lv['label']} dialogue too short for {lv['band']} "
                                                            f"(average {avg:.0f} words, target {lv['lo']}-{lv['hi']})."})
                fixes.append(f"Ucapan {lv['label']} giliran sebelumnya terlalu pendek untuk tingkat {lv['band']}: kalimatnya "
                             f"harus {lv['lo']}-{lv['hi']} kata.")
            missing = sum(1 for _, tr in lines_ if not tr)
            if missing:
                flags.append({"kind": "lang_untranslated", "text": f"{missing} {lv['label']} sentence(s) without a translation."})
                fixes.append(f"Ada kalimat {lv['label']} tanpa terjemahan di giliran sebelumnya: terjemahkan SETIAP kalimat.")
            self._lang_points(chat_id, mid, c, lv)
        prev_fix = (self.store.chat(chat_id) or {}).get("settings", {}).get("lang_fix") or {}
        if fixes:
            self.store.chat_settings(chat_id, lang_fix={"text": " ".join(fixes), "left": 3})
        elif prev_fix.get("left", 0) > 1:
            self.store.chat_settings(chat_id, lang_fix={**prev_fix, "left": prev_fix["left"] - 1})
        elif prev_fix:
            self.store.chat_settings(chat_id, lang_fix=None)
        if TXT.split_dialogue(full) >= 3:
            flags.append({"kind": "split", "text": "Dialogue looks split word by word with short translations."})
        persona = (c["cards"].get("persona") or {}).get("name", "")
        acts = TXT.acts_for_user(full, persona)
        if acts:
            flags.append({"kind": "acts_for_user", "text": "Narration seems to decide the player's words or actions: "
                                                           + "; ".join(acts[:3])})
        m["meta"]["flags"] = flags
        self.store.update_message(mid, meta=m["meta"])
        if rewrite_lang and not getattr(self, "_rewriting", False) and not self.stop.is_set() \
                and os.environ.get("QCHAT_LANG_REWRITE", "1") != "0":
            self.emit("toast", {"text": f"Narration is not in {narr}; the turn was rewritten. Swipe to see the old version.",
                                "kind": "warn"})
            self._rewrite(chat_id, mid, rewrite_lang)
            return
        # choices (game format)
        gm = self.prompt.gm(c)
        if gm.get("format") == "game" and gm.get("choices", "kadang") != "tidak" and not self.stop.is_set():
            if gm.get("choices") == "selalu" or random.random() < 0.6:
                self.emit("live", {"active": True, "content": m["content"], "phase": "Making choices…", "reasoning": "",
                                   "tools": [], "chat_id": chat_id})
                try:
                    choices = self._choices(chat_id, c, path)
                    if choices:
                        m = self.store.msg(mid)
                        m["meta"]["choices"] = choices
                        self.store.update_message(mid, meta=m["meta"])
                except Exception as e:
                    self.emit("toast", {"text": f"Could not make choices: {e}", "kind": "warn"})
                self.emit("live", {})
        # fact check
        mode = c["settings"].get("fact_mode") or "latar"
        if mode == "ketat" and not getattr(self, "_rewriting", False):
            self.emit("live", {"active": True, "content": m["content"], "phase": "Checking facts…", "reasoning": "",
                               "tools": [], "chat_id": chat_id})
            warnings = self._fact_check(chat_id, mid, False, stop=self.stop)
            self.emit("live", {})
            if warnings and not self.stop.is_set():
                # Strict mode: write the turn again with the corrections; the wrong version stays as a sibling.
                note = "Koreksi fakta untuk giliran ini (jawaban sebelumnya salah):\n" + "\n".join(
                    f"- {w['claim']} -> {w['correction']} ({w['source']})" for w in warnings)
                self.emit("toast", {"text": f"{len(warnings)} wrong fact(s); the reply was rewritten. Swipe to see the old version.",
                                    "kind": "warn"})
                self._rewrite(chat_id, mid, note)
                return  # the new version ran its own checks
        elif mode == "latar":
            self.fact_jobs.append((chat_id, mid))
        # continuity
        cmode = self.prompt.gm(c).get("continuity_check") or "latar"
        if cmode == "ketat" and not getattr(self, "_rewriting", False) and not self.stop.is_set():
            self.emit("live", {"active": True, "content": m["content"], "phase": "Checking continuity…", "reasoning": "",
                               "tools": [], "chat_id": chat_id})
            issues = self._continuity_check(chat_id, mid, True, stop=self.stop)
            self.emit("live", {})
            if issues and not self.stop.is_set():
                note = "Koreksi kontinuitas untuk giliran ini (jawaban sebelumnya keliru):\n" + "\n".join(
                    f"- {i.get('who', '')}: {i.get('text', '')} -> {i.get('fix', '')}" for i in issues)
                self.emit("toast", {"text": f"{len(issues)} continuity issue(s); the reply was rewritten. Swipe to see the old version.",
                                    "kind": "warn"})
                self._rewrite(chat_id, mid, note)
        elif cmode == "latar":
            self.continuity_jobs.append((chat_id, mid))

    def _rewrite(self, chat_id, mid, note):
        """Strict mode: write the turn again (in a group round only this speaker's part) with a correction; the wrong
        version stays as a sibling. Dice already rolled stay: the new version follows them instead of rolling again."""
        m = self.store.msg(mid)
        meta = (m or {}).get("meta") or {}
        seg, speaker = meta.get("seg_after"), meta.get("speaker")
        start = seg or (self._turn_user(chat_id, mid) or {}).get("id")
        if not start:
            return
        path = self.store.path(chat_id, head=mid)
        a, b = self._turn_start(path, mid)
        dice = [d for x in path[a:b + 1] for d in self.world.dice_for([x["id"]]).get(x["id"], [])]
        if dice:
            note += "\nHasil dadu giliran ini tetap berlaku (jangan roll lagi):\n" + "\n".join(
                f"- {d['event']}: {'BERHASIL' if d['success'] else 'GAGAL'}" for d in dice)
        also = [note] + ([self._speaker_note(speaker)] if speaker else [])
        self.store.set_head(chat_id, start)
        self._rewriting = True
        try:
            self._turn(chat_id, also=also, group_note=not speaker, seg_after=bool(seg), speaker=speaker,
                       length_override=False if speaker else None)
        finally:
            self._rewriting = False

    def _state_check(self, chat_id, mid, c, path, full, auto_time=True, unmet=None):
        """Side task after a turn: record what the narration shows but no tool recorded. If time still did not move
        (and the turn is not a time skip), it moves by an estimate from the length of the scene."""
        ids = [x["id"] for x in path]
        start, _ = self._turn_start(path, mid)
        done_lines, advanced = [], not auto_time
        for x in path[start:]:
            if x["role"] == "assistant" and x["tool_calls"]:
                for tc in json.loads(x["tool_calls"]):
                    fn = tc.get("function") or {}
                    done_lines.append(f"- {fn.get('name')}: {(fn.get('arguments') or '')[:300]}")
                    advanced = advanced or fn.get("name") == "world_advance"
        names = {"world_advance", "status_update", "knowledge_add", "tell", "world_event", "thread_open", "thread_close",
                 "relationship"}
        tools = self.tools.specs(c)  # the chat's full list: same prompt prefix as the turn (cache); names limits what runs
        kw = self.prompt.side_kwargs(c)
        st = self.world.state(chat_id, ids)
        now = [f"Jam {st['time_text']}"]
        if st["stats"]:
            now.append("Statistik pemain: " + ", ".join(f"{s['label']} {s['value']:g}" for s in st["stats"]))
        if st["status"]:
            now.append("Status: " + json.dumps(st["status"], ensure_ascii=False)[:3000])
        threads = THREADS.list(chat_id, now=st["time"])
        if threads:
            now.append("Benang terbuka:\n" + "\n".join(THREADS.line(r) for r in threads[:12]))
        instr = STATE_CHECK.format(done="\n".join(done_lines) or "- (belum ada)", now="\n".join(now))
        if self.prompt.narration_lang(c):
            instr += f"\nTulis isi catatan dalam bahasa {self.prompt.narration_lang(c)}."
        if unmet:
            instr += (f"\nPertemuan pertama dengan pemain mungkin terjadi di giliran ini: {', '.join(unmet)}. Untuk tiap tokoh yang "
                      "benar-benar bertemu atau berinteraksi dengan pemain di narasi, catat knowledge_add kind 'kenalan' (who: tokoh "
                      "itu): apakah ia tahu nama pemain, kesan pertamanya, dan bagaimana mereka bertemu (atau 'sudah kenal "
                      "sebelumnya' kalau memang begitu). Catat relationship kalau ada perasaan awal.")
        msgs = self.prompt.side(chat_id, instr, path=path)
        recorded = []
        for _ in range(3):
            acc = self.llm.chat(msgs, tools=tools, kwargs=kw, sampling={"temperature": 0.3},
                                max_tokens=3000 + self.prompt.think_budget(c, kw), stop=self.stop)
            got = [v for _, v in sorted(acc["calls"].items())]
            if not got and acc["finish"] == "length" and kw.get("enable_thinking", True):
                kw = self.prompt.side_kwargs(c, retry=True)  # thinking used up the budget: once more without it
                continue
            if not got or self.stop.is_set() or acc["finish"] == "stopped":
                break
            msgs.append({"role": "assistant", "content": acc["content"], "tool_calls": [
                {"id": cl["id"] or f"k{i}", "type": "function", "function": {"name": cl["name"], "arguments": cl["arguments"] or "{}"}}
                for i, cl in enumerate(got)]})
            for i, cl in enumerate(got):
                res, failed, _ = self.tools.call(chat_id, mid, cl["name"], cl["arguments"], allowed=names)
                msgs.append({"role": "tool", "tool_call_id": cl["id"] or f"k{i}", "content": res})
                if not failed:
                    recorded.append(f"{cl['name']}: {(cl['arguments'] or '')[:200]}")
                    advanced = advanced or cl["name"] == "world_advance"
        if not advanced and not self.stop.is_set():
            minutes = max(2, min(30, round(len(full.split()) / 90)))
            reason = "perkiraan dari panjang adegan (world_advance tidak dipanggil)"
            before = (self.world.state(chat_id, ids[:start]).get("status", {}).get("player") or {}).get("location")
            after = (self.world.state(chat_id, self.store.path_ids(chat_id, head=mid)).get("status", {}).get("player") or {}).get("location")
            trip = self.world.travel_minutes(c["cards"], before, after) if before and after else None
            if trip:
                minutes, reason = trip + max(0, minutes // 2), f"perjalanan {before} → {after} ({trip} menit) dan adegan"
            self.world.advance(chat_id, mid, minutes, reason)
            recorded.append(f"world_advance: {reason}, {minutes} menit")
        self.store.side_log("state_check", {"recorded": recorded,
                                            "transcript": [x for x in msgs if x["role"] in ("assistant", "tool")]}, chat_id, mid)
        return recorded

    @staticmethod
    def _range(text, default):
        m = re.match(r"\s*(\d+)\s*-\s*(\d+)", str(text or ""))
        return tuple(sorted((int(m.group(1)), int(m.group(2))))) if m else default

    def _json(self, text):
        """The first JSON object in a model answer, or None (never raises on bad JSON)."""
        t = (text or "").strip()
        t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
        dec = json.JSONDecoder()
        for n, mt in enumerate(re.finditer(r"\{", t)):
            if n >= 50:
                break
            try:
                obj, _ = dec.raw_decode(t[mt.start():])
            except ValueError:
                continue
            if isinstance(obj, dict):
                return obj
        return None

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
            kw = self.prompt.side_kwargs(c, retry=attempt > 0)
            acc = self.llm.complete(self.prompt.side(chat_id, instr), kwargs=kw,
                                    sampling={**self.prompt.sampling(c), "temperature": 1.1},
                                    max_tokens=3000 + self.prompt.think_budget(c, kw), tools=self.tools.specs(c), stop=self.stop)
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

    def _fact_check(self, chat_id, mid, announce, stop=None):
        # foreground (announce / strict) stops with Stop; background checks stop when the user sends something
        stop = stop or (self.stop if announce else self.bg_cancel)
        c = self.prompt.ctx(chat_id)
        world = c["cards"].get("world")
        real = not world or (world["data"].get("realworld") or "ya") == "ya"
        m = self.store.msg(mid)
        if not m or not m["content"].strip():
            return
        path = self.store.path(chat_id, head=mid)
        acc = self.llm.complete(self.prompt.side(chat_id, FACTCHECK_CLAIMS.format(kind="dunia nyata" if real else "tentang dunia cerita"),
                                                 path=path),
                                kwargs=self.prompt.side_kwargs(c), sampling={"temperature": 0.3},
                                max_tokens=3000 + self.prompt.think_budget(c), tools=self.tools.specs(c), stop=stop)
        if acc["finish"] == "stopped" or stop.is_set():
            if not announce:
                self.fact_jobs.insert(0, (chat_id, mid))  # interrupted by a new message: check it again later
            return []
        data = self._json(acc["content"]) or {}
        warnings = []
        for claim in (data.get("claims") or [])[:6]:
            if stop.is_set():
                if not announce:
                    self.fact_jobs.insert(0, (chat_id, mid))
                return []
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
                text = self.stories.canon_text(c["story"]["id"], visible=self.store.visible_ids(chat_id), chat_id=chat_id) if c["story"] else ""
                text += "\n" + "\n".join(f"{e['title']}: {e['text']}" for e in self.mem.lore_triggered(c["mem"]["card_ids"], claim))
            if not text.strip():
                continue
            v = self.llm.complete(self.prompt.side(chat_id, FACTCHECK_VERIFY.format(claim=claim, source=source, text=text[:8000]),
                                                   path=path),
                                  kwargs=self.prompt.side_kwargs(c), sampling={"temperature": 0.2},
                                  max_tokens=2000 + self.prompt.think_budget(c), tools=self.tools.specs(c), stop=stop)
            verdict = self._json(v["content"]) or {}
            if verdict.get("verdict") == "salah":
                warnings.append({"claim": claim, "correction": verdict.get("correction", ""), "source": source})
            if real and verdict.get("fact") and verdict.get("verdict") in ("benar", "salah"):
                self.mem.fact_save(verdict["fact"], source, "", world["id"] if world else None, 0.8)
        self.store.side_log("fact_check", {"claims": data.get("claims") or [], "warnings": warnings}, chat_id, mid)
        m = self.store.msg(mid)
        m["meta"]["fact_warnings"] = warnings
        m["meta"]["fact_checked"] = True
        self.store.update_message(mid, meta=m["meta"])
        self.emit("history", chat_id)
        if announce:
            self.emit("toast", {"text": f"Fact check: {len(warnings)} wrong claim(s)." if warnings else "Fact check: nothing wrong."})
        return warnings

    # ---------- card change proposals ----------

    def propose_cards(self, chat_id, stop=None):
        """Ask the model which character cards should change after what happened; you approve each in the Story tab."""
        c = self.prompt.ctx(chat_id)
        if c["kind"] not in ("rp", "group") or not c["cards"]["character"]:
            return []
        fields = ", ".join(f["key"] for f in self.cards.schema("character")["fields"] if f.get("visibility") != "ui")
        acc = self.llm.complete(self.prompt.side(chat_id, CARD_PROPOSALS.format(fields=fields)), kwargs=self.prompt.side_kwargs(c),
                                sampling={"temperature": 0.4}, max_tokens=6000 + self.prompt.think_budget(c),
                                tools=self.tools.specs(c), stop=stop or self.stop)
        if acc["finish"] == "stopped":
            return []
        by_name = {}
        for ch in c["cards"]["character"]:
            for n in [ch["name"]] + list(ch["data"].get("aliases") or []):
                by_name[str(n).lower()] = ch
        keys = {f["key"] for f in self.cards.schema("character")["fields"]}
        out = []
        for p in ((self._json(acc["content"]) or {}).get("proposals") or [])[:6]:
            if not isinstance(p, dict):
                continue
            ch = by_name.get(str(p.get("card", "")).lower())
            field = str(p.get("field", ""))
            if not ch or field not in keys or p.get("value") in (None, ""):
                continue
            pid = self.store.x("INSERT INTO card_proposals (chat_id, card_id, field, value, reason, created) VALUES (?, ?, ?, ?, ?, ?)",
                               (chat_id, ch["id"], field, json.dumps(p["value"], ensure_ascii=False), str(p.get("reason", ""))[:500],
                                time.time()))
            out.append(pid)
        if out:
            self.emit("toast", {"text": f"{len(out)} card change proposal(s) await your approval (Story tab)."})
        self.store.side_log("card_proposals", {"answer": acc["content"], "saved": out}, chat_id)
        return out

    def proposals(self, chat_id):
        rows = self.store.q("SELECT p.*, c.name AS card_name FROM card_proposals p JOIN cards c ON c.id = p.card_id "
                            "WHERE p.chat_id = ? ORDER BY p.id DESC LIMIT 50", (chat_id,))
        for r in rows:
            r["value"] = json.loads(r["value"])
        return rows

    def decide_proposal(self, chat_id, pid, accept):
        p = self.store.one("SELECT * FROM card_proposals WHERE id = ? AND status = 'menunggu'", (int(pid),))
        if not p:
            return False
        if accept and not self.cards.get(p["card_id"]):
            self.store.x("UPDATE card_proposals SET status = 'ditolak' WHERE id = ?", (p["id"],))
            return False
        if accept:
            self.cards.set_field(p["card_id"], p["field"], json.loads(p["value"]))
            sid = (self.store.chat(chat_id) or {}).get("story_id")
            card = self.cards.get(p["card_id"])
            if sid and card:
                self.stories.pending(sid, chat_id, f"Kartu {card['name']} · {p['field']}: {json.loads(p['value'])}"[:600])
        self.store.x("UPDATE card_proposals SET status = ? WHERE id = ?", ("diterima" if accept else "ditolak", p["id"]))
        return True

    # ---------- continuity ----------

    def continuity_data(self, chat_id, mid):
        """What the check compares the reply with: who is where and in what state, what the named people know,
        the dice of this turn, and how each speaks."""
        c = self.prompt.ctx(chat_id)
        path = self.store.path(chat_id, head=mid)
        ids = [x["id"] for x in path]
        full, _ = self._turn_text(path, mid)
        st = self.world.state(chat_id, ids)
        status = self.world.with_schedule(st, c["cards"])
        here = (status.get("player") or {}).get("location") or "?"
        low = full.lower()
        lines = [f"Lokasi pemain: {here}"]
        for ch in c["cards"]["character"]:
            s = status.get(ch["name"]) or {}
            names = [ch["name"]] + list(ch["data"].get("aliases") or [])
            named = any(n and n.lower() in low for n in names)
            guess = " (perkiraan jadwal)" if s.get("location_from") == "jadwal" else ""
            lines.append(f"- {ch['name']}: lokasi {s.get('location') or '?'}{guess}, keadaan {s.get('keadaan') or 'hidup'}"
                         + ("" if named else " (tidak disebut di jawaban ini)"))
            if named:
                core = self.cards.render(ch, mode="all", limit=1500)
                if core:
                    lines.append("  kartu (yang ia tahu sendiri):\n  " + core.replace("\n", "\n  "))
                heads = KNOW.relevant(chat_id, ch["name"], full, limit=12)
                if heads:
                    lines.append("  ingatan:\n" + "\n".join("  " + KNOW.line(r) for r in heads))
                samples = ch["data"].get("speech_samples") or []
                if samples:
                    lines.append("  contoh ucapan: " + " / ".join(f'"{x}"' for x in samples[:5]))
        start, end = self._turn_start(path, mid)
        dice = [d for i in ids[start:end + 1] for d in self.world.dice_for([i]).get(i, [])]
        if dice:
            lines.append("Hasil dadu giliran ini:\n" + "\n".join(
                f"- {d['event']}: {'BERHASIL' if d['success'] else 'GAGAL'} ({d['odds']:.0%})" for d in dice))
        return "\n".join(lines), full

    def _continuity_check(self, chat_id, mid, announce=False, stop=None):
        stop = stop or (self.stop if announce else self.bg_cancel)
        c = self.prompt.ctx(chat_id)
        m = self.store.msg(mid)
        if not m or c["kind"] not in ("rp", "group"):
            return []
        data, full = self.continuity_data(chat_id, mid)
        if not full.strip():
            return []
        msgs = self.prompt.side(chat_id, CONTINUITY_CHECK.format(data=data), path=self.store.path(chat_id, head=mid))
        data_json = None
        for attempt in range(2):
            kw = self.prompt.side_kwargs(c, retry=attempt > 0)
            acc = self.llm.complete(msgs, kwargs=kw, sampling={"temperature": 0.2},
                                    max_tokens=4000 + self.prompt.think_budget(c, kw), tools=self.tools.specs(c), stop=stop)
            if acc["finish"] == "stopped" or stop.is_set():
                if not announce:
                    self.continuity_jobs.insert(0, (chat_id, mid))
                return []
            data_json = self._json(acc["content"])
            if data_json is not None:
                break
        if data_json is None:  # empty or cut off: that is a failed check, not a clean one
            m = self.store.msg(mid)
            m["meta"]["continuity_error"] = f"empty or cut-off answer (finish={acc['finish']})"
            self.store.update_message(mid, meta=m["meta"])
            if announce:
                self.emit("toast", {"text": "Continuity check failed: the model's answer was empty or cut off.", "kind": "warn"})
            return []
        issues = []
        for i in data_json.get("issues") or []:
            if isinstance(i, dict) and str(i.get("text", "")).strip():
                issues.append({k: str(i.get(k, ""))[:400] for k in ("kind", "who", "text", "fix")})
        m = self.store.msg(mid)
        m["meta"]["continuity"] = issues[:8]
        m["meta"]["continuity_checked"] = True
        self.store.update_message(mid, meta=m["meta"])
        self.store.side_log("continuity", {"issues": issues, "data": data}, chat_id, mid)
        self.emit("history", chat_id)
        if announce:
            self.emit("toast", {"text": f"Continuity check: {len(issues)} issue(s)." if issues else "Continuity check: all clear."})
        return issues

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
            self.emit("toast", {"text": "No user message to answer again.", "kind": "warn"})
            return
        self.run(self._turn_from, chat_id, u["id"])

    def _turn_from(self, chat_id, head):
        """Answer from a given message (reroll, a stopped turn, a failed turn)."""
        self.store.set_head(chat_id, head)
        self.emit("history", chat_id)
        self._respond(chat_id)

    def _respond(self, chat_id, extra=None, pending_estimate=0):
        chat = self.store.chat(chat_id) or {}
        head = self.store.msg(chat.get("head_id")) if chat.get("head_id") else None
        ooc = bool(head and head["role"] == "user" and head["ooc"])
        if chat.get("kind") == "group" and (chat.get("settings") or {}).get("group_mode") == "single" and not ooc:
            return self._group_round(chat_id, extra, pending_estimate)
        return self._turn(chat_id, extra=extra, pending_estimate=pending_estimate)

    MAX_SPEAKERS = 3

    def _group_round(self, chat_id, extra=None, pending_estimate=0):
        """One character per reply: the model picks who reacts next, that character's reply is generated on its own;
        up to MAX_SPEAKERS per turn, or until it hands the turn back to the player."""
        c = self.prompt.ctx(chat_id)
        names = self._speakers(chat_id, c)
        forced = c["settings"].get("speaker")
        spoken = []
        for k in range(min(self.MAX_SPEAKERS, max(1, len(names)))):
            if self.stop.is_set():
                break
            if k == 0 and forced:
                who = self.tools._holder(chat_id, forced)
                who = who if who and who != "player" else forced
                self.store.chat_settings(chat_id, speaker=None)
            else:
                who = self._next_speaker(chat_id, c, names, spoken, first=k == 0)
                if not who:
                    break
            # Each speaker writes after the previous one: its instruction rides along every round of its own turn
            # (not stored with the player's message), it writes a short part, and its checks cover only that part.
            err = self._turn(chat_id, extra=list(extra or []) if k == 0 else None, also=[self._speaker_note(who)],
                             pending_estimate=pending_estimate if k == 0 else 0, group_note=False, seg_after=k > 0,
                             speaker=who, length_override=False)
            spoken.append(who)
            if err:
                break

    @staticmethod
    def _speaker_note(who):
        return (f"Giliran ini hanya {who} yang bicara dan bertindak, 1-3 paragraf. Awali dengan **{who}**. Jangan menulis "
                f"tokoh lain atau tindakan pemain.")

    def _speakers(self, chat_id, c):
        """Characters who can speak now: not dead, gone, held, or unconscious; those in the scene when anyone is."""
        ids = self.store.path_ids(chat_id)
        st = self.world.state(chat_id, ids)
        where = self.world.with_schedule(st, c["cards"])
        path = self.store.path(chat_id, ids=ids[-3:]) if ids else []
        recent = "\n".join(m["content"] for m in path)
        able = [ch for ch in c["cards"]["character"]
                if str((where.get(ch["name"]) or {}).get("keadaan") or "").lower() not in
                ("mati", "pergi", "tewas", "meninggal", "ditahan", "pingsan")]
        if (where.get("player") or {}).get("location"):  # a known place: only those there (or named) can answer
            here = {ch["name"] for ch in self.prompt.present_characters(c, recent, where)}
            names = [ch["name"] for ch in able if ch["name"] in here] or [ch["name"] for ch in able]
        else:  # nobody's place is known: the whole group is in the scene
            names = [ch["name"] for ch in able]
        return names or [ch["name"] for ch in c["cards"]["character"]]

    def _next_speaker(self, chat_id, c, names, spoken, first=False):
        msgs = self.prompt.side(chat_id, NEXT_SPEAKER.format(names=", ".join(names), spoken=", ".join(spoken) or "-"))
        data = None
        for attempt in range(2):
            kw = self.prompt.side_kwargs(c, retry=attempt > 0)
            acc = self.llm.complete(msgs, kwargs=kw, sampling={"temperature": 0.4}, max_tokens=300 + self.prompt.think_budget(c, kw),
                                    tools=self.tools.specs(c), stop=self.stop)
            data = self._json(acc["content"])
            if data is not None or self.stop.is_set():
                break
        left = [n for n in names if n not in spoken]
        who = (data or {}).get("next")
        if who:
            name = self.tools._holder(chat_id, who)
            if name in left:
                return name
        # the first speaker of a round is never skipped: the player is waiting for someone to answer
        return left[0] if first and left else None

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
        if not m:
            return None
        if m["role"] == "user":
            self.run(self._edit_user, chat_id, mid, text)
            return None
        if m["role"] != "assistant":
            self.emit("toast", {"text": "Tool results cannot be edited.", "kind": "warn"})
            return None
        # the edited text is a plain answer: a copied tool call without its results would be cut from the prompt
        nid = self.store.add_message(chat_id, m["parent_id"], "assistant", text, m["reasoning"], meta={"edited": True})
        self.emit("history", chat_id)
        return nid

    def _edit_user(self, chat_id, mid, text):
        m = self.store.msg(mid)
        typed = m["meta"].get("typed", m["content"])
        # keep what the attachments added: their text blocks after the typed text, and the images/videos
        tail = m["content"][len(typed):] if m["content"].startswith(typed) else ""
        media = [{k: a[k] for k in ("kind", "mime", "name", "data")} for a in self.store.attachments([mid]).get(mid, [])]
        meta = {k: v for k, v in m["meta"].items() if k != "ephemeral"}
        meta["typed"] = text
        self.store.add_message(chat_id, m["parent_id"], "user", text + tail, meta=meta, ooc=bool(m["ooc"]), media=media)
        self.emit("history", chat_id)
        self._respond(chat_id)

    def continue_msg(self, chat_id, mid):
        m = self.store.msg(mid)
        if not m:
            return
        if m["role"] in ("user", "tool"):
            # Nothing to continue yet: answer from here. A turn stopped after a tool call goes on with its tool loop.
            self.run(self._turn_from, chat_id, mid)
            return
        self.run(self._continue, chat_id, mid)

    def _continue(self, chat_id, mid):
        try:
            self._continue_inner(chat_id, mid)
        finally:
            self.emit("live", {})
            self.emit("history", chat_id)

    def _continue_inner(self, chat_id, mid):
        c = self.prompt.ctx(chat_id)
        m = self.store.msg(mid)
        if self.store.children(chat_id, mid):
            # Later turns hang on this reply: writing into it would change their history. Continue a copy instead,
            # as a new branch; the old branch keeps its turns.
            old_mid = mid
            mid = self.store.add_message(chat_id, m["parent_id"], "assistant", m["content"], m["reasoning"],
                                         meta={**m["meta"], "continued_from": mid}, status=m["status"])
            self.store.clone_effects(old_mid, mid)
            for r in self.store.q("SELECT id, text FROM memories WHERE message_id = ?", (mid,)):
                self.mem.emb.enqueue("mem", r["id"], r["text"])
            for r in self.store.q("SELECT id, text FROM knowledge WHERE message_id = ?", (mid,)):
                EMB.enqueue("know", r["id"], r["text"])
            m = self.store.msg(mid)
        self.store.set_head(chat_id, mid)
        live = {"active": True, "content": m["content"], "reasoning": "", "tools": [], "phase": "Continuing…", "chat_id": chat_id}
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
            self.store.purge_messages(sub)
            for i in range(0, len(sub), 500):
                part = sub[i:i + 500]
                marks = ",".join("?" * len(part))
                for t, col in (("attachments", "message_id"), ("status_events", "message_id"), ("world_events", "message_id"),
                               ("dice_log", "message_id"), ("chapters", "message_id"), ("summaries", "node_id"), ("messages", "id")):
                    self.store.conn.execute(f"DELETE FROM {t} WHERE {col} IN ({marks})", part)
                for m_id in part:
                    self.store.conn.execute("DELETE FROM vectors WHERE kind = 'msg' AND ref_id BETWEEN ? AND ?",
                                            (m_id * 100, m_id * 100 + 99))
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
        self.emit("toast", {"text": "New branch: the next message branches from here."})

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
                                                                                                         "typed": f"Time skip {label}"})
        ids = self.store.path_ids(chat_id)
        t0 = self.world.state(chat_id, ids)["time"]
        self.world.advance(chat_id, uid, minutes, f"lompat {label}")
        self.emit("history", chat_id)
        self._tick(chat_id, t0, minutes, f"Pemain melompati waktu {label} dan menjalani rutinitas yang wajar.", head=uid)
        self._offscreen_done(chat_id, t0 + timedelta(minutes=minutes))
        self._turn(chat_id)  # the time skip note comes from the user message (a reroll gets it too)

    def suggest_fame(self, chat_id, stop=None):
        """Pamor suggestions for the story's characters (latest card versions), ten cards per request. Rows for the UI
        table; nothing is saved here."""
        stop = stop or self.stop
        c = self.prompt.ctx(chat_id)
        sid = (c["story"] or {}).get("id")
        chars = self.prompt.stories.cards_of(sid, latest=True)["character"] if sid else []
        kw = self.prompt.side_kwargs(c)
        rows = []
        try:
            for i in range(0, len(chars), 10):
                if stop.is_set():
                    break
                part = chars[i:i + 10]
                self.emit("status", f"Drafting fame suggestions {min(i + 10, len(chars))}/{len(chars)}…")
                text = "\n\n".join(self.prompt.cards.render(ch, mode="all", limit=900) for ch in part)
                msgs = [{"role": "system", "content": "Kamu membantu menyusun cerita. Jawab hanya JSON."},
                        {"role": "user", "content": FAME_SUGGEST.format(n=len(chars), cards=text)}]
                try:
                    acc = self.llm.complete(msgs, kwargs=kw, sampling={"temperature": 0.3},
                                            max_tokens=3000 + self.prompt.think_budget(c, kw), stop=stop)
                    items = (self._json(acc["content"]) or {}).get("items") or []
                except Exception:
                    items = []
                got = {str(x.get("name", "")).strip().lower(): x for x in items if isinstance(x, dict)}
                for ch in part:
                    x = got.get(ch["name"].strip().lower()) or {}
                    fame = fame_level(x.get("fame"))
                    now = self.prompt.fame(ch)
                    rows.append({"card_id": ch["id"], "name": ch["name"], "current": now,
                                 "fame": fame or now,
                                 "fame_for": str(x.get("fame_for") or ch["data"].get("fame_for") or "")[:200],
                                 "reason": str(x.get("reason") or "")[:300]})
        finally:
            self.emit("status", "")
        return rows

    OFFSCREEN_HOURS = 4

    def _offscreen_span(self, chat_id, c=None):
        """(world time of the last off-screen move, now, minutes since) on the active branch when it is due, else None."""
        if not self.store.chat(chat_id):
            return None
        c = c or self.prompt.ctx(chat_id)
        try:
            hours = float(self.prompt.gm(c).get("offscreen_hours", self.OFFSCREEN_HOURS) or 0)
        except (TypeError, ValueError):
            hours = self.OFFSCREEN_HOURS
        if hours <= 0:
            return None
        now = self.world.state(chat_id, self.store.path_ids(chat_id))["time"]
        sync = TXT.parse_datetime((self.store.chat(chat_id) or {}).get("settings", {}).get("offscreen_sync") or "")
        if not sync or sync > now:  # the first time, or the branch went back in time: count from here
            self._offscreen_done(chat_id, now)
            return None
        minutes = int((now - sync).total_seconds() // 60)
        return (sync, now, minutes) if minutes >= hours * 60 else None

    def _offscreen_done(self, chat_id, t):
        self.store.chat_settings(chat_id, offscreen_sync=t.strftime("%Y-%m-%d %H:%M"))

    def _queue_offscreen(self, chat_id, c=None):
        if chat_id not in self.offscreen_jobs and self._offscreen_span(chat_id, c):
            self.offscreen_jobs.append(chat_id)

    def _offscreen(self, chat_id, stop=None):
        """Characters away from the player's scene follow their agendas for the world time that passed in play (runs in
        the background; a new message stops it and it runs again later)."""
        span = self._offscreen_span(chat_id)
        if not span:
            return
        sync, now, minutes = span
        stop = stop or self.stop
        self.emit("status", "The off-screen world moves…")
        try:
            self._tick(chat_id, sync, minutes, "Waktu itu berlalu selama adegan pemain. Gerakkan hanya tokoh dan pihak yang TIDAK "
                                               "sedang satu adegan dengan pemain; tokoh di adegan pemain jangan diubah.", stop=stop)
        finally:
            self.emit("status", "")
        if not stop.is_set():
            self._offscreen_done(chat_id, now)
            self.emit("panels", chat_id)

    def _tick(self, chat_id, t0, minutes, why, head=None, stop=None):
        c = self.prompt.ctx(chat_id)
        allowed = {"world_event", "status_update", "roll", "tell", "knowledge_add", "thread_close", "thread_open"}
        tools = self.tools.specs(c)  # the chat's full list: same prompt prefix as the turns (cache); allowed limits what runs
        t1 = t0 + timedelta(minutes=minutes)
        instr = TICK_INSTRUCTION.format(span=World.fmt_span(minutes), t0=World.fmt_time(t0), t1=World.fmt_time(t1), why=why)
        instr += "\nPakai hanya world_event, status_update, tell, knowledge_add, roll, thread_open, dan thread_close."
        if self.prompt.narration_lang(c):
            instr += f" Tulis teks kejadian dan catatan dalam bahasa {self.prompt.narration_lang(c)}."
        top = [ch["name"] for ch in c["cards"]["character"] if self.prompt.fame(ch) in TOP_FAME]
        if top:
            instr += ("\nTokoh paling dikenal: " + ", ".join(top[:15]) + ". Agenda mereka didahulukan, dan mereka sering jadi "
                      "bahan obrolan atau gosip tokoh lain (tell).")
        due = [r for r in THREADS.list(chat_id, now=t1) if r["overdue"]]
        if due:
            instr += ("\nBenang cerita yang lewat tenggat selama itu (tentukan akibatnya dengan world_event; thread_close kalau "
                      "sudah berakhir):\n" + "\n".join(THREADS.line(r) for r in due[:8]))
        msgs = self.prompt.side(chat_id, instr)
        head = head or self.store.chat(chat_id)["head_id"]
        for _ in range(3):
            acc = self.llm.chat(msgs, tools=tools, kwargs=self.prompt.kwargs(c), sampling=self.prompt.sampling(c),
                                max_tokens=12000, stop=stop or self.stop)
            calls = [v for _, v in sorted(acc["calls"].items())]
            if not calls or (stop or self.stop).is_set() or acc["finish"] == "stopped":
                break
            msgs.append({"role": "assistant", "content": acc["content"], "tool_calls": [
                {"id": cl["id"] or f"t{i}", "type": "function", "function": {"name": cl["name"], "arguments": cl["arguments"] or "{}"}}
                for i, cl in enumerate(calls)]})
            for i, cl in enumerate(calls):
                res, _, _ = self.tools.call(chat_id, head, cl["name"], cl["arguments"], allowed=allowed)
                msgs.append({"role": "tool", "tool_call_id": cl["id"] or f"t{i}", "content": res})
        self.store.side_log("world_tick", {"why": why, "from": str(t0), "minutes": minutes,
                                           "transcript": [m for m in msgs if m["role"] in ("assistant", "tool")]},
                            chat_id, head)

    def _idle_loop(self):
        while not self.dead:
            time.sleep(30)
            try:
                self._idle_once()
            except Exception:
                pass

    def _idle_once(self):
        if self.dead or self.importing or self.busy or self.bg_busy or not self.servers.ready():
            return
        # Mark busy and clear the cancel flag first, then look again: run() and a Load set their flags after this
        # point, so neither a send nor a Load can slip between the check and the work.
        self.bg_busy = True
        self.bg_cancel.clear()
        if self.importing or self.busy or self.dead:
            self.bg_busy = False
            return
        # Embed whatever is new (messages, summaries, lore, events...) every few minutes while idle.
        if EMB.ready() and time.time() - (self.backfilled or 0) > 300:
            self.backfilled = time.time()
            threading.Thread(target=EMB.backfill, daemon=True).start()
        try:
            while self.fact_jobs and not self.busy and not self.bg_cancel.is_set():
                chat_id, mid = self.fact_jobs.pop(0)
                self._fact_check(chat_id, mid, False)
            while self.continuity_jobs and not self.busy and not self.bg_cancel.is_set():
                chat_id, mid = self.continuity_jobs.pop(0)
                if self.store.msg(mid):
                    self._continuity_check(chat_id, mid, False)
            while self.offscreen_jobs and not self.busy and not self.bg_cancel.is_set():
                self._offscreen(self.offscreen_jobs.pop(0), stop=self.bg_cancel)
            chat_id = self.active_chat
            chat = self.store.chat(chat_id) if chat_id else None
            if not chat:
                return
            idle = time.time() - self.last_activity
            maxc = self.llm.max_context()
            used = self.last_used.get(chat_id, 0)
            if maxc and used > self.IDLE_COMPACT_AT * maxc and idle > 60 and not self.busy:
                # Runs while the player is away, so a turn rarely has to wait for it (a turn compacts at 90%).
                # Sending a message cancels it; finished pieces stay, the rest is done later.
                note = " (send a message to cancel; finished parts are kept)"
                # run() marks the engine busy before it sets the cancel flag: clear first, then look at busy.
                if self.bg_cancel.is_set() or self.importing:
                    return
                self.compactor.cancel.clear()
                if self.busy or self.bg_cancel.is_set() or self.importing:
                    return
                if time.time() < self.compact_backoff.get(chat_id, 0):
                    return  # it failed recently: wait instead of retrying every 30 s
                self.emit("status", "Idle compaction…" + note)
                c = self.prompt.ctx(chat_id)
                try:
                    self.last_used[chat_id] = self.compactor.maybe(chat_id, self.tools.specs(c), self.tools,
                                                                   lambda m: self.emit("status", m + note), force=False,
                                                                   threshold=self.IDLE_COMPACT_AT, clear_cancel=False,
                                                                   reserve=self._default_max_tokens(c))
                    self._compaction_note(chat_id)
                except Exception as e:
                    self.compact_backoff[chat_id] = time.time() + 15 * 60
                    self.store.side_log("compaction_error", {"error": f"{type(e).__name__}: {e}"}, chat_id)
                    self.emit("toast", {"text": f"Idle compaction failed: {type(e).__name__}: {str(e)[:300]}. "
                                                f"Retrying in 15 minutes (or click Compact).", "kind": "error", "long": True})
                    return
                finally:
                    self.emit("status", "")
                if self.last_used[chat_id] > self.IDLE_COMPACT_AT * maxc and not self.compactor.cancel.is_set():
                    self.compact_backoff[chat_id] = time.time() + 10 * 60  # nothing left it could shrink: wait
                self.emit("history", chat_id)
                # only after a real compaction (new epoch), not every time the loop finds the context full
                if chat["kind"] in ("rp", "group") and not self.busy and not self.bg_cancel.is_set() \
                        and (self.store.chat(chat_id) or {}).get("epoch") != chat.get("epoch"):
                    self.emit("status", "Drafting card change proposals…")
                    try:
                        self.propose_cards(chat_id, stop=self.bg_cancel)
                    finally:
                        self.emit("status", "")
            if chat["kind"] in ("rp", "group"):
                c = self.prompt.ctx(chat_id)
                gm = self.prompt.gm(c)
                try:
                    every, scale = float(gm.get("tick_minutes") or 0), float(gm.get("afk_scale") or 0)
                except ValueError:
                    every, scale = 0, 0
                if not every or not scale:
                    return
                with self.afk_lock:  # the player's next message advances AFK time too: one of them takes each span
                    sync = (self.store.chat(chat_id) or {}).get("settings", {}).get("world_sync") or time.time()
                    if not (idle > every * 60 and time.time() - sync > every * 60 and not self.busy):
                        return
                    minutes = int((time.time() - sync) / 60 * scale)
                    ids = self.store.path_ids(chat_id)
                    head = chat["head_id"]
                    t0 = self.world.state(chat_id, ids)["time"]
                    before = self.world.last_event_id(chat_id)
                    self.world.advance(chat_id, head, minutes, "AFK")
                    self.store.chat_settings(chat_id, world_sync=time.time())
                self.emit("status", "The world moves on…")
                self._tick(chat_id, t0, minutes, "Pemain sedang tidak ada (AFK). Tokoh yang sedang satu adegan dengan pemain "
                                                 "tetap di tempat dan menunggu, kecuali waktunya sangat lama.",
                           head=head, stop=self.bg_cancel)
                self._offscreen_done(chat_id, t0 + timedelta(minutes=minutes))
                self._away_notice(chat_id, before, minutes)
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
        draft = (acc["content"] or "").strip()
        self.store.side_log("impersonate", {"hint": hint, "draft": draft}, chat_id)
        self.emit("compose", draft)

    def _studio_change(self, chat_id, request):
        """'/studio ...' or '((ubah: ...))' during RP: the model edits cards or the story book through tools."""
        c = self.prompt.ctx(chat_id)
        allowed = {"canon_set", "status_update", "memory_save", "memory_update"}
        tools = [t for t in self.tools.specs(c) if t["function"]["name"] in allowed] + TOOL_CARD_EDIT
        msgs = self.prompt.side(chat_id, f"Permintaan perubahan dari pemain (di luar cerita): {request}\n"
                                         f"Kalau yang berubah adalah sifat tetap tokoh/dunia/gaya, pakai card_update (kartu). Kalau yang "
                                         f"berubah keadaan cerita, pakai canon_set / status_update / memory_save. Jawab singkat apa yang diubah.")
        head = self.store.chat(chat_id)["head_id"]
        names = {t["function"]["name"] for t in tools}
        answered = False
        for _ in range(3):
            acc = self.llm.chat(msgs, tools=tools, kwargs=self.prompt.kwargs(c), sampling=self.prompt.sampling(c), max_tokens=8000,
                                stop=self.stop)
            calls = [v for _, v in sorted(acc["calls"].items())]
            if self.stop.is_set():
                break
            if not calls:
                answered = True
                self.store.side_log("studio_change", {"request": request, "answer": acc["content"],
                                                      "transcript": [m for m in msgs if m["role"] in ("assistant", "tool")]},
                                    chat_id, head)
                self.emit("toast", {"text": (acc["content"] or "Done.").strip()[:600], "long": True})
                break
            msgs.append({"role": "assistant", "content": acc["content"], "tool_calls": [
                {"id": cl["id"] or f"s{i}", "type": "function", "function": {"name": cl["name"], "arguments": cl["arguments"] or "{}"}}
                for i, cl in enumerate(calls)]})
            for i, cl in enumerate(calls):
                res, _, _ = self.tools.call(chat_id, head, cl["name"], cl["arguments"], allowed=names)
                msgs.append({"role": "tool", "tool_call_id": cl["id"] or f"s{i}", "content": res})
        if not answered:
            done = [m["tool_calls"][0]["function"]["name"] for m in msgs if m.get("tool_calls")]
            self.store.side_log("studio_change", {"request": request, "answer": "",
                                                  "transcript": [m for m in msgs if m["role"] in ("assistant", "tool")]},
                                chat_id, head)
            self.emit("toast", {"text": "Changes processed" + (f" ({', '.join(done)})" if done else "") + ". Check the cards and the story book.",
                                "long": True})
        self.emit("panels", chat_id)

    def variations(self, chat_id, card_id, field):
        self.run(self._variations, chat_id, card_id, field)

    def _variations(self, chat_id, card_id, field):
        card = self.cards.get(card_id)
        f = next((x for x in self.cards.visible_fields(card) if x["key"] == field), {"label": field, "type": "text"})
        c = self.prompt.ctx(chat_id)
        shape = "array" if f["type"] in ("list", "tags", "table") else "string"
        instr = (f"Beri 3 alternatif yang jelas berbeda untuk field '{f['label']}' ({f['type']}) di kartu #{card_id} "
                 f"({card['name']}), konsisten dengan kartu lain. Nilai sekarang: "
                 f"{json.dumps(card['data'].get(field), ensure_ascii=False)}\n"
                 f'Jawab HANYA JSON: {{"options": [<{shape}>, <{shape}>, <{shape}>]}}')
        acc = self.llm.complete(self.prompt.side(chat_id, instr), kwargs=self.prompt.kwargs(c),
                                sampling={**self.prompt.sampling(c), "temperature": 1.1}, max_tokens=12000,
                                tools=self.tools.specs(c), stop=self.stop)
        data = self._json(acc["content"]) or {}
        options = (data.get("options") or [])[:3]
        self.store.side_log("variations", {"card_id": card_id, "field": field, "options": options}, chat_id)
        self.emit("variations", {"card_id": card_id, "field": field, "label": f["label"], "options": options})

    def compare(self, chat_id, a, b):
        """Two branches side by side, from the message where they split."""
        pa, pb = self.store.path_ids(chat_id, a), self.store.path_ids(chat_id, b)
        k = 0
        while k < min(len(pa), len(pb)) and pa[k] == pb[k]:
            k += 1

        def side(ids):
            return [{"id": m["id"], "role": m["role"], "content": m["content"][:4000]}
                    for m in self.store.path(chat_id, ids=ids[k:k + 16]) if m["role"] in ("user", "assistant") and m["content"]]
        return {"split_at": k, "a": side(pa), "b": side(pb), "a_id": a, "b_id": b}

    def learn(self, chat_id, text):
        self.run(self._learn, chat_id, text)

    def _learn(self, chat_id, text):
        c = self.prompt.ctx(chat_id)
        code = Lang.code(c["cards"])
        lang = Lang.LABEL.get(code) or self.prompt.style(c).get("target_lang") or "a foreign language"
        acc = self.llm.complete(self.prompt.side(chat_id, LEARN_INSTRUCTION.format(lang=lang, text=text)),
                                kwargs=self.prompt.kwargs(c), sampling={"temperature": 0.3}, max_tokens=6000,
                                tools=self.tools.specs(c), stop=self.stop)
        data = self._json(acc["content"]) or {"translation": acc["content"]}
        self.store.side_log("learn", {"text": text, "lang": lang, **data}, chat_id)
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
            self.emit("recall", {"error": "Not enough older history to test yet."})
            return
        sample = random.sample(early, min(len(early), 6))
        text = "\n\n".join(f"[{m['role']}] {m['content'][:2500]}" for m in sample)
        qa = self._json(self.llm.complete(self.prompt.side(chat_id, RECALL_QUESTIONS.format(n=n, text=text)),
                                          kwargs=self.prompt.kwargs(c), sampling={"temperature": 0.4}, max_tokens=8000,
                                          tools=self.tools.specs(c))["content"]) or {}
        items = (qa.get("qa") or [])[:n]
        if not items:
            self.emit("recall", {"error": "Could not make the questions."})
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
        result = {"items": report, "score": sum(r["ok"] for r in report), "total": len(report)}
        self.store.side_log("recall_test", result, chat_id)
        self.emit("recall", result)

    def switch_model(self, preset, ctx, mtp=True, embed=True, embed_model=None):
        def job():
            def log(title, text, code):
                self.emit("status", f"{title}: {'done' if code == 0 else 'failed' if code else 'running…'}")
            try:
                SERVERS.start(preset, ctx, mtp=mtp, embed=embed, log=log, embed_model=embed_model)
                self.store.meta_set("server", {"preset": preset, "ctx": ctx, "mtp": mtp, "embed": embed,
                                               "embed_model": embed_model or SERVERS.state.get("embed_model") or "0.6B"})
                self.emit("toast", {"text": f"{preset} is starting. Wait for READY in the top bar."})
            except Exception as e:
                self.emit("toast", {"text": f"Model switch failed: {e}", "kind": "error"})
            finally:
                self.emit("status", "")
                self.emit("model", None)
        if self.busy:
            self.emit("toast", {"text": "Wait for the reply to finish first.", "kind": "warn"})
            return
        threading.Thread(target=job, daemon=True).start()
