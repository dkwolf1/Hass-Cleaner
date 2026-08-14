# Hass-Cleaner

[Nederlands](#nederlands) · [English](#english)

Hass-Cleaner is a Home Assistant App for inspecting storage, stale entities and registry relationships before anything is cleaned up. Safety, evidence and recovery come before reclaimed space.

> **Release status:** version 1.0.0 is the first stable release and is available for controlled early testing. Hass-Cleaner provides facts, advice, backup options and recovery guidance; the user makes the final cleanup decision.

> [!WARNING]
> **Testversie — voorzichtig gebruiken / Test version — handle with care.** Hass-Cleaner kan bestanden, Home Assistant-registerobjecten en Recorder-gegevens wijzigen. Controleer iedere selectie en maak vooraf bij voorkeur een volledige Home Assistant-back-up. Test bij voorkeur eerst op een niet-kritische installatie. Gebruik is op eigen risico; quarantaine en herstelvoorzieningen verkleinen het risico, maar kunnen niet garanderen dat iedere integratie of gebruikersconfiguratie zonder gevolgen blijft werken.
>
> Hass-Cleaner can modify files, Home Assistant registry objects and Recorder data. Review every selection and preferably create a full Home Assistant backup first. Test on a non-critical installation where possible. Use is at your own risk; quarantine and recovery safeguards reduce risk, but cannot guarantee that every integration or user configuration remains unaffected.

## Nederlands

### Wat is Hass-Cleaner?

Hass-Cleaner helpt Home Assistant-gebruikers om vervuiling begrijpelijk en gecontroleerd te beoordelen. De app zoekt onder andere naar oude logs, opnieuw op te bouwen cachebestanden, langdurig onbeschikbare entities en afwijkende registerrelaties.

Een gevonden item is nooit automatisch verwijderbewijs. De app toont waarom iets is gevonden, wat het risico is, wat er kan gebeuren en hoe herstel werkt.

### Belangrijkste functies

- Veilige opslagscan met één duidelijk exportvenster: een leesbaar Markdownrapport, CSV voor Excel en JSON voor technische analyse.
- Begrijpelijke opruimcategorieën en de actie **Opschoning voorbereiden**.
- Entities filteren op status, duur, integratie, apparaat en ruimte.
- Apparaten en entities bundelen per integratie of apparaat.
- Verschillen tussen scans: nieuw, gewijzigd, hersteld en verdwenen.
- Officiële Home Assistant Recorder-purge met afzonderlijke bevestiging.
- Quarantaine voor veilige, persoonlijke en door de gebruiker beoordeelde bestanden; beschermde kernbestanden blijven uitgesloten.
- Gebruikersgestuurde verwijdering van geregistreerde entities en ondersteunde apparaatbundels via de officiële Home Assistant-API.
- Wisbare lokale scan- en afgeronde quarantainelogboeken voor een schone start.
- Hersteltest en terugplaatsen zonder bestaande bestanden te overschrijven.

### Veiligheidsmodel van 1.0.0

Een bestand kan alleen naar quarantaine als aan alle voorwaarden wordt voldaan:

1. Het bestand komt uit de laatste voltooide scan.
2. Bestandstype, pad, leeftijd, risicoklasse en beschermde scopes komen nog overeen met de scan.
3. Grootte, wijzigingstijd en SHA-256 komen overeen met de scan.
4. De gebruiker kiest bewust voor een door Supervisor geverifieerde back-up, een zelf gecontroleerde recente back-up of doorgaan zonder back-up.
5. Een afwijking van de aanbevolen geverifieerde back-up vereist een extra risicobevestiging.
6. De gebruiker bevestigt de actie met `QUARANTAINE`.

De volledige selectie wordt gecontroleerd voordat het eerste bestand wordt verplaatst. Quarantaine bewaart oorsprong, checksum, gebruiker, back-upbewijs en vervaldatum. Herstel vereist `HERSTEL` en overschrijft nooit een bestaand bestand.

Na de ingestelde bewaartermijn van 1–10 dagen wordt niets automatisch gewist. Definitief verwijderen is pas daarna beschikbaar, voert opnieuw een checksumcontrole uit en vereist `VERWIJDER`.

Persoonlijke of onzekere inhoud vereist een extra inhoudsbevestiging. Registeropschoning vereist adviesweergave, back-upkeuze, risicobevestiging en een exact aantal. Runtime-only entities en beschermde kernbestanden blijven technisch uitgesloten.

### Talen

- Interface en Home Assistant App-instellingen: Automatisch, Nederlands en English.
- Automatisch gebruikt de browser-/Home Assistant-weergavetaal en valt bij een niet-ondersteunde taal terug op Engels.
- De taalkeuze binnen Hass-Cleaner heeft voorrang op de Home Assistant App-configuratie.

### Installeren vanuit GitHub

1. Open Home Assistant en ga naar **Instellingen → Apps → App store → Repositories**.
2. Voeg `https://github.com/dkwolf1/Hass-Cleaner` toe.
3. Installeer **Hass-Cleaner**.
4. Start de app en open de webinterface.
5. Voer eerst alleen een scan uit en beoordeel het rapport.

GitHub Actions bouwt versie 1.0.0 voor `amd64` en `aarch64`. Na publicatie van de container kan Home Assistant de release via deze repository installeren of bijwerken.

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

- Safe storage scanning with one clear export dialog: a readable Markdown report, CSV for Excel and JSON for technical analysis.
- Beginner-friendly cleanup categories and a clear **Prepare cleanup** action.
- Entity filters for state, duration, integration, device and area.
- Device and entity grouping by integration or device.
- Scan differences for new, changed, recovered and disappeared signals.
- Official Home Assistant Recorder purge with separate confirmation.
- Quarantine for safe, personal and explicitly user-reviewed files; protected core files remain excluded.
- User-directed removal of registered entities and supported device bundles through Home Assistant's official API.
- Clearable local scan and completed-quarantine logs for a clean start.
- Restore testing and recovery without overwriting existing files.

### 1.0.0 safety model

A file can enter quarantine only when all conditions are satisfied:

1. It belongs to the latest completed scan.
2. Its type, path, age, risk class and protected scopes still match the scan immediately before execution.
3. Its size, modification time and SHA-256 still match the scan.
4. The user explicitly chooses a Supervisor-verified backup, a manually checked recent backup or proceeding without a backup.
5. Deviating from the recommended verified backup requires an additional risk acknowledgement.
6. The user confirms the operation with `QUARANTAINE`.

The entire selection is validated before the first file is moved. Quarantine records the original path, checksum, user, backup evidence and expiry time. Recovery requires `HERSTEL` and never overwrites an existing file.

Nothing is deleted automatically after the configured 1–10 day retention period. Permanent removal becomes available only after expiry, verifies the checksum again and requires `VERWIJDER`.

Personal or uncertain content requires an additional content acknowledgement. Registry cleanup requires displayed advice, a backup choice, risk acknowledgement and exact count confirmation. Runtime-only entities and protected core files remain technically excluded.

### Languages

- Interface and Home Assistant App settings: Automatic, Dutch and English.
- Automatic uses the browser/Home Assistant display language and falls back to English for unsupported languages.
- The language selected inside Hass-Cleaner takes precedence over the Home Assistant App configuration.

### Install from GitHub

1. In Home Assistant, open **Settings → Apps → App store → Repositories**.
2. Add `https://github.com/dkwolf1/Hass-Cleaner`.
3. Install **Hass-Cleaner**.
4. Start the App and open its web interface.
5. Run a scan first and review the report before preparing an action.

GitHub Actions builds version 1.0.0 for `amd64` and `aarch64`. After the container is published, Home Assistant can install or update the release through this repository.

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
