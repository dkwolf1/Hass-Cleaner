from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from pathlib import Path

from .storage import atomic_write_json, read_json_object, json_file_lock


@dataclass(frozen=True)
class Settings:
    min_temp_age_days: int = 30
    min_log_age_days: int = 14
    retention_days: int = 7
    advanced_mode: bool = False
    report_retention_count: int = 10
    language: str = "auto"

    def validated(self) -> "Settings":
        if not 1 <= self.min_temp_age_days <= 365:
            raise ValueError("min_temp_age_days moet tussen 1 en 365 liggen")
        if not 1 <= self.min_log_age_days <= 365:
            raise ValueError("min_log_age_days moet tussen 1 en 365 liggen")
        if not 1 <= self.retention_days <= 10:
            raise ValueError("retention_days moet tussen 1 en 10 liggen")
        if not isinstance(self.advanced_mode, bool):
            raise ValueError("advanced_mode moet true of false zijn")
        if not 1 <= self.report_retention_count <= 50:
            raise ValueError("report_retention_count moet tussen 1 en 50 liggen")
        if self.language not in {"auto", "nl", "en"}:
            raise ValueError("language moet auto, nl of en zijn")
        return self

    def public_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["backup_prompt_required"] = True
        return result


def _options_path(data_root: Path) -> Path:
    return data_root / "options.json"


def load_settings(data_root: Path) -> Settings:
    values: dict[str, object] = {}
    path = _options_path(data_root)
    if path.exists():
        values = read_json_object(path)

    advanced_value = values.get("advanced_mode", False)
    return Settings(
        min_temp_age_days=int(values.get("min_temp_age_days", 30)),
        min_log_age_days=int(values.get("min_log_age_days", 14)),
        retention_days=int(values.get("retention_days", 7)),
        advanced_mode=advanced_value if isinstance(advanced_value, bool) else False,
        report_retention_count=int(values.get("report_retention_count", 10)),
        language=str(values.get("language", "auto")),
    ).validated()


def save_local_settings(data_root: Path, settings: Settings) -> None:
    """Persist settings during local development.

    On Home Assistant OS, Supervisor owns /data/options.json. The API therefore
    stores UI overrides in a separate file and never rewrites Supervisor options.
    """
    data_root.mkdir(parents=True, exist_ok=True)
    path = data_root / "ui-settings.json"
    with json_file_lock(path):
        atomic_write_json(path, {**asdict(settings.validated()), "_supervisor_snapshot": asdict(load_settings(data_root))})


def load_effective_settings(data_root: Path) -> Settings:
    override = data_root / "ui-settings.json"
    with json_file_lock(override):
        base = load_settings(data_root)
        if not override.exists():
            return base
        try:
            values = read_json_object(override)
            values.pop("deletion_mode", None)
            snapshot = values.pop("_supervisor_snapshot", None)
            current = asdict(base)
            if isinstance(snapshot, dict):
                # Only changed Supervisor fields supersede UI choices. Persist
                # the new baseline so subsequent UI changes can win again.
                values.update({key: value for key, value in current.items() if snapshot.get(key) != value})
            elif _options_path(data_root).exists() and _options_path(data_root).stat().st_mtime_ns > override.stat().st_mtime_ns:
                values = current
            effective = Settings(**values).validated()
            stored = {**asdict(effective), "_supervisor_snapshot": current}
            if snapshot != current or values != asdict(effective):
                atomic_write_json(override, stored)
            return effective
        except (TypeError, ValueError):
            return base


def environment() -> tuple[str, int, Path, Path]:
    host = os.environ.get("HASS_CLEANER_HOST", "127.0.0.1")
    port = int(os.environ.get("HASS_CLEANER_PORT", "8099"))
    config_root = Path(os.environ.get("HASS_CLEANER_CONFIG_ROOT", "/homeassistant"))
    data_root = Path(os.environ.get("HASS_CLEANER_DATA_ROOT", "/data"))
    return host, port, config_root, data_root
