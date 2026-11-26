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
    calls = [{"tool_calls": [{"name": "fact_lookup", "arguments": json.dumps({"query": f"x{i}"})}]} for i in range(15)]
    fake["script"] += calls + [{"content": "Selesai setelah lima belas tool."}]
    engine.send(chat, "Cari terus.")
    wait_idle(engine, 60)
    last = engine.display(chat)["items"][-1]
    assert last["content"].startswith("Selesai") and not last.get("error"), last
    assert len(last["tools"]) >= 15


def test_identical_tool_calls_are_not_repeated_forever(engine, nb, fake):
    chat, _ = _story(nb, engine)
    call = {"tool_calls": [{"name": "fact_lookup", "arguments": json.dumps({"query": "sama"})}]}
    fake["script"] += [call] * 3 + [{"content": "Jawab dengan yang ada."}]
    engine.send(chat, "Cari.")
    wait_idle(engine, 60)
    tools = [m for m in nb["STORE"].path(chat) if m["role"] == "tool"][-3:]
    assert "sudah dilakukan 2 kali" in tools[-1]["content"] and "sudah dilakukan" not in tools[0]["content"]
    assert engine.display(chat)["items"][-1]["content"].startswith("Jawab")


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


def test_dates_in_model_formats(nb):
    P = nb["TXT"].parse_datetime
    want = "2026-11-01 07:30"
    for s in ["2026-11-01 07:30", "2026-11-01T07:30:00", "01.11.2026 07:30", "1 November 2026 pukul 07.30",
              "Minggu, 1 November 2026, 07:30", "1. November 2026, um 7:30 Uhr", "1 Nov 2026 07:30"]:
        assert P(s) and P(s).strftime("%Y-%m-%d %H:%M") == want, s
    assert P("1 Desember 1916").strftime("%Y-%m-%d %H:%M") == "1916-12-01 00:00"
    assert P("besok pagi") is None and P("") is None


def test_scenario_card_from_studio_is_readable(engine, nb):
    T, C = nb["TOOLS"], nb["CARDS"]
    chat = engine.new_chat("studio", "Studio skenario")

    def put(field, value, cid=None):
        args = {"type": "scenario", "field": field, "value": value}
        if cid:
            args["card_id"] = cid
        out, failed, _ = T.call(chat, None, "card_draft_update", json.dumps(args))
        return json.loads(out)

    sid = put("title", "The Haircut")["card_id"]
    rep = put("start_time", "Minggu, 1 November 2026, 07:30", sid)
    assert "error" not in rep and C.get(sid)["data"]["start_time"] == "2026-11-01 07:30"
    rep = put("start_time", "pagi hari pertama", sid)
    assert "error" in rep and "YYYY-MM-DD" in rep["error"]
    put("start_time", "2026-11-01 07:30", sid)
    style = C.save(None, "style", {"name": "Gaya uji"})
    T.call(chat, None, "card_draft_update", json.dumps({"type": "style", "card_id": style, "field": "pov", "value": "ORANG KETIGA"}))
    assert C.get(style)["data"]["pov"] == "orang ketiga"  # matched to the option, so the form shows it
    out, _, _ = T.call(chat, None, "card_draft_update", json.dumps({"type": "style", "card_id": style, "field": "pov",
                                                                  "value": "campuran"}))
    assert "Pilihan" in json.loads(out)["note"] and C.get(style)["data"]["pov"] == "campuran"
    put("start_stats", [{"key": "lapar", "nilai": 42}], sid)
    card = C.get(sid)
    assert card["data"]["start_stats"] == [["lapar", "42"]]
    assert nb["WORLD"].start_time({"scenario": card}).strftime("%Y-%m-%d %H:%M") == "2026-11-01 07:30"
    drafts = nb["STORE"].chat(chat)["settings"]["studio"]["drafts"]
    assert drafts["scenario"] == sid


def test_compaction_progress_and_clean_cancel(engine, nb, fake):
    import threading as _th
    eng = engine
    chat, _ = _story(nb, eng)
    for i in range(5):
        eng.send(chat, f"giliran {i}")
        wait_idle(eng)
    comp, S = eng.compactor, nb["STORE"]
    path = S.path(chat)
    tools = nb["TOOLS"].specs(nb["PROMPT"].ctx(chat))
    comp.cancel.clear()  # every send sets it (it stops a running idle compaction)
    # progress lines while the model writes
    seen = []
    text = comp.summarize(chat, path, 0, len(path) - 1, 4096, 0, tools, comp.progress(seen.append, "Meringkas…", 4096))
    assert text and "## Inti" in text
    cb = comp.progress(seen.append, "Meringkas…", 4096)
    cb({"reasoning": "x" * 700, "content": "y" * 3500})
    assert seen[-1] == "Meringkas… mikir ≈200 · tulis ≈1.000 / 4.096 token"
    # a cancelled summary is never stored as if it were complete
    comp.cancel.set()
    try:
        assert comp.summarize(chat, path, 0, len(path) - 1, 4096, 0, tools) is None
    finally:
        comp.cancel.clear()
    # compaction runs one at a time
    assert comp.lock.acquire(timeout=1)
    got = []
    t = _th.Thread(target=lambda: got.append(comp.maybe(chat, tools, nb["TOOLS"], force=True, clear_cancel=False)))
    t.start()
    t.join(0.5)
    assert t.is_alive() and not got  # waits for the lock
    comp.cancel.set()  # the waiting run starts after the lock is freed and stops right away when cancelled
    comp.lock.release()
    t.join(30)
    assert not t.is_alive()
    comp.cancel.clear()
    before = S.q("SELECT COUNT(*) AS n FROM summaries WHERE chat_id = ?", (chat,))[0]["n"]
    assert before == 0  # nothing half-written was stored


# ---------- regressions from the code review ----------

def test_saved_database_loads_back(nb, tmp_path):
    S = nb["STORE"]
    cid = S.new_chat("simpan-muat")
    S.add_message(cid, None, "user", "isi untuk diuji")
    data = S.export_bytes()  # the live DB runs in WAL mode
    before = S.q("SELECT COUNT(*) AS n FROM messages")[0]["n"]
    S.import_bytes(data)
    assert S.q("SELECT COUNT(*) AS n FROM messages")[0]["n"] == before
    assert S.file.with_name(S.file.name + ".before-import").exists()
    import pytest
    with pytest.raises(ValueError):
        S.import_bytes(b"bukan database sama sekali" * 100)
    assert S.q("SELECT COUNT(*) AS n FROM messages")[0]["n"] == before  # a bad file changes nothing


def test_import_refused_while_a_reply_is_written(engine, nb):
    import pytest
    S = nb["STORE"]
    data = S.export_bytes()
    engine.busy = True
    try:
        with pytest.raises(RuntimeError):
            S.import_bytes(data)
    finally:
        engine.busy = False
    assert not engine.importing


def test_turn_note_is_kept_in_tool_rounds(engine, nb, fake):
    chat, _ = _story(nb, engine)
    fake["script"] += [{"tool_calls": [{"name": "world_advance", "arguments": json.dumps({"minutes": 5})}]},
                       {"content": "Lotte tersenyum."}]
    n0 = len(fake["log"])
    engine.send(chat, "Aku duduk.")
    wait_idle(engine)
    reqs = [b for b in fake["log"][n0:] if any(m.get("role") == "tool" for m in b["messages"])]
    assert reqs, "no request after the tool call"
    user = [m for m in reqs[0]["messages"] if m["role"] == "user"][-1]
    assert "Catatan sistem untuk giliran ini" in json.dumps(user, ensure_ascii=False)


def test_turn_writes_under_its_own_head(engine, nb, fake):
    import threading as _th
    chat, _ = _story(nb, engine)
    S = nb["STORE"]
    engine.send(chat, "Pertama.")
    wait_idle(engine)
    other = S.chat(chat)["head_id"]
    fake["script"].append({"content": "Jawaban lambat. " * 30, "slow": 0.05})
    engine.send(chat, "Kedua.")
    time.sleep(0.4)
    uid = [m for m in S.path(chat) if m["role"] == "user"][-1]["id"]
    S.set_head(chat, other)  # the UI moves the branch while the reply streams
    wait_idle(engine, 60)
    reply = [m for m in S.q("SELECT * FROM messages WHERE chat_id = ? AND role = 'assistant' ORDER BY id DESC LIMIT 1", (chat,))][0]
    assert reply["parent_id"] == uid and reply["content"].startswith("Jawaban lambat")


def test_reroll_while_busy_does_not_move_the_head(engine, nb):
    chat, _ = _story(nb, engine)
    engine.send(chat, "Halo.")
    wait_idle(engine)
    S = nb["STORE"]
    head = S.chat(chat)["head_id"]
    engine.busy = True
    try:
        engine.reroll(chat, head)
    finally:
        engine.busy = False
    assert S.chat(chat)["head_id"] == head


def test_stream_error_is_shown_once(engine, nb, fake):
    chat = engine.new_chat("chat", "galat")
    fake["script"].append({"stream_error": "CUDA out of memory"})
    engine.send(chat, "Halo")
    wait_idle(engine)
    items = engine.display(chat)["items"]
    bots = [i for i in items if i["kind"] == "bot"]
    assert len(bots) == 1
    msgs = [m for m in nb["STORE"].path(chat) if m["role"] == "assistant"]
    assert len(msgs) == 1 and "CUDA out of memory" in (msgs[0]["meta"].get("error") or "")


def test_status_list_fields(engine, nb):
    chat, _ = _story(nb, engine)
    W, S = nb["WORLD"], nb["STORE"]
    head = S.chat(chat)["head_id"]
    W.status_update(chat, head, "Lotte Braun", {"inventory": {"add": "pisau"}})
    W.status_update(chat, head, "Lotte Braun", {"inventory": {"add": "perisai"}})
    W.status_update(chat, head, "Lotte Braun", {"inventory": {"remove": "pisau"}})
    st = W.state(chat, S.path_ids(chat))["status"]["Lotte Braun"]
    assert st["inventory"] == ["perisai"]
    import pytest
    with pytest.raises(ValueError):  # nothing is applied when one change is bad
        W.status_update(chat, head, "player", {"lapar": 5, "energi": "banyak"})
    assert W.state(chat, S.path_ids(chat))["stats"][0]["value"] == 20


def test_card_delete_and_memory_undo_with_reused_ids(nb):
    C, M, S = nb["CARDS"], nb["MEM"], nb["STORE"]
    w = C.save(None, "world", {"name": "Hapus aku"})
    M.fact_save("Fakta milik dunia lama", "", "", w, 0.8)
    C.delete(w)
    assert not S.q("SELECT * FROM facts WHERE world_card_id = ?", (w,))
    ctx = {"chat_id": None, "story_id": None, "card_ids": []}
    a = M.save("Memory A unik untuk undo", "user", ctx)["saved"]
    log_a = S.one("SELECT id FROM memory_log WHERE memory_id = ? AND action = 'save'", (a,))["id"]
    M.forget(a, ctx)
    b = M.save("Memory B yang lain sama sekali", "user", ctx)["saved"]
    assert not M.undo(log_a)  # would have deleted B (same id)
    assert S.one("SELECT text FROM memories WHERE id = ?", (b,))["text"].startswith("Memory B")


def test_cancelled_background_fact_check_is_redone(engine, nb, fake):
    chat, _ = _story(nb, engine)
    engine.send(chat, "Halo.")
    wait_idle(engine)
    mid = nb["STORE"].chat(chat)["head_id"]
    engine.bg_cancel.set()
    try:
        engine.fact_jobs.clear()
        assert engine._fact_check(chat, mid, False) == []
        assert engine.fact_jobs and engine.fact_jobs[0] == (chat, mid)
        assert not nb["STORE"].msg(mid)["meta"].get("fact_checked")
    finally:
        engine.bg_cancel.clear()
        engine.fact_jobs.clear()


def test_json_and_ranges_never_raise(engine):
    assert engine._json('{"a": 1} lalu {x}') == {"a": 1}
    assert engine._json("tidak ada json {x}") is None
    assert engine._range("6-3", (1, 2)) == (3, 6)


def test_card_imports_odd_files(nb):
    import base64 as _b64
    import struct
    import zlib
    import pytest
    C = nb["CARDS"]
    st = {"spec": "chara_card_v2", "data": {"name": 7, "first_mes": "Halo {{user}}, aku {{char}}.",
                                             "character_book": {"entries": [{"keys": "naga, api", "content": "{{char}} takut naga"}]}}}
    cid = C.import_any(b"\xef\xbb\xbf" + json.dumps(st).encode())  # UTF-8 BOM, numeric name, keys as a string
    card = C.get(cid)
    assert card["name"] == "7" and card["data"]["greetings"][0] == "Halo {{user}}, aku 7."
    assert C.lore(cid)[0]["keys"] == "naga, api" and C.lore(cid)[0]["text"] == "7 takut naga"
    with pytest.raises(ValueError):
        C.import_any(b"[1, 2]")

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d))
    bomb = zlib.compress(b"A" * (80 * 1024 * 1024))
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"zTXt", b"chara\x00\x00" + bomb) + chunk(b"IEND", b"")
    with pytest.raises(ValueError):
        C.import_any(png)
    good = _b64.b64encode(json.dumps({"data": {"name": "Zia"}}).encode())
    png2 = b"\x89PNG\r\n\x1a\n" + chunk(b"iTXt", b"chara\x00\x01\x00\x00\x00" + zlib.compress(good)) + chunk(b"IEND", b"")
    assert C.get(C.import_any(png2))["name"] == "Zia"


def test_thinking_level_fallback(nb):
    tk, P = nb["thinking_kwargs"], nb["PRESETS"]
    gemma = next(p for p in P.values() if p["family"] == "gemma")
    qwen = next(p for p in P.values() if p["family"] == "qwen" and "off" in p["thinking"])
    assert tk(gemma, "high")["enable_thinking"] is True
    assert tk(qwen, "on")["reasoning_effort"] == "high"
    assert tk(qwen, "off")["enable_thinking"] is False


def test_stop_returns_queued_text(engine, nb, fake):
    chat = engine.new_chat("chat", "antrian")
    fake["script"].append({"content": "Lambat sekali. " * 40, "slow": 0.05})
    engine.send(chat, "pertama")
    time.sleep(0.3)
    engine.send(chat, "kedua yang diantrikan")
    engine.stop_now()
    wait_idle(engine, 30)
    assert any("kedua yang diantrikan" in str(p) for p in engine.events.of("compose"))


def test_continued_chat_shows_every_summary(engine, nb):
    chat, _ = _story(nb, engine)
    S = nb["STORE"]
    head = S.chat(chat)["head_id"]
    for i in range(2):
        S.x("INSERT INTO summaries (chat_id, node_id, from_id, level, text, core, created) VALUES (?, ?, ?, 'chunk', ?, '', ?)",
            (chat, head, head, f"## Inti\nRingkasan {i}", time.time()))
    new = engine.continue_in_new_chat(chat)
    sums = [i for i in engine.display(new)["items"] if i["kind"] == "summary"]
    assert len(sums) == 2


def test_memory_and_story_book_follow_the_branch(engine, nb, fake):
    chat, _ = _story(nb, engine)
    S, M, ST = nb["STORE"], nb["MEM"], nb["STORIES"]
    engine.send(chat, "Aku duduk.")
    wait_idle(engine)
    first = S.chat(chat)["head_id"]
    sid = S.chat(chat)["story_id"]
    fake["script"] += [{"tool_calls": [{"name": "memory_save", "arguments": json.dumps({"text": "Lotte menyembunyikan surat merah", "scope": "story"})},
                                       {"name": "canon_set", "arguments": json.dumps({"section": "Rahasia", "text": "Surat merah di laci"})}]},
                       {"content": "Lotte menyimpan sesuatu."}]
    engine.reroll(chat, first)  # second answer on a sibling branch writes the memory and the story book
    wait_idle(engine)
    ctx = M.ctx_of(chat)
    assert any("surat merah" in r["text"] for r in M.search("surat merah Lotte", ctx, kinds=("fact",)))
    assert "Surat merah" in ST.canon_text(sid, visible=S.visible_ids(chat))
    engine.swipe(chat, S.chat(chat)["head_id"], -1)  # back to the first answer: none of it happened here
    ctx = M.ctx_of(chat)
    assert not any("surat merah" in r["text"] for r in M.search("surat merah Lotte", ctx, kinds=("fact",)))
    assert "Surat merah" not in ST.canon_text(sid, visible=S.visible_ids(chat))
    # a second chat of the same story does not see it either; a continued chat does
    other = engine.new_chat("rp", "jalan lain", sid)
    assert "Surat merah" not in ST.canon_text(sid, visible=S.visible_ids(other))
    engine.swipe(chat, S.chat(chat)["head_id"], 1)
    cont = engine.continue_in_new_chat(chat)
    assert "Surat merah" in ST.canon_text(sid, visible=S.visible_ids(cont))
    assert any("surat merah" in r["text"] for r in M.search("surat merah Lotte", M.ctx_of(cont), kinds=("fact",)))


def test_memory_forget_and_update_on_a_branch(engine, nb):
    chat, _ = _story(nb, engine)
    S, M = nb["STORE"], nb["MEM"]
    engine.send(chat, "Satu.")
    wait_idle(engine)
    a = S.chat(chat)["head_id"]
    ctx = M.ctx_of(chat)
    mid = M.save("Kunci gudang ada di bawah pot", "story", ctx, message_id=a)["saved"]
    engine.send(chat, "Dua.")
    wait_idle(engine)
    b = S.chat(chat)["head_id"]
    M.update(mid, "Kunci gudang dipindah ke saku Lotte", M.ctx_of(chat), message_id=b)
    assert M.search("kunci gudang", M.ctx_of(chat))[0]["text"].startswith("Kunci gudang dipindah")
    S.set_head(chat, a)  # before the update: the old text
    assert M.search("kunci gudang", M.ctx_of(chat))[0]["text"].startswith("Kunci gudang ada")
    S.set_head(chat, b)
    M.forget(mid, M.ctx_of(chat), message_id=b)
    assert not M.search("kunci gudang", M.ctx_of(chat))
    S.set_head(chat, a)
    assert M.search("kunci gudang", M.ctx_of(chat))


def test_character_memory_tell_and_presence(engine, nb, fake):
    chat, _ = _story(nb, engine)
    S, T, K, P = nb["STORE"], nb["TOOLS"], nb["KNOW"], nb["PROMPT"]
    C = nb["CARDS"]
    sid = S.chat(chat)["story_id"]
    otto = C.save(None, "character", {"name": "Otto Kranz", "aliases": ["Otto"]})
    nb["STORIES"].attach(sid, otto, "character")
    engine.send(chat, "Halo.")
    wait_idle(engine)
    head = S.chat(chat)["head_id"]
    T.call(chat, head, "tell", json.dumps({"from": "Lotte", "to": ["Otto"], "text": "Pemilik flat akan menaikkan sewa",
                                           "truthful": False}))
    T.call(chat, head, "world_event", json.dumps({"text": "Lotte melihat pemain mengambil kunci", "known_to": ["Lotte", "player"]}))
    T.call(chat, head, "knowledge_add", json.dumps({"who": ["Raka"], "text": "Lotte punya adik di Hamburg", "source": "diberi tahu",
                                                   "from": "Lotte"}))
    otto_k = K.of(chat, "Otto Kranz")
    assert otto_k and otto_k[0]["truth"] == "keliru" and otto_k[0]["source_who"] == "Lotte Braun"
    assert any("kunci" in r["text"] for r in K.of(chat, "Lotte Braun"))
    assert any("Hamburg" in r["text"] for r in K.of(chat, "player"))  # the persona's name is the player
    # presence comes from location, not from being named
    W = nb["WORLD"]
    W.status_update(chat, head, "player", {"location": "Dapur"})
    W.status_update(chat, head, "Otto Kranz", {"location": "Dapur"})
    W.status_update(chat, head, "Lotte Braun", {"location": "Kamar Lotte"})
    path = S.path(chat)
    note, _ = P.ephemeral(chat, path, "Aku membuka kulkas.")
    assert "Tokoh di adegan, Otto Kranz" in note and "Tokoh di adegan, Lotte Braun" not in note
    assert "KELIRU" in note and "menaikkan sewa" in note
    assert "Ingatan tokoh pemain (Raka)" in note
    # another branch knows none of it
    S.set_head(chat, path[0]["id"])
    assert not K.of(chat, "Otto Kranz")


def test_secret_lore_is_labelled(engine, nb):
    chat, _ = _story(nb, engine)
    S, C, P = nb["STORE"], nb["CARDS"], nb["PROMPT"]
    world = nb["STORIES"].cards_of(S.chat(chat)["story_id"])["world"]["id"]
    C.lore_save(world, "Identitas Lotte", "Lotte sebenarnya agen", "agen", "rahasia", known_to="Lotte, Otto")
    note, _ = P.ephemeral(chat, S.path(chat), "Apa kamu agen?")
    assert "RAHASIA, hanya diketahui: Lotte, Otto" in note


def test_state_check_fills_in_what_the_model_forgot(engine, nb, fake, monkeypatch):
    monkeypatch.setenv("QCHAT_STATE_CHECK", "1")
    chat, _ = _story(nb, engine)
    S, W, K = nb["STORE"], nb["WORLD"], nb["KNOW"]
    S.chat_settings(chat, length="pendek")  # no paragraph fill-in request between the turn and the check
    t0 = W.state(chat, S.path_ids(chat))["time"]
    fake["script"] += [
        {"content": "Lotte menyodorkan roti. Kamu makan dengan lahap, lalu Lotte berbisik bahwa kunci gudang hilang."},
        {"tool_calls": [{"name": "status_update", "arguments": json.dumps({"subject": "player", "changes": {"lapar": -30}})},
                        {"name": "knowledge_add", "arguments": json.dumps({"who": ["player"], "text": "Kunci gudang hilang",
                                                                           "source": "diberi tahu", "from": "Lotte"})}]},
        {"content": "selesai"}]
    engine.send(chat, "Aku duduk di meja.")
    wait_idle(engine, 60)
    st = W.state(chat, S.path_ids(chat))
    assert next(s for s in st["stats"] if s["key"] == "lapar")["value"] < 20  # 20 start, minus 30, clamped at 0
    assert any("Kunci gudang" in r["text"] for r in K.of(chat, "player"))
    assert st["time"] > t0  # no world_advance in the turn: time moved by an estimate
    log = S.side_logs(chat, "state_check")[0]["data"]
    assert any(r.startswith("world_advance: perkiraan") for r in log["recorded"])


def test_schema_v2_fields(nb):
    C = nb["CARDS"]
    keys = lambda t: {f["key"] for f in C.schema(t)["fields"]}
    assert {"schedule", "skill_levels"} <= keys("character") and "skill_levels" in keys("persona")
    assert "locations" in keys("world") and {"state_check", "continuity_check"} <= keys("gm") and "keadaan" in keys("status")


def test_panel_shows_only_what_the_player_sees(engine, nb):
    chat, _ = _story(nb, engine, fmt="game")
    S, W = nb["STORE"], nb["WORLD"]
    head = S.chat(chat)["head_id"]
    W.status_update(chat, head, "player", {"location": "Dapur"})
    W.status_update(chat, head, "Lotte Braun", {"location": "Dapur", "mood": "gugup", "plan_now": "Kabur malam ini",
                                                 "knows": ["surat merah"]})
    W.status_update(chat, head, "Otto", {"location": "Stasiun", "mood": "marah"})
    p = engine.panels(chat)
    assert p["characters"]["Lotte Braun"] == {"mood": "gugup"}
    assert "Otto" not in p["characters"] and not p["characters_gm"]
    S.chat_settings(chat, gm_view=True)
    p = engine.panels(chat)
    assert p["characters_gm"]["Lotte Braun"]["plan_now"] == "Kabur malam ini" and "Otto" in p["characters_gm"]


def test_continuity_check_flags_and_strict_rewrites(engine, nb, fake):
    chat, _ = _story(nb, engine)
    S, W, K, C = nb["STORE"], nb["WORLD"], nb["KNOW"], nb["CARDS"]
    S.chat_settings(chat, length="pendek")
    engine.send(chat, "Halo.")
    wait_idle(engine)
    head = S.chat(chat)["head_id"]
    W.status_update(chat, head, "player", {"location": "Dapur"})
    W.status_update(chat, head, "Lotte Braun", {"location": "Dapur"})
    K.add(chat, head, ["Lotte Braun"], "Raka suka kopi hitam")
    W.roll(chat, head, "membuka pintu macet", 0.3)
    data, _ = engine.continuity_data(chat, head)
    assert "Lotte Braun: lokasi Dapur" in data and "Raka suka kopi hitam" in data
    # background mode only queues the job
    engine.continuity_jobs.clear()
    fake["script"].append({"content": "Lotte bilang kamu dulu tinggal di Wina."})
    engine.send(chat, "Lotte, ingat aku?")
    wait_idle(engine)
    assert engine.continuity_jobs
    mid = engine.continuity_jobs.pop(0)[1]
    fake["script"].append({"content": json.dumps({"issues": [{"kind": "pengetahuan", "who": "Lotte Braun",
                                                              "text": "tahu soal Wina", "fix": "Lotte tidak tahu"}]})})
    issues = engine._continuity_check(chat, mid, True)
    assert issues and issues[0]["kind"] == "pengetahuan"
    item = engine.display(chat)["items"][-1]
    assert item["continuity"][0]["who"] == "Lotte Braun"
    # strict mode writes the turn again with the correction
    gm = nb["STORIES"].cards_of(S.chat(chat)["story_id"])["gm"]
    C.set_field(gm["id"], "continuity_check", "ketat")
    nb["STORIES"].refresh_versions(S.chat(chat)["story_id"])
    fake["script"] += [{"content": "Lotte bilang kamu dulu tinggal di Wina."},
                       {"content": json.dumps({"issues": [{"kind": "pengetahuan", "who": "Lotte Braun", "text": "Wina",
                                                           "fix": "tidak tahu"}]})},
                       {"content": "Lotte menatapmu, mencoba mengingat."}]
    engine.send(chat, "Kita pernah bertemu?")
    wait_idle(engine, 60)
    last = engine.display(chat)["items"][-1]
    assert last["content"].startswith("Lotte menatapmu") and last["swipe"] == [2, 2]


def test_story_threads_with_deadlines(engine, nb, fake):
    chat, _ = _story(nb, engine)
    S, T, P, TH = nb["STORE"], nb["TOOLS"], nb["PROMPT"], nb["THREADS"]
    engine.send(chat, "Halo.")
    wait_idle(engine)
    head = S.chat(chat)["head_id"]
    res, failed, _ = T.call(chat, head, "thread_open", json.dumps(
        {"kind": "janji temu", "title": "Bertemu Lotte di Odeonsplatz", "who": ["Lotte"], "due": "19 Desember 2026, 21:30"}))
    assert not failed, res
    tid = json.loads(res)["opened"]
    T.call(chat, head, "thread_open", json.dumps({"kind": "utang", "title": "Utang 20 euro ke Otto"}))
    note, _ = P.ephemeral(chat, S.path(chat), "Aku menunggu.")
    assert "Benang cerita terbuka" in note and "Bertemu Lotte di Odeonsplatz" in note and "Lotte Braun" in note
    nb["WORLD"].advance(chat, head, 120, "uji")
    rows = TH.list(chat, now=nb["WORLD"].state(chat, S.path_ids(chat))["time"])
    assert rows[0]["id"] == tid and rows[0]["overdue"]
    note, _ = P.ephemeral(chat, S.path(chat), "Aku menunggu.")
    assert "LEWAT TENGGAT" in note
    res, failed, _ = T.call(chat, head, "thread_close", json.dumps({"id": tid, "status": "gagal", "note": "tidak datang"}))
    assert not failed
    assert all(r["id"] != tid for r in TH.list(chat))
    # the world tick sees overdue threads
    tid2 = TH.open(chat, head, "janji temu", "Makan malam dengan Otto", due="2026-12-19 22:00")
    n0 = len(fake["log"])
    t0 = nb["WORLD"].state(chat, S.path_ids(chat))["time"]
    engine._tick(chat, t0, 240, "uji")
    sent = json.dumps(fake["log"][n0]["messages"][-1], ensure_ascii=False)
    assert "Makan malam dengan Otto" in sent and "lewat tenggat" in sent
    # another branch does not have these threads
    S.set_head(chat, S.path(chat)[0]["id"])
    assert all(r["id"] not in (tid, tid2) for r in TH.list(chat, include_closed=True))


def test_dice_from_skill_and_condition(engine, nb):
    chat, _ = _story(nb, engine)
    S, T, C, W = nb["STORE"], nb["TOOLS"], nb["CARDS"], nb["WORLD"]
    cards = nb["STORIES"].cards_of(S.chat(chat)["story_id"])
    C.set_field(cards["persona"]["id"], "skill_levels", [["Bahasa Jerman", "55"], ["Memasak", "80"]])
    C.set_field(cards["character"][0]["id"], "skill_levels", "Berbohong, 70")
    nb["STORIES"].refresh_versions(S.chat(chat)["story_id"])
    p, why = T.roll_odds(chat, "player", "bahasa jerman", "sulit")
    assert abs(p - 0.35) < 1e-9 and why[0].startswith("Bahasa Jerman")
    p, _ = T.roll_odds(chat, "Lotte", "Berbohong", "mudah")
    assert abs(p - 0.9) < 1e-9
    p, why = T.roll_odds(chat, "player", "Panjat tebing", "sedang")
    assert abs(p - 0.4) < 1e-9 and "tidak terlatih" in why[0]
    head = S.chat(chat)["head_id"]
    W.status_update(chat, head, "player", {"injuries": {"add": "pergelangan terkilir"}, "energi": {"set": 10}})
    p, why = T.roll_odds(chat, "player", "Memasak", "sedang")
    assert abs(p - (0.8 - 0.05 - 0.15)) < 1e-9 and any("luka" in w for w in why)
    W.status_update(chat, head, "Lotte Braun", {"keadaan": "pingsan"})
    assert T.roll_odds(chat, "Lotte", "Berbohong")[0] == 0.0
    res, failed, _ = T.call(chat, head, "roll", json.dumps({"event": "membujuk", "skill": "Bahasa Jerman", "difficulty": "sedang"}))
    assert not failed and "peluang" in json.loads(res)["result"]


def test_schedule_travel_and_healing(engine, nb, fake, monkeypatch):
    chat, _ = _story(nb, engine)
    S, W, C, P = nb["STORE"], nb["WORLD"], nb["CARDS"], nb["PROMPT"]
    sid = S.chat(chat)["story_id"]
    cards = nb["STORIES"].cards_of(sid)
    lotte = cards["character"][0]["id"]
    C.set_field(lotte, "schedule", [["20-23", "Dapur", "memasak"], ["23-07", "Kamar Lotte", "tidur"]])
    C.set_field(cards["world"]["id"], "locations", "Dapur, Stasiun, 25")
    nb["STORIES"].refresh_versions(sid)
    head = S.chat(chat)["head_id"]  # world clock starts 2026-12-19 21:00
    W.status_update(chat, head, "player", {"location": "Dapur"})
    st = W.state(chat, S.path_ids(chat))
    where = W.with_schedule(st, nb["STORIES"].cards_of(sid))
    assert where["Lotte Braun"]["location"] == "Dapur" and where["Lotte Braun"]["location_from"] == "jadwal"
    note, _ = P.ephemeral(chat, S.path(chat), "Halo.")
    assert "Tokoh di adegan, Lotte Braun" in note and "Waktu tempuh dari Dapur: Stasiun 25 menit" in note
    # a sighting is newer than the schedule
    W.status_update(chat, head, "Lotte Braun", {"location": "Balkon"})
    st = W.state(chat, S.path_ids(chat))
    assert W.with_schedule(st, nb["STORIES"].cards_of(sid))["Lotte Braun"]["location"] == "Balkon"
    assert W.travel_minutes(nb["STORIES"].cards_of(sid), "stasiun", "dapur") == 25
    # a trip without world_advance moves the clock by the travel time
    monkeypatch.setenv("QCHAT_STATE_CHECK", "1")
    S.chat_settings(chat, length="pendek")
    t0 = W.state(chat, S.path_ids(chat))["time"]
    fake["script"] += [{"tool_calls": [{"name": "status_update", "arguments": json.dumps({"subject": "player",
                                                                                          "changes": {"location": "Stasiun"}})}]},
                       {"content": "Kamu berjalan ke stasiun."}, {"content": "selesai"}]
    engine.send(chat, "Aku pergi ke stasiun.")
    wait_idle(engine, 60)
    t1 = W.state(chat, S.path_ids(chat))["time"]
    assert (t1 - t0).total_seconds() >= 25 * 60


def test_relationships_and_card_proposals(engine, nb, fake):
    chat, _ = _story(nb, engine, fmt="game")
    S, T, P = nb["STORE"], nb["TOOLS"], nb["PROMPT"]
    engine.send(chat, "Halo.")
    wait_idle(engine)
    head = S.chat(chat)["head_id"]
    T.call(chat, head, "relationship", json.dumps({"a": "Lotte", "b": "player", "delta": 12, "reason": "dibantu membawa belanjaan"}))
    T.call(chat, head, "relationship", json.dumps({"a": "Lotte", "b": "Raka", "delta": 15, "reason": "ditolong saat jatuh"}))
    sc = nb["RELATIONS"].scores(chat)[("Lotte Braun", "player")]
    assert sc["score"] == 27 and sc["last"] == "ditolong saat jatuh"
    assert engine.panels(chat)["relations"][0]["word"] == "dekat"
    nb["WORLD"].status_update(chat, head, "player", {"location": "Dapur"})
    nb["WORLD"].status_update(chat, head, "Lotte Braun", {"location": "Dapur"})
    note, _ = P.ephemeral(chat, S.path(chat), "Halo.")
    assert "ke pemain dekat (+27" in note
    fake["script"].append({"content": json.dumps({"proposals": [
        {"card": "Lotte", "field": "relations", "value": [["Raka", "teman dekat", "sejak insiden tangga"]], "reason": "makin akrab"},
        {"card": "Nobody", "field": "age", "value": "30"}]})})
    pids = engine.propose_cards(chat)
    assert len(pids) == 1
    rows = engine.proposals(chat)
    assert rows[0]["card_name"] == "Lotte Braun" and rows[0]["status"] == "menunggu"
    assert engine.decide_proposal(chat, pids[0], True)
    lotte = nb["STORIES"].cards_of(S.chat(chat)["story_id"], latest=True)["character"][0]
    assert lotte["data"]["relations"][0][0] == "Raka"


def test_delete_chat_removes_tahap8_rows(engine, nb):
    chat, _ = _story(nb, engine)
    S = nb["STORE"]
    engine.send(chat, "Halo.")
    wait_idle(engine)
    head = S.chat(chat)["head_id"]
    nb["KNOW"].add(chat, head, ["Lotte Braun"], "Sesuatu")
    tid = nb["THREADS"].open(chat, head, "utang", "Utang")
    nb["THREADS"].close(chat, head, tid, "selesai")
    nb["RELATIONS"].change(chat, head, "Lotte Braun", "player", 5, "baik")
    nb["STORIES"].canon_set(S.chat(chat)["story_id"], "Bagian", "isi", chat, message_id=head)
    S.delete_chat(chat)
    for table in ("knowledge", "threads", "relations_log", "canon_log", "card_proposals"):
        assert not S.q(f"SELECT 1 AS x FROM {table} WHERE chat_id = ?", (chat,)), table
    assert not S.q("SELECT 1 AS x FROM thread_events WHERE thread_id = ?", (tid,))


def test_continue_on_an_older_turn_branches(engine, nb, fake):
    chat = engine.new_chat("chat", "lanjut lama")
    S = nb["STORE"]
    fake["script"].append({"content": "Jawaban pertama."})
    engine.send(chat, "Satu")
    wait_idle(engine)
    first = S.chat(chat)["head_id"]
    engine.send(chat, "Dua")
    wait_idle(engine)
    later = S.chat(chat)["head_id"]
    fake["script"].append({"content": "lalu tambahan."})
    engine.continue_msg(chat, first)
    wait_idle(engine)
    assert S.msg(first)["content"] == "Jawaban pertama."  # the old branch is untouched
    head = S.chat(chat)["head_id"]
    assert head != first and S.msg(head)["content"].startswith("Jawaban pertama.") and "tambahan" in S.msg(head)["content"]
    assert later in S.path_ids(chat, later)


def test_message_metadata_and_quant(nb, engine):
    q = nb["quant_of"]
    P = nb["PRESETS"]
    assert q(P["Dark-Gemistry 31B FP8 (W8A16) · vLLM"]) in ("W8A16", "FP8")
    assert q(next(p for n, p in P.items() if "Q8_0" in n)) == "Q8_0"
    chat = engine.new_chat("chat", "meta")
    engine.send(chat, "Halo")
    wait_idle(engine)
    stats = nb["STORE"].msg(nb["STORE"].chat(chat)["head_id"])["meta"]["stats"]
    assert "quant" in stats and "yarn" in stats and "seed" in stats
