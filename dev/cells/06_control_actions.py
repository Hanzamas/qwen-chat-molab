def _act():
    if ctl_hf.value.strip():
        os.environ["HF_TOKEN"] = ctl_hf.value.strip()
    if ctl_install.value:
        try:
            SERVERS.install()
            return mo.callout(mo.md("Install finished. Pick a model, then click **Start**."), kind="success")
        except Exception as e:
            return mo.callout(mo.md(f"Install failed: {e}"), kind="danger")
    if ctl_start.value:
        p = PRESETS[ctl_preset.value]
        if ctl_ctx.value > p["yarn_max"]:
            return mo.callout(mo.md(f"**{ctl_preset.value}** allows at most {p['yarn_max']:,} tokens. Pick a smaller context."),
                              kind="danger")
        try:
            SERVERS.start(ctl_preset.value, ctl_ctx.value, mtp=ctl_mtp.value, embed=ctl_embed.value,
                          embed_model=ctl_embed_model.value)
        except Exception as e:
            return mo.callout(mo.md(f"Start failed: {e}"), kind="danger")
        STORE.meta_set("server", {"preset": ctl_preset.value, "ctx": ctl_ctx.value, "mtp": ctl_mtp.value,
                                  "embed": ctl_embed.value, "embed_model": ctl_embed_model.value})
        note = ""
        if ctl_ctx.value > p["max_ctx"] and p.get("yarn_exp"):
            note = ("\n\n**Experimental YaRN:** this model has no official YaRN recipe. Check `n_ctx` in the log and test "
                    "its recall before you trust answers beyond 262K.")
        return mo.callout(mo.md(f"**{ctl_preset.value}** started with a context of {ctl_ctx.value:,}. "
                                f"Watch the status below.{note}"), kind="neutral")
    if ctl_stop.value:
        stopped = SERVERS.stop()
        return mo.md("Server stopped." if stopped else "No server is running.")
    return None


_act()
