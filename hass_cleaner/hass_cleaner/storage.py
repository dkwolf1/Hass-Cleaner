from __future__ import annotations

import json
import os
import threading
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


class StorageError(RuntimeError):
    """Raised when local state cannot be persisted safely."""


_LOCKS_GUARD = threading.Lock()
_LOCKS: dict[str, threading.RLock] = {}


def _lock_for(path: Path) -> threading.RLock:
    key = str(path.resolve())
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(key, threading.RLock())


@contextmanager
def json_file_lock(path: Path) -> Iterator[None]:
    """Serialize read-modify-write operations for one JSON state file."""
    with _lock_for(path):
        yield


def read_json_object(path: Path) -> dict[str, Any]:
    """Read a JSON object while excluding an in-process replacement."""
    with json_file_lock(path):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return value if isinstance(value, dict) else {}


def atomic_write_json(path: Path, value: Any) -> None:
    """Durably replace a JSON file without exposing a partial document."""
    with json_file_lock(path):
        temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with temporary.open("w", encoding="utf-8", newline="\n") as handle:
                json.dump(value, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            temporary.replace(path)
            if os.name != "nt":
                descriptor = os.open(path.parent, os.O_RDONLY)
                try:
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
        except (OSError, TypeError, ValueError) as exc:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            raise StorageError(f"Lokale status kon niet veilig worden opgeslagen: {path.name}") from exc
