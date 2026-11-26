import struct as _struct
import zlib as _zlib


class Cards:
    """Cards of every type, driven by their schemas: CRUD with versions, prompt rendering, lore,
    timeline, and import/export (own qcard format, SillyTavern V2/V3 JSON or PNG)."""

    TYPE_ORDER = ("style", "gm", "persona", "world", "scenario", "character")
    ST_MAP = {"description": "description", "personality": "personality", "scenario": "default_scenario",
              "mes_example": "example_dialogue", "creator_notes": "notes", "tags": "tags"}

    def __init__(self, store):
        self.store = store
        self.on_change = None  # set by the chat app: called with a card id (None = some lore/timeline entry)
        self.ensure_defaults()

    def _changed(self, card_id):
        if self.on_change:
            try:
                self.on_change(card_id)
            except Exception:
                pass

    # ---------- schemas ----------

    def ensure_defaults(self):
        for t, sch in DEFAULT_SCHEMAS.items():
            row = self.store.one("SELECT version FROM card_schemas WHERE type = ?", (t,))
            if row is None or row["version"] < sch["version"]:
                self.store.x("INSERT OR REPLACE INTO card_schemas (type, version, json) VALUES (?, ?, ?)",
                             (t, sch["version"], json.dumps(sch)))
        for t, name, data in DEFAULT_CARDS:
            if not self.store.one("SELECT id FROM cards WHERE type = ? LIMIT 1", (t,)):
                self.save(None, t, data, name=name)

    def schema(self, type_):
        row = self.store.one("SELECT json FROM card_schemas WHERE type = ?", (type_,))
        return json.loads(row["json"]) if row else DEFAULT_SCHEMAS[type_]

    def save_schema(self, sch):
        if not isinstance(sch, dict) or not sch.get("type") or not isinstance(sch.get("fields"), list):
            raise ValueError("Skema harus punya 'type' dan daftar 'fields'.")
        keys = set()
        for f in sch["fields"]:
            if not f.get("key") or f["key"] in keys:
                raise ValueError(f"Field tanpa key atau key dobel: {f.get('key')!r}")
            keys.add(f["key"])
            f.setdefault("label", f["key"])
            f.setdefault("section", "Lainnya")
            f.setdefault("type", "text")
            f.setdefault("core", False)
            f.setdefault("visibility", "model")
        old = self.store.one("SELECT version FROM card_schemas WHERE type = ?", (sch["type"],))
        sch["version"] = (old["version"] if old else 0) + 1
        self.store.x("INSERT OR REPLACE INTO card_schemas (type, version, json) VALUES (?, ?, ?)",
                     (sch["type"], sch["version"], json.dumps(sch)))
        return sch

    # ---------- field values ----------

    # Other names models use for table columns (compared without case, spaces or punctuation).
    COLUMN_ALIASES = {"awal": ("start", "initial", "nilaiawal", "value", "nilai"),
                      "lajuperjam": ("laju", "rate", "perjam", "rateperhour", "perhour"),
                      "suhumin": ("min", "tmin", "minimum"), "suhumax": ("max", "tmax", "maximum"),
                      "istilah": ("term", "kata", "nama"), "arti": ("meaning", "definisi", "definition", "penjelasan"),
                      "bulan": ("month", "musim", "season", "periode"), "cuaca": ("weather",),
                      "label": ("nama", "name"), "key": ("kunci", "id")}

    @staticmethod
    def _norm_key(s):
        return re.sub(r"[^a-z0-9]", "", str(s).lower())

    @staticmethod
    def _cell(v):
        if v is None:
            return ""
        if isinstance(v, (list, tuple)):
            return ", ".join(str(x).strip() for x in v)
        if isinstance(v, float) and v.is_integer():
            return str(int(v))
        return (json.dumps(v, ensure_ascii=False) if isinstance(v, dict) else str(v)).strip()

    @classmethod
    def _split_row(cls, line):
        line = re.sub(r"^\s*(?:[*\u2022]|-(?=\s)|\d+[.)](?=\s))\s*", "", line).strip()
        if not line or re.fullmatch(r"[|:\-\s]+", line):  # empty, or a markdown separator row
            return None
        # ", " before ",": a decimal comma ("0,5") is not a column break
        for sep in ("|", "\t", ";", ", ", ","):
            if sep in line:
                return [c.strip() for c in line.strip("|").split(sep)] if sep == "|" else [c.strip() for c in line.split(sep)]
        return [line]

    @classmethod
    def _row_from_dict(cls, r, cols):
        nk = {cls._norm_key(k): v for k, v in r.items()}
        cells, hits = [], 0
        for c in cols:
            key = cls._norm_key(c)
            names = (key,) + cls.COLUMN_ALIASES.get(key, ())
            hit = next((n for n in names if n in nk), None)
            if hit is None:
                hit = next((k for k in nk if len(k) >= 3 and key.startswith(k)), None)
            if hit is not None:
                hits += 1
                cells.append(nk.pop(hit))
            else:
                cells.append("")
        return cells if hits else list(r.values())

    @classmethod
    def table_rows(cls, value, columns):
        """A table field as rows of strings in column order. Accepts an array of arrays or of objects, a JSON
        string of either, an object of rows, or text with one row per line (| ; , or tab separated)."""
        cols = list(columns or ["nilai"])
        if isinstance(value, str) and value.strip()[:1] in "[{":
            try:
                value = json.loads(value)
            except ValueError:
                pass
        if isinstance(value, dict):
            rows = value.get("rows") or value.get("data")
            if isinstance(rows, list):
                value = rows
            elif any(cls._norm_key(k) in {cls._norm_key(c) for c in cols} for k in value):
                value = [value]
            else:  # {"term": "meaning", ...}
                value = [[k, v] for k, v in value.items()]
        if isinstance(value, str):
            value = [r for r in (cls._split_row(line) for line in value.splitlines()) if r]
        if not isinstance(value, list):
            return []
        out = []
        for r in value:
            if isinstance(r, dict):
                cells = cls._row_from_dict(r, cols)
            elif isinstance(r, (list, tuple)):
                cells = list(r)
            elif isinstance(r, str):
                cells = cls._split_row(r) or []
            elif r is not None:
                cells = [r]
            else:
                continue
            cells = [cls._cell(c) for c in cells]
            if len(cells) > len(cols):  # extra cells belong to the last column (e.g. "cerah, berawan, hujan")
                cells = cells[:len(cols) - 1] + [", ".join(c for c in cells[len(cols) - 1:] if c)]
            cells += [""] * (len(cols) - len(cells))
            if any(cells):
                out.append(cells)
        names = {cls._norm_key(c) for c in cols}
        if out and all(cls._norm_key(c) in names for c in out[0] if c):  # the header row, repeated by the model
            out = out[1:]
        return out

    def normalize(self, type_, data):
        """Field values in the shape the UI and the engine read: tables as rows of strings, lists as arrays."""
        try:
            fields = {f["key"]: f for f in self.schema(type_)["fields"]}
        except Exception:
            return data
        out = dict(data)
        for k, v in data.items():
            f = fields.get(k)
            if not f or v in (None, "", [], {}):
                continue
            t = f.get("type")
            if t == "table":
                out[k] = self.table_rows(v, f.get("columns"))
            elif t in ("list", "tags"):
                if isinstance(v, str) and v.strip()[:1] == "[":
                    try:
                        v = json.loads(v)
                    except ValueError:
                        pass
                if isinstance(v, str):
                    parts = re.split(r"\n|,", v) if t == "tags" else v.splitlines()
                    v = [re.sub(r"^\s*(?:[*\u2022]|-(?=\s)|\d+[.)](?=\s))\s*", "", p).strip() for p in parts]
                if isinstance(v, list):
                    out[k] = [self._cell(x) for x in v if self._cell(x)]
            elif t in ("text", "longtext", "select") and isinstance(v, (list, dict)):
                out[k] = "\n".join(map(self._cell, v)) if isinstance(v, list) else self._cell(v)
            if t == "datetime" and isinstance(out[k], str):
                dt = TXT.parse_datetime(out[k])
                if dt:
                    out[k] = dt.strftime("%Y-%m-%d %H:%M")
            elif t == "select" and isinstance(out[k], str):
                match = next((o for o in f.get("options") or [] if o.lower() == out[k].strip().lower()), None)
                if match:
                    out[k] = match
            elif t == "number" and isinstance(out[k], str):
                m = re.fullmatch(r"\s*(-?\d+(?:[.,]\d+)?)\s*", out[k])
                if m:
                    n = float(m.group(1).replace(",", "."))
                    out[k] = int(n) if n.is_integer() else n
        return out

    # ---------- cards ----------

    def list(self, type_=None):
        sql = "SELECT id, type, name, version, updated, avatar IS NOT NULL AS has_avatar FROM cards"
        rows = self.store.q(sql + (" WHERE type = ?" if type_ else "") + " ORDER BY type, name",
                            (type_,) if type_ else ())
        return rows

    def get(self, card_id, version=None):
        c = self.store.one("SELECT id, type, name, data, version, avatar FROM cards WHERE id = ?", (card_id,))
        if not c:
            return None
        if version and version != c["version"]:
            v = self.store.one("SELECT data FROM card_versions WHERE card_id = ? AND version = ?", (card_id, version))
            if v:
                c["data"], c["version"] = v["data"], version
        c["data"] = self.normalize(c["type"], json.loads(c["data"] or "{}"))
        c["avatar"] = base64.b64encode(c["avatar"]).decode() if c["avatar"] else None
        return c

    def save(self, card_id, type_, data, name=None, avatar=None):
        """Create or update a card. Every change of data makes a new version. Returns the card id."""
        data = self.normalize(type_, dict(data or {}))
        name = (name or data.get("name") or data.get("title") or "Tanpa nama").strip()
        now = time.time()
        if card_id:
            cur = self.store.one("SELECT data, version FROM cards WHERE id = ?", (card_id,))
            if cur is None:
                card_id = None
        if not card_id:
            card_id = self.store.x("INSERT INTO cards (type, name, data, avatar, version, created, updated) VALUES (?, ?, ?, ?, 1, ?, ?)",
                                   (type_, name, json.dumps(data), avatar, now, now))
            self.store.x("INSERT INTO card_versions (card_id, version, data, created) VALUES (?, 1, ?, ?)",
                         (card_id, json.dumps(data), now))
            self._changed(card_id)
            return card_id
        if json.loads(cur["data"] or "{}") != data:
            ver = cur["version"] + 1
            self.store.x("INSERT INTO card_versions (card_id, version, data, created) VALUES (?, ?, ?, ?)",
                         (card_id, ver, json.dumps(data), now))
            self.store.x("UPDATE cards SET data = ?, name = ?, version = ?, updated = ? WHERE id = ?",
                         (json.dumps(data), name, ver, now, card_id))
        else:
            self.store.x("UPDATE cards SET name = ?, updated = ? WHERE id = ?", (name, now, card_id))
        if avatar is not None:
            self.store.x("UPDATE cards SET avatar = ? WHERE id = ?", (avatar or None, card_id))
        self._changed(card_id)
        return card_id

    def set_field(self, card_id, key, value):
        c = self.get(card_id)
        data = {**c["data"], key: value}
        return self.save(card_id, c["type"], data, name=c["name"] if key not in ("name", "title") else None)

    def delete(self, card_id):
        # SQLite reuses the highest id after a delete, so everything that points at this card goes with it.
        for kind, sql in (("lore", "SELECT id FROM lore_entries WHERE card_id = ?"),
                          ("fact", "SELECT id FROM facts WHERE world_card_id = ?"),
                          ("mem", "SELECT id FROM memories WHERE scope = 'card' AND card_id = ?")):
            for r in self.store.q(sql, (card_id,)):
                self.store.x("DELETE FROM vectors WHERE kind = ? AND ref_id = ?", (kind, r["id"]))
        self.store.x("DELETE FROM facts WHERE world_card_id = ?", (card_id,))
        self.store.x("DELETE FROM memories WHERE scope = 'card' AND card_id = ?", (card_id,))
        for t in ("cards", "card_versions"):
            self.store.x(f"DELETE FROM {t} WHERE {'id' if t == 'cards' else 'card_id'} = ?", (card_id,))
        self.store.x("DELETE FROM lore_entries WHERE card_id = ?", (card_id,))
        self.store.x("DELETE FROM timeline WHERE card_id = ?", (card_id,))
        self.store.x("DELETE FROM story_cards WHERE card_id = ?", (card_id,))
        self._changed(card_id)

    def versions(self, card_id):
        return self.store.q("SELECT version, created FROM card_versions WHERE card_id = ? ORDER BY version DESC", (card_id,))

    def find(self, type_, name):
        low = (name or "").strip().lower()
        for c in self.list(type_):
            if c["name"].lower() == low:
                return c["id"]
        return None

    # ---------- rendering ----------

    @staticmethod
    def _value_text(f, v):
        if v in (None, "", [], {}):
            return ""
        if f["type"] in ("list", "tags"):
            items = v if isinstance(v, list) else [x.strip() for x in str(v).split("\n") if x.strip()]
            if f["type"] == "tags":
                return ", ".join(map(str, items))
            return "\n" + "\n".join(f"  - {x}" for x in items)
        if f["type"] == "table":
            rows = v if isinstance(v, list) else []
            cols = f.get("columns") or []
            lines = []
            for r in rows:
                cells = r if isinstance(r, list) else [r.get(c, "") for c in cols] if isinstance(r, dict) else [r]
                lines.append("  - " + " | ".join(str(x) for x in cells if str(x).strip()))
            return "\n" + "\n".join(lines) if lines else ""
        text = str(v).strip()
        return ("\n  " + text.replace("\n", "\n  ")) if f["type"] == "longtext" and "\n" in text else text

    def render(self, card, mode="core", keys=None, limit=6000):
        """Text for the prompt. mode: core (frozen part), detail (the rest), all. 'ui' fields never render."""
        return TXT.macros(self._render(card, mode, keys, limit), char=card.get("name", ""))

    def _render(self, card, mode="core", keys=None, limit=6000):
        sch = self.schema(card["type"])
        out, section = [f"## {sch.get('label', card['type'])}: {card['name']}"], None
        for f in sch["fields"]:
            if f.get("visibility") == "ui" or (keys and f["key"] not in keys):
                continue
            if mode == "core" and not f.get("core") or mode == "detail" and f.get("core"):
                continue
            text = self._value_text(f, card["data"].get(f["key"]))
            if not text:
                continue
            if f.get("section") != section:
                section = f.get("section")
                out.append(f"### {section}")
            secret = " (rahasia: hanya kamu yang tahu, jangan diungkap tanpa sebab)" if f.get("visibility") == "secret" else ""
            out.append(f"- {f['label']}{secret}: {text}")
        known = {f["key"] for f in sch["fields"]}
        if mode != "core":
            for k, v in card["data"].items():
                if k not in known and v not in (None, "", [], {}) and not k.startswith("_"):
                    out.append(f"- {k}: {str(v)[:1500]}")
        text = "\n".join(out) if len(out) > 1 else ""
        return text[:limit]

    def visible_fields(self, card):
        """Fields of a card for the UI form, schema order, with unknown keys appended."""
        sch = self.schema(card["type"])
        known = {f["key"] for f in sch["fields"]}
        extra = [{"key": k, "label": k, "section": "Tambahan", "type": "longtext", "core": False, "visibility": "model"}
                 for k in card["data"] if k not in known]
        return sch["fields"] + extra

    # ---------- lore and timeline ----------

    def lore(self, card_id):
        return self.store.q("SELECT * FROM lore_entries WHERE card_id = ? ORDER BY kind, title", (card_id,))

    def lore_save(self, card_id, title, text, keys="", kind="istilah", core=False, entry_id=None):
        if entry_id:
            self.store.x("UPDATE lore_entries SET title = ?, text = ?, keys = ?, kind = ?, core = ?, updated = ? WHERE id = ?",
                         (title, text, keys, kind, int(core), time.time(), entry_id))
        else:
            entry_id = self.store.x("INSERT INTO lore_entries (card_id, kind, title, keys, text, core, updated) "
                                    "VALUES (?, ?, ?, ?, ?, ?, ?)", (card_id, kind, title, keys, text, int(core), time.time()))
        self._changed(card_id)
        return entry_id

    def lore_delete(self, entry_id):
        self.store.x("DELETE FROM lore_entries WHERE id = ?", (entry_id,))
        self._changed(None)

    def timeline(self, card_id):
        return self.store.q("SELECT * FROM timeline WHERE card_id = ? ORDER BY at", (card_id,))

    def timeline_save(self, card_id, at, title, text="", entry_id=None):
        if entry_id:
            self.store.x("UPDATE timeline SET at = ?, title = ?, text = ? WHERE id = ?", (at, title, text, entry_id))
        else:
            entry_id = self.store.x("INSERT INTO timeline (card_id, at, title, text) VALUES (?, ?, ?, ?)", (card_id, at, title, text))
        self._changed(card_id)
        return entry_id

    def timeline_delete(self, entry_id):
        self.store.x("DELETE FROM timeline WHERE id = ?", (entry_id,))
        self._changed(None)

    # ---------- export / import ----------

    def export_qcard(self, card_id):
        c = self.get(card_id)
        out = {"format": "qcard", "version": 1, "type": c["type"], "name": c["name"], "schema": self.schema(c["type"]),
               "data": c["data"], "avatar": c["avatar"],
               "lore": [{k: e[k] for k in ("kind", "title", "keys", "text", "core")} for e in self.lore(card_id)],
               "timeline": [{k: e[k] for k in ("at", "title", "text")} for e in self.timeline(card_id)]}
        if c["type"] == "world":
            out["facts"] = self.store.q("SELECT claim, source_url, source_title, checked, confidence, status, tags "
                                        "FROM facts WHERE world_card_id = ?", (card_id,))
        out["memories"] = self.store.q("SELECT text, kind FROM memories WHERE scope = 'card' AND card_id = ?", (card_id,))
        return out

    def import_any(self, data, filename=""):
        """qcard JSON, SillyTavern V2/V3 JSON, or a PNG with an embedded card. Returns the new card id."""
        if isinstance(data, (bytes, bytearray)) and data[:8] == b"\x89PNG\r\n\x1a\n":
            obj, avatar = self._png_card(bytes(data)), bytes(data)
        else:
            text = data if isinstance(data, str) else bytes(data).decode("utf-8-sig")
            obj, avatar = json.loads(text.lstrip("﻿")), None
        if not isinstance(obj, dict):
            raise ValueError("File kartu harus berisi satu objek JSON.")
        if obj.get("format") == "qcard":
            return self._import_qcard(obj)
        return self._import_st(obj, avatar)

    def _import_qcard(self, obj):
        avatar = base64.b64decode(obj["avatar"]) if obj.get("avatar") else None
        type_ = str(obj.get("type") or "")
        if not type_:
            raise ValueError("qcard tanpa jenis kartu.")
        known = self.store.one("SELECT 1 AS x FROM card_schemas WHERE type = ?", (type_,)) or type_ in DEFAULT_SCHEMAS
        if not known:  # a custom type brings its own schema
            sch = obj.get("schema")
            if not isinstance(sch, dict):
                raise ValueError(f"Jenis kartu '{type_}' tidak dikenal dan qcard ini tidak membawa skemanya.")
            self.save_schema({**sch, "type": type_})
        data = {k: v for k, v in (obj.get("data") or {}).items() if re.match(r"^[A-Za-z_][\w-]{0,63}$", str(k))}
        name = obj.get("name")
        cid = self.save(None, type_, data, name=str(name) if name is not None else None, avatar=avatar)
        for e in obj.get("lore") or []:
            self.lore_save(cid, e.get("title", ""), e.get("text", ""), e.get("keys", ""), e.get("kind", "istilah"),
                           bool(e.get("core")))
        for e in obj.get("timeline") or []:
            self.timeline_save(cid, e.get("at", ""), e.get("title", ""), e.get("text", ""))
        for f in obj.get("facts") or []:
            self.store.x("INSERT INTO facts (world_card_id, claim, source_url, source_title, checked, confidence, status, tags) "
                         "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                         (cid, f.get("claim", ""), f.get("source_url", ""), f.get("source_title", ""),
                          f.get("checked") or time.time(), f.get("confidence", 0.7), f.get("status", "terverifikasi"),
                          f.get("tags", "")))
        for m in obj.get("memories") or []:
            now = time.time()
            self.store.x("INSERT INTO memories (scope, card_id, kind, text, created, updated) VALUES ('card', ?, ?, ?, ?, ?)",
                         (cid, m.get("kind", "fact"), m.get("text", ""), now, now))
        return cid

    def _import_st(self, obj, avatar):
        d = obj.get("data") if isinstance(obj.get("data"), dict) else obj
        if not d.get("name"):
            raise ValueError("Bukan kartu karakter yang dikenali (tidak ada nama).")
        name = str(d["name"]).strip()
        data = {"name": name}
        # {{char}} becomes the name now; {{user}} stays and is replaced with the persona's name in the prompt
        fix = lambda v: TXT.macros(v, char=name) if isinstance(v, str) else (
            [TXT.macros(x, char=name) if isinstance(x, str) else x for x in v] if isinstance(v, list) else v)
        for src, dst in self.ST_MAP.items():
            if d.get(src):
                data[dst] = fix(d[src])
        greet = [fix(g) for g in [d.get("first_mes")] + list(d.get("alternate_greetings") or []) if isinstance(g, str) and g]
        if greet:
            data["greetings"] = greet
        for k in ("system_prompt", "post_history_instructions"):
            if d.get(k):
                data[f"st_{k}"] = fix(d[k])
        cid = self.save(None, "character", data, avatar=avatar)
        book = d.get("character_book") if isinstance(d.get("character_book"), dict) else {}
        for e in book.get("entries") or []:
            if not isinstance(e, dict):
                continue
            raw_keys = e.get("keys") or []
            keys = ", ".join(k.strip() for k in (raw_keys.split(",") if isinstance(raw_keys, str) else map(str, raw_keys)) if k.strip())
            self.lore_save(cid, str(e.get("name") or e.get("comment") or (keys[:40] or "Lore")), fix(str(e.get("content", ""))),
                           keys, "lore", bool(e.get("constant")))
        return cid

    @staticmethod
    def _inflate(raw, limit=50 * 1024 * 1024):
        """zlib with a size limit: a few MB of crafted data must not expand into gigabytes."""
        d = _zlib.decompressobj()
        out = d.decompress(raw, limit)
        if d.unconsumed_tail:
            raise ValueError("Data kartu di PNG terlalu besar.")
        return out

    @staticmethod
    def _png_card(data):
        pos, found = 8, {}
        while pos + 8 <= len(data):
            length, ctype = _struct.unpack(">I4s", data[pos:pos + 8])
            chunk = data[pos + 8:pos + 8 + length]
            if ctype in (b"tEXt", b"iTXt", b"zTXt"):
                key, _, rest = chunk.partition(b"\x00")
                key = key.decode("latin-1").lower()
                if key in ("chara", "ccv3"):  # other text chunks are never decompressed
                    if ctype == b"zTXt":
                        rest = Cards._inflate(rest[1:])
                    elif ctype == b"iTXt":
                        compressed = rest[:1] == b"\x01"
                        rest = rest[2:].split(b"\x00", 2)[-1]
                        if compressed:
                            rest = Cards._inflate(rest)
                    found[key] = rest
            pos += 12 + length
        raw = found.get("ccv3") or found.get("chara")
        if raw is None:
            raise ValueError("PNG ini tidak berisi kartu karakter.")
        return json.loads(base64.b64decode(raw).decode("utf-8"))

    def export_st_v2(self, card_id):
        c = self.get(card_id)
        d = c["data"]
        rev = {v: k for k, v in self.ST_MAP.items()}
        out = {rev[k]: v for k, v in d.items() if k in rev}
        greet = d.get("greetings") or []
        out.update(name=c["name"], first_mes=greet[0] if greet else "", alternate_greetings=greet[1:])
        out["description"] = "\n\n".join(x for x in [d.get("description", ""), d.get("appearance", ""),
                                                     d.get("backstory", "")] if x)
        entries = [{"keys": [k.strip() for k in e["keys"].split(",") if k.strip()], "content": e["text"],
                    "name": e["title"], "constant": bool(e["core"]), "enabled": True} for e in self.lore(card_id)]
        if entries:
            out["character_book"] = {"entries": entries}
        return {"spec": "chara_card_v2", "spec_version": "2.0", "data": out}


CARDS = Cards(STORE)
