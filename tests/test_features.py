"""Features after the second review: repeated openings, new defaults, per-branch knowledge delete, UI markers."""
import json

from conftest import wait_idle
from test_core import _story


def test_opening_helpers(nb):
    T = nb["TXT"]
    assert T.opening("**Lotte**: Na, du bist spät heute") == ["na", "du", "bist", "spät", "heute"]
    same = T.opening("Lotte menatapmu lama dari ambang pintu.")
    assert T.repeats_opening(same, [T.opening("Lotte menatapmu lama sekali.")])
    step = T.opening("Kamu melangkah masuk ke dapur.")
    assert not T.repeats_opening(step, [T.opening("Kamu melangkah keluar dari kamar.")])
    assert T.repeats_opening(step, [T.opening("Kamu melangkah keluar dari kamar."), T.opening("Kamu melangkah pelan ke jendela.")])
    four = [T.opening(f"Hujan {w} di luar jendela.") for w in ("turun", "reda", "deras", "tipis")]
    assert T.repeats_opening(T.opening("Hujan lagi, katamu dalam hati."), four)
    assert not T.repeats_opening(T.opening("Lotte tertawa."), [T.opening("Pintu terbuka pelan.")])


def test_repeated_opening_is_flagged_and_noted(engine, nb, fake):
    chat, _ = _story(nb, engine)
    reply = "Lotte menatapmu lama dari ambang pintu. Hujan turun di luar.\n\nIa diam saja."
    for _ in range(2):
        fake["script"].append({"content": reply})
        engine.send(chat, "Aku menunggu.")
        wait_idle(engine)
    bot = engine.display(chat)["items"][-1]
    assert any(f["kind"] == "opening" for f in bot["flags"])
    openers = nb["STORE"].chat(chat)["settings"]["openers"]
    assert openers == [{"text": "lotte menatapmu lama dari", "left": 3}]
    n = len(fake["log"])
    fake["script"].append({"content": "Di dapur, ketel mulai bersiul. Kamu mendengarnya dari jauh.\n\nLotte menoleh."})
    engine.send(chat, "Aku ke dapur.")
    wait_idle(engine)
    assert any("Variasikan pembuka balasan" in json.dumps(b, ensure_ascii=False) for b in fake["log"][n:])
    assert nb["STORE"].chat(chat)["settings"]["openers"][0]["left"] == 2  # the note fades after three turns


def test_new_defaults_and_one_time_move(nb):
    C, S = nb["CARDS"], nb["STORE"]
    style = dict(next(d for t, _, d in nb["DEFAULT_CARDS"] if t == "style"))
    gm = dict(next(d for t, _, d in nb["DEFAULT_CARDS"] if t == "gm"))
    assert (style["paragraphs"], style["sentences"], gm["afk_scale"]) == ("4-7", "4-7", "0")
    sid = S.one("SELECT id FROM cards WHERE type = 'style' AND name = 'Gaya RP default'")["id"]
    C.save(sid, "style", {**C.get(sid)["data"], "paragraphs": "5-10", "sentences": "3-4"})
    S.x("DELETE FROM meta WHERE key = 'defaults_v2'")
    C.ensure_defaults()
    d = C.get(sid)["data"]
    assert (d["paragraphs"], d["sentences"]) == ("4-7", "3-4")  # an edited value stays
    C.save(sid, "style", {**d, "paragraphs": "5-10"})
    C.ensure_defaults()
    assert C.get(sid)["data"]["paragraphs"] == "5-10"  # only once: choosing the old value again is respected


def test_knowledge_delete_is_per_branch_and_restorable(engine, nb):
    chat, _ = _story(nb, engine)
    S, K = nb["STORE"], nb["KNOW"]
    engine.send(chat, "Halo.")
    wait_idle(engine)
    head = S.chat(chat)["head_id"]
    kid = K.add(chat, None, ["Lotte Braun"], "Lotte tahu Raka alergi kacang")[0]
    user = nb["ChatApp"]._know_anchor(chat)
    assert S.msg(user)["role"] == "user"
    K.hide(kid, user)
    assert not any(r["id"] == kid for r in K.of(chat, "Lotte Braun"))
    assert [r["id"] for r in K.hidden(chat, "Lotte Braun")] == [kid]
    S.set_head(chat, S.msg(user)["parent_id"])  # the branch before that message still has it
    assert any(r["id"] == kid for r in K.of(chat, "Lotte Braun"))
    S.set_head(chat, head)
    K.restore(kid, chat)
    assert any(r["id"] == kid for r in K.of(chat, "Lotte Braun")) and not K.hidden(chat, "Lotte Braun")
    K.hide(kid, user)
    engine.delete_msg(chat, user)  # the delete hangs on that message: it goes with it
    assert S.one("SELECT hidden_at FROM knowledge WHERE id = ?", (kid,))["hidden_at"] == ""


def test_ui_markers(nb):
    esm = nb["UI_ESM"]
    for marker in ("live-th-rp", "qr-toolset", "STYLE_SUGGEST", "know-restore", "flushRedraws"):
        assert marker in esm, marker


# ---------- RP naturalness (third review) ----------

def _story_rich(nb, engine):
    C = nb["CARDS"]
    world = C.save(None, "world", {"name": "Berlin kecil", "realworld": "tidak"})
    sc = C.save(None, "scenario", {"title": "Malam", "start_time": "2026-12-19 21:00", "start_location": "Ruang tengah",
                                   "opening": "Lotte mengetuk pintumu."})
    persona = C.save(None, "persona", {"name": "Raka"})
    lotte = C.save(None, "character", {"name": "Lotte Braun", "aliases": ["Lotte"], "backstory": "Tumbuh di Hamburg.",
                                       "fears": ["gelap"]})
    gm = C.save(None, "gm", {"format": "prosa"})
    return engine.start_story({"world": world, "scenario": sc, "persona": persona, "character": [lotte], "gm": gm})


def test_note_is_background_with_the_player_last(engine, nb):
    chat = _story_rich(nb, engine)
    S, R, TH = nb["STORE"], nb["RELATIONS"], nb["THREADS"]
    engine.send(chat, "Aku menatap Lotte.")
    wait_idle(engine)
    first = [m for m in S.path(chat) if m["role"] == "user"][-1]
    assert "Tumbuh di Hamburg" in first["meta"]["ephemeral"]  # entering the scene: the whole card detail
    head = S.chat(chat)["head_id"]
    R.change(chat, head, "Lotte Braun", "player", 20, "dibantu")
    TH.open(chat, None, "janji", "Mengembalikan payung tetangga")
    TH.open(chat, None, "misteri", "Siapa yang mencuri sepeda Lotte")
    S.add_message(chat, head, "user", "Aku bertanya ke Lotte soal sepeda.")
    msgs, _ = nb["PROMPT"].build(chat)
    last = msgs[-1]["content"]
    assert last.startswith("[Catatan sistem") and last.endswith("[Pesan pemain]\nAku bertanya ke Lotte soal sepeda.")
    assert "acuan konsistensi" in last
    assert "sepeda Lotte" in last and "payung" not in last and "+1 benang terbuka lain" in last
    assert "+20" not in last and "baru: dibantu" in last
    assert "Tumbuh di Hamburg" not in last and "gelap" in last and "card_read kalau perlu" in last  # still in the scene


def test_old_mood_carries_its_age(nb):
    from datetime import datetime, timedelta
    now = datetime(2026, 1, 1, 12, 0)
    out = json.loads(nb["PROMPT"].status_json({"mood": "cemas", "outfit": "mantel", "plan_now": ""},
                                              {"mood": now - timedelta(hours=5), "outfit": now - timedelta(hours=9)}, now))
    assert out["mood"].startswith("cemas (dicatat 5 jam lalu") and out["outfit"] == "mantel" and "plan_now" not in out
    fresh = json.loads(nb["PROMPT"].status_json({"mood": "senang"}, {"mood": now - timedelta(minutes=30)}, now))
    assert fresh["mood"] == "senang"


def test_length_note_and_no_fill_after_a_hand_off(engine, nb, fake):
    chat, _ = _story(nb, engine)
    fake["script"].append({"content": "Lotte mengangkat bahu.\n\n\"Na, und jetzt?\" tanyanya, lalu menunggu."})
    engine.send(chat, "Aku diam.")
    wait_idle(engine)
    bot = engine.display(chat)["items"][-1]
    assert "Paragraf tambahan" not in bot["content"]
    note = [m for m in nb["STORE"].path(chat) if m["role"] == "user"][-1]["meta"]["ephemeral"]
    assert "paragraf pendek" in note and "kerangka per paragraf" not in note


def test_news_counts_as_told_only_when_told(engine, nb, fake):
    chat, _ = _story(nb, engine)
    S, W = nb["STORE"], nb["WORLD"]
    eid = W.add_world_event(chat, None, "2026-12-19 21:00", "Polisi menggeledah toko roti Herr Weber.", ["player"])
    unseen = lambda: [e["id"] for e in W.world_events(chat, S.path_ids(chat), who="player", unseen_only=True)]
    fake["script"].append({"content": "Lotte menyalakan lampu dan duduk di sofa.\n\nHujan mengetuk jendela."})
    engine.send(chat, "Aku duduk.")
    wait_idle(engine)
    assert eid in unseen() and S.chat(chat)["settings"]["offered"] == {str(eid): 1}
    fake["script"].append({"content": "Dari jendela kamu melihat polisi menggeledah toko roti Herr Weber di seberang jalan."})
    engine.send(chat, "Aku melihat keluar.")
    wait_idle(engine)
    assert eid not in unseen() and S.chat(chat)["settings"]["offered"] == {}


def test_offscreen_world_moves_after_hours_of_play(engine, nb, fake):
    chat, _ = _story(nb, engine)
    S = nb["STORE"]
    assert engine._offscreen_span(chat) is None  # the first look sets the mark
    nb["WORLD"].advance(chat, S.chat(chat)["head_id"], 300, "tidur")
    sync, now, minutes = engine._offscreen_span(chat)
    assert minutes == 300
    engine._queue_offscreen(chat)
    assert engine.offscreen_jobs == [chat]
    n = len(fake["log"])
    engine._offscreen(engine.offscreen_jobs.pop(0))
    body = fake["log"][n]
    assert "TIDAK sedang satu adegan dengan pemain" in json.dumps(body, ensure_ascii=False)
    assert len(body["tools"]) == len(engine.tools.specs(engine.prompt.ctx(chat)))  # same prompt prefix as the chat
    assert any("Frau Brunner" in e["text"] for e in nb["WORLD"].world_events(chat, S.path_ids(chat)))
    assert engine._offscreen_span(chat) is None


def test_checker_records_when_it_runs(engine, nb, monkeypatch):
    P = nb["PROMPT"]
    monkeypatch.setenv("QCHAT_STATE_CHECK", "1")
    chat, _ = _story(nb, engine)
    text = P.system_text(chat)
    assert nb["RECORD_MARK"] in text and "catat dengan relationship" not in text
    monkeypatch.setenv("QCHAT_STATE_CHECK", "0")
    other, _ = _story(nb, engine)
    assert "catat dengan relationship" in P.system_text(other)


# ---------- pamor and first meetings ----------

def _campus(nb, engine, n=14):
    C = nb["CARDS"]
    world = C.save(None, "world", {"name": "Kampus Fiksi", "realworld": "tidak"})
    sc = C.save(None, "scenario", {"title": "Ospek", "start_time": "2026-08-01 08:00", "start_location": "Aula",
                                   "opening": "Aula penuh mahasiswa baru."})
    persona = C.save(None, "persona", {"name": "Hanz Pratama"})
    ids = []
    for name in ["Mira Santoso", "Bu Ratna"] + [f"Mahasiswi {i}" for i in range(n - 2)]:
        fame = {"Mira Santoso": "bintang", "Bu Ratna": "terkenal"}.get(name, "biasa")
        ids.append(C.save(None, "character", {"name": name, "role": "dosen" if name.startswith("Bu ") else "mahasiswi",
                                              "personality": f"Kepribadian khas {name}.", "fame": fame,
                                              "fame_for": "ketua BEM" if name == "Mira Santoso" else ""}))
    gm = C.save(None, "gm", {"format": "prosa"})
    return engine.start_story({"world": world, "scenario": sc, "persona": persona, "character": ids, "gm": gm}), ids


def test_large_cast_keeps_the_best_known_in_the_prompt(engine, nb):
    chat, _ = _campus(nb, engine)
    P, S = nb["PROMPT"], nb["STORE"]
    text = P.system_text(chat)
    assert "Kepribadian khas Mira Santoso" in text and "Kepribadian khas Bu Ratna" in text
    assert "Kepribadian khas Mahasiswi 3" not in text and "- Mahasiswi 3: mahasiswi · pamor biasa" in text
    assert "## Dikenal umum" in text and "- Mira Santoso (bintang): mahasiswi · ketua BEM" in text
    S.add_message(chat, S.chat(chat)["head_id"], "user", "Aku menyapa Mahasiswi 3.")
    msgs, used = P.build(chat)
    note = msgs[-1]["content"]
    assert "Kepribadian khas Mahasiswi 3" in note  # its card comes along when it appears
    assert "belum tercatat kenal Hanz Pratama" in note and used["unmet"] == ["Mahasiswi 3"]


def test_first_meeting_is_noted_and_recorded(engine, nb, fake, monkeypatch):
    chat, _ = _campus(nb, engine, n=4)  # a small cast: every card stays in the system prompt
    S, K, P = nb["STORE"], nb["KNOW"], nb["PROMPT"]
    assert "Kepribadian khas Mahasiswi 1" in P.system_text(chat)
    monkeypatch.setenv("QCHAT_STATE_CHECK", "1")
    n = len(fake["log"])
    engine.send(chat, "Aku menyapa Mira Santoso.")
    wait_idle(engine)
    assert any("Pertemuan pertama dengan pemain mungkin terjadi di giliran ini: Mira Santoso" in json.dumps(b, ensure_ascii=False)
               for b in fake["log"][n:])
    monkeypatch.setenv("QCHAT_STATE_CHECK", "0")
    K.add(chat, None, ["Mira Santoso"], "Bertemu mahasiswa baru di aula saat ospek; belum tahu namanya", kind="kenalan")
    K.add(chat, None, ["Bu Ratna"], "Hanz sering telat masuk kelas")  # knowing something about him counts too
    S.add_message(chat, S.chat(chat)["head_id"], "user", "Aku menyapa Mira Santoso dan Bu Ratna.")
    msgs, used = P.build(chat)
    assert "belum tercatat kenal" not in msgs[-1]["content"] and not used.get("unmet")


def test_fame_suggestions_and_save(engine, nb, fake):
    from types import SimpleNamespace
    chat, _ = _campus(nb, engine, n=4)
    fake["script"].append({"content": json.dumps({"items": [
        {"name": "Mahasiswi 0", "fame": "terkenal", "fame_for": "juara debat", "reason": "prestasi"},
        {"name": "Mahasiswi 1", "fame": "super", "reason": "x"}]})})
    rows = engine.suggest_fame(chat)
    by = {r["name"]: r for r in rows}
    assert len(rows) == 4 and by["Mahasiswi 0"]["fame"] == "terkenal" and by["Mahasiswi 0"]["fame_for"] == "juara debat"
    assert by["Mahasiswi 1"]["fame"] == "biasa" and by["Mira Santoso"]["current"] == "bintang"
    toasts = []
    obj = SimpleNamespace(w=SimpleNamespace(), _toast=lambda t, k="info": toasts.append(t), _cur=lambda: chat,
                          story_info=lambda ch: {"ok": 1})
    nb["ChatApp"].c_fame_save(obj, [{"card_id": by["Mahasiswi 0"]["card_id"], "fame": "terkenal", "fame_for": "juara debat"},
                                    {"card_id": by["Mira Santoso"]["card_id"], "fame": "bintang", "fame_for": "ketua BEM"}])
    assert nb["CARDS"].get(by["Mahasiswi 0"]["card_id"])["data"]["fame"] == "terkenal"
    assert "untuk 1 kartu" in toasts[0] and obj.w.story == {"ok": 1}


def test_world_tick_puts_the_best_known_first(engine, nb, fake):
    from datetime import datetime
    chat, _ = _campus(nb, engine, n=4)
    n = len(fake["log"])
    engine._tick(chat, datetime(2026, 8, 1, 8, 0), 300, "uji")
    assert "Tokoh paling dikenal: Mira Santoso, Bu Ratna" in json.dumps(fake["log"][n], ensure_ascii=False)
