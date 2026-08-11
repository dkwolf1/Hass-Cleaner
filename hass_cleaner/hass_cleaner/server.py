from __future__ import annotations

import json
import mimetypes
import os
import re
from dataclasses import asdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from . import __version__
from .scanner import ScanManager
from .reporting import report_path
from .recorder import PurgeManager
from .registry_audit import HomeAssistantApiError, fetch_related
from .plans import PlanError, PlanManager
from .settings import Settings, environment, load_effective_settings, save_local_settings
from .supervisor import SupervisorError, create_full_backup, supervisor_available


class AppState:
    def __init__(self, config_root: Path, data_root: Path, web_root: Path):
        self.config_root = config_root
        self.data_root = data_root
        self.web_root = web_root
        self.report_root = data_root / "reports"
        self.scan_manager = ScanManager(
            config_root,
            lambda: load_effective_settings(data_root),
            self.report_root,
        )
        self.purge_manager = PurgeManager(data_root)
        self.plan_manager = PlanManager(data_root)


class CleanupHandler(BaseHTTPRequestHandler):
    server_version = "HassCleaner/0.6.1"

    @property
    def state(self) -> AppState:
        return self.server.state  # type: ignore[attr-defined]

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path == "/health":
            self._json({"status": "ok"})
        elif path == "/api/status":
            self._json(
                {
                    "version": __version__,
                    "mode": "local" if not supervisor_available() else "home_assistant",
                    "config_root_available": self.state.config_root.is_dir(),
                    "audit_only": True,
                    "destructive_execution_enabled": supervisor_available(),
                    "destructive_scope": "recorder_only",
                    "file_execution_enabled": False,
                    "registry_execution_enabled": False,
                    "recorder_purge_enabled": supervisor_available(),
                    "config_mount_expected_read_only": True,
                    "backup_available": supervisor_available(),
                    "registry_scan_available": supervisor_available(),
                    "impact_advice_available": True,
                    "advanced_review_available": True,
                    "plan_download_available": True,
                    "beginner_recipes_available": True,
                    "evidence_gate_enforced": True,
                }
            )
        elif path == "/api/settings":
            self._json(load_effective_settings(self.state.data_root).public_dict())
        elif path == "/api/scans/latest":
            scan = self.state.scan_manager.latest()
            self._json(scan.to_dict() if scan else {"status": "never_run"})
        elif path == "/api/recorder/purges":
            self._json({"items": self.state.purge_manager.history()})
        elif path.startswith("/api/scans/"):
            scan_id = path.rsplit("/", 1)[-1]
            scan = self.state.scan_manager.get(scan_id)
            if scan is None:
                self._json({"error": "Scan niet gevonden"}, HTTPStatus.NOT_FOUND)
            else:
                self._json(scan.to_dict())
        elif path.startswith("/api/reports/"):
            match = re.fullmatch(r"/api/reports/([a-zA-Z0-9]+)\.(json|csv|md)", path)
            file_path = report_path(self.state.report_root, match.group(1), match.group(2)) if match else None
            if file_path is None:
                self._json({"error": "Rapport niet gevonden"}, HTTPStatus.NOT_FOUND)
            else:
                self._download(file_path)
        elif path.startswith("/api/plans/"):
            match = re.fullmatch(r"/api/plans/([a-zA-Z0-9]+)\.(json|md)", path)
            file_path = self.state.plan_manager.path(match.group(1), match.group(2)) if match else None
            if file_path is None:
                self._json({"error": "Plan niet gevonden"}, HTTPStatus.NOT_FOUND)
            else:
                self._download(file_path)
        elif path == "/" or path.endswith("/index.html"):
            self._file(self.state.web_root / "index.html")
        elif "/assets/" in path:
            filename = path.split("/assets/", 1)[1]
            if "/" in filename or "\\" in filename or ".." in filename:
                self.send_error(HTTPStatus.NOT_FOUND)
            else:
                self._file(self.state.web_root / "assets" / filename)
        else:
            # Ingress may pass a path prefix. Serving the shell for unknown GETs
            # keeps client-side navigation prefix-safe.
            self._file(self.state.web_root / "index.html")

    def do_POST(self) -> None:
        path = urlsplit(self.path).path
        if path == "/api/scans":
            try:
                scan = self.state.scan_manager.start()
            except RuntimeError as exc:
                self._json({"error": str(exc)}, HTTPStatus.CONFLICT)
                return
            self._json(scan.to_dict(include_items=False), HTTPStatus.ACCEPTED)
        elif path == "/api/settings":
            body = self._read_json()
            try:
                settings = Settings(
                    min_temp_age_days=int(body.get("min_temp_age_days", 30)),
                    min_log_age_days=int(body.get("min_log_age_days", 14)),
                    deletion_mode=str(body.get("deletion_mode", "quarantine")),
                    retention_days=int(body.get("retention_days", 7)),
                    advanced_mode=_optional_bool(body, "advanced_mode", False),
                ).validated()
                save_local_settings(self.state.data_root, settings)
            except (TypeError, ValueError) as exc:
                self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return
            self._json(settings.public_dict())
        elif path == "/api/backups":
            try:
                result = create_full_backup()
            except SupervisorError as exc:
                self._json({"error": str(exc)}, HTTPStatus.SERVICE_UNAVAILABLE)
                return
            self._json({"status": "started", "backup": result}, HTTPStatus.ACCEPTED)
        elif path == "/api/related":
            body = self._read_json()
            item_type = str(body.get("item_type", ""))
            item_id = str(body.get("item_id", ""))
            if not item_id or len(item_id) > 255:
                self._json({"error": "Ongeldig relatie-item"}, HTTPStatus.BAD_REQUEST)
                return
            try:
                related = fetch_related(item_type, item_id)
            except HomeAssistantApiError as exc:
                self._json({"error": str(exc)}, HTTPStatus.SERVICE_UNAVAILABLE)
                return
            self._json({"item_type": item_type, "item_id": item_id, "related": related})
        elif path == "/api/recorder/purge":
            body = self._read_json()
            try:
                keep_days = int(body.get("keep_days", 10))
                repack = _required_bool(body, "repack")
                apply_filter = _required_bool(body, "apply_filter")
                backup_confirmed = _required_bool(body, "backup_confirmed")
                record = self.state.purge_manager.execute(
                    keep_days=keep_days,
                    repack=repack,
                    apply_filter=apply_filter,
                    backup_confirmed=backup_confirmed,
                    confirmation=str(body.get("confirmation", "")),
                )
            except (TypeError, ValueError) as exc:
                self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return
            except HomeAssistantApiError as exc:
                self._json({"error": str(exc)}, HTTPStatus.SERVICE_UNAVAILABLE)
                return
            except RuntimeError as exc:
                self._json({"error": str(exc)}, HTTPStatus.CONFLICT)
                return
            self._json({"status": "accepted", "record": asdict(record)}, HTTPStatus.ACCEPTED)
        elif path == "/api/plans/preview":
            body = self._read_json()
            try:
                plan = self.state.plan_manager.create(
                    self.state.scan_manager.latest(),
                    load_effective_settings(self.state.data_root),
                    selected_ids=_string_list(body, "selected_ids"),
                    selected_bundle_ids=_string_list(body, "selected_bundle_ids"),
                    backup_choice=str(body.get("backup_choice", "not_required_for_dry_run")),
                )
            except PlanError as exc:
                self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return
            self._json(
                {
                    "status": "dry_run_only",
                    "message": "Impact- en herstelplan opgeslagen; destructieve uitvoering blijft vergrendeld.",
                    "plan": plan,
                    "downloads": {
                        "json": f"api/plans/{plan['id']}.json",
                        "md": f"api/plans/{plan['id']}.md",
                    },
                },
                HTTPStatus.CREATED,
            )
        else:
            self._json({"error": "Endpoint niet gevonden"}, HTTPStatus.NOT_FOUND)

    def _read_json(self) -> dict[str, object]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(min(length, 1_000_000))
            value = json.loads(raw or b"{}")
            return value if isinstance(value, dict) else {}
        except (ValueError, json.JSONDecodeError):
            return {}

    def _json(self, payload: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _file(self, path: Path) -> None:
        if not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        data = path.read_bytes()
        mime, _ = mimetypes.guess_type(path.name)
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", (mime or "application/octet-stream") + ("; charset=utf-8" if path.suffix in {".html", ".css", ".js"} else ""))
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; connect-src 'self'")
        self.end_headers()
        self.wfile.write(data)

    def _download(self, path: Path) -> None:
        data = path.read_bytes()
        mime = {
            ".json": "application/json; charset=utf-8",
            ".csv": "text/csv; charset=utf-8",
            ".md": "text/markdown; charset=utf-8",
        }.get(path.suffix, "application/octet-stream")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Disposition", f'attachment; filename="{path.name}"')
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"{self.address_string()} - {fmt % args}", flush=True)


def create_server(host: str, port: int, config_root: Path, data_root: Path) -> ThreadingHTTPServer:
    web_root = Path(__file__).resolve().parent.parent / "web"
    data_root.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((host, port), CleanupHandler)
    server.state = AppState(config_root, data_root, web_root)  # type: ignore[attr-defined]
    return server


def _required_bool(body: dict[str, object], key: str) -> bool:
    value = body.get(key)
    if not isinstance(value, bool):
        raise ValueError(f"{key} moet true of false zijn")
    return value


def _optional_bool(body: dict[str, object], key: str, default: bool) -> bool:
    if key not in body:
        return default
    return _required_bool(body, key)


def _string_list(body: dict[str, object], key: str) -> list[str]:
    value = body.get(key, [])
    if not isinstance(value, list) or any(not isinstance(item, str) or len(item) > 255 for item in value):
        raise PlanError(f"{key} is ongeldig")
    return list(dict.fromkeys(value))


def run() -> None:
    host, port, config_root, data_root = environment()
    server = create_server(host, port, config_root, data_root)
    print(f"Hass-Cleaner {__version__} luistert op http://{host}:{port}", flush=True)
    server.serve_forever()
