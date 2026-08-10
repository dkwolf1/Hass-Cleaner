from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime


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
