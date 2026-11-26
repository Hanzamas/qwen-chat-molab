import http.server as _hs


def _make_proxy(upstream, ctx_len):
    """HTTP handler that forwards to llama-server and adds what the chat expects from vLLM:
    max_model_len in /v1/models and /tokenize with chat messages."""

    class Proxy(_hs.BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *a):
            pass

        def _call(self, method, path, body=None):
            hdr = {k: v for k, v in self.headers.items() if k.lower() in ("authorization", "content-type", "accept")}
            return urllib.request.urlopen(urllib.request.Request(upstream + path, data=body, method=method, headers=hdr),
                                          timeout=7200)

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
                        m["max_model_len"] = ctx_len
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
                self.send_header("Transfer-Encoding", "chunked")
                self.end_headers()
                while True:
                    chunk = resp.read1(65536)
                    if not chunk:
                        break
                    self.wfile.write(b"%x\r\n%s\r\n" % (len(chunk), chunk))
                    self.wfile.flush()
                self.wfile.write(b"0\r\n\r\n")
            except urllib.error.HTTPError as e:
                self._json(e.code, {"error": e.read().decode("utf-8", "replace")[:2000]})
            except (BrokenPipeError, ConnectionResetError):
                pass
            except Exception as e:
                self._json(503, {"error": f"{type(e).__name__}: {e}"})

        def do_GET(self):
            self._handle("GET")

        def do_POST(self):
            self._handle("POST")

    return Proxy


class ServerManager:
    """Install, start and stop the model server (vLLM or llama.cpp) and the embedder.
    Used by the control cells and by the chat's model switcher."""

    def __init__(self):
        self.lock = threading.RLock()
        self.pid = {k: CFG.WORK / f"{k}.pid" for k in ("vllm", "llama", "embed")}
        self.logf = {k: CFG.LOG_DIR / f"{k}.log" for k in ("vllm", "llama", "embed")}
        self.state_file = CFG.WORK / "server.json"
        self.proxy = None
        self.procs = {}
        self.state = {"phase": "idle", "preset": None, "ctx": None, "mtp": False, "embed": False,
                      "warnings": [], "error": "", "started": None}
        try:
            saved = json.loads(self.state_file.read_text())
            if saved.get("preset") and any(Sys.pid_alive(self.pid[k]) for k in ("vllm", "llama")):
                self.state.update(saved)
                if saved.get("backend") == "llama" and Sys.pid_alive(self.pid["llama"]):
                    self._start_proxy(saved["ctx"])
        except (FileNotFoundError, ValueError):
            pass

    # ---------- info ----------

    def preset(self):
        return PRESETS.get(self.state.get("preset") or "")

    def current(self):
        """What the chat needs: URLs, the preset, the context length."""
        root = CFG.BASE_URL.rstrip("/").removesuffix("/v1") if CFG.BASE_URL else f"http://127.0.0.1:{CFG.PORT}"
        return {"root_url": root, "base_url": root + "/v1", "health_url": root + "/health",
                "preset_name": self.state.get("preset"), "preset": self.preset(), "ctx": self.state.get("ctx"),
                "phase": self.state.get("phase"), "warnings": list(self.state.get("warnings") or [])}

    def ready(self):
        cur = self.current()
        if CFG.BASE_URL:
            return Sys.http("GET", cur["health_url"], timeout=2)[0] == 200
        return self.state.get("phase") == "ready" and Sys.http("GET", cur["health_url"], timeout=2)[0] == 200

    def status(self):
        backend = (self.preset() or {}).get("backend")
        log = self.logf.get(backend) if backend else None
        return {**self.state, "backend": backend,
                "log": Sys.tail(log, 40) if log else "", "errors": Sys.log_errors(log) if log else "",
                "embed_ready": self.embed_ready()}

    def _save(self):
        self.state["backend"] = (self.preset() or {}).get("backend")
        self.state_file.write_text(json.dumps(self.state))

    # ---------- install ----------

    def install(self, log=None):
        """Compiler bits, browser tools, vLLM (own venv), llama.cpp (pinned release). Safe to run again."""
        log = log or Sys.cell_log
        gpu = subprocess.run("nvidia-smi --query-gpu=driver_version --format=csv,noheader", shell=True,
                             capture_output=True, text=True).stdout.strip()
        try:
            driver = int(gpu.split(".")[0])
        except ValueError:
            driver = 0
        if not driver:
            raise RuntimeError("GPU belum terdeteksi. Nyalakan GPU lewat notebook specs, lalu Install lagi.")
        # Triton needs cc, FlashInfer JIT needs ninja and links -lcudart from nvidia/cu13/lib64,
        # where the pip CUDA runtime only ships libcudart.so.13.
        Sys.run_live(
            "(command -v cc && command -v ninja) >/dev/null && echo 'cc + ninja ada' "
            "|| (apt-get -qq update && apt-get -qq install -y gcc g++ ninja-build >/dev/null && echo 'gcc + ninja terpasang') "
            "|| echo 'gcc/ninja gagal dipasang'; "
            "for D in /usr/local/lib/python3.*/site-packages/nvidia/cu13 "
            f"{CFG.VENV}/lib/python3.*/site-packages/nvidia/cu13; do "
            "[ -d \"$D\" ] || continue; L=$(find \"$D\" -name 'libcudart.so.1*' | head -1); "
            "[ -n \"$L\" ] && mkdir -p \"$D/lib64\" && ln -sf \"$L\" \"$D/lib64/libcudart.so\" && echo \"libcudart.so -> $L\"; done",
            "Persiapan compiler", log)
        pins = " ".join(f"'{k}=={v}'" for k, v in CFG.PIP_PINS.items())
        code = Sys.run_live(
            f"(uv pip install --python {sys.executable} {pins} || {sys.executable} -m pip install -q {pins}) "
            f"&& {sys.executable} -m playwright install --with-deps chromium firefox "
            f"&& {sys.executable} -m camoufox fetch",
            "Paket kernel + Camoufox + Playwright", log)
        if code != 0:
            raise RuntimeError("Gagal memasang paket kernel. Lihat log di atas.")
        if not CFG.VLLM_OK.exists():
            pkg = (f'"https://github.com/vllm-project/vllm/releases/download/v{CFG.VLLM_VERSION}/'
                   f'vllm-{CFG.VLLM_VERSION}+cu129-cp38-abi3-manylinux_2_28_x86_64.whl" --torch-backend=cu129'
                   if driver < 580 else f"vllm=={CFG.VLLM_VERSION} --torch-backend=cu130")
            code = Sys.run_live(
                f"set -e; uv venv --allow-existing {CFG.VENV}; uv pip install --python {CFG.VENV}/bin/python {pkg}; "
                f"{CFG.VLLM_BIN} download-kernels || echo 'download-kernels dilewati'",
                f"vLLM {CFG.VLLM_VERSION}", log)
            if code != 0:
                raise RuntimeError("Gagal memasang vLLM. Lihat log di atas.")
            CFG.VLLM_OK.touch()
        if not self.llama_bin():
            rel = Sys.get_json(f"https://api.github.com/repos/ggml-org/llama.cpp/releases/tags/{CFG.LLAMA_TAG}", timeout=30)
            urls = [a["browser_download_url"] for a in rel["assets"]
                    if CFG.LLAMA_ASSET in a["name"] and a["name"].endswith("-x64.tar.gz")]
            code = Sys.run_live(
                f"set -e; rm -rf {CFG.LLAMA_DIR}; mkdir -p {CFG.LLAMA_DIR}; cd {CFG.LLAMA_DIR}; "
                + "; ".join(f"curl -fsSL '{u}' | tar xz" for u in urls) + "; find . -name llama-server -type f",
                f"llama.cpp {CFG.LLAMA_TAG}", log)
            if code != 0 or not self.llama_bin():
                raise RuntimeError("Gagal memasang llama.cpp. Lihat log di atas.")
        return True

    def installed(self):
        return CFG.VLLM_OK.exists() and bool(self.llama_bin())

    def llama_bin(self):
        return next(iter(CFG.LLAMA_DIR.rglob("llama-server")), None) if CFG.LLAMA_DIR.exists() else None

    def _llama_env(self):
        libs = sorted({str(p.parent) for p in CFG.LLAMA_DIR.rglob("*.so*")})
        return {**os.environ, "LD_LIBRARY_PATH": ":".join(libs + [os.environ.get("LD_LIBRARY_PATH", "")])}

    # ---------- download ----------

    def fetch(self, repo, revision, filename=None, log=None):
        """Download a file (or a whole repo) at a pinned revision into MODEL_DIR. Returns the local path."""
        dest = CFG.MODEL_DIR / repo.replace("/", "__") / revision[:12]
        target = dest / filename if filename else dest
        marker = dest / f".ok-{hashlib.sha1((filename or '*').encode()).hexdigest()[:8]}"
        if marker.exists():
            return target
        call = (f"hf_hub_download('{repo}', '{filename}', revision='{revision}', local_dir='{dest}')" if filename
                else f"snapshot_download('{repo}', revision='{revision}', local_dir='{dest}')")
        code = Sys.run_live(
            f"{sys.executable} -c \"from huggingface_hub import hf_hub_download, snapshot_download; {call}; print('selesai')\"",
            f"Download {repo}{'/' + filename if filename else ''}", log)
        if code != 0:
            raise RuntimeError(f"Download {repo} gagal. Lihat log di atas.")
        marker.touch()
        return target

    # ---------- start / stop ----------

    def start(self, name, ctx, mtp=True, embed=False, log=None):
        """Download (if needed) and launch a preset. Returns once the process is running;
        a watcher thread marks it ready, or retries without MTP if the drafter makes it crash."""
        p = PRESETS[name]
        if ctx > p["yarn_max"]:
            raise ValueError(f"{name} maksimal {p['yarn_max']:,} token. Pilih konteks yang lebih kecil.")
        if not self.installed() and not CFG.BASE_URL:
            raise RuntimeError("Belum terpasang. Klik Install dulu.")
        with self.lock:
            self.stop(keep_embed=embed)
            self.state.update(phase="downloading", preset=name, ctx=ctx, mtp=bool(mtp and p.get("mtp")),
                              embed=embed, warnings=[], error="", started=time.time())
            self._save()
        try:
            if p["backend"] == "vllm":
                files = {"model": self.fetch(p["repo"], p["revision"], log=log)}
                if self.state["mtp"] and p.get("mtp") == "draft":
                    files["draft"] = self.fetch(*p["draft_hf"], log=log)
            else:
                files = {"model": self.fetch(p["repo"], p["revision"], p["file"], log=log)}
                if p.get("mmproj"):
                    files["mmproj"] = self.fetch(p["mmproj"][0], p["mmproj"][2], p["mmproj"][1], log=log)
                if self.state["mtp"] and p.get("mtp") == "draft":
                    files["draft"] = self.fetch(p["draft_gguf"][0], p["draft_gguf"][2], p["draft_gguf"][1], log=log)
            if embed:
                self.embed_start(log=log)
        except Exception as e:
            self.state.update(phase="failed", error=str(e))
            self._save()
            raise
        with self.lock:
            self._launch(p, files, ctx, self.state["mtp"])
        threading.Thread(target=self._watch, args=(p, files, ctx), daemon=True).start()
        return self.state

    def _vllm_cmd(self, p, files, ctx, mtp):
        yarn = ctx > p["max_ctx"]
        top = p["thinking"][-1]
        cmd = [str(CFG.VLLM_BIN), "serve", str(files["model"]), "--served-model-name", CFG.SERVED_NAME,
               "--host", "127.0.0.1", "--port", str(CFG.PORT), "--api-key", CFG.API_KEY,
               "--max-model-len", str(ctx),
               # One long conversation: all the memory, no batch sharing.
               "--gpu-memory-utilization", "0.92" if self.state.get("embed") else "0.94",
               "--max-num-seqs", "1",
               # Every turn resends the whole history; prefix caching reuses its KV instead of recomputing it.
               "--enable-prefix-caching", "--max-num-batched-tokens", "8192",
               "--reasoning-parser", p["reasoning_parser"], "--enable-auto-tool-choice",
               "--tool-call-parser", p["tool_parser"],
               "--default-chat-template-kwargs", json.dumps(thinking_kwargs(p, top)),
               # BF16 KV scored best at native context; with YaRN, FP8 KV scored the same (MRCR v2, n=15).
               "--kv-cache-dtype", p.get("kv_dtype") or ("fp8" if yarn else "auto")]
        if p.get("quantization"):
            cmd += ["--quantization", p["quantization"]]
        if yarn and p["family"] == "qwen":
            # YaRN override from the Qwen3.8 model card: factor 4.0 for 1M, 2.0 for ~524K.
            rope = {"mrope_interleaved": True, "mrope_section": [11, 11, 10], "rope_type": "yarn",
                    "rope_theta": 10000000, "partial_rotary_factor": 0.25,
                    "factor": 4.0 if ctx > 524288 else 2.0, "original_max_position_embeddings": 262144}
            cmd += ["--hf-overrides", json.dumps({"text_config": {"rope_parameters": rope}})]
        if mtp and p.get("mtp") == "heads":
            cmd += ["--speculative-config", json.dumps({"method": "mtp", "num_speculative_tokens": 3})]
        elif mtp and p.get("mtp") == "draft" and files.get("draft"):
            # gemma4_assistant drafter: vLLM maps it to gemma4_mtp, it reads the target's KV cache.
            cmd += ["--speculative-config", json.dumps({"model": str(files["draft"]), "num_speculative_tokens": 3})]
        return cmd

    def _llama_cmd(self, p, files, ctx, mtp):
        cmd = [str(self.llama_bin()), "-m", str(files["model"]), "--alias", CFG.SERVED_NAME,
               "--host", "127.0.0.1", "--port", str(CFG.LLAMA_PORT), "--api-key", CFG.API_KEY,
               "-c", str(ctx), "-ngl", "999", "-np", "1", "-fa", "on", "--jinja", "--reasoning-format", "deepseek",
               "-ctk", "q8_0", "-ctv", "q8_0", "--metrics"]
        if files.get("mmproj"):
            cmd += ["--mmproj", str(files["mmproj"])]
        if ctx > p["max_ctx"]:
            cmd += ["--rope-scaling", "yarn", "--rope-scale", "4" if ctx > 524288 else "2", "--yarn-orig-ctx", "262144"]
        if mtp and p.get("mtp") == "heads":
            cmd += ["--spec-type", "draft-mtp", "--spec-draft-n-max", "2", "-ctkd", "q8_0", "-ctvd", "q8_0"]
        elif mtp and p.get("mtp") == "draft" and files.get("draft"):
            cmd += ["--spec-type", "draft-mtp", "-md", str(files["draft"]), "-ngld", "all",
                    "--spec-draft-n-max", "3", "-ctkd", "q8_0", "-ctvd", "q8_0"]
        return cmd

    def _launch(self, p, files, ctx, mtp):
        backend = p["backend"]
        if backend == "vllm":
            cmd = self._vllm_cmd(p, files, ctx, mtp)
            env = {**os.environ, "VLLM_ALLOW_LONG_MAX_MODEL_LEN": "1", "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True",
                   # FlashInfer JIT looks for ninja and nvcc on PATH; molab does not export the CUDA bin dir.
                   "PATH": f"{CFG.VLLM_BIN.parent}:/usr/local/cuda/bin:{os.environ.get('PATH', '')}",
                   "CUDA_HOME": os.environ.get("CUDA_HOME", "/usr/local/cuda")}
        else:
            cmd = self._llama_cmd(p, files, ctx, mtp)
            env = self._llama_env()
        (CFG.LOG_DIR / f"{backend}.cmd").write_text(" ".join(cmd))
        proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=open(self.logf[backend], "w"),
                                stderr=subprocess.STDOUT, start_new_session=True, env=env)
        self.pid[backend].write_text(str(proc.pid))
        self.procs[backend] = proc
        if backend == "llama":
            self._start_proxy(ctx)
        self.state.update(phase="loading", mtp=mtp)
        self._save()

    def _start_proxy(self, ctx):
        if self.proxy:
            self.proxy.shutdown()
            self.proxy.server_close()
        self.proxy = _hs.ThreadingHTTPServer(("127.0.0.1", CFG.PORT), _make_proxy(f"http://127.0.0.1:{CFG.LLAMA_PORT}", ctx))
        threading.Thread(target=self.proxy.serve_forever, daemon=True).start()

    def _watch(self, p, files, ctx):
        backend = p["backend"]
        health = (f"http://127.0.0.1:{CFG.PORT}/health" if backend == "vllm"
                  else f"http://127.0.0.1:{CFG.LLAMA_PORT}/health")
        while self.state.get("preset") and PRESETS.get(self.state["preset"]) is p:
            proc = self.procs.get(backend)
            if proc is not None and proc.poll() is not None:
                if self.state.get("mtp"):
                    with self.lock:
                        self.state["warnings"].append("Server mati dengan MTP/drafter; dijalankan ulang tanpa MTP.")
                        (CFG.LOG_DIR / f"{backend}-mtp-failed.log").write_text(Sys.tail(self.logf[backend], 200))
                        self._launch(p, files, ctx, False)
                    continue
                self.state.update(phase="failed", error=Sys.log_errors(self.logf[backend]) or "server berhenti")
                self._save()
                return
            if Sys.http("GET", health, timeout=2)[0] == 200:
                self.state.update(phase="ready")
                self._save()
                return
            time.sleep(3)

    def stop(self, keep_embed=False):
        with self.lock:
            if self.proxy:
                self.proxy.shutdown()
                self.proxy.server_close()
                self.proxy = None
            stopped = [k for k in ("vllm", "llama") if Sys.kill_group(self.pid[k])]
            for k in stopped:
                self.procs.pop(k, None)
            if not keep_embed:
                self.embed_stop()
            self.state.update(phase="idle", preset=None, ctx=None, warnings=[], error="")
            self._save()
            return stopped

    # ---------- embedder ----------

    def embed_start(self, log=None):
        if self.embed_ready() or Sys.pid_alive(self.pid["embed"]):
            return
        path = self.fetch(EMBEDDER["repo"], EMBEDDER["revision"], EMBEDDER["file"], log=log)
        cmd = [str(self.llama_bin()), "-m", str(path), "--embedding", "--pooling", "last", "--host", "127.0.0.1",
               "--port", str(CFG.EMBED_PORT), "--api-key", CFG.API_KEY, "-ngl", "999", "-c", "8192", "-ub", "8192",
               "-np", "1"]
        proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=open(self.logf["embed"], "w"),
                                stderr=subprocess.STDOUT, start_new_session=True, env=self._llama_env())
        self.pid["embed"].write_text(str(proc.pid))
        self.procs["embed"] = proc
        self.state["embed"] = True

    def embed_stop(self):
        Sys.kill_group(self.pid["embed"])
        self.procs.pop("embed", None)
        self.state["embed"] = False

    def embed_url(self):
        return os.environ.get("QCHAT_EMBED_URL") or f"http://127.0.0.1:{CFG.EMBED_PORT}"

    def embed_ready(self):
        return Sys.http("GET", self.embed_url() + "/health", timeout=1)[0] == 200


SERVERS = ServerManager()
