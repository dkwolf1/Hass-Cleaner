# Changelog

## 0.7.2

- Vervangt misleidende `0 dagen` door **Eerste meting**, **< 24 uur** of een onderbouwde meetduur uit Home Assistant en opeenvolgende scans.
- Scheidt tijdelijke signalen om te volgen van concrete, langdurige aandachtspunten; tijdelijke runtime-only states zijn nooit selecteerbaar.
- Slaat per entity lokale keuzes op: volgen, verwacht en 7/30/90 dagen uitstellen, zonder Home Assistant te wijzigen.
- Vergelijkt scans en toont nieuwe, gewijzigde, herstelde en verdwenen entitysignalen.
- Voegt scan-historie, compacte scan-samenvattingen en gepagineerde API-routes voor bestanden, entities en bundels toe.
- Voegt een instelbare rapportretentie van 1 tot 50 scans toe en verwijdert uitsluitend eigen oude rapportsets.
- Legt geaccepteerde Supervisor-back-upverzoeken en de Ingress-gebruiker bij Recorder-purge vast; voltooiing blijft een expliciete gebruikerscontrole.
- Beperkt de webapp tot Home Assistant Ingress, voegt CSRF-controle, snelheidsbegrenzing en een AppArmor-profiel toe.
- Markeert deze reeks als experimenteel en voegt Nederlands/Engels, icon/logo, licentie, bijdrage- en beveiligingsdocumentatie toe.
- Voegt CI, Home Assistant app-linting en officiële multi-architecture GHCR-builds voor `amd64` en `aarch64` toe.
- Rapportformaat verhoogd naar schema 9; bestands-, entity- en apparaatverwijdering blijft technisch afwezig.

## 0.7.1

- Scheidt echte statusproblemen van informatief uitgeschakelde entities.
- Neemt runtime-only Home Assistant-states zonder entityregister-item veilig mee in het entityonderzoek.
- Legt in de interface uit wat `0 dagen` en de grens voor langdurige problemen betekenen.
- Voegt filters en kengetallen toe voor runtime-only, uitgeschakelde en onderzoekbare entities.
- Maakt het Markdownrapport compact; JSON en CSV blijven de volledige technische exports.
- Verwijdering blijft geblokkeerd en runtime-only states zijn nooit selecteerbaar voor verwijdering.

## 0.7.0

- Aparte tab **Entiteiten** toegevoegd met zoeken en filters op status, minimumduur, integratie en ruimte.
- Entiteiten kunnen per apparaat, integratie of status worden gegroepeerd en los of als groep aan een onderzoeksplan worden toegevoegd.
- Officiële algemene Home Assistant-states `unavailable`, `unknown` en `problem` worden afzonderlijk en over meerdere scans gevolgd.
- Niet-geladen entities, kapotte registerverwijzingen en de drie oorzaken van `disabled_by` blijven duidelijk van elkaar gescheiden.
- Apparaatnaam en effectieve ruimte (entityruimte met fallback naar apparaatruimte) worden in de beoordeling opgenomen.
- Integratiespecifieke velden `reachable`, `connected` en `online` worden alleen als niet-gevoelige aanwijzing getoond.
- Per entity is de officiële `search/related`-controle vanuit het detailvenster beschikbaar.
- Alleen langdurige statusproblemen, niet-geladen entities en kapotte verwijzingen zijn selecteerbaar voor onderzoek; tijdelijke uitval en uitgeschakelde entities niet.
- JSON-, CSV- en Markdownrapporten bevatten de nieuwe entiteitenclassificatie en duur.
- Onderzoeksplannen bevatten entities, verplichte controles en altijd `execution_allowed: false`; registerverwijdering blijft afwezig.

## 0.6.1

- `Dry-run` in de interface vervangen door het duidelijkere `Veilig opruimplan`.
- Veilige Python-cache tot één hoofdrecept gebundeld met details per producerende integratie.
- Knop toegevoegd om alle volledig bewezen veilige recepten in één keer te selecteren.
- Het exacte Home Assistant-pad `.cache/brands` als herbouwbare pictogramcache herkend; onbekende cache blijft geblokkeerd.
- Generieke registry-afwijkingsdetectie toegevoegd voor grote orphan-groepen en gebroken verwijzingen.
- Bundelscherm toont standaard alleen concrete aandachtspunten; gezonde integraties blijven opvraagbaar.
- Detectieregels zijn integratie-onafhankelijk en bevatten geen HASS.Agent-specifieke uitzonderingen.
- Onbeschikbare, niet-geladen en uitgeschakelde entiteiten worden per integratie met hun oorzaak gebundeld.
- `last_changed` en niet-gevoelige waarnemingshistorie onderscheiden tijdelijke van langdurige onbeschikbaarheid.
- Langdurige onbeschikbaarheid blijft een geblokkeerd aandachtspunt en wordt nooit zelfstandig een verwijderadvies.

## 0.6.0

- Beginnersmodus met gebundelde opruimrecepten toegevoegd.
- Generieke producentherkenning toegevoegd voor cache van integraties, camera's, NVR's en andere toepassingen.
- Strenge bewijspoort toegevoegd: alleen bekende inactieve logs, oude herbouwbare Python-cache en editorrestanten kunnen in een dry-run.
- Minimumleeftijd wordt nu ook op Python-cache toegepast.
- Custom-integratiecode, HACS/frontendbestanden, dashboardbestanden, configuratie, databases en `.storage` zijn systeeminventaris en worden behouden.
- Opnames, snapshots en timelapses worden als persoonlijke inhoud behandeld, nooit als cache.
- Cache-achtige paden blijven geblokkeerd totdat verwijzingen en automatische herbouw bewezen zijn.
- De server weigert review- en protected-bestanden ook bij een rechtstreeks API-verzoek.

## 0.5.0

- Inhoudsbewuste impactanalyse aan ieder gevonden bestand en iedere integratiebundel toegevoegd.
- Bewijsniveaus toegevoegd: sterk bewijs, waarschijnlijk veilig, meer bewijs nodig, hoog risico en geblokkeerd.
- Veilige structuurpreviews voor JSON, YAML, code en tekst toegevoegd; gevoelige waarden worden nooit opgenomen.
- Gevolgadvies, aanbevolen eerste stap en concrete herstelroutes in UI en rapporten opgenomen.
- Geavanceerde beoordelingsmodus toegevoegd waarmee review-items aan een dry-runplan kunnen worden toegevoegd zonder ze uitvoerbaar te maken.
- Persistente JSON- en Markdown-impactplannen met voor/na-snapshot en hersteladvies toegevoegd.
- Bestands-, entity- en apparaatuitvoering blijft technisch vergrendeld.

## 0.4.0

- Apparaten en entities per configuratie-entry/integratie gebundeld.
- Bovenliggende apparaten, onderliggende apparaten en losse entities samen zichtbaar gemaakt.
- Officiële Home Assistant `search/related`-analyse toegevoegd voor automatiseringen, scripts, scènes en andere afhankelijkheden.
- Volledige bundels kunnen met één klik worden beoordeeld en aan een dry-runplan worden toegevoegd; registerverwijdering blijft vergrendeld.
- Afzonderlijke `recorder.purge`-actie toegevoegd met `keep_days`, `repack` en `apply_filter`.
- Recorder-purge vereist een bevestigde back-up en de exacte bevestigingstekst `PURGE`.
- De laatste 50 purgeaanvragen worden lokaal zonder gevoelige gegevens gelogd.

## 0.3.0

- Read-only registerscan via de officiële Home Assistant WebSocket API toegevoegd.
- Entities zonder apparaat, apparaten zonder entities en lege gebieden worden informatief gerapporteerd.
- Gebroken device-, area-, parent-device- en config-entryverwijzingen worden voor handmatige beoordeling gemarkeerd.
- Ingeschakelde entities zonder actuele state worden voor handmatige beoordeling gemarkeerd.
- Uitgeschakelde entities en `unavailable` states worden zonder cleanupadvies geïnventariseerd.
- Registerbevindingen toegevoegd aan JSON-, CSV- en Markdownrapporten en aan een eigen UI-tab.

## 0.2.1

- Ongeldige Python-basisimage vervangen door de officiële multi-architecture
  `ghcr.io/home-assistant/base-python:3.13-alpine3.24` image.

## 0.2.0

- Home Assistant-configuratiemount gewijzigd naar read-only.
- Audit-only status expliciet toegevoegd aan API en interface.
- Persistente JSON-, CSV- en Markdown-rapporten toegevoegd.
- Downloadacties voor rapporten toegevoegd.
- Offline auditcommando toegevoegd.
- Git-installatieklare app-repositorystructuur toegevoegd.

## 0.1.0

- Eerste lokale scanbackend en Ingress-interface.
- Veilige, review- en beschermde classificaties.
- Bewaarbeleid van 1 tot 10 dagen en back-updialoog voorbereid.
- Destructieve uitvoering hard uitgeschakeld.
