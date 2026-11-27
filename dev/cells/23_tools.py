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
        "story using its card; give card = character name), story (this story), chat (this chat only). "
        "importance 0..1 (default 0.5): 0.9 for facts that must never be lost, 0.2 for small details.",
        {"text": _S, "scope": {"type": "string", "enum": ["user", "card", "story", "chat"]}, "card": _S, "importance": _N},
        ["text"]),
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
    _fn("roll", "Roll for an uncertain outcome. Give skill (as on the card, e.g. 'Bahasa Jerman') and difficulty: the system "
        "computes the chance from that skill level and the roller's condition (injuries, fatigue). who: 'player' (default) "
        "or a character name. odds 0..1 only when no skill fits. The system's result is binding.",
        {"event": _S, "skill": _S, "difficulty": {"type": "string", "enum": ["mudah", "sedang", "sulit", "sangat sulit"]},
         "who": _S, "odds": _N}, ["event"]),
    _fn("world_event", "Record an off-screen event. known_to: names who know it (use 'player' for the player). "
        "Everyone in known_to also gets it in their memory.",
        {"text": _S, "known_to": {"type": "array", "items": _S}, "public": _B}, ["text"]),
    _fn("knowledge_add", "Record what characters now know or believe (who: names; 'player' = the player's character). Use "
        "it for what they witnessed, were told, overheard, guessed or misunderstood. truth: benar, keliru (they believe "
        "something false: a lie, a wrong rumor), belum pasti. Characters act only on what is in their memory.",
        {"who": {"type": "array", "items": _S}, "text": _S,
         "kind": {"type": "string", "enum": list(Knowledge.KINDS)},
         "source": {"type": "string", "enum": list(Knowledge.SOURCES)}, "from": _S,
         "truth": {"type": "string", "enum": list(Knowledge.TRUTH)}, "importance": _N}, ["who", "text"]),
    _fn("thread_open", "Open a story thread to keep track of: a promise, an appointment (with due time), a mystery, a clue, a "
        "debt, a grudge, a plan. due: 'YYYY-MM-DD HH:MM' world time, optional.",
        {"kind": {"type": "string", "enum": list(Threads.KINDS)}, "title": _S, "text": _S,
         "who": {"type": "array", "items": _S}, "due": _S}, ["kind", "title"]),
    _fn("thread_close", "Close a story thread when it is resolved, failed or dropped.",
        {"id": _I, "status": {"type": "string", "enum": list(Threads.CLOSED)}, "note": _S}, ["id", "status"]),
    _fn("story_search", "Search everything known about this story by meaning, not only by words: memories, the story book, "
        "what characters know, lore, cards, summaries of earlier parts, past world events.", {"query": _S, "limit": _I}, ["query"]),
    _fn("relationship", "Change how a character feels about another (b: a name or 'player'). delta -20..20 with the reason "
        "(what happened). Small, earned changes; big swings only for big events.",
        {"a": _S, "b": _S, "delta": _N, "reason": _S}, ["a", "b", "delta", "reason"]),
    _fn("tell", "A character tells others something (true or a lie). It lands in the listeners' memory.",
        {"from": _S, "to": {"type": "array", "items": _S}, "text": _S, "truthful": _B}, ["from", "to", "text"]),
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
        self.on_call = None  # set by the chat app: called with (chat_id, tool name) after every tool call

    def specs(self, c):
        kind = c["kind"]
        out = list(TOOL_BASE)
        if kind in ("rp", "group"):
            out += TOOL_RP
        if kind == "studio":
            out += TOOL_STUDIO
        return out

    FIELD_KEY = re.compile(r"^[A-Za-z_][\w-]{0,63}$")

    def call(self, chat_id, message_id, name, raw_args, allowed=None):
        """Run one tool. Returns (result text, failed, media list). allowed: names offered to the model;
        a tool it was not offered is refused even if it exists."""
        if allowed is not None and name not in allowed:
            return json.dumps({"error": f"tool {name} tidak tersedia di sini"}), True, []
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
            try:
                res = fn(chat_id, message_id, **args)
            finally:
                if self.on_call:
                    try:
                        self.on_call(chat_id, name)
                    except Exception:
                        pass
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

    def t_memory_save(self, chat_id, mid, text, scope="", card="", importance=0.5):
        ctx = self.mem.ctx_of(chat_id)
        card_id = self.cards.find("character", card) if card else None
        if scope == "card" and not card_id:
            return {"error": "scope card butuh nama tokoh yang ada di kartu (field card)."}
        return self.mem.save(text, scope or ("story" if ctx.get("story_id") else "user"), ctx, card_id=card_id,
                             message_id=mid, importance=importance)

    def t_memory_update(self, chat_id, mid, id, text):
        return self.mem.update(int(id), text, self.mem.ctx_of(chat_id), message_id=mid)

    def t_memory_forget(self, chat_id, mid, id):
        return self.mem.forget(int(id), self.mem.ctx_of(chat_id), message_id=mid)

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
        subject = self._holder(chat_id, subject) or "player"  # "Lotte", "pemain", the persona's name: one key each
        done = self.world.status_update(chat_id, mid, subject, changes, reason)
        return {"updated": done}

    DIFFICULTY = {"mudah": 0.2, "sedang": 0.0, "sulit": -0.2, "sangat sulit": -0.35}

    def roll_odds(self, chat_id, who="player", skill="", difficulty="sedang", odds=None):
        """Chance of success: skill level from the card (persona for the player), difficulty, and condition from the
        world state. Returns (odds, reasons)."""
        holder = self._holder(chat_id, who or "player") or "player"
        _, cards = self._story(chat_id)
        card = (cards or {}).get("persona") if holder == "player" else next(
            (ch for ch in (cards or {}).get("character", []) if ch["name"] == holder), None)
        why = []
        if skill:
            rows = (card or {}).get("data", {}).get("skill_levels") or []
            want = skill.strip().lower()
            hit = next((r for r in rows if r and str(r[0]).strip().lower() == want), None) or next(
                (r for r in rows if r and (want in str(r[0]).lower() or str(r[0]).lower() in want)), None)
            try:
                base = float(str(hit[1]).replace(",", ".")) / 100 if hit and len(hit) > 1 else 0.4
            except ValueError:
                base = 0.4
            lv = Lang.of(cards, self.world.state(chat_id, self.store.path_ids(chat_id)), self.world.start_time(cards)) \
                if holder == "player" and cards else None
            if lv and Lang.is_skill(skill, lv["code"]):  # the language level grows in play: the dice use the grown one
                base, hit = lv["value"] / 100, [f"{lv['label']} {lv['band']}"]
            why.append(f"{hit[0]} {base:.0%}" if hit else f"{skill}: tidak terlatih 40%")
            mod = self.DIFFICULTY.get(difficulty or "sedang", 0.0)
            if mod:
                why.append(f"{difficulty} {mod:+.0%}")
            p = base + mod
        else:
            try:
                p = float(odds) if odds is not None else 0.5
            except (TypeError, ValueError):
                p = 0.5
            why.append(f"peluang dasar {p:.0%}")
        st = self.world.state(chat_id, self.store.path_ids(chat_id))
        status = st["status"].get(holder) or {}
        keadaan = str(status.get("keadaan") or "").lower()
        if keadaan in ("pingsan", "mati"):
            return 0.0, why + [f"{keadaan}: tidak bisa"]
        if keadaan == "terluka parah":
            p -= 0.2
            why.append("terluka parah -20%")
        injuries = status.get("injuries") or []
        if isinstance(injuries, list) and injuries:
            cut = min(0.2, 0.05 * len(injuries))
            p -= cut
            why.append(f"{len(injuries)} luka -{cut:.0%}")
        if holder == "player":
            for s in st["stats"]:
                key, v = s["key"].lower(), s["value"]
                lo, hi = s["min"] if s["min"] is not None else 0, s["max"] if s["max"] is not None else 100
                share = (v - lo) / (hi - lo) if hi > lo else 0.5
                if any(k in key for k in ("energi", "energy", "stamina")) and share < 0.4:
                    cut = 0.15 if share < 0.2 else 0.05
                    p -= cut
                    why.append(f"{s['label']} rendah -{cut:.0%}")
                if any(k in key for k in ("lapar", "haus", "hunger", "thirst", "lelah", "capek")) and share > 0.8:
                    p -= 0.05
                    why.append(f"{s['label']} tinggi -5%")
        return min(max(p, 0.03), 0.97), why

    def t_roll(self, chat_id, mid, event, odds=None, skill="", difficulty="sedang", who="player"):
        p, why = self.roll_odds(chat_id, self._holder(chat_id, who) or "player", skill, difficulty, odds)
        r = self.world.roll(chat_id, mid, event, p)
        cards = self._story(chat_id)[1] or {}
        if skill and (self._holder(chat_id, who) or "player") == "player" and Lang.is_skill(skill, Lang.code(cards)):
            Lang.gain(self.world, chat_id, mid, self.world.state(chat_id, self.store.path_ids(chat_id)),
                      2 if r["success"] else 0.5, "roll bahasa")
        verdict = "BERHASIL" if r["success"] else "GAGAL"
        return {**r, "why": why, "result": f"{verdict} (peluang {r['odds']:.0%}: {', '.join(why)}). Hasil ini wajib diikuti."}

    def _holder(self, chat_id, name):
        """Card name for a character name or alias; 'player' for the player or the persona's name."""
        n = str(name or "").strip()
        if not n:
            return ""
        if n.lower() in ("player", "pemain", "kamu", "you"):
            return "player"
        _, cards = self._story(chat_id)
        persona = cards.get("persona") if cards else None
        if persona and n.lower() == persona["name"].lower():
            return "player"
        chars = (cards or {}).get("character", [])
        for ch in chars:
            if n.lower() in [ch["name"].lower()] + [str(a).lower() for a in ch["data"].get("aliases") or []]:
                return ch["name"]
        # a first name alone, when exactly one card (or the persona) has it
        first = n.lower().split()[0]
        hits = [ch["name"] for ch in chars if ch["name"].lower().split()[0] == first]
        if persona and persona["name"].lower().split()[0] == first:
            hits.append("player")
        if len(hits) == 1 and len(n.split()) == 1:
            return hits[0]
        return n  # someone without a card: kept as written

    def _holders(self, chat_id, names):
        names = names if isinstance(names, list) else [x for x in re.split(r"[,;]", str(names or ""))]
        return [h for h in (self._holder(chat_id, x) for x in names) if h]

    def t_world_event(self, chat_id, mid, text, known_to=None, public=False):
        st = self.world.state(chat_id, self.store.path_ids(chat_id))
        holders = self._holders(chat_id, known_to or [])
        eid = self.world.add_world_event(chat_id, mid, st["time"], text, holders, public)
        if holders:
            KNOW.add(chat_id, mid, holders, text, source="lihat sendiri", world_time=st["time_text"])
        return {"saved": eid}

    def t_knowledge_add(self, chat_id, mid, who, text, kind="fakta", source="lihat sendiri", truth="benar",
                        importance=0.5, **kw):
        holders = self._holders(chat_id, who)
        if not holders:
            return {"error": "who kosong"}
        st = self.world.state(chat_id, self.store.path_ids(chat_id))
        ids = KNOW.add(chat_id, mid, holders, text, kind, source, kw.get("from") or kw.get("start") or "", truth, importance,
                       st["time_text"])
        return {"saved": ids, "who": holders}

    @staticmethod
    def _rank(query, kind, rows, text_of, limit=4):
        """Rows ordered by meaning when the embedder runs, otherwise by shared words."""
        if not rows:
            return []
        by_id = {r["id"]: r for r in rows}
        if EMB.ready():
            found = [by_id[i] for i, s in EMB.search(kind, query, limit=limit, allowed=set(by_id)) if s > 0.3]
            if found:
                return found  # nothing embedded yet for this kind: fall back to words
        scored = sorted(((TXT.overlap(query, text_of(r)), r["id"]) for r in rows), reverse=True)
        return [by_id[i] for n, i in scored[:limit] if n > 0]

    def t_story_search(self, chat_id, mid, query, limit=10):
        ctx = self.mem.ctx_of(chat_id)
        vis, sid = ctx["visible"], ctx["story_id"]
        out = [{"type": "memory", "id": r["id"], "text": r["text"][:500]}
               for r in self.mem.search(query, ctx, limit=4, kinds=("fact", "summary_core"))]
        out += [{"type": "ingatan", "holder": r["holder"], "text": KNOW.line(r)}
                for r in self._rank(query, "know", KNOW._rows(chat_id), lambda r: r["text"])]
        if sid:
            canon = self.stories.canon(sid, vis, chat_id)
            logs = [r for r in self.store.q("SELECT id, message_id, section, text FROM canon_log WHERE story_id = ? AND text != ''",
                                            (sid,)) if r["message_id"] in vis and canon.get(r["section"]) == r["text"]]
            hit = {r["section"] for r in self._rank(query, "canon", logs, lambda r: f"{r['section']}: {r['text']}", 3)}
            hit |= {k for k, v in canon.items() if TXT.overlap(query, f"{k} {v}") >= 2}
            out += [{"type": "buku cerita", "section": k, "text": canon[k][:600]} for k in list(hit)[:3]]
        card_ids = ctx["card_ids"]
        if card_ids:
            lore = self.store.q(f"SELECT * FROM lore_entries WHERE card_id IN ({','.join('?' * len(card_ids))})", card_ids)
            out += [{"type": "lore", "title": r["title"], "known_to": r.get("known_to", ""), "text": r["text"][:500]}
                    for r in self._rank(query, "lore", lore, lambda r: f"{r['title']} {r['text']}", 3)]
            cards = [c for c in (self.cards.get(i) for i in card_ids) if c]
            out += [{"type": "kartu", "name": c["name"], "text": self.cards.render(c, mode="all", limit=600)}
                    for c in self._rank(query, "card", cards, lambda c: self.cards.render(c, mode="all"), 2)]
        sums = [s for s in self.store.q("SELECT id, node_id, text FROM summaries WHERE chat_id = ?", (chat_id,)) if s["node_id"] in vis]
        out += [{"type": "ringkasan", "id": s["id"], "text": s["text"][:800]} for s in self._rank(query, "sum", sums, lambda s: s["text"], 2)]
        events = [e for e in self.store.q("SELECT id, message_id, world_time, text FROM world_events WHERE chat_id IN "
                                          f"({','.join('?' * len(self.store.lineage(chat_id)))})", self.store.lineage(chat_id))
                  if not e["message_id"] or e["message_id"] in vis]
        out += [{"type": "kejadian", "time": e["world_time"], "text": e["text"][:400]}
                for e in self._rank(query, "event", events, lambda e: e["text"], 3)]
        return {"results": out[:max(1, min(int(limit), 30))]} if out else {"results": [], "note": "Tidak ketemu."}

    def t_relationship(self, chat_id, mid, a, b, delta, reason=""):
        ha, hb = self._holder(chat_id, a), self._holder(chat_id, b)
        if not ha or not hb or ha == hb:
            return {"error": "a dan b harus dua tokoh berbeda"}
        st = self.world.state(chat_id, self.store.path_ids(chat_id))
        RELATIONS.change(chat_id, mid, ha, hb, delta, reason, st["time_text"])
        s = RELATIONS.scores(chat_id).get((ha, hb), {"score": 0})["score"]
        return {"a": ha, "b": hb, "score": s, "feeling": Relations.word(s)}

    def t_thread_open(self, chat_id, mid, kind, title, text="", who=None, due=""):
        st = self.world.state(chat_id, self.store.path_ids(chat_id))
        tid = THREADS.open(chat_id, mid, kind, title, text, self._holders(chat_id, who or []) or (who or ""), due, st["time_text"])
        return {"opened": tid}

    def t_thread_close(self, chat_id, mid, id, status="selesai", note=""):
        if not any(r["id"] == int(id) for r in THREADS.list(chat_id, include_closed=True)):
            return {"error": f"benang #{id} tidak ada di cerita ini"}
        THREADS.close(chat_id, mid, int(id), status, note)
        return {"closed": int(id), "status": status}

    def t_tell(self, chat_id, mid, text, to, truthful=True, **kw):
        speaker = self._holder(chat_id, kw.get("from") or kw.get("start") or "")
        holders = [h for h in self._holders(chat_id, to) if h != speaker]
        if not holders:
            return {"error": "to kosong"}
        st = self.world.state(chat_id, self.store.path_ids(chat_id))
        ids = KNOW.add(chat_id, mid, holders, text, "fakta", "diberi tahu", speaker,
                       "benar" if truthful else "keliru", 0.5, st["time_text"])
        return {"saved": ids, "to": holders}

    def t_canon_set(self, chat_id, mid, section, text):
        sid, _ = self._story(chat_id)
        if not sid:
            return {"error": "chat ini tidak terhubung ke cerita"}
        # logged on this branch (mid); a turn always has one, a side task passes the head
        self.stories.canon_set(sid, section, text, chat_id, message_id=mid or (self.store.chat(chat_id) or {}).get("head_id"))
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
        if not self.FIELD_KEY.match(str(field or "")) or (field not in keys and field not in target["data"]):
            return {"error": f"field '{field}' tidak ada di skema {target['type']}. Field: {', '.join(sorted(keys))}"}
        self.cards.set_field(target["id"], field, value)
        report = self._field_report(target["id"], field, value)
        if report.get("error"):
            return {"card_id": target["id"], **report}
        shown = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
        self.stories.pending(sid, chat_id, f"Kartu {target['name']} · {field}: {shown[:600]}")
        return {"card_id": target["id"], "version": self.cards.get(target["id"])["version"], "ok": True, **report}

    def _field_report(self, card_id, field, value):
        card = self.cards.get(card_id)
        f = next((x for x in self.cards.schema(card["type"])["fields"] if x["key"] == field), None)
        stored = card["data"].get(field)
        if f and f.get("type") == "datetime" and stored and not TXT.parse_datetime(stored):
            return {"error": f"'{field}' tidak terbaca sebagai tanggal. Tulis YYYY-MM-DD HH:MM, misalnya 1916-07-01 06:30."}
        if f and f.get("type") == "select" and stored and stored not in (f.get("options") or []):
            return {"note": f"'{stored}' bukan pilihan {field}. Pilihan: {', '.join(f.get('options') or [])}."}
        if not f or f.get("type") != "table":
            return {}
        rows = card["data"].get(field) or []
        if value not in (None, "", [], {}) and not rows:
            return {"error": f"Tabel '{field}' kosong setelah dibaca. Kirim array of array sesuai kolom "
                             f"{f.get('columns')}, satu array per baris."}
        return {"rows": len(rows), "columns": f.get("columns"), "first_row": rows[0] if rows else None}

    # ---------- studio ----------

    def _drafts(self, chat_id):
        chat = self.store.chat(chat_id)
        st = chat["settings"].get("studio") or {}
        return st.setdefault("drafts", {}), st

    def t_card_draft_update(self, chat_id, mid, type, field, value, card_id=None):
        if type not in Cards.TYPE_ORDER:
            return {"error": f"jenis kartu '{type}' tidak ada. Pilihan: {', '.join(Cards.TYPE_ORDER)}"}
        if not self.FIELD_KEY.match(str(field or "")):
            return {"error": "nama field hanya huruf, angka, _ atau - (lihat skema)"}
        drafts, st = self._drafts(chat_id)
        if card_id:
            card = self.cards.get(int(card_id))
            if not card:
                return {"error": f"kartu #{card_id} tidak ada"}
            if card["type"] != type:
                return {"error": f"kartu #{card_id} ({card['name']}) bertipe {card['type']}, bukan {type}. "
                                 f"Tanpa card_id, card_draft_update membuat kartu {type} baru."}
            cid = self.cards.set_field(int(card_id), field, value)
            ids = drafts.get(type)
            ids = ids if isinstance(ids, list) else [ids] if ids else []
            if cid not in ids:  # a library card edited here is part of this studio session from now on
                drafts[type] = ids + [cid] if type == "character" else cid
                self.store.chat_settings(chat_id, studio=st)
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
        report = self._field_report(cid, field, value)
        card = self.cards.get(cid)
        if not card["data"].get("name") and not card["data"].get("title"):
            report["note"] = "Kartu ini belum punya nama: isi field name (title untuk skenario)."
        return {"card_id": cid, "name": card["name"], "field": field,
                **({"ok": True} if not report.get("error") else {}), **report}

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
