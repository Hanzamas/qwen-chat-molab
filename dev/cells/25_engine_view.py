class EngineView:
    """Read-only views for the UI: history items, panels, branches, prompt inspector, story export."""

    DISPLAY_LIMIT = 150

    def display(self, chat_id, limit=None):
        """History for the UI: user messages and bot turns (assistant + tool messages folded together)."""
        if not chat_id:
            return {"items": [], "total": 0}
        path = self.store.path(chat_id)
        ids = [m["id"] for m in path]
        pos = {mid: i for i, mid in enumerate(ids)}
        chapters = {r["message_id"]: r["title"] for r in self.store.q("SELECT message_id, title FROM chapters WHERE chat_id = ?",
                                                                      (chat_id,))}
        # several summaries can hang on one node (a continued chat carries the whole chronicle on its root)
        sums = {}
        for s in self.store.q("SELECT id, node_id, from_id, level, text FROM summaries WHERE chat_id = ? "
                              "AND level IN ('chunk', 'era') ORDER BY id", (chat_id,)):
            if s["node_id"] in pos:
                sums.setdefault(s["node_id"], []).append(s)
        dice = self.world.dice_for(ids)
        att_meta = {r["message_id"]: r for r in self.store.q(
            f"SELECT message_id, COUNT(*) AS n, GROUP_CONCAT(kind || ':' || name, '|') AS names FROM attachments "
            f"WHERE message_id IN ({','.join(str(i) for i in ids) or '0'}) GROUP BY message_id")}
        kids = {}
        for r in self.store.q("SELECT id, parent_id, role FROM messages WHERE chat_id = ? ORDER BY id", (chat_id,)):
            kids.setdefault(r["parent_id"], []).append(r)
        items, cur = [], None
        for m in path:
            n = pos[m["id"]] + 1
            if m["role"] == "user":
                cur = None
                sib = [k["id"] for k in kids.get(m["parent_id"], []) if k["role"] == "user"]
                a = att_meta.get(m["id"])
                items.append({"kind": "user", "id": m["id"], "n": n, "content": m["meta"].get("typed", m["content"]),
                              "ooc": bool(m["ooc"]), "pinned": bool(m["pinned"]), "time_skip": m["meta"].get("time_skip"),
                              "attachments": (a["names"].split("|") if a else []), "notes": m["meta"].get("notes") or [],
                              "has_note": bool(m["meta"].get("ephemeral")),
                              "swipe": [sib.index(m["id"]) + 1 if m["id"] in sib else 1, max(1, len(sib))]})
            else:
                if cur is None:
                    parent = m["parent_id"]
                    sib = [k["id"] for k in kids.get(parent, []) if k["role"] == "assistant"]
                    cur = {"kind": "bot", "id": m["id"], "root": m["id"], "n": n, "ids": [], "content": "", "reasoning": "",
                           "tools": [], "stats": None, "flags": [], "choices": None, "dice": [], "pinned": False,
                           "partial": False, "ooc": False, "fact_warnings": [], "continuity": [],
                           "swipe": [sib.index(m["id"]) + 1 if m["id"] in sib else 1, max(1, len(sib))]}
                    items.append(cur)
                cur["ids"].append(m["id"])
                cur["id"] = m["id"]
                if m["role"] == "assistant":
                    cur["answer_id"], cur["edit_text"] = m["id"], m["content"]
                    if m["reasoning"]:
                        cur["reasoning"] += ("\n\n" if cur["reasoning"] else "") + m["reasoning"]
                    if m["content"]:
                        cur["content"] += ("\n\n" if cur["content"] else "") + m["content"]
                    for tc in json.loads(m["tool_calls"] or "[]"):
                        fn = tc.get("function") or {}
                        cur["tools"].append({"id": tc.get("id"), "name": fn.get("name"), "args": fn.get("arguments"),
                                             "result": "", "error": False})
                    meta = m["meta"]
                    cur["stats"] = meta.get("stats") or cur["stats"]
                    cur["flags"] = meta.get("flags") or cur["flags"]
                    cur["choices"] = meta.get("choices") or cur["choices"]
                    cur["fact_warnings"] = meta.get("fact_warnings") or cur["fact_warnings"]
                    cur["continuity"] = meta.get("continuity") or cur["continuity"]
                    cur["pinned"] = cur["pinned"] or bool(m["pinned"])
                    cur["partial"] = m["status"] == "partial"
                    cur["ooc"] = bool(m["ooc"])
                    if meta.get("error"):
                        cur["error"] = meta["error"]
                elif m["role"] == "tool":
                    for t in cur["tools"]:
                        if t["id"] == m["tool_call_id"]:
                            t["result"] = m["content"][:4000] + (" …" if len(m["content"]) > 4000 else "")
                            t["error"] = bool(m["meta"].get("error"))
                cur["dice"] += dice.get(m["id"], [])
            if m["id"] in chapters:
                items[-1]["chapter"] = chapters[m["id"]]
            for s in sums.get(m["id"], []):
                items.append({"kind": "summary", "id": f"s{s['id']}", "text": s["text"], "level": s["level"],
                              "range": [pos.get(s["from_id"], 0) + 1, n]})
                cur = None
        limit = limit or self.DISPLAY_LIMIT
        return {"items": items[-limit:], "total": len(items), "chapters": sorted(
            ({"id": mid, "title": t, "n": pos[mid] + 1} for mid, t in chapters.items() if mid in pos), key=lambda x: x["n"])}

    def panels(self, chat_id):
        """Status and world panels for the game format, computed from the database."""
        chat = self.store.chat(chat_id) if chat_id else None
        if not chat or chat["kind"] not in ("rp", "group"):
            return {}
        c = self.prompt.ctx(chat_id)
        ids = self.store.path_ids(chat_id)
        st = self.world.state(chat_id, ids)
        gm = self.prompt.gm(c)
        player = st["status"].get("player", {})
        events = self.world.world_events(chat_id, ids, who="player", limit=6)
        wthr = self.world.weather((c["story"] or {}).get("id"), c["cards"], st["time"])
        persona = c["cards"].get("persona")
        return {"format": gm.get("format", "prosa"), "time": st["time_text"], "turn": st["turn"],
                "location": player.get("location") or ((c["cards"].get("scenario") or {}).get("data") or {}).get("start_location", ""),
                "stats": [{"key": s["key"], "label": s["label"], "value": s["value"], "min": s["min"], "max": s["max"],
                           "change": s["change"]} for s in st["stats"]],
                "status": {k: v for k, v in player.items() if k != "location" and not str(k).startswith("_")},
                "lang": self._lang_panel(c, st),
                "characters": self._observable(self.world.with_schedule(st, c["cards"]), player.get("location")),
                "gm_view": bool(chat["settings"].get("gm_view")),
                "relations": [{"who": a, "score": v["score"], "word": Relations.word(v["score"]), "last": v["last"]}
                              for (a, b), v in RELATIONS.scores(chat_id).items() if b == "player"],
                "characters_gm": {k: v for k, v in st["status"].items() if k != "player"} if chat["settings"].get("gm_view") else {},
                "weather": wthr["text"] if wthr else "", "events": [{"id": e["id"], "time": e["world_time"], "text": e["text"],
                                                                     "new": not e["shown"]} for e in events],
                "time_skips": gm.get("time_skips") or ["2 jam", "1 hari", "1 minggu"], "persona": persona["name"] if persona else "",
                "story": (c["story"] or {}).get("title", "")}

    def _lang_panel(self, c, st):
        lv = Lang.of(c["cards"], st, self.world.start_time(c["cards"]))
        return {k: lv[k] for k in ("label", "band", "value")} if lv else None

    # What can be seen of someone in the same place. Plans, attitudes, what they know and carry stay hidden.
    OBSERVABLE = ("outfit", "mood", "injuries", "keadaan")

    @classmethod
    def _observable(cls, status, here):
        norm = lambda s: re.sub(r"\s+", " ", str(s or "").strip().lower())
        here = norm(here)
        out = {}
        for name, st in status.items():
            if name == "player":
                continue
            loc = norm(st.get("location"))
            if here and loc and (loc == here or here in loc or loc in here):
                out[name] = {k: st[k] for k in cls.OBSERVABLE if st.get(k) not in (None, "", [])}
            elif not here or not loc:
                out[name] = {k: st[k] for k in ("keadaan",) if st.get(k) not in (None, "", [])}
        return out

    def branches(self, chat_id):
        """Leaves of the message tree with a preview, newest first."""
        rows = self.store.q("SELECT id, parent_id, role, content, created FROM messages WHERE chat_id = ? ORDER BY id", (chat_id,))
        parents = {r["parent_id"] for r in rows}
        head = (self.store.chat(chat_id) or {}).get("head_id")
        active = set(self.store.path_ids(chat_id))
        leaves = [r for r in rows if r["id"] not in parents]
        out = []
        for r in sorted(leaves, key=lambda r: -r["created"]):
            depth = len(self.store.path_ids(chat_id, r["id"]))
            out.append({"id": r["id"], "depth": depth, "preview": (r["content"] or "")[:140], "active": r["id"] in active,
                        "head": r["id"] == head})
        return out[:50]

    def prompt_view(self, chat_id):
        c = self.prompt.ctx(chat_id)
        msgs, used = self.prompt.build(chat_id)
        tools = self.tools.specs(c)
        parts = {"system": msgs[0]["content"], "history_messages": len(msgs) - 1,
                 "last_user": msgs[-1]["content"] if msgs[-1]["role"] == "user" else ""}
        count = self.llm.tokenize(msgs, tools, self.prompt.kwargs(c))
        sys_count = self.llm.tokenize(msgs[:1], tools, self.prompt.kwargs(c))
        return {"tokens": count, "system_tokens": sys_count, "max": self.llm.max_context(), "kwargs": self.prompt.kwargs(c),
                "sampling": self.prompt.sampling(c), "epoch": c["chat"]["epoch"], **parts,
                "last_user_text": parts["last_user"] if isinstance(parts["last_user"], str) else json.dumps(parts["last_user"])[:20000]}

    # ---------- export ----------

    def export_story(self, chat_id, fmt="md"):
        chat = self.store.chat(chat_id)
        c = self.prompt.ctx(chat_id)
        persona = (c["cards"].get("persona") or {}).get("name") or "Me"
        chapters = {r["message_id"]: r["title"] for r in self.store.q("SELECT message_id, title FROM chapters WHERE chat_id = ?",
                                                                      (chat_id,))}
        blocks, current = [], {"title": chat["title"], "parts": []}
        for m in self.store.path(chat_id):
            if m["ooc"] or m["role"] not in ("user", "assistant") or not m["content"].strip():
                continue
            if m["id"] in chapters and current["parts"]:
                blocks.append(current)
                current = {"title": chapters[m["id"]], "parts": []}
            elif m["id"] in chapters:
                current["title"] = chapters[m["id"]]
            text = m["meta"].get("typed", m["content"]) if m["role"] == "user" else m["content"]
            current["parts"].append((m["role"], text))
        blocks.append(current)
        safe = re.sub(r"[^\w\- ]+", "", chat["title"])[:60].strip() or "story"
        if fmt == "md":
            out = [f"# {chat['title']}\n"]
            for b in blocks:
                out.append(f"\n## {b['title']}\n")
                for role, text in b["parts"]:
                    out.append(f"> **{persona}:** {text}\n" if role == "user" else text + "\n")
            return f"{safe}.md", "\n".join(out).encode("utf-8")

        def html_body(b):
            h = [f"<h2>{_esc(b['title'])}</h2>"]
            for role, text in b["parts"]:
                paras = "".join(f"<p>{_esc(p)}</p>" for p in TXT.paragraphs(text))
                h.append(f'<blockquote><b>{_esc(persona)}:</b> {paras}</blockquote>' if role == "user" else paras)
            return "\n".join(h)

        def _esc(s):
            return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        if fmt == "html":
            body = "\n".join(html_body(b) for b in blocks)
            page = (f"<!doctype html><html lang='id'><head><meta charset='utf-8'><title>{_esc(chat['title'])}</title>"
                    "<style>body{max-width:42rem;margin:3rem auto;padding:0 1rem;font:17px/1.75 Georgia,serif;color:#222}"
                    "blockquote{border-left:3px solid #bbb;margin:1rem 0;padding-left:1rem;color:#555}</style></head>"
                    f"<body><h1>{_esc(chat['title'])}</h1>{body}</body></html>")
            return f"{safe}.html", page.encode("utf-8")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip", compress_type=zipfile.ZIP_STORED)
            z.writestr("META-INF/container.xml", '<?xml version="1.0"?><container version="1.0" '
                       'xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="OEBPS/content.opf" '
                       'media-type="application/oebps-package+xml"/></rootfiles></container>')
            manifest, spine, nav = [], [], []
            for i, b in enumerate(blocks, 1):
                z.writestr(f"OEBPS/ch{i}.xhtml", '<?xml version="1.0" encoding="utf-8"?><html xmlns="http://www.w3.org/1999/xhtml">'
                           f"<head><title>{_esc(b['title'])}</title></head><body>{html_body(b)}</body></html>")
                manifest.append(f'<item id="ch{i}" href="ch{i}.xhtml" media-type="application/xhtml+xml"/>')
                spine.append(f'<itemref idref="ch{i}"/>')
                nav.append(f'<li><a href="ch{i}.xhtml">{_esc(b["title"])}</a></li>')
            z.writestr("OEBPS/nav.xhtml", '<?xml version="1.0" encoding="utf-8"?><html xmlns="http://www.w3.org/1999/xhtml" '
                       'xmlns:epub="http://www.idpf.org/2007/ops"><head><title>Contents</title></head><body>'
                       f'<nav epub:type="toc"><ol>{"".join(nav)}</ol></nav></body></html>')
            uid = hashlib.sha1(f"{chat_id}-{chat['title']}".encode()).hexdigest()
            z.writestr("OEBPS/content.opf", '<?xml version="1.0" encoding="utf-8"?><package xmlns="http://www.idpf.org/2007/opf" '
                       f'version="3.0" unique-identifier="uid"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
                       f'<dc:identifier id="uid">{uid}</dc:identifier><dc:title>{_esc(chat["title"])}</dc:title>'
                       f'<dc:language>id</dc:language><meta property="dcterms:modified">{time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}</meta>'
                       f'</metadata><manifest><item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>'
                       f'{"".join(manifest)}</manifest><spine>{"".join(spine)}</spine></package>')
        return f"{safe}.epub", buf.getvalue()
