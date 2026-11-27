class Backup:
    """Copy the SQLite file to a private Hugging Face dataset repo when it has changed.
    The token is kept only in this object (kernel memory): never written to the database, disk or the backup."""

    KEEP = 20

    def __init__(self, store):
        self.store = store
        self.token = ""
        self.repo = ""
        self.interval = 600
        self.saved_rev = store.rev
        self.status = {"enabled": False, "last_ok": None, "last_error": "", "repo": "", "busy": False}
        self.lock = threading.Lock()
        self.thread = None

    def configure(self, token, repo, interval):
        self.token = (token or os.environ.get("HF_TOKEN", "")).strip()
        self.interval = max(60, int(interval))
        self.repo = repo.strip()
        self.status["enabled"] = bool(self.token)
        if self.token and not self.repo:
            try:
                self.repo = f"{self._api().whoami()['name']}/qwen-chat-backup"
            except Exception as e:
                self.status["last_error"] = f"The token cannot be used: {type(e).__name__}"
                self.status["enabled"] = False
        self.status["repo"] = self.repo
        if self.status["enabled"]:
            self.store.meta_set("backup", {"repo": self.repo, "interval": self.interval})
        if self.status["enabled"] and (self.thread is None or not self.thread.is_alive()):
            self.thread = threading.Thread(target=self._loop, daemon=True)
            self.thread.start()

    def _api(self):
        from huggingface_hub import HfApi
        return HfApi(token=self.token)

    def _loop(self):
        while self.status["enabled"]:
            time.sleep(self.interval)
            if self.store.rev != self.saved_rev:
                try:
                    self.backup_now()
                except Exception:
                    pass  # recorded in status["last_error"]; the next interval tries again

    def backup_now(self):
        if not self.token:
            raise RuntimeError("Enter an HF token first.")
        with self.lock:
            self.status["busy"] = True
            rev = self.store.rev
            tmp = CFG.WORK / "backup-upload.sqlite"
            try:
                self.store.backup_to(tmp)
                api = self._api()
                api.create_repo(self.repo, repo_type="dataset", private=True, exist_ok=True)
                # exist_ok keeps an existing repo as it is: never upload chats to a public one
                if not getattr(api.repo_info(self.repo, repo_type="dataset"), "private", False):
                    raise RuntimeError(f"Repo {self.repo} is public. Make it private on Hugging Face first; nothing was uploaded.")
                stamp = time.strftime("%Y%m%d-%H%M%S")
                from huggingface_hub import CommitOperationAdd, CommitOperationDelete
                ops = [CommitOperationAdd(f"backups/qwen-chat-{stamp}.sqlite", str(tmp)),
                       CommitOperationAdd("latest.sqlite", str(tmp))]
                old = sorted(f for f in api.list_repo_files(self.repo, repo_type="dataset") if f.startswith("backups/"))
                ops += [CommitOperationDelete(f) for f in old[:max(0, len(old) + 1 - self.KEEP)]]
                api.create_commit(self.repo, ops, commit_message=f"backup {stamp}", repo_type="dataset")
                self.saved_rev = rev
                self.status.update(last_ok=time.time(), last_error="")
            except Exception as e:
                self.status["last_error"] = f"{type(e).__name__}: {str(e)[:200]}"
                raise
            finally:
                self.status["busy"] = False
                tmp.unlink(missing_ok=True)

    def restore_latest(self):
        from huggingface_hub import hf_hub_download
        path = hf_hub_download(self.repo, "latest.sqlite", repo_type="dataset", token=self.token,
                               local_dir=str(CFG.WORK / "restore"), force_download=True)
        self.store.import_bytes(Path(path).read_bytes())
        self.saved_rev = self.store.rev

    def dirty(self):
        return self.store.rev != self.saved_rev


BACKUP = Backup(STORE)
