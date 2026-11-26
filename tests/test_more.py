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
    assert "linear_backend_per_quant" in SM.hint(humming, {})
    assert SM.SPEC_ERROR.search("ValueError: speculative config for draft model is invalid")


def test_dark_gemistry_vllm_cmd_uses_marlin_and_mtp(nb):
    SM, P = nb["SERVERS"], nb["PRESETS"]
    p = P["Dark-Gemistry 31B FP8 (W8A16) · vLLM"]
    SM.state["embed"] = False
    cmd = SM._vllm_cmd(p, {"model": "/m", "draft": "/d"}, 262144, True)
    i = cmd.index("--kernel-config")
    assert json.loads(cmd[i + 1]) == {"linear_backend_per_quant": {"w8a16_fp8": "marlin"}}
    spec = json.loads(cmd[cmd.index("--speculative-config") + 1])
    assert spec["model"] == "/d" and spec["num_speculative_tokens"] == 3
    assert "--tool-call-parser" in cmd and cmd[cmd.index("--tool-call-parser") + 1] == "gemma4"


def test_llama_install_skips_github_api_and_checks_sha(nb):
    cmd = nb["ServerManager"].llama_install_cmd()
    assert "api.github.com" not in cmd
    for name, sha in nb["CFG"].LLAMA_ASSETS.items():
        assert f"releases/download/{nb['CFG'].LLAMA_TAG}/{name}" in cmd and f"echo '{sha}  {name}' | sha256sum -c -" in cmd


def test_tool_rounds_have_no_cap(engine, nb, fake):
    chat, _ = _story(nb, engine)
    call = {"tool_calls": [{"name": "fact_lookup", "arguments": json.dumps({"query": "x"})}]}
    fake["script"] += [call] * 15 + [{"content": "Selesai setelah lima belas tool."}]
    engine.send(chat, "Cari terus.")
    wait_idle(engine, 60)
    last = engine.display(chat)["items"][-1]
    assert last["content"].startswith("Selesai") and not last.get("error"), last
    assert len(last["tools"]) >= 15


def test_failed_camoufox_start_does_not_break_chromium_fallback(nb, monkeypatch):
    """A Camoufox launch that fails after Playwright started used to leave Playwright's asyncio loop running on the
    browser thread: every later search then failed with "using Playwright Sync API inside the asyncio loop"."""
    import types
    import pytest
    sync_api = pytest.importorskip("playwright.sync_api")
    import asyncio
    import sys
    policy = asyncio.get_event_loop_policy()
    if sys.platform == "win32":  # marimo switches Windows to the selector loop, which cannot start subprocesses
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    class BrokenCamoufox:
        def __init__(self, **kw):
            self.cm = sync_api.sync_playwright()

        def __enter__(self):
            self.cm.__enter__()
            raise RuntimeError("firefox would not start")

        def __exit__(self, *a):
            raise RuntimeError("cleanup failed too")  # worst case: the loop stays marked as running

    mod = types.ModuleType("camoufox.sync_api")
    mod.Camoufox = BrokenCamoufox
    monkeypatch.setitem(__import__("sys").modules, "camoufox", types.ModuleType("camoufox"))
    monkeypatch.setitem(__import__("sys").modules, "camoufox.sync_api", mod)
    web = nb["WebTools"]()
    try:
        for _ in range(2):
            res = json.loads(web.web_search("Odeonsplatz", engine="tidak-ada"))
            assert "asyncio loop" not in json.dumps(res), res
        assert "firefox would not start" in web.camoufox_failed[1], (web.camoufox_failed, res)
        web._run(web._close)
    finally:
        asyncio.set_event_loop_policy(policy)


def test_table_fields_accept_what_models_send(engine, nb):
    T, C = nb["TOOLS"], nb["CARDS"]
    chat = engine.new_chat("studio", "Studio tabel")
    res = json.loads(T.call(chat, None, "card_draft_update", json.dumps({"type": "world", "field": "name", "value": "M"}))[0])
    wid = res["card_id"]

    def put(field, value):
        out, failed, _ = T.call(chat, None, "card_draft_update", json.dumps({"type": "world", "card_id": wid,
                                                                          "field": field, "value": value}))
        return json.loads(out), C.get(wid)["data"][field]

    # a JSON string of rows (what the screenshot's model sent)
    rep, rows = put("stats", json.dumps([["energi", "Energi", 0, 100, 88, -2], ["lapar", "Lapar", 0, 100, 42, 4]]))
    assert rows == [["energi", "Energi", "0", "100", "88", "-2"], ["lapar", "Lapar", "0", "100", "42", "4"]] and rep["rows"] == 2
    # markdown table with a header and separator row
    _, rows = put("stats", "| key | label | min | max | awal | laju per jam |\n|---|---|---|---|---|---|\n| mandi | Mandi | 0 | 3 | 1 | |")
    assert rows == [["mandi", "Mandi", "0", "3", "1", ""]]
    # objects with the model's own key names
    _, rows = put("climate", [{"month": "11", "min": -1, "max": 6, "weather": ["berawan", "hujan"]}])
    assert rows == [["11", "-1", "6", "berawan, hujan"]]
    # CSV lines: the extra commas belong to the last column
    _, rows = put("climate", "12, -3, 3, salju, berawan")
    assert rows == [["12", "-3", "3", "salju, berawan"]]
    # a mapping for a two-column table
    _, rows = put("terms", {"Tach": "salam santai", "Kiez": "lingkungan"})
    assert rows == [["Tach", "salam santai"], ["Kiez", "lingkungan"]]
    rep, _ = put("terms", "|---|")
    assert "error" in rep
    defs = nb["WORLD"].stat_defs({"world": {"data": {"stats": "lapar, Lapar, 0, 100, 20, 4"}}})
    assert defs[0]["key"] == "lapar" and defs[0]["rate"] == 4.0  # a raw string never crashes the engine
    assert C.get(wid)["data"]["stats"][0][0] == "mandi"


def test_card_get_repairs_tables_stored_as_text(nb):
    C, S = nb["CARDS"], nb["STORE"]
    wid = C.save(None, "world", {"name": "Lama"})
    S.x("UPDATE cards SET data = ? WHERE id = ?", (json.dumps({"name": "Lama", "stats": '[["haus","Haus",0,100,10,5]]'}), wid))
    assert C.get(wid)["data"]["stats"] == [["haus", "Haus", "0", "100", "10", "5"]]


def test_studio_card_changes_reach_the_widget(engine, nb):
    T, C = nb["TOOLS"], nb["CARDS"]
    seen = []
    old = C.on_change
    C.on_change = seen.append
    try:
        chat = engine.new_chat("studio", "Studio NPC")
        res = json.loads(T.call(chat, None, "card_draft_update", json.dumps({"type": "character", "field": "backstory",
                                                                           "value": "Lahir di Wina"}))[0])
        cid = res["card_id"]
        assert cid in seen and "note" in res  # no name yet: the model is told
        gm = C.save(None, "gm", {"name": "GM uji"})
        res, failed, _ = T.call(chat, None, "card_draft_update", json.dumps({"type": "character", "card_id": gm,
                                                                           "field": "name", "value": "Otto"}))
        assert failed and "bertipe gm" in res and C.get(gm)["name"] == "GM uji"
        lib = C.save(None, "character", {"name": "Frau Brunner"})
        T.call(chat, None, "card_draft_update", json.dumps({"type": "character", "card_id": lib, "field": "age", "value": "70"}))
        drafts = nb["STORE"].chat(chat)["settings"]["studio"]["drafts"]["character"]
        assert drafts == [cid, lib]
        world = C.save(None, "world", {"name": "W"})
        seen.clear()
        C.lore_save(world, "Kiez", "lingkungan")
        C.timeline_save(world, "2026-11-01 08:00", "Mulai")
        assert seen == [world, world]
    finally:
        C.on_change = old


def test_widget_refreshes_library_after_card_change(nb):
    import time as _t
    app = nb["CHAT_APP"]
    app.w.library = app.library_info()
    cid = nb["CARDS"].save(None, "character", {"name": "Weber Widget"})
    for _ in range(60):
        if any(c["id"] == cid for c in app.w.library["cards"]):
            break
        _t.sleep(0.05)
    assert any(c["id"] == cid for c in app.w.library["cards"])


def test_tool_calls_refresh_widget(nb, engine):
    import time as _t
    app = nb["CHAT_APP"]
    rev = app.w.rev
    chat = engine.new_chat("chat", "memori")
    nb["TOOLS"].call(chat, None, "memory_save", json.dumps({"text": "Pemain suka kopi tubruk.", "scope": "user"}))
    for _ in range(60):
        if app.w.rev > rev:
            break
        _t.sleep(0.05)
    assert app.w.rev > rev
