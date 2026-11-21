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
app = marimo.App(width="full", app_title="Qwen Chat")


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
        base64,
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
    web search (Google, Bing, DuckDuckGo lewat Playwright), buka halaman web plus screenshot, memory, riwayat yang bisa
    dicari ulang, dan lampiran: gambar, video, PDF (teks + gambar halaman), DOCX, XLSX, PPTX, ZIP, dan file teks (maks 25 MB).

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
    return (
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
    # Playwright lives in the notebook kernel's Python (the agent tools run there), not in the vLLM venv.
    run_live(
        f"(uv pip install --python {sys.executable} playwright || {sys.executable} -m pip install -q playwright) "
        f"&& {sys.executable} -m playwright install --with-deps chromium firefox",
        "Install Playwright + Chromium + Firefox",
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
            "--enable-auto-tool-choice",
            "--tool-call-parser", "qwen3_coder",
            # A long chat replays every earlier image and video, so allow many per prompt.
            "--limit-mm-per-prompt", json.dumps({"image": 64, "video": 4}),
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
    return STORE, fts_query


@app.cell(hide_code=True)
def _(API_KEY, BASE_URL, HEALTH_URL, REASONING, ROOT_URL, SERVED_NAME, STORE, Path):
    import types
    import urllib.request as _request

    # The chat app lives in qwen_chat_app.py so a running notebook can update it by re-running this cell only.
    # A local copy next to the notebook wins; otherwise it is fetched from the GitHub repo.
    _local = Path(__file__).parent / "qwen_chat_app.py" if "__file__" in globals() else None
    if _local is not None and _local.exists():
        _src = _local.read_text(encoding="utf-8")
    else:
        _src = _request.urlopen(
            "https://raw.githubusercontent.com/Hanzamas/qwen-chat-molab/main/qwen_chat_app.py", timeout=30
        ).read().decode("utf-8")
    _app = types.ModuleType("qwen_chat_app")
    exec(compile(_src, "qwen_chat_app.py", "exec"), _app.__dict__)
    chat = _app.build(
        STORE,
        dict(
            api_key=API_KEY,
            base_url=BASE_URL,
            root_url=ROOT_URL,
            health_url=HEALTH_URL,
            served_name=SERVED_NAME,
            reasoning=REASONING,
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


if __name__ == "__main__":
    app.run()
