"""Build a local install archive containing only the companion's source files."""
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED


def build():
    root = Path(__file__).resolve().parents[1]
    source = root / "custom_components" / "hass_cleaner"
    version = json.loads((source / "manifest.json").read_text(encoding="utf-8"))["version"]
    destination = root / "dist" / f"hass-cleaner-companion-{version}.zip"
    destination.parent.mkdir(exist_ok=True)
    paths = sorted([*source.glob("*.py"), *source.glob("*.json"), *source.glob("translations/*.json")])
    with ZipFile(destination, "w", ZIP_DEFLATED) as archive:
        for path in paths:
            archive.write(path, path.relative_to(root).as_posix())
        archive.write(root / "LICENSE", "custom_components/hass_cleaner/LICENSE")
    with ZipFile(destination) as archive:
        assert archive.testzip() is None
        assert "custom_components/hass_cleaner/manifest.json" in archive.namelist()
    print(destination)


if __name__ == "__main__":
    build()
