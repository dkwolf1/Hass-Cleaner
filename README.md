# Hass-Cleaner

[Nederlands](#nederlands) · [English](#english)

Hass-Cleaner is a Home Assistant App for inspecting storage, stale entities and registry relationships before anything is cleaned up. Safety, evidence and recovery come before reclaimed space.

> **Release status:** version 0.9.0 is a release candidate under local development. Install it only for controlled testing and create a verified Home Assistant backup before executing any cleanup action.

## Nederlands

### Wat is Hass-Cleaner?

Hass-Cleaner helpt Home Assistant-gebruikers om vervuiling begrijpelijk en gecontroleerd te beoordelen. De app zoekt onder andere naar oude logs, opnieuw op te bouwen cachebestanden, langdurig onbeschikbare entities en afwijkende registerrelaties.

Een gevonden item is nooit automatisch verwijderbewijs. De app toont waarom iets is gevonden, wat het risico is, wat er kan gebeuren en hoe herstel werkt.

### Belangrijkste functies

- Veilige opslagscan met JSON-, CSV- en Markdownrapporten.
- Begrijpelijke opruimrecepten en technische detailweergave.
- Entities filteren op status, duur, integratie, apparaat en ruimte.
- Apparaten en entities bundelen per integratie of apparaat.
- Verschillen tussen scans: nieuw, gewijzigd, hersteld en verdwenen.
- Officiële Home Assistant Recorder-purge met afzonderlijke bevestiging.
- Quarantaine voor uitsluitend bewezen veilige bestanden.
- Hersteltest en terugplaatsen zonder bestaande bestanden te overschrijven.

### Veiligheidsmodel van 0.9.0

Een bestand kan alleen naar quarantaine als aan alle voorwaarden wordt voldaan:

1. Het bestand komt uit de laatste voltooide scan.
2. Bestandstype, pad, leeftijd en beschermde scopes leveren opnieuw de classificatie **veilig** op.
3. Grootte, wijzigingstijd en SHA-256 komen overeen met de scan.
4. Home Assistant Supervisor bevestigt dat de specifieke volledige back-up is voltooid en toegankelijk is.
5. De gebruiker bevestigt de actie met `QUARANTAINE`.

De volledige selectie wordt gecontroleerd voordat het eerste bestand wordt verplaatst. Quarantaine bewaart oorsprong, checksum, gebruiker, back-upbewijs en vervaldatum. Herstel vereist `HERSTEL` en overschrijft nooit een bestaand bestand.

Na de ingestelde bewaartermijn van 1–10 dagen wordt niets automatisch gewist. Definitief verwijderen is pas daarna beschikbaar, voert opnieuw een checksumcontrole uit en vereist `VERWIJDER`.

Registermutaties, automatische entityverwijdering en directe permanente verwijdering buiten quarantaine blijven geblokkeerd.

### Talen

- Home Assistant App-instellingen: Nederlands en Engels.
- README en roadmap: Nederlands en Engels.
- Ingress-interface: Nederlands; volledige Engelse UI is een vereiste vóór versie 1.0.

### Installeren vanuit GitHub

1. Open Home Assistant en ga naar **Instellingen → Apps → App store → Repositories**.
2. Voeg `https://github.com/dkwolf1/Hass-Cleaner` toe.
3. Installeer **Hass-Cleaner**.
4. Start de app en open de webinterface.
5. Voer eerst alleen een scan uit en beoordeel het rapport.

Versie 0.9.0 moet eerst naar GitHub worden gepusht en door de containerworkflow worden gebouwd voordat deze installatiestappen de nieuwe release opleveren.

### Lokaal ontwikkelen en testen

Voer deze opdrachten uit vanuit de map `hass_cleaner`:

```powershell
$env:HASS_CLEANER_CONFIG_ROOT = "$PWD\..\dev-fixtures\homeassistant"
$env:HASS_CLEANER_DATA_ROOT = "$PWD\..\data"
$env:HASS_CLEANER_HOST = "127.0.0.1"
$env:HASS_CLEANER_PORT = "8099"
python -m hass_cleaner
```

Open vervolgens `http://127.0.0.1:8099`.

```powershell
python -m unittest discover -s tests -v
node --check web/assets/app.js
```

Lees [ROADMAP.md](ROADMAP.md) voor de resterende releasecriteria.

---

## English

### What is Hass-Cleaner?

Hass-Cleaner helps Home Assistant users review accumulated data in a clear and controlled way. It can identify old logs, rebuildable cache files, persistently unavailable entities and inconsistent registry relationships.

A finding is never treated as deletion evidence by itself. The App explains why it was found, its risk, possible consequences and the available recovery path.

### Main features

- Safe storage scanning with JSON, CSV and Markdown reports.
- Beginner-friendly cleanup recipes and technical detail views.
- Entity filters for state, duration, integration, device and area.
- Device and entity grouping by integration or device.
- Scan differences for new, changed, recovered and disappeared signals.
- Official Home Assistant Recorder purge with separate confirmation.
- Quarantine for proven-safe files only.
- Restore testing and recovery without overwriting existing files.

### 0.9.0 safety model

A file can enter quarantine only when all conditions are satisfied:

1. It belongs to the latest completed scan.
2. Its type, path, age and protected scopes are reclassified as **safe** immediately before execution.
3. Its size, modification time and SHA-256 still match the scan.
4. Home Assistant Supervisor confirms that the specific full backup completed and is accessible.
5. The user confirms the operation with `QUARANTAINE`.

The entire selection is validated before the first file is moved. Quarantine records the original path, checksum, user, backup evidence and expiry time. Recovery requires `HERSTEL` and never overwrites an existing file.

Nothing is deleted automatically after the configured 1–10 day retention period. Permanent removal becomes available only after expiry, verifies the checksum again and requires `VERWIJDER`.

Registry mutations, automatic entity deletion and direct permanent deletion outside quarantine remain disabled.

### Languages

- Home Assistant App settings: Dutch and English.
- README and roadmap: Dutch and English.
- Ingress interface: Dutch; a complete English UI is a release requirement for version 1.0.

### Install from GitHub

1. In Home Assistant, open **Settings → Apps → App store → Repositories**.
2. Add `https://github.com/dkwolf1/Hass-Cleaner`.
3. Install **Hass-Cleaner**.
4. Start the App and open its web interface.
5. Run a scan first and review the report before preparing an action.

Version 0.9.0 must be pushed to GitHub and built by the container workflow before these steps install the new release.

### Local development and tests

Run the following from the `hass_cleaner` directory:

```powershell
$env:HASS_CLEANER_CONFIG_ROOT = "$PWD\..\dev-fixtures\homeassistant"
$env:HASS_CLEANER_DATA_ROOT = "$PWD\..\data"
$env:HASS_CLEANER_HOST = "127.0.0.1"
$env:HASS_CLEANER_PORT = "8099"
python -m hass_cleaner
```

Then open `http://127.0.0.1:8099`.

```powershell
python -m unittest discover -s tests -v
node --check web/assets/app.js
```

See [ROADMAP.md](ROADMAP.md) for the remaining release gates.

## Repository layout

```text
repository.yaml
hass_cleaner/
  config.yaml
  Dockerfile
  DOCS.md
  CHANGELOG.md
  translations/
  hass_cleaner/
  web/
  tests/
```

## License and contributions

Contributions are welcome, but cleanup rules must fail closed and include tests, impact information and a recovery path. See [CONTRIBUTING.md](CONTRIBUTING.md).
