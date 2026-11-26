class Embedder:
    """Client for the llama-server embedding endpoint plus a vector index stored in SQLite (float16 BLOBs).
    Search is brute force with numpy; everything falls back to FTS when the embedder is not running."""

    def __init__(self, store, servers):
        self.store, self.servers = store, servers
        self.queue = []
        self.qlock = threading.Lock()
        self.cache = {}
        self.worker = None
        try:
            import numpy
            self.np = numpy
        except ImportError:
            self.np = None

    def ready(self):
        return self.np is not None and self.servers.embed_ready()

    def embed(self, texts, query=False):
        prefix = EMBEDDER["query_prefix"] if query else ""
        body = {"input": [prefix + t[:6000] for t in texts], "model": "embed"}
        status, text = Sys.http("POST", self.servers.embed_url() + "/v1/embeddings", body,
                                {"Authorization": f"Bearer {CFG.API_KEY}"}, timeout=120)
        if status != 200:
            raise RuntimeError(f"embedder {status}: {text[:200]}")
        vecs = [d["embedding"] for d in sorted(json.loads(text)["data"], key=lambda d: d["index"])]
        arr = self.np.asarray(vecs, dtype=self.np.float32)
        arr /= self.np.linalg.norm(arr, axis=1, keepdims=True) + 1e-9
        return arr

    def enqueue(self, kind, ref_id, text):
        if self.np is None or not (text or "").strip():
            return
        with self.qlock:
            pending = getattr(self, "pending", None)
            if pending is None:
                pending = self.pending = {}
            if (kind, ref_id) in pending:
                pending[(kind, ref_id)] = text  # already queued: embed the newest text once
                self.queue = [(k, r, text if (k, r) == (kind, ref_id) else t) for k, r, t in self.queue]
                return
            pending[(kind, ref_id)] = text
            self.queue.append((kind, ref_id, text))
            # The worker decides to stop under the same lock, so an item added now is never left behind.
            if not getattr(self, "working", False):
                self.working = True
                self.worker = threading.Thread(target=self._work, daemon=True)
                self.worker.start()

    def _work(self):
        while True:
            with self.qlock:
                batch, self.queue = self.queue[:32], self.queue[32:]
                if not batch:
                    self.working = False
                    return
            if not self.ready():
                time.sleep(2)
                with self.qlock:
                    self.queue = batch + self.queue
                if not self.servers.state.get("embed"):
                    with self.qlock:
                        self.working = False
                    return
                continue
            try:
                arr = self.embed([t for _, _, t in batch])
                rows = [(k, r, arr.shape[1], arr[i].astype(self.np.float16).tobytes()) for i, (k, r, _) in enumerate(batch)]
                self.store.many("INSERT OR REPLACE INTO vectors (kind, ref_id, dim, v) VALUES (?, ?, ?, ?)", rows)
                with self.qlock:
                    for k, r, t in batch:
                        if self.pending.get((k, r)) == t:
                            self.pending.pop((k, r), None)
                for k, _, _ in batch:
                    self.cache.pop(k, None)
            except Exception:
                time.sleep(5)

    def _matrix(self, kind):
        if kind not in self.cache:
            rows = self.store.q("SELECT ref_id, v FROM vectors WHERE kind = ?", (kind,))
            if not rows:
                self.cache[kind] = ([], None)
            else:
                mat = self.np.stack([self.np.frombuffer(r["v"], dtype=self.np.float16) for r in rows]).astype(self.np.float32)
                self.cache[kind] = ([r["ref_id"] for r in rows], mat)
        return self.cache[kind]

    def search(self, kind, query, limit=20, allowed=None):
        """[(ref_id, score)] by cosine similarity, restricted to `allowed` ids when given."""
        if not self.ready():
            return []
        ids, mat = self._matrix(kind)
        if mat is None:
            return []
        try:
            q = self.embed([query], query=True)[0]
        except Exception:
            return []
        scores = mat @ q
        order = self.np.argsort(-scores)
        out = []
        for i in order:
            if allowed is None or ids[i] in allowed:
                out.append((ids[i], float(scores[i])))
                if len(out) >= limit:
                    break
        return out

    def backfill(self):
        """Queue everything that has no vector yet (after Load, or when the embedder starts)."""
        have = {(r["kind"], r["ref_id"]) for r in self.store.q("SELECT kind, ref_id FROM vectors")}
        for kind, sql in (("mem", "SELECT id, text FROM memories"), ("fact", "SELECT id, claim AS text FROM facts"),
                          ("lore", "SELECT id, title || ': ' || text AS text FROM lore_entries"),
                          ("sum", "SELECT id, text FROM summaries"),
                          ("event", "SELECT id, text FROM world_events")):
            for r in self.store.q(sql):
                if (kind, r["id"]) not in have:
                    self.enqueue(kind, r["id"], r["text"])
        for r in self.store.q("SELECT id, content FROM messages WHERE role IN ('user', 'assistant') AND content != ''"):
            for i, piece in enumerate(Memory.chunks(r["content"])):
                if ("msg", r["id"] * 100 + i) not in have:
                    self.enqueue("msg", r["id"] * 100 + i, piece)


class Memory:
    """Scoped memories, the fact book, lore triggers, and hybrid recall (BM25 + vectors with RRF)."""

    SCOPES = ("user", "card", "story", "chat")

    def __init__(self, store, cards, stories, embedder):
        self.store, self.cards, self.stories, self.emb = store, cards, stories, embedder

    @staticmethod
    def chunks(text, size=1600, overlap=300):
        t = text or ""
        if len(t) <= size:
            return [t] if t.strip() else []
        return [t[i:i + size] for i in range(0, len(t), size - overlap)][:20]

    @staticmethod
    def rrf(*rankings, k=60):
        score = {}
        for ranking in rankings:
            for rank, rid in enumerate(ranking):
                score[rid] = score.get(rid, 0.0) + 1.0 / (k + rank + 1)
        return [rid for rid, _ in sorted(score.items(), key=lambda kv: -kv[1])]

    # ---------- scope filter ----------

    def ctx_of(self, chat_id):
        chat = self.store.chat(chat_id) or {}
        sid = chat.get("story_id")
        card_ids = [l["card_id"] for l in self.stories.card_links(sid)] if sid else []
        return {"chat_id": chat_id, "story_id": sid, "card_ids": card_ids}

    def _scope_sql(self, ctx):
        conds, args = ["m.scope = 'user'"], []
        if ctx.get("card_ids"):
            conds.append(f"(m.scope = 'card' AND m.card_id IN ({','.join('?' * len(ctx['card_ids']))}))")
            args += ctx["card_ids"]
        if ctx.get("story_id"):
            conds.append("(m.scope = 'story' AND m.story_id = ?)")
            args.append(ctx["story_id"])
        if ctx.get("chat_id"):
            conds.append("(m.scope = 'chat' AND m.chat_id = ?)")
            args.append(ctx["chat_id"])
        return "(" + " OR ".join(conds) + ")", args

    # ---------- memories ----------

    def save(self, text, scope, ctx, kind="fact", card_id=None):
        text = (text or "").strip()
        if not text:
            return {"error": "teks kosong"}
        scope = scope if scope in self.SCOPES else ("story" if ctx.get("story_id") else "user")
        if scope == "story" and not ctx.get("story_id"):
            scope = "user"
        cand = self.search(text, ctx, limit=8, kinds=(kind,))
        similar = []
        for c in cand:
            j = TXT.jaccard(text, c["text"])
            if j >= 0.8:
                return {"duplicate_of": c["id"], "note": "Sudah ada memory yang hampir sama; tidak disimpan ulang."}
            if j >= 0.45:
                similar.append({"id": c["id"], "text": c["text"][:300]})
        now = time.time()
        mid = self.store.x("INSERT INTO memories (scope, card_id, story_id, chat_id, kind, text, created, updated) "
                           "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                           (scope, card_id if scope == "card" else None,
                            ctx.get("story_id") if scope == "story" else None,
                            ctx.get("chat_id") if scope in ("chat",) or kind == "summary_core" else None,
                            kind, text, now, now))
        self.store.x("INSERT INTO memory_log (memory_id, action, after, chat_id, created) VALUES (?, 'save', ?, ?, ?)",
                     (mid, text, ctx.get("chat_id"), now))
        self.emb.enqueue("mem", mid, text)
        out = {"saved": mid, "scope": scope}
        if similar:
            out["similar"] = similar
            out["note"] = "Ada memory mirip. Kalau yang lama sudah tidak berlaku, pakai memory_update atau memory_forget."
        return out

    def update(self, mid, text, ctx):
        row = self.store.one("SELECT text FROM memories WHERE id = ?", (mid,))
        if not row:
            return {"error": f"memory #{mid} tidak ada"}
        self.store.x("UPDATE memories SET text = ?, updated = ? WHERE id = ?", (text.strip(), time.time(), mid))
        self.store.x("INSERT INTO memory_log (memory_id, action, before, after, chat_id, created) VALUES (?, 'update', ?, ?, ?, ?)",
                     (mid, row["text"], text.strip(), ctx.get("chat_id"), time.time()))
        self.emb.enqueue("mem", mid, text)
        return {"updated": mid}

    def forget(self, mid, ctx):
        row = self.store.one("SELECT * FROM memories WHERE id = ?", (mid,))
        if not row:
            return {"error": f"memory #{mid} tidak ada"}
        self.store.x("DELETE FROM memories WHERE id = ?", (mid,))
        self.store.x("DELETE FROM vectors WHERE kind = 'mem' AND ref_id = ?", (mid,))
        self.store.x("INSERT INTO memory_log (memory_id, action, before, chat_id, created) VALUES (?, 'forget', ?, ?, ?)",
                     (mid, json.dumps(row), ctx.get("chat_id"), time.time()))
        return {"deleted": mid}

    def undo(self, log_id):
        log = self.store.one("SELECT * FROM memory_log WHERE id = ? AND undone = 0", (log_id,))
        if not log:
            return False
        cur = self.store.one("SELECT text FROM memories WHERE id = ?", (log["memory_id"],))
        if log["action"] == "save":
            # ids are reused after a delete: only remove the row if it is still the memory this entry saved
            if not cur or cur["text"] != log["after"]:
                return False
            self.store.x("DELETE FROM memories WHERE id = ?", (log["memory_id"],))
            self.store.x("DELETE FROM vectors WHERE kind = 'mem' AND ref_id = ?", (log["memory_id"],))
        elif log["action"] == "update":
            if not cur or cur["text"] != log["after"]:
                return False
            self.store.x("UPDATE memories SET text = ?, updated = ? WHERE id = ?", (log["before"], time.time(), log["memory_id"]))
            self.emb.enqueue("mem", log["memory_id"], log["before"])
        elif log["action"] == "forget":
            r = json.loads(log["before"])
            cols = "scope, card_id, story_id, chat_id, kind, text, created, updated"
            vals = (r["scope"], r["card_id"], r["story_id"], r["chat_id"], r["kind"], r["text"], r["created"], time.time())
            if cur is None:
                new_id = self.store.x(f"INSERT INTO memories (id, {cols}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (r["id"],) + vals)
            else:  # the old id is taken by a newer memory: bring it back under a new id
                new_id = self.store.x(f"INSERT INTO memories ({cols}) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", vals)
            self.emb.enqueue("mem", new_id, r["text"])
        self.store.x("UPDATE memory_log SET undone = 1 WHERE id = ?", (log_id,))
        return True

    def log(self, chat_id=None, limit=50):
        sql = "SELECT * FROM memory_log" + (" WHERE chat_id = ?" if chat_id else "") + " ORDER BY id DESC LIMIT ?"
        return self.store.q(sql, ((chat_id, limit) if chat_id else (limit,)))

    def search(self, query, ctx, limit=8, kinds=("fact",), exclude=(), min_overlap=1):
        """Hybrid search over memories visible in this chat's scopes."""
        scope_sql, args = self._scope_sql(ctx)
        kind_sql = f"m.kind IN ({','.join('?' * len(kinds))})"
        q = TXT.fts_query(query)
        fts = []
        if q:
            fts = self.store.q(f"SELECT m.* FROM memories_fts f JOIN memories m ON m.id = f.rowid WHERE memories_fts MATCH ? "
                               f"AND {scope_sql} AND {kind_sql} ORDER BY bm25(memories_fts) LIMIT 40",
                               [q] + args + list(kinds))
            fts = [r for r in fts if TXT.overlap(query, r["text"]) >= min_overlap]
        allowed_rows = {r["id"]: r for r in fts}
        vec_ids = []
        if self.emb.ready():
            pool = {r["id"]: r for r in self.store.q(f"SELECT m.* FROM memories m WHERE {scope_sql} AND {kind_sql}",
                                                     args + list(kinds))}
            vec_ids = [i for i, s in self.emb.search("mem", query, limit=40, allowed=set(pool)) if s > 0.35]
            allowed_rows.update({i: pool[i] for i in vec_ids})
        ranked = self.rrf([r["id"] for r in fts], vec_ids)
        return [allowed_rows[i] for i in ranked if i in allowed_rows and i not in exclude][:limit]

    def recall(self, text, ctx, exclude=(), limit=10, max_chars=500):
        rows = self.search(text, ctx, limit=limit, kinds=("fact",), exclude=exclude, min_overlap=2)
        return [{"id": r["id"], "scope": r["scope"], "text": r["text"][:max_chars]} for r in rows]

    def frozen(self, ctx, limit_chars=8000):
        """Memories of scope user + the story's cards, shortened, for the frozen prompt."""
        args = []
        sql = "SELECT id, scope, text FROM memories WHERE kind = 'fact' AND (scope = 'user'"
        if ctx.get("card_ids"):
            sql += f" OR (scope = 'card' AND card_id IN ({','.join('?' * len(ctx['card_ids']))}))"
            args += ctx["card_ids"]
        rows = self.store.q(sql + ") ORDER BY id DESC LIMIT 60", args)
        lines = [f"- (#{r['id']}) {r['text'][:400]}" for r in reversed(rows)]
        return "\n".join(lines)[:limit_chars], [r["id"] for r in rows]

    # ---------- facts ----------

    def fact_lookup(self, query, world_card_id=None, limit=6):
        q = TXT.fts_query(query)
        where, args = ("AND (f2.world_card_id = ? OR f2.world_card_id IS NULL)", [world_card_id]) if world_card_id else ("", [])
        fts = self.store.q(f"SELECT f2.* FROM facts_fts f JOIN facts f2 ON f2.id = f.rowid WHERE facts_fts MATCH ? {where} "
                           f"ORDER BY bm25(facts_fts) LIMIT 30", [q] + args) if q else []
        rows = {r["id"]: r for r in fts}
        vec = []
        if self.emb.ready():
            pool = {r["id"]: r for r in self.store.q("SELECT * FROM facts" + (" WHERE world_card_id = ? OR world_card_id IS NULL"
                                                                               if world_card_id else ""), args)}
            vec = [i for i, s in self.emb.search("fact", query, limit=20, allowed=set(pool)) if s > 0.4]
            rows.update({i: pool[i] for i in vec})
        ranked = self.rrf([r["id"] for r in fts], vec)
        return [{k: rows[i][k] for k in ("id", "claim", "source_url", "source_title", "status", "confidence")}
                for i in ranked if i in rows][:limit]

    def fact_save(self, claim, source_url="", source_title="", world_card_id=None, confidence=0.8,
                  status="terverifikasi", tags=""):
        claim = (claim or "").strip()
        if not claim:
            return {"error": "klaim kosong"}
        for c in self.fact_lookup(claim, world_card_id, limit=5):
            if TXT.jaccard(claim, c["claim"]) >= 0.85:
                self.store.x("UPDATE facts SET source_url = ?, source_title = ?, checked = ?, confidence = ?, status = ? WHERE id = ?",
                             (source_url or c["source_url"], source_title or c["source_title"], time.time(), confidence,
                              status, c["id"]))
                return {"updated": c["id"]}
        fid = self.store.x("INSERT INTO facts (world_card_id, claim, source_url, source_title, checked, confidence, status, tags) "
                           "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                           (world_card_id, claim, source_url, source_title, time.time(), confidence, status, tags))
        self.emb.enqueue("fact", fid, claim)
        return {"saved": fid}

    # ---------- lore ----------

    def lore_triggered(self, card_ids, text, limit=12):
        """Lore entries (not core) whose keywords appear in `text`."""
        if not card_ids:
            return []
        low = (text or "").lower()
        rows = self.store.q(f"SELECT * FROM lore_entries WHERE core = 0 AND card_id IN ({','.join('?' * len(card_ids))})",
                            list(card_ids))
        hits = []
        for r in rows:
            keys = [k.strip().lower() for k in (r["keys"] or "").split(",") if k.strip()] or [r["title"].lower()]
            if any(re.search(rf"(?<!\w){re.escape(k)}(?!\w)", low) for k in keys):
                hits.append(r)
        return hits[:limit]

    def lore_core(self, card_ids):
        if not card_ids:
            return []
        return self.store.q(f"SELECT * FROM lore_entries WHERE core = 1 AND card_id IN ({','.join('?' * len(card_ids))}) "
                            f"ORDER BY kind, title", list(card_ids))


EMB = Embedder(STORE, SERVERS)
MEM = Memory(STORE, CARDS, STORIES, EMB)
