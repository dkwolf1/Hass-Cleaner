# Hass-Cleaner

[English](#english) · [Nederlands](#nederlands) · [Wiki](https://github.com/dkwolf1/Hass-Cleaner/wiki) · [Releases](https://github.com/dkwolf1/Hass-Cleaner/releases)

Hass-Cleaner is a Home Assistant App for inspecting storage, stale entities and registry relationships before anything is cleaned up. Safety, informed user choice and recovery come before reclaimed space.

> **Release status:** version 1.0.2 is the current maintenance release for controlled early use. Hass-Cleaner provides facts, advice, backup options and recovery guidance; the user makes the final cleanup decision.

## English

**Development preview: 1.1.0.** This checkout adds [reference checks and native Repairs](docs/reference-checks.md) through an optional, separately installed **Hass-Cleaner Companion** integration. This is not a published release or a claim of complete reference coverage. Live Home Assistant acceptance testing is still required.

> [!WARNING]
> **Test version — handle with care.** Hass-Cleaner can modify files, Home Assistant registry objects and Recorder data. Review every selection and preferably create a full Home Assistant backup first. Test on a non-critical installation where possible. Use is at your own risk; quarantine and recovery safeguards reduce risk, but cannot guarantee that every integration or user configuration remains unaffected.

### What is Hass-Cleaner?

Hass-Cleaner helps Home Assistant users review accumulated data in a clear and controlled way. It can identify old logs, rebuildable cache files, persistently unavailable entities and inconsistent registry relationships.

A finding is never treated as deletion evidence by itself. The App explains why it was found, its risk, possible consequences and the available recovery path.

### Main features

- Safe storage scanning with one clear export dialog: a readable Markdown report, CSV for spreadsheet analysis and JSON for technical analysis.
- Beginner-friendly cleanup categories and a clear **Prepare cleanup** action.
- Entity filters for state, duration, integration, device and area.
- Optional companion: static references in automations, scripts, dashboards, scenes, groups, supported helpers/templates and energy/statistics configuration; native Repairs for missing targets and dependency context before registry cleanup. Coverage limits are explicit.
- Device and entity grouping by integration or device.
- Scan differences for new, changed, recovered and disappeared signals.
- Official Home Assistant Recorder purge with separate confirmation.
- Quarantine for safe, personal and explicitly user-reviewed files; protected core files remain excluded.
- User-directed removal of registered entities and supported device bundles through Home Assistant's official API.
- Clearable local scan and completed-quarantine logs for a clean start.
- Restore testing and recovery without overwriting existing files.

### 1.0.x safety model

A file can enter quarantine only when all conditions are satisfied:

1. It belongs to the latest completed scan.
2. Its type, path, age, risk class and protected scopes still match the scan immediately before execution.
3. Its size, modification time and SHA-256 still match the scan.
4. The user explicitly chooses a Supervisor-verified backup, a manually checked recent backup or proceeding without a backup.
5. Deviating from the recommended verified backup requires an additional risk acknowledgement.
6. The user confirms the operation with `QUARANTAINE`.

The complete selection is validated before the first file is moved. Quarantine records the original path, checksum, user, backup evidence and expiry time. Recovery requires `HERSTEL` and never overwrites an existing file.

Nothing is deleted automatically after the configured 1–10 day retention period. Permanent removal becomes available only after expiry, verifies the checksum again and requires `VERWIJDER`.

Personal or uncertain content requires an additional content acknowledgement. Registry cleanup requires displayed advice, a backup choice, risk acknowledgement and exact count confirmation. Runtime-only entities and protected core files remain technically excluded.

### Documentation

The [Hass-Cleaner Wiki](https://github.com/dkwolf1/Hass-Cleaner/wiki) contains the user guide, including:

- installation and updates;
- the recommended first scan;
- file classification and quarantine;
- entity and bundle review;
- Recorder cleanup and backups;
- settings, reports and troubleshooting;
- safety and recovery guidance;
- a concise Dutch quick-start.

For version-specific changes, see [CHANGELOG.md](hass_cleaner/CHANGELOG.md). For planned work and release criteria, see [ROADMAP.md](ROADMAP.md).

### Languages

- Project documentation and GitHub communication use English as the primary language and Dutch as the secondary language.
- Interface and Home Assistant App settings support Automatic, English and Nederlands.
- Automatic uses the browser or Home Assistant display language and falls back to English for unsupported languages.
- Both configuration locations work: changed App configuration fields override their saved UI values; unchanged fields retain your UI choices. Saving in Hass-Cleaner applies your new choices again. Supervisor options are not rewritten by UI saves.

### Install from GitHub

1. In Home Assistant, open **Settings → Apps → App store → Repositories**.
2. Add `https://github.com/dkwolf1/Hass-Cleaner`.
3. Install **Hass-Cleaner**.
4. Start the App and open its web interface.
5. Run a scan first and review the report before preparing an action.

GitHub Actions builds the version in `hass_cleaner/config.yaml` for `amd64` and `aarch64`. After the container is published, Home Assistant can install or update that version through this repository. The companion is a separate integration, not part of the app container.

### Local development and tests

Run the following commands from the `hass_cleaner` directory:

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

---

## Nederlands

> [!WARNING]
> **Testversie — voorzichtig gebruiken.** Hass-Cleaner kan bestanden, Home Assistant-registerobjecten en Recorder-gegevens wijzigen. Controleer iedere selectie en maak vooraf bij voorkeur een volledige Home Assistant-back-up. Test waar mogelijk eerst op een niet-kritische installatie. Gebruik is op eigen risico; quarantaine en herstelvoorzieningen verkleinen het risico, maar kunnen niet garanderen dat iedere integratie of gebruikersconfiguratie zonder gevolgen blijft werken.

### Wat is Hass-Cleaner?

Hass-Cleaner helpt Home Assistant-gebruikers om verzamelde gegevens begrijpelijk en gecontroleerd te beoordelen. De App zoekt onder andere naar oude logs, opnieuw op te bouwen cachebestanden, langdurig onbeschikbare entities en afwijkende registerrelaties.

Een gevonden onderdeel is nooit automatisch verwijderbewijs. De App toont waarom iets is gevonden, wat het risico is, wat er kan gebeuren en hoe herstel werkt.

### Belangrijkste functies

- Veilige opslagscan met één duidelijk exportvenster: een leesbaar Markdownrapport, CSV voor spreadsheetanalyse en JSON voor technische analyse.
- Begrijpelijke opruimcategorieën en de actie **Opschoning voorbereiden**.
- Entities filteren op status, duur, integratie, apparaat en ruimte.
- Apparaten en entities bundelen per integratie of apparaat.
- Verschillen tussen scans: nieuw, gewijzigd, hersteld en verdwenen.
- Officiële Home Assistant Recorder-purge met afzonderlijke bevestiging.
- Quarantaine voor veilige, persoonlijke en door de gebruiker beoordeelde bestanden; beschermde kernbestanden blijven uitgesloten.
- Gebruikersgestuurde verwijdering van geregistreerde entities en ondersteunde apparaatbundels via de officiële Home Assistant-API.
- Wisbare lokale scan- en afgeronde quarantainelogboeken voor een schone start.
- Hersteltest en terugplaatsen zonder bestaande bestanden te overschrijven.

### Veiligheidsmodel van 1.0.x

Een bestand kan alleen naar quarantaine als aan alle voorwaarden wordt voldaan:

1. Het bestand komt uit de laatste voltooide scan.
2. Bestandstype, pad, leeftijd, risicoklasse en beschermde scopes komen vlak voor uitvoering nog overeen met de scan.
3. Grootte, wijzigingstijd en SHA-256 komen overeen met de scan.
4. De gebruiker kiest bewust voor een door Supervisor geverifieerde back-up, een zelf gecontroleerde recente back-up of doorgaan zonder back-up.
5. Afwijken van de aanbevolen geverifieerde back-up vereist een extra risicobevestiging.
6. De gebruiker bevestigt de actie met `QUARANTAINE`.

De volledige selectie wordt gecontroleerd voordat het eerste bestand wordt verplaatst. Quarantaine bewaart het oorspronkelijke pad, de checksum, de gebruiker, het back-upbewijs en de vervaldatum. Herstel vereist `HERSTEL` en overschrijft nooit een bestaand bestand.

Na de ingestelde bewaartermijn van 1–10 dagen wordt niets automatisch gewist. Definitief verwijderen is pas daarna beschikbaar, voert opnieuw een checksumcontrole uit en vereist `VERWIJDER`.

Persoonlijke of onzekere inhoud vereist een extra inhoudsbevestiging. Registeropschoning vereist adviesweergave, back-upkeuze, risicobevestiging en een exact aantal. Runtime-only entities en beschermde kernbestanden blijven technisch uitgesloten.

### Documentatie

De [Hass-Cleaner Wiki](https://github.com/dkwolf1/Hass-Cleaner/wiki) bevat de uitgebreide Engelstalige handleiding en een korte Nederlandse snelstart. Onderwerpen zijn onder andere:

- installatie en updates;
- de aanbevolen eerste scan;
- bestandsclassificatie en quarantaine;
- beoordeling van entities en bundels;
- Recorder-opschoning en back-ups;
- instellingen, rapporten en probleemoplossing;
- veiligheid en herstel.

Versiegebonden wijzigingen staan in [CHANGELOG.md](hass_cleaner/CHANGELOG.md). Gepland werk en releasecriteria staan in [ROADMAP.md](ROADMAP.md).

### Talen

- Projectdocumentatie en GitHub-communicatie gebruiken Engels als primaire taal en Nederlands als tweede taal.
- De interface en Home Assistant App-instellingen ondersteunen Automatisch, English en Nederlands.
- Automatisch gebruikt de browser- of Home Assistant-weergavetaal en valt bij een niet-ondersteunde taal terug op Engels.
- Beide configuratieplekken werken: gewijzigde App-instellingen krijgen per veld voorrang; overige UI-keuzes blijven behouden. Opnieuw opslaan binnen Hass-Cleaner past je nieuwe keuze toe.

### Installeren vanuit GitHub

1. Open in Home Assistant **Instellingen → Apps → App store → Repositories**.
2. Voeg `https://github.com/dkwolf1/Hass-Cleaner` toe.
3. Installeer **Hass-Cleaner**.
4. Start de App en open de webinterface.
5. Voer eerst een scan uit en beoordeel het rapport voordat je een actie voorbereidt.

GitHub Actions bouwt de versie uit `hass_cleaner/config.yaml` voor `amd64` en `aarch64`. Na publicatie van de container kan Home Assistant die versie installeren of bijwerken. De ontwikkelversie 1.1.0 bevat [referentiecontrole en Reparaties](docs/reference-checks.md#nederlands-kort) via een apart te installeren companion-integratie. Praktijktests zijn nog nodig; de companion zit niet in de app-container.

### Lokaal ontwikkelen en testen

Voer de volgende opdrachten uit vanuit de map `hass_cleaner`:

```powershell
$env:HASS_CLEANER_CONFIG_ROOT = "$PWD\..\dev-fixtures\homeassistant"
$env:HASS_CLEANER_DATA_ROOT = "$PWD\..\data"
$env:HASS_CLEANER_HOST = "127.0.0.1"
$env:HASS_CLEANER_PORT = "8099"
python -m hass_cleaner
```

Open daarna `http://127.0.0.1:8099`.

```powershell
python -m unittest discover -s tests -v
node --check web/assets/app.js
```

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
