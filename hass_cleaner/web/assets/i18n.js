(() => {
  "use strict";

  const english = {
    "Verbinden...": "Connecting...", "Niet verbonden": "Not connected", "Home Assistant verbonden": "Connected to Home Assistant", "Lokale ontwikkelmodus": "Local development mode",
    "Nieuwe scan": "New scan", "Overzicht": "Overview", "Scanresultaten": "Scan results", "Entiteiten": "Entities", "Bundels": "Bundles", "Database": "Database", "Quarantaine": "Quarantine", "Historie": "History", "Instellingen": "Settings",
    "Veilige scheiding actief": "Safety boundaries active", "Scans wijzigen niets. Daarna kiest de gebruiker zelf: niet-beschermde bestanden kunnen naar herstelbare quarantaine en geselecteerde registerobjecten kunnen na waarschuwing worden verwijderd. Een back-up wordt sterk aanbevolen.": "Scans do not change anything. You decide what happens next: non-protected files can enter recoverable quarantine and selected registry objects can be removed after a warning. A backup is strongly recommended.",
    "OPSLAGAUDIT": "STORAGE AUDIT", "Maak ruimte vrij,": "Free up space,", "zonder verrassingen.": "without surprises.", "Bekijk eerst wat veilig weg kan, beoordeel twijfelgevallen en kies zelf hoe lang bestanden herstelbaar blijven.": "Review safe candidates and uncertain items first, then choose how long files remain recoverable.", "Start veilige scan": "Start safe scan", "Bewaarbeleid instellen": "Set retention policy", "Veiligheidsscore": "Safety score",
    "VEILIG": "SAFE", "BEOORDELING": "REVIEW", "BESCHERMD": "PROTECTED", "MOGELIJKE WINST": "POTENTIAL SAVINGS", "Nog niet gescand": "Not scanned yet", "Nooit automatisch wijzigen": "Never changed automatically", "Na controle van alle kandidaten": "After reviewing all candidates",
    "LAATSTE CONTROLE": "LATEST CHECK", "Scanstatus": "Scan status", "Exporteren": "Export", "Niet uitgevoerd": "Not run", "Nog geen opslagscan uitgevoerd": "No storage scan has been run", "De scan leest alleen metadata en wijzigt geen enkel bestand.": "The scan reads metadata only and does not change any files.", "Bestanden inventariseren": "Inventorying files", "Scan voorbereiden...": "Preparing scan...",
    "BEWAARBELEID": "RETENTION POLICY", "Na goedkeuring": "After approval", "Wijzigen": "Change", "Verplaatsen naar beveiligde quarantaine": "Move to protected quarantine", "Back-upkeuze verplicht": "Backup choice required", "Een back-up is sterk aanbevolen; de gebruiker kiest en bevestigt bewust": "A backup is strongly recommended; the user makes and confirms an explicit choice",
    "BEGINNERSMODUS": "BEGINNER MODE", "Opruimcategorieën": "Cleanup categories", "Alle categorieën": "All categories", "Veilig": "Safe", "Beoordeling": "Review", "Beschermd": "Protected", "Alles veilig selecteren": "Select all safe items", "Opschoning voorbereiden": "Prepare cleanup",
    "Gebruikerskeuze met vangrails": "User choice with safeguards", "Hass-Cleaner geeft advies en sluit beschermde kernbestanden uit. Andere veilige en persoonlijke kandidaten kun je zelf aan de opschoning toevoegen; quarantaine en een back-up beperken het herstelrisico.": "Hass-Cleaner provides guidance and excludes protected core files. You can add other safe and personal candidates to the cleanup yourself; quarantine and a backup reduce recovery risk.",
    "Voer eerst een scan uit.": "Run a scan first.", "Wacht op de nieuwe scan.": "Waiting for the new scan.", "Technische inventaris en afzonderlijke bestanden": "Technical inventory and individual files", "Bestand": "File", "Categorie": "Category", "Risico": "Risk", "Grootte": "Size",
    "ENTITEITENONDERZOEK": "ENTITY REVIEW", "Vind wat echt aandacht nodig heeft": "Find what truly needs attention", "Zichtbare selecteren": "Select visible", "Status is geen verwijderbewijs": "A state is not proof that removal is safe", "Hass-Cleaner geeft context en advies; jij bepaalt wat aan de opschoning wordt toegevoegd en accepteert het risico bij uitvoering.": "Hass-Cleaner provides context and guidance; you decide what to add to the cleanup and accept the risk when executing it.",
    "Zoek entity, apparaat, integratie of ruimte": "Search entity, device, integration or area", "Alleen actie nodig": "Needs attention only", "Alle tijdelijke en langdurige signalen": "All temporary and persistent signals", "Alleen tijdelijk volgen": "Temporarily monitored only", "Genegeerd of verwacht": "Ignored or expected", "Onbeschikbaar": "Unavailable", "Onbekende waarde": "Unknown value", "Probleemstatus": "Problem state", "Niet geladen": "Not loaded", "Uitgeschakeld": "Disabled", "Alleen runtime-only": "Runtime-only only", "Kapotte verwijzing": "Broken reference", "Alle entiteiten": "All entities", "Alle integraties": "All integrations", "Alle ruimtes": "All areas", "Minimaal": "Minimum", "dagen": "days", "Per integratie": "By integration", "Per apparaat": "By device", "Per status": "By state", "Niet groeperen": "Do not group",
    "De duur komt uit Home Assistant wanneer beschikbaar; anders begint Hass-Cleaner met een eigen eerste meting.": "Duration comes from Home Assistant when available; otherwise Hass-Cleaner starts its own first measurement.", "Scanvergelijking": "Scan comparison", "De eerste scan vormt de nulmeting.": "The first scan establishes the baseline.", "GEREGISTREERD": "REGISTERED", "RUNTIME-ONLY": "RUNTIME ONLY", "ACTIE NODIG": "NEEDS ATTENTION", "UITGESCHAKELD": "DISABLED", "TIJDELIJK VOLGEN": "MONITOR TEMPORARILY", "In het entityregister": "In the entity registry", "State zonder registeritem": "State without a registry entry", "Langdurig of concreet aangetoond": "Persistent or specifically identified", "Informatief, meestal normaal": "Informational, usually normal", "Zelf beoordelen": "Review yourself",
    "RELATIEANALYSE": "RELATIONSHIP ANALYSIS", "Apparaten en entities gebundeld": "Devices and entities grouped", "Zoek integratie, apparaat of entity": "Search integration, device or entity", "Alleen aandachtspunten": "Attention items only", "Alle bundels": "All bundles", "Met waarschuwingen": "With warnings", "Met apparaten": "With devices", "Met entities": "With entities", "Nog niet gescand": "Not scanned yet", "Eén bundel per integratie": "One bundle per integration", "Hass-Cleaner groepeert configuratie, apparaten en entities. Jij beoordeelt advies en risico en kiest wat aan de opschoning wordt toegevoegd.": "Hass-Cleaner groups configuration, devices and entities. You review the guidance and risk, then choose what to add to the cleanup.", "ENTITIES": "ENTITIES", "BUNDELS": "BUNDLES", "AANDACHTSPUNTEN": "ATTENTION ITEMS", "Integraties en losse platformen": "Integrations and standalone platforms", "Concrete registerafwijkingen": "Specific registry anomalies", "Alleen geteld, nooit opgeschoond": "Counted only, never cleaned automatically", "Alle afzonderlijke registerbevindingen": "All individual registry findings", "Onderdeel": "Item", "Status": "Status", "Reden": "Reason",
    "Database opschonen": "Clean database", "Controleren...": "Checking...", "Dit verwijdert historische gegevens permanent": "This permanently removes historical data", "De actie gebruikt rechtstreeks recorder.purge. Actuele entities en apparaten worden niet verwijderd.": "This action directly uses recorder.purge. Current entities and devices are not removed.", "BEWAARTERMIJN": "RETENTION", "Oude historie verwijderen": "Remove old history", "Dagen geschiedenis bewaren": "Days of history to retain", "Database herverpakken": "Repack database", "Kan schijfruimte vrijmaken, maar is zwaar en kan tijdelijk extra ruimte gebruiken.": "May reclaim disk space, but is resource intensive and can temporarily require extra space.", "Recorder-filter toepassen": "Apply Recorder filter", "Verwijdert ook gegevens die volgens de huidige include/exclude-filters niet meer opgenomen horen te worden.": "Also removes data that no longer matches the current include/exclude filters.", "Purge voorbereiden": "Prepare purge", "Laatste purgeacties": "Recent purge actions", "Nog geen purgeactie uitgevoerd.": "No purge has been run.",
    "HERSTELBARE OPSLAG": "RECOVERABLE STORAGE", "Afgerond logboek wissen": "Clear completed log", "Checksum bewaakt herstel": "Checksum-protected recovery", "Alleen opnieuw gevalideerde, geselecteerde bestanden komen hier. Herstel overschrijft nooit een bestaand bestand.": "Only revalidated, selected files appear here. Restore never overwrites an existing file.", "Nog geen bestanden in quarantaine.": "No files in quarantine.",
    "AUDIT-LOG": "AUDIT LOG", "Schone start": "Clean start", "Schone start wist lokale meetgeschiedenis": "A clean start clears local measurement history", "Scanrapporten, duurmetingen, lokale entitykeuzes, opgeslagen voorbereidingen en registerlogboeken worden gewist. Home Assistant zelf wordt niet gewijzigd.": "Scan reports, duration measurements, local entity choices, saved cleanup preparations and registry logs are cleared. Home Assistant itself is not changed.", "Nog geen voltooide scans opgeslagen.": "No completed scans saved.",
    "VEILIGHEID EN GEDRAG": "SAFETY AND BEHAVIOUR", "Instellingen opslaan": "Save settings", "TAAL": "LANGUAGE", "Interfacetaal": "Interface language", "Automatisch (browser/Home Assistant)": "Automatic (browser/Home Assistant)", "Nederlands": "Dutch", "Engels": "English", "Automatisch gebruikt de browsertaal en kiest Engels als de taal niet wordt ondersteund.": "Automatic uses the browser language and falls back to English when it is not supported.",
    "VERWIJDERBELEID": "REMOVAL POLICY", "Wat gebeurt er met bestanden?": "What happens to files?", "Altijd eerst in quarantaine": "Always quarantine first", "Bestanden blijven tijdelijk herstelbaar en kunnen na afloop handmatig permanent worden verwijderd.": "Files remain temporarily recoverable and can be permanently deleted manually afterwards.", "Bewaartermijn": "Retention period", "1 dag": "1 day", "10 dagen": "10 days",
    "SELECTIEREGELS": "SELECTION RULES", "Minimumleeftijd": "Minimum age", "Tijdelijke- en editorbestanden": "Temporary and editor files", "Oude logbestanden": "Old log files", "Aantal scanrapporten bewaren": "Scan reports to retain", "scans": "scans", "Een bestandsnaam alleen is nooit voldoende. Pad, type, leeftijd en beschermingsregels worden altijd gecombineerd.": "A filename alone is never sufficient. Path, type, age and protection rules are always combined.",
    "GEAVANCEERDE BEOORDELING": "ADVANCED REVIEW", "Ook buiten de veilige marges beoordelen": "Review beyond safe recommendations", "Eigen keuze": "Your choice", "Technische bestandsinventaris tonen": "Show technical file inventory", "Persoonlijke en onzekere inhoud is selecteerbaar met extra risicobevestiging; systeembestanden blijven beschermd.": "Personal and uncertain content can be selected with an additional risk acknowledgement; system files remain protected.", "De gebruiker beslist": "The user decides", "Hass-Cleaner geeft advies en beschermt systeembestanden. Alleen de gebruiker kan de functionele noodzaak beoordelen.": "Hass-Cleaner provides guidance and protects system files. Only the user can judge whether something is functionally required.",
    "Sluiten": "Close", "Annuleren": "Cancel", "Opschoning opslaan": "Save cleanup preparation", "IMPACTANALYSE": "IMPACT ANALYSIS", "Dit overzicht legt de voor- en nasituatie, risico's en herstelstappen vast. Omdat niets wordt gewijzigd, is voor deze stap geen back-up nodig.": "This overview records the before and after state, risks and recovery steps. No backup is needed for this preparation because it changes nothing.", "Uitvoering is apart beveiligd": "Execution has separate safeguards", "Vóór uitvoering wordt ieder bestand opnieuw gecontroleerd. Een voltooide back-up is sterk aanbevolen, maar geen technische verplichting.": "Every file is checked again before execution. A completed backup is strongly recommended, but is not technically required.", "Bestandsadvies": "File guidance", "INHOUD, IMPACT EN HERSTEL": "CONTENT, IMPACT AND RECOVERY", "Bundel": "Bundle", "BUNDELBEOORDELING": "BUNDLE REVIEW", "Bundel aan opschoning toevoegen": "Add bundle to cleanup", "ENTITEITDETAILS": "ENTITY DETAILS", "Blijven volgen": "Keep monitoring", "Verwacht gedrag": "Expected behaviour", "7 dagen negeren": "Ignore for 7 days", "30 dagen negeren": "Ignore for 30 days", "VOORBEREIDE OPSCHONING": "PREPARED CLEANUP", "Impact- en hersteloverzicht gereed": "Impact and recovery overview ready", "Veilige vervolgstap": "Safe next step", "De voorbereiding heeft nog niets gewijzigd.": "The preparation has not changed anything yet.", "Technische gegevens downloaden": "Download technical data", "Leesbaar overzicht downloaden": "Download readable overview", "Bestanden naar quarantaine": "Move files to quarantine", "Registeropschoning uitvoeren": "Run registry cleanup",
    "VEILIGE UITVOERING": "SAFE EXECUTION", "Back-up verifiëren en verplaatsen": "Verify backup and move", "De volledige selectie wordt vlak vóór uitvoering opnieuw gecontroleerd. Bij één afwijking stopt de hele batch.": "The complete selection is checked again immediately before execution. One mismatch stops the entire batch.", "Volledige back-up starten": "Start full backup", "Back-upstatus controleren": "Check backup status", "Nog geen back-up aangevraagd.": "No backup requested yet.", "Door Hass-Cleaner geverifieerde back-up": "Backup verified by Hass-Cleaner", "Recente back-up zelf gecontroleerd": "Recent backup checked manually", "Zonder back-up doorgaan": "Proceed without a backup", "Ik begrijp en accepteer het extra risico.": "I understand and accept the additional risk.", "Ik heb de persoonlijke of onzekere inhoud beoordeeld en accepteer mogelijk gegevensverlies.": "I reviewed the personal or uncertain content and accept possible data loss.", "Veilig verplaatsen": "Move safely",
    "REGISTEROPSCHONING OP EIGEN RISICO": "REGISTRY CLEANUP AT YOUR OWN RISK", "Entiteiten en apparaten verwijderen": "Remove entities and devices", "Geen quarantaine of individuele undo": "No quarantine or individual undo", "Integraties kunnen objecten opnieuw aanmaken. Dashboards en automatiseringen kunnen breken. Herstel gebeurt via een volledige Home Assistant-back-up.": "Integrations may recreate objects. Dashboards and automations may break. Recovery requires a full Home Assistant backup.", "Geverifieerde back-up": "Verified backup", "Zelf gecontroleerde back-up": "Manually checked backup", "Zonder back-up": "Without a backup", "Ik heb advies en relaties beoordeeld en accepteer verlies, heraanmaak en mogelijke kapotte verwijzingen.": "I reviewed the guidance and relationships and accept loss, recreation and possible broken references.", "Definitief uit register verwijderen": "Remove from registry",
    "DESTRUCTIEVE DATABASEACTIE": "DESTRUCTIVE DATABASE ACTION", "Recorder-database opschonen": "Clean Recorder database", "Eerst volledige back-up starten": "Start a full backup first", "Ik bevestig dat een recente, voltooide en bruikbare back-up beschikbaar is.": "I confirm that a recent, completed and usable backup is available.", "Recorder-purge uitvoeren": "Run Recorder purge",
    "EXPORTEREN": "EXPORT", "Exporteer scanresultaten": "Export scan results", "Kies het formaat dat past bij wat je wilt doen.": "Choose the format that matches what you want to do.", "Leesbaar rapport": "Readable report", "Markdown (.md) voor lezen, delen en ondersteuning.": "Markdown (.md) for reading, sharing and support.", "Spreadsheet": "Spreadsheet", "CSV (.csv) om grote resultaten in Excel te filteren en sorteren.": "CSV (.csv) for filtering and sorting large result sets in Excel.", "Technische gegevens": "Technical data", "JSON (.json) voor foutonderzoek, automatisering en volledige details.": "JSON (.json) for troubleshooting, automation and complete details.", "Downloaden": "Download",
    "Beschikbaar": "Available", "Alleen in Home Assistant": "Home Assistant only", "In wachtrij": "Queued", "Bezig": "Running", "Voltooid": "Completed", "Mislukt": "Failed", "Instellingen opgeslagen": "Settings saved",
    "Oude logbestanden": "Old log files", "Oude diagnosegegevens die niet meer actief worden geschreven.": "Old diagnostic data that is no longer actively written.", "Tijdelijke Python-cache": "Temporary Python cache", "Gegenereerde bytecode; Home Assistant maakt deze zo nodig opnieuw.": "Generated bytecode; Home Assistant recreates it when needed.", "Editor- en systeemrestanten": "Editor and system leftovers", "Bekende restbestanden zonder Home Assistant-functie.": "Known leftover files with no Home Assistant function.", "Home Assistant pictogramcache": "Home Assistant icon cache", "Gegenereerde integratiepictogrammen; Home Assistant kan deze opnieuw ophalen.": "Generated integration icons; Home Assistant can download them again.",
    "Mogelijke integratiecache": "Possible integration cache", "De mapnaam wijst op cache, maar actief gebruik en automatische herbouw zijn nog niet bewezen.": "The directory name suggests a cache, but active use and automatic rebuilding are not known.", "Persoonlijke media": "Personal media", "Opnames, timelapses of snapshots zijn gebruikersdata en worden nooit als cache aangenomen.": "Recordings, time-lapses and snapshots are user data and are never assumed to be cache.", "Nader beoordelen": "Review further", "Niet genoeg bewijs voor een veilig opruimadvies.": "Not enough information for a safe cleanup recommendation.",
    "Bestandstype en producer zijn herkend.": "The file type and producer are recognised.", "De ingestelde minimumleeftijd is gehaald.": "The configured minimum age has been reached.", "Geen actieve verwijzing verwacht.": "No active reference is expected.", "Gebruik door dashboards, automatiseringen of de integratie is niet uitgesloten.": "Use by dashboards, automations or the integration has not been ruled out.", "Quarantaine of automatische herbouw is mogelijk.": "Quarantine or automatic rebuilding is available.", "Automatische herbouw of herstel is niet bewezen.": "Automatic rebuilding or recovery is not known.", "Kan aan de opschoning worden toegevoegd.": "Can be added to the cleanup.", "Beoordeel risico en herstel; alleen de gebruiker kan bepalen of deze inhoud gemist kan worden.": "Review the risk and recovery options; only the user can decide whether this content is still needed.",
    "Python-cache": "Python cache", "Python-cache zonder bron": "Python cache without source", "Editorrestant": "Editor leftover", "Tijdelijk / back-up": "Temporary / backup", "Oud logbestand": "Old log file", "Custom component": "Custom component", "HACS/frontendpakket": "HACS/frontend package", "Dashboard-/webbestand": "Dashboard/web file", "Mogelijke integratiecache": "Possible integration cache", "Kernconfiguratie": "Core configuration", "Symbolische link": "Symbolic link",
    "Entity zonder apparaat": "Entity without device", "Ontbrekend apparaat": "Missing device", "Ontbrekend gebied": "Missing area", "Ontbrekende config-entry": "Missing config entry", "Ontbrekend bovenliggend apparaat": "Missing parent device", "Entity niet geladen": "Entity not loaded", "Uitgeschakelde entity": "Disabled entity", "Apparaat zonder entities": "Device without entities", "Leeg gebied": "Empty area",
    "Aan opschoning toevoegen": "Add to cleanup", "Uit opschoning verwijderen": "Remove from cleanup", "Geen opruimcategorieën gevonden. Je systeeminventaris blijft behouden.": "No cleanup categories found. Your system inventory remains protected.", "Aanbevolen": "Recommended", "Eigen beoordeling": "Your review", "VEILIG RECEPT": "RECOMMENDED CATEGORY", "EERST ONDERZOEKEN": "REVIEW FIRST", "Veiligheidscontrole": "Safety checks", "Producenten, voorbeelden en advies": "Producers, examples and guidance",
    "Opschoning voorbereid": "Cleanup prepared", "Opschoning voorbereiden...": "Preparing cleanup...", "Opschoning opslaan": "Save cleanup preparation", "Opschoning voorbereid. De gebruiker kiest na advies, back-upafweging en bevestiging welke acties worden uitgevoerd.": "Cleanup prepared. After reviewing guidance, backup options and confirmation, the user chooses which actions to execute.",
    "Geen integratiespecifieke signalen": "No integration-specific signals", "Officiële relaties": "Official relationships", "Geen relaties gevonden. Dat is nog geen verwijderbewijs.": "No relationships found. That does not prove removal is safe.", "Algemene bundelanalyse tonen": "Show general bundle analysis", "Apparaten": "Devices", "Herstel": "Recovery", "Mogelijke gevolgen": "Possible consequences", "Aanbevolen eerste stap": "Recommended first step", "Veilige inhoudspreview": "Safe content preview", "Waarden die gevoelig kunnen zijn worden niet opgenomen.": "Potentially sensitive values are not included.",
    "Systeeminventaris · behouden": "System inventory · retained", "Veilige scan voltooid": "Safe scan completed", "HOME ASSISTANT-BACK-UP": "HOME ASSISTANT BACKUP", "Verplichte vraag vóór cleanup": "Backup choice before cleanup", "Altijd actief": "Always active", "Voor elke bestands- of database-uitvoering geldt:": "For every file or database action:", "1. Volledige back-up starten": "1. Start a full backup", "De app bewaart het unieke Supervisor-taaknummer bij de actie.": "The app records the unique Supervisor job number with the action.", "2. Voltooiing verifiëren": "2. Verify completion", "Hass-Cleaner zoekt de aangemaakte back-up in de officiële Supervisor-back-uplijst.": "Hass-Cleaner looks up the created backup in the official Supervisor backup list.", "3. Bewuste keuze": "3. Make an explicit choice", "Handmatig bevestigen of zonder back-up doorgaan kan, maar wordt nadrukkelijk gewaarschuwd en geaudit.": "You may confirm a backup manually or proceed without one, but this is clearly warned about and audited.", "Hoofdnavigatie": "Main navigation", "Scanoverzicht": "Scan overview", "Entiteitenoverzicht": "Entity overview", "Entiteitenfilters": "Entity filters", "Registeroverzicht": "Registry overview",
    "7 gerapporteerd · 2 volgens beleid genegeerd. Details worden pas geopend wanneer nodig.": "7 reported · 2 ignored by policy. Details are loaded only when needed.", "unavailable, unknown en problem zijn algemene Home Assistant-statussen. Hass-Cleaner geeft context en advies; jij bepaalt wat aan de opschoning wordt toegevoegd en accepteert het risico bij uitvoering.": "unavailable, unknown and problem are general Home Assistant states. Hass-Cleaner provides context and guidance; you decide what to add to the cleanup and accept the execution risk.", "De duur gebruikt Home Assistant last_changed wanneer beschikbaar; anders start Hass-Cleaner een eigen meting. Actie nodig volgt na 30 dagen, of 3 scans verspreid over minimaal 7 dagen.": "Duration uses Home Assistant last_changed when available; otherwise Hass-Cleaner starts its own measurement. Attention is raised after 30 days, or after 3 scans spanning at least 7 days.", "Geen entiteiten binnen deze filters.": "No entities match these filters.", "Niet beschikbaar": "Unavailable", "Registerscan is alleen beschikbaar binnen Home Assistant": "Registry scanning is available only inside Home Assistant", "Geen bundelgegevens beschikbaar.": "No bundle data available.", "De actie gebruikt rechtstreeks recorder.purge. Actuele entities en apparaten worden niet verwijderd.": "This action directly uses recorder.purge. Current entities and devices are not removed.", "Alleen opnieuw gevalideerde, geselecteerde bestanden komen hier. Herstel overschrijft nooit een bestaand bestand.": "Only revalidated, selected files appear here. Restore never overwrites an existing file.", "Scanrapporten, duurmetingen, lokale entitykeuzes, opgeslagen voorbereidingen en registerlogboeken worden gewist. Home Assistant zelf wordt niet gewijzigd.": "Scan reports, duration measurements, local entity choices, saved cleanup preparations and registry logs are cleared. Home Assistant itself is not changed."
  };

  Object.assign(english, {
    "Risico-indicatie": "Risk indication",
    "Sterk bewijs": "Strong evidence",
    "Waarschijnlijk veilig": "Likely safe",
    "Hoog risico": "High risk",
    "Meer bewijs nodig": "Review required",
    "Behouden": "Retain",
    "Geblokkeerd": "Blocked",
    "Wat is dit?": "What is this?",
    "Wat kan er gebeuren?": "What could happen?",
    "Hoe herstel je dit?": "How do you recover?",
    "Geen gevolgadvies beschikbaar.": "No consequence guidance is available.",
    "Hersteladvies ontbreekt; niet uitvoeren.": "Recovery guidance is missing; do not execute.",
    "Geen beschrijving beschikbaar.": "No description is available.",
    "Niet wijzigen zonder aanvullende controle.": "Do not change without further review.",
    "Samenhangende Home Assistant-objecten van dezelfde integratie of hetzelfde platform.": "Related Home Assistant objects belonging to the same integration or platform.",
    "Entities kunnen uit dashboards, automatiseringen en scripts verdwijnen.": "Entities may disappear from dashboards, automations and scripts.",
    "Een apparaat kan opnieuw door de integratie worden aangemaakt.": "The integration may recreate a device.",
    "Het verwijderen van een config-entry kan de volledige integratie uitschakelen.": "Removing a config entry can disable the entire integration.",
    "Herstel de Home Assistant-back-up als registrygegevens verloren zijn.": "Restore the Home Assistant backup if registry data is lost.",
    "Voeg de eigenaar-integratie opnieuw toe en configureer het apparaat opnieuw.": "Add the owning integration again and reconfigure the device.",
    "Herstel daarna afhankelijke automatiseringen en dashboards uit het planrapport.": "Then restore dependent automations and dashboards using the preparation report.",
    "Beoordeel eerst alle officiële search/related-verwijzingen; schakel losse entities zo mogelijk tijdelijk uit.": "Review official search/related references first; temporarily disable individual entities where possible.",
    "Gegenereerde Python-bytecode met aantoonbare broncode.": "Generated Python bytecode with matching source code.",
    "De cache wordt bij gebruik opnieuw opgebouwd; de eerste start kan iets langer duren.": "The cache is rebuilt when used; the first startup may take longer.",
    "Herstart de integratie of Home Assistant zodat Python de cache opnieuw maakt.": "Restart the integration or Home Assistant so Python recreates the cache.",
    "Plaats eerst in quarantaine; permanent verwijderen is doorgaans herstelbaar.": "Quarantine first; generated cache can usually be rebuilt after permanent removal.",
    "Gegenereerde Home Assistant-pictogramcache op het exact bekende cachepad.": "Generated Home Assistant icons at the known cache path.",
    "Pictogrammen kunnen kort ontbreken terwijl Home Assistant ze opnieuw ophaalt.": "Icons may briefly be missing while Home Assistant downloads them again.",
    "Herlaad Home Assistant; de pictogramcache wordt opnieuw opgebouwd.": "Reload Home Assistant to rebuild the icon cache.",
    "Kies Opschoning voorbereiden en gebruik daarna quarantaine.": "Choose Prepare cleanup, then use quarantine.",
    "Bekend editor- of besturingssysteemrestant.": "Known editor or operating-system leftover.",
    "Een editor of besturingssysteem kan het bestand opnieuw aanmaken.": "An editor or operating system may recreate the file.",
    "Geen herstel nodig; plaats het bestand desgewenst terug uit quarantaine.": "Recovery is not required; restore from quarantine if needed.",
    "Quarantaine is de veiligste eerste stap.": "Quarantine is the safest first step.",
    "Niet-actief oud Home Assistant-logbestand.": "Inactive old Home Assistant log file.",
    "Oude diagnose-informatie gaat verloren.": "Old diagnostic information will be lost.",
    "Zet het bestand vanuit quarantaine terug als oude logregels nodig zijn.": "Restore from quarantine if the old log entries are needed.",
    "Controleer of er geen lopend onderzoek is en gebruik daarna quarantaine.": "Check that no investigation needs the log, then use quarantine.",
    "Bestandsnaam wijst op een tijdelijke kopie of handmatige back-up.": "The filename suggests a temporary copy or manual backup.",
    "Dit kan de enige werkende kopie van configuratie of code zijn.": "This may be the only working copy of configuration or code.",
    "Zet het bestand terug uit quarantaine en vergelijk het met de actieve versie.": "Restore from quarantine and compare it with the active version.",
    "Vergelijk inhoud en wijzigingsdatum met het actieve bestand.": "Compare its contents and modification date with the active file.",
    "Bytecode zonder aantoonbaar bijbehorend bronbestand.": "Bytecode without a matching source file.",
    "Een custom integratie kan hierdoor niet meer laden.": "This can prevent a custom integration from loading.",
    "Zet de bytecode terug of installeer de bijbehorende integratie opnieuw.": "Restore the bytecode or reinstall its integration.",
    "Niet verwijderen totdat de eigenaar van de bytecode bekend is.": "Identify the owner of the bytecode before removing it.",
    "Padnaam wijst op cache van een integratie of toepassing.": "The path suggests an integration or application cache.",
    "Actieve previews, afdrukken, camerabeelden of indexen kunnen verdwijnen.": "Active previews, prints, camera images or indexes may disappear.",
    "Laat de eigenaar-integratie de cache opnieuw opbouwen of herstel een back-up.": "Let the owning integration rebuild the cache or restore a backup.",
    "Controleer producent, verwijzingen en herbouwgedrag; nog niet verwijderen.": "Check ownership, references and rebuilding behaviour before removing it.",
    "Opname, snapshot of timelapse is gebruikersdata.": "Recordings, snapshots and time-lapses are user data.",
    "De opname of afbeelding kan permanent verloren gaan.": "The recording or image may be permanently lost.",
    "Herstel uit een volledige back-up of externe mediakopie.": "Restore from a full backup or an external media copy.",
    "Alleen bewust beoordelen; nooit als cache behandelen.": "Review deliberately; never treat this as cache.",
    "Bestands- en registeracties beschikbaar": "File and registry actions available",
    "Bestandsquarantaine beschikbaar": "File quarantine available",
    "Registeropschoning beschikbaar": "Registry cleanup available",
    "Een back-up is sterk aanbevolen. Ieder bestand wordt vlak vóór verplaatsing opnieuw gecontroleerd.": "A backup is strongly recommended. Every file is rechecked immediately before moving.",
    "Entities en apparaten zijn registerobjecten. De gebruiker kan ze na advies, back-upkeuze en zware bevestiging verwijderen.": "Entities and devices are registry objects. Removal requires reviewing guidance, choosing a backup option and explicit confirmation.",
    "Filter op risico": "Filter by risk",
    "Zoek entiteiten": "Search entities",
    "Filter op status": "Filter by state",
    "Filter op integratie": "Filter by integration",
    "Filter op ruimte": "Filter by area",
    "Groepeer entiteiten": "Group entities",
    "Zoek bundels": "Search bundles",
    "Filter bundels": "Filter bundles",
    "Scan kon niet worden voltooid": "The scan could not be completed",
    "Onbekende scanfout": "Unknown scan error",
    "Deze scan is de nulmeting. Vanaf de volgende scan worden nieuw, hersteld en gewijzigd apart getoond.": "This scan is the baseline. New, recovered and changed entities will be shown separately from the next scan onward.",
    "Geen entiteiten binnen het huidige aandachtsfilter": "No entities match the current attention filter",
    "Tijdelijke signalen gegroepeerd bekijken": "View temporary signals grouped",
    "jij beslist na advies en back-upkeuze": "you decide after reviewing guidance and the backup choice",
    "Beoordeling": "Review",
    "Nog nodig:": "Still needed:",
    "Lokale keuze:": "Local choice:",
    "Herkomst": "Source",
    "Waarneming": "Observation",
    "Relaties ophalen...": "Loading relationships...",
    "Direct aangetoond": "Immediately confirmed",
    "Niet van toepassing": "Not applicable",
    "Eerste meting": "First observation",
    "nulmeting": "baseline",
    "nieuw": "new",
    "gewijzigd": "changed",
    "hersteld": "recovered",
    "ongewijzigd": "unchanged",
    "geen vergelijking": "no comparison",
    "Tijdelijk onbeschikbaar": "Temporarily unavailable",
    "Langdurig onbeschikbaar": "Persistently unavailable",
    "Tijdelijk onbekend": "Temporarily unknown",
    "Langdurig onbekend": "Persistently unknown",
    "Tijdelijke probleemstatus": "Temporary problem state",
    "Langdurige probleemstatus": "Persistent problem state",
    "Uitgeschakeld door gebruiker": "Disabled by user",
    "Standaard uitgeschakeld door integratie": "Disabled by integration by default",
    "Uitgeschakeld via config-entry": "Disabled through config entry",
    "Lokale entitykeuze opgeslagen; Home Assistant is niet gewijzigd": "Local entity choice saved; Home Assistant was not changed",
    "Recente back-up is voltooid en geverifieerd; je hoeft geen nieuwe te maken.": "A recent backup is complete and verified; you do not need to create another one.",
    "Er is een recente back-upaanvraag. Controleer de status; opnieuw aanmaken is niet nodig.": "A recent backup request exists. Check its status; you do not need to start another one.",
    "Nog geen recente back-upaanvraag gevonden. Een back-up is sterk aanbevolen.": "No recent backup request was found. A backup is strongly recommended.",
    "Back-up gestart; controleer de status zodra Home Assistant klaar is": "Backup started; check its status when Home Assistant is ready",
    "Hersteltest geslaagd: bestand is leesbaar en checksum klopt": "Restore test passed: the file is readable and its checksum matches",
    "Bestand veilig teruggeplaatst": "File restored safely",
    "Verlopen quarantainebestand definitief verwijderd": "Expired quarantined file permanently deleted",
    "Maak eerst een impactplan": "Prepare a cleanup first",
    "Kies 1 tot en met 365 dagen": "Choose between 1 and 365 days",
    "Recorder-purge is door Home Assistant geaccepteerd": "Recorder purge was accepted by Home Assistant",
    "Lokale scan-, meet-, plan-, register- en Recorder-historie gewist": "Local scan, measurement, preparation, registry and Recorder history cleared"
  });

  const patterns = [
    [/^(\d+) entiteiten · (\d+) actie nodig · (\d+) tijdelijk · maximaal (.+) \/ (\d+) meting\(en\)$/, (match, total, attention, temporary, duration, observations) => `${total} entities · ${attention} need attention · ${temporary} temporary · up to ${translated(duration)} / ${observations} observations`],
    [/^(\d+) meting\(en\) · (.+)$/, (match, count, status) => `${count} observations · ${translated(status)}`],
    [/^Back-up voltooid en geverifieerd(.*)$/, "Backup completed and verified$1"],
    [/^Back-upstatus controleren \((\d+)%\)$/, "Check backup status ($1%)"],
    [/^Back-upstatus: (.+)$/, "Backup status: $1"],
    [/^(\d+) dagen herstelbaar$/, "$1 days recoverable"],
    [/^(\d+) bestanden bekeken$/, "$1 files checked"],
    [/^(\d+) bestanden gecontroleerd$/, "$1 files checked"],
    [/^(\d+) gerapporteerd · (\d+) volgens beleid genegeerd\. De scan heeft niets gewijzigd\.$/, "$1 reported · $2 ignored by policy. The scan did not change anything."],
    [/^(\d+) gerapporteerd · (\d+) volgens beleid genegeerd\. Details worden pas geopend wanneer nodig\.$/, "$1 reported · $2 ignored by policy. Details are loaded only when needed."],
    [/^(\d+) veilige categorieën$/, "$1 safe categories"],
    [/^(\d+) zelf beoordelen$/, "$1 to review"],
    [/^Opschoning voorbereiden \((\d+)\)$/, "Prepare cleanup ($1)"],
    [/^Mogelijke cache van (.+)$/, "Possible cache from $1"],
    [/^Persoonlijke media van (.+)$/, "Personal media from $1"],
    [/^Nader beoordelen: (.+)$/, "Review further: $1"],
    [/^(\d+) bestanden geselecteerd · (\d+) zelf te beoordelen · de voorbereiding wijzigt nog niets$/, "$1 files selected · $2 require your review · preparation does not change anything"],
    [/^(\d+) bestanden · (.+)$/, (match, count, rest) => `${count} ${count === "1" ? "file" : "files"} · ${rest}`],
    [/^producer: (.+)$/, "producer: $1"],
    [/^(\d+) apparaten · (\d+) entities$/, "$1 devices · $2 entities"],
    [/^Nog (\d+) apparaten$/, "$1 more devices"],
    [/^(\d+) resultaten · (\d+) geselecteerd$/, "$1 results · $2 selected"],
    [/^(\d+) geregistreerde entities, (\d+) runtime-only states en (\d+) apparaten read-only gecontroleerd\. (\d+) langdurig onbeschikbaar; (\d+) voorlopig alleen informatief\.$/, "$1 registered entities, $2 runtime-only states and $3 devices checked read-only. $4 persistently unavailable; $5 currently informational only."],
    [/^(\d+) nieuw · (\d+) gewijzigd · (\d+) hersteld · (\d+) verdwenen$/, "$1 new · $2 changed · $3 recovered · $4 removed"],
    [/^(\d+) resultaten · (\d+) geselecteerd · jij beslist na advies en back-upkeuze$/, "$1 results · $2 selected · you decide after reviewing guidance and the backup choice"],
    [/^(\d+) tijdelijke signalen worden gevolgd\. Open die groep om zelf entities te selecteren en de risico's te beoordelen\.$/, "$1 temporary signals are being monitored. Open that group to select entities and assess the risks yourself."],
    [/^(\d+) uur gevolgd$/, "$1 hours monitored"],
    [/^< 1 uur gevolgd$/, "< 1 hour monitored"],
    [/^(\d+) dagen$/, "$1 days"],
    [/^(\d+) apparaten en (\d+) entities\. 1 registerafwijking voor eigen beoordeling\.$/, "$1 devices and $2 entities. 1 registry anomaly for your review."],
    [/^(\d+) apparaten en (\d+) entities\. (\d+) waarschuwingen\.$/, "$1 devices and $2 entities. $3 warnings."],
    [/^(\d+) bestanden, (\d+) bundels en (\d+) entiteiten vastgelegd\. Uitvoerbare acties: (\d+)\.$/, "$1 files, $2 bundles and $3 entities recorded. Executable actions: $4."],
    [/^(\d+) entiteiten en (\d+) apparaten worden definitief uit hun Home Assistant-registerrelatie verwijderd\.$/, "$1 entities and $2 devices will be permanently removed from their Home Assistant registry relationships."],
    [/^Alle Recorder-historie ouder dan (\d+) dagen wordt permanent verwijderd; (.+)\.$/, "All Recorder history older than $1 days will be permanently deleted; $2."],
    [/^Scanroot bestaat niet of is geen directory: (.+)$/, "Scan root does not exist or is not a directory: $1"],
  ];
  const originals = new WeakMap();
  const rendered = new WeakMap();
  const observationOptions = { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ["placeholder", "aria-label", "title"] };
  let preference = "auto";
  let locale = "en";
  let observer;

  function resolve(value) {
    if (value === "nl" || value === "en") return value;
    const languages = navigator.languages?.length ? navigator.languages : [navigator.language || "en"];
    for (const language of languages) {
      const base = String(language).toLowerCase().split("-")[0];
      if (base === "nl" || base === "en") return base;
    }
    return "en";
  }

  function translated(value) {
    const trimmed = value.trim();
    if (!trimmed) return value;
    let result = english[trimmed];
    if (!result) {
      const match = patterns.find(([pattern]) => pattern.test(trimmed));
      if (match) result = trimmed.replace(match[0], match[1]);
    }
    if (!result) return value;
    return value.replace(trimmed, result);
  }

  function localizeNode(node) {
    if (node.nodeType === Node.TEXT_NODE) {
      if (!originals.has(node) || node.nodeValue !== rendered.get(node)) originals.set(node, node.nodeValue);
      const source = originals.get(node);
      const wanted = locale === "en" ? translated(source) : source;
      if (node.nodeValue !== wanted) node.nodeValue = wanted;
      rendered.set(node, wanted);
      return;
    }
    if (node.nodeType !== Node.ELEMENT_NODE) return;
    if (["SCRIPT", "STYLE", "CODE", "PRE"].includes(node.tagName)) return;
    for (const attribute of ["placeholder", "aria-label", "title"]) {
      if (!node.hasAttribute(attribute)) continue;
      if (!originals.has(node) || typeof originals.get(node) !== "object") originals.set(node, {});
      if (!rendered.has(node)) rendered.set(node, {});
      const record = originals.get(node);
      const last = rendered.get(node);
      if (!(attribute in record) || node.getAttribute(attribute) !== last[attribute]) record[attribute] = node.getAttribute(attribute);
      const wanted = locale === "en" ? translated(record[attribute]) : record[attribute];
      if (node.getAttribute(attribute) !== wanted) node.setAttribute(attribute, wanted);
      last[attribute] = wanted;
    }
    node.childNodes.forEach(localizeNode);
  }

  function apply(root = document.documentElement) {
    observer?.disconnect();
    document.documentElement.lang = locale;
    localizeNode(root);
    observer?.observe(document.body, observationOptions);
  }

  function setPreference(value) {
    preference = ["auto", "nl", "en"].includes(value) ? value : "auto";
    locale = resolve(preference);
    apply();
    window.dispatchEvent(new CustomEvent("hass-cleaner-language", { detail: { preference, locale } }));
  }

  function text(value) {
    return locale === "en" ? translated(String(value)) : String(value);
  }

  observer = new MutationObserver((mutations) => {
    observer.disconnect();
    for (const mutation of mutations) {
      if (mutation.type === "childList") mutation.addedNodes.forEach(localizeNode);
      else if (!["SCRIPT", "STYLE", "CODE", "PRE"].includes(mutation.target.parentElement?.tagName)) localizeNode(mutation.target);
    }
    observer.observe(document.body, observationOptions);
  });
  document.addEventListener("DOMContentLoaded", () => {
    locale = resolve(preference);
    apply();
  });
  window.HassCleanerI18n = { apply, setPreference, text, get locale() { return locale; }, get preference() { return preference; } };
})();
