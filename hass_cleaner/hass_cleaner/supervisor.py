from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path


class SupervisorError(RuntimeError):
    pass


def supervisor_available() -> bool:
    return bool(os.environ.get("SUPERVISOR_TOKEN"))


def create_full_backup() -> dict[str, object]:
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        raise SupervisorError("Supervisor is niet beschikbaar in lokale ontwikkelmodus")
    payload = {
        "name": f"Voor Hass-Cleaner - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "compressed": True,
        "background": True,
    }
    request = urllib.request.Request(
        "http://supervisor/backups/new/full",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise SupervisorError(f"Back-up kon niet worden gestart: {exc}") from exc
    return result.get("data", result)


class BackupEvidenceManager:
    """Persist proof that Home Assistant accepted a backup request."""

    def __init__(self, data_root: Path, creator=create_full_backup):
        self.path = data_root / "backup-evidence.json"
        self.creator = creator

    def create(self, requested_by: str = "") -> dict[str, object]:
        result = self.creator()
        record = {
            "token": uuid.uuid4().hex,
            "requested_at": datetime.now(timezone.utc).isoformat(),
            "requested_by": requested_by,
            "status": "accepted",
            "backup_reference": str(result.get("slug") or result.get("id") or result.get("job_id") or ""),
        }
        records = self.history()
        records.insert(0, record)
        self._save(records[:20])
        return record

    def valid(self, token: str, *, max_age_hours: int = 24) -> bool:
        now = datetime.now(timezone.utc)
        for record in self.history():
            if record.get("token") != token or record.get("status") not in {"accepted", "completed"}:
                continue
            try:
                requested = datetime.fromisoformat(str(record.get("requested_at", "")).replace("Z", "+00:00"))
            except ValueError:
                return False
            return (now - requested).total_seconds() <= max_age_hours * 3600
        return False

    def history(self) -> list[dict[str, object]]:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            return value if isinstance(value, list) else []
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return []

    def _save(self, records: list[dict[str, object]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)
