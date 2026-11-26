import json
import time

from conftest import wait_idle
from test_core import _story


def test_studio_tools(engine, nb):
    T, C, S = nb["TOOLS"], nb["CARDS"], nb["STORE"]
    chat = engine.new_chat("studio", "Studio uji")
    res, failed, _ = T.call(chat, None, "card_draft_update", json.dumps({"type": "character", "field": "name", "value": "Mira"}))
    assert not failed, res
    cid = json.loads(res)["card_id"]
    T.call(chat, None, "card_draft_update", json.dumps({"type": "character", "card_id": cid, "field": "speech_samples",
                                                         "value": ["Hm.", "Nein!"]}))
    assert C.get(cid)["data"]["speech_samples"] == ["Hm.", "Nein!"] and C.get(cid)["version"] == 2
    res, failed, _ = T.call(chat, None, "lore_add", json.dumps({"title": "Kiez", "text": "lingkungan"}))
    assert failed and "kartu dunia" in res  # no world yet
    T.call(chat, None, "card_draft_update", json.dumps({"type": "world", "field": "name", "value": "Berlin"}))
    res, failed, _ = T.call(chat, None, "lore_add", json.dumps({"title": "Kiez", "text": "lingkungan", "keys": "kiez"}))
    assert not failed, res
    res, failed, _ = T.call(chat, None, "timeline_add", json.dumps({"at": "kemarin", "title": "x"}))
    assert failed
    res, failed, _ = T.call(chat, None, "timeline_add", json.dumps({"at": "2026-12-24 18:00", "title": "Malam Natal"}))
    assert not failed
    drafts = S.chat(chat)["settings"]["studio"]["drafts"]
    assert drafts["character"] == [cid] and drafts["world"]
    note = nb["STUDIO_EPHEMERAL"](nb["PROMPT"].ctx(chat))
    assert "Mira" in note and "Malam Natal" in note


def test_card_update_from_rp(engine, nb, fake):
    chat, _ = _story(nb, engine)
    sid0 = nb["STORE"].chat(chat)["story_id"]
    lotte = nb["STORIES"].cards_of(sid0)["character"][0]["id"]  # other tests made their own "Lotte Braun" cards
    v = nb["CARDS"].get(lotte)["version"]
    fake["script"] += [{"tool_calls": [{"name": "card_update", "arguments": json.dumps({"card": "Lotte", "field": "age", "value": "24"})}]},
                       {"content": "Umur Lotte jadi 24."}]
    engine.send(chat, "((ubah: Lotte umurnya 24))")
    wait_idle(engine)
    card = nb["CARDS"].get(lotte)
    assert card["data"]["age"] == "24" and card["version"] == v + 1
    sid = nb["STORE"].chat(chat)["story_id"]
    assert any("Lotte Braun · age: 24" in p["text"] for p in nb["STORIES"].pending_list(sid, chat))
    assert nb["STORE"].side_logs(chat, "studio_change")


def _real_world_story(nb, engine):
    C = nb["CARDS"]
    world = C.save(None, "world", {"name": "Westfront", "realworld": "ya", "wiki_lang": "de"})
    lotte = C.save(None, "character", {"name": "Feldwebel Kraus"})
    chat = engine.start_story({"world": world, "character": [lotte]})
    nb["STORE"].chat_settings(chat, length="pendek")
    return chat, world


def _fake_wiki(nb, monkeypatch):
    web = nb["WEB"]
    monkeypatch.setattr(web, "wiki_search", lambda q, langs=("de",), limit=3: json.dumps(
        {"results": [{"lang": "de", "title": "Schlacht an der Somme", "url": "https://de.wikipedia.org/wiki/Schlacht_an_der_Somme"}]}))
    monkeypatch.setattr(web, "wiki_read", lambda title, lang="de", max_chars=8000: json.dumps(
        {"title": title, "url": "https://de.wikipedia.org/wiki/Schlacht_an_der_Somme", "text": "Die Schlacht begann am 1. Juli 1916."}))


def test_fact_check_flow_and_lookup(engine, nb, fake, monkeypatch):
    _fake_wiki(nb, monkeypatch)
    chat, world = _real_world_story(nb, engine)
    fake["script"].append({"content": "Serangan Somme dimulai 3 Juli 1916. Kraus menatap parit."})
    engine.send(chat, "Kapan serangan dimulai?")
    wait_idle(engine)
    mid = nb["STORE"].chat(chat)["head_id"]
    fake["script"] += [{"content": json.dumps({"claims": ["Serangan Somme dimulai 3 Juli 1916"]})},
                       {"content": json.dumps({"verdict": "salah", "correction": "Dimulai 1 Juli 1916.",
                                               "fact": "Pertempuran Somme dimulai 1 Juli 1916."})}]
    warnings = engine._fact_check(chat, mid, True)
    assert warnings and warnings[0]["correction"] == "Dimulai 1 Juli 1916."
    assert nb["STORE"].msg(mid)["meta"]["fact_warnings"]
    res, _, _ = nb["TOOLS"].call(chat, None, "fact_lookup", json.dumps({"query": "Somme dimulai"}))
    assert "1 Juli 1916" in res and "wikipedia" in res
    assert nb["STORE"].side_logs(chat, "fact_check")


def test_strict_fact_mode_rewrites(engine, nb, fake, monkeypatch):
    _fake_wiki(nb, monkeypatch)
    chat, _ = _real_world_story(nb, engine)
    nb["STORE"].chat_settings(chat, fact_mode="ketat")
    fake["script"] += [{"content": "Serangan dimulai 3 Juli 1916."},
                       {"content": json.dumps({"claims": ["Serangan Somme dimulai 3 Juli 1916"]})},
                       {"content": json.dumps({"verdict": "salah", "correction": "Dimulai 1 Juli 1916.", "fact": "Somme 1 Juli 1916."})},
                       {"content": "Serangan dimulai 1 Juli 1916, pagi berkabut."}]
    engine.send(chat, "Kapan serangan dimulai?")
    wait_idle(engine, 60)
    last = engine.display(chat)["items"][-1]
    assert "1 Juli 1916" in last["content"] and last["swipe"] == [2, 2], last
    rewrite = next(b for b in reversed(fake["log"]) if "pagi berkabut" not in json.dumps(b) and "Koreksi fakta" in json.dumps(b["messages"][-1]))
    assert rewrite
    assert any(t.get("kind") == "warn" for t in engine.events.of("toast"))


def test_turn_note_and_side_logs(engine, nb):
    chat, _ = _story(nb, engine)
    engine.send(chat, "Halo Lotte.")
    wait_idle(engine)
    user = next(i for i in engine.display(chat)["items"] if i["kind"] == "user")
    assert user["has_note"]
    note = nb["STORE"].msg(user["id"])["meta"]["ephemeral"]
    assert "Jam dunia" in note
    engine.slash(chat, "impersonate", "")
    wait_idle(engine)
    assert nb["STORE"].side_logs(chat, "impersonate")[0]["data"]["draft"].startswith("Aku")


def test_meta_set_does_not_dirty_when_unchanged(nb):
    S = nb["STORE"]
    S.meta_set("server", {"preset": "x", "ctx": 1})
    rev = S.rev
    S.meta_set("server", {"preset": "x", "ctx": 1})
    assert S.rev == rev


def test_compare_branches(engine, nb, fake):
    chat, _ = _story(nb, engine)
    engine.send(chat, "Aku duduk.")
    wait_idle(engine)
    first = nb["STORE"].chat(chat)["head_id"]
    fake["script"].append({"content": "Versi kedua narasi."})
    engine.reroll(chat, first)
    wait_idle(engine)
    second = nb["STORE"].chat(chat)["head_id"]
    cmp = engine.compare(chat, first, second)
    assert cmp["a"] and cmp["b"] and cmp["b"][0]["content"].startswith("Versi kedua")


def test_history_search_hybrid(engine, nb, monkeypatch):
    import os
    monkeypatch.setenv("QCHAT_EMBED_URL", os.environ["QCHAT_BASE_URL"].removesuffix("/v1"))
    chat = engine.new_chat("chat", "kopi")
    S = nb["STORE"]
    mid = S.add_message(chat, None, "user", "Pagi ini aku minum kopi tubruk di dapur.")
    nb["EMB"].backfill()
    for _ in range(300):
        if S.one("SELECT 1 AS x FROM vectors WHERE kind = 'msg' AND ref_id = ?", (mid * 100,)):
            break
        time.sleep(0.05)
    nb["EMB"].cache.clear()
    res, failed, _ = nb["TOOLS"].call(chat, None, "history_search", json.dumps({"query": "coffee"}))
    assert not failed and any(r["id"] == mid for r in json.loads(res)["results"]), res


def test_away_notice(engine, nb):
    chat, _ = _story(nb, engine)
    nb["STORE"].chat_settings(chat, world_sync=time.time() - 2 * 3600)
    engine.send(chat, "Aku pulang.")
    wait_idle(engine)
    notes = engine.events.of("notice")
    assert notes and notes[-1]["text"].startswith("Selama kamu pergi") and "Frau Brunner" in notes[-1]["text"]


def test_server_failure_diagnosis(nb, tmp_path):
    SM = nb["ServerManager"]
    humming = ("RuntimeError: NVRTCCompiler failed with exit code 1; source and compiler logs: " + str(tmp_path) +
               "\n  File humming/kernel/repack_weight.py")
    (tmp_path / "compile.log").write_text("error: identifier __nv_fp8_e4m3 is undefined")
    assert not SM.SPEC_ERROR.search(humming)
    assert "__nv_fp8_e4m3" in SM.jit_logs(humming)
    assert "llama.cpp" in SM.hint(humming, {})
    assert SM.SPEC_ERROR.search("ValueError: speculative config for draft model is invalid")
