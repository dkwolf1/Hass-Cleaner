# Hass-Cleaner App Repository

Git-installatieklare Home Assistant App-repository voor een veilige opslag-audit.

## Huidige veiligheidsstatus

Versie 0.7.1 houdt bestands- en registeropschoning technisch **audit-only**:

- `/homeassistant` wordt door Supervisor read-only gemount;
- er bestaat geen verwijder- of verplaatsendpoint voor bestanden, entities of apparaten;
- de UI kan uitsluitend scannen, filteren, exporteren en een veilig opruimplan tonen;
- iedere scan schrijft JSON, CSV en Markdown naar `/data/reports`;
- entities, apparaten, gebieden, config-entries en actuele states worden read-only via de officiële Home Assistant WebSocket API vergeleken;
- entities zonder apparaat zijn uitsluitend informatief; gebroken registerverwijzingen zijn nooit automatisch selecteerbaar;
- `.storage`, kernconfiguratie en databases worden expliciet als beschermd gerapporteerd;
- apparaten en entities worden per integratie gebundeld en via `search/related` op afhankelijkheden gecontroleerd;
- alleen de aparte, expliciet bevestigde officiële `recorder.purge`-actie kan historische Recorder-gegevens verwijderen;
- een Recorder-purge vereist back-upbevestiging, het woord `PURGE` en wordt in een lokaal auditlog opgenomen.
- ieder bestand en iedere bundel bevat bewijsniveau, mogelijke gevolgen en herstelstappen;
- inhoudspreviews tonen alleen structuur en sleutelnamen; gevoelige waarden worden gemaskeerd of geheel weggelaten;
- geavanceerde beoordeling toont technische details zonder de bewijspoort te omzeilen;
- ieder impactplan wordt als JSON en Markdown opgeslagen met een expliciete voor/na-snapshot.
- de standaardweergave bundelt bestanden tot begrijpelijke opruimrecepten per type en producerende integratie;
- een bewijspoort vereist een herkend bestandstype, minimumleeftijd, afwezigheid van beschermde scope en een bekende herstelroute;
- generieke cachepaden van onder meer camera-, NVR- en printerintegraties worden alleen als onderzoekskandidaat getoond;
- HACS-code, custom integrations, dashboardbestanden en persoonlijke opnames worden niet als opruimwinst gepresenteerd.
- beschikbaarheidsproblemen worden per integratie gebundeld; tijdelijke uitval en bewust uitgeschakelde entiteiten blijven informatief;
- alleen langdurige of herhaald waargenomen onbeschikbaarheid wordt een geblokkeerd aandachtspunt, nooit automatisch een verwijderkandidaat.
- een aparte entiteitenwerkruimte onderscheidt `unavailable`, `unknown`, `problem`, niet-geladen en bewust uitgeschakelde entities;
- entiteiten zijn filterbaar op duur, integratie, apparaat en ruimte en groepeerbaar per apparaat, integratie of status;
- alleen langdurige statusproblemen, niet-geladen entities en kapotte verwijzingen kunnen aan een onderzoeksplan worden toegevoegd;
- integratiespecifieke signalen zoals `reachable=false` zijn uitsluitend aanwijzingen en nooit zelfstandig selecteerbaar;
- ieder entiteitenplan blijft geblokkeerd met `execution_allowed: false` en nul uitvoerbare acties.
- runtime-only states zonder entityregister-item zijn apart zichtbaar en nooit verwijderbaar;
- uitgeschakelde entities zijn informatief en tellen niet als statusprobleem;
- het Markdownrapport is compact; JSON en CSV bevatten de volledige inventaris.

## Repositorystructuur

```text
repository.yaml
hass_cleaner/
  config.yaml
  build.yaml
  Dockerfile
  DOCS.md
  CHANGELOG.md
  requirements.txt
  hass_cleaner/
  web/
  tests/
```

## Lokaal starten

Voer onderstaande opdrachten uit vanuit `hass_cleaner`:

```powershell
$env:HASS_CLEANER_CONFIG_ROOT = "$PWD\..\dev-fixtures\homeassistant"
$env:HASS_CLEANER_DATA_ROOT = "$PWD\..\data"
$env:HASS_CLEANER_HOST = "127.0.0.1"
$env:HASS_CLEANER_PORT = "8099"
python -m hass_cleaner
```

Open daarna `http://127.0.0.1:8099`.

## Tests

```powershell
cd hass_cleaner
python -m unittest discover -s tests -v
```

## Offline auditrapport

```powershell
cd hass_cleaner
python -m hass_cleaner.audit `
  --root "C:\pad\naar\config" `
  --output "C:\pad\naar\rapporten"
```

## Later via GitHub installeren

1. Push de inhoud van deze map naar https://github.com/dkwolf1/Hass-Cleaner.
2. Open Home Assistant: **Instellingen → Apps → App store → Repositories**.
3. Voeg `https://github.com/dkwolf1/Hass-Cleaner` toe.
4. Installeer **Hass-Cleaner**.
5. Start de app en open de Ingress-interface.
6. Voer alleen een scan uit en download eerst het Markdown- of JSON-rapport.

De audit-only release hoeft geen vooraf gebouwde containerimage te gebruiken: Home Assistant kan de app lokaal uit de repository bouwen. Publicatie van multi-arch images kan later worden toegevoegd.
