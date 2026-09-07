from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .registry_audit import HomeAssistantApiError, WEBSOCKET_URL, _receive_json, _receive_result
from .storage import atomic_write_json, StorageError


class RegistryCleanupError(RuntimeError):
    pass


class RegistryExecutionError(RegistryCleanupError):
    """A registry command failed after zero or more commands completed."""

    def __init__(self, message: str, completed: list[dict[str, str]]):
        super().__init__(message)
        self.completed = list(completed)


def execute_registry_commands(
    entities: list[str],
    devices: list[dict[str, str]],
    *,
    token: str | None = None,
    connect: Callable[..., Any] | None = None,
    url: str = WEBSOCKET_URL,
    progress: Callable[[list[dict[str, str]], dict[str, str] | None], None] | None = None,
) -> list[dict[str, str]]:
    access_token = token or os.environ.get("SUPERVISOR_TOKEN")
    if not access_token:
        raise RegistryCleanupError("Registeropschoning is alleen beschikbaar binnen Home Assistant")
    if connect is None:
        try:
            import websocket
        except ImportError as exc:  # pragma: no cover
            raise RegistryCleanupError("Python-package websocket-client ontbreekt") from exc
        connect = websocket.create_connection
    connection = connect(url, timeout=30, header=[f"Authorization: Bearer {access_token}"])
    completed: list[dict[str, str]] = []
    try:
        greeting = _receive_json(connection)
        if greeting.get("type") == "auth_required":
            connection.send(json.dumps({"type": "auth", "access_token": access_token}))
            authentication = _receive_json(connection)
        else:
            authentication = greeting
        if authentication.get("type") != "auth_ok":
            raise RegistryCleanupError(authentication.get("message", "WebSocket-authenticatie geweigerd"))
        command_id = 1
        for entity_id in entities:
            if progress:
                progress(completed, {"type": "entity", "id": entity_id})
            connection.send(json.dumps({"id": command_id, "type": "config/entity_registry/remove", "entity_id": entity_id}))
            _receive_result(connection, command_id)
            completed.append({"type": "entity", "id": entity_id, "status": "removed"})
            if progress:
                progress(completed, None)
            command_id += 1
        for device in devices:
            if progress:
                progress(completed, {"type": "device", "id": device["device_id"], "config_entry_id": device["config_entry_id"]})
            connection.send(json.dumps({
                "id": command_id,
                "type": "config/device_registry/remove_config_entry",
                "device_id": device["device_id"],
                "config_entry_id": device["config_entry_id"],
            }))
            _receive_result(connection, command_id)
            completed.append({"type": "device", "id": device["device_id"], "status": "config_entry_removed"})
            if progress:
                progress(completed, None)
            command_id += 1
    except Exception as exc:
        if isinstance(exc, RegistryExecutionError):
            raise
        message = str(exc) if isinstance(exc, (HomeAssistantApiError, RegistryCleanupError)) else f"{type(exc).__name__}: {exc}"
        raise RegistryExecutionError(message, completed) from exc
    finally:
        try:
            connection.close()
        except Exception:
            # Closing the transport does not undo commands Home Assistant already accepted.
            pass
    return completed


class RegistryCleanupManager:
    def __init__(self, data_root: Path, executor=execute_registry_commands):
        self.history_path = data_root / "registry-cleanup-history.json"
        self.executor = executor
        self._lock = threading.RLock()
        try:
            records = self.history()
            interrupted = [record for record in records if record.get("status") == "running"]
            for record in interrupted:
                record.update(status="interrupted", error="Execution was interrupted; verify pending commands in Home Assistant before retrying.")
            if interrupted:
                self._save(records)
        except RegistryCleanupError as exc:
            print(f"Hass-Cleaner registry journal error: {exc}", flush=True)

    def history(self) -> list[dict[str, Any]]:
        try:
            value = json.loads(self.history_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return []
        except (OSError, ValueError) as exc:
            raise RegistryCleanupError("Registry journal cannot be read; no changes were made to it") from exc
        if not isinstance(value, list) or any(not isinstance(record, dict) or not record.get("id") for record in value):
            raise RegistryCleanupError("Registry journal has an invalid structure")
        return value

    def execute(self, scan, plan: dict[str, Any], *, backup_choice: str, backup_token: str,
                backup_valid: bool, risk_acknowledged: bool, confirmation: str, requested_by: str) -> dict[str, Any]:
        entities = sorted({str(item.get("entity_id", "")) for item in plan.get("entities", []) if item.get("execution_allowed")})
        device_items = [
            {"device_id": str(item.get("device_id", "")), "config_entry_id": str(item.get("config_entry_id", ""))}
            for item in plan.get("devices", []) if item.get("execution_allowed")
        ]
        devices = list({
            (item["device_id"], item["config_entry_id"]): item
            for item in device_items if item["device_id"] and item["config_entry_id"]
        }.values())
        total = len(entities) + len(devices)
        if scan is None or scan.status != "completed" or plan.get("scan_id") != scan.id:
            raise RegistryCleanupError("De voorbereide opschoning hoort niet bij de laatste scan; scan opnieuw")
        workspace = scan.registry_audit.entity_workspace
        allowed_entities = {
            str(item.get("entity_id", ""))
            for item in workspace.get("items", [])
            if item.get("entity_id") and item.get("registry_entry", True) is not False
        }
        allowed_devices = {
            (str(device.get("device_id", "")), str(bundle.config_entry_id or ""))
            for bundle in scan.registry_audit.bundles
            for device in bundle.devices
            if device.get("device_id") and bundle.config_entry_id
        }
        if any(entity_id not in allowed_entities for entity_id in entities) or any(
            (item["device_id"], item["config_entry_id"]) not in allowed_devices for item in devices
        ):
            raise RegistryCleanupError("De voorbereide opschoning bevat registerobjecten die niet meer in de laatste scan staan; scan opnieuw")
        if not total:
            raise RegistryCleanupError("Deze voorbereide opschoning bevat geen uitvoerbare registerobjecten")
        if confirmation not in {f"VERWIJDER {total}", f"DELETE {total}"}:
            raise RegistryCleanupError(f"Typ exact VERWIJDER {total} of DELETE {total} om de registeropschoning te bevestigen")
        if backup_choice not in {"verified", "manual", "none"}:
            raise RegistryCleanupError("Kies hoe je met de back-up wilt omgaan")
        if backup_choice == "verified" and (not backup_token or not backup_valid):
            raise RegistryCleanupError("De gekozen Home Assistant-back-up is nog niet geverifieerd")
        if not risk_acknowledged:
            raise RegistryCleanupError("Bevestig dat je de gevolgen en het herstelrisico begrijpt")
        if not self._lock.acquire(blocking=False):
            raise RegistryCleanupError("Er loopt al een registeropschoning")
        record: dict[str, Any] = {
            "id": uuid.uuid4().hex,
            "scan_id": scan.id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "requested_by": requested_by,
            "backup_choice": backup_choice,
            "backup_evidence_token": backup_token,
            "requested_entities": entities,
            "requested_devices": devices,
            "status": "running",
            "completed": [],
        }
        try:
            from .references import validate_before_cleanup
            validate_before_cleanup(scan, plan)
            history = self.history()
            history.insert(0, record)
            # An unavailable journal must prevent the first external command.
            self._save(history)

            def progress(completed, pending):
                record["completed"] = list(completed)
                record["pending"] = pending
                self._save(history)

            try:
                record["completed"] = self.executor(entities, devices, progress=progress)
                record["pending"] = None
                record["status"] = "completed"
            except Exception as exc:
                if isinstance(exc, RegistryExecutionError):
                    record["completed"] = exc.completed
                record["status"] = "partial" if record["completed"] else "failed"
                record["outcome_uncertain"] = bool(record.get("pending"))
                record["error"] = f"{type(exc).__name__}: {exc}"
                self._save(history)
                raise RegistryCleanupError(str(exc)) from exc
            self._save(history)
        finally:
            self._lock.release()
        return record

    def clear_history(self) -> None:
        if not self._lock.acquire(blocking=False):
            raise RegistryCleanupError("Registry cleanup is running; history cannot be cleared yet")
        try:
            records = self.history()
            # Keep unresolved external outcomes available for investigation.
            self._save([record for record in records if record.get("status") in {"running", "interrupted"} or record.get("outcome_uncertain")])
        finally:
            self._lock.release()

    def _save(self, history: list[dict[str, Any]]) -> None:
        self.history()
        unresolved = [record for record in history if record.get("status") in {"running", "interrupted"} or record.get("outcome_uncertain")]
        resolved = [record for record in history if record not in unresolved]
        try:
            atomic_write_json(self.history_path, unresolved + resolved[:50])
        except StorageError as exc:
            raise RegistryCleanupError("Registry journal could not be saved; execution stopped") from exc
