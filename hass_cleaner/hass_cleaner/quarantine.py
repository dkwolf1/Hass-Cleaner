from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .policy import RISK_SAFE, classify
from .scanner import ScanResult
from .settings import Settings


class QuarantineError(RuntimeError):
    pass


class QuarantineManager:
    """Move only revalidated safe scan results into app-owned storage."""

    def __init__(self, config_root: Path, data_root: Path):
        self.config_root = config_root.resolve()
        self.root = data_root / "quarantine"
        self.manifest_path = self.root / "manifest.json"

    def execute(
        self,
        scan: ScanResult | None,
        settings: Settings,
        *,
        plan: dict[str, Any],
        backup_token: str,
        backup_valid: bool,
        confirmation: str,
        requested_by: str,
    ) -> dict[str, Any]:
        if confirmation != "QUARANTAINE":
            raise QuarantineError("Typ QUARANTAINE om de verplaatsing te bevestigen")
        if settings.deletion_mode != "quarantine":
            raise QuarantineError("Direct permanent verwijderen is niet beschikbaar; kies quarantaine")
        if not backup_token or not backup_valid:
            raise QuarantineError("Een geverifieerde, voltooide Home Assistant-back-up is verplicht")
        if scan is None or scan.status != "completed" or plan.get("scan_id") != scan.id:
            raise QuarantineError("Het plan hoort niet bij de laatste voltooide scan; scan opnieuw")
        plan_files = plan.get("files", [])
        if not isinstance(plan_files, list) or not plan_files:
            raise QuarantineError("Dit plan bevat geen veilige bestanden")

        scan_map = {item.id: item for item in scan.items}
        operation_id = uuid.uuid4().hex
        operation_root = self.root / operation_id / "files"
        prepared: list[tuple[Path, Path, dict[str, Any]]] = []
        now = datetime.now(timezone.utc)

        # Validate the complete batch before changing a single source file.
        for planned in plan_files:
            item = scan_map.get(str(planned.get("id", "")))
            if item is None or item.risk != RISK_SAFE or not item.path.startswith("/homeassistant/"):
                raise QuarantineError("De selectie is gewijzigd of bevat geen bewezen veilige kandidaat")
            relative = Path(item.path.removeprefix("/homeassistant/"))
            source = (self.config_root / relative).resolve(strict=False)
            try:
                source.relative_to(self.config_root)
            except ValueError as exc:
                raise QuarantineError("Een bronpad valt buiten de Home Assistant-configuratie") from exc
            try:
                metadata = source.lstat()
            except OSError as exc:
                raise QuarantineError(f"Bestand is sinds de scan verdwenen: {item.path}") from exc
            if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
                raise QuarantineError(f"Bestandstype is sinds de scan gewijzigd: {item.path}")
            expected_mtime = datetime.fromisoformat(item.modified_at.replace("Z", "+00:00")).timestamp()
            if metadata.st_size != item.size_bytes or abs(metadata.st_mtime - expected_mtime) >= 1:
                raise QuarantineError(f"Bestand is sinds de scan gewijzigd: {item.path}")
            decision = classify(
                self.config_root,
                source,
                metadata.st_mode,
                metadata.st_mtime,
                min_temp_age_days=settings.min_temp_age_days,
                min_log_age_days=settings.min_log_age_days,
            )
            if decision is None or decision.risk != RISK_SAFE or decision.category != item.category:
                raise QuarantineError(f"Veiligheidsclassificatie is gewijzigd: {item.path}")
            current_hash = _sha256(source)
            if not item.sha256 or current_hash != item.sha256:
                raise QuarantineError(f"Bestandsinhoud is sinds de scan gewijzigd: {item.path}")
            destination = operation_root / relative
            prepared.append((source, destination, {
                "id": item.id,
                "original_path": item.path,
                "relative_path": relative.as_posix(),
                "category": item.category,
                "size_bytes": metadata.st_size,
                "modified_at": item.modified_at,
                "mode": stat.S_IMODE(metadata.st_mode),
                "scan_sha256": item.sha256,
            }))

        records: list[dict[str, Any]] = []
        try:
            for source, destination, record in prepared:
                destination.parent.mkdir(parents=True, exist_ok=True)
                temporary = destination.with_name(destination.name + ".copying")
                with source.open("rb") as input_file, temporary.open("xb") as output_file:
                    shutil.copyfileobj(input_file, output_file, 1024 * 1024)
                    output_file.flush()
                    os.fsync(output_file.fileno())
                source_hash = _sha256(source)
                if _sha256(temporary) != source_hash:
                    temporary.unlink(missing_ok=True)
                    raise QuarantineError(f"Checksumcontrole mislukt voor {record['original_path']}")
                temporary.replace(destination)
                source.unlink()
                record.update({"sha256": source_hash, "status": "quarantined"})
                records.append(record)
        except Exception:
            # Already moved files remain recoverable and are recorded below.
            if records:
                self._store_operation(operation_id, scan.id, backup_token, requested_by, now, settings, records, "partial")
            raise

        return self._store_operation(operation_id, scan.id, backup_token, requested_by, now, settings, records, "quarantined")

    def restore(self, operation_id: str, file_id: str, *, confirmation: str, requested_by: str) -> dict[str, Any]:
        if confirmation != "HERSTEL":
            raise QuarantineError("Typ HERSTEL om terugplaatsen te bevestigen")
        operation = self._find_operation(operation_id)
        record = next((item for item in operation.get("files", []) if item.get("id") == file_id), None)
        if record is None or record.get("status") != "quarantined":
            raise QuarantineError("Quarantainebestand is niet beschikbaar voor herstel")
        source = self.root / operation_id / "files" / Path(str(record["relative_path"]))
        target = self.config_root / Path(str(record["relative_path"]))
        if target.exists() or target.is_symlink():
            raise QuarantineError("Herstel is gestopt: op de oorspronkelijke locatie bestaat al een bestand")
        if not source.is_file() or _sha256(source) != record.get("sha256"):
            raise QuarantineError("Herstel is gestopt: checksum van het quarantainebestand klopt niet")
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + ".hass-cleaner-restore")
        with source.open("rb") as input_file, temporary.open("xb") as output_file:
            shutil.copyfileobj(input_file, output_file, 1024 * 1024)
            output_file.flush()
            os.fsync(output_file.fileno())
        if _sha256(temporary) != record["sha256"]:
            temporary.unlink(missing_ok=True)
            raise QuarantineError("Hersteltest is mislukt; bronbestand blijft in quarantaine")
        temporary.replace(target)
        os.chmod(target, int(record.get("mode", 0o644)))
        restored_mtime = datetime.fromisoformat(str(record["modified_at"]).replace("Z", "+00:00")).timestamp()
        os.utime(target, (restored_mtime, restored_mtime))
        source.unlink()
        record.update({"status": "restored", "restored_at": datetime.now(timezone.utc).isoformat(), "restored_by": requested_by})
        self._replace_operation(operation)
        return operation

    def test_restore(self, operation_id: str, file_id: str) -> dict[str, Any]:
        operation = self._find_operation(operation_id)
        record = next((item for item in operation.get("files", []) if item.get("id") == file_id), None)
        if record is None or record.get("status") != "quarantined":
            raise QuarantineError("Quarantainebestand is niet beschikbaar voor een hersteltest")
        source = self.root / operation_id / "files" / Path(str(record["relative_path"]))
        passed = source.is_file() and _sha256(source) == record.get("sha256")
        result = {"tested_at": datetime.now(timezone.utc).isoformat(), "passed": passed, "method": "read-and-sha256"}
        record["last_restore_test"] = result
        self._replace_operation(operation)
        if not passed:
            raise QuarantineError("Hersteltest mislukt: het opgeslagen bestand of de checksum klopt niet")
        return result

    def purge_expired(self, operation_id: str, file_id: str, *, confirmation: str, requested_by: str) -> dict[str, Any]:
        if confirmation != "VERWIJDER":
            raise QuarantineError("Typ VERWIJDER om een verlopen quarantainebestand definitief te verwijderen")
        operation = self._find_operation(operation_id)
        try:
            expires_at = datetime.fromisoformat(str(operation.get("expires_at", "")).replace("Z", "+00:00"))
        except ValueError as exc:
            raise QuarantineError("De bewaartermijn kan niet veilig worden vastgesteld") from exc
        if datetime.now(timezone.utc) < expires_at:
            raise QuarantineError("De bewaartermijn is nog niet verstreken; herstellen blijft mogelijk")
        record = next((item for item in operation.get("files", []) if item.get("id") == file_id), None)
        if record is None or record.get("status") != "quarantined":
            raise QuarantineError("Quarantainebestand is niet beschikbaar")
        source = self.root / operation_id / "files" / Path(str(record["relative_path"]))
        if not source.is_file() or _sha256(source) != record.get("sha256"):
            raise QuarantineError("Definitief verwijderen is gestopt: checksumcontrole mislukt")
        source.unlink()
        record.update({"status": "deleted", "deleted_at": datetime.now(timezone.utc).isoformat(), "deleted_by": requested_by})
        self._replace_operation(operation)
        return operation

    def list(self) -> list[dict[str, Any]]:
        return self._load()

    def _store_operation(self, operation_id: str, scan_id: str, backup_token: str, requested_by: str, now: datetime, settings: Settings, files: list[dict[str, Any]], status: str) -> dict[str, Any]:
        operation = {
            "id": operation_id,
            "scan_id": scan_id,
            "created_at": now.isoformat(),
            "expires_at": (now + timedelta(days=settings.retention_days)).isoformat(),
            "retention_days": settings.retention_days,
            "status": status,
            "requested_by": requested_by,
            "backup_evidence_token": backup_token,
            "files": files,
            "total_bytes": sum(int(item.get("size_bytes", 0)) for item in files),
        }
        operations = self._load()
        operations.insert(0, operation)
        self._save(operations)
        return operation

    def _find_operation(self, operation_id: str) -> dict[str, Any]:
        if not operation_id.isalnum():
            raise QuarantineError("Ongeldig quarantaine-ID")
        operation = next((item for item in self._load() if item.get("id") == operation_id), None)
        if operation is None:
            raise QuarantineError("Quarantaineactie niet gevonden")
        return operation

    def _replace_operation(self, operation: dict[str, Any]) -> None:
        operations = self._load()
        self._save([operation if item.get("id") == operation.get("id") else item for item in operations])

    def _load(self) -> list[dict[str, Any]]:
        try:
            value = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            return value if isinstance(value, list) else []
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return []

    def _save(self, operations: list[dict[str, Any]]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        temporary = self.manifest_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(operations, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.manifest_path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
