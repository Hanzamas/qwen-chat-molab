import anywidget as _aw
import traitlets as _tl


class ChatWidget(_aw.AnyWidget):
    _esm = UI_ESM
    _css = UI_CSS
    boot = _tl.Dict({}).tag(sync=True)
    chats = _tl.List([]).tag(sync=True)
    chat = _tl.Dict({}).tag(sync=True)
    history = _tl.Dict({"items": [], "total": 0}).tag(sync=True)
    live = _tl.Dict({}).tag(sync=True)
    busy = _tl.Bool(False).tag(sync=True)
    status = _tl.Unicode("").tag(sync=True)
    toast = _tl.Dict({}).tag(sync=True)
    ctx = _tl.Dict({"used": 0, "max": 0}).tag(sync=True)
    panels = _tl.Dict({}).tag(sync=True)
    server = _tl.Dict({}).tag(sync=True)
    backup = _tl.Dict({}).tag(sync=True)
    library = _tl.Dict({}).tag(sync=True)
    card = _tl.Dict({}).tag(sync=True)
    story = _tl.Dict({}).tag(sync=True)
    aux = _tl.Dict({}).tag(sync=True)
    command = _tl.Dict({}).tag(sync=True)
    export = _tl.Dict({}).tag(sync=True)
    compose = _tl.Dict({}).tag(sync=True)
    queue = _tl.Int(0).tag(sync=True)


class ChatApp:
    """Bridges the widget and the Engine: commands from the browser in, state out."""

    def __init__(self):
        self.w = ChatWidget()
        self.engine = Engine(emit=self.on_event)
        self.limit = EngineView.DISPLAY_LIMIT
        self._live_t = 0.0
        self.w.boot = self.boot()
        self.w.observe(self.on_command, names="command")
        self.refresh_chats()
        chats = self.w.chats
        if chats:
            self.select(chats[0]["id"])
        threading.Thread(target=self._ticker, daemon=True).start()

    # ---------- state out ----------

    def boot(self):
        return {"presets": [{"name": n, "backend": p["backend"], "family": p["family"], "thinking": list(p["thinking"]),
                             "max_ctx": p["max_ctx"], "yarn_max": p["yarn_max"], "yarn_exp": p.get("yarn_exp", False),
                             "size_gb": p.get("size_gb")} for n, p in PRESETS.items()],
                "ctx_choices": CTX_CHOICES, "types": {t: CARDS.schema(t).get("label", t) for t in Cards.TYPE_ORDER},
                "roles": list(Stories.ROLES)}

    def refresh_chats(self):
        stories = {s["id"]: s["title"] for s in STORIES.list()}
        self.w.chats = [{**c, "story_title": stories.get(c["story_id"], "")} for c in STORE.chats()]

    def select(self, chat_id):
        chat = STORE.chat(chat_id) if chat_id else None
        self.engine.active_chat = chat_id or 0
        if not chat:
            self.w.chat, self.w.history, self.w.panels, self.w.story = {}, {"items": [], "total": 0}, {}, {}
            return
        self.limit = EngineView.DISPLAY_LIMIT
        self.w.chat = self.chat_info(chat)
        self.w.history = self.engine.display(chat_id, self.limit)
        self.w.panels = self.engine.panels(chat_id)
        self.w.story = self.story_info(chat)
        self.w.ctx = {"used": self.engine.last_used.get(chat_id, 0), "max": LLM_CLIENT.max_context() if SERVERS.ready() else 0}

    def chat_info(self, chat):
        return {"id": chat["id"], "title": chat["title"], "kind": chat["kind"], "story_id": chat["story_id"],
                "settings": {k: v for k, v in chat["settings"].items() if k not in ("studio", "avoid")},
                "system": chat["system"], "epoch": chat["epoch"],
                "drafts": (chat["settings"].get("studio") or {}).get("drafts") or {}}

    def story_info(self, chat):
        sid = chat.get("story_id")
        if chat["kind"] == "studio":
            drafts = (chat["settings"].get("studio") or {}).get("drafts") or {}
            cards = []
            for t, ids in drafts.items():
                for cid in ids if isinstance(ids, list) else [ids]:
                    c = CARDS.get(cid)
                    if c:
                        cards.append({"id": cid, "type": c["type"], "name": c["name"]})
            return {"studio": True, "cards": cards}
        if not sid:
            return {}
        s = STORIES.get(sid)
        links = []
        for l in STORIES.card_links(sid):
            c = CARDS.get(l["card_id"])
            if c:
                links.append({"id": c["id"], "role": l["role"], "name": c["name"], "version": l["version"],
                              "latest": c["version"], "avatar": c["avatar"]})
        return {"id": sid, "title": s["title"], "canon": s["data"]["canon"], "never_forget": s["data"]["never_forget"],
                "cards": links, "pending": [p["text"] for p in STORIES.pending_list(sid, chat["id"])]}

    def library_info(self):
        return {"cards": CARDS.list(), "stories": STORIES.list()}

    def card_info(self, card_id):
        c = CARDS.get(card_id)
        if not c:
            return {}
        return {**c, "fields": CARDS.visible_fields(c), "versions": CARDS.versions(card_id),
                "lore": CARDS.lore(card_id) if c["type"] in ("world", "character") else [],
                "timeline": CARDS.timeline(card_id) if c["type"] == "world" else [],
                "facts": STORE.q("SELECT id, claim, source_url, status FROM facts WHERE world_card_id = ? ORDER BY id DESC LIMIT 200",
                                 (card_id,)) if c["type"] == "world" else []}

    def on_event(self, kind, payload=None):
        w = self.w
        cur = (w.chat or {}).get("id")
        if kind == "live":
            if payload and payload.get("chat_id") not in (None, cur):
                return
            now = time.time()
            if payload and payload.get("active") and now - self._live_t < 0.08 and not payload.get("phase"):
                return
            self._live_t = now
            w.live = dict(payload or {}, tools=[dict(t) for t in (payload or {}).get("tools", [])])
        elif kind == "history":
            if payload == cur:
                w.history = self.engine.display(cur, self.limit)
                chat = STORE.chat(cur)
                if chat:
                    w.chat = self.chat_info(chat)
                    w.story = self.story_info(chat)
            self.refresh_chats()
        elif kind == "panels":
            if payload == cur:
                w.panels = self.engine.panels(cur)
        elif kind == "busy":
            w.busy = bool(payload)
        elif kind == "status":
            w.status = payload or ""
        elif kind == "toast":
            w.toast = {"n": time.time(), **payload}
        elif kind == "ctx":
            w.ctx = payload
        elif kind == "chats":
            self.refresh_chats()
        elif kind == "select":
            self.select(payload)
        elif kind == "compose":
            w.compose = {"n": time.time(), "text": payload}
        elif kind == "queue":
            w.queue = int(payload or 0)
        elif kind == "settings" and payload == cur:
            w.chat = self.chat_info(STORE.chat(cur))
        elif kind in ("learn", "recall"):
            w.aux = {"n": time.time(), "kind": kind, "data": payload}
        elif kind == "model":
            w.server = self.server_info()

    def server_info(self):
        st = SERVERS.status()
        gpu = Sys.gpu_line() if not CFG.BASE_URL else None
        return {"phase": "ready" if SERVERS.ready() else st["phase"],
                "preset": st.get("preset") or ("Server eksternal" if CFG.BASE_URL else None), "ctx": st.get("ctx"),
                "mtp": st.get("mtp"), "embed": st.get("embed"), "embed_ready": st.get("embed_ready"),
                "warnings": st.get("warnings") or [], "error": st.get("error") or "", "gpu": gpu,
                "installed": SERVERS.installed() or bool(CFG.BASE_URL)}

    def _ticker(self):
        while True:
            try:
                self.w.server = self.server_info()
                self.w.backup = {**BACKUP.status, "dirty": BACKUP.dirty()}
            except Exception:
                pass
            time.sleep(3)

    # ---------- commands in ----------

    def on_command(self, change):
        cmd = dict(change["new"] or {})
        action = cmd.pop("action", "")
        try:
            fn = getattr(self, "c_" + action, None)
            if fn is None:
                raise ValueError(f"perintah tidak dikenal: {action}")
            fn(**{k: v for k, v in cmd.items() if k != "n"})
        except Exception as e:
            self.w.toast = {"n": time.time(), "text": f"{type(e).__name__}: {e}", "kind": "error"}

    def _cur(self):
        return (self.w.chat or {}).get("id")

    # chat
    def c_send(self, text="", files=None, kind=None):
        self.engine.send(self._cur(), text, files or [], kind)

    def c_stop(self):
        self.engine.stop_now()

    def c_new(self, kind="chat"):
        cid = self.engine.new_chat(kind)
        self.select(cid)

    def c_select(self, chat_id):
        self.select(int(chat_id))

    def c_delete_chat(self, chat_id):
        STORE.delete_chat(int(chat_id))
        self.refresh_chats()
        if int(chat_id) == self._cur():
            self.select(self.w.chats[0]["id"] if self.w.chats else 0)

    def c_rename(self, chat_id, title):
        STORE.x("UPDATE chats SET title = ? WHERE id = ?", (title.strip()[:120] or "Tanpa judul", int(chat_id)))
        self.refresh_chats()
        if int(chat_id) == self._cur():
            self.w.chat = self.chat_info(STORE.chat(int(chat_id)))

    def c_load_more(self):
        self.limit += 150
        self.w.history = self.engine.display(self._cur(), self.limit)

    def c_settings(self, **updates):
        cid = self._cur()
        if not cid:
            return
        system = updates.pop("system", None)
        if system is not None:
            STORE.x("UPDATE chats SET system = ? WHERE id = ?", (system, cid))
            self.w.toast = {"n": time.time(), "text": "System prompt manual berlaku di epoch berikutnya (Terapkan sekarang)."}
        if updates:
            STORE.chat_settings(cid, **updates)
        self.w.chat = self.chat_info(STORE.chat(cid))

    def c_reroll(self, mid):
        self.engine.reroll(self._cur(), int(mid))

    def c_swipe(self, mid, dir):
        self.engine.swipe(self._cur(), int(mid), int(dir))

    def c_edit(self, mid, text):
        self.engine.edit(self._cur(), int(mid), text)

    def c_continue(self, mid):
        self.engine.continue_msg(self._cur(), int(mid))

    def c_delete_msg(self, mid):
        self.engine.delete_msg(self._cur(), int(mid))

    def c_branch(self, mid):
        self.engine.branch_here(self._cur(), int(mid))

    def c_goto(self, mid):
        STORE.set_head(self._cur(), STORE.deepest(self._cur(), int(mid)))
        self.on_event("history", self._cur())
        self.on_event("panels", self._cur())

    def c_branches(self):
        self.w.aux = {"n": time.time(), "kind": "branches", "data": self.engine.branches(self._cur())}

    def c_pin(self, mid, on=True):
        self.engine.pin(int(mid), on)
        self.on_event("history", self._cur())

    def c_chapter(self, mid, title):
        STORE.x("INSERT INTO chapters (chat_id, message_id, title, created) VALUES (?, ?, ?, ?)",
                (self._cur(), int(mid), title or "Bab baru", time.time()))
        self.on_event("history", self._cur())

    def c_choose(self, text):
        self.engine.choose(self._cur(), text)

    def c_time_skip(self, label):
        self.engine.time_skip(self._cur(), label)

    def c_compact(self):
        cid = self._cur()

        def job():
            c = PROMPT.ctx(cid)
            used = self.engine.compactor.maybe(cid, TOOLS.specs(c), TOOLS, lambda m: self.on_event("status", m), force=True)
            self.engine.last_used[cid] = used
            self.on_event("status", "")
            self.on_event("history", cid)
            self.on_event("ctx", {"used": used, "max": LLM_CLIENT.max_context()})
        self.engine.run(job)

    def c_apply_now(self):
        PROMPT.new_epoch(self._cur())
        self.on_event("history", self._cur())
        self.w.toast = {"n": time.time(), "text": "Prompt beku dibangun ulang dengan kartu dan buku cerita terbaru."}

    def c_continue_new(self):
        cid = self.engine.continue_in_new_chat(self._cur())
        self.select(cid)

    def c_search(self, q):
        q2 = TXT.fts_query(q)
        rows = STORE.q("SELECT m.id, m.chat_id, c.title, snippet(messages_fts, 0, '[', ']', '…', 14) AS snippet FROM messages_fts "
                       "JOIN messages m ON m.id = messages_fts.rowid JOIN chats c ON c.id = m.chat_id WHERE messages_fts MATCH ? "
                       "ORDER BY bm25(messages_fts) LIMIT 40", (q2,)) if q2 else []
        self.w.aux = {"n": time.time(), "kind": "search", "data": {"q": q, "results": rows}}

    def c_jump(self, chat_id, mid):
        chat_id, mid = int(chat_id), int(mid)
        if mid not in STORE.path_ids(chat_id):
            STORE.set_head(chat_id, STORE.deepest(chat_id, mid))
        self.select(chat_id)
        self.limit = 100000
        self.w.history = self.engine.display(chat_id, self.limit)
        self.w.aux = {"n": time.time(), "kind": "scroll_to", "data": mid}

    def c_prompt_view(self):
        self.w.aux = {"n": time.time(), "kind": "prompt", "data": self.engine.prompt_view(self._cur())}

    def c_export(self, fmt="md"):
        name, data = self.engine.export_story(self._cur(), fmt)
        self.w.export = {"n": time.time(), "name": name, "b64": base64.b64encode(data).decode()}

    def c_save_db(self):
        self.w.export = {"n": time.time(), "name": time.strftime("qwen-chat-%Y%m%d-%H%M%S.sqlite"),
                         "b64": base64.b64encode(STORE.export_bytes()).decode()}
        BACKUP.saved_rev = STORE.rev

    def c_load_db(self, b64):
        STORE.import_bytes(base64.b64decode(b64))
        self.refresh_chats()
        self.select(self.w.chats[0]["id"] if self.w.chats else 0)
        self.w.toast = {"n": time.time(), "text": "Database dimuat."}

    def c_impersonate(self, hint=""):
        self.engine.slash(self._cur(), "impersonate", hint)

    def c_learn(self, text):
        self.engine.learn(self._cur(), text)

    def c_vocab_add(self, term, translation="", note="", example=""):
        c = PROMPT.ctx(self._cur()) if self._cur() else None
        lang = PROMPT.style(c).get("target_lang", "") if c else ""
        ok = self.engine.vocab_add(term, translation, note, example, lang)
        self.w.toast = {"n": time.time(), "text": f"'{term}' {'masuk daftar kosakata' if ok else 'sudah ada'}."}

    def c_vocab(self):
        self.w.aux = {"n": time.time(), "kind": "vocab", "data": {"due": self.engine.vocab_due(),
                                                                  "all": STORE.q("SELECT * FROM vocab ORDER BY id DESC LIMIT 300")}}

    def c_vocab_review(self, vid, grade):
        self.engine.vocab_review(int(vid), int(grade))
        self.c_vocab()

    def c_vocab_delete(self, vid):
        STORE.x("DELETE FROM vocab WHERE id = ?", (int(vid),))
        self.c_vocab()

    def c_recall_test(self):
        self.engine.recall_test(self._cur())

    def c_fact_check(self, mid):
        self.engine.run(self.engine._fact_check, self._cur(), int(mid), True)

    # memory
    def c_memory(self, q=""):
        cid = self._cur()
        ctx = MEM.ctx_of(cid) if cid else {"chat_id": None, "story_id": None, "card_ids": []}
        rows = MEM.search(q, ctx, limit=50, kinds=("fact", "summary_core")) if q.strip() else STORE.q(
            "SELECT * FROM memories ORDER BY id DESC LIMIT 100")
        self.w.aux = {"n": time.time(), "kind": "memory", "data": {"q": q, "rows": rows, "log": MEM.log(limit=40)}}

    def c_memory_undo(self, log_id):
        MEM.undo(int(log_id))
        self.c_memory()

    def c_memory_delete(self, mid):
        MEM.forget(int(mid), MEM.ctx_of(self._cur()) if self._cur() else {})
        self.c_memory()

    # story
    def c_canon(self, section, text):
        sid = (self.w.story or {}).get("id")
        if sid:
            STORIES.canon_set(sid, section, text, self._cur())
            self.w.story = self.story_info(STORE.chat(self._cur()))

    def c_never_forget(self, items):
        sid = (self.w.story or {}).get("id")
        if sid:
            STORIES.never_forget(sid, items)
            STORIES.pending(sid, self._cur(), "Daftar 'jangan pernah lupa' diperbarui.")
            self.w.story = self.story_info(STORE.chat(self._cur()))

    def c_story_attach(self, card_id, role):
        sid = (self.w.story or {}).get("id")
        if sid:
            STORIES.attach(sid, int(card_id), role)
            STORIES.pending(sid, self._cur(), f"Kartu {role} dipasang: {CARDS.get(int(card_id))['name']}.")
            self.w.story = self.story_info(STORE.chat(self._cur()))

    def c_story_detach(self, card_id, role):
        sid = (self.w.story or {}).get("id")
        if sid:
            STORIES.detach(sid, int(card_id), role)
            self.w.story = self.story_info(STORE.chat(self._cur()))

    def c_start_story(self, cards, title="", greeting=0):
        ids = {k: (int(v) if not isinstance(v, list) else [int(x) for x in v]) for k, v in cards.items() if v}
        cid = self.engine.start_story(ids, title or None, int(greeting or 0))
        self.select(cid)

    def c_studio_start(self):
        cid = self.engine.new_chat("studio", "Studio")
        self.select(cid)

    def c_studio_finish(self, title=""):
        chat = STORE.chat(self._cur())
        drafts = (chat["settings"].get("studio") or {}).get("drafts") or {}
        ids = {k: v for k, v in drafts.items()}
        cid = self.engine.start_story(ids, title or None)
        self.select(cid)

    # cards
    def c_library(self):
        self.w.library = self.library_info()

    def c_card_open(self, card_id):
        self.w.card = self.card_info(int(card_id))

    def c_card_new(self, type):
        # New Gaya/GM cards start from the defaults, so a fresh card already plays sensibly.
        base = next((dict(data) for t, _, data in DEFAULT_CARDS if t == type), {})
        cid = CARDS.save(None, type, {**base, "title" if type == "scenario" else "name": "Baru"})
        self.w.library = self.library_info()
        self.w.card = self.card_info(cid)

    def c_card_save(self, card_id, data, avatar=None):
        c = CARDS.get(int(card_id))
        CARDS.save(int(card_id), c["type"], data, avatar=base64.b64decode(avatar) if avatar else None)
        self.w.card = self.card_info(int(card_id))
        self.w.library = self.library_info()
        chat = STORE.chat(self._cur()) if self._cur() else None
        if chat:
            self.w.story = self.story_info(chat)
        self.w.toast = {"n": time.time(), "text": "Kartu disimpan (versi baru)."}

    def c_card_delete(self, card_id):
        CARDS.delete(int(card_id))
        self.w.card = {}
        self.w.library = self.library_info()

    def c_card_version(self, card_id, version):
        c = CARDS.get(int(card_id), int(version))
        CARDS.save(int(card_id), c["type"], c["data"])
        self.w.card = self.card_info(int(card_id))

    def c_card_import(self, b64, name=""):
        cid = CARDS.import_any(base64.b64decode(b64), name)
        self.w.library = self.library_info()
        self.w.card = self.card_info(cid)
        self.w.toast = {"n": time.time(), "text": f"Kartu diimpor: {CARDS.get(cid)['name']}"}

    def c_card_export(self, card_id, fmt="qcard"):
        c = CARDS.get(int(card_id))
        data = CARDS.export_st_v2(int(card_id)) if fmt == "st" else CARDS.export_qcard(int(card_id))
        safe = re.sub(r"[^\w\- ]+", "", c["name"])[:60] or "kartu"
        self.w.export = {"n": time.time(), "name": f"{safe}.{'st' if fmt == 'st' else 'qcard'}.json",
                         "b64": base64.b64encode(json.dumps(data, ensure_ascii=False, indent=1).encode()).decode()}

    def c_lore_save(self, card_id, title, text, keys="", kind="istilah", core=False, entry_id=None):
        CARDS.lore_save(int(card_id), title, text, keys, kind, bool(core), int(entry_id) if entry_id else None)
        self.w.card = self.card_info(int(card_id))

    def c_lore_delete(self, card_id, entry_id):
        CARDS.lore_delete(int(entry_id))
        self.w.card = self.card_info(int(card_id))

    def c_timeline_save(self, card_id, at, title, text="", entry_id=None):
        if not World.parse_time(at):
            raise ValueError("Format waktu: YYYY-MM-DD HH:MM")
        CARDS.timeline_save(int(card_id), at, title, text, int(entry_id) if entry_id else None)
        self.w.card = self.card_info(int(card_id))

    def c_timeline_delete(self, card_id, entry_id):
        CARDS.timeline_delete(int(entry_id))
        self.w.card = self.card_info(int(card_id))

    def c_schema_get(self, type):
        self.w.aux = {"n": time.time(), "kind": "schema", "data": CARDS.schema(type)}

    def c_schema_save(self, schema):
        sch = CARDS.save_schema(schema if isinstance(schema, dict) else json.loads(schema))
        self.w.boot = self.boot()
        self.w.aux = {"n": time.time(), "kind": "schema", "data": sch}
        self.w.toast = {"n": time.time(), "text": f"Skema {sch['type']} disimpan (versi {sch['version']})."}

    # model
    def c_model_switch(self, preset, ctx, mtp=True, embed=True):
        p = PRESETS[preset]
        if int(ctx) > p["yarn_max"]:
            raise ValueError(f"{preset} maksimal {p['yarn_max']:,} token.")
        self.engine.switch_model(preset, int(ctx), bool(mtp), bool(embed))

    def c_model_stop(self):
        SERVERS.stop()
        self.w.server = self.server_info()


CHAT_APP = ChatApp()
mo.ui.anywidget(CHAT_APP.w)
