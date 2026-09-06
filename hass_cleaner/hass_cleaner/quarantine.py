from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import threading
import uuid
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path
from typing import Any

from .policy import RISK_SAFE, classify
from .scanner import ScanResult
from .settings import Settings


class QuarantineError(RuntimeError):
    pass


def _serialized(method):
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        with self._lock:
            try:
                return method(self, *args, **kwargs)
            except OSError as exc:
                raise QuarantineError(f"Quarantine storage operation failed: {exc}") from exc

    return wrapper


class QuarantineManager:
    """Move revalidated, user-selected non-protected files into app-owned storage."""

    def __init__(self, config_root: Path, data_root: Path):
        self.config_root = config_root.resolve()
        self.root = (data_root / "quarantine").resolve()
        self.manifest_path = self.root / "manifest.json"
        self._lock = threading.RLock()
        with self._lock:
            try:
                self._reconcile_incomplete_operations()
            except (QuarantineError, OSError) as exc:
                # Keep the interface available to report the error. Every read
                # and mutation still validates the manifest before proceeding.
                print(f"Hass-Cleaner quarantine recovery error: {exc}", flush=True)

    def execute(
        self,
        scan: ScanResult | None,
        settings: Settings,
        *,
        plan: dict[str, Any],
        backup_token: str,
        backup_valid: bool,
        backup_choice: str,
        risk_acknowledged: bool,
        content_risk_acknowledged: bool = False,
        confirmation: str,
        requested_by: str,
    ) -> dict[str, Any]:
        if not self._lock.acquire(blocking=False):
            raise QuarantineError("Er loopt al een quarantaineactie")
        try:
            return self._execute(
                scan,
                settings,
                plan=plan,
                backup_token=backup_token,
                backup_valid=backup_valid,
                backup_choice=backup_choice,
                risk_acknowledged=risk_acknowledged,
                content_risk_acknowledged=content_risk_acknowledged,
                confirmation=confirmation,
                requested_by=requested_by,
            )
        except OSError as exc:
            raise QuarantineError(f"Quarantine storage operation failed: {exc}") from exc
        finally:
            self._lock.release()

    def _execute(
        self,
        scan: ScanResult | None,
        settings: Settings,
        *,
        plan: dict[str, Any],
        backup_token: str,
        backup_valid: bool,
        backup_choice: str,
        risk_acknowledged: bool,
        content_risk_acknowledged: bool,
        confirmation: str,
        requested_by: str,
    ) -> dict[str, Any]:
        if confirmation not in {"QUARANTAINE", "QUARANTINE"}:
            raise QuarantineError("Typ QUARANTAINE of QUARANTINE om de verplaatsing te bevestigen")
        if backup_choice not in {"verified", "manual", "none"}:
            raise QuarantineError("Kies hoe je met de back-up wilt omgaan")
        if backup_choice == "verified" and (not backup_token or not backup_valid):
            raise QuarantineError("De gekozen Home Assistant-back-up is nog niet geverifieerd")
        if backup_choice in {"manual", "none"} and not risk_acknowledged:
            raise QuarantineError("Bevestig bewust de gekozen back-upafweging")
        if scan is None or scan.status != "completed" or plan.get("scan_id") != scan.id:
            raise QuarantineError("Het plan hoort niet bij de laatste voltooide scan; scan opnieuw")
        plan_files = plan.get("files", [])
        if not isinstance(plan_files, list) or not plan_files:
            raise QuarantineError("Dit plan bevat geen veilige bestanden")
        if any(str(item.get("risk", "safe")) == "review" for item in plan_files) and not content_risk_acknowledged:
            raise QuarantineError("Bevestig dat je bewust persoonlijke of onzekere inhoud naar quarantaine verplaatst")

        scan_map = {item.id: item for item in scan.items}
        operation_id = uuid.uuid4().hex
        operation_root = self.root / operation_id / "files"
        prepared: list[tuple[Path, Path, dict[str, Any]]] = []
        now = datetime.now(timezone.utc)

        # Validate the complete batch before changing a single source file.
        for planned in plan_files:
            item = scan_map.get(str(planned.get("id", "")))
            planned_risk = str(planned.get("risk", "safe"))
            if item is None or item.risk not in {RISK_SAFE, "review"} or item.risk != planned_risk or not item.path.startswith("/homeassistant/"):
                raise QuarantineError("De selectie is gewijzigd of bevat een beschermd bestand")
            relative = self._validated_relative_path(item.path.removeprefix("/homeassistant/"))
            source = self._contained_path(self.config_root, relative, "Een bronpad valt buiten de Home Assistant-configuratie")
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
            if decision is None or decision.risk != item.risk or decision.category != item.category:
                raise QuarantineError(f"Veiligheidsclassificatie is gewijzigd: {item.path}")
            current_hash = _sha256(source)
            if not item.sha256 or current_hash != item.sha256:
                raise QuarantineError(f"Bestandsinhoud is sinds de scan gewijzigd: {item.path}")
            destination = self._contained_path(operation_root, relative, "Een quarantainepad valt buiten de eigen opslag")
            prepared.append((source, destination, {
                "id": item.id,
                "original_path": item.path,
                "relative_path": relative.as_posix(),
                "category": item.category,
                "size_bytes": metadata.st_size,
                "modified_at": item.modified_at,
                "mode": stat.S_IMODE(metadata.st_mode),
                "scan_sha256": item.sha256,
                "sha256": item.sha256,
                "status": "planned",
            }))

        records = [record for _, _, record in prepared]
        operation = self._new_operation(
            operation_id, scan.id, backup_token or backup_choice, requested_by, now,
            settings, records, "preparing", backup_choice,
        )
        # The complete intent is durable before the first source file is touched.
        self._insert_operation(operation)
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
                record.update({"sha256": source_hash, "status": "copied"})
                operation["status"] = "running"
                self._replace_operation(operation)
                source.unlink()
                record["status"] = "quarantined"
                self._replace_operation(operation)
        except Exception as exc:
            operation["status"] = "partial" if any(item.get("status") == "quarantined" for item in records) else "failed"
            operation["error"] = f"{type(exc).__name__}: {exc}"
            self._replace_operation(operation)
            if isinstance(exc, QuarantineError):
                raise
            raise QuarantineError(f"Quarantaineactie is veilig gestopt: {exc}") from exc

        operation["status"] = "quarantined"
        operation.pop("error", None)
        self._replace_operation(operation)
        return operation

    @_serialized
    def restore(self, operation_id: str, file_id: str, *, confirmation: str, requested_by: str) -> dict[str, Any]:
        if confirmation not in {"HERSTEL", "RESTORE"}:
            raise QuarantineError("Typ HERSTEL of RESTORE om terugplaatsen te bevestigen")
        self._reconcile_incomplete_operations()
        operation = self._find_operation(operation_id)
        record = next((item for item in operation.get("files", []) if item.get("id") == file_id), None)
        if record is None or record.get("status") != "quarantined":
            raise QuarantineError("Quarantainebestand is niet beschikbaar voor herstel")
        relative = self._validated_relative_path(str(record["relative_path"]))
        source = self._contained_path(self._operation_files_root(operation_id), relative, "Ongeldig quarantainepad")
        target = self._contained_path(self.config_root, relative, "Ongeldig herstelpad")
        if target.exists() or target.is_symlink():
            raise QuarantineError("Herstel is gestopt: op de oorspronkelijke locatie bestaat al een bestand")
        if source.is_symlink() or not source.is_file() or _sha256(source) != record.get("sha256"):
            raise QuarantineError("Herstel is gestopt: checksum van het quarantainebestand klopt niet")
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.hass-cleaner-restore")
        record.update({
            "status": "restoring", "restore_temporary": temporary.name,
            "restored_at": datetime.now(timezone.utc).isoformat(), "restored_by": requested_by,
        })
        self._replace_operation(operation)
        with source.open("rb") as input_file, temporary.open("xb") as output_file:
            shutil.copyfileobj(input_file, output_file, 1024 * 1024)
            output_file.flush()
            os.fsync(output_file.fileno())
        if _sha256(temporary) != record["sha256"]:
            temporary.unlink(missing_ok=True)
            raise QuarantineError("Hersteltest is mislukt; bronbestand blijft in quarantaine")
        os.chmod(temporary, int(record.get("mode", 0o644)))
        restored_mtime = datetime.fromisoformat(str(record["modified_at"]).replace("Z", "+00:00")).timestamp()
        os.utime(temporary, (restored_mtime, restored_mtime))
        if os.name != "nt":
            with temporary.open("rb") as stream:
                os.fsync(stream.fileno())
        # A hard link publishes the complete file atomically and fails if a
        # concurrent writer has created the target. Never fall back to replace.
        os.link(temporary, target)
        _sync_directory(target.parent)
        record["status"] = "restored"
        self._replace_operation(operation)
        self._cleanup_restored(operation, record)
        return operation

    @_serialized
    def test_restore(self, operation_id: str, file_id: str) -> dict[str, Any]:
        operation = self._find_operation(operation_id)
        record = next((item for item in operation.get("files", []) if item.get("id") == file_id), None)
        if record is None or record.get("status") != "quarantined":
            raise QuarantineError("Quarantainebestand is niet beschikbaar voor een hersteltest")
        relative = self._validated_relative_path(str(record["relative_path"]))
        source = self._contained_path(self._operation_files_root(operation_id), relative, "Ongeldig quarantainepad")
        passed = self._matches_regular_file(source, str(record.get("sha256", "")))
        result = {"tested_at": datetime.now(timezone.utc).isoformat(), "passed": passed, "method": "read-and-sha256"}
        record["last_restore_test"] = result
        self._replace_operation(operation)
        if not passed:
            raise QuarantineError("Hersteltest mislukt: het opgeslagen bestand of de checksum klopt niet")
        return result

    @_serialized
    def purge_expired(self, operation_id: str, file_id: str, *, confirmation: str, requested_by: str) -> dict[str, Any]:
        if confirmation not in {"VERWIJDER", "DELETE"}:
            raise QuarantineError("Typ VERWIJDER of DELETE om een verlopen quarantainebestand definitief te verwijderen")
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
        relative = self._validated_relative_path(str(record["relative_path"]))
        source = self._contained_path(self._operation_files_root(operation_id), relative, "Ongeldig quarantainepad")
        if source.is_symlink() or not source.is_file() or _sha256(source) != record.get("sha256"):
            raise QuarantineError("Definitief verwijderen is gestopt: checksumcontrole mislukt")
        record.update({"status": "purging", "deleted_at": datetime.now(timezone.utc).isoformat(), "deleted_by": requested_by})
        self._replace_operation(operation)
        source.unlink()
        _sync_directory(source.parent)
        record["status"] = "deleted"
        self._replace_operation(operation)
        return operation

    @_serialized
    def list(self) -> list[dict[str, Any]]:
        return self._load()

    @_serialized
    def clear_completed_history(self) -> int:
        self._reconcile_incomplete_operations()
        operations = self._load()
        retained_statuses = {"planned", "quarantined", "copied", "restoring", "purging", "recovery_required"}
        active = [
            item for item in operations
            if item.get("status") == "recovery_required"
            or any(file.get("status") in retained_statuses for file in item.get("files", []))
        ]
        removed = len(operations) - len(active)
        self._save(active)
        for operation in operations:
            if operation not in active:
                try:
                    operation_root = self._operation_root(str(operation.get("id", "")))
                except QuarantineError:
                    continue
                shutil.rmtree(operation_root, ignore_errors=True)
        return removed

    def _new_operation(self, operation_id: str, scan_id: str, backup_token: str, requested_by: str, now: datetime, settings: Settings, files: list[dict[str, Any]], status: str, backup_choice: str = "verified") -> dict[str, Any]:
        return {
            "id": operation_id,
            "scan_id": scan_id,
            "created_at": now.isoformat(),
            "expires_at": (now + timedelta(days=settings.retention_days)).isoformat(),
            "retention_days": settings.retention_days,
            "status": status,
            "requested_by": requested_by,
            "backup_evidence_token": backup_token,
            "backup_choice": backup_choice,
            "files": files,
            "total_bytes": sum(int(item.get("size_bytes", 0)) for item in files),
        }

    def _insert_operation(self, operation: dict[str, Any]) -> None:
        operations = self._load()
        operations.insert(0, operation)
        self._save(operations)

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
        except FileNotFoundError as exc:
            if self.root.exists() and any(path.is_dir() for path in self.root.iterdir()):
                raise QuarantineError("Quarantine manifest is missing; existing recovery data has been preserved") from exc
            return []
        except (OSError, ValueError) as exc:
            raise QuarantineError("Quarantine manifest cannot be read; existing recovery data has been preserved") from exc
        if not isinstance(value, list):
            raise QuarantineError("Quarantine manifest has an invalid structure")
        ids = set()
        for operation in value:
            if (not isinstance(operation, dict) or not isinstance(operation.get("id"), str)
                    or not operation["id"].isalnum() or operation["id"] in ids
                    or not isinstance(operation.get("files"), list)
                    or not isinstance(operation.get("status"), str)):
                raise QuarantineError("Quarantine manifest has an invalid operation")
            ids.add(operation["id"])
            file_ids = set()
            file_paths = set()
            for record in operation["files"]:
                if (not isinstance(record, dict) or not isinstance(record.get("id"), str)
                        or not record["id"].isalnum() or record["id"] in file_ids
                        or not isinstance(record.get("status"), str)
                        or not isinstance(record.get("relative_path"), str)
                        or not isinstance(record.get("sha256"), str)
                        or len(record["sha256"]) != 64
                        or any(c not in "0123456789abcdef" for c in record["sha256"])
                        or record.get("status") not in {"planned", "copied", "quarantined", "restoring", "restored", "purging", "deleted", "rolled_back", "recovery_required"}
                        or record["relative_path"] in file_paths):
                    raise QuarantineError("Quarantine manifest has an invalid file record")
                self._validated_relative_path(record["relative_path"])
                file_ids.add(record["id"])
                file_paths.add(record["relative_path"])
        return value

    def _save(self, operations: list[dict[str, Any]]) -> None:
        self._load()  # Never replace a damaged journal with an empty/new one.
        self.root.mkdir(parents=True, exist_ok=True)
        temporary = self.manifest_path.with_suffix(".tmp")
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump(operations, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(self.manifest_path)
        try:
            directory = os.open(self.root, os.O_RDONLY)
        except OSError:
            return
        try:
            os.fsync(directory)
        except OSError:
            pass
        finally:
            os.close(directory)

    def _reconcile_incomplete_operations(self) -> None:
        operations = self._load()
        changed = False
        for operation in operations:
            for record in operation["files"]:
                if record["status"] in {"restoring", "purging", "quarantined"}:
                    changed = self._recover_file(operation, record) or changed
            if operation.get("status") not in {"preparing", "running", "partial", "failed", "recovery_required"}:
                continue
            operation_id = str(operation.get("id", ""))
            try:
                files_root = self._operation_files_root(operation_id)
            except QuarantineError:
                operation["status"] = "recovery_required"
                changed = True
                continue
            files = operation.get("files", [])
            if not isinstance(files, list):
                operation["status"] = "recovery_required"
                changed = True
                continue
            invalid_structure = False
            for record in files:
                if not isinstance(record, dict):
                    invalid_structure = True
                    changed = True
                    continue
                if record.get("status") not in {"planned", "copied"}:
                    continue
                try:
                    relative = self._validated_relative_path(str(record.get("relative_path", "")))
                    source = self._contained_path(self.config_root, relative, "Ongeldig bronpad")
                    destination = self._contained_path(files_root, relative, "Ongeldig quarantainepad")
                except QuarantineError:
                    record["status"] = "recovery_required"
                    changed = True
                    continue
                expected = str(record.get("sha256") or record.get("scan_sha256") or "")
                source_ok = self._matches_regular_file(source, expected)
                destination_ok = self._matches_regular_file(destination, expected)
                temporary = destination.with_name(destination.name + ".copying")
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    record["status"] = "recovery_required"
                    changed = True
                    continue
                source_present = source.exists() or source.is_symlink()
                if destination_ok and not source_present:
                    record["status"] = "quarantined"
                elif source_ok:
                    if destination_ok:
                        try:
                            destination.unlink()
                        except OSError:
                            record["status"] = "recovery_required"
                            changed = True
                            continue
                    record["status"] = "rolled_back"
                else:
                    record["status"] = "recovery_required"
                changed = True
            statuses = {str(item.get("status", "")) for item in files if isinstance(item, dict)}
            if invalid_structure:
                statuses.add("recovery_required")
            if statuses and statuses <= {"quarantined"}:
                operation["status"] = "quarantined"
                operation.pop("error", None)
            elif "recovery_required" in statuses:
                operation["status"] = "recovery_required"
            elif "quarantined" in statuses:
                operation["status"] = "partial"
            elif statuses:
                operation["status"] = "rolled_back"
        if changed:
            self._save(operations)
        for operation in operations:
            for record in operation["files"]:
                if record["status"] == "restored" and record.get("restore_temporary"):
                    self._cleanup_restored(operation, record)

    def _restore_temporary(self, target: Path, record: dict[str, Any]) -> Path:
        name = record.get("restore_temporary", "")
        prefix = f".{target.name}."
        suffix = ".hass-cleaner-restore"
        if (not isinstance(name, str) or not name.startswith(prefix) or not name.endswith(suffix)
                or len(name[len(prefix):-len(suffix)]) != 32
                or any(c not in "0123456789abcdef" for c in name[len(prefix):-len(suffix)])):
            raise QuarantineError("Invalid restore temporary path; recovery data preserved")
        return target.with_name(name)

    def _recover_file(self, operation: dict[str, Any], record: dict[str, Any]) -> bool:
        relative = self._validated_relative_path(record["relative_path"])
        source = self._contained_path(self._operation_files_root(operation["id"]), relative, "Invalid quarantine path")
        target = self._contained_path(self.config_root, relative, "Invalid restore path")
        status = record["status"]
        if status == "quarantined" and (source.exists() or source.is_symlink()):
            return False
        if status == "purging":
            # If unlink did not happen, let the user explicitly retry it.
            record["status"] = "quarantined" if self._matches_regular_file(source, record["sha256"]) else (
                "recovery_required" if source.exists() or source.is_symlink() else "deleted")
        elif status == "restoring":
            temporary = self._restore_temporary(target, record)
            published = (not target.is_symlink() and not temporary.is_symlink()
                         and target.is_file() and temporary.is_file() and target.samefile(temporary))
            if published:
                record["status"] = "restored"
            elif self._matches_regular_file(source, record["sha256"]):
                temporary.unlink(missing_ok=True)
                record["status"] = "quarantined"
                record.pop("restore_temporary", None)
            else:
                record["status"] = "recovery_required"
        else:
            # Recover older releases interrupted after deleting the quarantine
            # copy but before recording a completed restore.
            record["status"] = "restored" if self._matches_regular_file(target, record["sha256"]) else "recovery_required"
        return True

    def _cleanup_restored(self, operation: dict[str, Any], record: dict[str, Any]) -> None:
        relative = self._validated_relative_path(record["relative_path"])
        source = self._contained_path(self._operation_files_root(operation["id"]), relative, "Invalid quarantine path")
        target = self._contained_path(self.config_root, relative, "Invalid restore path")
        temporary = self._restore_temporary(target, record)
        temporary.unlink(missing_ok=True)
        source.unlink(missing_ok=True)
        _sync_directory(source.parent)

    @staticmethod
    def _validated_relative_path(value: str) -> Path:
        relative = Path(value)
        if not value or relative.is_absolute() or ".." in relative.parts:
            raise QuarantineError("Ongeldig relatief pad")
        return relative

    def _contained_path(self, root: Path, relative: Path, message: str) -> Path:
        resolved_root = root.resolve()
        candidate = resolved_root / relative
        try:
            candidate.resolve(strict=False).relative_to(resolved_root)
        except ValueError as exc:
            raise QuarantineError(message) from exc
        return candidate

    @staticmethod
    def _matches_regular_file(path: Path, expected_hash: str) -> bool:
        if not expected_hash or path.is_symlink():
            return False
        try:
            return path.is_file() and _sha256(path) == expected_hash
        except OSError:
            return False

    def _operation_root(self, operation_id: str) -> Path:
        if not operation_id.isalnum():
            raise QuarantineError("Ongeldig quarantaine-ID")
        return self._contained_path(self.root, Path(operation_id), "Ongeldig quarantaine-ID")

    def _operation_files_root(self, operation_id: str) -> Path:
        return self._contained_path(self._operation_root(operation_id), Path("files"), "Ongeldig quarantainepad")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sync_directory(path: Path) -> None:
    if os.name == "nt":
        return
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
