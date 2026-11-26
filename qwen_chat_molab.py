# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "marimo",
#     "anywidget",
#     "traitlets",
#     "playwright",
# ]
# [tool.marimo.display]
# theme = "dark"
# ///

import marimo

__generated_with = "0.25.2"
app = marimo.App(width="full", app_title="Qwen Chat", auto_download=["html"])


@app.cell(hide_code=True)
def _():
    import marimo as mo
    import base64
    import json
    import os
    import re
    import secrets
    import signal
    import sqlite3
    import subprocess
    import sys
    import threading
    import time
    import urllib.error
    import urllib.parse
    import urllib.request
    from pathlib import Path

    return (
        Path,
        json,
        mo,
        os,
        re,
        secrets,
        signal,
        sqlite3,
        subprocess,
        sys,
        threading,
        time,
        urllib,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # Qwen Chat

    Chat panjang dengan **Qwen3.8-27B abliterated** (uncensored, FP8) di GPU molab lewat vLLM, lengkap dengan agent:
    web search (Google, Bing, DuckDuckGo lewat Playwright), buka halaman web, memory, dan riwayat yang bisa dicari ulang.

    1. Nyalakan GPU lewat *notebook specs*, lalu klik **Install** (vLLM + Playwright + browser).
    2. Klik **Start**, tunggu panel server `READY` (download sekitar 31 GB lalu load).
    3. Ngobrol di jendela chat di bawah.

    Semua chat, ringkasan, dan memory tersimpan di satu file SQLite. Isi workspace molab hilang saat notebook mati,
    jadi klik **Simpan** di chat untuk mengunduh file itu, dan **Muat** untuk melanjutkan di sesi berikutnya.
    Kalau notebook masih terang, ganti tema ke dark di pengaturan tampilan molab.
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
    DB_PATH = WORK / "qwen_chat.sqlite"
    MODEL = "munekazu/Huihui-Qwen3.8-27B-abliterated-FP8"
    SERVED_NAME = "qwen3.8-27b"
    # xhigh is the highest level Qwen3.8's chat template accepts.
    REASONING = "xhigh"
    PORT = 8000
    # QWEN_CHAT_BASE_URL lets the chat talk to another OpenAI-compatible server.
    BASE_URL = os.environ.get("QWEN_CHAT_BASE_URL", f"http://127.0.0.1:{PORT}/v1")
    ROOT_URL = BASE_URL.rsplit("/v1", 1)[0]
    HEALTH_URL = ROOT_URL + "/health"

    # The key stays inside the sandbox; /tmp keeps it stable across reruns.
    _key_file = WORK / "api_key"
    if not _key_file.exists():
        _key_file.write_text(secrets.token_hex(16))
    API_KEY = os.environ.get("QWEN_CHAT_API_KEY", _key_file.read_text().strip())

    # Popen handles started from this kernel; poll() reaps exited children.
    PROCS = {}
    # Sampler yang dikirim jendela chat. Diisi ulang setiap Start sesuai model yang sedang jalan,
    # jadi ganti model tidak perlu menjalankan ulang sel chat. Default: Qwen3.8 thinking (model card).
    SAMPLING = {"temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0.0}
    return (
        SAMPLING,
        API_KEY,
        BASE_URL,
        DB_PATH,
        HEALTH_URL,
        MODEL,
        PORT,
        PROCS,
        REASONING,
        ROOT_URL,
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
        value="512K (YaRN factor 2.0)",
        label="Konteks",
    )
    use_mtp = mo.ui.switch(value=True, label="MTP speculative decoding (generate lebih cepat, startup pertama compile kernel)")
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
def _(VENV, VLLM_BIN, VLLM_OK, install_btn, mo, run_live, subprocess, sys):
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
    # Playwright + Camoufox live in the notebook kernel's Python (agent tools), not in the vLLM venv.
    run_live(
        f"(uv pip install --python {sys.executable} 'camoufox[geoip]' || {sys.executable} -m pip install -q 'camoufox[geoip]') "
        f"&& {sys.executable} -m playwright install --with-deps chromium firefox "
        f"&& {sys.executable} -m camoufox fetch",
        "Install Camoufox + Playwright + Chromium + Firefox",
    )
    if VLLM_OK.exists():
        mo.output.replace(mo.md(f"vLLM sudah terpasang di `{VENV}`, Playwright siap."))
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
    SAMPLING,
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
        # vLLM menjalankan Qwen3.8-27B: kembalikan sampler thinking dari model card Qwen
        SAMPLING.clear()
        SAMPLING.update({"temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0.0})
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
            "--gpu-memory-utilization", "0.94",
            "--max-num-seqs", "1",
            # Every turn resends the whole history; prefix caching reuses its KV instead of recomputing it.
            "--enable-prefix-caching",
            # Larger prefill chunks speed up the first pass over a long history.
            "--max-num-batched-tokens", "8192",
            "--reasoning-parser", "qwen3",
            "--enable-auto-tool-choice",
            "--tool-call-parser", "qwen3_coder",
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
                "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True",
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


@app.cell
def _(PORT, Path, mo):
    LLAMA_DIR = Path.home() / "llama.cpp"
    LLAMA_LOG = Path("/tmp/qwen-chat/llama.log")
    LLAMA_PID = Path("/tmp/qwen-chat/llama.pid")
    LLAMA_PORT = PORT + 2  # llama-server di sini; proxy memakai PORT supaya jendela chat nggak perlu diubah
    _QWEN40_MMPROJ = ("https://huggingface.co/mradermacher/Qwen3.8-40B-Ultimate-Heretic-Uncensored-Build2-GGUF"
                      "/resolve/main/Qwen3.8-40B-Ultimate-Heretic-Uncensored-Build2.mmproj-Q8_0.gguf")
    # Sampler Dark-Gemistry dari model card Nimbz (temp 0.75-1.0, top_k 0, top_p 0.95, min_p 0.05,
    # tanpa repetition penalty/DRY karena melawan "suara" StyleTune di lm_head).
    _DG_SAMPLING = {"temperature": 1.0, "top_p": 0.95, "top_k": 0, "min_p": 0.05,
                    "repetition_penalty": 1.0, "frequency_penalty": 0, "presence_penalty": 0}
    # Dark-Gemistry adalah merge Gemma4ForConditionalGeneration dan masih membawa vision tower (356 tensor),
    # tapi repo GGUF-nya tidak menyertakan mmproj. Pakai mmproj Gemma 4 31B resmi dari ggml-org
    # (backbone merge-nya heretic-ara, turunan langsung Gemma 4 31B-it).
    _G4_MMPROJ = ("https://huggingface.co/ggml-org/gemma-4-31B-it-GGUF"
                  "/resolve/main/mmproj-gemma-4-31B-it-BF16.gguf")
    # gguf = "repo:quant". mmproj None = teks saja.
    # mtp = draft MTP (khusus Qwen3.8). max_ctx = konteks native; yarn_max = batas dengan YaRN
    # (Qwen3.8: resmi sampai 1M). yarn_exp = YaRN tidak resmi untuk model ini (Gemma 4 tidak punya resep YaRN).
    LLAMA_MODELS = {
        "Dark-Gemistry 31B HB16-Q8_0 (36.8GB, kualitas tertinggi)": {
            "gguf": "ReadyArt/Nimbz_Gemma-4-Dark-Gemistry-31B-GGUF:HB16-Q8_0", "mmproj": _G4_MMPROJ, "mtp": False,
            "max_ctx": 262144, "yarn_max": 524288, "yarn_exp": True, "sampling": _DG_SAMPLING},
        "Dark-Gemistry 31B HB16-Q6_K (29.7GB, lebih cepat)": {
            "gguf": "ReadyArt/Nimbz_Gemma-4-Dark-Gemistry-31B-GGUF:HB16-Q6_K", "mmproj": _G4_MMPROJ, "mtp": False,
            "max_ctx": 262144, "yarn_max": 524288, "yarn_exp": True, "sampling": _DG_SAMPLING},
        "Qwen3.8 40B Heretic Build2 i1-Q6_K (lama)": {
            "gguf": "mradermacher/Qwen3.8-40B-Ultimate-Heretic-Uncensored-Build2-i1-GGUF:Q6_K", "mmproj": _QWEN40_MMPROJ,
            # sampler dari card DavidAU (temp 1.0, top_k 64, top_p 0.95, min_p 0.05, rep pen 1.0).
            # Card menyebut maks 256K; YaRN 512K/1M ikut resep Qwen3.8 dasar.
            "mtp": True, "max_ctx": 262144, "yarn_max": 1000000, "yarn_exp": False,
            "sampling": {"temperature": 1.0, "top_p": 0.95, "top_k": 64, "min_p": 0.05,
                         "repetition_penalty": 1.0, "frequency_penalty": 0, "presence_penalty": 0}},
    }
    LLAMA_MMPROJ = _QWEN40_MMPROJ  # dipertahankan untuk kompatibilitas

    llama_model = mo.ui.dropdown(
        options=list(LLAMA_MODELS), value=next(iter(LLAMA_MODELS)), label="Model GGUF", full_width=True,
    )
    llama_gguf = mo.ui.text(
        value="", label="Atau repo:quant sendiri (kosong = pakai pilihan di atas)", full_width=True,
    )
    llama_ctx = mo.ui.dropdown(
        options={"128K": 131072, "262K (native)": 262144, "512K (YaRN; Gemma eksperimental)": 524288,
                 "1M (YaRN, Qwen saja)": 1000000},
        value="512K (YaRN; Gemma eksperimental)",
        label="Konteks llama.cpp",
    )
    llama_install_btn = mo.ui.run_button(label="Install llama.cpp")
    llama_start_btn = mo.ui.run_button(label="Start llama.cpp", kind="success")
    llama_stop_btn = mo.ui.run_button(label="Stop llama.cpp", kind="danger")
    mo.vstack([
        mo.md("### llama.cpp (GGUF). Stop vLLM dulu sebelum Start."),
        llama_model,
        llama_gguf,
        mo.hstack([llama_ctx, llama_install_btn, llama_start_btn, llama_stop_btn], justify="start"),
    ])
    return (
        LLAMA_DIR,
        LLAMA_LOG,
        LLAMA_MMPROJ,
        LLAMA_MODELS,
        LLAMA_PID,
        LLAMA_PORT,
        llama_ctx,
        llama_gguf,
        llama_model,
        llama_install_btn,
        llama_start_btn,
        llama_stop_btn,
    )


@app.cell
def _(LLAMA_DIR, json, llama_install_btn, mo, run_live):
    mo.stop(not llama_install_btn.value)

    import urllib.request as _ur

    _rels = json.load(_ur.urlopen("https://api.github.com/repos/ggml-org/llama.cpp/releases?per_page=10", timeout=30))
    _pick = lambda a: "ubuntu-cuda-13" in a["name"] and a["name"].endswith("-x64.tar.gz")
    _rel = next(r for r in _rels if any(_pick(a) for a in r["assets"]))
    _urls = [a["browser_download_url"] for a in _rel["assets"] if _pick(a)]
    run_live(
        f"set -e; rm -rf {LLAMA_DIR}; mkdir -p {LLAMA_DIR}; cd {LLAMA_DIR}; "
        + "; ".join(f"curl -fsSL '{u}' | tar xz" for u in _urls)
        + "; find . -name llama-server -type f",
        f"Install llama.cpp {_rel['tag_name']} (CUDA 13)",
    )
    return


@app.cell
def _(
    API_KEY,
    LLAMA_DIR,
    LLAMA_LOG,
    LLAMA_MODELS,
    LLAMA_PID,
    LLAMA_PORT,
    PORT,
    PROCS,
    Path,
    SAMPLING,
    SERVED_NAME,
    json,
    llama_ctx,
    llama_gguf,
    llama_model,
    llama_start_btn,
    mo,
    os,
    run_live,
    subprocess,
    sys,
    vllm_alive,
):
    mo.stop(not llama_start_btn.value)
    mo.stop(vllm_alive(), mo.callout(mo.md("vLLM masih jalan. Klik **Stop** vLLM dulu, GPU nggak cukup untuk dua server."), kind="danger"))
    mo.stop("llama" in PROCS and PROCS["llama"].poll() is None, mo.md("llama.cpp sudah jalan. Stop dulu kalau mau ganti model."))

    import threading as _threading
    import urllib.error as _uerr
    import urllib.request as _ureq
    from http.server import BaseHTTPRequestHandler as _Base, ThreadingHTTPServer as _Server

    _bin = next(LLAMA_DIR.rglob("llama-server"), None)
    mo.stop(_bin is None, mo.callout(mo.md("llama.cpp belum terpasang. Klik **Install llama.cpp**."), kind="danger"))

    _m = LLAMA_MODELS[llama_model.value]
    _spec = llama_gguf.value.strip() or _m["gguf"]
    mo.stop(
        llama_ctx.value > _m["yarn_max"],
        mo.callout(mo.md(f"Model ini maksimal {_m['yarn_max']:,} token. Pilih konteks yang lebih kecil."), kind="danger"),
    )
    _yarn_exp = llama_ctx.value > _m["max_ctx"] and _m["yarn_exp"]

    # Download paralel lewat huggingface_hub (hf_xet), jauh lebih cepat dari downloader bawaan llama.cpp.
    _gdir = Path.home() / "gguf"
    _repo, _, _quant = _spec.partition(":")
    _files = [s["rfilename"] for s in json.load(_ureq.urlopen(f"https://huggingface.co/api/models/{_repo}", timeout=30))["siblings"]]
    _q = _quant.lower()
    # cocokkan akhiran persis lalu ambil nama terpendek: "HB16-Q8_0" tidak boleh terambil "ATTN8-HB16-Q8_0",
    # "Q8_0" tidak boleh terambil "HB16-Q8_0"
    _cands = [f for f in _files if f.endswith(".gguf") and "mmproj" not in f.lower()
              and f.lower().rsplit("/", 1)[-1].endswith((f"-{_q}.gguf", f".{_q}.gguf", f"_{_q}.gguf"))]
    _gguf = min(_cands, key=len) if _cands else None
    mo.stop(_gguf is None, mo.callout(mo.md(f"Quant `{_quant}` nggak ditemukan di `{_repo}`."), kind="danger"))
    # mmproj: dari preset (Qwen 40B / Gemma 4 resmi), atau file mmproj di repo yang sama, atau tidak ada (teks saja)
    if _m["mmproj"] and not llama_gguf.value.strip():
        _mm_repo, _mm_file = _m["mmproj"].split("huggingface.co/", 1)[1].split("/resolve/main/", 1)
    else:
        _mm = sorted((f for f in _files if "mmproj" in f.lower() and f.endswith(".gguf")), key=len)
        _mm_repo, _mm_file = (_repo, _mm[0]) if _mm else (None, None)
    _dl = f"d('{_repo}', '{_gguf}', local_dir='{_gdir}'); " + (
        f"d('{_mm_repo}', '{_mm_file}', local_dir='{_gdir}'); " if _mm_file else "")
    _rc = run_live(
        f"({sys.executable} -c 'import hf_xet' 2>/dev/null || uv pip install --python {sys.executable} -U 'huggingface_hub[hf_xet]') && "
        f"{sys.executable} -c \"from huggingface_hub import hf_hub_download as d; {_dl}print('download selesai')\"",
        f"Download {_gguf}",
    )
    mo.stop(_rc != 0, mo.callout(mo.md("Download gagal. Lihat output di atas."), kind="danger"))

    _libdirs = sorted({str(p.parent) for p in LLAMA_DIR.rglob("*.so*")})
    _cmd = [
        str(_bin), "-m", str(_gdir / _gguf),
        "--alias", SERVED_NAME, "--host", "127.0.0.1", "--port", str(LLAMA_PORT), "--api-key", API_KEY,
        "-c", str(llama_ctx.value), "-ngl", "999", "-np", "1", "-fa", "on",
        "--jinja", "--reasoning-format", "deepseek",
        "-ctk", "q8_0", "-ctv", "q8_0",
    ]
    if _mm_file:
        _cmd += ["--mmproj", str(_gdir / _mm_file)]
    if llama_ctx.value > 262144:
        _cmd += ["--rope-scaling", "yarn", "--rope-scale", "4" if llama_ctx.value > 524288 else "2", "--yarn-orig-ctx", "262144"]
    if _m["mtp"]:
        # draft MTP hanya ada di Qwen3.8; GGUF Gemma 4 tidak punya kepala MTP
        _cmd += ["--spec-type", "draft-mtp", "--spec-draft-n-max", "2", "-ctkd", "q8_0", "-ctvd", "q8_0"]
    # jendela chat langsung memakai sampler model ini (tanpa menjalankan ulang sel chat)
    SAMPLING.clear()
    SAMPLING.update(_m["sampling"])
    _proc = subprocess.Popen(
        _cmd, stdin=subprocess.DEVNULL, stdout=open(LLAMA_LOG, "w"), stderr=subprocess.STDOUT, start_new_session=True,
        env={**os.environ, "LD_LIBRARY_PATH": ":".join(_libdirs + [os.environ.get("LD_LIBRARY_PATH", "")])},
    )
    LLAMA_PID.write_text(str(_proc.pid))
    PROCS["llama"] = _proc

    _up = f"http://127.0.0.1:{LLAMA_PORT}"
    _ctx = llama_ctx.value


    class _Proxy(_Base):
        """Teruskan ke llama-server; tambahkan max_model_len di /v1/models dan /tokenize ala vLLM."""

        def log_message(self, *a):
            pass

        def _call(self, method, path, body=None):
            hdr = {k: v for k, v in self.headers.items() if k.lower() in ("authorization", "content-type", "accept")}
            return _ureq.urlopen(_ureq.Request(_up + path, data=body, method=method, headers=hdr), timeout=3600)

        def _json(self, code, obj):
            data = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _handle(self, method):
            body = self.rfile.read(int(self.headers.get("Content-Length") or 0)) if method == "POST" else None
            try:
                if method == "GET" and self.path.startswith("/v1/models"):
                    d = json.loads(self._call("GET", self.path).read())
                    for m in d.get("data", []):
                        m["max_model_len"] = _ctx
                    return self._json(200, d)
                if method == "POST" and self.path == "/tokenize" and b'"messages"' in (body or b""):
                    req = json.loads(body)
                    req.pop("model", None)
                    prompt = json.loads(self._call("POST", "/apply-template", json.dumps(req).encode()).read())["prompt"]
                    toks = json.loads(self._call("POST", "/tokenize", json.dumps({"content": prompt}).encode()).read())["tokens"]
                    return self._json(200, {"count": len(toks)})
                resp = self._call(method, self.path, body)
                self.send_response(resp.status)
                self.send_header("Content-Type", resp.headers.get("Content-Type", "application/json"))
                self.end_headers()
                while True:
                    chunk = resp.read1(65536)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    self.wfile.flush()
            except _uerr.HTTPError as e:
                self._json(e.code, {"error": e.read().decode("utf-8", "replace")[:2000]})
            except (BrokenPipeError, ConnectionResetError):
                pass
            except Exception as e:
                self._json(503, {"error": f"{type(e).__name__}: {e}"})

        def do_GET(self):
            self._handle("GET")

        def do_POST(self):
            self._handle("POST")


    _srv = _Server(("127.0.0.1", PORT), _Proxy)
    _threading.Thread(target=_srv.serve_forever, daemon=True).start()
    PROCS["llama_proxy"] = _srv
    mo.output.append(mo.md(
        f"llama.cpp dimulai: `{_gguf}` (pid `{_proc.pid}`, port {LLAMA_PORT}), proxy di port {PORT}. "
        f"mmproj: {'`' + _mm_file + '`' if _mm_file else 'tidak (teks saja)'}. "
        f"Sampler chat: `{json.dumps(SAMPLING)}`. Pantau log di Sel 5."
        + ("\n\n**YaRN eksperimental:** Gemma 4 tidak punya resep YaRN resmi. Cek `n_ctx` di log, "
           "lalu uji needle-in-haystack sebelum percaya jawaban di atas 262K." if _yarn_exp else "")))
    return


@app.cell
def _(LLAMA_PID, PROCS, llama_stop_btn, mo, os, signal, time):
    mo.stop(not llama_stop_btn.value)
    _srv = PROCS.pop("llama_proxy", None)
    if _srv is not None:
        _srv.shutdown()
        _srv.server_close()
    try:
        _pid = int(LLAMA_PID.read_text())
        os.killpg(_pid, signal.SIGTERM)
        for _ in range(30):
            if "llama" in PROCS:
                PROCS["llama"].poll()
            try:
                os.killpg(_pid, 0)
            except ProcessLookupError:
                break
            time.sleep(1)
        else:
            os.killpg(_pid, signal.SIGKILL)
        LLAMA_PID.unlink(missing_ok=True)
        PROCS.pop("llama", None)
        mo.output.replace(mo.md(f"llama.cpp (pid `{_pid}`) dan proxy dihentikan."))
    except (FileNotFoundError, ProcessLookupError, ValueError):
        mo.output.replace(mo.md("llama.cpp tidak jalan."))
    return


@app.cell
def _(HEALTH_URL, LLAMA_LOG, PROCS, http_get, mo, tail, time):
    def _watch_llama():
        _me = mo.current_thread()
        while not _me.should_exit:
            _alive = "llama" in PROCS and PROCS["llama"].poll() is None
            _ready = _alive and http_get(HEALTH_URL)[0] == 200
            _badge = (mo.callout(mo.md("**llama.cpp READY**, jendela chat sudah bisa dipakai."), kind="success") if _ready
                      else mo.callout(mo.md("**llama.cpp loading / download…**"), kind="neutral") if _alive
                      else mo.callout(mo.md("llama.cpp tidak jalan."), kind="neutral"))
            mo.output.replace(mo.vstack([_badge, mo.accordion({"Log llama.cpp": mo.plain_text(tail(LLAMA_LOG, 40))})]))
            time.sleep(3)

    mo.Thread(target=_watch_llama, daemon=True).start()
    return


@app.cell(hide_code=True)
def _(
    HEALTH_URL,
    VLLM_LOG,
    VLLM_PID,
    http_get,
    log_errors,
    mo,
    tail,
    time,
    vllm_alive,
):
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
def _(ROOT_URL, http_get, mo, subprocess, time):
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
        status, body = http_get(ROOT_URL + "/metrics")
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
def _(DB_PATH, json, re, sqlite3, threading, time):
    _SCHEMA = """
    CREATE TABLE IF NOT EXISTS chats (
        id INTEGER PRIMARY KEY, title TEXT NOT NULL, system TEXT NOT NULL DEFAULT '',
        strip_upto INTEGER NOT NULL DEFAULT 0, created REAL NOT NULL, updated REAL NOT NULL
    );
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY, chat_id INTEGER NOT NULL, seq INTEGER NOT NULL, role TEXT NOT NULL,
        content TEXT NOT NULL DEFAULT '', reasoning TEXT NOT NULL DEFAULT '', tool_calls TEXT,
        tool_call_id TEXT, meta TEXT NOT NULL DEFAULT '{}', created REAL NOT NULL
    );
    CREATE INDEX IF NOT EXISTS messages_chat_seq ON messages (chat_id, seq);
    CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(content, reasoning, content='messages', content_rowid='id');
    CREATE TRIGGER IF NOT EXISTS messages_ai AFTER INSERT ON messages BEGIN
        INSERT INTO messages_fts(rowid, content, reasoning) VALUES (new.id, new.content, new.reasoning);
    END;
    CREATE TRIGGER IF NOT EXISTS messages_ad AFTER DELETE ON messages BEGIN
        INSERT INTO messages_fts(messages_fts, rowid, content, reasoning) VALUES ('delete', old.id, old.content, old.reasoning);
    END;
    CREATE TABLE IF NOT EXISTS summaries (
        id INTEGER PRIMARY KEY, chat_id INTEGER NOT NULL, upto_seq INTEGER NOT NULL, text TEXT NOT NULL, created REAL NOT NULL
    );
    CREATE TABLE IF NOT EXISTS memories (id INTEGER PRIMARY KEY, text TEXT NOT NULL, created REAL NOT NULL);
    CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(text, content='memories', content_rowid='id');
    CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
        INSERT INTO memories_fts(rowid, text) VALUES (new.id, new.text);
    END;
    CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
        INSERT INTO memories_fts(memories_fts, rowid, text) VALUES ('delete', old.id, old.text);
    END;
    """

    def fts_query(text):
        """Turn free text into an FTS5 OR-query of quoted words, so punctuation can never break MATCH."""
        words = re.findall(r"\w+", text or "")
        return " OR ".join(f'"{w}"' for w in words[:20])

    class Store:
        """Chats, every message, compaction summaries and memories in one SQLite file."""

        def __init__(self, path):
            self.path = path
            self.lock = threading.RLock()
            self._open()

        def _open(self):
            self.conn = sqlite3.connect(self.path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            self.conn.executescript(_SCHEMA)
            self.conn.commit()

        def q(self, sql, args=()):
            with self.lock:
                return [dict(r) for r in self.conn.execute(sql, args).fetchall()]

        def one(self, sql, args=()):
            rows = self.q(sql, args)
            return rows[0] if rows else None

        def x(self, sql, args=()):
            with self.lock:
                cur = self.conn.execute(sql, args)
                self.conn.commit()
                return cur.lastrowid

        def new_chat(self, title):
            now = time.time()
            return self.x("INSERT INTO chats (title, created, updated) VALUES (?, ?, ?)", (title, now, now))

        def add_message(self, chat_id, role, content="", reasoning="", tool_calls=None, tool_call_id=None, meta=None):
            with self.lock:
                seq = self.one("SELECT COALESCE(MAX(seq), 0) + 1 AS s FROM messages WHERE chat_id = ?", (chat_id,))["s"]
                self.x(
                    "INSERT INTO messages (chat_id, seq, role, content, reasoning, tool_calls, tool_call_id, meta, created) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        chat_id, seq, role, content or "", reasoning or "",
                        json.dumps(tool_calls) if tool_calls else None, tool_call_id,
                        json.dumps(meta or {}), time.time(),
                    ),
                )
                self.x("UPDATE chats SET updated = ? WHERE id = ?", (time.time(), chat_id))
                return seq

        def export_bytes(self):
            with self.lock:
                self.conn.commit()
                return self.conn.serialize()

        def import_bytes(self, data):
            """Replace the whole database with an uploaded file, after checking it is one of ours."""
            probe = sqlite3.connect(":memory:")
            probe.deserialize(data)
            names = {r[0] for r in probe.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
            probe.close()
            if not {"chats", "messages", "memories"} <= names:
                raise ValueError("File bukan database Qwen Chat.")
            with self.lock:
                self.conn.close()
                self.path.write_bytes(data)
                self._open()

    STORE = Store(DB_PATH)
    return (STORE,)


@app.cell(hide_code=True)
def _(
    API_KEY,
    BASE_URL,
    HEALTH_URL,
    REASONING,
    ROOT_URL,
    SAMPLING,
    SERVED_NAME,
    STORE,
    re,
    urllib,
):
    import types as _types

    _src = urllib.request.urlopen(
        "https://raw.githubusercontent.com/Hanzamas/qwen-chat-molab/376cee2d6bb1d2f8ab15523c8eb0aaaa805a9191/qwen_chat_app.py",
        timeout=30,
    ).read().decode("utf-8")

    # Kembalikan browser stealth + Camoufox yang dihapus dari file remote.
    _STEALTH = r'''import os
    import random

    _CHROMIUM_UA = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    ]
    _FIREFOX_UA = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:127.0) Gecko/20100101 Firefox/127.0",
        "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0",
    ]

    # Menyamar sebagai browser manusia: hapus flag otomasi, navigator.webdriver,
    # user-agent "Headless", dan isi hal-hal yang biasanya dipakai untuk deteksi bot.
    _STEALTH_JS = r"""
    () => {
      const def = Object.defineProperty;
      try { def(Navigator.prototype, 'webdriver', { get: () => undefined }); } catch (e) {}
      try { def(navigator, 'webdriver', { get: () => undefined }); } catch (e) {}
      try { def(navigator, 'languages', { get: () => ['en-US', 'en'] }); } catch (e) {}
      try { def(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] }); } catch (e) {}
      try { def(navigator, 'hardwareConcurrency', { get: () => 8 }); } catch (e) {}
      try { def(navigator, 'deviceMemory', { get: () => 8 }); } catch (e) {}
      // Headless Chromium kadang tidak punya window.chrome, jadi dibuatkan yang minimal.
      if (!window.chrome) window.chrome = { runtime: {}, csi() {}, loadTimes() {} };
      if (window.navigator.permissions && window.navigator.permissions.query) {
        const q = window.navigator.permissions.query.bind(window.navigator.permissions);
        window.navigator.permissions.query = (p) =>
          p && p.name === 'notifications' ? Promise.resolve({ state: Notification.permission }) : q(p);
      }
    }
    """

    def _launch(p, browser):
        if browser == "firefox":
            return p.firefox.launch(headless=True)
        return p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-features=IsolateOrigins,site-per-process",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-infobars",
                "--hide-scrollbars",
                "--mute-audio",
                "--disable-extensions",
            ],
            ignore_default_args=["--enable-automation"],
        )

    def _new_page(b, browser):
        """Buat halaman dengan user-agent manusia dan patch anti-deteksi."""
        ua = random.choice(_FIREFOX_UA if browser == "firefox" else _CHROMIUM_UA)
        ctx = b.new_context(
            locale="en-US",
            timezone_id="Asia/Jakarta",
            user_agent=ua,
            viewport={"width": random.choice([1366, 1440, 1536, 1920]), "height": random.choice([768, 900, 1080])},
            screen={"width": 1920, "height": 1080},
            color_scheme="light",
            is_mobile=False,
            has_touch=False,
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
        )
        ctx.add_init_script(_STEALTH_JS)
        return ctx.new_page()

    def _camoufox_page():
        """Buka Camoufox (fork Firefox anti-detect). Balikan (cleanup, page)."""
        from camoufox.sync_api import Camoufox

        env = dict(os.environ)
        # Firefox/Camoufox menolak start kalau $HOME bukan milik uid kita (molab jalan sebagai root).
        if os.getuid() == 0 and os.path.isdir("/root"):
            env["HOME"] = "/root"
        # Sandbox yang kadang bikin Firefox crash di container.
        env.setdefault("MOZ_DISABLE_CONTENT_SANDBOX", "1")
        env.setdefault("MOZ_DISABLE_RDD_SANDBOX", "1")
        env.setdefault("MOZ_DISABLE_GMP_SANDBOX", "1")

        cam = Camoufox(
            headless=True,
            humanize=True,
            geoip=True,
            block_webrtc=True,
            # WASM canvas-noise bisa crash di headless pada sebagian kernel/host.
            canvas_noise=False,
            env=env,
        )
        b = cam.__enter__()
        try:
            page = b.new_page()
        except BaseException:
            cam.__exit__(*sys.exc_info())
            raise
        return (lambda: cam.__exit__(None, None, None)), page


    def _pw_page(browser):
        """Buka Playwright chromium/firefox stealth lama. Balikan (cleanup, page)."""
        from playwright.sync_api import sync_playwright

        p = sync_playwright().start()
        try:
            b = _launch(p, browser)
            page = _new_page(b, browser)
        except BaseException:
            p.stop()
            raise

        def cleanup():
            try:
                b.close()
            finally:
                p.stop()

        return cleanup, page


    def _launch_page(browser):
        """Return (cleanup, page, warning). Camoufox diutamakan; fallback ke stealth Chromium."""
        if browser == "camoufox":
            try:
                cleanup, page = _camoufox_page()
                return cleanup, page, ""
            except Exception as e:
                warn = f"camoufox gagal start ({type(e).__name__}: {str(e)[:120]}); pakai chromium"
                cleanup, page = _pw_page("chromium")
                return cleanup, page, warn
        cleanup, page = _pw_page(browser)
        return cleanup, page, ""


    def web_search(query, engine="auto", max_results=8, browser="camoufox"):
        """Search lewat browser stealth (default Camoufox). CAPTCHA = engine itu gagal, lanjut engine berikutnya."""
        order = ["google", "bing"] if engine in (None, "", "auto") else [engine]
        cleanup, page, warn = _launch_page(browser)
        notes = [warn] if warn else []
        try:
            for eng in order:
                if eng not in _SEARCH_URL:
                    notes.append(f"{eng}: mesin tidak dikenal")
                    continue
                try:
                    page.goto(_SEARCH_URL[eng].format(urllib.parse.quote(query)), wait_until="domcontentloaded", timeout=30000)
                    page.wait_for_timeout(2500)
                    if "/sorry/" in page.url or "consent." in page.url or "unusual traffic" in page.content().lower():
                        notes.append(f"{eng}: diblokir (CAPTCHA/consent)")
                        continue
                    rows = page.evaluate(_SEARCH_JS[eng])
                except Exception as e:
                    notes.append(f"{eng}: {type(e).__name__}: {str(e)[:150]}")
                    continue
                if rows:
                    return json.dumps(
                        {"engine": eng, "query": query, "results": rows[: int(max_results)], "notes": notes},
                        ensure_ascii=False,
                    )
                notes.append(f"{eng}: tidak ada hasil (mungkin diblokir atau tata letak halaman berubah)")
        finally:
            cleanup()
        return json.dumps({"error": "Semua mesin pencari gagal.", "notes": notes}, ensure_ascii=False)


    def visit(url, max_chars=15000, browser="camoufox", screenshot=False):
        """Buka halaman dengan JavaScript aktif dan kembalikan teks yang terbaca."""
        if not re.match(r"^https?://", url or ""):
            return json.dumps({"error": "URL harus diawali http:// atau https://"}), None
        cleanup, page, warn = _launch_page(browser)
        try:
            resp = page.goto(url, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(1500)
            final_url, title = page.url, page.title()
            text = page.evaluate("() => document.body ? document.body.innerText : ''")
            shot = page.screenshot(type="jpeg", quality=70) if screenshot else None
        finally:
            cleanup()
        text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text or "").strip()
        limit = max(1000, min(int(max_chars), 60000))
        out = {
            "url": final_url,
            "status": resp.status if resp else None,
            "title": title,
            "text": text[:limit],
            "truncated": len(text) > limit,
            "notes": [warn] if warn else [],
        }
        if shot:
            out["screenshot"] = "terlampir sebagai gambar"
        return json.dumps(out, ensure_ascii=False), shot'''

    _src = re.sub(
        r"def _launch\(p, browser\):.*?(?=\ndef _fn\()",
        lambda _m: _STEALTH,
        _src,
        count=1,
        flags=re.DOTALL,
    )
    _src = _src.replace('"browser": "chromium"', '"browser": "camoufox"')
    _src = _src.replace('s.browser || "chromium"', 's.browser || "camoufox"')
    _src = _src.replace('.get("browser", "chromium")', '.get("browser", "camoufox")')
    _src = _src.replace(
        '<option value="chromium">Chromium</option><option value="firefox">Firefox</option>',
        '<option value="chromium">Chromium</option><option value="firefox">Firefox</option><option value="camoufox">Camoufox</option>',
    )
    # Buang duckduckgo dari daftar engine (ke-block di IP datacenter ini)
    _src = _src.replace('engine \'auto\' tries Google, then Bing, then DuckDuckGo.', 'engine \'auto\' tries Google, then Bing.')
    _src = _src.replace('["auto", "google", "bing", "duckduckgo"]', '["auto", "google", "bing"]')

    # ============================================================
    # PATCH 1: Sampling parameters — dari dict SAMPLING yang diisi sel Start (vLLM / llama.cpp)
    # sesuai model yang sedang jalan. Patch lama menyisipkan sampler SEBELUM
    # "temperature": 1.0, "top_k": 20 di stream(), sehingga tertimpa dan tidak pernah berlaku.
    # ============================================================
    _old_sampling = '"temperature": 1.0, "top_p": 0.95, "top_k": 20, "chat_template_kwargs": template_kwargs,'
    assert _old_sampling in _src, "struktur stream() di qwen_chat_app.py berubah; patch sampler perlu disesuaikan"
    _src = _src.replace(_old_sampling, '**SAMPLING, "chat_template_kwargs": template_kwargs,', 1)

    # Gemma 4 (Dark-Gemistry) membaca enable_thinking, Qwen3.8 membaca reasoning_effort: kirim keduanya.
    _old_kwargs = 'template_kwargs = {"reasoning_effort": reasoning, "preserve_thinking": True}'
    assert _old_kwargs in _src, "template_kwargs di qwen_chat_app.py berubah; patch thinking perlu disesuaikan"
    _src = _src.replace(
        _old_kwargs,
        'template_kwargs = {"reasoning_effort": reasoning, "enable_thinking": True, "preserve_thinking": True}', 1)


    # ============================================================
    # PATCH 2: Fix reasoning — pakai xhigh, bukan low
    # ============================================================
    # (diperbaiki di build() call di bawah)


    # ============================================================
    # PATCH 3: Tombol Compact manual
    # ============================================================

    # 3a. Tambah tombol "Compact" di top bar (frontend ESM)
    _src = _src.replace(
        '<button type="button" data-act="settings">Pengaturan</button>',
        '<button type="button" data-act="settings">Pengaturan</button>'
        '<button type="button" data-act="compact" title="Padatkan konteks lama jadi ringkasan" '
        'style="font-size:12px;padding:2px 10px">Compact</button>',
    )

    # 3b. Tambah click handler untuk "compact" di frontend
    _src = _src.replace(
        'else if (act === "toggle") el.classList.toggle("qc-side-open");',
        'else if (act === "toggle") el.classList.toggle("qc-side-open");\n'
        '    else if (act === "compact") command("compact");',
    )

    # 3c. maybe_compact menerima force=True dan melewati dua pengecekan ambang batas
    _src = re.sub(r'def maybe_compact\(([^)]*)\):', r'def maybe_compact(\1, force=False):', _src)
    _src = _src.replace(
        'if state["last_used"] and state["last_used"] < 0.7 * maxc:',
        'if not force and state["last_used"] and state["last_used"] < 0.7 * maxc:',
    )
    _src = _src.replace('if used < COMPACT_AT * maxc:', 'if not force and used < COMPACT_AT * maxc:')
    print("maybe_compact patched:", "force=False" in _src, "| threshold patched:", "not force and used" in _src)

    # 3d. Handler tombol Compact: jalan di thread supaya kernel nggak beku selama meringkas
    _compact_handler_code = '''
        def _compact_handler(change):
            cmd = change["new"] or {}
            if cmd.get("action") != "compact":
                return
            if widget.busy:
                widget.status = "Tunggu balasan selesai dulu."
                return
            if not widget.chat_id:
                widget.status = "Buka chat dulu sebelum compact."
                return

            def _run():
                widget.busy = True
                widget.status = "Compacting..."
                try:
                    tools = TOOLS if (widget.settings or {}).get("tools", True) else None
                    used = maybe_compact(widget.chat_id, tools, lambda m: setattr(widget, "status", m), force=True)
                    widget.history = load_display(widget.chat_id)
                    state["last_used"] = used or 0
                    widget.ctx = {"used": state["last_used"], "max": max_context()}
                    widget.status = ""
                except Exception as e:
                    widget.status = f"Compact gagal: {type(e).__name__}: {e}"
                finally:
                    widget.busy = False

            mo.Thread(target=_run, daemon=True).start()

        widget.observe(_compact_handler, names="command")

    '''
    _src = _src.replace(
        '    def on_settings(',
        _compact_handler_code + '    def on_settings(',
    )

    # PATCH 4: setiap ringkasan compaction (tahap 2) juga disimpan ke memory lintas chat
    _src = _src.replace(
        '            store.x("INSERT INTO summaries (chat_id, upto_seq, text, created) VALUES (?, ?, ?, ?)", (chat_id, cutoff, text, time.time()))',
        '            store.x("INSERT INTO summaries (chat_id, upto_seq, text, created) VALUES (?, ?, ?, ?)", (chat_id, cutoff, text, time.time()))\n'
        '            _title = store.one("SELECT title FROM chats WHERE id = ?", (chat_id,))\n'
        '            store.x("INSERT INTO memories (text, created) VALUES (?, ?)",\n'
        '                    (f"[Ringkasan chat \'{_title[\'title\'] if _title else chat_id}\', pesan #1-#{cutoff}]\\n" + text, time.time()))',
    )
    print("compaction -> memory patched:", "INSERT INTO memories (text, created)" in _src and "Ringkasan chat" in _src)

    # PATCH 5a: aturan tetap untuk chat baru
    _RULES = """# Aturan penulisan
    - Kalimat bahasa Jerman ditulis UTUH dalam satu tanda kutip. JANGAN dipecah per kata atau disambung pakai "...".
    - Terjemahannya SATU kali untuk seluruh kalimat, dalam kurung, tepat setelah tanda kutip penutup.
      Benar: "Das ist ein guter Indikator." (Itu indikator yang bagus.)
      Salah: "Das..." (Itu) "...ist..." (adalah) "...ein..." (satu)
    - Jangan pernah menulis terjemahan dua kali. "(Iya.) (Iya)" salah, "(Iya.)" benar.
    - Kalimat yang sudah berbahasa Indonesia, nama orang, dan nama tempat tidak diterjemahkan.
    - Pakai bahasa Jerman yang benar (misalnya "der Beste", bukan "gutesten").
    - Kalau ada pola salah di pesan-pesan sebelumnya, jangan ditiru."""
    _src = _src.replace("BASE_SYSTEM = ", "CHAT_RULES = " + repr(_RULES) + "\n\nBASE_SYSTEM = ", 1)

    # PATCH 5b: tabel snapshot memory per chat
    _src = _src.replace(
        "CREATE INDEX IF NOT EXISTS attachments_msg ON attachments (message_id);",
        "CREATE INDEX IF NOT EXISTS attachments_msg ON attachments (message_id);\n"
        "CREATE TABLE IF NOT EXISTS chat_memory_snapshot (chat_id INTEGER PRIMARY KEY, text TEXT NOT NULL);",
    )

    # PATCH 5c: aturan + memory dibekukan ke system prompt saat chat baru dimulai
    _src = _src.replace(
        r'''        if summ:
                parts.append(''',
        r'''        _snap = store.one("SELECT text FROM chat_memory_snapshot WHERE chat_id = ?", (chat_id,))
            if _snap is None:
                # Frozen once per chat so the system prompt (and the server's prefix cache) never changes mid-chat.
                _n = store.one("SELECT COUNT(*) AS n FROM messages WHERE chat_id = ?", (chat_id,))["n"]
                _txt = ""
                if _n <= 1:
                    _rows = store.q("SELECT id, text FROM memories ORDER BY id DESC LIMIT 40")
                    _mem = "\n".join(f"- (#{r['id']}) {r['text'][:800]}" for r in reversed(_rows))[:12000]
                    _txt = CHAT_RULES + ("\n\n# Memory dari chat sebelumnya (dibekukan saat chat ini dimulai)\n" + _mem if _mem else "")
                store.x("INSERT INTO chat_memory_snapshot (chat_id, text) VALUES (?, ?)", (chat_id, _txt))
                _snap = {"text": _txt}
            if _snap["text"]:
                parts.append(_snap["text"])
            if summ:
                parts.append(''',
        1,
    )

    # PATCH 5d: memory relevan disuntik ke tiap pesan (disimpan bersama pesan, tidak tampil di layar)
    _src = _src.replace(
        r'''        full = "\n\n".join([text] + blocks).strip()''',
        r'''        _mq = fts_query(text)
            _hits = store.q(
                "SELECT m.id, m.text FROM memories_fts f JOIN memories m ON m.id = f.rowid "
                "WHERE memories_fts MATCH ? ORDER BY bm25(memories_fts) LIMIT 5", (_mq,)) if _mq else []
            if _hits:
                blocks = blocks + ["[Memory relevan, diambil otomatis, bukan tulisan pengguna]\n" + "\n".join(f"- (#{r['id']}) {r['text'][:800]}" for r in _hits)]
            full = "\n\n".join([text] + blocks).strip()''',
        1,
    )
    print("patch 5:", "CHAT_RULES = " in _src, "chat_memory_snapshot" in _src, "Memory relevan" in _src)

    # PATCH 6a: helper dedup + pembatasan ringkasan di memory
    _MEM_HELPERS = r'''
    def _norm_words(s):
        return set(re.findall(r"\w+", (s or "").lower()))


    def prune_summary_memories(store, keep=30):
        """Keep only the newest compaction summaries in memory; facts are never pruned automatically."""
        store.x(
            "DELETE FROM memories WHERE text LIKE '[Ringkasan chat %' AND id NOT IN "
            "(SELECT id FROM memories WHERE text LIKE '[Ringkasan chat %' ORDER BY id DESC LIMIT ?)",
            (keep,),
        )


    def memory_save_dedup(store, text):
        """Insert a memory unless an existing one says nearly the same thing (word overlap >= 80%)."""
        words = _norm_words(text)
        q = fts_query(text)
        cands = store.q(
            "SELECT m.id, m.text FROM memories_fts f JOIN memories m ON m.id = f.rowid "
            "WHERE memories_fts MATCH ? ORDER BY bm25(memories_fts) LIMIT 10", (q,)) if q else []
        for c in cands:
            other = _norm_words(c["text"])
            if words and other and len(words & other) / len(words | other) >= 0.8:
                return json.dumps({"duplicate_of": c["id"], "note": "Sudah ada memory yang sama; tidak disimpan ulang."})
        mid = store.x("INSERT INTO memories (text, created) VALUES (?, ?)", (text, time.time()))
        return json.dumps({"saved": mid})
    '''
    _src = _src.replace("class QwenChat(anywidget.AnyWidget):", _MEM_HELPERS + "\n\nclass QwenChat(anywidget.AnyWidget):", 1)

    # PATCH 6b: tool memory_save pakai dedup
    _src = _src.replace(
        r'''            elif name == "memory_save":
                    mid = store.x("INSERT INTO memories (text, created) VALUES (?, ?)", (str(args["text"]).strip(), time.time()))
                    res = json.dumps({"saved": mid})''',
        r'''            elif name == "memory_save":
                    res = memory_save_dedup(store, str(args["text"]).strip())''',
        1,
    )

    # PATCH 6c: bersihkan ringkasan lama tiap kali chat dibuka dan setelah compaction menyimpan ringkasan
    _src = _src.replace("    ensure_schema()\n    widget = QwenChat()", "    ensure_schema()\n    prune_summary_memories(store)\n    widget = QwenChat()", 1)
    _src = _src.replace(
        "pesan #1-#{cutoff}]\\n\" + text, time.time()))",
        "pesan #1-#{cutoff}]\\n\" + text, time.time()))\n            prune_summary_memories(store)",
        1,
    )

    # PATCH 6d: snapshot chat baru = 60 fakta terbaru (dipendekkan) + 3 ringkasan terakhir
    _src = _src.replace(
        r'''                _rows = store.q("SELECT id, text FROM memories ORDER BY id DESC LIMIT 40")
                    _mem = "\n".join(f"- (#{r['id']}) {r['text'][:800]}" for r in reversed(_rows))[:12000]''',
        r'''                _facts = store.q("SELECT id, text FROM memories WHERE text NOT LIKE '[Ringkasan chat %' ORDER BY id DESC LIMIT 60")
                    _sums = store.q("SELECT id, text FROM memories WHERE text LIKE '[Ringkasan chat %' ORDER BY id DESC LIMIT 3")
                    _mem = "\n".join(f"- (#{r['id']}) {r['text'][:500]}" for r in reversed(_facts))[:9000]
                    if _sums:
                        _mem += "\n\n" + "\n\n".join(r["text"][:1500] for r in reversed(_sums))''',
        1,
    )
    print("patch 6:", "def memory_save_dedup" in _src, "memory_save_dedup(store, str(args" in _src,
          "prune_summary_memories(store)\n    widget" in _src, "_facts = store.q" in _src)

    # PATCH 7a: hapus terjemahan kurung yang dobel sebelum jawaban disimpan,
    # supaya riwayat chat nggak berisi contoh salah yang ditiru model.
    _DEDUPE = r'''
    def dedupe_parens(text):
        """Drop a parenthetical that repeats the one right before it, e.g. "(Iya.) (Iya)" -> "(Iya.)"."""
        parts = re.split(r"(\([^()\n]{1,300}\))", text or "")
        out, last = [], None
        for p in parts:
            if p.startswith("(") and p.endswith(")"):
                norm = re.sub(r"[\s.!?,…]+", " ", p[1:-1]).strip().lower()
                if norm == last:
                    while out and not out[-1].strip():
                        out.pop()
                    continue
                last = norm
            elif p.strip():
                last = None
            out.append(p)
        return "".join(out)
    '''
    _src = _src.replace("class QwenChat(anywidget.AnyWidget):", _DEDUPE + "\n\nclass QwenChat(anywidget.AnyWidget):", 1)
    _src = _src.replace(
        'add_message(chat_id, "assistant", acc["content"], acc["reasoning"], calls or None)',
        'add_message(chat_id, "assistant", dedupe_parens(acc["content"]), acc["reasoning"], calls or None)',
        1,
    )



    _app = _types.ModuleType("qwen_chat_app")
    _app.__dict__["SAMPLING"] = SAMPLING  # dict yang sama: diubah sel Start, langsung terbaca stream()
    exec(compile(_src, "qwen_chat_app.py", "exec"), _app.__dict__)


    # Perbaiki selector Google: hasil sekarang pakai redirect google.com/goto,
    # jadi jangan buang link ber-host google.com.
    _app._SEARCH_JS['google'] = '''() => [...document.querySelectorAll('a h3')].map((h) => {
        const a = h.closest('a');
        const box = a.closest('div[data-hveid]') || a.parentElement;
        const snippet = (box ? box.innerText : '').replace(h.innerText, '').trim().slice(0, 300);
        return { title: h.innerText, url: a ? a.href : null, snippet };
    }).filter((r) => r.url && r.url.startsWith('http'))'''

    chat = _app.build(
        STORE,
        dict(
            api_key=API_KEY,
            base_url=BASE_URL,
            root_url=ROOT_URL,
            health_url=HEALTH_URL,
            served_name=SERVED_NAME,
            reasoning=REASONING,  # xhigh, dari cell vblA
        ),
    )
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


@app.cell
def _(PROCS, mo):
    import os as _os

    def _size(path):
        total = 0
        for root, _, files in _os.walk(_os.path.expanduser(path)):
            for f in files:
                try:
                    total += _os.path.getsize(_os.path.join(root, f))
                except OSError:
                    pass
        return f"{total / 1e9:.2f} GB"

    _p = PROCS.get("llama")
    _lines = [
        f"proses llama-server: {'hidup' if _p and _p.poll() is None else 'MATI, exit ' + str(_p.poll() if _p else None)}",
        f"~/.cache/llama.cpp: {_size('~/.cache/llama.cpp')}",
        f"~/.cache/huggingface: {_size('~/.cache/huggingface')}",
        f"/tmp/qwen-chat/llama.log: {_os.path.getsize('/tmp/qwen-chat/llama.log') if _os.path.exists('/tmp/qwen-chat/llama.log') else 0} byte",
    ]
    mo.plain_text("\n".join(_lines))
    return


if __name__ == "__main__":
    app.run()
