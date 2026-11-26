_SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS stories (
    id INTEGER PRIMARY KEY, title TEXT NOT NULL, data TEXT NOT NULL DEFAULT '{}',
    created REAL NOT NULL, updated REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS story_cards (
    story_id INTEGER NOT NULL, card_id INTEGER NOT NULL, role TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (story_id, card_id, role)
);
CREATE TABLE IF NOT EXISTS chats (
    id INTEGER PRIMARY KEY, story_id INTEGER, title TEXT NOT NULL, kind TEXT NOT NULL DEFAULT 'chat',
    system TEXT NOT NULL DEFAULT '', settings TEXT NOT NULL DEFAULT '{}', head_id INTEGER,
    strip_node INTEGER NOT NULL DEFAULT 0, epoch INTEGER NOT NULL DEFAULT 0,
    created REAL NOT NULL, updated REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY, chat_id INTEGER NOT NULL, parent_id INTEGER, role TEXT NOT NULL,
    content TEXT NOT NULL DEFAULT '', reasoning TEXT NOT NULL DEFAULT '', tool_calls TEXT, tool_call_id TEXT,
    ooc INTEGER NOT NULL DEFAULT 0, pinned INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'final',
    meta TEXT NOT NULL DEFAULT '{}', created REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS messages_chat ON messages (chat_id, parent_id);
CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(content, reasoning, content='messages', content_rowid='id');
CREATE TRIGGER IF NOT EXISTS messages_ai AFTER INSERT ON messages BEGIN
    INSERT INTO messages_fts(rowid, content, reasoning) VALUES (new.id, new.content, new.reasoning);
END;
CREATE TRIGGER IF NOT EXISTS messages_ad AFTER DELETE ON messages BEGIN
    INSERT INTO messages_fts(messages_fts, rowid, content, reasoning) VALUES ('delete', old.id, old.content, old.reasoning);
END;
CREATE TRIGGER IF NOT EXISTS messages_au AFTER UPDATE OF content, reasoning ON messages BEGIN
    INSERT INTO messages_fts(messages_fts, rowid, content, reasoning) VALUES ('delete', old.id, old.content, old.reasoning);
    INSERT INTO messages_fts(rowid, content, reasoning) VALUES (new.id, new.content, new.reasoning);
END;
CREATE TABLE IF NOT EXISTS attachments (
    id INTEGER PRIMARY KEY, message_id INTEGER NOT NULL, kind TEXT NOT NULL,
    mime TEXT NOT NULL, name TEXT NOT NULL, data BLOB NOT NULL
);
CREATE INDEX IF NOT EXISTS attachments_msg ON attachments (message_id);
CREATE TABLE IF NOT EXISTS summaries (
    id INTEGER PRIMARY KEY, chat_id INTEGER NOT NULL, node_id INTEGER NOT NULL, from_id INTEGER NOT NULL DEFAULT 0,
    level TEXT NOT NULL DEFAULT 'chunk', text TEXT NOT NULL, core TEXT NOT NULL DEFAULT '', created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS snapshots (
    chat_id INTEGER NOT NULL, epoch INTEGER NOT NULL, text TEXT NOT NULL, created REAL NOT NULL,
    PRIMARY KEY (chat_id, epoch)
);
CREATE TABLE IF NOT EXISTS pending_changes (
    id INTEGER PRIMARY KEY, story_id INTEGER, chat_id INTEGER, text TEXT NOT NULL, created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS chapters (
    id INTEGER PRIMARY KEY, chat_id INTEGER NOT NULL, message_id INTEGER NOT NULL, title TEXT NOT NULL, created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS card_schemas (type TEXT PRIMARY KEY, version INTEGER NOT NULL, json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS cards (
    id INTEGER PRIMARY KEY, type TEXT NOT NULL, name TEXT NOT NULL, data TEXT NOT NULL DEFAULT '{}', avatar BLOB,
    version INTEGER NOT NULL DEFAULT 1, created REAL NOT NULL, updated REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS card_versions (
    card_id INTEGER NOT NULL, version INTEGER NOT NULL, data TEXT NOT NULL, created REAL NOT NULL,
    PRIMARY KEY (card_id, version)
);
CREATE TABLE IF NOT EXISTS lore_entries (
    id INTEGER PRIMARY KEY, card_id INTEGER NOT NULL, kind TEXT NOT NULL DEFAULT 'istilah', title TEXT NOT NULL,
    keys TEXT NOT NULL DEFAULT '', text TEXT NOT NULL DEFAULT '', core INTEGER NOT NULL DEFAULT 0, updated REAL NOT NULL
);
CREATE VIRTUAL TABLE IF NOT EXISTS lore_fts USING fts5(title, keys, text, content='lore_entries', content_rowid='id');
CREATE TRIGGER IF NOT EXISTS lore_ai AFTER INSERT ON lore_entries BEGIN
    INSERT INTO lore_fts(rowid, title, keys, text) VALUES (new.id, new.title, new.keys, new.text);
END;
CREATE TRIGGER IF NOT EXISTS lore_ad AFTER DELETE ON lore_entries BEGIN
    INSERT INTO lore_fts(lore_fts, rowid, title, keys, text) VALUES ('delete', old.id, old.title, old.keys, old.text);
END;
CREATE TRIGGER IF NOT EXISTS lore_au AFTER UPDATE ON lore_entries BEGIN
    INSERT INTO lore_fts(lore_fts, rowid, title, keys, text) VALUES ('delete', old.id, old.title, old.keys, old.text);
    INSERT INTO lore_fts(rowid, title, keys, text) VALUES (new.id, new.title, new.keys, new.text);
END;
CREATE TABLE IF NOT EXISTS facts (
    id INTEGER PRIMARY KEY, world_card_id INTEGER, claim TEXT NOT NULL, source_url TEXT NOT NULL DEFAULT '',
    source_title TEXT NOT NULL DEFAULT '', checked REAL NOT NULL, confidence REAL NOT NULL DEFAULT 0.7,
    status TEXT NOT NULL DEFAULT 'terverifikasi', tags TEXT NOT NULL DEFAULT ''
);
CREATE VIRTUAL TABLE IF NOT EXISTS facts_fts USING fts5(claim, tags, content='facts', content_rowid='id');
CREATE TRIGGER IF NOT EXISTS facts_ai AFTER INSERT ON facts BEGIN
    INSERT INTO facts_fts(rowid, claim, tags) VALUES (new.id, new.claim, new.tags);
END;
CREATE TRIGGER IF NOT EXISTS facts_ad AFTER DELETE ON facts BEGIN
    INSERT INTO facts_fts(facts_fts, rowid, claim, tags) VALUES ('delete', old.id, old.claim, old.tags);
END;
CREATE TRIGGER IF NOT EXISTS facts_au AFTER UPDATE ON facts BEGIN
    INSERT INTO facts_fts(facts_fts, rowid, claim, tags) VALUES ('delete', old.id, old.claim, old.tags);
    INSERT INTO facts_fts(rowid, claim, tags) VALUES (new.id, new.claim, new.tags);
END;
CREATE TABLE IF NOT EXISTS timeline (
    id INTEGER PRIMARY KEY, card_id INTEGER NOT NULL, at TEXT NOT NULL, title TEXT NOT NULL, text TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS status_events (
    id INTEGER PRIMARY KEY, chat_id INTEGER NOT NULL, message_id INTEGER, subject TEXT NOT NULL, field TEXT NOT NULL,
    op TEXT NOT NULL DEFAULT 'add', value TEXT NOT NULL, reason TEXT NOT NULL DEFAULT '', created REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS status_events_chat ON status_events (chat_id);
CREATE TABLE IF NOT EXISTS world_events (
    id INTEGER PRIMARY KEY, chat_id INTEGER NOT NULL, message_id INTEGER, world_time TEXT NOT NULL, text TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'kejadian', known_to TEXT NOT NULL DEFAULT '[]', public INTEGER NOT NULL DEFAULT 0,
    shown INTEGER NOT NULL DEFAULT 0, created REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS world_events_chat ON world_events (chat_id);
CREATE TABLE IF NOT EXISTS dice_log (
    id INTEGER PRIMARY KEY, chat_id INTEGER NOT NULL, message_id INTEGER, event TEXT NOT NULL, odds REAL NOT NULL,
    roll REAL NOT NULL, success INTEGER NOT NULL, created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY, scope TEXT NOT NULL DEFAULT 'story', card_id INTEGER, story_id INTEGER, chat_id INTEGER,
    kind TEXT NOT NULL DEFAULT 'fact', text TEXT NOT NULL, created REAL NOT NULL, updated REAL NOT NULL
);
CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(text, content='memories', content_rowid='id');
CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
    INSERT INTO memories_fts(rowid, text) VALUES (new.id, new.text);
END;
CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, text) VALUES ('delete', old.id, old.text);
END;
CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE OF text ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, text) VALUES ('delete', old.id, old.text);
    INSERT INTO memories_fts(rowid, text) VALUES (new.id, new.text);
END;
CREATE TABLE IF NOT EXISTS memory_log (
    id INTEGER PRIMARY KEY, memory_id INTEGER, action TEXT NOT NULL, before TEXT, after TEXT,
    chat_id INTEGER, created REAL NOT NULL, undone INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS vectors (kind TEXT NOT NULL, ref_id INTEGER NOT NULL, dim INTEGER NOT NULL, v BLOB NOT NULL,
    PRIMARY KEY (kind, ref_id));
CREATE TABLE IF NOT EXISTS side_log (
    id INTEGER PRIMARY KEY, kind TEXT NOT NULL, chat_id INTEGER, message_id INTEGER, data TEXT NOT NULL, created REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS side_log_chat ON side_log (chat_id, kind);
CREATE TABLE IF NOT EXISTS vocab (
    id INTEGER PRIMARY KEY, term TEXT NOT NULL, lang TEXT NOT NULL DEFAULT '', translation TEXT NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT '', example TEXT NOT NULL DEFAULT '', due REAL NOT NULL, interval REAL NOT NULL DEFAULT 0,
    ease REAL NOT NULL DEFAULT 2.5, reps INTEGER NOT NULL DEFAULT 0, created REAL NOT NULL
);
"""

SCHEMA_VERSION = 2

# Columns added after v1. ALTER TABLE ADD COLUMN for databases made before them.
_COLUMNS_V2 = [
    ("memories", "message_id", "INTEGER"),      # message that made it (NULL: made outside a chat, visible everywhere)
    ("memories", "forgotten_at", "INTEGER"),    # message that forgot it (hidden only where that message is on the path)
    ("memories", "importance", "REAL NOT NULL DEFAULT 0.5"),
    ("memory_log", "message_id", "INTEGER"),
    ("lore_entries", "known_to", "TEXT NOT NULL DEFAULT ''"),  # empty: common knowledge; else who knows this lore
]
_SCHEMA_V2 = """
CREATE TABLE IF NOT EXISTS canon_log (
    id INTEGER PRIMARY KEY, story_id INTEGER NOT NULL, chat_id INTEGER, message_id INTEGER, section TEXT NOT NULL,
    text TEXT NOT NULL DEFAULT '', created REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS canon_log_story ON canon_log (story_id);
CREATE TABLE IF NOT EXISTS threads (
    id INTEGER PRIMARY KEY, story_id INTEGER, chat_id INTEGER NOT NULL, message_id INTEGER, kind TEXT NOT NULL DEFAULT 'misteri',
    title TEXT NOT NULL, text TEXT NOT NULL DEFAULT '', who TEXT NOT NULL DEFAULT '', due TEXT NOT NULL DEFAULT '',
    opened_at TEXT NOT NULL DEFAULT '', created REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS threads_chat ON threads (chat_id);
CREATE TABLE IF NOT EXISTS thread_events (
    id INTEGER PRIMARY KEY, thread_id INTEGER NOT NULL, chat_id INTEGER, message_id INTEGER, status TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT '', created REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS thread_events_thread ON thread_events (thread_id);
CREATE TABLE IF NOT EXISTS relations_log (
    id INTEGER PRIMARY KEY, chat_id INTEGER NOT NULL, message_id INTEGER, a TEXT NOT NULL, b TEXT NOT NULL,
    delta REAL NOT NULL, reason TEXT NOT NULL DEFAULT '', world_time TEXT NOT NULL DEFAULT '', created REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS relations_chat ON relations_log (chat_id);
CREATE TABLE IF NOT EXISTS card_proposals (
    id INTEGER PRIMARY KEY, chat_id INTEGER, card_id INTEGER NOT NULL, field TEXT NOT NULL, value TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'menunggu', created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS knowledge (
    id INTEGER PRIMARY KEY, chat_id INTEGER NOT NULL, message_id INTEGER, holder TEXT NOT NULL, text TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'fakta', source TEXT NOT NULL DEFAULT 'lihat sendiri', source_who TEXT NOT NULL DEFAULT '',
    truth TEXT NOT NULL DEFAULT 'benar', importance REAL NOT NULL DEFAULT 0.5, world_time TEXT NOT NULL DEFAULT '',
    forgotten_at INTEGER, created REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS knowledge_chat ON knowledge (chat_id, holder);
CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts USING fts5(text, content='knowledge', content_rowid='id');
CREATE TRIGGER IF NOT EXISTS knowledge_ai AFTER INSERT ON knowledge BEGIN
    INSERT INTO knowledge_fts(rowid, text) VALUES (new.id, new.text);
END;
CREATE TRIGGER IF NOT EXISTS knowledge_ad AFTER DELETE ON knowledge BEGIN
    INSERT INTO knowledge_fts(knowledge_fts, rowid, text) VALUES ('delete', old.id, old.text);
END;
CREATE TRIGGER IF NOT EXISTS knowledge_au AFTER UPDATE OF text ON knowledge BEGIN
    INSERT INTO knowledge_fts(knowledge_fts, rowid, text) VALUES ('delete', old.id, old.text);
    INSERT INTO knowledge_fts(rowid, text) VALUES (new.id, new.text);
END;
"""


class Store:
    """One SQLite file: chats (message trees), cards, lore, facts, world state, memories, vectors, vocabulary."""

    def __init__(self, path):
        self.file = Path(path)
        self.lock = threading.RLock()
        self.rev = 0
        self.listeners = []
        # import_guards raise when the database must not be replaced now (a reply is being written);
        # import_hooks(ok) run after every attempt (on success, caches holding ids of the old database are reset).
        self.import_guards = []
        self.import_hooks = []
        self._open()

    # ---------- connection ----------

    def _open(self):
        self.conn = sqlite3.connect(self.file, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=OFF")
        self._migrate()

    def _columns(self, table):
        return {r[1] for r in self.conn.execute(f"PRAGMA table_info({table})")}

    def _migrate(self):
        version = self.conn.execute("PRAGMA user_version").fetchone()[0]
        if version > SCHEMA_VERSION:
            raise ValueError(f"Database dibuat versi notebook yang lebih baru (skema {version}).")
        if "messages" in self._tables() and "seq" in self._columns("messages"):
            self._migrate_legacy()
        # Every statement is IF NOT EXISTS, so this also adds tables introduced after a database was created.
        self.conn.executescript(_SCHEMA_V1)
        for table, col, decl in _COLUMNS_V2:
            if col not in self._columns(table):
                self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")
        self.conn.executescript(_SCHEMA_V2)
        self.conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        self.conn.commit()

    def _tables(self):
        return {r[0] for r in self.conn.execute("SELECT name FROM sqlite_master WHERE type IN ('table', 'view')")}

    def _migrate_legacy(self):
        """Database from the old notebook (linear messages with seq) -> message trees."""
        c = self.conn
        old = self._tables()
        for t in ("messages_fts", "memories_fts"):
            if t in old:
                c.execute(f"DROP TABLE {t}")
        for trg in ("messages_ai", "messages_ad", "memories_ai", "memories_ad"):
            c.execute(f"DROP TRIGGER IF EXISTS {trg}")
        for t in ("chats", "messages", "summaries", "memories"):
            if t in old:
                c.execute(f"ALTER TABLE {t} RENAME TO legacy_{t}")
        c.executescript(_SCHEMA_V1)
        seq_to_id = {}
        if "chats" in old:
            for ch in c.execute("SELECT * FROM legacy_chats ORDER BY id").fetchall():
                c.execute("INSERT INTO chats (id, title, system, kind, settings, created, updated) VALUES (?, ?, ?, 'chat', '{}', ?, ?)",
                          (ch["id"], ch["title"], ch["system"] or "", ch["created"], ch["updated"]))
        prev = {}
        for m in c.execute("SELECT * FROM legacy_messages ORDER BY chat_id, seq").fetchall():
            parent = prev.get(m["chat_id"])
            c.execute("INSERT INTO messages (id, chat_id, parent_id, role, content, reasoning, tool_calls, tool_call_id, meta, created) "
                      "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                      (m["id"], m["chat_id"], parent, m["role"], m["content"] or "", m["reasoning"] or "",
                       m["tool_calls"], m["tool_call_id"], m["meta"] or "{}", m["created"]))
            prev[m["chat_id"]] = m["id"]
            seq_to_id[(m["chat_id"], m["seq"])] = m["id"]
        for chat_id, head in prev.items():
            c.execute("UPDATE chats SET head_id = ? WHERE id = ?", (head, chat_id))
        if "chats" in old and "strip_upto" in {r[1] for r in c.execute("PRAGMA table_info(legacy_chats)")}:
            for ch in c.execute("SELECT id, strip_upto FROM legacy_chats").fetchall():
                node = seq_to_id.get((ch["id"], ch["strip_upto"]), 0)
                c.execute("UPDATE chats SET strip_node = ? WHERE id = ?", (node, ch["id"]))
        if "summaries" in old:
            for s in c.execute("SELECT * FROM legacy_summaries").fetchall():
                node = seq_to_id.get((s["chat_id"], s["upto_seq"]))
                if node:
                    c.execute("INSERT INTO summaries (chat_id, node_id, level, text, created) VALUES (?, ?, 'chunk', ?, ?)",
                              (s["chat_id"], node, s["text"], s["created"]))
        if "memories" in old:
            for m in c.execute("SELECT * FROM legacy_memories").fetchall():
                kind = "summary_core" if (m["text"] or "").startswith("[Ringkasan chat") else "fact"
                c.execute("INSERT INTO memories (scope, kind, text, created, updated) VALUES ('user', ?, ?, ?, ?)",
                          (kind, m["text"], m["created"], m["created"]))
        for t in ("chats", "messages", "summaries", "memories"):
            if t in old:
                c.execute(f"DROP TABLE legacy_{t}")
        c.execute("DROP TABLE IF EXISTS chat_memory_snapshot")
        c.commit()

    # ---------- primitives ----------

    def q(self, sql, args=()):
        with self.lock:
            return [dict(r) for r in self.conn.execute(sql, args).fetchall()]

    def one(self, sql, args=()):
        with self.lock:
            r = self.conn.execute(sql, args).fetchone()
            return dict(r) if r else None

    def x(self, sql, args=()):
        with self.lock:
            cur = self.conn.execute(sql, args)
            self.conn.commit()
            self._changed()
            return cur.lastrowid

    def many(self, sql, rows):
        with self.lock:
            self.conn.executemany(sql, rows)
            self.conn.commit()
            self._changed()

    def _changed(self):
        self.rev += 1
        for fn in list(self.listeners):
            try:
                fn(self.rev)
            except Exception:
                pass

    def meta_get(self, key, default=None):
        r = self.one("SELECT value FROM meta WHERE key = ?", (key,))
        return json.loads(r["value"]) if r else default

    def meta_set(self, key, value):
        if self.meta_get(key) == value:
            return  # unchanged: do not mark the database dirty (that would trigger a backup)
        self.x("INSERT INTO meta (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
               (key, json.dumps(value)))

    def side_log(self, kind, data, chat_id=None, message_id=None):
        """Keep the output of side tasks (drafts, explanations, transcripts, server logs) so nothing is lost."""
        text = json.dumps(data, ensure_ascii=False, default=str)
        if len(text) > 400_000:  # cut, but keep it valid JSON
            text = json.dumps({"truncated": True, "text": text[:400_000]}, ensure_ascii=False)
        return self.x("INSERT INTO side_log (kind, chat_id, message_id, data, created) VALUES (?, ?, ?, ?, ?)",
                      (kind, chat_id, message_id, text, time.time()))

    def side_logs(self, chat_id=None, kind=None, limit=50):
        sql, args = "SELECT * FROM side_log WHERE 1 = 1", []
        if chat_id:
            sql += " AND chat_id = ?"
            args.append(chat_id)
        if kind:
            sql += " AND kind = ?"
            args.append(kind)
        rows = self.q(sql + " ORDER BY id DESC LIMIT ?", args + [limit])
        for r in rows:
            try:
                r["data"] = json.loads(r["data"])
            except ValueError:
                r["data"] = {"truncated": True, "text": r["data"]}
        return rows

    # ---------- export / import ----------

    def export_bytes(self):
        with self.lock:
            self.conn.commit()
            return self.conn.serialize()

    def backup_to(self, path):
        """Consistent copy of the live database (SQLite backup API)."""
        with self.lock:
            dst = sqlite3.connect(path)
            try:
                self.conn.backup(dst)
            finally:
                dst.close()

    def import_bytes(self, data):
        """Replace the database with an uploaded one (old or new format). The upload is written to a separate file,
        checked and migrated there first; the live database is replaced only when all of that worked, and the
        previous file stays next to it as .before-import. (A file saved from a WAL database cannot be loaded with
        sqlite3.deserialize, which is why this goes through a file.)"""
        for fn in list(self.import_guards):
            fn()
        ok = False
        try:
            self._import(data)
            ok = True
        finally:
            for fn in list(self.import_hooks):
                try:
                    fn(ok)
                except Exception:
                    pass

    def _import(self, data):
        tmp = self.file.with_name(self.file.name + ".import")
        side = lambda p: [p, Path(str(p) + "-wal"), Path(str(p) + "-shm")]
        for p in side(tmp):
            p.unlink(missing_ok=True)
        tmp.write_bytes(data)
        try:
            con = sqlite3.connect(tmp)
            try:
                check = con.execute("PRAGMA quick_check").fetchone()[0]
                names = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
            finally:
                con.close()
            if check != "ok":
                raise ValueError(f"Database rusak: {check}")
            if not {"chats", "messages"} <= names:
                raise ValueError("File bukan database Qwen Chat.")
            probe = Store(tmp)  # runs the migrations on the copy; a failure leaves the live database untouched
            probe.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            probe.conn.close()
        except sqlite3.DatabaseError as e:
            for p in side(tmp):
                p.unlink(missing_ok=True)
            raise ValueError(f"File bukan database SQLite yang bisa dibaca: {e}") from None
        except Exception:
            for p in side(tmp):
                p.unlink(missing_ok=True)
            raise
        with self.lock:
            try:
                self.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            except sqlite3.DatabaseError:
                pass
            self.conn.close()
            for p in side(self.file)[1:]:
                p.unlink(missing_ok=True)
            if self.file.exists():
                os.replace(self.file, self.file.with_name(self.file.name + ".before-import"))
            os.replace(tmp, self.file)
            for p in side(tmp)[1:]:
                p.unlink(missing_ok=True)
            self._open()
            self._changed()

    # ---------- chats ----------

    def new_chat(self, title, kind="chat", story_id=None, settings=None, system=""):
        now = time.time()
        return self.x("INSERT INTO chats (title, kind, story_id, settings, system, created, updated) VALUES (?, ?, ?, ?, ?, ?, ?)",
                      (title, kind, story_id, json.dumps(settings or {}), system, now, now))

    def chat(self, chat_id):
        c = self.one("SELECT * FROM chats WHERE id = ?", (chat_id,))
        if c:
            c["settings"] = json.loads(c["settings"] or "{}")
        return c

    def chat_settings(self, chat_id, **updates):
        c = self.chat(chat_id)
        s = {**(c["settings"] if c else {}), **updates}
        self.x("UPDATE chats SET settings = ?, updated = ? WHERE id = ?", (json.dumps(s), time.time(), chat_id))
        return s

    def chats(self):
        return self.q("SELECT id, title, kind, story_id, updated FROM chats ORDER BY updated DESC")

    def delete_chat(self, chat_id):
        with self.lock:
            ids = [r["id"] for r in self.q("SELECT id FROM messages WHERE chat_id = ?", (chat_id,))]
            for i in range(0, len(ids), 500):
                part = ids[i:i + 500]
                marks = ",".join("?" * len(part))
                self.conn.execute(f"DELETE FROM attachments WHERE message_id IN ({marks})", part)
                for m_id in part:  # message vectors are keyed mid*100 + chunk number
                    self.conn.execute("DELETE FROM vectors WHERE kind = 'msg' AND ref_id BETWEEN ? AND ?",
                                      (m_id * 100, m_id * 100 + 99))
            for table in ("messages", "summaries", "snapshots", "chapters", "status_events", "world_events",
                          "dice_log", "pending_changes", "memory_log", "side_log"):
                self.conn.execute(f"DELETE FROM {table} WHERE chat_id = ?", (chat_id,))
            self.conn.execute("DELETE FROM memories WHERE chat_id = ? AND (scope = 'chat' OR kind = 'summary_core')", (chat_id,))
            self.conn.execute("DELETE FROM chats WHERE id = ?", (chat_id,))
            self.conn.commit()
            self._changed()

    # ---------- message trees ----------

    def add_message(self, chat_id, parent_id, role, content="", reasoning="", tool_calls=None, tool_call_id=None,
                    meta=None, ooc=False, status="final", media=None, set_head=True):
        with self.lock:
            cur = self.conn.execute(
                "INSERT INTO messages (chat_id, parent_id, role, content, reasoning, tool_calls, tool_call_id, ooc, status, meta, created) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (chat_id, parent_id, role, content or "", reasoning or "",
                 json.dumps(tool_calls) if tool_calls else None, tool_call_id, int(bool(ooc)), status,
                 json.dumps(meta or {}), time.time()))
            mid = cur.lastrowid
            for a in media or []:
                self.conn.execute("INSERT INTO attachments (message_id, kind, mime, name, data) VALUES (?, ?, ?, ?, ?)",
                                  (mid, a["kind"], a["mime"], a["name"], a["data"]))
            if set_head:
                self.conn.execute("UPDATE chats SET head_id = ?, updated = ? WHERE id = ?", (mid, time.time(), chat_id))
            self.conn.commit()
            self._changed()
            return mid

    def update_message(self, mid, **fields):
        if "meta" in fields and isinstance(fields["meta"], dict):
            fields["meta"] = json.dumps(fields["meta"])
        if "tool_calls" in fields and isinstance(fields["tool_calls"], list):
            fields["tool_calls"] = json.dumps(fields["tool_calls"])
        sets = ", ".join(f"{k} = ?" for k in fields)
        with self.lock:
            self.x(f"UPDATE messages SET {sets} WHERE id = ?", (*fields.values(), mid))
            if "content" in fields:  # changed text: its old vectors would match words that are gone
                self.x("DELETE FROM vectors WHERE kind = 'msg' AND ref_id BETWEEN ? AND ?", (mid * 100, mid * 100 + 99))

    def msg(self, mid):
        m = self.one("SELECT * FROM messages WHERE id = ?", (mid,))
        if m:
            m["meta"] = json.loads(m["meta"] or "{}")
        return m

    def set_head(self, chat_id, mid):
        self.x("UPDATE chats SET head_id = ?, updated = ? WHERE id = ?", (mid, time.time(), chat_id))

    def _parents(self, chat_id):
        return {r["id"]: r["parent_id"] for r in self.q("SELECT id, parent_id FROM messages WHERE chat_id = ?", (chat_id,))}

    def path_ids(self, chat_id, head=None):
        """Message ids from the root to `head` (default: the chat's head)."""
        if head is None:
            c = self.one("SELECT head_id FROM chats WHERE id = ?", (chat_id,))
            head = c["head_id"] if c else None
        parents = self._parents(chat_id)
        out, cur, seen = [], head, set()
        while cur and cur in parents and cur not in seen:
            seen.add(cur)
            out.append(cur)
            cur = parents[cur]
        return out[::-1]

    def lineage(self, chat_id):
        """This chat and the chats it continues, oldest last."""
        out, cur = [], chat_id
        while cur and cur not in out and len(out) < 20:
            out.append(cur)
            cur = ((self.chat(cur) or {}).get("settings") or {}).get("continued_from")
        return out

    def visible_ids(self, chat_id):
        """Messages whose effects (memories, story book changes) count in this chat: its active path, plus the path of
        the chat it continues up to the point it was continued (and so on). Other chats of the same story, and
        branches that were rerolled away, are not included."""
        out, cur, head, depth = set(), chat_id, None, 0
        while cur and depth < 20:
            out.update(self.path_ids(cur, head))
            chat = self.chat(cur)
            s = (chat or {}).get("settings") or {}
            cur, head, depth = s.get("continued_from"), s.get("continued_head"), depth + 1
        return out

    def path(self, chat_id, head=None, ids=None):
        """Full message rows along the active path, in order, with meta decoded."""
        ids = ids if ids is not None else self.path_ids(chat_id, head)
        rows = {}
        for i in range(0, len(ids), 500):
            part = ids[i:i + 500]
            for r in self.q(f"SELECT * FROM messages WHERE id IN ({','.join('?' * len(part))})", part):
                r["meta"] = json.loads(r["meta"] or "{}")
                rows[r["id"]] = r
        return [rows[i] for i in ids if i in rows]

    def children(self, chat_id, parent_id):
        if parent_id is None:
            return [r["id"] for r in self.q("SELECT id FROM messages WHERE chat_id = ? AND parent_id IS NULL ORDER BY id", (chat_id,))]
        return [r["id"] for r in self.q("SELECT id FROM messages WHERE chat_id = ? AND parent_id = ? ORDER BY id",
                                        (chat_id, parent_id))]

    def deepest(self, chat_id, mid):
        """Follow the newest child down to a leaf (used when switching to another branch)."""
        kids = {}
        for r in self.q("SELECT id, parent_id FROM messages WHERE chat_id = ? ORDER BY id", (chat_id,)):
            kids.setdefault(r["parent_id"], []).append(r["id"])
        cur = mid
        while kids.get(cur):
            cur = kids[cur][-1]
        return cur

    def attachments(self, ids):
        out = {}
        for i in range(0, len(ids), 500):
            part = ids[i:i + 500]
            for a in self.q(f"SELECT id, message_id, kind, mime, name, data FROM attachments WHERE message_id IN "
                            f"({','.join('?' * len(part))}) ORDER BY id", part):
                out.setdefault(a["message_id"], []).append(a)
        return out


STORE = Store(CFG.DB_PATH)
