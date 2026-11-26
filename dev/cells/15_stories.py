class Stories:
    """A story ties cards together (world, scenario, style, GM, persona, characters) and holds what changes while
    playing: the story book (canon), the never-forget list, and changes waiting for the next prompt epoch."""

    ROLES = ("world", "scenario", "style", "gm", "persona", "character")

    def __init__(self, store, cards):
        self.store, self.cards = store, cards

    def create(self, title, card_ids):
        """card_ids: {"world": id, "scenario": id, "style": id, "gm": id, "persona": id, "character": [ids]}"""
        now = time.time()
        sid = self.store.x("INSERT INTO stories (title, data, created, updated) VALUES (?, ?, ?, ?)",
                           (title, json.dumps({"canon": {}, "never_forget": []}), now, now))
        for role, ids in card_ids.items():
            for cid in ids if isinstance(ids, list) else [ids]:
                if cid:
                    self.attach(sid, cid, role)
        return sid

    def get(self, story_id):
        s = self.store.one("SELECT * FROM stories WHERE id = ?", (story_id,)) if story_id else None
        if s:
            s["data"] = json.loads(s["data"] or "{}")
            s["data"].setdefault("canon", {})
            s["data"].setdefault("never_forget", [])
        return s

    def list(self):
        return self.store.q("SELECT id, title, updated FROM stories ORDER BY updated DESC")

    def _save_data(self, story_id, data):
        self.store.x("UPDATE stories SET data = ?, updated = ? WHERE id = ?", (json.dumps(data), time.time(), story_id))

    def attach(self, story_id, card_id, role, version=None):
        if role != "character":
            self.store.x("DELETE FROM story_cards WHERE story_id = ? AND role = ?", (story_id, role))
        c = self.cards.get(card_id)
        self.store.x("INSERT OR REPLACE INTO story_cards (story_id, card_id, role, version) VALUES (?, ?, ?, ?)",
                     (story_id, card_id, role, version or (c["version"] if c else 1)))

    def detach(self, story_id, card_id, role):
        self.store.x("DELETE FROM story_cards WHERE story_id = ? AND card_id = ? AND role = ?", (story_id, card_id, role))

    def card_links(self, story_id):
        return self.store.q("SELECT card_id, role, version FROM story_cards WHERE story_id = ? ORDER BY role, card_id",
                            (story_id,))

    def cards_of(self, story_id, latest=False):
        """{role: card} for single roles, {"character": [cards]} for characters. Uses the pinned card version
        unless latest=True."""
        out = {"character": []}
        for link in self.card_links(story_id) if story_id else []:
            c = self.cards.get(link["card_id"], None if latest else link["version"])
            if not c:
                continue
            if link["role"] == "character":
                out["character"].append(c)
            else:
                out[link["role"]] = c
        return out

    def refresh_versions(self, story_id):
        """Point the story at the newest version of each card (done at a new prompt epoch)."""
        for link in self.card_links(story_id):
            c = self.store.one("SELECT version FROM cards WHERE id = ?", (link["card_id"],))
            if c and c["version"] != link["version"]:
                self.store.x("UPDATE story_cards SET version = ? WHERE story_id = ? AND card_id = ? AND role = ?",
                             (c["version"], story_id, link["card_id"], link["role"]))

    def outdated(self, story_id):
        rows = self.store.q("SELECT sc.card_id, c.name, sc.version, c.version AS latest FROM story_cards sc "
                            "JOIN cards c ON c.id = sc.card_id WHERE sc.story_id = ? AND c.version > sc.version", (story_id,))
        return rows

    # ---------- canon and never-forget ----------

    def canon_set(self, story_id, section, text, chat_id=None, message_id=None):
        """message_id given (the model wrote it during a turn): logged on that branch. Without (edited in the UI):
        changes the base every chat of the story starts from."""
        if message_id:
            self.store.x("INSERT INTO canon_log (story_id, chat_id, message_id, section, text, created) VALUES (?, ?, ?, ?, ?, ?)",
                         (story_id, chat_id, message_id, section, text.strip(), time.time()))
        else:
            s = self.get(story_id)
            if text.strip():
                s["data"]["canon"][section] = text.strip()
            else:
                s["data"]["canon"].pop(section, None)
            self._save_data(story_id, s["data"])
        self.pending(story_id, chat_id, f"Buku cerita · {section}: {text.strip() or '(dihapus)'}")

    def canon(self, story_id, visible=None):
        """Sections as they are on a branch: the base, then the logged changes whose message is visible."""
        s = self.get(story_id)
        if not s:
            return {}
        out = dict(s["data"]["canon"])
        if visible:
            for r in self.store.q("SELECT message_id, section, text FROM canon_log WHERE story_id = ? ORDER BY id", (story_id,)):
                if r["message_id"] in visible:
                    if r["text"]:
                        out[r["section"]] = r["text"]
                    else:
                        out.pop(r["section"], None)
        return out

    def canon_text(self, story_id, limit=48000, visible=None):
        s = self.get(story_id)
        if not s:
            return ""
        parts = [f"### {k}\n{v}" for k, v in self.canon(story_id, visible).items()]
        nf = s["data"]["never_forget"]
        if nf:
            parts.append("### Jangan pernah lupa\n" + "\n".join(f"- {x}" for x in nf))
        return "\n\n".join(parts)[:limit]

    def never_forget(self, story_id, items):
        s = self.get(story_id)
        s["data"]["never_forget"] = [x.strip() for x in items if x and x.strip()]
        self._save_data(story_id, s["data"])

    def pending(self, story_id, chat_id, text):
        self.store.x("INSERT INTO pending_changes (story_id, chat_id, text, created) VALUES (?, ?, ?, ?)",
                     (story_id, chat_id, text[:2000], time.time()))

    def pending_list(self, story_id, chat_id):
        return self.store.q("SELECT id, text FROM pending_changes WHERE (story_id = ? AND story_id IS NOT NULL) OR chat_id = ? "
                            "ORDER BY id", (story_id, chat_id))

    def clear_pending(self, story_id, chat_id):
        self.store.x("DELETE FROM pending_changes WHERE (story_id = ? AND story_id IS NOT NULL) OR chat_id = ?",
                     (story_id, chat_id))


STORIES = Stories(STORE, CARDS)
