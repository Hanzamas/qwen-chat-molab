def _fn(name, description, properties, required=()):
    return {"type": "function", "function": {"name": name, "description": description,
            "parameters": {"type": "object", "properties": properties, "required": list(required)}}}


_S, _I, _N, _B = {"type": "string"}, {"type": "integer"}, {"type": "number"}, {"type": "boolean"}

TOOL_BASE = [
    _fn("web_search", "Search the web through a headless browser (Google, then Bing). Returns titles, URLs, snippets.",
        {"query": _S, "engine": {"type": "string", "enum": ["auto", "google", "bing"]}, "max_results": _I}, ["query"]),
    _fn("visit", "Open a web page (JavaScript runs) and return its readable text. screenshot=true also returns an image.",
        {"url": _S, "max_chars": _I, "screenshot": _B}, ["url"]),
    _fn("wiki_search", "Search Wikipedia. lang is a comma list of language codes, e.g. 'de,en'.",
        {"query": _S, "lang": _S}, ["query"]),
    _fn("wiki_read", "Read a Wikipedia article as plain text.", {"title": _S, "lang": _S, "max_chars": _I}, ["title"]),
    _fn("fact_lookup", "Look up the fact book (checked facts with sources) before searching the web.", {"query": _S}, ["query"]),
    _fn("fact_save", "Save a checked real-world fact with its source to the fact book.",
        {"claim": _S, "source_url": _S, "source_title": _S, "confidence": _N,
         "status": {"type": "string", "enum": ["terverifikasi", "diperdebatkan", "belum terverifikasi"]}}, ["claim"]),
    _fn("memory_search", "Search stored memories visible in this chat.", {"query": _S, "limit": _I}, ["query"]),
    _fn("memory_save", "Store a durable fact. scope: user (about the user, all chats), card (about a character, every "
        "story using its card; give card = character name), story (this story), chat (this chat only).",
        {"text": _S, "scope": {"type": "string", "enum": ["user", "card", "story", "chat"]}, "card": _S}, ["text"]),
    _fn("memory_update", "Replace the text of a memory that is no longer accurate.", {"id": _I, "text": _S}, ["id", "text"]),
    _fn("memory_forget", "Delete a memory by id.", {"id": _I}, ["id"]),
    _fn("history_search", "Keyword search over the original messages (also the parts already summarized).",
        {"query": _S, "scope": {"type": "string", "enum": ["chat", "all"]}, "limit": _I}, ["query"]),
    _fn("history_read", "Read original messages by position (1-based, inclusive) on the active path of a chat "
        "(default: this chat).", {"from": _I, "to": _I, "chat_id": _I}, ["from", "to"]),
    _fn("summary_read", "Read the full compaction summaries of a chat (default: this chat).", {"chat_id": _I}),
]

TOOL_RP = [
    _fn("world_advance", "Report how many in-world minutes passed in this turn.", {"minutes": _I, "summary": _S}, ["minutes"]),
    _fn("status_update", "Change status. subject: 'player' or a character name. changes: object of field -> value. "
        "Numeric player stats take a delta (+n / -n) or {\"set\": n}; list fields take {\"add\": x} or {\"remove\": x}.",
        {"subject": _S, "changes": {"type": "object"}, "reason": _S}, ["subject", "changes"]),
    _fn("roll", "Roll for an uncertain outcome. odds = chance of success 0..1 chosen for plausibility. "
        "The system's result is binding.", {"event": _S, "odds": _N}, ["event", "odds"]),
    _fn("world_event", "Record an off-screen event. known_to: names who know it (use 'player' for the player).",
        {"text": _S, "known_to": {"type": "array", "items": _S}, "public": _B}, ["text"]),
    _fn("canon_set", "Write a section of the story book (what is true now in this story). Empty text removes it.",
        {"section": _S, "text": _S}, ["section", "text"]),
    _fn("card_read", "Read the full card of a character in this story.", {"name": _S}, ["name"]),
]

TOOL_CARD_EDIT = [
    _fn("card_update", "Change one field of a card used by this story (character, persona, world, scenario, style, gm). "
        "Makes a new card version; it applies now through the system note and in the frozen prompt from the next epoch.",
        {"card": _S, "field": _S, "value": {}}, ["card", "field", "value"]),
]

TOOL_STUDIO = [
    _fn("card_draft_update", "Create or edit a card in this Studio. type: world, persona, character, scenario, style, gm. "
        "Give card_id to edit an existing draft; without it a new card of that type is created. field = schema key.",
        {"type": {"type": "string", "enum": ["world", "persona", "character", "scenario", "style", "gm"]},
         "card_id": _I, "field": _S, "value": {}}, ["type", "field", "value"]),
    _fn("lore_add", "Add a lore entry to a world card (kind: tempat, faksi, benda, peristiwa, istilah, ...).",
        {"world_card_id": _I, "title": _S, "text": _S, "keys": _S, "kind": _S, "core": _B}, ["title", "text"]),
    _fn("timeline_add", "Add a dated event to a world card's timeline (at: 'YYYY-MM-DD HH:MM').",
        {"world_card_id": _I, "at": _S, "title": _S, "text": _S}, ["at", "title"]),
]


class ToolBox:
    def __init__(self, store, cards, stories, world, memory, web):
        self.store, self.cards, self.stories, self.world, self.mem, self.web = store, cards, stories, world, memory, web

    def specs(self, c):
        kind = c["kind"]
        out = list(TOOL_BASE)
        if kind in ("rp", "group"):
            out += TOOL_RP
        if kind == "studio":
            out += TOOL_STUDIO
        return out

    def call(self, chat_id, message_id, name, raw_args):
        """Run one tool. Returns (result text, failed, media list)."""
        try:
            args = json.loads(raw_args or "{}")
            if not isinstance(args, dict):
                raise ValueError
        except ValueError:
            return json.dumps({"error": f"argumen bukan objek JSON: {str(raw_args)[:200]}"}), True, []
        try:
            fn = getattr(self, "t_" + name, None)
            if fn is None:
                return json.dumps({"error": f"tool tidak dikenal: {name}"}), True, []
            if "chat_id" in args:
                args["src_chat"] = args.pop("chat_id")
            if "from" in args:
                args["start"] = args.pop("from")
            res = fn(chat_id, message_id, **args)
            media = []
            if isinstance(res, tuple):
                res, media = res
            text = res if isinstance(res, str) else json.dumps(res, ensure_ascii=False)
            return text[:30000], '"error"' in text[:200], media
        except TypeError as e:
            return json.dumps({"error": f"argumen salah: {e}"}), True, []
        except Exception as e:
            return json.dumps({"error": f"{type(e).__name__}: {str(e)[:300]}"}), True, []

    # ---------- helpers ----------

    def _story(self, chat_id):
        chat = self.store.chat(chat_id)
        return chat.get("story_id"), self.stories.cards_of(chat.get("story_id")) if chat.get("story_id") else {"character": []}

    def _world_id(self, chat_id):
        _, cards = self._story(chat_id)
        if cards.get("world"):
            return cards["world"]["id"]
        drafts = ((self.store.chat(chat_id) or {}).get("settings", {}).get("studio") or {}).get("drafts") or {}
        w = drafts.get("world")
        return (w[0] if isinstance(w, list) else w) if w else None

    # ---------- web and facts ----------

    def t_web_search(self, chat_id, mid, query, engine="auto", max_results=8):
        return self.web.web_search(query, engine, max_results)

    def t_visit(self, chat_id, mid, url, max_chars=15000, screenshot=False):
        text, shot = self.web.visit(url, max_chars, bool(screenshot))
        media = [{"kind": "image", "mime": "image/jpeg", "name": f"screenshot {url[:80]}", "data": shot}] if shot else []
        return text, media

    def t_wiki_search(self, chat_id, mid, query, lang=""):
        langs = [x.strip() for x in (lang or "").split(",") if x.strip()]
        if not langs:
            _, cards = self._story(chat_id)
            wl = ((cards.get("world") or {}).get("data") or {}).get("wiki_lang") or ""
            langs = [x.strip() for x in wl.split(",") if x.strip()] or ["id", "en"]
        return self.web.wiki_search(query, langs)

    def t_wiki_read(self, chat_id, mid, title, lang="en", max_chars=12000):
        return self.web.wiki_read(title, lang or "en", max_chars)

    def t_fact_lookup(self, chat_id, mid, query):
        rows = self.mem.fact_lookup(query, self._world_id(chat_id))
        return {"results": rows} if rows else {"results": [], "note": "Belum ada di buku fakta. Cari dengan wiki_search/web_search."}

    def t_fact_save(self, chat_id, mid, claim, source_url="", source_title="", confidence=0.8, status="terverifikasi"):
        return self.mem.fact_save(claim, source_url, source_title, self._world_id(chat_id), confidence, status)

    # ---------- memory and history ----------

    def t_memory_search(self, chat_id, mid, query, limit=8):
        rows = self.mem.search(query, self.mem.ctx_of(chat_id), limit=int(limit), kinds=("fact", "summary_core"))
        if not rows:
            return {"results": [], "note": "Tidak ada yang cocok."}
        return {"results": [{"id": r["id"], "scope": r["scope"], "text": r["text"]} for r in rows]}

    def t_memory_save(self, chat_id, mid, text, scope="", card=""):
        ctx = self.mem.ctx_of(chat_id)
        card_id = self.cards.find("character", card) if card else None
        if scope == "card" and not card_id:
            return {"error": "scope card butuh nama tokoh yang ada di kartu (field card)."}
        return self.mem.save(text, scope or ("story" if ctx.get("story_id") else "user"), ctx, card_id=card_id)

    def t_memory_update(self, chat_id, mid, id, text):
        return self.mem.update(int(id), text, self.mem.ctx_of(chat_id))

    def t_memory_forget(self, chat_id, mid, id):
        return self.mem.forget(int(id), self.mem.ctx_of(chat_id))

    def t_history_search(self, chat_id, mid, query, scope="chat", limit=10):
        """Hybrid: BM25 over the original messages plus vector search when the embedder runs (RRF)."""
        q = TXT.fts_query(query)
        rows = []
        if q:
            sql = ("SELECT m.id, m.chat_id, m.role, snippet(messages_fts, 0, '[', ']', '…', 16) AS snippet "
                   "FROM messages_fts JOIN messages m ON m.id = messages_fts.rowid WHERE messages_fts MATCH ?")
            args = [q]
            if scope != "all":
                sql += " AND m.chat_id = ?"
                args.append(chat_id)
            rows = self.store.q(sql + " ORDER BY bm25(messages_fts) LIMIT 40", args)
        emb = self.mem.emb
        if emb.ready():
            ids_sql = "SELECT id FROM messages" + ("" if scope == "all" else " WHERE chat_id = ?")
            allowed_msgs = {r["id"] for r in self.store.q(ids_sql, () if scope == "all" else (chat_id,))}
            hits = emb.search("msg", query, limit=60, allowed={m * 100 + i for m in allowed_msgs for i in range(20)})
            vec_ids = list(dict.fromkeys(ref // 100 for ref, s in hits if s > 0.35))
            by_id = {r["id"]: r for r in rows}
            for mid2 in vec_ids:
                if mid2 not in by_id:
                    m = self.store.msg(mid2)
                    if m:
                        by_id[mid2] = {"id": m["id"], "chat_id": m["chat_id"], "role": m["role"], "snippet": m["content"][:240]}
            order = Memory.rrf([r["id"] for r in rows], vec_ids)
            rows = [by_id[i] for i in order if i in by_id]
        rows = rows[:int(limit)]
        if not rows:
            return {"results": []}
        paths = {}
        for r in rows:
            if r["chat_id"] not in paths:
                paths[r["chat_id"]] = {m: i + 1 for i, m in enumerate(self.store.path_ids(r["chat_id"]))}
            r["position"] = paths[r["chat_id"]].get(r["id"])
            r["note"] = "" if r["position"] else "di cabang lain"
        return {"results": rows}

    def t_history_read(self, chat_id, mid, to, start=1, src_chat=None):
        src = int(src_chat or chat_id)
        start = int(start or 1)
        ids = self.store.path_ids(src)[max(0, start - 1):int(to)]
        out, budget = [], 40000
        for m in self.store.path(src, ids=ids):
            item = {"position": start + len(out), "role": m["role"], "content": m["content"][:budget]}
            if m["reasoning"]:
                item["reasoning"] = m["reasoning"][:2000]
            budget -= len(item["content"])
            out.append(item)
            if budget <= 0:
                out.append({"note": "dipotong; baca rentang yang lebih kecil"})
                break
        return {"chat_id": src, "messages": out}

    def t_summary_read(self, chat_id, mid, src_chat=None):
        src = int(src_chat or chat_id)
        rows = self.store.q("SELECT level, text FROM summaries WHERE chat_id = ? ORDER BY id", (src,))
        return {"chat_id": src, "summaries": rows} if rows else {"chat_id": src, "summaries": [], "note": "belum ada ringkasan"}

    # ---------- world ----------

    def t_world_advance(self, chat_id, mid, minutes, summary=""):
        self.world.advance(chat_id, mid, int(minutes), summary)
        return {"ok": True, "minutes": int(minutes)}

    def t_status_update(self, chat_id, mid, subject, changes, reason=""):
        done = self.world.status_update(chat_id, mid, subject or "player", changes, reason)
        return {"updated": done}

    def t_roll(self, chat_id, mid, event, odds):
        r = self.world.roll(chat_id, mid, event, odds)
        verdict = "BERHASIL" if r["success"] else "GAGAL"
        return {**r, "result": f"{verdict} (peluang {r['odds']:.0%}). Hasil ini wajib diikuti."}

    def t_world_event(self, chat_id, mid, text, known_to=None, public=False):
        st = self.world.state(chat_id, self.store.path_ids(chat_id))
        eid = self.world.add_world_event(chat_id, mid, st["time"], text, known_to or [], public)
        return {"saved": eid}

    def t_canon_set(self, chat_id, mid, section, text):
        sid, _ = self._story(chat_id)
        if not sid:
            return {"error": "chat ini tidak terhubung ke cerita"}
        self.stories.canon_set(sid, section, text, chat_id)
        return {"ok": True, "note": "Berlaku sekarang lewat catatan sistem; masuk prompt beku di epoch berikutnya."}

    def t_card_read(self, chat_id, mid, name):
        _, cards = self._story(chat_id)
        for c in cards["character"] + [cards.get(r) for r in ("persona", "world", "scenario") if cards.get(r)]:
            names = [c["name"]] + list(c["data"].get("aliases") or [])
            if any(n and n.lower() == (name or "").lower() for n in names):
                return self.cards.render(c, mode="all", limit=12000)
        return {"error": f"tidak ada kartu bernama {name} di cerita ini"}

    def t_card_update(self, chat_id, mid, card, field, value):
        sid, cards = self._story(chat_id)
        if not sid:
            return {"error": "chat ini tidak terhubung ke cerita"}
        pool = cards["character"] + [cards[r] for r in ("persona", "world", "scenario", "style", "gm") if cards.get(r)]
        target = None
        for c in pool:
            names = [c["name"]] + list(c["data"].get("aliases") or [])
            if any(n and n.lower() == (card or "").lower() for n in names) or (card or "").lower() == c["type"]:
                target = c
                break
        if not target:
            return {"error": f"kartu '{card}' tidak dipakai cerita ini. Pilihan: {', '.join(c['name'] for c in pool)}"}
        keys = {f["key"] for f in self.cards.schema(target["type"])["fields"]}
        if field not in keys and field not in target["data"]:
            return {"error": f"field '{field}' tidak ada di skema {target['type']}. Field: {', '.join(sorted(keys))}"}
        self.cards.set_field(target["id"], field, value)
        shown = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
        self.stories.pending(sid, chat_id, f"Kartu {target['name']} · {field}: {shown[:600]}")
        return {"card_id": target["id"], "version": self.cards.get(target["id"])["version"], "ok": True}

    # ---------- studio ----------

    def _drafts(self, chat_id):
        chat = self.store.chat(chat_id)
        st = chat["settings"].get("studio") or {}
        return st.setdefault("drafts", {}), st

    def t_card_draft_update(self, chat_id, mid, type, field, value, card_id=None):
        drafts, st = self._drafts(chat_id)
        if card_id:
            if not self.cards.get(int(card_id)):
                return {"error": f"kartu #{card_id} tidak ada"}
            cid = self.cards.set_field(int(card_id), field, value)
        else:
            existing = drafts.get(type)
            if type != "character" and existing:
                cid = self.cards.set_field(existing if isinstance(existing, int) else existing[0], field, value)
            else:
                cid = self.cards.save(None, type, {field: value})
                if type == "character":
                    drafts.setdefault(type, [])
                    if isinstance(drafts[type], int):
                        drafts[type] = [drafts[type]]
                    drafts[type].append(cid)
                else:
                    drafts[type] = cid
                self.store.chat_settings(chat_id, studio=st)
        return {"card_id": cid, "field": field, "ok": True}

    def t_lore_add(self, chat_id, mid, title, text, keys="", kind="istilah", core=False, world_card_id=None):
        wid = int(world_card_id) if world_card_id else self._world_id(chat_id)
        if not wid:
            return {"error": "buat kartu dunia dulu (card_draft_update type=world)"}
        return {"saved": self.cards.lore_save(wid, title, text, keys, kind, bool(core))}

    def t_timeline_add(self, chat_id, mid, at, title, text="", world_card_id=None):
        wid = int(world_card_id) if world_card_id else self._world_id(chat_id)
        if not wid:
            return {"error": "buat kartu dunia dulu (card_draft_update type=world)"}
        if not World.parse_time(at):
            return {"error": "format waktu harus YYYY-MM-DD HH:MM"}
        return {"saved": self.cards.timeline_save(wid, at, title, text)}


TOOLS = ToolBox(STORE, CARDS, STORIES, WORLD, MEM, WEB)
