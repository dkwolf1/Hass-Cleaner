from __future__ import annotations

import os
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .policy import Classification, RISK_PROTECTED, RISK_REVIEW, RISK_SAFE, classify
from .registry_audit import RegistryAudit, scan_home_assistant_registries
from .settings import Settings


@dataclass(frozen=True)
class ScanItem:
    id: str
    path: str
    category: str
    risk: str
    reason: str
    recommended_action: str
    size_bytes: int
    modified_at: str


@dataclass
class ScanResult:
    id: str
    status: str = "queued"
    started_at: str | None = None
    finished_at: str | None = None
    current_path: str = ""
    visited_files: int = 0
    ignored_files: int = 0
    items: list[ScanItem] = field(default_factory=list)
    registry_audit: RegistryAudit = field(default_factory=lambda: RegistryAudit(status="not_run"))
    error: str | None = None

    def to_dict(self, *, include_items: bool = True) -> dict[str, object]:
        totals = {RISK_SAFE: 0, RISK_REVIEW: 0, RISK_PROTECTED: 0}
        counts = {RISK_SAFE: 0, RISK_REVIEW: 0, RISK_PROTECTED: 0}
        for item in self.items:
            totals[item.risk] += item.size_bytes
            counts[item.risk] += 1
        payload: dict[str, object] = {
            "id": self.id,
            "status": self.status,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "current_path": self.current_path,
            "visited_files": self.visited_files,
            "ignored_files": self.ignored_files,
            "totals": totals,
            "counts": counts,
            "error": self.error,
        }
        if include_items:
            payload["items"] = [asdict(item) for item in self.items]
        payload["registry_audit"] = self.registry_audit.to_dict()
        return payload


def scan_tree(root: Path, settings: Settings, scan_id: str | None = None) -> ScanResult:
    result = ScanResult(id=scan_id or uuid.uuid4().hex, status="running")
    result.started_at = datetime.now(timezone.utc).isoformat()
    if not root.exists() or not root.is_dir():
        result.status = "failed"
        result.error = f"Scanroot bestaat niet of is geen directory: {root}"
        result.finished_at = datetime.now(timezone.utc).isoformat()
        return result

    stack = [root]
    seen_inodes: set[tuple[int, int]] = set()
    try:
        while stack:
            directory = stack.pop()
            result.current_path = _display_path(root, directory)
            try:
                entries = list(os.scandir(directory))
            except (OSError, PermissionError):
                continue
            for entry in entries:
                path = Path(entry.path)
                try:
                    metadata = entry.stat(follow_symlinks=False)
                except (OSError, PermissionError, FileNotFoundError):
                    continue
                if entry.is_dir(follow_symlinks=False):
                    stack.append(path)
                    continue
                result.visited_files += 1
                decision = classify(
                    root,
                    path,
                    metadata.st_mode,
                    metadata.st_mtime,
                    min_temp_age_days=settings.min_temp_age_days,
                    min_log_age_days=settings.min_log_age_days,
                )
                if decision is None:
                    result.ignored_files += 1
                    continue
                if decision.category == "python_cache" and not _python_source_exists(path):
                    decision = Classification(
                        "python_cache_without_source",
                        RISK_REVIEW,
                        "Python-cache heeft geen aantoonbaar bijbehorend .py-bronbestand",
                        "review",
                    )
                # Windows may report st_ino=0. Only deduplicate when the
                # platform supplies a real inode and the file has hardlinks.
                inode_key = (metadata.st_dev, metadata.st_ino)
                deduplicate = bool(metadata.st_ino) and metadata.st_nlink > 1
                size = 0 if deduplicate and inode_key in seen_inodes else metadata.st_size
                if deduplicate:
                    seen_inodes.add(inode_key)
                result.items.append(
                    ScanItem(
                        id=uuid.uuid4().hex,
                        path=_display_path(root, path),
                        category=decision.category,
                        risk=decision.risk,
                        reason=decision.reason,
                        recommended_action=decision.recommended_action,
                        size_bytes=size,
                        modified_at=datetime.fromtimestamp(metadata.st_mtime, tz=timezone.utc).isoformat(),
                    )
                )
        result.status = "completed"
    except Exception as exc:  # fail closed; unexpected errors are visible in the UI
        result.status = "failed"
        result.error = f"{type(exc).__name__}: {exc}"
    result.current_path = ""
    result.finished_at = datetime.now(timezone.utc).isoformat()
    return result


def _display_path(root: Path, path: Path) -> str:
    relative = path.relative_to(root)
    return "/homeassistant" if not relative.parts else "/homeassistant/" + relative.as_posix()


def _python_source_exists(path: Path) -> bool:
    if path.parent.name != "__pycache__":
        return False
    stem = path.name.split(".cpython-", 1)[0]
    if stem == path.name:
        return False
    return (path.parent.parent / f"{stem}.py").is_file()


class ScanManager:
    def __init__(self, root: Path, settings_loader, report_dir: Path | None = None, registry_scanner=scan_home_assistant_registries):
        self.root = root
        self.settings_loader = settings_loader
        self.report_dir = report_dir
        self.registry_scanner = registry_scanner
        self._lock = threading.Lock()
        self._scans: dict[str, ScanResult] = {}
        self._latest_id: str | None = None

    def start(self) -> ScanResult:
        scan = ScanResult(id=uuid.uuid4().hex)
        with self._lock:
            if any(item.status in {"queued", "running"} for item in self._scans.values()):
                raise RuntimeError("Er loopt al een scan")
            self._scans[scan.id] = scan
            self._latest_id = scan.id
        threading.Thread(target=self._run, args=(scan.id,), daemon=True, name=f"scan-{scan.id[:8]}").start()
        return scan

    def _run(self, scan_id: str) -> None:
        settings = self.settings_loader()
        completed = scan_tree(self.root, settings, scan_id)
        if completed.status == "completed":
            completed.registry_audit = self.registry_scanner()
        if completed.status == "completed" and self.report_dir is not None:
            from .reporting import write_report_files

            write_report_files(completed, settings, self.report_dir)
        with self._lock:
            self._scans[scan_id] = completed

    def get(self, scan_id: str) -> ScanResult | None:
        with self._lock:
            return self._scans.get(scan_id)

    def latest(self) -> ScanResult | None:
        with self._lock:
            return self._scans.get(self._latest_id) if self._latest_id else None
