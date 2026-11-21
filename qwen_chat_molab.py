# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
#     "altair",
#     "anywidget",
#     "traitlets",
# ]
# [tool.marimo.display]
# theme = "dark"
# ///

import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium", app_title="Qwen Chat")


@app.cell(hide_code=True)
def _():
    import marimo as mo
    import json
    import os
    import re
    import secrets
    import signal
    import subprocess
    import threading
    import time
    import urllib.error
    import urllib.request
    from pathlib import Path

    return Path, json, mo, os, re, secrets, signal, subprocess, threading, time, urllib


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Qwen Chat

    Chat panjang dengan **Qwen3.8-27B abliterated** (uncensored, FP8) yang jalan di GPU molab lewat vLLM.

    1. Nyalakan GPU lewat *notebook specs*, lalu klik **Install**.
    2. Klik **Start**, tunggu panel server `READY` (download sekitar 31 GB lalu load).
    3. Ngobrol di jendela chat di bawah.

    Reasoning dikunci di `xhigh` (level tertinggi Qwen3.8) dan thinking tiap balasan diingat model (`preserve_thinking`).
    Tema gelap: kalau notebook masih terang, ganti tema ke dark di pengaturan tampilan molab.
    Isi workspace hilang saat notebook mati, jadi pakai **Simpan** di chat untuk mengunduh obrolan.
    """)
    return


@app.cell(hide_code=True)
def _(Path, os, secrets):
    WORK = Path("/tmp/qwen-chat")
    WORK.mkdir(parents=True, exist_ok=True)
    VENV = Path.home() / "vllm-env"
    VLLM_BIN = VENV / "bin" / "vllm"
    VLLM_OK = VENV / ".install-ok"
    VLLM_LOG = WORK / "vllm.log"
    VLLM_PID = WORK / "vllm.pid"
    MODEL = "munekazu/Huihui-Qwen3.8-27B-abliterated-FP8"
    SERVED_NAME = "qwen3.8-27b"
    # xhigh is the highest level Qwen3.8's chat template accepts.
    REASONING = "xhigh"
    PORT = 8000
    # QWEN_CHAT_BASE_URL lets the chat be tested against another OpenAI-compatible server.
    BASE_URL = os.environ.get("QWEN_CHAT_BASE_URL", f"http://127.0.0.1:{PORT}/v1")
    HEALTH_URL = BASE_URL.rsplit("/v1", 1)[0] + "/health"

    # The key stays inside the sandbox; /tmp keeps it stable across reruns.
    _key_file = WORK / "api_key"
    if not _key_file.exists():
        _key_file.write_text(secrets.token_hex(16))
    API_KEY = os.environ.get("QWEN_CHAT_API_KEY", _key_file.read_text().strip())

    # Popen handles started from this kernel; poll() reaps exited children.
    PROCS = {}
    return (
        API_KEY,
        BASE_URL,
        HEALTH_URL,
        MODEL,
        PORT,
        PROCS,
        REASONING,
        SERVED_NAME,
        VENV,
        VLLM_BIN,
        VLLM_LOG,
        VLLM_OK,
        VLLM_PID,
    )


@app.cell(hide_code=True)
def _(PROCS, VLLM_PID, mo, os, re, signal, subprocess, time, urllib):
    def run_live(cmd, title):
        """Run a shell command and stream its last lines into the cell output."""
        proc = subprocess.Popen(
            cmd,
            shell=True,
            executable="/bin/bash",
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
        )
        lines = []
        last = 0.0
        try:
            for line in proc.stdout:
                lines.append(line.rstrip("\n"))
                if time.time() - last > 0.5:
                    mo.output.replace(mo.vstack([mo.md(f"**{title}** (jalan...)"), mo.plain_text("\n".join(lines[-30:]))]))
                    last = time.time()
            code = proc.wait()
        finally:
            # An interrupted cell must not leave the command running in the background.
            if proc.poll() is None:
                os.killpg(proc.pid, signal.SIGTERM)
        status = "selesai" if code == 0 else f"GAGAL (exit {code})"
        mo.output.replace(mo.vstack([mo.md(f"**{title}**: {status}"), mo.plain_text("\n".join(lines[-30:]))]))
        return code

    def http_get(url, headers=None, timeout=2):
        """Return (status, body); status is None when the request fails."""
        try:
            req = urllib.request.Request(url, headers=headers or {})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, resp.read().decode("utf-8", "replace")
        except Exception as e:
            return None, str(e)

    def tail(path, n=30, max_bytes=65536):
        try:
            with open(path, "rb") as f:
                f.seek(0, os.SEEK_END)
                f.seek(max(0, f.tell() - max_bytes))
                return "\n".join(f.read().decode("utf-8", "replace").splitlines()[-n:])
        except FileNotFoundError:
            return "(belum ada log)"

    _error_line = re.compile(r"\b\w*(Error|Exception)\b:|\bERROR\b|out of memory|CUDA error")
    # vLLM's own wrapper messages only say "see root cause above".
    _wrapper = ("Engine core initialization failed", "Frontend process failed", "EngineCore failed to start")

    def log_errors(path, n=12):
        """Last distinct error lines of a log, without vLLM's generic wrapper messages."""
        found = []
        for line in tail(path, 5000, max_bytes=1 << 20).splitlines():
            if _error_line.search(line) and not any(w in line for w in _wrapper) and line not in found:
                found.append(line)
        return "\n".join(found[-n:])

    def vllm_alive():
        """True while the vLLM API server is running."""
        proc = PROCS.get("vllm")
        if proc is not None:
            return proc.poll() is None
        # Started before a kernel restart: the group is no longer our child, so check it directly.
        try:
            pid = int(VLLM_PID.read_text())
        except (FileNotFoundError, ValueError):
            return False
        try:
            os.killpg(pid, 0)
            return True
        except ProcessLookupError:
            return False

    def vllm_kill(sig=signal.SIGTERM, wait=60):
        """Signal the whole vLLM process group (API server + EngineCore) and wait until it is gone."""
        try:
            pid = int(VLLM_PID.read_text())
        except (FileNotFoundError, ValueError):
            return None
        try:
            os.killpg(pid, sig)
        except ProcessLookupError:
            pass
        for _ in range(wait):
            if "vllm" in PROCS:
                PROCS["vllm"].poll()
            try:
                os.killpg(pid, 0)
            except ProcessLookupError:
                break
            time.sleep(1)
        else:
            os.killpg(pid, signal.SIGKILL)
        VLLM_PID.unlink(missing_ok=True)
        PROCS.pop("vllm", None)
        return pid

    return http_get, log_errors, run_live, tail, vllm_alive, vllm_kill


@app.cell(hide_code=True)
def _(mo):
    ctx_len = mo.ui.dropdown(
        options={"1M (YaRN factor 4.0)": 1000000, "512K (YaRN factor 2.0)": 524288, "262K (native, paling akurat)": 262144},
        value="1M (YaRN factor 4.0)",
        label="Konteks",
    )
    use_mtp = mo.ui.switch(value=False, label="MTP speculative decoding (generate lebih cepat, startup pertama compile kernel)")
    install_btn = mo.ui.run_button(label="Install")
    start_btn = mo.ui.run_button(label="Start", kind="success")
    stop_btn = mo.ui.run_button(label="Stop", kind="danger")
    mo.vstack(
        [
            mo.hstack([ctx_len, use_mtp], justify="start", align="center"),
            mo.hstack([install_btn, start_btn, stop_btn], justify="start"),
        ]
    )
    return ctx_len, install_btn, start_btn, stop_btn, use_mtp


@app.cell(hide_code=True)
def _(VENV, VLLM_BIN, VLLM_OK, install_btn, mo, run_live, subprocess):
    mo.stop(not install_btn.value)

    _gpu = subprocess.run(
        "nvidia-smi --query-gpu=driver_version --format=csv,noheader", shell=True, capture_output=True, text=True
    ).stdout.strip()
    try:
        _driver = int(_gpu.split(".")[0])
    except ValueError:
        _driver = 0
    mo.stop(
        _driver == 0,
        mo.callout(mo.md("GPU belum terdeteksi. Nyalakan GPU lewat *notebook specs*, lalu klik Install lagi."), kind="danger"),
    )

    # Triton needs cc, FlashInfer JIT needs ninja, and FlashInfer links -lcudart from nvidia/cu13/lib64,
    # where the pip CUDA runtime only ships libcudart.so.13.
    run_live(
        "(command -v cc && command -v ninja) >/dev/null && echo 'cc + ninja ada' "
        "|| (apt-get -qq update && apt-get -qq install -y gcc g++ ninja-build >/dev/null && echo 'gcc + ninja terpasang') "
        "|| echo 'gcc/ninja gagal dipasang'; "
        "for D in /usr/local/lib/python3.*/site-packages/nvidia/cu13 "
        f"{VENV}/lib/python3.*/site-packages/nvidia/cu13; do "
        "[ -d \"$D\" ] || continue; L=$(find \"$D\" -name 'libcudart.so.1*' | head -1); "
        "[ -n \"$L\" ] && mkdir -p \"$D/lib64\" && ln -sf \"$L\" \"$D/lib64/libcudart.so\" && echo \"libcudart.so -> $L\"; done",
        "Persiapan compiler",
    )
    if VLLM_OK.exists():
        mo.output.replace(mo.md(f"vLLM sudah terpasang di `{VENV}`."))
    else:
        # A separate venv keeps vLLM's torch away from the notebook kernel's packages.
        if _driver < 580:
            _pkg = (
                '"https://github.com/vllm-project/vllm/releases/download/v0.32.0/'
                'vllm-0.32.0+cu129-cp38-abi3-manylinux_2_28_x86_64.whl" --torch-backend=cu129'
            )
        else:
            _pkg = "vllm==0.32.0 --torch-backend=cu130"
        _rc = run_live(
            f"set -e; uv venv --allow-existing {VENV}; "
            f"uv pip install --python {VENV}/bin/python {_pkg}; "
            f"{VLLM_BIN} download-kernels || echo 'download-kernels dilewati'",
            "Install vLLM 0.32.0",
        )
        if _rc == 0:
            VLLM_OK.touch()
    return


@app.cell(hide_code=True)
def _(
    API_KEY,
    HEALTH_URL,
    MODEL,
    PORT,
    PROCS,
    REASONING,
    SERVED_NAME,
    VLLM_BIN,
    VLLM_LOG,
    VLLM_OK,
    VLLM_PID,
    ctx_len,
    http_get,
    json,
    mo,
    os,
    signal,
    start_btn,
    subprocess,
    use_mtp,
    vllm_alive,
    vllm_kill,
):
    mo.stop(
        not start_btn.value,
        mo.md("_Server jalan dengan pengaturan lama. Stop lalu Start untuk menerapkan perubahan._") if vllm_alive() else None,
    )
    mo.stop(not VLLM_OK.exists(), mo.callout(mo.md("vLLM belum terpasang. Klik **Install** dulu."), kind="danger"))

    if vllm_alive() or http_get(HEALTH_URL)[0] == 200:
        mo.output.replace(mo.md("Server sudah jalan atau masih loading. Klik **Stop** dulu kalau mau ganti pengaturan."))
    else:
        # A crashed run can leave EngineCore children holding VRAM.
        vllm_kill(signal.SIGKILL, wait=15)
        _yarn = ctx_len.value > 262144
        _cmd = [
            str(VLLM_BIN), "serve", MODEL,
            "--served-model-name", SERVED_NAME,
            "--host", "127.0.0.1",
            "--port", str(PORT),
            "--api-key", API_KEY,
            "--max-model-len", str(ctx_len.value),
            # BF16 KV scored best at native context; with YaRN, FP8 KV scored the same (MRCR v2, n=15).
            "--kv-cache-dtype", "fp8" if _yarn else "auto",
            # One long conversation: give it all the memory and no batch sharing.
            "--gpu-memory-utilization", "0.95",
            "--max-num-seqs", "1",
            # Every turn resends the whole history; prefix caching reuses its KV instead of recomputing it.
            "--enable-prefix-caching",
            # Larger prefill chunks speed up the first pass over a long history.
            "--max-num-batched-tokens", "16384",
            "--reasoning-parser", "qwen3",
            "--default-chat-template-kwargs", json.dumps({"reasoning_effort": REASONING, "preserve_thinking": True}),
        ]
        if _yarn:
            # YaRN override from the Qwen3.8-27B model card: factor 4.0 for 1M, 2.0 for ~524K.
            _rope = {
                "mrope_interleaved": True,
                "mrope_section": [11, 11, 10],
                "rope_type": "yarn",
                "rope_theta": 10000000,
                "partial_rotary_factor": 0.25,
                "factor": 4.0 if ctx_len.value > 524288 else 2.0,
                "original_max_position_embeddings": 262144,
            }
            _cmd += ["--hf-overrides", json.dumps({"text_config": {"rope_parameters": _rope}})]
        if use_mtp.value:
            _cmd += ["--speculative-config", json.dumps({"method": "mtp", "num_speculative_tokens": 3})]

        _log = open(VLLM_LOG, "w")
        # start_new_session keeps the server alive when a cell is interrupted and makes pgid == pid.
        _proc = subprocess.Popen(
            _cmd,
            stdin=subprocess.DEVNULL,
            stdout=_log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            env={
                **os.environ,
                "VLLM_ALLOW_LONG_MAX_MODEL_LEN": "1",
                # FlashInfer JIT looks for ninja and nvcc on PATH; molab does not export the CUDA bin dir.
                "PATH": f"{VLLM_BIN.parent}:/usr/local/cuda/bin:{os.environ.get('PATH', '')}",
                "CUDA_HOME": os.environ.get("CUDA_HOME", "/usr/local/cuda"),
            },
        )
        VLLM_PID.write_text(str(_proc.pid))
        PROCS["vllm"] = _proc
        mo.output.replace(mo.md(f"vLLM dimulai (pid `{_proc.pid}`). Pantau panel server di bawah."))
    return


@app.cell(hide_code=True)
def _(mo, stop_btn, vllm_kill):
    mo.stop(not stop_btn.value)

    # Waits for the whole group to free the GPU before a new Start is allowed.
    _pid = vllm_kill()
    mo.output.replace(mo.md(f"vLLM (pid `{_pid}`) dihentikan.") if _pid else mo.md("Tidak ada server vLLM yang jalan."))
    return


@app.cell(hide_code=True)
def _(HEALTH_URL, VLLM_LOG, VLLM_PID, http_get, log_errors, mo, tail, time, vllm_alive):
    # A mo.Thread keeps updating while the kernel is busy elsewhere.
    def _watch_server():
        me = mo.current_thread()
        while not me.should_exit:
            if http_get(HEALTH_URL)[0] == 200:
                badge = mo.callout(mo.md("**READY**: server siap, silakan chat."), kind="success")
            elif vllm_alive():
                badge = mo.callout(mo.md("**Loading**: download atau load model."), kind="neutral")
            elif VLLM_PID.exists():
                badge = mo.callout(mo.md("**vLLM mati.** Lihat baris error di bawah, lalu Start lagi."), kind="danger")
            else:
                badge = mo.callout(mo.md("**Belum di-start.**"), kind="neutral")
            log = {"Log vLLM (40 baris terakhir)": mo.plain_text(tail(VLLM_LOG, 40))}
            errors = log_errors(VLLM_LOG)
            if errors:
                log = {"Baris error di log vLLM": mo.plain_text(errors), **log}
            mo.output.replace(mo.vstack([badge, mo.accordion(log)]))
            time.sleep(3)

    mo.Thread(target=_watch_server, daemon=True).start()
    return


@app.cell(hide_code=True)
def _(HEALTH_URL, http_get, mo, subprocess, time):
    def _gpu_line():
        r = subprocess.run(
            "nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total --format=csv,noheader,nounits",
            shell=True, capture_output=True, text=True,
        )
        try:
            util, used, total = [float(x) for x in r.stdout.strip().split("\n")[0].split(",")]
            return f"GPU {util:.0f}%  ·  VRAM {used / 1024:.1f} / {total / 1024:.0f} GB"
        except ValueError:
            return "GPU tidak terbaca"

    def _metrics():
        status, body = http_get(HEALTH_URL.replace("/health", "/metrics"))
        out = {}
        if status == 200:
            for line in body.splitlines():
                if line.startswith("#") or " " not in line:
                    continue
                try:
                    name = line.split("{")[0].split(" ")[0]
                    out[name] = out.get(name, 0.0) + float(line.rsplit(" ", 1)[1])
                except ValueError:
                    pass
        return out

    def _watch_gpu():
        me = mo.current_thread()
        prev = None
        while not me.should_exit:
            m = _metrics()
            now = time.time()
            gen = m.get("vllm:generation_tokens_total")
            tps = None
            if gen is not None and prev and now > prev[1]:
                tps = max(0.0, (gen - prev[0]) / (now - prev[1]))
            prev = (gen, now) if gen is not None else None
            kv = m.get("vllm:kv_cache_usage_perc", m.get("vllm:gpu_cache_usage_perc"))
            hits = m.get("vllm:prefix_cache_hits_total")
            queries = m.get("vllm:prefix_cache_queries_total")
            parts = [_gpu_line()]
            if kv is not None:
                parts.append(f"KV {kv * 100:.1f}%")
            if tps is not None:
                parts.append(f"{tps:.1f} token/s")
            if hits is not None and queries:
                parts.append(f"prefix cache hit {hits / queries * 100:.0f}%")
            mo.output.replace(mo.md("`" + "  ·  ".join(parts) + "`"))
            time.sleep(3)

    mo.Thread(target=_watch_gpu, daemon=True).start()
    return


@app.cell(hide_code=True)
def _(API_KEY, BASE_URL, HEALTH_URL, REASONING, SERVED_NAME, http_get, json, mo, threading, time, urllib):
    import anywidget
    import traitlets

    _ESM = r"""
    const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
    let md = (s) => `<p>${esc(s).replace(/\n/g, "<br>")}</p>`;
    const mdReady = (async () => {
      try {
        const [m, p] = await Promise.all([
          import("https://esm.sh/marked@14.1.4"),
          import("https://esm.sh/dompurify@3.2.4"),
        ]);
        const purify = p.default;
        md = (s) => purify.sanitize(m.marked.parse(String(s ?? ""), { gfm: true, breaks: true }));
      } catch (e) {
        console.warn("qwen-chat: markdown libraries unavailable, showing plain text", e);
      }
    })();

    const words = (s) => (String(s || "").trim().match(/\S+/g) || []).length;

    function statsLine(st) {
      if (!st) return "";
      const bits = [];
      if (st.tokens) bits.push(`${st.tokens.toLocaleString()} token`);
      if (st.tps) bits.push(`${st.tps.toFixed(1)} token/s`);
      if (st.think_s) bits.push(`mikir ${st.think_s.toFixed(0)} dtk`);
      if (st.total_s) bits.push(`total ${st.total_s.toFixed(0)} dtk`);
      if (st.stopped) bits.push("dihentikan");
      return bits.join(" · ");
    }

    function render({ model, el }) {
      el.classList.add("qc-root");
      el.innerHTML = `
        <div class="qc-top">
          <div class="qc-title">Qwen3.8 27B <span class="qc-badge">uncensored</span><span class="qc-badge">xhigh</span></div>
          <div class="qc-actions">
            <button type="button" data-act="new">Chat baru</button>
            <button type="button" data-act="save">Simpan</button>
            <button type="button" data-act="load">Muat</button>
            <button type="button" data-act="settings">System prompt</button>
          </div>
        </div>
        <div class="qc-ctx"><div class="qc-ctx-bar"><div class="qc-ctx-fill"></div></div><span class="qc-ctx-text"></span></div>
        <div class="qc-settings" hidden>
          <textarea class="qc-system" rows="3" placeholder="System prompt (opsional). Berlaku untuk pesan berikutnya."></textarea>
        </div>
        <div class="qc-scroll">
          <div class="qc-empty">Mulai ngobrol dengan Qwen.</div>
          <div class="qc-list"></div>
          <div class="qc-live"></div>
        </div>
        <button type="button" class="qc-jump" hidden>Ke pesan terbaru</button>
        <div class="qc-status" hidden></div>
        <form class="qc-form">
          <textarea class="qc-input" rows="1" placeholder="Kirim pesan  (Enter kirim, Shift+Enter baris baru)"></textarea>
          <button type="submit" class="qc-send">Kirim</button>
        </form>
        <input type="file" accept="application/json,.json" class="qc-file" hidden>`;

      const $ = (q) => el.querySelector(q);
      const scroll = $(".qc-scroll"), list = $(".qc-list"), live = $(".qc-live"), empty = $(".qc-empty");
      const input = $(".qc-input"), send = $(".qc-send"), status = $(".qc-status"), jump = $(".qc-jump");
      const system = $(".qc-system"), settings = $(".qc-settings"), file = $(".qc-file");
      const open = new Set();
      let stick = true;
      let liveParts = null;
      let thinkTouched = false;

      const command = (action, extra = {}) => {
        model.set("command", { n: Date.now() + Math.random(), action, ...extra });
        model.save_changes();
      };

      const toBottom = (force) => {
        if (force || stick) scroll.scrollTop = scroll.scrollHeight;
        jump.hidden = stick || force;
      };
      scroll.addEventListener("scroll", () => {
        stick = scroll.scrollHeight - scroll.scrollTop - scroll.clientHeight < 60;
        jump.hidden = stick;
      });
      jump.addEventListener("click", () => { stick = true; toBottom(true); });

      function thinkBlock(key, text, isLive) {
        const isOpen = open.has(key);
        return `<details class="qc-think" data-key="${key}" ${isOpen ? "open" : ""}>
          <summary>${isLive ? "Sedang mikir" : "Thinking"} <span class="qc-muted">${words(text).toLocaleString()} kata</span></summary>
          <div class="qc-think-body">${esc(text)}</div></details>`;
      }

      function messageHTML(m, i) {
        if (m.role === "user") return `<div class="qc-row qc-user"><div class="qc-bubble">${esc(m.content).replace(/\n/g, "<br>")}</div></div>`;
        const think = m.reasoning ? thinkBlock(`t${i}`, m.reasoning, false) : "";
        const error = m.error ? `<div class="qc-error">${esc(m.error)}</div>` : "";
        const st = statsLine(m.stats);
        return `<div class="qc-row qc-bot">${think}<div class="qc-md">${md(m.content || "")}</div>${error}${st ? `<div class="qc-stats">${st}</div>` : ""}</div>`;
      }

      function renderHistory() {
        const h = model.get("history") || [];
        list.innerHTML = h.map(messageHTML).join("");
        empty.hidden = h.length > 0 || !!liveParts;
        toBottom(false);
      }

      function renderLive() {
        const lv = model.get("live") || {};
        if (!lv.active) {
          live.innerHTML = "";
          liveParts = null;
          thinkTouched = false;
          empty.hidden = (model.get("history") || []).length > 0;
          return;
        }
        empty.hidden = true;
        if (!liveParts) {
          live.innerHTML = `<div class="qc-row qc-bot">
            <details class="qc-think" open hidden><summary></summary><div class="qc-think-body"></div></details>
            <div class="qc-md"></div><div class="qc-typing"><span></span><span></span><span></span></div></div>`;
          liveParts = {
            think: live.querySelector(".qc-think"),
            sum: live.querySelector(".qc-think summary"),
            body: live.querySelector(".qc-think-body"),
            md: live.querySelector(".qc-md"),
            typing: live.querySelector(".qc-typing"),
          };
          liveParts.think.addEventListener("toggle", () => { thinkTouched = true; });
        }
        const p = liveParts;
        if (lv.reasoning) {
          p.think.hidden = false;
          p.sum.innerHTML = `${lv.content ? "Thinking" : "Sedang mikir"} <span class="qc-muted">${words(lv.reasoning).toLocaleString()} kata</span>`;
          p.body.textContent = lv.reasoning;
          p.body.scrollTop = p.body.scrollHeight;
          // Fold the thinking away once the answer starts, unless the user opened or closed it.
          if (lv.content && !thinkTouched && p.think.open) p.think.open = false;
        }
        p.md.innerHTML = lv.content ? md(lv.content) : "";
        p.typing.hidden = !!lv.content;
        toBottom(false);
      }

      function renderBusy() {
        const busy = model.get("busy");
        send.textContent = busy ? "Stop" : "Kirim";
        send.classList.toggle("qc-stop", !!busy);
      }

      function renderStatus() {
        const s = model.get("status") || "";
        status.textContent = s;
        status.hidden = !s;
      }

      function renderCtx() {
        const c = model.get("ctx") || {};
        const used = c.used || 0, max = c.max || 0;
        const pct = max ? Math.min(100, (used / max) * 100) : 0;
        $(".qc-ctx-fill").style.width = `${pct}%`;
        $(".qc-ctx-fill").classList.toggle("qc-warn", pct > 85);
        $(".qc-ctx-text").textContent = max ? `${used.toLocaleString()} / ${max.toLocaleString()} token konteks (${pct.toFixed(1)}%)` : "konteks: -";
      }

      list.addEventListener("toggle", (e) => {
        const d = e.target;
        if (!(d instanceof HTMLDetailsElement) || !d.dataset.key) return;
        d.open ? open.add(d.dataset.key) : open.delete(d.dataset.key);
      }, true);

      const grow = () => { input.style.height = "auto"; input.style.height = `${Math.min(input.scrollHeight, 220)}px`; };
      input.addEventListener("input", grow);
      input.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); $(".qc-form").requestSubmit(); }
      });
      $(".qc-form").addEventListener("submit", (e) => {
        e.preventDefault();
        if (model.get("busy")) { command("stop"); return; }
        const text = input.value.trim();
        if (!text) return;
        command("send", { text });
        input.value = "";
        grow();
        stick = true;
      });

      system.value = (model.get("settings") || {}).system || "";
      system.addEventListener("change", () => {
        model.set("settings", { ...(model.get("settings") || {}), system: system.value });
        model.save_changes();
      });

      el.querySelector(".qc-actions").addEventListener("click", (e) => {
        const act = e.target?.dataset?.act;
        if (act === "new") { if (confirm("Mulai chat baru? Obrolan sekarang hilang kalau belum disimpan.")) command("clear"); }
        else if (act === "save") command("save");
        else if (act === "load") file.click();
        else if (act === "settings") settings.hidden = !settings.hidden;
      });
      file.addEventListener("change", async () => {
        const f = file.files?.[0];
        if (!f) return;
        try { command("load", { data: JSON.parse(await f.text()) }); }
        catch (err) { status.textContent = `File tidak valid: ${err}`; status.hidden = false; }
        file.value = "";
      });

      const onExport = () => {
        const ex = model.get("export") || {};
        if (!ex.json) return;
        const url = URL.createObjectURL(new Blob([ex.json], { type: "application/json" }));
        const a = Object.assign(document.createElement("a"), { href: url, download: ex.name || "qwen-chat.json" });
        document.body.appendChild(a); a.click(); a.remove();
        setTimeout(() => URL.revokeObjectURL(url), 2000);
      };

      let raf = 0;
      const onLive = () => { if (!raf) raf = requestAnimationFrame(() => { raf = 0; renderLive(); }); };
      const onHistory = () => renderHistory();
      model.on("change:history", onHistory);
      model.on("change:live", onLive);
      model.on("change:busy", renderBusy);
      model.on("change:status", renderStatus);
      model.on("change:ctx", renderCtx);
      model.on("change:export", onExport);

      renderHistory(); renderLive(); renderBusy(); renderStatus(); renderCtx();
      // Re-render once the markdown libraries arrive so earlier messages get formatted too.
      mdReady.then(() => { renderHistory(); renderLive(); });

      return () => {
        model.off("change:history", onHistory);
        model.off("change:live", onLive);
        model.off("change:busy", renderBusy);
        model.off("change:status", renderStatus);
        model.off("change:ctx", renderCtx);
        model.off("change:export", onExport);
      };
    }
    export default { render };
    """

    _CSS = r"""
    .qc-root {
      --qc-bg: #212121; --qc-panel: #171717; --qc-bubble: #303030; --qc-border: #3a3a3a;
      --qc-text: #ececec; --qc-muted: #a3a3a3; --qc-accent: #10a37f; --qc-danger: #ef4444;
      color-scheme: dark;
      background: var(--qc-bg); color: var(--qc-text);
      font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
      font-size: 15px; line-height: 1.6;
      border: 1px solid var(--qc-border); border-radius: 16px;
      display: flex; flex-direction: column; height: 78vh; min-height: 480px;
      overflow: hidden; position: relative;
    }
    .qc-root button { font: inherit; color: var(--qc-text); background: transparent; border: 1px solid var(--qc-border);
      border-radius: 999px; padding: 4px 12px; cursor: pointer; }
    .qc-root button:hover { background: #2a2a2a; }
    .qc-root button:focus-visible, .qc-root textarea:focus-visible { outline: 2px solid var(--qc-accent); outline-offset: 2px; }
    .qc-top { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap;
      padding: 12px 16px; border-bottom: 1px solid var(--qc-border); background: var(--qc-panel); }
    .qc-title { font-weight: 600; display: flex; align-items: center; gap: 8px; }
    .qc-badge { font-size: 12px; font-weight: 500; color: var(--qc-muted); border: 1px solid var(--qc-border);
      border-radius: 999px; padding: 0 8px; }
    .qc-actions { display: flex; gap: 8px; flex-wrap: wrap; }
    .qc-ctx { display: flex; align-items: center; gap: 10px; padding: 6px 16px; background: var(--qc-panel);
      border-bottom: 1px solid var(--qc-border); font-size: 12px; color: var(--qc-muted); }
    .qc-ctx-bar { flex: 1; height: 4px; background: #2f2f2f; border-radius: 999px; overflow: hidden; }
    .qc-ctx-fill { height: 100%; width: 0; background: var(--qc-accent); transition: width .3s ease; }
    .qc-ctx-fill.qc-warn { background: var(--qc-danger); }
    .qc-settings { padding: 12px 16px; border-bottom: 1px solid var(--qc-border); background: var(--qc-panel); }
    .qc-settings textarea { width: 100%; box-sizing: border-box; }
    .qc-scroll { flex: 1; overflow-y: auto; padding: 24px 0 12px; scroll-behavior: auto; }
    .qc-empty { color: var(--qc-muted); text-align: center; margin-top: 18vh; }
    .qc-row { max-width: 760px; margin: 0 auto 24px; padding: 0 20px; box-sizing: border-box; }
    .qc-user { display: flex; justify-content: flex-end; }
    .qc-bubble { background: var(--qc-bubble); border-radius: 20px; padding: 10px 16px; max-width: 80%;
      white-space: normal; overflow-wrap: anywhere; }
    .qc-md { overflow-wrap: anywhere; }
    .qc-md p { margin: 0 0 12px; }
    .qc-md p:last-child { margin-bottom: 0; }
    .qc-md pre { background: #0d0d0d; border: 1px solid var(--qc-border); border-radius: 10px; padding: 12px 14px;
      overflow-x: auto; font-size: 13px; line-height: 1.5; }
    .qc-md code { font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace; font-size: 0.9em; }
    .qc-md :not(pre) > code { background: #2f2f2f; padding: 1px 6px; border-radius: 6px; }
    .qc-md a { color: #7ab7ff; }
    .qc-md table { border-collapse: collapse; margin: 8px 0; }
    .qc-md th, .qc-md td { border: 1px solid var(--qc-border); padding: 4px 10px; }
    .qc-md blockquote { border-left: 3px solid var(--qc-border); margin: 8px 0; padding-left: 12px; color: var(--qc-muted); }
    .qc-think { margin-bottom: 10px; color: var(--qc-muted); font-size: 14px; }
    .qc-think summary { cursor: pointer; user-select: none; list-style: none; display: inline-flex; gap: 8px; }
    .qc-think summary::before { content: "▸"; transition: transform .15s ease; }
    .qc-think[open] summary::before { transform: rotate(90deg); }
    .qc-think-body { white-space: pre-wrap; border-left: 2px solid var(--qc-border); margin-top: 8px; padding: 2px 0 2px 14px;
      max-height: 320px; overflow-y: auto; }
    .qc-muted { color: var(--qc-muted); font-size: 12px; }
    .qc-stats { color: var(--qc-muted); font-size: 12px; margin-top: 8px; }
    .qc-error { color: var(--qc-danger); font-size: 14px; margin-top: 6px; }
    .qc-typing { display: inline-flex; gap: 4px; padding: 6px 0; }
    .qc-typing span { width: 6px; height: 6px; border-radius: 50%; background: var(--qc-muted); animation: qc-blink 1.2s infinite; }
    .qc-typing span:nth-child(2) { animation-delay: .2s; }
    .qc-typing span:nth-child(3) { animation-delay: .4s; }
    @keyframes qc-blink { 0%, 80%, 100% { opacity: .25; } 40% { opacity: 1; } }
    @media (prefers-reduced-motion: reduce) { .qc-typing span { animation: none; opacity: .6; } }
    .qc-jump { position: absolute; right: 24px; bottom: 96px; background: var(--qc-panel) !important; }
    .qc-status { max-width: 760px; margin: 0 auto 8px; padding: 0 20px; color: var(--qc-danger); font-size: 13px;
      box-sizing: border-box; width: 100%; }
    .qc-form { display: flex; gap: 8px; align-items: flex-end; max-width: 760px; width: 100%; margin: 0 auto 16px;
      padding: 0 20px; box-sizing: border-box; }
    .qc-root textarea { font: inherit; color: var(--qc-text); background: var(--qc-bubble); border: 1px solid var(--qc-border);
      border-radius: 18px; padding: 10px 14px; resize: none; }
    .qc-input { flex: 1; max-height: 220px; }
    .qc-send { background: var(--qc-text) !important; color: #111 !important; border: none !important; padding: 10px 18px !important;
      font-weight: 600; }
    .qc-send.qc-stop { background: var(--qc-danger) !important; color: #fff !important; }
    """

    class QwenChat(anywidget.AnyWidget):
        _esm = _ESM
        _css = _CSS
        history = traitlets.List([]).tag(sync=True)
        live = traitlets.Dict({}).tag(sync=True)
        busy = traitlets.Bool(False).tag(sync=True)
        status = traitlets.Unicode("").tag(sync=True)
        ctx = traitlets.Dict({"used": 0, "max": 0}).tag(sync=True)
        settings = traitlets.Dict({"system": ""}).tag(sync=True)
        command = traitlets.Dict({}).tag(sync=True)
        export = traitlets.Dict({}).tag(sync=True)

    widget = QwenChat()
    # Messages as sent to vLLM; assistant turns keep reasoning_content so preserve_thinking can replay them.
    STATE = {"api": [], "stop": threading.Event()}

    def _max_context():
        status, body = http_get(f"{BASE_URL}/models", headers={"Authorization": f"Bearer {API_KEY}"})
        try:
            return int(json.loads(body)["data"][0]["max_model_len"]) if status == 200 else 0
        except (KeyError, IndexError, ValueError):
            return 0

    def _stream(messages, acc, on_delta):
        body = {
            "model": SERVED_NAME,
            "messages": messages,
            "stream": True,
            "stream_options": {"include_usage": True},
            # Qwen3.8 thinking-mode sampling from the model card.
            "temperature": 1.0,
            "top_p": 0.95,
            "top_k": 20,
            "chat_template_kwargs": {"reasoning_effort": REASONING, "preserve_thinking": True},
        }
        req = urllib.request.Request(
            f"{BASE_URL}/chat/completions",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {API_KEY}"},
        )
        resp = urllib.request.urlopen(req, timeout=3600)
        try:
            for raw in resp:
                if STATE["stop"].is_set():
                    break
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                chunk = json.loads(data)
                if chunk.get("usage"):
                    acc["usage"] = chunk["usage"]
                for choice in chunk.get("choices") or []:
                    delta = choice.get("delta") or {}
                    reasoning = delta.get("reasoning") or delta.get("reasoning_content")
                    if reasoning:
                        if acc["t_think"] is None:
                            acc["t_think"] = time.time()
                        acc["reasoning"] += reasoning
                    if delta.get("content"):
                        if acc["t_answer"] is None:
                            acc["t_answer"] = time.time()
                        acc["content"] += delta["content"]
                    if reasoning or delta.get("content"):
                        on_delta()
        finally:
            # Closing the stream makes vLLM abort the request when Stop is pressed.
            resp.close()

    def _run_turn(text):
        w = widget
        STATE["stop"].clear()
        STATE["api"].append({"role": "user", "content": text})
        w.history = w.history + [{"role": "user", "content": text}]
        w.status = ""
        w.busy = True
        acc = {"content": "", "reasoning": "", "usage": None, "t_think": None, "t_answer": None}
        t0 = time.time()
        last = [0.0]

        def on_delta():
            # Throttled: each sync sends the live message to the browser.
            if time.time() - last[0] > 0.08:
                w.live = {"active": True, "content": acc["content"], "reasoning": acc["reasoning"]}
                last[0] = time.time()

        w.live = {"active": True, "content": "", "reasoning": ""}
        error = None
        try:
            if http_get(HEALTH_URL)[0] != 200:
                raise RuntimeError("Server vLLM belum READY. Klik Start dan tunggu panel server READY.")
            system = (w.settings or {}).get("system", "").strip()
            prefix = [{"role": "system", "content": system}] if system else []
            _stream(prefix + STATE["api"], acc, on_delta)
        except urllib.error.HTTPError as e:
            error = f"vLLM menolak request (HTTP {e.code}): {e.read().decode('utf-8', 'replace')[:400]}"
        except Exception as e:
            error = str(e)

        stopped = STATE["stop"].is_set()
        if acc["content"] or acc["reasoning"]:
            assistant = {"role": "assistant", "content": acc["content"]}
            if acc["reasoning"]:
                assistant["reasoning_content"] = acc["reasoning"]
            STATE["api"].append(assistant)
        elif error:
            # Nothing came back: drop the user turn so the next request is not two user messages in a row.
            STATE["api"].pop()
        end = time.time()
        usage = acc["usage"] or {}
        tokens = usage.get("completion_tokens") or 0
        gen_start = acc["t_think"] or acc["t_answer"]
        stats = {
            "tokens": tokens,
            "tps": tokens / (end - gen_start) if tokens and gen_start and end > gen_start else None,
            "think_s": (acc["t_answer"] or end) - acc["t_think"] if acc["t_think"] else None,
            "total_s": end - t0,
            "stopped": stopped,
        }
        w.history = w.history + [
            {"role": "assistant", "content": acc["content"], "reasoning": acc["reasoning"], "stats": stats, "error": error}
        ]
        w.live = {}
        if usage:
            w.ctx = {"used": usage.get("total_tokens") or 0, "max": _max_context()}
        w.busy = False

    def _on_command(change):
        cmd = change["new"] or {}
        action = cmd.get("action")
        if action == "send":
            text = str(cmd.get("text") or "").strip()
            if text and not widget.busy:
                widget.busy = True
                mo.Thread(target=_run_turn, args=(text,), daemon=True).start()
        elif action == "stop":
            STATE["stop"].set()
        elif action == "clear" and not widget.busy:
            STATE["api"] = []
            widget.history = []
            widget.ctx = {"used": 0, "max": widget.ctx.get("max", 0)}
            widget.status = ""
        elif action == "save":
            widget.export = {
                "name": time.strftime("qwen-chat-%Y%m%d-%H%M%S.json"),
                "json": json.dumps(
                    {"version": 1, "api": STATE["api"], "display": widget.history, "settings": widget.settings},
                    ensure_ascii=False,
                    indent=1,
                ),
            }
        elif action == "load" and not widget.busy:
            data = cmd.get("data") or {}
            if not isinstance(data.get("api"), list) or not isinstance(data.get("display"), list):
                widget.status = "File bukan simpanan Qwen Chat."
                return
            STATE["api"] = data["api"]
            widget.history = data["display"]
            if isinstance(data.get("settings"), dict):
                widget.settings = data["settings"]
            widget.status = ""

    widget.observe(_on_command, names="command")
    chat = mo.ui.anywidget(widget)
    chat
    return


@app.cell(hide_code=True)
def _(mo):
    shell_cmd = mo.ui.text_area(value="nvidia-smi", label="Shell (debug)", full_width=True)
    shell_btn = mo.ui.run_button(label="Jalankan")
    mo.accordion({"Shell untuk debug": mo.vstack([shell_cmd, shell_btn])})
    return shell_btn, shell_cmd


@app.cell(hide_code=True)
def _(mo, run_live, shell_btn, shell_cmd):
    mo.stop(not shell_btn.value)
    run_live(shell_cmd.value, "Shell")
    return


if __name__ == "__main__":
    app.run()
