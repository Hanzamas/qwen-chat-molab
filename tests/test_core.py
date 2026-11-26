import base64
import json
import sqlite3
import struct
import time
import zlib

from conftest import wait_idle


# ---------- text ----------

def test_sentences_and_shape(nb):
    T = nb["TXT"]
    s = T.sentences('Dia datang z.B. jam 7.30 pagi. "Es ist kalt!" (Dingin!) katanya. Lalu pergi?')
    assert len(s) == 3, s
    paras, per = T.shape("Satu. Dua.\n\nTiga. Empat. Lima.")
    assert paras == 2 and per == [2, 3]
    assert T.parse_input("((ubah sersan))") == {"kind": "ooc", "text": "ubah sersan"}
    assert T.parse_input("/note tegang")["cmd"] == "note"
    assert T.fts_query("yang dan di") == ""
    assert T.dedupe_parens('"Ja." (Iya.) (Iya)') == '"Ja." (Iya.)'
    assert T.split_dialogue('"Das..." (Itu) "...ist..." (adalah) "...gut" (bagus)') == 3
    assert T.acts_for_user("Kamu berkata pelan bahwa kamu lelah.")


# ---------- store ----------

def test_legacy_migration(nb, tmp_path):
    p = tmp_path / "old.sqlite"
    c = sqlite3.connect(p)
    c.executescript("""
    CREATE TABLE chats (id INTEGER PRIMARY KEY, title TEXT, system TEXT DEFAULT '', strip_upto INTEGER DEFAULT 0, created REAL, updated REAL);
    CREATE TABLE messages (id INTEGER PRIMARY KEY, chat_id INTEGER, seq INTEGER, role TEXT, content TEXT DEFAULT '',
        reasoning TEXT DEFAULT '', tool_calls TEXT, tool_call_id TEXT, meta TEXT DEFAULT '{}', created REAL);
    CREATE TABLE summaries (id INTEGER PRIMARY KEY, chat_id INTEGER, upto_seq INTEGER, text TEXT, created REAL);
    CREATE TABLE memories (id INTEGER PRIMARY KEY, text TEXT, created REAL);
    CREATE VIRTUAL TABLE messages_fts USING fts5(content, reasoning, content='messages', content_rowid='id');
    INSERT INTO chats VALUES (1, 'lama', '', 2, 1, 1);
    INSERT INTO messages VALUES (10, 1, 1, 'user', 'halo', '', NULL, NULL, '{}', 1);
    INSERT INTO messages VALUES (11, 1, 2, 'assistant', 'hai', 'pikir', NULL, NULL, '{}', 2);
    INSERT INTO messages VALUES (12, 1, 3, 'user', 'lagi', '', NULL, NULL, '{}', 3);
    INSERT INTO summaries VALUES (1, 1, 2, 'ringkasan', 4);
    INSERT INTO memories VALUES (1, 'suka teh', 5);
    """)
    c.commit()
    c.close()
    s = nb["Store"](p)
    assert s.path_ids(1) == [10, 11, 12]
    assert s.chat(1)["strip_node"] == 11
    assert s.one("SELECT node_id FROM summaries")["node_id"] == 11
    assert s.one("SELECT scope, kind FROM memories") == {"scope": "user", "kind": "fact"}
    assert s.q("SELECT rowid FROM messages_fts WHERE messages_fts MATCH 'halo'")


# ---------- cards ----------

def _png_with_card(card):
    sig = b"\x89PNG\r\n\x1a\n"

    def chunk(t, data):
        return struct.pack(">I", len(data)) + t + data + struct.pack(">I", zlib.crc32(t + data))
    raw = base64.b64encode(json.dumps(card).encode())
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    return sig + chunk(b"IHDR", ihdr) + chunk(b"tEXt", b"chara\x00" + raw) + chunk(b"IEND", b"")


def test_cards(nb):
    C = nb["CARDS"]
    cid = C.save(None, "character", {"name": "Lotte", "speech_samples": ["Na, du?"], "secrets": ["takut gelap"],
                                     "greetings": ["Hallo!"], "custom_field": "tetap ada"})
    C.set_field(cid, "age", "23")
    assert C.get(cid)["version"] == 2
    core = C.render(C.get(cid))
    assert "Na, du?" in core and "rahasia" in core and "Hallo!" not in core
    assert "custom_field" in C.render(C.get(cid), mode="all")
    st = {"spec": "chara_card_v2", "data": {"name": "Brunner", "description": "Pemilik WG", "first_mes": "Guten Tag.",
                                            "character_book": {"entries": [{"keys": ["Kiez"], "content": "lingkungan"}]}}}
    sid = C.import_any(_png_with_card(st))
    card = C.get(sid)
    assert card["name"] == "Brunner" and card["data"]["greetings"] == ["Guten Tag."] and card["avatar"]
    assert C.lore(sid)[0]["keys"] == "Kiez"
    q = C.export_qcard(sid)
    again = C.import_any(json.dumps(q))
    assert C.get(again)["data"]["description"] == "Pemilik WG" and C.lore(again)
    assert C.export_st_v2(sid)["data"]["first_mes"] == "Guten Tag."


# ---------- plain chat ----------

def test_plain_chat(engine, nb):
    eng = engine
    cid = eng.new_chat("chat", "uji")
    eng.send(cid, "halo")
    wait_idle(eng)
    d = eng.display(cid)
    assert [i["kind"] for i in d["items"]] == ["user", "bot"]
    bot = d["items"][1]
    assert "Paragraf 1" in bot["content"] and bot["stats"]["tokens"]
    assert bot["reasoning"]


# ---------- RP story ----------

def _story(nb, engine, fmt="prosa"):
    C = nb["CARDS"]
    world = C.save(None, "world", {"name": "Berlin 2026", "realworld": "tidak",
                                   "stats": [["lapar", "Lapar", 0, 100, 20, 4], ["energi", "Energi", 0, 100, 80, -2]],
                                   "climate": [["12", "-2", "5", "cerah, berawan, salju"]]})
    C.timeline_save(world, "2026-12-19 22:00", "Pesta WG", "Tetangga mengadakan pesta.")
    C.lore_save(world, "Kiez", "Lingkungan sekitar WG.", "kiez", "tempat")
    sc = C.save(None, "scenario", {"title": "Malam di WG", "start_time": "2026-12-19 21:00", "start_location": "Ruang tengah",
                                   "opening": "Lotte mengetuk pintumu."})
    persona = C.save(None, "persona", {"name": "Raka"})
    lotte = C.save(None, "character", {"name": "Lotte Braun", "aliases": ["Lotte"], "speech_samples": ["Na?"]})
    gm = C.save(None, "gm", {"format": fmt, "choices": "selalu", "time_skips": ["2 jam"], "afk_scale": "1", "tick_minutes": "20"})
    chat = engine.start_story({"world": world, "scenario": sc, "persona": persona, "character": [lotte], "gm": gm})
    return chat, world


def test_rp_tools_status_and_tree(engine, nb, fake):
    eng = engine
    chat, world = _story(nb, eng)
    d = eng.display(chat)
    assert d["items"][0]["content"] == "Lotte mengetuk pintumu."
    eng.send(chat, "Aku memasak. TOOLTEST")
    wait_idle(eng)
    p = eng.panels(chat)
    assert p["time"].endswith("21:30"), p["time"]
    lapar = next(s for s in p["stats"] if s["key"] == "lapar")
    assert lapar["value"] == 32.0, lapar  # 20 + 0.5h*4 + 10
    assert p["location"] == "Dapur"
    bot = eng.display(chat)["items"][-1]
    assert bot["dice"] and bot["dice"][0]["event"] == "terpeleset"
    assert [t["name"] for t in bot["tools"]] == ["world_advance", "status_update", "roll"]
    # reroll makes a sibling; the old branch's events no longer count
    fake["script"].append({"content": "Narasi lain tanpa tool. Lotte diam saja."})
    eng.reroll(chat, bot["id"])
    wait_idle(eng)
    p2 = eng.panels(chat)
    assert p2["time"].endswith("21:00"), p2["time"]
    last = eng.display(chat)["items"][-1]
    assert last["swipe"] == [2, 2]
    eng.swipe(chat, last["id"], -1)
    assert eng.panels(chat)["time"].endswith("21:30")


def test_prefix_stability(engine, nb, fake):
    eng = engine
    chat, _ = _story(nb, eng)
    eng.send(chat, "halo Lotte")
    wait_idle(eng)
    side = nb["PROMPT"].side(chat, "tugas apa saja")
    eng.send(chat, "lalu?")
    wait_idle(eng)
    main = [b for b in fake["log"] if b["messages"][-1]["role"] == "user" and "lalu?" in json.dumps(b["messages"][-1])][-1]
    n = len(side) - 1
    assert main["messages"][0] == side[0]
    assert main["messages"][1:n - 1] == side[1:n - 1]
    assert "Catatan sistem" in json.dumps(main["messages"][-1])
    assert "Catatan sistem" not in json.dumps(main["messages"][1:-1])


def test_game_format_choices_and_time_skip(engine, nb):
    eng = engine
    chat, _ = _story(nb, eng, fmt="game")
    eng.send(chat, "Aku duduk.")
    wait_idle(eng)
    bot = eng.display(chat)["items"][-1]
    assert bot["choices"] and len(bot["choices"]["problems"][0]["options"]) == 3
    eng.time_skip(chat, "2 jam")
    wait_idle(eng)
    p = eng.panels(chat)
    assert p["time"].endswith("23:00"), p["time"]
    assert any("Frau Brunner" in e["text"] for e in p["events"])
    assert p["weather"]


def test_length_continue_and_flags(engine, nb, fake):
    eng = engine
    chat, _ = _story(nb, eng)
    fake["script"].append({"content": "Satu paragraf saja. Kamu berkata pelan bahwa kamu lelah."})
    eng.send(chat, "pendek?")
    wait_idle(eng)
    bot = eng.display(chat)["items"][-1]
    assert "Paragraf tambahan dua" in bot["content"]
    assert any(f["kind"] == "acts_for_user" for f in bot["flags"])


def test_compaction_and_epoch(engine, nb, fake):
    eng = engine
    chat, _ = _story(nb, eng)
    for i in range(5):
        eng.send(chat, f"giliran {i}")
        wait_idle(eng)
    fake["max_len"] = 3000
    nb["LLM_CLIENT"]._ctx_cache = {}  # a real server restart changes the cache key; here the fake changes in place
    try:
        eng.compactor.CHUNK_TOKENS = 500
        eng.send(chat, "pesan terakhir")
        wait_idle(eng, 60)
    finally:
        fake["max_len"] = 200_000
        nb["LLM_CLIENT"]._ctx_cache = {}
    errors = [e for e in eng.events.of("toast") if e.get("kind") == "error"]
    assert not errors, errors
    s = nb["STORE"]
    sums = s.q("SELECT * FROM summaries WHERE chat_id = ?", (chat,))
    assert sums and "## Inti" in sums[0]["text"]
    assert s.chat(chat)["epoch"] >= 1
    assert "Kronik" in nb["PROMPT"].system_text(chat)
    assert s.q("SELECT * FROM memories WHERE kind = 'summary_core'")
    assert s.q("SELECT * FROM memories WHERE text = 'Lotte suka teh.'")
    assert any(i["kind"] == "summary" for i in eng.display(chat)["items"])


def test_memory_dedup_update_undo(nb):
    M = nb["MEM"]
    ctx = {"chat_id": None, "story_id": None, "card_ids": []}
    a = M.save("Pengguna suka kopi hitam tanpa gula setiap pagi", "user", ctx)
    assert "saved" in a
    b = M.save("Pengguna suka kopi hitam tanpa gula setiap pagi.", "user", ctx)
    assert b.get("duplicate_of") == a["saved"]
    M.update(a["saved"], "Pengguna sekarang suka teh", ctx)
    log = M.log(limit=1)[0]
    assert M.undo(log["id"])
    assert "kopi" in nb["STORE"].one("SELECT text FROM memories WHERE id = ?", (a["saved"],))["text"]


def test_export_and_misc(engine, nb):
    eng = engine
    chat, _ = _story(nb, eng)
    eng.send(chat, "halo")
    wait_idle(eng)
    nb["STORE"].x("INSERT INTO chapters (chat_id, message_id, title, created) VALUES (?, ?, 'Bab 1', ?)",
                  (chat, nb["STORE"].chat(chat)["head_id"], time.time()))
    for fmt in ("md", "html", "epub"):
        name, data = eng.export_story(chat, fmt)
        assert name.endswith(fmt) and len(data) > 100
    new = eng.continue_in_new_chat(chat)
    assert nb["WORLD"].state(new, nb["STORE"].path_ids(new))["time_text"] == \
        nb["WORLD"].state(chat, nb["STORE"].path_ids(chat))["time_text"]
    eng.slash(chat, "impersonate", "")
    wait_idle(eng)
    assert eng.events.of("compose")[-1].startswith("Aku")
    eng.learn(chat, "Es ist kalt heute.")
    wait_idle(eng)
    assert eng.events.of("learn")[-1]["translation"] == "Hari ini dingin."
    pv = eng.prompt_view(chat)
    assert pv["tokens"] > 0 and "Kartu" in pv["system"]
    eng.delete_msg(chat, nb["STORE"].chat(chat)["head_id"])
    assert eng.display(chat)["items"][-1]["kind"] == "user"
