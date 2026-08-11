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
        job_id = str(record.get("job_id", ""))
        slug = str(record.get("backup_slug", ""))
        if job_id:
            job = self.getter(f"/jobs/{job_id}")
            record["job_progress"] = int(job.get("progress") or 0)
            record["job_stage"] = str(job.get("stage") or "")
            errors = _job_errors(job)
            if errors:
                record["status"] = "failed"
                record["verification_error"] = "; ".join(str(value) for value in errors)
            elif not job.get("done"):
                record["status"] = "running"
            else:
                extra = job.get("extra") if isinstance(job.get("extra"), dict) else {}
                slug = slug or str(extra.get("slug") or job.get("reference") or "")
        if record.get("status") != "failed" and (not job_id or record.get("status") != "running"):
            if not slug:
                record["status"] = "failed"
                record["verification_error"] = "Supervisor leverde geen back-upslug"
            else:
                info = self.getter(f"/backups/{slug}/info")
                record.update({
                    "status": "completed",
                    "backup_slug": slug,
                    "backup_reference": slug,
                    "verified_at": datetime.now(timezone.utc).isoformat(),
                    "backup_name": str(info.get("name") or ""),
                    "backup_size": int(info.get("size") or 0),
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


def _job_errors(job: dict[str, object]) -> list[object]:
    errors = list(job.get("errors", [])) if isinstance(job.get("errors"), list) else []
    children = job.get("child_jobs", [])
    if isinstance(children, list):
        for child in children:
            if isinstance(child, dict):
                errors.extend(_job_errors(child))
    return errors
