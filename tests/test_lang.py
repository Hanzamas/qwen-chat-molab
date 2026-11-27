"""Compaction trigger, English narration and the target-language level."""
import json

from conftest import wait_idle


def _german_story(nb, engine, skill=55):
    C = nb["CARDS"]
    world = C.save(None, "world", {"name": "Berlin", "realworld": "tidak"})
    sc = C.save(None, "scenario", {"title": "Kurs", "start_time": "2026-09-01 09:00", "start_location": "Kelas",
                                   "opening": "Frau Weber betritt den Raum."})
    persona = C.save(None, "persona", {"name": "Hanz", "skill_levels": [["Bahasa Jerman", skill]]})
    weber = C.save(None, "character", {"name": "Frau Weber", "aliases": ["Weber"]})
    style = C.save(None, "style", {"narration_lang": "English", "target_lang": "de", "paragraphs": "1-2", "sentences": "2-4"})
    gm = C.save(None, "gm", {"format": "prosa"})
    return engine.start_story({"world": world, "scenario": sc, "persona": persona, "character": [weber], "gm": gm,
                               "style": style})


def test_compaction_counts_the_room_for_the_reply(engine, nb, monkeypatch):
    chat = engine.new_chat("chat", "ctx")
    cp = engine.compactor
    maxc = nb["LLM_CLIENT"].max_context()
    calls = []
    monkeypatch.setattr(cp, "_compact", lambda *a, **k: calls.append(1) or 1)
    monkeypatch.setattr(cp, "measure", lambda chat_id, tools: int(maxc * 0.70))
    assert cp.maybe(chat, [], engine.tools, reserve=int(maxc * 0.10)) == int(maxc * 0.70) and not calls
    cp.maybe(chat, [], engine.tools, reserve=int(maxc * 0.30))  # 70% + 30% does not fit: compact now
    assert calls == [1]
    monkeypatch.setattr(cp, "measure", lambda chat_id, tools: int(maxc * 0.81))
    cp.maybe(chat, [], engine.tools)
    assert calls == [1, 1] and cp.COMPACT_AT == 0.80


def test_compaction_says_why_it_did_not_run(engine, nb, monkeypatch):
    chat = engine.new_chat("chat", "kosong")
    engine.compactor.last_note = "Compaction skipped: only 1 player message(s) since the last summary; it runs after 4."
    engine._compaction_note(chat)
    engine._compaction_note(chat)  # the same reason is not repeated
    toasts = [t for t in engine.events.of("toast") if "Compaction skipped" in t["text"]]
    assert len(toasts) == 1


def test_note_forces_english_and_the_level(engine, nb):
    chat = _german_story(nb, engine)
    S = nb["STORE"]
    S.add_message(chat, S.chat(chat)["head_id"], "user", "Aku duduk.")
    msgs, used = nb["PROMPT"].build(chat)
    note = msgs[-1]["content"]
    assert "narasi wajib bahasa English" in note and "SELALU diterjemahkan ke English" in note
    assert "B1 (55/100)" in note and "8-15 kata" in note and used["lang"]["band"] == "B1"
    assert engine.panels(chat)["lang"] == {"label": "German", "band": "B1", "value": 55}


def test_short_untranslated_german_is_flagged_and_reinforced(engine, nb, fake):
    chat = _german_story(nb, engine)
    fake["script"].append({"content": 'Frau Weber looks up. "Ich bin da." She waits. "Und du?" (And you?)'})
    engine.send(chat, "I sit down.")
    wait_idle(engine)
    flags = {f["kind"] for f in engine.display(chat)["items"][-1]["flags"]}
    assert {"lang_short", "lang_untranslated"} <= flags
    fix = nb["STORE"].chat(chat)["settings"]["lang_fix"]
    assert fix["left"] == 3 and "terjemahkan SETIAP kalimat" in fix["text"]
    n = len(fake["log"])
    engine.send(chat, "I listen.")
    wait_idle(engine)
    assert "terjemahkan SETIAP kalimat" in json.dumps(fake["log"][n], ensure_ascii=False)


def test_level_grows_from_play(engine, nb, fake):
    chat = _german_story(nb, engine, skill=60)
    S, W, T = nb["STORE"], nb["WORLD"], nb["TOOLS"]
    fake["script"].append({"content": 'Frau Weber nods. "Das ist sehr gut gesagt, wirklich." (That is very well said, really.)'})
    engine.send(chat, '"Ich habe meine Hausaufgaben heute gemacht."')
    wait_idle(engine)
    assert engine.panels(chat)["lang"] == {"label": "German", "band": "B2", "value": 61}
    assert any("improved to B2" in n["text"] for n in engine.events.of("notice"))
    head = S.chat(chat)["head_id"]
    res = json.loads(T.call(chat, head, "roll", json.dumps({"event": "versteht den Dialekt", "skill": "Bahasa Jerman"}))[0])
    assert "German B2" in res["result"]
    assert engine.panels(chat)["lang"]["value"] in (62, 63)  # +0.5 failed, +2 passed
    W.advance(chat, head, 14 * 24 * 60, "dua minggu")
    assert engine.panels(chat)["lang"]["value"] >= 67  # +3 per world week


def test_learn_explains_in_english(engine, nb, fake):
    chat = _german_story(nb, engine)
    n = len(fake["log"])
    engine.learn(chat, "Ich habe keine Zeit.")
    wait_idle(engine)
    body = json.dumps(fake["log"][n], ensure_ascii=False)
    assert "learner of German" in body and "Write everything in English" in body


def test_wrong_narration_language_is_rewritten_once(engine, nb, fake, monkeypatch):
    monkeypatch.setenv("QCHAT_LANG_REWRITE", "1")
    chat = _german_story(nb, engine)
    indo = ("Frau Weber masuk ke kelas dan menutup pintu dengan pelan. Dia melihat ke arah kamu dan tersenyum, lalu dia "
            "berjalan ke meja yang ada di depan dan meletakkan tas di atas meja itu. Semua orang diam karena dia sudah ada di sini.")
    fake["script"] += [{"content": indo}, {"content": "Frau Weber walks in and closes the door. She smiles at you and waits."}]
    engine.send(chat, "I wait.")
    wait_idle(engine, 60)
    last = engine.display(chat)["items"][-1]
    assert last["content"].startswith("Frau Weber walks in") and last["swipe"] == [2, 2]
