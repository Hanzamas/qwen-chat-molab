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
