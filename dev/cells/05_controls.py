# Last used server settings are stored in the database, so a restored backup starts with them selected.
_last = STORE.meta_get("server", {}) or {}
_ctx_label = next((k for k, v in CTX_CHOICES.items() if v == _last.get("ctx")), "512K (YaRN)")
ctl_preset = mo.ui.dropdown(options=list(PRESETS), value=_last.get("preset") if _last.get("preset") in PRESETS else next(iter(PRESETS)),
                            label="Model", full_width=True)
ctl_ctx = mo.ui.dropdown(options=CTX_CHOICES, value=_ctx_label, label="Konteks")
ctl_mtp = mo.ui.switch(value=_last.get("mtp", True), label="MTP (lebih cepat)")
ctl_embed = mo.ui.switch(value=_last.get("embed", True), label="Embedder (pencarian memory lebih pintar)")
ctl_install = mo.ui.run_button(label="Install")
ctl_start = mo.ui.run_button(label="Start", kind="success")
ctl_stop = mo.ui.run_button(label="Stop", kind="danger")
mo.vstack([
    mo.md("### Server model"),
    ctl_preset,
    mo.hstack([ctl_ctx, ctl_mtp, ctl_embed], justify="start", align="center", gap=2),
    mo.hstack([ctl_install, ctl_start, ctl_stop], justify="start"),
])
