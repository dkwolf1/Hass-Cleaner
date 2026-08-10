# Hass-Cleaner

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

## Gebruik

1. Start de app.
2. Schakel **Tonen in zijbalk** in.
3. Open **Cleanup**.
4. Kies **Nieuwe scan**.
5. Controleer de bestandscategorieën veilig, beoordeling en beschermd.
6. Open **Entities & apparaten** voor de registercontrole.
7. Gebruik **Bundel beoordelen** om apparaten, entities en officiële relaties samen te bekijken.
8. Open **Database** alleen wanneer je bewust Recorder-historie wilt opschonen.
9. Download bij Scanstatus het Markdown-rapport, CSV of JSON.
10. Deel het rapport voor controle voordat register- of bestandsopschoning wordt overwogen.

## Registercontrole

De app vergelijkt read-only:

- entity-, device- en area-registers;
- configuratie-entries;
- de momenteel geladen entity-states.

Entities zonder apparaat, apparaten zonder entities, lege gebieden en uitgeschakelde entities zijn informatief. Verwijzingen naar ontbrekende apparaten, gebieden of config-entries en ingeschakelde entities zonder actuele state vragen om handmatige beoordeling. Een `unavailable` state wordt alleen geteld: dit kan tijdelijk en volkomen legitiem zijn.

## Rapportbestanden

Iedere voltooide scan levert drie rapporten:

- Markdown voor menselijke beoordeling;
- CSV voor filteren en sorteren;
- JSON voor technische controle.

Rapporten vermelden expliciet `audit_only: true` en `execution_locked: true`.

## Back-up

Een scan vereist geen back-up. Vóór een Recorder-purge kan de app via de officiële Supervisor API een volledige back-up starten. De purge wordt pas geaccepteerd nadat de gebruiker bevestigt dat een recente, voltooide en bruikbare back-up beschikbaar is en exact `PURGE` typt. `repack` is standaard uitgeschakeld omdat dit een zware bewerking is en tijdelijk extra schijfruimte kan gebruiken.
