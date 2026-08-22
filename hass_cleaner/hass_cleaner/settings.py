from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    min_temp_age_days: int = 30
    min_log_age_days: int = 14
    deletion_mode: str = "quarantine"
    retention_days: int = 7
    advanced_mode: bool = False
    report_retention_count: int = 10
    language: str = "auto"

    def validated(self) -> "Settings":
        if not 1 <= self.min_temp_age_days <= 365:
            raise ValueError("min_temp_age_days moet tussen 1 en 365 liggen")
        if not 1 <= self.min_log_age_days <= 365:
            raise ValueError("min_log_age_days moet tussen 1 en 365 liggen")
        if self.deletion_mode not in {"permanent", "quarantine"}:
            raise ValueError("deletion_mode moet permanent of quarantine zijn")
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
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                values = loaded
        except (OSError, json.JSONDecodeError):
            values = {}

    advanced_value = values.get("advanced_mode", False)
    return Settings(
        min_temp_age_days=int(values.get("min_temp_age_days", 30)),
        min_log_age_days=int(values.get("min_log_age_days", 14)),
        deletion_mode=str(values.get("deletion_mode", "quarantine")),
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
    path.write_text(json.dumps(asdict(settings), indent=2), encoding="utf-8")


def load_effective_settings(data_root: Path) -> Settings:
    override = data_root / "ui-settings.json"
    if override.exists():
        try:
            values = json.loads(override.read_text(encoding="utf-8"))
            return Settings(**values).validated()
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            pass
    return load_settings(data_root)


def environment() -> tuple[str, int, Path, Path]:
    host = os.environ.get("HASS_CLEANER_HOST", "127.0.0.1")
    port = int(os.environ.get("HASS_CLEANER_PORT", "8099"))
    config_root = Path(os.environ.get("HASS_CLEANER_CONFIG_ROOT", "/homeassistant"))
    data_root = Path(os.environ.get("HASS_CLEANER_DATA_ROOT", "/data"))
    return host, port, config_root, data_root
