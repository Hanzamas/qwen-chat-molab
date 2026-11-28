"""Broken replies: leaked tool text, runaway repetition, rollback, tool caps, doubled narration."""
import json

from conftest import wait_idle
from test_core import _story

STORY = ("Lena berjalan mendekat dengan langkah presisi, buku catatannya didekap di dada. Dia berhenti di depan mejamu "
         "dan menatapmu sebentar sebelum bicara.\n\n"
         "Lotte muncul tepat di belakangnya dengan thermos teh herbal di satu tangan. Dia tersenyum tipis dan meletakkan "
         "lembar kerjanya di meja, lalu menunggu siapa yang akan bicara lebih dulu di antara kalian bertiga.")
LEAKED = ('cio:roll{value:<|"|>{"event": "x", "odds": 0.7, "success": true}<|"|>}cio:world_advance{value:<|"|>{"ok": true, '
          '"minutes": 20}<|"|>}cio:memory_forget{id:25}cio:memory_forget{id:26}')


def test_text_checks(nb):
    T = nb["TXT"]
    assert T.runaway("cio:memory_forget{id:%d}" % 1 + "".join(f"cio:memory_forget{{id:{i}}}" for i in range(2, 40)))
    assert T.runaway("Sie kam herein. " + "Lotte " * 30)
    assert not T.runaway(STORY) and not T.runaway("Dia diam saja" + "." * 40)
    assert T.leaked_tools(LEAKED) and not T.leaked_tools(STORY)
    assert T.strip_leaks(LEAKED + "\n" + STORY) == STORY


def test_leaked_tool_text_is_stripped(engine, nb, fake):
    chat, _ = _story(nb, engine)
    fake["script"].append({"content": LEAKED + "\n" + STORY})
    engine.send(chat, "Aku menunggu.")
    wait_idle(engine)
    bot = engine.display(chat)["items"][-1]
    assert bot["content"].startswith("Lena berjalan mendekat") and "cio:" not in bot["content"]


def test_runaway_reply_is_rolled_back_and_written_again(engine, nb, fake):
    chat, _ = _story(nb, engine)
    S = nb["STORE"]
    n = len(fake["log"])
    fake["script"] += [{"content": "Lotte tersenyum. " + "Lotte " * 60, "tool_calls": []}, {"content": STORY}]
    engine.send(chat, "Aku menunggu.")
    wait_idle(engine, 60)
    bot = engine.display(chat)["items"][-1]
    assert bot["content"].startswith("Lena berjalan mendekat") and bot["swipe"] == [2, 2]
    assert any("set aside" in t["text"] for t in engine.events.of("toast"))
    retry = next(b for b in fake["log"][n:] if "Balasan sebelumnya rusak" in json.dumps(b, ensure_ascii=False))
    assert retry["temperature"] <= 0.7 and retry["frequency_penalty"] == 0.4
    assert S.side_logs(chat, "garbled")[0]["data"]["why"] == "runaway"


def test_broken_twice_stops_with_an_error(engine, nb, fake):
    chat, _ = _story(nb, engine)
    fake["script"] += [{"content": "Lotte " * 60}, {"content": "Lena " * 60}]
    engine.send(chat, "Aku menunggu.")
    wait_idle(engine, 60)
    bot = engine.display(chat)["items"][-1]
    assert "broke twice" in (bot.get("error") or "")


def test_tool_call_cap_rolls_back_without_running_them(engine, nb, fake):
    chat, _ = _story(nb, engine)
    S = nb["STORE"]
    forgets = [{"name": "memory_forget", "arguments": json.dumps({"id": i})} for i in range(30)]
    fake["script"] += [{"content": "", "tool_calls": forgets}, {"content": STORY}]
    engine.send(chat, "Aku menunggu.")
    wait_idle(engine, 60)
    assert engine.display(chat)["items"][-1]["content"].startswith("Lena berjalan mendekat")
    assert not [r for r in S.q("SELECT * FROM memory_log WHERE action = 'hide'")
                if r["message_id"] in S.visible_ids(chat)]


def test_recording_calls_after_a_full_narration_end_the_turn(engine, nb, fake):
    chat, _ = _story(nb, engine)
    fake["script"].append({"content": STORY, "tool_calls": [{"name": "world_advance", "arguments": json.dumps({"minutes": 20})}]})
    engine.send(chat, "Aku menunggu.")
    wait_idle(engine)
    bot = engine.display(chat)["items"][-1]
    assert bot["content"].count("Lena berjalan mendekat") == 1 and "Paragraf 1 dimulai" not in bot["content"]
    assert engine.panels(chat)["time"].endswith("21:20")


def test_same_narration_after_a_roll_is_kept_once(engine, nb, fake):
    chat, _ = _story(nb, engine)
    fake["script"] += [{"content": STORY, "tool_calls": [{"name": "roll", "arguments": json.dumps({"event": "x", "odds": 0.5})}]},
                       {"content": STORY + " Lalu dia duduk."}]
    engine.send(chat, "Aku menunggu.")
    wait_idle(engine)
    bot = engine.display(chat)["items"][-1]
    assert bot["content"].count("Lena berjalan mendekat") == 1 and "Lalu dia duduk." in bot["content"]


def test_gemma_runs_at_085_with_mtp(nb):
    spec_safe = nb["LLM"].spec_safe
    assert spec_safe({"temperature": 1.0}, {"preset": {"family": "gemma", "backend": "llama.cpp"}}, True)["temperature"] == 0.85
    assert spec_safe({"temperature": 0.7}, {"preset": {"family": "gemma", "backend": "vllm"}}, True)["temperature"] == 0.7
    assert spec_safe({"temperature": 1.0}, {"preset": {"family": "gemma"}}, False)["temperature"] == 1.0
