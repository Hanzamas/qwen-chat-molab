import asyncio as _asyncio
import queue as _queue


class _FreshThread(Exception):
    """The browser thread can no longer start Playwright; run the job again on a new thread."""


class WebTools:
    """web_search / visit through a browser that stays open (Camoufox first, stealth Chromium as fallback),
    plus wiki_search / wiki_read through the Wikipedia API (no key, no CAPTCHA).
    Playwright's sync API must stay on the thread that created it, so one worker thread owns the browser."""

    SEARCH_URL = {"google": "https://www.google.com/search?hl=en&num=10&q={}",
                  "bing": "https://www.bing.com/search?setlang=en&q={}"}
    SEARCH_JS = {
        # Google results now link through google.com redirects, so google.com hosts are not filtered out.
        "google": """() => [...document.querySelectorAll('a h3')].map((h) => {
            const a = h.closest('a');
            const box = a.closest('div[data-hveid]') || a.parentElement;
            const snippet = (box ? box.innerText : '').replace(h.innerText, '').trim().slice(0, 300);
            return { title: h.innerText, url: a ? a.href : null, snippet };
        }).filter((r) => r.url && r.url.startsWith('http'))""",
        "bing": """() => [...document.querySelectorAll('li.b_algo')].map((li) => {
            const a = li.querySelector('h2 a');
            if (!a) return null;
            let url = a.href;
            try {
                const u = new URL(url);
                const enc = u.searchParams.get('u');
                if (u.hostname.endsWith('bing.com') && enc && enc.startsWith('a1')) {
                    url = atob(enc.slice(2).replace(/-/g, '+').replace(/_/g, '/'));
                }
            } catch (e) {}
            const p = li.querySelector('.b_caption p, p');
            return { title: a.innerText, url, snippet: p ? p.innerText.slice(0, 300) : '' };
        }).filter(Boolean)""",
    }
    STEALTH_JS = """() => {
      const def = Object.defineProperty;
      try { def(Navigator.prototype, 'webdriver', { get: () => undefined }); } catch (e) {}
      try { def(navigator, 'languages', { get: () => ['en-US', 'en'] }); } catch (e) {}
      try { def(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] }); } catch (e) {}
      try { def(navigator, 'hardwareConcurrency', { get: () => 8 }); } catch (e) {}
      if (!window.chrome) window.chrome = { runtime: {}, csi() {}, loadTimes() {} };
    }"""
    UA = ["Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
          "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"]

    def __init__(self):
        self.jobs = _queue.Queue()
        self.thread = None
        self.page = None
        self.cleanup = None
        self.engine_name = ""
        self.last_used = 0.0
        self.camoufox_failed = (0.0, "")  # (when, error): Chromium is used for a while after Camoufox fails
        self.dead = False

    def shutdown(self):
        """A newer WebTools took over (the cell ran again): close the browser and end the worker."""
        self.dead = True
        if self.thread is not None and self.thread.is_alive():
            self.jobs.put((lambda: None, (), {}, threading.Event()))  # wake the worker so it sees `dead`

    # ---------- browser worker ----------

    def _ensure_thread(self):
        if self.thread is None or not self.thread.is_alive():
            self.thread = threading.Thread(target=self._loop, daemon=True)
            self.thread.start()

    @staticmethod
    def _loop_left_running():
        """Playwright's sync API runs an asyncio loop on this thread while it is started. A start that failed half
        way (a browser that would not launch) leaves that loop marked as running, and every later
        sync_playwright() on this thread then fails with "using Playwright Sync API inside the asyncio loop"."""
        try:
            _asyncio.get_running_loop()
            return True
        except RuntimeError:
            return False

    def _loop(self):
        me = threading.current_thread()
        while True:
            if self.dead:
                self._close()
                while True:  # jobs queued before it retired get an answer instead of waiting for the timeout
                    try:
                        _, _, box, done = self.jobs.get_nowait()
                    except _queue.Empty:
                        return
                    box["error"] = RuntimeError("browser ini sudah diganti; coba lagi")
                    done.set()
            try:
                fn, args, box, done = self.jobs.get(timeout=300)
            except _queue.Empty:
                self._close()  # idle for 5 minutes: free the browser's memory
                continue
            retire = False
            try:
                box["result"] = fn(*args)
            except BaseException as e:
                box["error"] = e
                self._close()
            finally:
                retire = isinstance(box.get("error"), _FreshThread) or (self.page is None and self._loop_left_running())
                if retire and self.thread is me:
                    self.thread = None  # before done.set(), so the next job starts a new thread
                done.set()
            if retire:
                return

    def _run(self, fn, *args, timeout=120):
        if self.dead:
            raise RuntimeError("browser ini sudah diganti (cell dijalankan ulang); coba lagi")
        for attempt in range(2):
            self._ensure_thread()
            box, done = {}, threading.Event()
            self.jobs.put((fn, args, box, done))
            if not done.wait(timeout):
                raise TimeoutError("browser tidak menjawab")
            if isinstance(box.get("error"), _FreshThread) and attempt == 0:
                continue
            if "error" in box:
                raise box["error"]
            return box["result"]

    def _close(self):
        if self.cleanup:
            try:
                self.cleanup()
            except Exception:
                pass
        self.page = self.cleanup = None

    def _open(self):
        if self.page is not None:
            try:
                self.page.evaluate("1")
                return self.page
            except Exception:
                self._close()
        if time.time() - self.camoufox_failed[0] > 1800:
            cam = None
            try:
                from camoufox.sync_api import Camoufox
                env = dict(os.environ)
                # Firefox/Camoufox refuses to start when $HOME is not owned by our uid (molab runs as root).
                if hasattr(os, "getuid") and os.getuid() == 0 and os.path.isdir("/root"):
                    env["HOME"] = "/root"
                for k in ("MOZ_DISABLE_CONTENT_SANDBOX", "MOZ_DISABLE_RDD_SANDBOX", "MOZ_DISABLE_GMP_SANDBOX"):
                    env.setdefault(k, "1")
                cam = Camoufox(headless=True, humanize=True, geoip=True, block_webrtc=True, canvas_noise=False, env=env)
                b = cam.__enter__()
                self.page = b.new_page()
                self.cleanup = lambda: cam.__exit__(None, None, None)
                self.engine_name = "camoufox"
                self.camoufox_failed = (0.0, "")
                return self.page
            except Exception as e:
                self.camoufox_failed = (time.time(), f"{type(e).__name__}: {str(e)[:300]}")
                self.page = None
                if cam is not None:
                    try:
                        cam.__exit__(None, None, None)  # stops the Playwright that Camoufox started
                    except Exception:
                        pass
        if self._loop_left_running():
            raise _FreshThread()
        from playwright.sync_api import sync_playwright
        p = sync_playwright().start()
        b = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled", "--no-first-run",
                                                   "--mute-audio", "--disable-extensions"],
                              ignore_default_args=["--enable-automation"])
        ctx = b.new_context(locale="en-US", user_agent=random.choice(self.UA),
                            viewport={"width": 1440, "height": 900}, extra_http_headers={"Accept-Language": "en-US,en;q=0.9"})
        ctx.add_init_script(self.STEALTH_JS)
        self.page = ctx.new_page()

        def cleanup():
            try:
                b.close()
            finally:
                p.stop()
        self.cleanup = cleanup
        self.engine_name = "chromium"
        return self.page

    # ---------- tools ----------

    def web_search(self, query, engine="auto", max_results=8):
        order = ["google", "bing"] if engine in (None, "", "auto") else [engine]

        def job():
            page = self._open()
            notes = [f"camoufox gagal, pakai chromium: {self.camoufox_failed[1]}"] if self.engine_name == "chromium" and \
                self.camoufox_failed[1] else []
            for eng in order:
                if eng not in self.SEARCH_URL:
                    notes.append(f"{eng}: mesin tidak dikenal")
                    continue
                try:
                    page.goto(self.SEARCH_URL[eng].format(urllib.parse.quote(query)), wait_until="domcontentloaded", timeout=30000)
                    page.wait_for_timeout(2000)
                    if "/sorry/" in page.url or "consent." in page.url or "unusual traffic" in page.content().lower():
                        notes.append(f"{eng}: diblokir (CAPTCHA/consent)")
                        continue
                    rows = page.evaluate(self.SEARCH_JS[eng])
                except Exception as e:
                    notes.append(f"{eng}: {type(e).__name__}: {str(e)[:150]}")
                    continue
                if rows:
                    return {"engine": eng, "query": query, "results": rows[:int(max_results)], "notes": notes}
                notes.append(f"{eng}: tidak ada hasil")
            return {"error": "Semua mesin pencari gagal. Coba wiki_search.", "notes": notes}

        try:
            return json.dumps(self._run(job), ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": f"browser gagal: {type(e).__name__}: {str(e)[:200]}. Coba wiki_search."})

    def visit(self, url, max_chars=15000, screenshot=False):
        if not re.match(r"^https?://", url or ""):
            return json.dumps({"error": "URL harus diawali http:// atau https://"}), None

        def job():
            page = self._open()
            resp = page.goto(url, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(1500)
            text = page.evaluate("() => document.body ? document.body.innerText : ''")
            shot = page.screenshot(type="jpeg", quality=70) if screenshot else None
            return page.url, page.title(), resp.status if resp else None, text, shot

        try:
            final_url, title, status, text, shot = self._run(job, timeout=90)
        except Exception as e:
            return json.dumps({"error": f"{type(e).__name__}: {str(e)[:200]}"}), None
        text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text or "").strip()
        limit = max(1000, min(int(max_chars), 60000))
        out = {"url": final_url, "status": status, "title": title, "text": text[:limit], "truncated": len(text) > limit}
        if shot:
            out["screenshot"] = "terlampir sebagai gambar"
        return json.dumps(out, ensure_ascii=False), shot

    @staticmethod
    def _wiki(lang, params):
        url = f"https://{lang}.wikipedia.org/w/api.php?" + urllib.parse.urlencode({**params, "format": "json", "formatversion": 2})
        return Sys.get_json(url, timeout=20)

    def wiki_search(self, query, langs=("id", "en"), limit=5):
        out, notes = [], []
        for lang in langs:
            try:
                d = self._wiki(lang, {"action": "query", "list": "search", "srsearch": query, "srlimit": limit})
            except Exception as e:
                notes.append(f"{lang}: {e}")
                continue
            for r in d.get("query", {}).get("search", []):
                snippet = re.sub(r"<[^>]+>", "", r.get("snippet", ""))
                out.append({"lang": lang, "title": r["title"], "snippet": snippet,
                            "url": f"https://{lang}.wikipedia.org/wiki/{urllib.parse.quote(r['title'].replace(' ', '_'))}"})
        return json.dumps({"query": query, "results": out, "notes": notes}, ensure_ascii=False)

    def wiki_read(self, title, lang="en", max_chars=12000):
        try:
            d = self._wiki(lang, {"action": "query", "prop": "extracts", "explaintext": 1, "redirects": 1, "titles": title})
        except Exception as e:
            return json.dumps({"error": str(e)})
        pages = d.get("query", {}).get("pages", [])
        if not pages or pages[0].get("missing"):
            return json.dumps({"error": f"halaman '{title}' tidak ada di {lang}.wikipedia"})
        p = pages[0]
        text = p.get("extract", "")
        limit = max(1000, min(int(max_chars), 40000))
        return json.dumps({"title": p["title"], "lang": lang,
                           "url": f"https://{lang}.wikipedia.org/wiki/{urllib.parse.quote(p['title'].replace(' ', '_'))}",
                           "text": text[:limit], "truncated": len(text) > limit}, ensure_ascii=False)


_reg = sys.modules.setdefault("_qchat_runtime", SimpleNamespace(engines=[]))
if getattr(_reg, "web", None) is not None:
    _reg.web.shutdown()
WEB = WebTools()
_reg.web = WEB
