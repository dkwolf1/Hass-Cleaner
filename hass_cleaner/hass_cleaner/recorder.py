from __future__ import annotations

import json
import os
import threading
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .registry_audit import HomeAssistantApiError, WEBSOCKET_URL, _receive_json, _receive_result


@dataclass(frozen=True)
class PurgeRecord:
    id: str
    requested_at: str
    keep_days: int
    repack: bool
    apply_filter: bool
    backup_confirmed: bool
    status: str
    requested_by: str = ""
    backup_evidence: str = "manual-confirmation"
    error: str | None = None


def call_recorder_purge(
    keep_days: int,
    repack: bool,
    apply_filter: bool,
    *,
    token: str | None = None,
    connect: Callable[..., Any] | None = None,
    url: str = WEBSOCKET_URL,
) -> None:
    access_token = token or os.environ.get("SUPERVISOR_TOKEN")
    if not access_token:
        raise HomeAssistantApiError("Recorder-purge is alleen beschikbaar binnen Home Assistant")
    if connect is None:
        try:
            import websocket
        except ImportError as exc:  # pragma: no cover
            raise HomeAssistantApiError("Python-package websocket-client ontbreekt") from exc
        connect = websocket.create_connection
    connection = connect(url, timeout=30, header=[f"Authorization: Bearer {access_token}"])
    try:
        greeting = _receive_json(connection)
        if greeting.get("type") == "auth_required":
            connection.send(json.dumps({"type": "auth", "access_token": access_token}))
            authentication = _receive_json(connection)
        else:
            authentication = greeting
        if authentication.get("type") != "auth_ok":
            raise HomeAssistantApiError(authentication.get("message", "WebSocket-authenticatie geweigerd"))
        connection.send(
            json.dumps(
                {
                    "id": 1,
                    "type": "call_service",
                    "domain": "recorder",
                    "service": "purge",
                    "service_data": {
                        "keep_days": keep_days,
                        "repack": repack,
                        "apply_filter": apply_filter,
                    },
                }
            )
        )
        _receive_result(connection, 1)
    finally:
        connection.close()


class PurgeManager:
    def __init__(self, data_root: Path, purge_caller: Callable[[int, bool, bool], None] = call_recorder_purge):
        self.history_path = data_root / "recorder-purge-history.json"
        self.purge_caller = purge_caller
        self._lock = threading.Lock()

    def history(self) -> list[dict[str, object]]:
        try:
            value = json.loads(self.history_path.read_text(encoding="utf-8"))
            return value if isinstance(value, list) else []
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return []

    def execute(self, *, keep_days: int, repack: bool, apply_filter: bool, backup_confirmed: bool,
                confirmation: str, requested_by: str = "", backup_evidence: str = "manual-confirmation") -> PurgeRecord:
        if not 1 <= keep_days <= 365:
            raise ValueError("Dagen om te bewaren moet tussen 1 en 365 liggen")
        if not backup_confirmed:
            raise ValueError("Bevestig eerst dat een bruikbare back-up beschikbaar is")
        if confirmation != "PURGE":
            raise ValueError("Typ exact PURGE om de databaseactie te bevestigen")
        if not self._lock.acquire(blocking=False):
            raise RuntimeError("Er loopt al een Recorder-purge")
        try:
            base = {
                "id": uuid.uuid4().hex,
                "requested_at": datetime.now(timezone.utc).isoformat(),
                "keep_days": keep_days,
                "repack": repack,
                "apply_filter": apply_filter,
                "backup_confirmed": True,
                "requested_by": requested_by,
                "backup_evidence": backup_evidence,
            }
            try:
                self.purge_caller(keep_days, repack, apply_filter)
                record = PurgeRecord(**base, status="accepted")
            except Exception as exc:
                record = PurgeRecord(**base, status="failed", error=f"{type(exc).__name__}: {exc}")
                self._append(record)
                raise HomeAssistantApiError(record.error) from exc
            self._append(record)
            return record
        finally:
            self._lock.release()

    def _append(self, record: PurgeRecord) -> None:
        history = self.history()
        history.insert(0, asdict(record))
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.history_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(history[:50], ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.history_path)
