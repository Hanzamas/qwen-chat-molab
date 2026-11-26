bk_token = mo.ui.text(kind="password", label="Token Hugging Face (write, sebaiknya fine-grained ke repo backup saja)",
                      full_width=True)
bk_repo = mo.ui.text(label="Repo dataset private (kosong = <username>/qwen-chat-backup)", full_width=True)
bk_interval = mo.ui.dropdown(options={"5 menit": 300, "10 menit": 600, "30 menit": 1800}, value="10 menit",
                             label="Backup otomatis tiap")
bk_now = mo.ui.run_button(label="Backup sekarang")
bk_restore = mo.ui.run_button(label="Pulihkan terbaru", kind="danger")
mo.accordion({"Backup ke Hugging Face": mo.vstack([
    mo.md("Token hanya disimpan di memori kernel, tidak pernah ditulis ke database, disk, atau file backup. "
          "Kalau kosong, dipakai env `HF_TOKEN`. Repo dibuat **private**."),
    bk_token, mo.hstack([bk_repo, bk_interval], widths=[3, 1]), mo.hstack([bk_now, bk_restore], justify="start"),
])})
