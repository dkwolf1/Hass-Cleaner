from __future__ import annotations

import argparse
from pathlib import Path

from .reporting import write_report_files
from .scanner import scan_tree
from .settings import Settings


def main() -> int:
    parser = argparse.ArgumentParser(description="Maak een read-only Hass-Cleaner auditrapport")
    parser.add_argument("--root", required=True, type=Path, help="Te scannen Home Assistant-configuratiemap")
    parser.add_argument("--output", required=True, type=Path, help="Directory voor JSON, CSV en Markdown")
    parser.add_argument("--min-temp-age-days", type=int, default=30)
    parser.add_argument("--min-log-age-days", type=int, default=14)
    args = parser.parse_args()

    settings = Settings(
        min_temp_age_days=args.min_temp_age_days,
        min_log_age_days=args.min_log_age_days,
    ).validated()
    result = scan_tree(args.root.resolve(), settings)
    if result.status != "completed":
        print(result.error or "Scan mislukt")
        return 1
    paths = write_report_files(result, settings, args.output.resolve())
    print(f"Scan-ID: {result.id}")
    print(f"Bekeken bestanden: {result.visited_files}")
    for kind, path in paths.items():
        print(f"{kind.upper()}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
