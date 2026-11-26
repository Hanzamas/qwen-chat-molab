import os
import sys
import tempfile
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import fake_server  # noqa: E402

_SRV = fake_server.start()
_WORK = tempfile.mkdtemp(prefix="qchat-test-")
os.environ.update(QCHAT_WORK=_WORK, QCHAT_BASE_URL=f"http://127.0.0.1:{_SRV.server_address[1]}/v1", HF_TOKEN="",
                  QCHAT_EMBED_URL="http://127.0.0.1:9")


@pytest.fixture(scope="session")
def nb():
    from qwen_chat_molab import app
    _, defs = app.run()
    return defs


@pytest.fixture(scope="session")
def fake():
    return fake_server.STATE


class Events:
    def __init__(self):
        self.items = []

    def __call__(self, kind, payload=None):
        self.items.append((kind, payload))

    def of(self, kind):
        return [p for k, p in self.items if k == kind]


@pytest.fixture()
def engine(nb):
    ev = Events()
    eng = nb["Engine"](emit=ev)
    eng.events = ev
    yield eng


def wait_idle(engine, timeout=30):
    end = time.time() + timeout
    time.sleep(0.05)
    while time.time() < end:
        if not engine.busy:
            return
        time.sleep(0.05)
    raise TimeoutError("engine masih sibuk")
