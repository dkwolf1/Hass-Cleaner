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
        "name": f"Voor Hass-Cleaner - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
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
    data = result.get("data", result)
    if not isinstance(data, dict):
        raise SupervisorError("Supervisor gaf een ongeldig antwoord op de back-upaanvraag")
    data["requested_name"] = payload["name"]
    return data


def supervisor_get(path: str) -> dict[str, object]:
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        raise SupervisorError("Supervisor is niet beschikbaar in lokale ontwikkelmodus")
    request = urllib.request.Request(
        "http://supervisor" + path,
        headers={"Authorization": f"Bearer {token}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise SupervisorError(f"Back-upstatus kon niet worden gecontroleerd: {exc}") from exc
    data = result.get("data", result)
    if not isinstance(data, dict):
        raise SupervisorError("Supervisor gaf een ongeldige back-upstatus terug")
    return data


class BackupEvidenceManager:
    """Persist proof that Home Assistant accepted a backup request."""

    def __init__(self, data_root: Path, creator=create_full_backup, getter=supervisor_get):
        self.path = data_root / "backup-evidence.json"
        self.creator = creator
        self.getter = getter

    def create(self, requested_by: str = "") -> dict[str, object]:
        result = self.creator()
        record = {
            "token": uuid.uuid4().hex,
            "requested_at": datetime.now(timezone.utc).isoformat(),
            "requested_by": requested_by,
            "status": "accepted",
            "backup_reference": str(result.get("slug") or result.get("id") or result.get("job_id") or ""),
            "backup_slug": str(result.get("slug") or ""),
            "job_id": str(result.get("job_id") or ""),
            "requested_name": str(result.get("requested_name") or ""),
        }
        records = self.history()
        records.insert(0, record)
        self._save(records[:20])
        return record

    def refresh(self, token: str) -> dict[str, object]:
        records = self.history()
        record = next((item for item in records if item.get("token") == token), None)
        if record is None:
            raise SupervisorError("Back-upbewijs niet gevonden")
        slug = str(record.get("backup_slug", ""))
        backups_data = self.getter("/backups")
        backups = backups_data.get("backups", [])
        if not isinstance(backups, list):
            raise SupervisorError("Supervisor gaf een ongeldige back-uplijst terug")
        requested_name = str(record.get("requested_name", ""))
        match = next((item for item in backups if isinstance(item, dict) and slug and item.get("slug") == slug), None)
        if match is None and requested_name:
            match = next((item for item in backups if isinstance(item, dict) and item.get("name") == requested_name), None)
        if match is None:
            record["status"] = "running"
        else:
            slug = str(match.get("slug") or "")
            record.update({
                "status": "completed",
                "backup_slug": slug,
                "backup_reference": slug,
                "verified_at": datetime.now(timezone.utc).isoformat(),
                "backup_name": str(match.get("name") or requested_name),
                "backup_size": int(match.get("size") or 0),
            })
        self._save(records)
        return record

    def valid(self, token: str, *, max_age_hours: int = 24) -> bool:
        now = datetime.now(timezone.utc)
        for record in self.history():
            if record.get("token") != token or record.get("status") != "completed":
                continue
            try:
                requested = datetime.fromisoformat(str(record.get("requested_at", "")).replace("Z", "+00:00"))
            except ValueError:
                return False
            age = (now - requested).total_seconds()
            return 0 <= age <= max_age_hours * 3600
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
