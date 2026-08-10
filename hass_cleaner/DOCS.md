# Hass-Cleaner

Deze versie is uitsluitend bedoeld om veilig bestanden en Home Assistant-registers te inventariseren.

## Veiligheidswaarborg

- Home Assistant-configuratie is read-only gemount.
- De app bevat geen verwijderendpoint.
- Scannen verandert geen bestanden of metadata.
- Niets wordt vooraf geselecteerd.
- Beschermde bestanden zijn niet selecteerbaar.
- Registergegevens worden alleen via de officiële read-only WebSocket-commando's opgevraagd.
- Entities, apparaten, gebieden en config-entries kunnen niet vanuit Hass-Cleaner worden gewijzigd.

## Gebruik

1. Start de app.
2. Schakel **Tonen in zijbalk** in.
3. Open **Cleanup**.
4. Kies **Nieuwe scan**.
5. Controleer de bestandscategorieën veilig, beoordeling en beschermd.
6. Open **Entities & apparaten** voor de registercontrole.
7. Download bij Scanstatus het Markdown-rapport, CSV of JSON.
8. Deel het rapport voor controle voordat een latere cleanupversie wordt overwogen.

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

De interface bevat alvast de toekomstige verplichte back-upkeuze. De optie om een volledige Home Assistant-back-up te starten gebruikt de officiële Supervisor API. Omdat deze release niets kan verwijderen, is een back-up niet nodig om een gewone scan uit te voeren.
