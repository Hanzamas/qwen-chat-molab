class Sys:
    """Process, HTTP and log helpers shared by the server cells and the chat."""

    ERROR_LINE = re.compile(r"\b\w*(Error|Exception)\b:|\bERROR\b|out of memory|CUDA error|error:")
    # vLLM's own wrapper messages only say "see root cause above".
    WRAPPERS = ("Engine core initialization failed", "Frontend process failed", "EngineCore failed to start")

    @staticmethod
    def run_live(cmd, title, log=None, env=None):
        """Run a shell command, streaming its last lines to `log(title, text, done)`. Returns the exit code."""
        log = log or Sys.cell_log
        proc = subprocess.Popen(cmd, shell=True, executable="/bin/bash", stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                start_new_session=True, env=env)
        lines, last = [], 0.0
        try:
            for line in proc.stdout:
                lines.append(line.rstrip("\n"))
                if time.time() - last > 0.5:
                    log(title, "\n".join(lines[-30:]), None)
                    last = time.time()
            code = proc.wait()
        finally:
            # An interrupted cell must not leave the command running in the background.
            if proc.poll() is None:
                os.killpg(proc.pid, signal.SIGTERM)
        log(title, "\n".join(lines[-30:]), code)
        return code

    @staticmethod
    def cell_log(title, text, code):
        status = "jalan..." if code is None else ("selesai" if code == 0 else f"GAGAL (exit {code})")
        mo.output.replace(mo.vstack([mo.md(f"**{title}**: {status}"), mo.plain_text(text)]))

    @staticmethod
    def http(method, url, body=None, headers=None, timeout=10):
        """Return (status, text). status is None when the request never got an answer."""
        data = json.dumps(body).encode() if isinstance(body, (dict, list)) else body
        hdr = {"User-Agent": CFG.USER_AGENT, **(headers or {})}
        if data is not None and "Content-Type" not in hdr:
            hdr["Content-Type"] = "application/json"
        try:
            req = urllib.request.Request(url, data=data, method=method, headers=hdr)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8", "replace")
        except Exception as e:
            return None, f"{type(e).__name__}: {e}"

    @staticmethod
    def get_json(url, headers=None, timeout=10):
        status, text = Sys.http("GET", url, headers=headers, timeout=timeout)
        if status != 200:
            raise RuntimeError(f"GET {url} -> {status}: {text[:300]}")
        return json.loads(text)

    @staticmethod
    def tail(path, n=30, max_bytes=65536):
        try:
            with open(path, "rb") as f:
                f.seek(0, os.SEEK_END)
                f.seek(max(0, f.tell() - max_bytes))
                return "\n".join(f.read().decode("utf-8", "replace").splitlines()[-n:])
        except FileNotFoundError:
            return "(belum ada log)"

    @staticmethod
    def log_errors(path, n=12):
        """Last distinct error lines of a log, without vLLM's generic wrapper messages."""
        found = []
        for line in Sys.tail(path, 5000, max_bytes=1 << 20).splitlines():
            if Sys.ERROR_LINE.search(line) and not any(w in line for w in Sys.WRAPPERS) and line not in found:
                found.append(line)
        return "\n".join(found[-n:])

    @staticmethod
    def pid_alive(pid_file):
        try:
            pid = int(Path(pid_file).read_text())
            os.killpg(pid, 0)
            return pid
        except (FileNotFoundError, ValueError, ProcessLookupError, PermissionError):
            return None

    @staticmethod
    def kill_group(pid_file, wait=60):
        """SIGTERM the process group in pid_file, SIGKILL after `wait` seconds. Returns the pid or None."""
        try:
            pid = int(Path(pid_file).read_text())
        except (FileNotFoundError, ValueError):
            return None
        for sig, limit in ((signal.SIGTERM, wait), (signal.SIGKILL, 10)):
            try:
                os.killpg(pid, sig)
            except ProcessLookupError:
                break
            for _ in range(limit):
                try:
                    os.waitpid(-pid, os.WNOHANG)
                except ChildProcessError:
                    pass
                try:
                    os.killpg(pid, 0)
                except ProcessLookupError:
                    break
                time.sleep(1)
            else:
                continue
            break
        Path(pid_file).unlink(missing_ok=True)
        return pid

    @staticmethod
    def gpu_line():
        r = subprocess.run("nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total --format=csv,noheader,nounits",
                           shell=True, capture_output=True, text=True)
        try:
            util, used, total = [float(x) for x in r.stdout.strip().split("\n")[0].split(",")]
            return {"util": util, "used_gb": used / 1024, "total_gb": total / 1024}
        except ValueError:
            return None

    @staticmethod
    def metrics(url):
        status, body = Sys.http("GET", url, timeout=2)
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
