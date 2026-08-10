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


class CleanupHandler(BaseHTTPRequestHandler):
    server_version = "HassCleaner/0.2"

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
                    "destructive_execution_enabled": False,
                    "config_mount_expected_read_only": True,
                    "backup_available": supervisor_available(),
                }
            )
        elif path == "/api/settings":
            self._json(load_effective_settings(self.state.data_root).public_dict())
        elif path == "/api/scans/latest":
            scan = self.state.scan_manager.latest()
            self._json(scan.to_dict() if scan else {"status": "never_run"})
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
        elif path == "/api/plans/preview":
            body = self._read_json()
            self._json(
                {
                    "status": "dry_run_only",
                    "message": "Destructieve uitvoering is in versie 0.1.0 nog vergrendeld.",
                    "backup_choice": body.get("backup_choice"),
                    "deletion_mode": body.get("deletion_mode"),
                    "retention_days": body.get("retention_days"),
                    "selected_ids": body.get("selected_ids", []),
                },
                HTTPStatus.ACCEPTED,
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


def run() -> None:
    host, port, config_root, data_root = environment()
    server = create_server(host, port, config_root, data_root)
    print(f"Hass-Cleaner {__version__} luistert op http://{host}:{port}", flush=True)
    server.serve_forever()
