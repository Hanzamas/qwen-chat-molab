ctl_preset = mo.ui.dropdown(options=list(PRESETS), value=next(iter(PRESETS)), label="Model", full_width=True)
ctl_ctx = mo.ui.dropdown(options=CTX_CHOICES, value="512K (YaRN)", label="Konteks")
ctl_mtp = mo.ui.switch(value=True, label="MTP (lebih cepat)")
ctl_embed = mo.ui.switch(value=True, label="Embedder (pencarian memory lebih pintar)")
ctl_install = mo.ui.run_button(label="Install")
ctl_start = mo.ui.run_button(label="Start", kind="success")
ctl_stop = mo.ui.run_button(label="Stop", kind="danger")
mo.vstack([
    mo.md("### Server model"),
    ctl_preset,
    mo.hstack([ctl_ctx, ctl_mtp, ctl_embed], justify="start", align="center", gap=2),
    mo.hstack([ctl_install, ctl_start, ctl_stop], justify="start"),
])
