def _act():
    if ctl_install.value:
        try:
            SERVERS.install()
            return mo.callout(mo.md("Install selesai. Pilih model lalu klik **Start**."), kind="success")
        except Exception as e:
            return mo.callout(mo.md(f"Install gagal: {e}"), kind="danger")
    if ctl_start.value:
        p = PRESETS[ctl_preset.value]
        if ctl_ctx.value > p["yarn_max"]:
            return mo.callout(mo.md(f"**{ctl_preset.value}** maksimal {p['yarn_max']:,} token. Pilih konteks yang lebih kecil."),
                              kind="danger")
        try:
            SERVERS.start(ctl_preset.value, ctl_ctx.value, mtp=ctl_mtp.value, embed=ctl_embed.value)
        except Exception as e:
            return mo.callout(mo.md(f"Start gagal: {e}"), kind="danger")
        STORE.meta_set("server", {"preset": ctl_preset.value, "ctx": ctl_ctx.value, "mtp": ctl_mtp.value,
                                  "embed": ctl_embed.value})
        note = ""
        if ctl_ctx.value > p["max_ctx"] and p.get("yarn_exp"):
            note = ("\n\n**YaRN eksperimental:** model ini tidak punya resep YaRN resmi. Cek `n_ctx` di log dan uji "
                    "ingatan sebelum percaya jawaban di atas 262K.")
        return mo.callout(mo.md(f"**{ctl_preset.value}** dimulai dengan konteks {ctl_ctx.value:,}. "
                                f"Pantau status di bawah.{note}"), kind="neutral")
    if ctl_stop.value:
        stopped = SERVERS.stop()
        return mo.md("Server dihentikan." if stopped else "Tidak ada server yang jalan.")
    return None


_act()
