def _status_view():
    st = SERVERS.status()
    phase = st["phase"]
    kinds = {"ready": "success", "failed": "danger"}
    titles = {"idle": "Not started.", "downloading": "Downloading model…", "loading": "Loading model…",
              "ready": "READY: the chat is ready to use.", "failed": "Server failed."}
    head = f"**{titles.get(phase, phase)}**"
    if st.get("preset"):
        head += f" {st['preset']} · context {st['ctx']:,} · MTP {'on' if st.get('mtp') else 'off'}"
    if st.get("embed"):
        head += f" · embedder {'ready' if st.get('embed_ready') else 'loading'}"
    parts = [mo.callout(mo.md(head), kind=kinds.get(phase, "neutral"))]
    for w in st.get("warnings") or []:
        parts.append(mo.callout(mo.md(w), kind="warn"))
    if st.get("error"):
        parts.append(mo.callout(mo.plain_text(st["error"]), kind="danger"))
    gpu = Sys.gpu_line()
    if gpu:
        parts.append(mo.md(f"`GPU {gpu['util']:.0f}% · VRAM {gpu['used_gb']:.1f} / {gpu['total_gb']:.0f} GB`"))
    if st.get("log"):
        parts.append(mo.accordion({"Server log (last 40 lines)": mo.plain_text(st["log"])}))
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
