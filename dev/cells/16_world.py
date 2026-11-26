class World:
    """Things the code computes so the model cannot fudge them: world clock, player stats (with per-hour rates),
    character status, dice, weather, timeline events, and off-screen events. Everything follows the message tree:
    events attached to messages that are not on the active path are ignored."""

    UNITS = {"menit": 1, "min": 1, "jam": 60, "hour": 60, "hari": 1440, "day": 1440, "minggu": 10080,
             "week": 10080, "bulan": 43200, "month": 43200, "tahun": 525600}
    MONTHS = {m: i + 1 for i, m in enumerate(
        "januari februari maret april mei juni juli agustus september oktober november desember".split())}

    def __init__(self, store, cards, stories):
        self.store, self.cards, self.stories = store, cards, stories

    # ---------- helpers ----------

    @staticmethod
    def parse_time(text):
        return TXT.parse_datetime(text)

    @staticmethod
    def minutes(label):
        m = re.match(r"\s*(\d+(?:[.,]\d+)?)\s*([a-zA-Z]+)", label or "")
        if not m:
            return 0
        n = float(m.group(1).replace(",", "."))
        unit = next((v for k, v in World.UNITS.items() if m.group(2).lower().startswith(k)), 0)
        return int(n * unit)

    @staticmethod
    def fmt_span(minutes):
        m = int(minutes)
        for unit, size in (("bulan", 43200), ("minggu", 10080), ("hari", 1440), ("jam", 60)):
            if m >= size:
                n = m / size
                return f"{n:.0f} {unit}" if abs(n - round(n)) < 0.1 else f"{n:.1f} {unit}"
        return f"{m} menit"

    @staticmethod
    def fmt_time(dt):
        days = ["Sen", "Sel", "Rab", "Kam", "Jum", "Sab", "Min"]
        months = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
        return f"{days[dt.weekday()]} {dt.day} {months[dt.month - 1]} {dt.year} {dt.strftime('%H:%M')}"

    def _events(self, chat_id, path_ids):
        on_path = set(path_ids)
        rows = self.store.q("SELECT * FROM status_events WHERE chat_id = ? ORDER BY id", (chat_id,))
        return [r for r in rows if r["message_id"] is None or r["message_id"] in on_path]

    def _story_cards(self, chat_id):
        chat = self.store.chat(chat_id)
        return (chat or {}).get("story_id"), self.stories.cards_of((chat or {}).get("story_id"))

    # ---------- clock and stats ----------

    def start_time(self, cards):
        sc = cards.get("scenario")
        dt = self.parse_time((sc or {}).get("data", {}).get("start_time", "")) if sc else None
        return dt or datetime(2000, 1, 1, 8, 0)

    def stat_defs(self, cards):
        """[{key, label, min, max, start, rate}] from the world card, start values overridden by the scenario."""
        rows = Cards.table_rows(((cards.get("world") or {}).get("data") or {}).get("stats") or [],
                                ["key", "label", "min", "max", "awal", "laju per jam"])
        defs = []
        for cells in rows:

            def num(x, d=None):
                try:
                    return float(str(x).replace(",", "."))
                except (TypeError, ValueError):
                    return d
            if not str(cells[0]).strip():
                continue
            defs.append({"key": str(cells[0]).strip(), "label": str(cells[1] or cells[0]).strip(),
                         "min": num(cells[2]), "max": num(cells[3]), "start": num(cells[4], 0.0), "rate": num(cells[5], 0.0)})
        overrides = Cards.table_rows(((cards.get("scenario") or {}).get("data") or {}).get("start_stats") or [],
                                     ["key", "nilai"])
        for cells in overrides:
            for d in defs:
                if len(cells) > 1 and d["key"] == str(cells[0]).strip():
                    try:
                        d["start"] = float(str(cells[1]).replace(",", "."))
                    except ValueError:
                        pass
        return defs

    def state(self, chat_id, path_ids):
        """Replay events along the active path. Returns clock, turn, player stats, character status."""
        _, cards = self._story_cards(chat_id)
        now = self.start_time(cards)
        defs = {d["key"]: d for d in self.stat_defs(cards)}
        stats = {k: d["start"] for k, d in defs.items()}
        status = {}
        changes = {}

        def clamp(k, v):
            d = defs.get(k)
            if d and d["min"] is not None:
                v = max(d["min"], v)
            if d and d["max"] is not None:
                v = min(d["max"], v)
            return v

        for e in self._events(chat_id, path_ids):
            val = json.loads(e["value"])
            if e["subject"] == "world" and e["field"] == "time":
                if e["op"] == "set":
                    t = self.parse_time(str(val))
                    mins = (t - now).total_seconds() / 60 if t else 0
                    now = t or now
                else:
                    mins = float(val)
                    now = now + timedelta(minutes=mins)
                for k, d in defs.items():
                    if d["rate"] and mins > 0:
                        stats[k] = clamp(k, stats[k] + d["rate"] * mins / 60)
            elif e["subject"] == "player" and e["field"] in defs:
                before = stats[e["field"]]
                stats[e["field"]] = clamp(e["field"], float(val) if e["op"] == "set" else before + float(val))
                changes[e["field"]] = {"delta": stats[e["field"]] - before, "reason": e["reason"], "message_id": e["message_id"]}
            else:
                cur = status.setdefault(e["subject"], {})
                if e["op"] == "add" and isinstance(cur.get(e["field"]), list):
                    cur[e["field"]] = cur[e["field"]] + (val if isinstance(val, list) else [val])
                elif e["op"] == "remove" and isinstance(cur.get(e["field"]), list):
                    cur[e["field"]] = [x for x in cur[e["field"]] if x not in (val if isinstance(val, list) else [val])]
                else:
                    cur[e["field"]] = val
        turn = 0
        if path_ids:
            ids = ",".join(str(i) for i in path_ids[-5000:])
            turn = self.store.one(f"SELECT COUNT(*) AS n FROM messages WHERE id IN ({ids}) AND role = 'user' AND ooc = 0")["n"]
        return {"time": now, "time_text": self.fmt_time(now), "turn": turn,
                "stats": [{**defs[k], "value": round(v, 1), "change": changes.get(k)} for k, v in stats.items()],
                "status": status}

    def add_event(self, chat_id, message_id, subject, field, value, op="set", reason=""):
        return self.store.x("INSERT INTO status_events (chat_id, message_id, subject, field, op, value, reason, created) "
                            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                            (chat_id, message_id, subject, field, op, json.dumps(value), reason[:300], time.time()))

    def advance(self, chat_id, message_id, minutes, reason=""):
        if minutes:
            self.add_event(chat_id, message_id, "world", "time", float(minutes), op="add", reason=reason)

    def status_update(self, chat_id, message_id, subject, changes, reason=""):
        """changes: {field: value} for text fields, {stat: +n / -n} or {"stat": {"set": n}} for numbers."""
        _, cards = self._story_cards(chat_id)
        defs = {d["key"] for d in self.stat_defs(cards)}
        done = []
        for field, v in (changes or {}).items():
            if subject == "player" and field in defs:
                if isinstance(v, dict) and "set" in v:
                    self.add_event(chat_id, message_id, "player", field, float(v["set"]), "set", reason)
                else:
                    self.add_event(chat_id, message_id, "player", field, float(v), "add", reason)
            elif isinstance(v, dict) and ("add" in v or "remove" in v):
                op = "add" if "add" in v else "remove"
                self.add_event(chat_id, message_id, subject, field, v[op], op, reason)
            else:
                self.add_event(chat_id, message_id, subject, field, v, "set", reason)
            done.append(field)
        return done

    # ---------- dice ----------

    def roll(self, chat_id, message_id, event, odds):
        odds = min(max(float(odds), 0.0), 1.0)
        r = random.random()
        ok = r < odds
        self.store.x("INSERT INTO dice_log (chat_id, message_id, event, odds, roll, success, created) VALUES (?, ?, ?, ?, ?, ?, ?)",
                     (chat_id, message_id, event[:300], odds, r, int(ok), time.time()))
        return {"event": event, "odds": odds, "roll": round(r, 3), "success": ok}

    def dice_for(self, message_ids):
        if not message_ids:
            return {}
        rows = self.store.q(f"SELECT * FROM dice_log WHERE message_id IN ({','.join('?' * len(message_ids))}) ORDER BY id",
                            list(message_ids))
        out = {}
        for r in rows:
            out.setdefault(r["message_id"], []).append({"event": r["event"], "odds": r["odds"], "roll": r["roll"],
                                                        "success": bool(r["success"])})
        return out

    # ---------- weather and timeline ----------

    def weather(self, story_id, cards, dt):
        rows = Cards.table_rows(((cards.get("world") or {}).get("data") or {}).get("climate") or [],
                                ["bulan", "suhu min", "suhu max", "cuaca"])
        pick = None
        for cells in rows:
            key = str(cells[0]).strip().lower()
            if key == str(dt.month) or self.MONTHS.get(key) == dt.month:
                pick = cells
                break
            if key in ("*", "semua", "all") and pick is None:
                pick = cells
        if not pick:
            return None
        rng = random.Random(f"{story_id}-{dt.date().isoformat()}")
        try:
            lo, hi = float(pick[1]), float(pick[2])
        except (TypeError, ValueError):
            lo, hi = 10.0, 20.0
        kinds = [x.strip() for x in str(pick[3] or "cerah").split(",") if x.strip()] or ["cerah"]
        a = round(rng.uniform(lo, (lo + hi) / 2))
        b = round(rng.uniform((lo + hi) / 2, hi))
        return {"text": f"{rng.choice(kinds)}, {a}° s/d {b}°C"}

    def due_timeline(self, chat_id, cards, now, path_ids):
        world = cards.get("world")
        if not world:
            return []
        on_path = set(path_ids)
        fired = {r["kind"] for r in self.store.q("SELECT kind, message_id FROM world_events WHERE chat_id = ? AND kind LIKE 'timeline:%'",
                                                 (chat_id,)) if r["message_id"] is None or r["message_id"] in on_path}
        due = []
        for e in self.cards.timeline(world["id"]):
            t = self.parse_time(e["at"])
            if t and t <= now and f"timeline:{e['id']}" not in fired:
                due.append(e)
        return due

    # ---------- off-screen events ----------

    def add_world_event(self, chat_id, message_id, world_time, text, known_to=None, public=False, kind="kejadian"):
        return self.store.x("INSERT INTO world_events (chat_id, message_id, world_time, text, kind, known_to, public, shown, created) "
                            "VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)",
                            (chat_id, message_id, str(world_time), text[:2000], kind, json.dumps(known_to or []),
                             int(bool(public)), time.time()))

    def world_events(self, chat_id, path_ids, who=None, unseen_only=False, limit=30):
        on_path = set(path_ids)
        rows = self.store.q("SELECT * FROM world_events WHERE chat_id = ? ORDER BY id DESC LIMIT 500", (chat_id,))
        out = []
        for r in rows:
            if r["message_id"] is not None and r["message_id"] not in on_path:
                continue
            known = json.loads(r["known_to"] or "[]")
            if who and not (r["public"] or who in known):
                continue
            if unseen_only and r["shown"]:
                continue
            out.append({**r, "known_to": known})
            if len(out) >= limit:
                break
        return out[::-1]

    def events_after(self, chat_id, after_id, who="player"):
        rows = self.store.q("SELECT * FROM world_events WHERE chat_id = ? AND id > ? ORDER BY id", (chat_id, after_id))
        return [r for r in rows if r["public"] or who in json.loads(r["known_to"] or "[]")]

    def last_event_id(self, chat_id):
        r = self.store.one("SELECT MAX(id) AS m FROM world_events WHERE chat_id = ?", (chat_id,))
        return (r or {}).get("m") or 0

    def mark_shown(self, ids):
        if ids:
            self.store.x(f"UPDATE world_events SET shown = 1 WHERE id IN ({','.join('?' * len(ids))})", list(ids))


WORLD = World(STORE, CARDS, STORIES)
