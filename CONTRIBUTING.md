# Bijdragen aan Hass-Cleaner

Bedankt dat je Hass-Cleaner wilt verbeteren. Veiligheid gaat altijd voor extra opruimwinst.

## Ontwikkelregels

- Bestands- en registerscans moeten read-only blijven.
- Een nieuwe opruimregel controleert type, producer, minimumleeftijd, beschermde scopes en herstelroute.
- `unavailable`, `unknown` of een integratiespecifiek offline-signaal is nooit zelfstandig verwijderbewijs.
- Voeg voor iedere gedragswijziging tests toe.
- Neem nooit tokens, geheime waarden, ruwe `.storage`-inhoud of privérapporten op in issues of commits.

## Lokale controle

```powershell
cd hass_cleaner
python -m unittest discover -s tests -v
node --check web/assets/app.js
```

Installeer optioneel `pre-commit` en voer `pre-commit run --all-files` uit.

## Pull requests

Beschrijf wat verandert, waarom het veilig is, wat er bij fouten kan gebeuren en hoe herstel werkt. Houd wijzigingen klein en vermijd ongerelateerde formattering.
