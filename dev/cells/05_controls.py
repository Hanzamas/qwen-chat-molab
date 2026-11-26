# Last used server settings are stored in the database, so a restored backup starts with them selected.
_last = STORE.meta_get("server", {}) or {}
_ctx_label = next((k for k, v in CTX_CHOICES.items() if v == _last.get("ctx")), "512K (YaRN)")
ctl_preset = mo.ui.dropdown(options=list(PRESETS), value=_last.get("preset") if _last.get("preset") in PRESETS else next(iter(PRESETS)),
                            label="Model", full_width=True)
ctl_ctx = mo.ui.dropdown(options=CTX_CHOICES, value=_ctx_label, label="Konteks")
ctl_mtp = mo.ui.switch(value=_last.get("mtp", True), label="MTP (lebih cepat)")
ctl_embed = mo.ui.switch(value=_last.get("embed", True), label="Embedder (pencarian memory lebih pintar)")
ctl_embed_model = mo.ui.dropdown(options=list(EMBEDDERS), value=_last.get("embed_model") if _last.get("embed_model") in EMBEDDERS
                                 else "0.6B", label="Ukuran embedder")
ctl_hf = mo.ui.text(kind="password", full_width=True,
                     label="Token Hugging Face (opsional; untuk model gated, download lebih cepat, dan backup)")
ctl_install = mo.ui.run_button(label="Install")
ctl_start = mo.ui.run_button(label="Start", kind="success")
ctl_stop = mo.ui.run_button(label="Stop", kind="danger")
mo.vstack([
    mo.md("### Server model"),
    ctl_preset,
    mo.hstack([ctl_ctx, ctl_mtp, ctl_embed, ctl_embed_model], justify="start", align="center", gap=2),
    ctl_hf,
    mo.md("_Token hanya disimpan di memori kernel (env `HF_TOKEN`), tidak ditulis ke database, disk, atau backup._"),
    mo.hstack([ctl_install, ctl_start, ctl_stop], justify="start"),
])
