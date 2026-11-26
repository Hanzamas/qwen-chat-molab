"""Second review round: data integrity across branches, deletes and continued chats."""
import json

from conftest import wait_idle
from test_core import _story


def _turn(engine, nb, chat, text="Halo."):
    engine.send(chat, text)
    wait_idle(engine)
    return nb["STORE"].chat(chat)["head_id"]


def test_message_ids_are_never_reused(engine, nb):
    S = nb["STORE"]
    chat = engine.new_chat("chat", "ids")
    a = S.add_message(chat, None, "user", "satu")
    b = S.add_message(chat, a, "assistant", "dua")
    engine.delete_msg(chat, b)
    c = S.add_message(chat, a, "assistant", "tiga")
    assert c > b
    other = engine.new_chat("chat", "x")
    S.delete_chat(other)
    assert engine.new_chat("chat", "y") > other


def test_deleting_a_turn_takes_its_effects(engine, nb):
    chat, _ = _story(nb, engine)
    S, K, TH, R, ST, M = nb["STORE"], nb["KNOW"], nb["THREADS"], nb["RELATIONS"], nb["STORIES"], nb["MEM"]
    head = _turn(engine, nb, chat)
    sid = S.chat(chat)["story_id"]
    K.add(chat, head, ["Lotte Braun"], "Lotte tahu kunci cadangan ada di pot bunga")
    TH.open(chat, head, "janji", "Mengembalikan buku Lotte")
    R.change(chat, head, "Lotte Braun", "player", 20, "dibantu")
    ST.canon_set(sid, "Rahasia", "Lotte pernah tinggal di Hamburg", chat, message_id=head)
    mid = M.save("Lotte suka teh melati", "story", M.ctx_of(chat), message_id=head)["saved"]
    engine.delete_msg(chat, head)
    for table in ("knowledge", "threads", "relations_log", "canon_log", "memories"):
        assert not S.q(f"SELECT 1 AS x FROM {table} WHERE message_id = ?", (head,)), table
    assert mid  # saved before the delete


def test_continued_chat_stands_on_its_own(engine, nb):
    chat, _ = _story(nb, engine)
    S, K, TH, R, ST, M = nb["STORE"], nb["KNOW"], nb["THREADS"], nb["RELATIONS"], nb["STORIES"], nb["MEM"]
    head = _turn(engine, nb, chat)
    sid = S.chat(chat)["story_id"]
    K.add(chat, head, ["Lotte Braun"], "Lotte tahu Raka takut gelap")
    TH.open(chat, head, "janji", "Mengantar Lotte ke stasiun")
    R.change(chat, head, "Lotte Braun", "player", 15, "ditolong")
    ST.canon_set(sid, "Kota", "Hujan tidak berhenti sejak Senin", chat, message_id=head)
    M.save("Raka berutang 20 euro ke Lotte", "story", M.ctx_of(chat), message_id=head)
    new = engine.continue_in_new_chat(chat)
    S.delete_chat(chat)
    assert any("takut gelap" in r["text"] for r in K.of(new, "Lotte Braun"))
    assert any(t["title"] == "Mengantar Lotte ke stasiun" for t in TH.list(new))
    assert R.scores(new)[("Lotte Braun", "player")]["score"] == 15
    assert ST.canon(sid, S.visible_ids(new), new).get("Kota") == "Hujan tidak berhenti sejak Senin"
    assert "20 euro" in json.dumps(M.search("utang euro Lotte", M.ctx_of(new), limit=8))
    # another chat of the same story sees none of it
    other = engine.new_chat("rp", "lain", sid)
    assert "Kota" not in ST.canon(sid, S.visible_ids(other), other)
    assert not K.of(other, "Lotte Braun")


def test_manual_edits_survive_a_reroll(engine, nb):
    chat, _ = _story(nb, engine)
    S, K, TH, ST = nb["STORE"], nb["KNOW"], nb["THREADS"], nb["STORIES"]
    head = _turn(engine, nb, chat)
    sid = S.chat(chat)["story_id"]
    K.add(chat, None, ["Lotte Braun"], "Lotte tahu nomor telepon Raka")
    tid = TH.open(chat, None, "misteri", "Siapa yang mengetuk")
    ST.canon_set(sid, "Catatan", "Ditulis tangan", chat, chat_wide=True)
    parent = S.msg(head)["parent_id"]
    S.set_head(chat, parent)  # a reroll moves the head off the old reply
    assert any("nomor telepon" in r["text"] for r in K.of(chat, "Lotte Braun"))
    assert any(t["id"] == tid for t in TH.list(chat))
    assert ST.canon(sid, S.visible_ids(chat), chat).get("Catatan") == "Ditulis tangan"
    other = engine.new_chat("rp", "lain", sid)
    assert "Catatan" not in ST.canon(sid, S.visible_ids(other), other)


def test_pending_notes_follow_the_branch(engine, nb):
    chat, _ = _story(nb, engine)
    S, ST = nb["STORE"], nb["STORIES"]
    head = _turn(engine, nb, chat)
    sid = S.chat(chat)["story_id"]
    ST.canon_set(sid, "Musim", "Salju turun", chat, message_id=head)
    assert any("Salju turun" in p["text"] for p in ST.pending_list(sid, chat))
    S.set_head(chat, S.msg(head)["parent_id"])
    assert not any("Salju turun" in p["text"] for p in ST.pending_list(sid, chat))
    other = engine.new_chat("rp", "lain", sid)
    assert not any("Salju turun" in p["text"] for p in ST.pending_list(sid, other))


def test_memory_forget_and_update_per_branch(engine, nb):
    chat, _ = _story(nb, engine)
    S, M = nb["STORE"], nb["MEM"]
    root = S.add_message(chat, S.chat(chat)["head_id"], "user", "a")
    b1 = S.add_message(chat, root, "assistant", "cabang satu")
    b2 = S.add_message(chat, root, "assistant", "cabang dua")
    mid = M.save("Kunci ada di laci meja", "story", M.ctx_of(chat))["saved"]
    S.set_head(chat, b1)
    M.forget(mid, M.ctx_of(chat), message_id=b1)
    S.set_head(chat, b2)
    M.forget(mid, M.ctx_of(chat), message_id=b2)
    for head in (b1, b2):
        S.set_head(chat, head)
        assert not M._resolve([S.one("SELECT * FROM memories WHERE id = ?", (mid,))], M.ctx_of(chat))
    S.set_head(chat, root)
    assert M._resolve([S.one("SELECT * FROM memories WHERE id = ?", (mid,))], M.ctx_of(chat))
    # updates replay in order on their own branch
    m3 = M.save("Pintu belakang terkunci", "story", M.ctx_of(chat))["saved"]
    S.set_head(chat, b1)
    M.update(m3, "Pintu belakang terbuka", M.ctx_of(chat), message_id=b1)
    S.set_head(chat, b2)
    M.update(m3, "Pintu belakang dirusak", M.ctx_of(chat), message_id=b2)
    S.set_head(chat, b1)
    assert M._resolve([S.one("SELECT * FROM memories WHERE id = ?", (m3,))], M.ctx_of(chat))[0]["text"] == "Pintu belakang terbuka"
    S.set_head(chat, b2)
    assert M._resolve([S.one("SELECT * FROM memories WHERE id = ?", (m3,))], M.ctx_of(chat))[0]["text"] == "Pintu belakang dirusak"
    S.set_head(chat, root)
    assert M._resolve([S.one("SELECT * FROM memories WHERE id = ?", (m3,))], M.ctx_of(chat))[0]["text"] == "Pintu belakang terkunci"


def test_schedule_hours_with_dots_and_held_characters(nb):
    W = nb["WORLD"]
    assert W._hour_in("08.00-12.00", 9) and not W._hour_in("08.00-12.00", 13)


def test_card_delete_and_orphan_proposal(engine, nb):
    chat, _ = _story(nb, engine)
    S, C = nb["STORE"], nb["CARDS"]
    otto = C.save(None, "character", {"name": "Otto"})
    pid = S.x("INSERT INTO card_proposals (chat_id, card_id, field, value, reason, created) VALUES (?, ?, 'backstory', '\"x\"', '', 0)",
              (chat, otto))
    S.x("INSERT INTO card_proposals (chat_id, card_id, field, value, reason, created) VALUES (?, 999999, 'backstory', '\"x\"', '', 0)",
        (chat,))
    orphan = S.one("SELECT MAX(id) AS id FROM card_proposals")["id"]
    assert engine.decide_proposal(chat, orphan, True) is False
    assert S.one("SELECT status FROM card_proposals WHERE id = ?", (orphan,))["status"] == "ditolak"
    C.delete(otto)
    assert not S.q("SELECT 1 AS x FROM card_proposals WHERE id = ?", (pid,))


def test_continue_copy_keeps_the_turns_effects(engine, nb):
    chat, _ = _story(nb, engine)
    S, K = nb["STORE"], nb["KNOW"]
    head = _turn(engine, nb, chat)
    K.add(chat, head, ["Lotte Braun"], "Lotte melihat surat di meja")
    S.add_message(chat, head, "user", "lanjut")  # a later turn hangs on it, so Continue makes a copy
    copy = S.add_message(chat, S.msg(head)["parent_id"], "assistant", S.msg(head)["content"])
    S.clone_effects(head, copy)
    S.set_head(chat, copy)
    assert any("surat di meja" in r["text"] for r in K.of(chat, "Lotte Braun"))


def test_embedder_failed_batch_is_not_stuck(nb):
    EMB = nb["EMB"]
    with EMB.qlock:
        EMB.pending[("mem", 123456)] = "teks"
        EMB._settle([(("mem", 123456), "teks")])
    assert ("mem", 123456) not in EMB.pending
    with EMB.qlock:
        EMB.pending[("mem", 123457)] = "baru"
        EMB._settle([(("mem", 123457), "lama")])  # changed while embedding: queued again
        assert ("mem", 123457) in EMB.queue
        EMB.queue.remove(("mem", 123457))
        EMB.pending.pop(("mem", 123457))
