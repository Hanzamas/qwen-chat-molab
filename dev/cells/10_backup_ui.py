bk_token = mo.ui.text(kind="password", label="Hugging Face token (write; ideally fine-grained to the backup repo only)",
                      full_width=True)
_bk_last = STORE.meta_get("backup", {}) or {}
_bk_choices = {"5 minutes": 300, "10 minutes": 600, "30 minutes": 1800}
bk_repo = mo.ui.text(value=_bk_last.get("repo", ""), label="Private dataset repo (empty = <username>/qwen-chat-backup)",
                     full_width=True)
bk_interval = mo.ui.dropdown(options=_bk_choices, label="Automatic backup every",
                             value=next((k for k, v in _bk_choices.items() if v == _bk_last.get("interval")), "10 minutes"))
bk_now = mo.ui.run_button(label="Back up now")
bk_restore = mo.ui.run_button(label="Restore latest", kind="danger")
mo.accordion({"Backup to Hugging Face": mo.vstack([
    mo.md("The token stays in kernel memory only and is never written to the database, disk, or backup file. "
          "If it is empty, the token from the **Model server** panel (env `HF_TOKEN`) is used; that token needs write "
          "access. The repo is created **private**."),
    bk_token, mo.hstack([bk_repo, bk_interval], widths=[3, 1]), mo.hstack([bk_now, bk_restore], justify="start"),
])})
