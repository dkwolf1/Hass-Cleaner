from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


MAX_PREVIEW_BYTES = 256_000
SENSITIVE_KEY = re.compile(r"(?:pass(?:word)?|token|secret|api[_-]?key|credential|authorization|private[_-]?key|access[_-]?key)", re.I)
YAML_KEY = re.compile(r"^\s*(?:-\s*)?([A-Za-z_][A-Za-z0-9_.-]*)\s*:")
CODE_SYMBOL = re.compile(r"^\s*(?:async\s+)?(?:def|class|function)\s+([A-Za-z_][A-Za-z0-9_]*)", re.M)
IMPORT_NAME = re.compile(r"^\s*(?:from\s+([A-Za-z0-9_.]+)\s+import|import\s+([A-Za-z0-9_.]+))", re.M)


def analyze_file(path: Path, category: str, risk: str, reason: str) -> dict[str, Any]:
    profile = _category_profile(category)
    preview = _content_preview(path)
    return {
        "evidence_level": profile["evidence_level"],
        "evidence_label": profile["evidence_label"],
        "summary": profile["summary"],
        "reason": reason,
        "possible_consequences": profile["possible_consequences"],
        "recovery_steps": profile["recovery_steps"],
        "recommended_first_step": profile["recommended_first_step"],
        "content_preview": preview,
        "sensitive_values_redacted": True,
        "execution_allowed": False,
        "risk": risk,
    }


def analyze_bundle(
    *,
    devices: list[dict[str, Any]],
    entities: list[dict[str, Any]],
    review_count: int,
) -> dict[str, Any]:
    domains = Counter(str(item.get("entity_id", "")).partition(".")[0] for item in entities if item.get("entity_id"))
    disabled = sum(1 for item in entities if item.get("disabled"))
    parents = sum(1 for item in devices if item.get("child_device_ids"))
    evidence_level = "high_risk" if review_count else "insufficient"
    evidence_label = "Hoog risico" if review_count else "Meer bewijs nodig"
    return {
        "evidence_level": evidence_level,
        "evidence_label": evidence_label,
        "summary": "Samenhangende Home Assistant-objecten van dezelfde integratie of hetzelfde platform.",
        "possible_consequences": [
            "Entities kunnen uit dashboards, automatiseringen en scripts verdwijnen.",
            "Een apparaat kan opnieuw door de integratie worden aangemaakt.",
            "Het verwijderen van een config-entry kan de volledige integratie uitschakelen.",
        ],
        "recovery_steps": [
            "Herstel de Home Assistant-back-up als registrygegevens verloren zijn.",
            "Voeg de eigenaar-integratie opnieuw toe en configureer het apparaat opnieuw.",
            "Herstel daarna afhankelijke automatiseringen en dashboards uit het planrapport.",
        ],
        "recommended_first_step": "Beoordeel eerst alle officiële search/related-verwijzingen; schakel losse entities zo mogelijk tijdelijk uit.",
        "content_preview": {
            "kind": "registry_structure",
            "device_count": len(devices),
            "entity_count": len(entities),
            "disabled_entity_count": disabled,
            "parent_device_count": parents,
            "entity_domains": dict(domains.most_common()),
        },
        "sensitive_values_redacted": True,
        "execution_allowed": False,
    }


def _content_preview(path: Path) -> dict[str, Any]:
    try:
        size = path.stat().st_size
    except OSError:
        return {"kind": "unavailable", "message": "Bestandsmetadata kon niet worden gelezen."}
    if size > MAX_PREVIEW_BYTES:
        return {"kind": "metadata_only", "message": "Bestand is te groot voor een veilige inhoudspreview.", "size_bytes": size}
    if path.suffix.lower() in {".pyc", ".pyo", ".db", ".sqlite", ".wal", ".shm"}:
        return {"kind": "binary", "message": "Binaire inhoud wordt nooit getoond.", "size_bytes": size}
    try:
        text = path.read_text(encoding="utf-8", errors="strict")
    except (OSError, UnicodeError):
        return {"kind": "binary_or_unknown", "message": "Geen betrouwbare UTF-8-tekstpreview beschikbaar.", "size_bytes": size}

    lower_name = path.name.lower()
    if lower_name.endswith(".json") or ".json." in lower_name:
        try:
            value = json.loads(text)
        except json.JSONDecodeError:
            return _text_structure(text)
        return {"kind": "json_keys", "key_paths": _json_key_paths(value), "line_count": text.count("\n") + 1}
    if any(marker in lower_name for marker in (".yaml", ".yml")):
        keys = []
        sensitive = []
        for line in text.splitlines():
            match = YAML_KEY.match(line)
            if not match:
                continue
            key = match.group(1)
            (sensitive if SENSITIVE_KEY.search(key) else keys).append(key)
        return {
            "kind": "yaml_keys",
            "keys": _unique(keys)[:80],
            "redacted_sensitive_keys": len(_unique(sensitive)),
            "line_count": text.count("\n") + 1,
        }
    if any(marker in lower_name for marker in (".py", ".js", ".ts")):
        imports = [left or right for left, right in IMPORT_NAME.findall(text)]
        return {
            "kind": "code_structure",
            "symbols": _unique(CODE_SYMBOL.findall(text))[:60],
            "imports": _unique(imports)[:40],
            "line_count": text.count("\n") + 1,
        }
    return _text_structure(text)


def _text_structure(text: str) -> dict[str, Any]:
    sensitive_lines = sum(1 for line in text.splitlines() if SENSITIVE_KEY.search(line))
    return {
        "kind": "text_metadata",
        "line_count": text.count("\n") + 1,
        "non_empty_lines": sum(1 for line in text.splitlines() if line.strip()),
        "redacted_sensitive_lines": sensitive_lines,
        "message": "Ruwe tekstwaarden worden uit veiligheid niet in het rapport opgenomen.",
    }


def _json_key_paths(value: Any, prefix: str = "", depth: int = 0) -> list[str]:
    if depth > 2:
        return []
    paths: list[str] = []
    if isinstance(value, dict):
        for raw_key, child in list(value.items())[:80]:
            key = str(raw_key)
            display = "<gevoelige sleutel>" if SENSITIVE_KEY.search(key) else key
            path = f"{prefix}.{display}" if prefix else display
            paths.append(path)
            paths.extend(_json_key_paths(child, path, depth + 1))
    elif isinstance(value, list) and value:
        paths.extend(_json_key_paths(value[0], f"{prefix}[]", depth + 1))
    return _unique(paths)[:120]


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _category_profile(category: str) -> dict[str, Any]:
    profiles: dict[str, dict[str, Any]] = {
        "python_cache": _profile("strong", "Sterk bewijs", "Gegenereerde Python-bytecode met aantoonbare broncode.", ["De cache wordt bij gebruik opnieuw opgebouwd; de eerste start kan iets langer duren."], ["Herstart de integratie of Home Assistant zodat Python de cache opnieuw maakt."], "Plaats eerst in quarantaine; permanent verwijderen is doorgaans herstelbaar."),
        "brand_cache": _profile("strong", "Sterk bewijs", "Gegenereerde Home Assistant-pictogramcache op het exact bekende cachepad.", ["Pictogrammen kunnen kort ontbreken terwijl Home Assistant ze opnieuw ophaalt."], ["Herlaad Home Assistant; de pictogramcache wordt opnieuw opgebouwd."], "Kies Opschoning voorbereiden en gebruik daarna quarantaine."),
        "editor_artifact": _profile("strong", "Sterk bewijs", "Bekend editor- of besturingssysteemrestant.", ["Een editor of besturingssysteem kan het bestand opnieuw aanmaken."], ["Geen herstel nodig; plaats het bestand desgewenst terug uit quarantaine."], "Quarantaine is de veiligste eerste stap."),
        "old_log": _profile("likely", "Waarschijnlijk veilig", "Niet-actief oud Home Assistant-logbestand.", ["Oude diagnose-informatie gaat verloren."], ["Zet het bestand vanuit quarantaine terug als oude logregels nodig zijn."], "Controleer of er geen lopend onderzoek is en gebruik daarna quarantaine."),
        "temporary_or_backup": _profile("insufficient", "Meer bewijs nodig", "Bestandsnaam wijst op een tijdelijke kopie of handmatige back-up.", ["Dit kan de enige werkende kopie van configuratie of code zijn."], ["Zet het bestand terug uit quarantaine en vergelijk het met de actieve versie."], "Vergelijk inhoud en wijzigingsdatum met het actieve bestand."),
        "python_cache_without_source": _profile("insufficient", "Meer bewijs nodig", "Bytecode zonder aantoonbaar bijbehorend bronbestand.", ["Een custom integratie kan hierdoor niet meer laden."], ["Zet de bytecode terug of installeer de bijbehorende integratie opnieuw."], "Niet verwijderen totdat de eigenaar van de bytecode bekend is."),
        "custom_components": _profile("high_risk", "Hoog risico", "Onderdeel van een custom integratie.", ["De integratie en bijbehorende entities kunnen stoppen of verdwijnen."], ["Zet de volledige componentmap terug of installeer dezelfde versie opnieuw."], "Beoordeel de volledige integratiebundel; verwijder nooit één willekeurig bronbestand."),
        "frontend_package": _profile("blocked", "Behouden", "Geïnstalleerd HACS- of frontendpakket.", ["Dashboardkaarten kunnen verdwijnen of niet meer laden."], ["Installeer exact hetzelfde pakket en dezelfde versie opnieuw."], "Niet via bestandsopschoning verwijderen."),
        "www_asset_inventory": _profile("blocked", "Behouden", "Bestand kan door dashboards, thema's of kaarten worden gebruikt.", ["Afbeeldingen, scripts of dashboardkaarten kunnen niet meer laden."], ["Zet hetzelfde pad terug en herlaad de browsercache."], "Alleen via de technische inventaris bekijken."),
        "integration_cache_candidate": _profile("insufficient", "Meer bewijs nodig", "Padnaam wijst op cache van een integratie of toepassing.", ["Actieve previews, afdrukken, camerabeelden of indexen kunnen verdwijnen."], ["Laat de eigenaar-integratie de cache opnieuw opbouwen of herstel een back-up."], "Controleer producent, verwijzingen en herbouwgedrag; nog niet verwijderen."),
        "personal_media": _profile("high_risk", "Persoonlijke inhoud", "Opname, snapshot of timelapse is gebruikersdata.", ["De opname of afbeelding kan permanent verloren gaan."], ["Herstel uit een volledige back-up of externe mediakopie."], "Alleen bewust beoordelen; nooit als cache behandelen."),
        "home_assistant_storage": _profile("blocked", "Geblokkeerd", "Intern Home Assistant-registerbestand.", ["Direct wijzigen kan registers beschadigen of Home Assistant onstartbaar maken."], ["Herstel een volledige back-up; wijzig registers alleen via officiële API's."], "Nooit rechtstreeks verwijderen of bewerken."),
        "core_configuration": _profile("blocked", "Geblokkeerd", "Kritiek configuratiebestand.", ["Home Assistant kan niet meer starten of automatiseringen kunnen verdwijnen."], ["Herstel het bestand of een volledige back-up en voer configuratiecontrole uit."], "Nooit via bestandsopschoning verwijderen."),
        "database": _profile("blocked", "Geblokkeerd", "Actieve of ondersteunende database.", ["Historie en statistieken kunnen verloren gaan; de database kan beschadigen."], ["Herstel de databaseback-up of volledige Home Assistant-back-up."], "Gebruik uitsluitend de officiële Recorder-purgeactie."),
        "symlink": _profile("blocked", "Geblokkeerd", "Symbolische link met mogelijk doel buiten de scanroot.", ["Verwijderen kan onverwachte paden of koppelingen beïnvloeden."], ["Maak dezelfde link opnieuw met het oorspronkelijke doel."], "Handmatig beoordelen buiten Hass-Cleaner."),
    }
    return profiles.get(category, _profile("insufficient", "Meer bewijs nodig", "Onbekend of onvoldoende geclassificeerd bestand.", ["Onbekende afhankelijkheden kunnen stoppen."], ["Herstel uit quarantaine of uit een volledige back-up."], "Niet verwijderen zonder aanvullende analyse."))


def _profile(level: str, label: str, summary: str, consequences: list[str], recovery: list[str], first_step: str) -> dict[str, Any]:
    return {
        "evidence_level": level,
        "evidence_label": label,
        "summary": summary,
        "possible_consequences": consequences,
        "recovery_steps": recovery,
        "recommended_first_step": first_step,
    }
