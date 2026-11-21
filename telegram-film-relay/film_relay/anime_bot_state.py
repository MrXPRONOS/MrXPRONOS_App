"""Private, atomic and lockable durable Bot API state.

Use a persistent volume or private durable backend, never ephemeral GitHub
Actions storage. Never commit raw Telegram file_id or source-message records
to a public repository.
"""
from __future__ import annotations

import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path


class BotStateStore:
    def __init__(self, path):
        self.path = Path(path).expanduser().resolve()

    def load(self):
        if not self.path.is_file():
            return {"schema_version": 1, "messages": {}, "series": {},
                    "last_update_id": -1, "operation_receipts": {},
                    "identity_review": [], "alerts": []}
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("schema_version") != 1:
            raise ValueError("Unsupported CinéX Bot state schema.")
        return data

    def save(self, state):
        if not isinstance(state, dict) or state.get("schema_version") != 1:
            raise ValueError("Refuse to save non-versioned state.")
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd, temp_path = tempfile.mkstemp(
            prefix=".cinex-anime-", suffix=".tmp", dir=self.path.parent)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(state, stream, sort_keys=True, ensure_ascii=False,
                          separators=(",", ":"))
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_path, self.path)
            if hasattr(os, "O_DIRECTORY"):
                dir_fd = os.open(str(self.path.parent), os.O_DIRECTORY)
                try:
                    os.fsync(dir_fd)
                finally:
                    os.close(dir_fd)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    @contextmanager
    def exclusive(self):
        # No automatic retry and no overlapping writers in one host.
        import fcntl
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        lock_path = str(self.path) + ".lock"
        fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)


def require_durable_store(path, env=None):
    env = os.environ if env is None else env
    if env.get("CINEX_ANIME_PRIVATE_PERSISTENCE_ATTESTED") != "true":
        raise RuntimeError(
            "Private persistent storage must be attested before live bot polling.")
    if not path or not Path(path).is_absolute():
        raise RuntimeError("Absolute persistent state path required.")
    if str(path).startswith(("/tmp/", "/var/tmp/", "/home/runner/work/")):
        raise RuntimeError("Ephemeral CI runner storage is not durable.")
    return BotStateStore(path)
