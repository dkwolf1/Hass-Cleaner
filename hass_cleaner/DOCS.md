# Hass-Cleaner

Deze versie is uitsluitend bedoeld om veilig te inventariseren welke bestanden mogelijk voor cleanup in aanmerking komen.

## Veiligheidswaarborg

- Home Assistant-configuratie is read-only gemount.
- De app bevat geen verwijderendpoint.
- Scannen verandert geen bestanden of metadata.
- Niets wordt vooraf geselecteerd.
- Beschermde bestanden zijn niet selecteerbaar.

## Gebruik

1. Start de app.
2. Schakel **Tonen in zijbalk** in.
3. Open **Cleanup**.
4. Kies **Nieuwe scan**.
5. Controleer de categorieën veilig, beoordeling en beschermd.
6. Download bij Scanstatus het Markdown-rapport of JSON.
7. Deel het rapport voor controle voordat een latere cleanupversie wordt overwogen.

## Rapportbestanden

Iedere voltooide scan levert drie rapporten:

- Markdown voor menselijke beoordeling;
- CSV voor filteren en sorteren;
- JSON voor technische controle.

Rapporten vermelden expliciet `audit_only: true` en `execution_locked: true`.

## Back-up

De interface bevat alvast de toekomstige verplichte back-upkeuze. De optie om een volledige Home Assistant-back-up te starten gebruikt de officiële Supervisor API. Omdat deze release niets kan verwijderen, is een back-up niet nodig om een gewone scan uit te voeren.
