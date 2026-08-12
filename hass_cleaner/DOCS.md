# Hass-Cleaner

Versie 1.0.0 toont geregistreerde entities en runtime-only states apart. Status en meetduur zijn advies en filters, geen verwijdertoestemming. De gebruiker kan geregistreerde entities selecteren en na risico- en back-upkeuze via de officiële Home Assistant-API verwijderen. Runtime-only states hebben geen registeritem en blijven uitgesloten.

Deze versie inventariseert veilig bestanden en Home Assistant-registers en kan afzonderlijk de officiële Recorder-purgeactie uitvoeren.

## Veiligheidswaarborg

- Scannen en registeronderzoek zijn read-only. De beschrijfbare configuratiemount wordt uitsluitend gebruikt voor exact geselecteerde, opnieuw gevalideerde veilige bestanden.
- De volledige batch wordt vóór de eerste wijziging gevalideerd op pad, type, grootte, wijzigingstijd en actuele beleidsclassificatie.
- Quarantainekopieën en herstel worden met SHA-256 gecontroleerd; een bestaand doelbestand wordt nooit overschreven.
- Na de bewaartermijn wordt niets automatisch gewist: definitief verwijderen vereist een nieuwe checksumcontrole en de exacte bevestiging `VERWIJDER`.
- Permanent verwijderen van bestanden buiten verlopen quarantaine is technisch uitgesloten.
- Registeruitvoering gebruikt uitsluitend officiële Home Assistant WebSocket-opdrachten en vereist een exacte aantalsbevestiging.
- Scannen verandert geen bestanden of metadata.
- Niets wordt vooraf geselecteerd.
- Beschermde bestanden zijn niet selecteerbaar.
- Registergegevens worden alleen via de officiële read-only WebSocket-commando's opgevraagd.
- Alleen expliciet geselecteerde entities en apparaat/config-entryrelaties kunnen worden gewijzigd; gebieden en config-entries zelf blijven buiten scope.
- `recorder.purge`, bestandsquarantaine en expliciet gekozen registeropschoning hebben ieder hun eigen waarschuwing en bevestiging.
- Inhoudsadvies toont nooit ruwe geheime waarden en verandert geen bestanden.
- Geavanceerde beoordeling toont alleen technische analyse, geen uitvoering.

## Gebruik

1. Start de app.
2. Schakel **Tonen in zijbalk** in.
3. Open **Cleanup**.
4. Kies **Nieuwe scan**.
5. Controleer de bestandscategorieën veilig, beoordeling en beschermd.
6. Open **Entiteiten**. De veilige standaard toont alleen bewezen aandachtspunten; kies **Tijdelijke signalen gegroepeerd bekijken** om de nulmeting en gevolgde signalen per integratie te openen.
7. Filter zo nodig op `unavailable`, `unknown`, duur, integratie, apparaat of ruimte. Selecteer geregistreerde entities voor een opruimplan; controleer advies en relaties en maak bewust een back-upkeuze.
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

Review-items en persoonlijke inhoud zijn selecteerbaar voor een opruimplan en vereisen extra risicobevestiging voor quarantaine. Beschermde items blijven altijd geblokkeerd. Het plan kan als JSON of Markdown worden gedownload en bevat risico en herstelstappen.

## Registercontrole

De app vergelijkt read-only:

- entity-, device- en area-registers;
- configuratie-entries;
- de momenteel geladen entity-states.

Entities zonder apparaat, apparaten zonder entities, uitgeschakelde entities en statussignalen worden als feiten en advies getoond. De gebruiker bepaalt de functionele noodzaak. Iedere geregistreerde entity kan aan een opruimplan worden toegevoegd; runtime-only states niet. Verwijderen kan relaties breken of door een integratie ongedaan worden gemaakt en heeft geen individuele undo. Herstel gebeurt via een Home Assistant-back-up.

De lokale keuzes **Volgen**, **Verwacht** en **Uitstellen** verbergen alleen een melding in Hass-Cleaner. Ze schakelen geen entity uit en wijzigen geen Home Assistant-register. In **Historie** zie je wat sinds de voorgaande scan nieuw, gewijzigd, hersteld of verdwenen is.

Tijdelijke signalen worden standaard ingeklapt per integratie. Iedere groep toont afzonderlijk hoeveel entities `unavailable`, `unknown` of `problem` zijn, de langste gevolgde duur en het hoogste aantal metingen. Open een groep om de afzonderlijke apparaten en entities te beoordelen. Bij grote registerafwijkingen toont de app maximaal 100 apparaten in het dialoogvenster; JSON en CSV blijven volledig.

## Rapportbestanden

Iedere voltooide scan levert drie rapporten:

- Markdown voor menselijke beoordeling;
- CSV voor filteren en sorteren;
- JSON voor technische controle.

Rapporten leggen scanresultaten en keuzes vast. Onder **Instellingen** bepaal je hoeveel complete rapportsets Hass-Cleaner bewaart. Alleen bestanden met de eigen naamstructuur in `/data/reports` worden beheerd. Via **Historie → Schone start** kun je scan-, plan-, register- en Recorder-logboeken wissen; actieve quarantainebestanden blijven altijd behouden.

## Back-up

Een scan vereist geen back-up. Vóór bestandsquarantaine of Recorder-purge kan de app via de officiële Supervisor API een volledige back-up starten. Hass-Cleaner controleert voltooiing via de toegestane back-uplijst en kan recent bewijs maximaal 24 uur hergebruiken. Een geverifieerde back-up is sterk aanbevolen, maar de gebruiker kan ook een zelf gecontroleerde back-up bevestigen of bewust zonder back-up doorgaan; die keuze wordt geaudit. Recorder-purge vereist daarnaast exact `PURGE`. `repack` is standaard uitgeschakeld omdat dit een zware bewerking is en tijdelijk extra schijfruimte kan gebruiken.
