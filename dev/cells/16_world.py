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
        seen_at = {}  # subject -> field -> world time it was last set

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
                seen_at.setdefault(e["subject"], {})[e["field"]] = now
                items = val if isinstance(val, list) else [val]
                old = cur.get(e["field"])
                old = old if isinstance(old, list) else ([] if old in (None, "") else [old])
                if e["op"] == "add":  # a list field that does not exist yet starts as a list
                    cur[e["field"]] = old + [x for x in items if x not in old]
                elif e["op"] == "remove":
                    cur[e["field"]] = [x for x in old if x not in items]
                else:
                    cur[e["field"]] = val
        turn = 0
        if path_ids:
            ids = ",".join(str(i) for i in path_ids[-5000:])
            turn = self.store.one(f"SELECT COUNT(*) AS n FROM messages WHERE id IN ({ids}) AND role = 'user' AND ooc = 0")["n"]
        return {"time": now, "time_text": self.fmt_time(now), "turn": turn,
                "stats": [{**defs[k], "value": round(v, 1), "change": changes.get(k)} for k, v in stats.items()],
                "status": status, "seen_at": seen_at}

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
        if not isinstance(changes, dict):
            raise ValueError("changes harus objek {field: nilai}")
        # Check everything first: a retry after an error must not apply the first half twice.
        planned = []
        for field, v in changes.items():
            if subject == "player" and field in defs:
                if isinstance(v, dict) and "set" in v:
                    planned.append(("player", field, float(str(v["set"]).replace(",", ".")), "set"))
                else:
                    planned.append(("player", field, float(str(v).replace(",", ".").replace("+", "")), "add"))
            elif isinstance(v, dict) and ("add" in v or "remove" in v):
                op = "add" if "add" in v else "remove"
                planned.append((subject, field, v[op], op))
            else:
                planned.append((subject, field, v, "set"))
        for subj, field, value, op in planned:
            self.add_event(chat_id, message_id, subj, field, value, op, reason)
        return [p[1] for p in planned]

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
            # shown = id of the reply that told the player (1 = shown before this was tracked per branch)
            if unseen_only and r["shown"] and (r["shown"] == 1 or r["shown"] in on_path):
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

    # ---------- schedules and travel ----------

    SCHEDULE_STALE_HOURS = 4

    @staticmethod
    def _hour_in(spec, hour):
        """'8', '08-12', '22-06', '08:00-12:30' -> whether hour falls inside (end exclusive, wraps at midnight)."""
        nums = [int(x) for x in re.findall(r"(\d{1,2})(?:[:.]\d{2})?", str(spec or ""))]
        if not nums:
            return False
        a, b = (nums[0], nums[1]) if len(nums) > 1 else (nums[0], nums[0] + 1)
        return a <= hour < b if a < b else (hour >= a or hour < b)

    def with_schedule(self, st, cards):
        """Status with locations from the characters' schedules where nobody has seen them for a few hours
        (or ever). Those get location_from = 'jadwal'."""
        out = {k: dict(v) for k, v in st["status"].items()}
        now = st["time"]
        for ch in (cards or {}).get("character", []):
            rows = Cards.table_rows(ch["data"].get("schedule") or [], ["jam", "lokasi", "kegiatan"])
            if not rows:
                continue
            if str((st["status"].get(ch["name"]) or {}).get("keadaan") or "").lower() in ("ditahan", "pingsan", "mati", "pergi"):
                continue
            seen = (st.get("seen_at") or {}).get(ch["name"], {}).get("location")
            if seen and (now - seen).total_seconds() < self.SCHEDULE_STALE_HOURS * 3600:
                continue
            row = next((r for r in rows if self._hour_in(r[0], now.hour)), None)
            if row and row[1]:
                cur = out.setdefault(ch["name"], {})
                cur.update(location=row[1], location_from="jadwal")
                if row[2]:
                    cur["activity"] = row[2]
        return out

    @staticmethod
    def travel_minutes(cards, a, b):
        """Minutes between two places from the world card, either direction; None if unknown."""
        norm = lambda s: re.sub(r"\s+", " ", str(s or "").strip().lower())
        a, b = norm(a), norm(b)
        if not a or not b or a == b:
            return None
        rows = Cards.table_rows(((cards.get("world") or {}).get("data") or {}).get("locations") or [], ["dari", "ke", "menit"])
        for r in rows:
            x, y = norm(r[0]), norm(r[1])
            if {x, y} == {a, b} or (x in a and y in b) or (x in b and y in a):
                try:
                    return int(float(str(r[2]).replace(",", ".")))
                except ValueError:
                    return None
        return None

    def travel_from(self, cards, here):
        rows = Cards.table_rows(((cards.get("world") or {}).get("data") or {}).get("locations") or [], ["dari", "ke", "menit"])
        norm = lambda s: re.sub(r"\s+", " ", str(s or "").strip().lower())
        out = []
        for r in rows:
            if norm(r[0]) == norm(here):
                out.append((r[1], r[2]))
            elif norm(r[1]) == norm(here):
                out.append((r[0], r[2]))
        return out

    def mark_shown(self, ids, message_id):
        """Remember which reply told the player: a reroll on another branch still gets the news."""
        if ids:
            self.store.x(f"UPDATE world_events SET shown = ? WHERE id IN ({','.join('?' * len(ids))})",
                         [int(message_id) if message_id and int(message_id) != 1 else 2] + list(ids))


class Threads:
    """Open story threads on the active branch: promises, mysteries, clues, debts, grudges, appointments.
    A thread can have a deadline on the world clock; overdue ones are pointed out to the GM and the world tick."""

    KINDS = ("janji", "janji temu", "misteri", "petunjuk", "utang", "dendam", "rencana", "lain")
    CLOSED = ("selesai", "gagal", "batal")

    def __init__(self, store):
        self.store = store

    def open(self, chat_id, message_id, kind, title, text="", who="", due="", opened_at=""):
        title = (title or "").strip()
        if not title:
            raise ValueError("judul kosong")
        kind = kind if kind in self.KINDS else "lain"
        due_dt = TXT.parse_datetime(due) if due else None
        if due and not due_dt:
            raise ValueError("tenggat harus YYYY-MM-DD HH:MM")
        chat = self.store.chat(chat_id) or {}
        who = ", ".join(who) if isinstance(who, list) else str(who or "")
        for r in self.list(chat_id):  # already open on this branch: the same thread, not a new one
            if r["kind"] == kind and TXT.jaccard(r["title"], title) >= 0.6:
                return r["id"]
        return self.store.x("INSERT INTO threads (story_id, chat_id, message_id, kind, title, text, who, due, opened_at, created) "
                            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            (chat.get("story_id"), chat_id, message_id, kind, title[:200], (text or "")[:1500], who[:300],
                             due_dt.strftime("%Y-%m-%d %H:%M") if due_dt else "", str(opened_at or ""), time.time()))

    def close(self, chat_id, message_id, thread_id, status="selesai", note=""):
        status = status if status in self.CLOSED + ("terbuka",) else "selesai"
        self.store.x("INSERT INTO thread_events (thread_id, chat_id, message_id, status, note, created) VALUES (?, ?, ?, ?, ?, ?)",
                     (int(thread_id), chat_id, message_id, status, (note or "")[:500], time.time()))

    def list(self, chat_id, now=None, include_closed=False):
        """Threads visible on this branch with their current status; overdue ones flagged and first."""
        chats = self.store.lineage(chat_id)
        if not chats:
            return []
        vis = self.store.visible_ids(chat_id)
        marks = ",".join("?" * len(chats))
        rows = [r for r in self.store.q(f"SELECT * FROM threads WHERE chat_id IN ({marks}) ORDER BY id", list(chats))
                if not r["message_id"] or r["message_id"] in vis]
        events = {}
        for e in self.store.q(f"SELECT * FROM thread_events WHERE chat_id IN ({marks}) ORDER BY id", list(chats)):
            if not e["message_id"] or e["message_id"] in vis:
                events[e["thread_id"]] = e
        out = []
        for r in rows:
            e = events.get(r["id"])
            r["status"] = e["status"] if e else "terbuka"
            r["note"] = e["note"] if e else ""
            due = TXT.parse_datetime(r["due"]) if r["due"] else None
            r["overdue"] = bool(due and now and due <= now and r["status"] == "terbuka")
            r["due_soon"] = bool(due and now and not r["overdue"] and (due - now).total_seconds() <= 3600)
            if include_closed or r["status"] == "terbuka":
                out.append(r)
        return sorted(out, key=lambda r: (not r["overdue"], not r["due_soon"], r["due"] or "9999", -r["id"]))

    @staticmethod
    def line(r):
        bits = [r["who"]] if r["who"] else []
        if r["due"]:
            bits.append("tenggat " + r["due"] + (" (LEWAT TENGGAT)" if r["overdue"] else " (sebentar lagi)" if r["due_soon"] else ""))
        return f"- #{r['id']} [{r['kind']}] {r['title']}{' (' + '; '.join(bits) + ')' if bits else ''}" + (
            f": {r['text'][:200]}" if r["text"] else "")


THREADS = Threads(STORE)


class Relations:
    """How characters feel about each other, as a running score (-100..100) with the reason for every change,
    on the active branch. 'player' is the player's character."""

    def __init__(self, store):
        self.store = store

    def change(self, chat_id, message_id, a, b, delta, reason="", world_time=""):
        delta = max(-20.0, min(20.0, float(delta)))
        return self.store.x("INSERT INTO relations_log (chat_id, message_id, a, b, delta, reason, world_time, created) "
                            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (chat_id, message_id, a, b, delta, (reason or "")[:300],
                                                                str(world_time or ""), time.time()))

    def log(self, chat_id):
        chats = self.store.lineage(chat_id)
        if not chats:
            return []
        vis = self.store.visible_ids(chat_id)
        rows = self.store.q(f"SELECT * FROM relations_log WHERE chat_id IN ({','.join('?' * len(chats))}) ORDER BY id",
                            list(chats))
        return [r for r in rows if not r["message_id"] or r["message_id"] in vis]

    def scores(self, chat_id):
        """{(a, b): {"score", "last"}}: a's feeling toward b, with the latest reason."""
        out = {}
        for r in self.log(chat_id):
            cur = out.setdefault((r["a"], r["b"]), {"score": 0.0, "last": ""})
            cur["score"] = max(-100.0, min(100.0, cur["score"] + r["delta"]))
            cur["last"] = r["reason"]
            cur["mid"] = r["message_id"]
        return out

    @staticmethod
    def word(score):
        for limit, w in ((-60, "benci"), (-25, "tidak suka"), (-5, "dingin"), (5, "netral"), (25, "ramah"), (60, "dekat")):
            if score < limit:
                return w
        return "sangat dekat"


RELATIONS = Relations(STORE)
WORLD = World(STORE, CARDS, STORIES)
