def _status_view():
    st = SERVERS.status()
    phase = st["phase"]
    kinds = {"ready": "success", "failed": "danger"}
    titles = {"idle": "Belum di-start.", "downloading": "Download model…", "loading": "Memuat model…",
              "ready": "READY: chat siap dipakai.", "failed": "Server gagal."}
    head = f"**{titles.get(phase, phase)}**"
    if st.get("preset"):
        head += f" {st['preset']} · konteks {st['ctx']:,} · MTP {'nyala' if st.get('mtp') else 'mati'}"
    if st.get("embed"):
        head += f" · embedder {'siap' if st.get('embed_ready') else 'memuat'}"
    parts = [mo.callout(mo.md(head), kind=kinds.get(phase, "neutral"))]
    for w in st.get("warnings") or []:
        parts.append(mo.callout(mo.md(w), kind="warn"))
    if st.get("error"):
        parts.append(mo.callout(mo.plain_text(st["error"]), kind="danger"))
    gpu = Sys.gpu_line()
    if gpu:
        parts.append(mo.md(f"`GPU {gpu['util']:.0f}% · VRAM {gpu['used_gb']:.1f} / {gpu['total_gb']:.0f} GB`"))
    if st.get("log"):
        parts.append(mo.accordion({"Log server (40 baris terakhir)": mo.plain_text(st["log"])}))
    return mo.vstack(parts)


def _watch_status():
    me = mo.current_thread()
    while not me.should_exit:
        mo.output.replace(_status_view())
        time.sleep(3)


if mo.running_in_notebook():
    mo.Thread(target=_watch_status, daemon=True).start()
else:
    _status_view()
