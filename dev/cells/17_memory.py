class Embedder:
    """Client for the llama-server embedding endpoint plus a vector index stored in SQLite (float16 BLOBs).
    Search is brute force with numpy; everything falls back to FTS when the embedder is not running."""

    def __init__(self, store, servers):
        self.store, self.servers = store, servers
        self.queue = []      # keys (kind, ref_id) waiting, oldest first
        self.pending = {}    # key -> newest text; a key stays here while queued or being embedded
        self.qlock = threading.Lock()
        self.cache = {}      # kind -> (ids, matrix)
        self.qcache = {}     # (model, query) -> vector, a small LRU
        self.worker = None
        self.working = False
        self.gen = 0         # bumped when queued work no longer applies (Load, model change)
        self.dim = None      # size of the vectors the running model returns
        self._model = None
        self.backfilling = False
        try:
            import numpy
            self.np = numpy
        except ImportError:
            self.np = None

    def ready(self):
        if self.np is None or not self.servers.embed_ready():
            return False
        model = self.servers.state.get("embed_model") or "0.6B"
        if model != self._model:  # switched (Model tab, restart, Load): check the stored vectors once
            self._model = model
            self.dim = None
            try:
                self.check_model()
            except Exception:
                pass
        return True

    def reset(self):
        """Drop queued work (after Load the ids belong to another database)."""
        with self.qlock:
            self.queue = []
            self.pending = {}
            self.gen += 1
        self.cache.clear()
        self.qcache.clear()

    def check_model(self):
        """Vectors from another embedder model cannot be compared: rebuild them when the model changed. A database
        with no record of the model keeps only vectors of the running model's size."""
        model = self.servers.state.get("embed_model") or "0.6B"
        have = self.store.meta_get("embed_model")
        if have == model:
            return
        with self.qlock:
            self.gen += 1  # a batch being embedded by the old model must not land
            self.queue = list(self.pending)
        if have is not None:
            self.store.x("DELETE FROM vectors")
        else:
            try:
                self.embed(["dim"])
                self.store.x("DELETE FROM vectors WHERE dim != ?", (self.dim,))
            except Exception:
                pass
        self.cache.clear()
        self.qcache.clear()
        self.store.meta_set("embed_model", model)

    def embed(self, texts, query=False):
        prefix = self.servers.embed_spec()["query_prefix"] if query else ""
        body = {"input": [prefix + t[:6000] for t in texts], "model": "embed"}
        status, text = Sys.http("POST", self.servers.embed_url() + "/v1/embeddings", body,
                                {"Authorization": f"Bearer {CFG.API_KEY}"}, timeout=120)
        if status != 200:
            raise RuntimeError(f"embedder {status}: {text[:200]}")
        vecs = [d["embedding"] for d in sorted(json.loads(text)["data"], key=lambda d: d["index"])]
        arr = self.np.asarray(vecs, dtype=self.np.float32)
        arr /= self.np.linalg.norm(arr, axis=1, keepdims=True) + 1e-9
        self.dim = int(arr.shape[1])
        return arr

    def enqueue(self, kind, ref_id, text):
        if self.np is None or not (text or "").strip():
            return
        key = (kind, ref_id)
        with self.qlock:
            if key in self.pending:
                self.pending[key] = text  # already queued or being embedded: the newest text is embedded once
                return
            self.pending[key] = text
            self.queue.append(key)
            # The worker decides to stop under the same lock, so an item added now is never left behind.
            if not self.working:
                self.working = True
                self.worker = threading.Thread(target=self._work, daemon=True)
                self.worker.start()

    def _settle(self, batch):
        """After a batch, done or failed (call with qlock): keys whose text changed meanwhile go back in the queue;
        the rest leave pending (a failed one is queued again by the next backfill)."""
        for k, t in batch:
            if k not in self.pending:
                continue
            if self.pending[k] == t:
                self.pending.pop(k)
            else:
                self.queue.append(k)

    def _work(self):
        while True:
            with self.qlock:
                keys, self.queue = self.queue[:32], self.queue[32:]
                if not keys:
                    self.working = False
                    return
                gen = self.gen
                batch = [(k, self.pending[k]) for k in keys if k in self.pending]
            if not batch:
                continue
            if not self.ready():
                time.sleep(2)
                with self.qlock:
                    if gen == self.gen:
                        self.queue = [k for k, _ in batch] + self.queue
                    if not self.servers.state.get("embed"):
                        self.working = False
                        return
                continue
            try:
                arr = self.embed([t for _, t in batch])
            except Exception:
                with self.qlock:
                    self._settle(batch)
                time.sleep(5)
                continue
            with self.qlock:
                stale = gen != self.gen
                if stale:  # Load or a model change happened meanwhile: embed again what is still wanted
                    self.queue += [k for k, _ in batch if k in self.pending]
            if stale:
                continue
            rows = [(k[0], k[1], arr.shape[1], arr[i].astype(self.np.float16).tobytes()) for i, (k, _) in enumerate(batch)]
            self.store.many("INSERT OR REPLACE INTO vectors (kind, ref_id, dim, v) VALUES (?, ?, ?, ?)", rows)
            with self.qlock:
                self._settle(batch)
            for kind in {k[0] for k, _ in batch}:
                self.cache.pop(kind, None)

    def _matrix(self, kind):
        hit = self.cache.get(kind)
        if hit is None:
            dim = self.dim or self.servers.embed_spec()["dim"]
            rows = self.store.q("SELECT ref_id, v FROM vectors WHERE kind = ? AND dim = ?", (kind, dim))
            if not rows:
                hit = ([], None)
            else:
                mat = self.np.stack([self.np.frombuffer(r["v"], dtype=self.np.float16) for r in rows]).astype(self.np.float32)
                hit = ([r["ref_id"] for r in rows], mat)
            self.cache[kind] = hit
        return hit

    def _query_vec(self, query):
        key = (self._model, query)
        v = self.qcache.get(key)
        if v is None:
            v = self.embed([query], query=True)[0]
            self.qcache[key] = v
            while len(self.qcache) > 64:
                try:
                    self.qcache.pop(next(iter(self.qcache)))
                except (StopIteration, KeyError, RuntimeError):
                    break
        return v

    def search(self, kind, query, limit=20, allowed=None):
        """[(ref_id, score)] by cosine similarity, restricted to `allowed` ids when given."""
        if not self.ready():
            return []
        ids, mat = self._matrix(kind)
        if mat is None:
            return []
        try:
            scores = mat @ self._query_vec(query)
        except Exception:  # embedder down, or a vector of another size
            return []
        order = self.np.argsort(-scores)
        out = []
        for i in order:
            if allowed is None or ids[i] in allowed:
                out.append((ids[i], float(scores[i])))
                if len(out) >= limit:
                    break
        return out

    def backfill(self):
        """Queue everything that has no vector yet (after Load, or when the embedder starts). One at a time."""
        if self.backfilling:
            return
        self.backfilling = True
        try:
            self._backfill()
        finally:
            self.backfilling = False

    def _backfill(self):
        if self.ready():
            self.check_model()
        have = {(r["kind"], r["ref_id"]) for r in self.store.q("SELECT kind, ref_id FROM vectors")}
        for kind, sql in (("mem", "SELECT id, text FROM memories"), ("fact", "SELECT id, claim AS text FROM facts"),
                          ("lore", "SELECT id, title || ': ' || text AS text FROM lore_entries"),
                          ("sum", "SELECT id, text FROM summaries"),
                          ("event", "SELECT id, text FROM world_events"),
                          ("know", "SELECT id, text FROM knowledge"),
                          ("canon", "SELECT id, section || ': ' || text AS text FROM canon_log WHERE text != ''")):
            for r in self.store.q(sql):
                if (kind, r["id"]) not in have:
                    self.enqueue(kind, r["id"], r["text"])
        # cards change: re-embed a card when its version is newer than the one embedded
        done = self.store.meta_get("emb_cards", {}) or {}
        changed = False
        for c in self.store.q("SELECT id, version FROM cards"):
            if done.get(str(c["id"])) != c["version"] or ("card", c["id"]) not in have:
                card = CARDS.get(c["id"])
                text = CARDS.render(card, mode="all", limit=4000) if card else ""
                if text:
                    self.enqueue("card", c["id"], text)
                    done[str(c["id"])] = c["version"]
                    changed = True
        if changed:
            self.store.meta_set("emb_cards", done)
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
        return {"chat_id": chat_id, "story_id": sid, "card_ids": card_ids,
                "visible": self.store.visible_ids(chat_id) if chat_id else set()}

    BRANCHED = ("story", "chat")  # user and card memories are about the real user / the character everywhere

    def _visible(self, row, ctx):
        """A story/chat memory made by a message counts only where that message is on the path; a forget made by a
        turn hides it only on that turn's branch (several branches can each forget it). Memories made outside a chat
        count everywhere."""
        if row.get("scope") not in self.BRANCHED or "visible" not in ctx:
            return True
        vis = ctx["visible"]
        if row.get("message_id") and row["message_id"] not in vis:
            return False
        if not row.get("forgotten_at"):  # set while any branch has forgotten it
            return True
        hides = self.store.q("SELECT message_id FROM memory_log WHERE memory_id = ? AND action = 'hide' AND undone = 0",
                             (row["id"],))
        return not any(h["message_id"] in vis for h in hides)

    def _resolve(self, rows, ctx):
        """Visible rows, with updates made on other branches undone."""
        rows = [dict(r) for r in rows if self._visible(r, ctx)]
        vis = ctx.get("visible")
        if not rows or vis is None:
            return rows
        ids = [r["id"] for r in rows]
        logs = {}
        for i in range(0, len(ids), 500):
            part = ids[i:i + 500]
            for lg in self.store.q(f"SELECT memory_id, action, before, after, message_id FROM memory_log WHERE action IN "
                                   f"('save', 'update') AND undone = 0 AND memory_id IN ({','.join('?' * len(part))}) ORDER BY id",
                                   part):
                logs.setdefault(lg["memory_id"], []).append(lg)
        for r in rows:
            # replay in order: the saved text, then each update this branch can see
            seq = logs.get(r["id"], [])
            if not any(lg["action"] == "update" for lg in seq):
                continue
            text = next((lg["after"] for lg in seq if lg["action"] == "save"), None)
            if text is None:
                text = next(lg["before"] for lg in seq if lg["action"] == "update")
            for lg in seq:
                if lg["action"] == "update" and (not lg["message_id"] or lg["message_id"] in vis):
                    text = lg["after"]
            r["text"] = text
        return rows

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

    def save(self, text, scope, ctx, kind="fact", card_id=None, message_id=None, importance=0.5):
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
        try:
            importance = min(max(float(importance), 0.0), 1.0)
        except (TypeError, ValueError):
            importance = 0.5
        mid = self.store.x("INSERT INTO memories (scope, card_id, story_id, chat_id, kind, text, created, updated, message_id, "
                           "importance) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                           (scope, card_id if scope == "card" else None,
                            ctx.get("story_id") if scope == "story" else None,
                            ctx.get("chat_id") if scope in ("chat",) or kind == "summary_core" else None,
                            kind, text, now, now, message_id, importance))
        self.store.x("INSERT INTO memory_log (memory_id, action, after, chat_id, created, message_id) VALUES (?, 'save', ?, ?, ?, ?)",
                     (mid, text, ctx.get("chat_id"), now, message_id))
        self.emb.enqueue("mem", mid, text)
        out = {"saved": mid, "scope": scope}
        if similar:
            out["similar"] = similar
            out["note"] = "Ada memory mirip. Kalau yang lama sudah tidak berlaku, pakai memory_update atau memory_forget."
        return out

    def update(self, mid, text, ctx, message_id=None):
        row = self.store.one("SELECT * FROM memories WHERE id = ?", (mid,))
        if not row or not self._visible(row, ctx):
            return {"error": f"memory #{mid} tidak ada"}
        before = self._resolve([row], ctx)[0]["text"]
        self.store.x("UPDATE memories SET text = ?, updated = ? WHERE id = ?", (text.strip(), time.time(), mid))
        self.store.x("INSERT INTO memory_log (memory_id, action, before, after, chat_id, created, message_id) "
                     "VALUES (?, 'update', ?, ?, ?, ?, ?)", (mid, before, text.strip(), ctx.get("chat_id"), time.time(), message_id))
        self.emb.enqueue("mem", mid, text)
        return {"updated": mid}

    def forget(self, mid, ctx, message_id=None):
        """From a turn (message_id) a story/chat memory is only hidden on that branch; from the UI it is deleted."""
        row = self.store.one("SELECT * FROM memories WHERE id = ?", (mid,))
        if not row or (message_id and not self._visible(row, ctx)):
            return {"error": f"memory #{mid} tidak ada"}
        if message_id and row["scope"] in self.BRANCHED:
            self.store.x("UPDATE memories SET forgotten_at = ? WHERE id = ?", (message_id, mid))
            self.store.x("INSERT INTO memory_log (memory_id, action, before, chat_id, created, message_id) "
                         "VALUES (?, 'hide', ?, ?, ?, ?)", (mid, json.dumps(row), ctx.get("chat_id"), time.time(), message_id))
            return {"deleted": mid}
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
        elif log["action"] == "hide":
            pass  # marking the log undone below is what brings it back on that branch
        elif log["action"] == "forget":
            r = json.loads(log["before"])
            cols = "scope, card_id, story_id, chat_id, kind, text, created, updated, message_id, importance"
            vals = (r["scope"], r["card_id"], r["story_id"], r["chat_id"], r["kind"], r["text"], r["created"], time.time(),
                    r.get("message_id"), r.get("importance", 0.5))
            if cur is None:
                new_id = self.store.x(f"INSERT INTO memories (id, {cols}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (r["id"],) + vals)
            else:  # the old id is taken by a newer memory: bring it back under a new id
                new_id = self.store.x(f"INSERT INTO memories ({cols}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", vals)
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
        rows = self._resolve([allowed_rows[i] for i in ranked if i in allowed_rows and i not in exclude], ctx)
        # more important memories first among similarly relevant ones
        rows = [r for _, r in sorted(enumerate(rows), key=lambda p: p[0] - 6 * (float(p[1].get("importance") or 0.5) - 0.5))]
        return rows[:limit]

    def recall(self, text, ctx, exclude=(), limit=10, max_chars=500):
        rows = self.search(text, ctx, limit=limit, kinds=("fact",), exclude=exclude, min_overlap=2)
        return [{"id": r["id"], "scope": r["scope"], "text": r["text"][:max_chars], "importance": r.get("importance", 0.5)}
                for r in rows]

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
        if len(hits) < limit and text and self.emb.ready():
            by_id = {r["id"]: r for r in rows}
            have = {r["id"] for r in hits}
            for i, s in self.emb.search("lore", text[-2000:], limit=4, allowed=set(by_id) - have):
                if s >= 0.55:
                    hits.append(by_id[i])
        return hits[:limit]

    def lore_core(self, card_ids):
        if not card_ids:
            return []
        return self.store.q(f"SELECT * FROM lore_entries WHERE core = 1 AND card_id IN ({','.join('?' * len(card_ids))}) "
                            f"ORDER BY kind, title", list(card_ids))


class Knowledge:
    """What each character knows or believes in one chat (and the chats it continues), on the active branch.
    The story book is the truth only the narrator sees; this is what is in each head, and it can be wrong."""

    KINDS = ("fakta", "rahasia", "pendapat", "perasaan", "janji", "salah paham", "kenalan")
    SOURCES = ("lihat sendiri", "diberi tahu", "gosip", "menduga")
    TRUTH = ("benar", "keliru", "belum pasti")

    def __init__(self, store):
        self.store = store

    @staticmethod
    def _hides(r):
        return {int(x) for x in (r.get("hidden_at") or "").split(",") if x.strip().isdigit()}

    def _rows(self, chat_id, sql="", args=(), hidden=False):
        """Rows that count on the active branch; hidden=True: the ones forgotten on it instead."""
        chats = self.store.lineage(chat_id)
        vis = self.store.visible_ids(chat_id)
        rows = self.store.q(f"SELECT * FROM knowledge WHERE chat_id IN ({','.join('?' * len(chats))}) {sql}",
                            list(chats) + list(args)) if chats else []

        def forgotten(r):
            return bool(r["forgotten_at"] and r["forgotten_at"] in vis) or bool(self._hides(r) & vis)
        return [r for r in rows if (not r["message_id"] or r["message_id"] in vis) and forgotten(r) == hidden]

    def hide(self, kid, message_id):
        """The user's delete: forgotten on the branches through message_id only, and restorable."""
        r = self.store.one("SELECT hidden_at FROM knowledge WHERE id = ?", (kid,))
        if r:
            ids = sorted(self._hides(r) | {int(message_id)})
            self.store.x("UPDATE knowledge SET hidden_at = ? WHERE id = ?", (",".join(map(str, ids)), kid))

    def restore(self, kid, chat_id):
        """Undo every forget of this row that lies on the active branch (the user's deletes and the model's)."""
        r = self.store.one("SELECT hidden_at, forgotten_at FROM knowledge WHERE id = ?", (kid,))
        if not r:
            return
        vis = self.store.visible_ids(chat_id)
        self.store.x("UPDATE knowledge SET hidden_at = ?, forgotten_at = ? WHERE id = ?",
                     (",".join(map(str, sorted(self._hides(r) - vis))),
                      None if r["forgotten_at"] in vis else r["forgotten_at"], kid))

    def hidden(self, chat_id, holder, limit=100):
        return sorted(self._rows(chat_id, "AND holder = ?", (holder,), hidden=True), key=lambda r: -r["id"])[:limit]

    def add(self, chat_id, message_id, holders, text, kind="fakta", source="lihat sendiri", source_who="", truth="benar",
            importance=0.5, world_time=""):
        text = (text or "").strip()
        if not text:
            raise ValueError("teks kosong")
        kind = kind if kind in self.KINDS else "fakta"
        source = source if source in self.SOURCES else "lihat sendiri"
        truth = truth if truth in self.TRUTH else "benar"
        try:
            importance = min(max(float(importance), 0.0), 1.0)
        except (TypeError, ValueError):
            importance = 0.5
        out = []
        for h in dict.fromkeys(holders):
            same = [r for r in self._rows(chat_id, "AND holder = ?", (h,)) if TXT.jaccard(text, r["text"]) >= 0.8]
            if same:
                out.append(same[0]["id"])
                continue
            kid = self.store.x("INSERT INTO knowledge (chat_id, message_id, holder, text, kind, source, source_who, truth, "
                               "importance, world_time, created) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                               (chat_id, message_id, h, text[:2000], kind, source, source_who or "", truth, importance,
                                str(world_time or ""), time.time()))
            EMB.enqueue("know", kid, text)
            out.append(kid)
        return out

    def acquainted(self, chat_id, holder, player_names=()):
        """The holder has met the player on this branch: a 'kenalan' entry, or anything they know that names the player."""
        pats = [re.compile(r"(?<!\w)" + re.escape(n.lower()) + r"(?!\w)") for n in player_names if n]
        for r in self._rows(chat_id, "AND holder = ?", (holder,)):
            if r["kind"] == "kenalan" or any(p.search((r["text"] or "").lower()) for p in pats):
                return True
        return False

    def holders(self, chat_id):
        return sorted({r["holder"] for r in self._rows(chat_id)})

    def of(self, chat_id, holder, limit=200):
        rows = self._rows(chat_id, "AND holder = ?", (holder,))
        return sorted(rows, key=lambda r: -r["id"])[:limit]

    def relevant(self, chat_id, holder, query, limit=6):
        """The holder's knowledge most related to the scene: keyword match first, then importance, then recency."""
        rows = self._rows(chat_id, "AND holder = ?", (holder,))
        if not rows:
            return []
        q = TXT.fts_query(query or "")
        hit = {}
        if q:
            ids = {r["id"] for r in rows}
            for rank, r in enumerate(self.store.q("SELECT k.id FROM knowledge_fts f JOIN knowledge k ON k.id = f.rowid "
                                                  "WHERE knowledge_fts MATCH ? AND k.chat_id = ? AND k.holder = ? "
                                                  "ORDER BY bm25(knowledge_fts) LIMIT 200", (q, chat_id, holder))):
                if r["id"] in ids:
                    hit[r["id"]] = rank
        sim = {}
        if query and EMB.ready():  # by meaning too, when the embedder runs
            sim = {i: s for i, s in EMB.search("know", query, limit=40, allowed={r["id"] for r in rows}) if s > 0.3}
        newest = max(r["id"] for r in rows)

        def score(r):
            s = (3.0 - min(hit[r["id"]], 30) / 10) if r["id"] in hit else 0.0
            s += 4 * max(0.0, sim.get(r["id"], 0.0) - 0.3)
            return s + 2 * float(r["importance"] or 0.5) + (0.5 if r["id"] > newest - 20 else 0)
        return sorted(rows, key=score, reverse=True)[:limit]

    def forget(self, kid, chat_id=None, message_id=None):
        if message_id:
            self.store.x("UPDATE knowledge SET forgotten_at = ? WHERE id = ?", (message_id, kid))
        else:
            self.store.x("DELETE FROM knowledge WHERE id = ?", (kid,))
            self.store.x("DELETE FROM vectors WHERE kind = 'know' AND ref_id = ?", (kid,))

    def edit(self, kid, **fields):
        allowed = {k: v for k, v in fields.items() if k in ("text", "kind", "truth", "source", "source_who", "importance")}
        if allowed:
            sets = ", ".join(f"{k} = ?" for k in allowed)
            self.store.x(f"UPDATE knowledge SET {sets} WHERE id = ?", (*allowed.values(), kid))
            if "text" in allowed:
                EMB.enqueue("know", kid, allowed["text"])

    @staticmethod
    def line(r):
        tags = [r["kind"]] if r["kind"] != "fakta" else []
        if r["truth"] != "benar":
            tags.append(r["truth"].upper())
        src = r["source"] + (f" dari {r['source_who']}" if r["source_who"] else "")
        return f"- {r['text']} ({src}{'; ' + ', '.join(tags) if tags else ''})"


KNOW = Knowledge(STORE)
EMB = Embedder(STORE, SERVERS)
MEM = Memory(STORE, CARDS, STORIES, EMB)
