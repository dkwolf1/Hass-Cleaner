# Hass-Cleaner

Versie 0.9.1 toont geregistreerde entities en runtime-only states apart. Uitgeschakelde entities zijn informatief en tellen niet als statusprobleem. De app verzint geen historie: als Home Assistant `last_changed` levert, gebruikt Hass-Cleaner die duur; anders begint de teller met **Eerste meting**. Daarna toont de app gevolgde uren of dagen en het aantal metingen. Langdurig betekent 30 dagen, of minimaal 3 scans verspreid over minimaal 7 dagen. Tijdelijke geregistreerde entities kunnen voor beoordeling worden geselecteerd, maar entity- en registeruitvoering blijft geblokkeerd.

Deze versie inventariseert veilig bestanden en Home Assistant-registers en kan afzonderlijk de officiële Recorder-purgeactie uitvoeren.

## Veiligheidswaarborg

- Scannen en registeronderzoek zijn read-only. De beschrijfbare configuratiemount wordt uitsluitend gebruikt voor exact geselecteerde, opnieuw gevalideerde veilige bestanden.
- De volledige batch wordt vóór de eerste wijziging gevalideerd op pad, type, grootte, wijzigingstijd en actuele beleidsclassificatie.
- Quarantainekopieën en herstel worden met SHA-256 gecontroleerd; een bestaand doelbestand wordt nooit overschreven.
- Na de bewaartermijn wordt niets automatisch gewist: definitief verwijderen vereist een nieuwe checksumcontrole en de exacte bevestiging `VERWIJDER`.
- Permanent verwijderen van bestanden buiten verlopen quarantaine is in 0.9.1 geblokkeerd.
- De app bevat geen verwijderendpoint voor bestanden, entities of apparaten.
- Scannen verandert geen bestanden of metadata.
- Niets wordt vooraf geselecteerd.
- Beschermde bestanden zijn niet selecteerbaar.
- Registergegevens worden alleen via de officiële read-only WebSocket-commando's opgevraagd.
- Entities, apparaten, gebieden en config-entries kunnen niet vanuit Hass-Cleaner worden gewijzigd.
- Alleen `recorder.purge` is uitvoerbaar, na expliciete back-up- en tekstbevestiging.
- Inhoudsadvies toont nooit ruwe geheime waarden en verandert geen bestanden.
- Geavanceerde beoordeling toont alleen technische analyse, geen uitvoering.

## Gebruik

1. Start de app.
2. Schakel **Tonen in zijbalk** in.
3. Open **Cleanup**.
4. Kies **Nieuwe scan**.
5. Controleer de bestandscategorieën veilig, beoordeling en beschermd.
6. Open **Entiteiten**. De veilige standaard toont alleen bewezen aandachtspunten; kies **Tijdelijke signalen gegroepeerd bekijken** om de nulmeting en gevolgde signalen per integratie te openen.
7. Filter zo nodig op `unavailable`, `unknown`, duur, integratie, apparaat of ruimte. Markeer tijdelijke signalen eventueel als verwacht of stel ze 7, 30 of 90 dagen uit. Geregistreerde tijdelijke en langdurige signalen kunnen worden geselecteerd voor een geblokkeerd onderzoeksplan; controleer per entity de officiële relaties.
8. Open **Bundels** om apparaten, entities en integraties samen te beoordelen.
9. Open **Database** alleen wanneer je bewust Recorder-historie wilt opschonen.
10. Download bij Scanstatus het Markdown-rapport, CSV of JSON.
11. Deel het rapport voor controle voordat register- of bestandsopschoning wordt overwogen.

## Impact- en hersteladvies

Klik in **Scanresultaten** op een bestandsnaam om te zien:

- hoe sterk het bewijs voor opschoning is;
- welke veilige structuur uit het bestand is herkend;
- wat mogelijk kan stoppen of verloren gaan;
- hoe het onderdeel hersteld kan worden;
- welke eerste stap Hass-Cleaner adviseert.

JSON- en YAML-previews bevatten alleen sleutelnamen en tellingen. Wachtwoorden, tokens, API-sleutels en andere waarden worden niet in de scanresultaten of impactplannen opgenomen.

## Geavanceerde beoordeling

In **Instellingen** kan geavanceerde beoordeling worden ingeschakeld. Review-items worden dan selecteerbaar voor een impactplan. Beschermde items blijven geblokkeerd en ieder plan vermeldt `execution_locked: true` en `executable_actions: 0`. Het plan kan als JSON of Markdown worden gedownload en bevat de verwachte voor- en nasituatie plus herstelstappen.

## Registercontrole

De app vergelijkt read-only:

- entity-, device- en area-registers;
- configuratie-entries;
- de momenteel geladen entity-states.

Entities zonder apparaat, apparaten zonder entities, lege gebieden en uitgeschakelde entities zijn informatief. Verwijzingen naar ontbrekende apparaten, gebieden of config-entries en ingeschakelde entities zonder actuele state vragen om handmatige beoordeling. `unavailable`, `unknown` en `problem` worden qua duur gevolgd. Tijdelijke geregistreerde waarnemingen zijn selecteerbaar voor beoordeling, maar vormen geen verwijderbewijs. De duur komt eerst uit `last_changed` wanneer Home Assistant die waarde levert en wordt daarna door opeenvolgende Hass-Cleaner-scans onderbouwd. Integratiespecifieke signalen als `reachable=false` zijn alleen extra aanwijzingen. Ook een geselecteerde entity komt uitsluitend in een niet-uitvoerbaar onderzoeksplan terecht.

De lokale keuzes **Volgen**, **Verwacht** en **Uitstellen** verbergen alleen een melding in Hass-Cleaner. Ze schakelen geen entity uit en wijzigen geen Home Assistant-register. In **Historie** zie je wat sinds de voorgaande scan nieuw, gewijzigd, hersteld of verdwenen is.

Tijdelijke signalen worden standaard ingeklapt per integratie. Iedere groep toont afzonderlijk hoeveel entities `unavailable`, `unknown` of `problem` zijn, de langste gevolgde duur en het hoogste aantal metingen. Open een groep om de afzonderlijke apparaten en entities te beoordelen. Bij grote registerafwijkingen toont de app maximaal 100 apparaten in het dialoogvenster; JSON en CSV blijven volledig.

## Rapportbestanden

Iedere voltooide scan levert drie rapporten:

- Markdown voor menselijke beoordeling;
- CSV voor filteren en sorteren;
- JSON voor technische controle.

Rapporten vermelden expliciet `audit_only: true` en `execution_locked: true`. Onder **Instellingen** bepaal je hoeveel complete rapportsets Hass-Cleaner bewaart. Alleen bestanden met de eigen naamstructuur in `/data/reports` worden verwijderd.

## Back-up

Een scan vereist geen back-up. Vóór bestandsquarantaine of Recorder-purge kan de app via de officiële Supervisor API een volledige back-up starten. Hass-Cleaner controleert voltooiing via de toegestane back-uplijst en kan recent bewijs maximaal 24 uur hergebruiken. Een geverifieerde back-up is sterk aanbevolen, maar de gebruiker kan ook een zelf gecontroleerde back-up bevestigen of bewust zonder back-up doorgaan; die keuze wordt geaudit. Recorder-purge vereist daarnaast exact `PURGE`. `repack` is standaard uitgeschakeld omdat dit een zware bewerking is en tijdelijk extra schijfruimte kan gebruiken.
