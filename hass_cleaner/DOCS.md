# Hass-Cleaner

Versie 0.7.1 toont geregistreerde entities en runtime-only states apart. Uitgeschakelde entities zijn informatief en tellen niet als statusprobleem. `0 dagen` betekent korter dan 24 uur of een eerste waarneming; langdurig betekent 30 dagen, of minimaal 3 scans verspreid over minimaal 7 dagen. Markdown is een compacte beoordeling, terwijl JSON en CSV de volledige inventaris bevatten. Alle bestands- en entityacties blijven geblokkeerd.

Deze versie inventariseert veilig bestanden en Home Assistant-registers en kan afzonderlijk de officiële Recorder-purgeactie uitvoeren.

## Veiligheidswaarborg

- Home Assistant-configuratie is read-only gemount.
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
6. Open **Entiteiten** om te filteren op status, duur, integratie, apparaat of ruimte.
7. Selecteer alleen langdurige aandachtspunten voor een geblokkeerd onderzoeksplan en controleer per entity de officiële relaties.
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

Entities zonder apparaat, apparaten zonder entities, lege gebieden en uitgeschakelde entities zijn informatief. Verwijzingen naar ontbrekende apparaten, gebieden of config-entries en ingeschakelde entities zonder actuele state vragen om handmatige beoordeling. `unavailable`, `unknown` en `problem` worden qua duur gevolgd, maar tijdelijke waarnemingen blijven niet selecteerbaar. Integratiespecifieke signalen als `reachable=false` zijn alleen extra aanwijzingen. Ook een geselecteerde entity komt uitsluitend in een niet-uitvoerbaar onderzoeksplan terecht.

## Rapportbestanden

Iedere voltooide scan levert drie rapporten:

- Markdown voor menselijke beoordeling;
- CSV voor filteren en sorteren;
- JSON voor technische controle.

Rapporten vermelden expliciet `audit_only: true` en `execution_locked: true`.

## Back-up

Een scan vereist geen back-up. Vóór een Recorder-purge kan de app via de officiële Supervisor API een volledige back-up starten. De purge wordt pas geaccepteerd nadat de gebruiker bevestigt dat een recente, voltooide en bruikbare back-up beschikbaar is en exact `PURGE` typt. `repack` is standaard uitgeschakeld omdat dit een zware bewerking is en tijdelijk extra schijfruimte kan gebruiken.
