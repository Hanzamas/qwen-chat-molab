bk_token = mo.ui.text(kind="password", label="Token Hugging Face (write, sebaiknya fine-grained ke repo backup saja)",
                      full_width=True)
_bk_last = STORE.meta_get("backup", {}) or {}
_bk_choices = {"5 menit": 300, "10 menit": 600, "30 menit": 1800}
bk_repo = mo.ui.text(value=_bk_last.get("repo", ""), label="Repo dataset private (kosong = <username>/qwen-chat-backup)",
                     full_width=True)
bk_interval = mo.ui.dropdown(options=_bk_choices, label="Backup otomatis tiap",
                             value=next((k for k, v in _bk_choices.items() if v == _bk_last.get("interval")), "10 menit"))
bk_now = mo.ui.run_button(label="Backup sekarang")
bk_restore = mo.ui.run_button(label="Pulihkan terbaru", kind="danger")
mo.accordion({"Backup ke Hugging Face": mo.vstack([
    mo.md("Token hanya disimpan di memori kernel, tidak pernah ditulis ke database, disk, atau file backup. "
          "Kalau kosong, dipakai token di panel **Server model** (env `HF_TOKEN`); token itu harus punya izin write. "
          "Repo dibuat **private**."),
    bk_token, mo.hstack([bk_repo, bk_interval], widths=[3, 1]), mo.hstack([bk_now, bk_restore], justify="start"),
])})
