# Hass-Cleaner Roadmap

[Nederlands](#nederlands) · [English](#english)

## Nederlands

### Uitgangspunt

Veiligheid gaat vóór extra opruimwinst. Een release gaat pas door wanneer risicovolle situaties aantoonbaar worden geblokkeerd en herstel getest kan worden.

### Afgerond

| Versie | Status | Inhoud |
|---|---|---|
| 0.7.2 | Afgerond | Betrouwbare tijdmetingen, verschillen tussen scans, opgeslagen gebruikersbeslissingen, beveiliging en paginering/performance. |
| 0.7.3 | Afgerond | Duidelijkere entitysignalen, compacte bundels, apart onderscheid tussen tijdelijk, langdurig, `unavailable`, `unknown` en integratiespecifieke problemen. |
| 0.8.0 | Lokaal geïmplementeerd | Werkende quarantaine voor bewezen veilige bestanden, batchvalidatie, SHA-256-manifest en veilig herstel. |
| 0.9.0 | Afgerond | Supervisor-back-upverificatie, hersteltest, bewaartermijn en expliciete verwijdering na verval. |
| 0.9.1 | Afgerond | Toegestane back-upcontrole, hergebruik van back-upbewijs, bewuste optionele back-upkeuze en selecteerbare entitybeoordeling. |
| 1.0.0 | In ontwikkeling | Gebruikersgestuurde cleanup, registeruitvoering, persoonlijke inhoud, schone start en behoud van harde systeembescherming. |

### Vereist vóór 1.0

- 1.0.0 bouwen en installeren via de echte GitHub/GHCR-workflow.
- Volledige back-up starten en voltooiing op Home Assistant OS verifiëren.
- Zowel een veilige als een bewust gekozen reviewkandidaat naar quarantaine verplaatsen.
- Hersteltest uitvoeren en hetzelfde bestand werkelijk terugplaatsen.
- Controleren dat een gewijzigd of beschermd bestand en een verkeerde bevestiging worden geblokkeerd.
- Een kleine set test-entities verwijderen en herstel vanuit een Home Assistant-back-up oefenen.
- Recorder-purge met een kleine, veilige testinstelling controleren.
- Interface testen op desktop en mobiel.
- Volledige Ingress-interface in Nederlands en Engels aanbieden.
- Minimaal enkele gebruikerstests uitvoeren met verschillende integraties en opslagprofielen.
- Bekende problemen documenteren en alle releaseblokkerende fouten oplossen.

### 1.0.0 — Eerste stabiele versie

- Alleen publiceren wanneer alle bovenstaande releasecriteria zijn afgetekend.
- Stabiel quarantaine- en herstelcontract.
- Tweetalige interface, documentatie en Home Assistant-instellingen.
- Alleen expliciet door de gebruiker geselecteerde entity-, apparaat- en registerverwijdering via officiële API's.
- Veilige migratie van bestaande rapporten, plannen en quarantainegegevens.

### Na 1.0

- Meer generieke, aantoonbaar herstelbare cacheprofielen.
- Betere opslagtrends en geschatte winst per integratie.
- Optionele meldingen voor verlopen quarantaine en langdurige entityproblemen.
- Uitbreiding naar extra talen via losse vertaalbestanden.
- Entityverwijdering uitsluitend onderzoeken als Home Assistant daarvoor een officiële, controleerbare en herstelbare API biedt.

---

## English

### Principle

Safety takes priority over reclaimed space. A release proceeds only when risky situations are demonstrably blocked and recovery can be tested.

### Completed

| Version | Status | Scope |
|---|---|---|
| 0.7.2 | Completed | Reliable duration tracking, scan differences, saved user decisions, security controls and pagination/performance. |
| 0.7.3 | Completed | Clearer entity signals, compact bundles and separate treatment of temporary, persistent, `unavailable`, `unknown` and integration-specific problems. |
| 0.8.0 | Implemented locally | Working quarantine for proven-safe files, batch validation, SHA-256 manifests and safe recovery. |
| 0.9.0 | Completed | Supervisor backup verification, restore testing, retention and explicit post-expiry deletion. |
| 0.9.1 | Completed | Permitted backup verification, reusable evidence, an explicit optional backup choice and selectable entity reviews. |
| 1.0.0 | In development | User-directed cleanup, registry execution, personal content, clean-start controls and hard core-system protection. |

### Required before 1.0

- Build and install 1.0.0 through the real GitHub/GHCR workflow.
- Start a full backup and verify completion on Home Assistant OS.
- Move both a safe file and an explicitly accepted review candidate into quarantine.
- Run the restore test and restore that file to its original location.
- Confirm that changed or protected files and incorrect confirmations are blocked.
- Remove a small set of test entities and rehearse recovery from a Home Assistant backup.
- Validate Recorder purge with a small and safe test configuration.
- Test the interface on desktop and mobile.
- Provide the complete Ingress interface in Dutch and English.
- Run user tests across several integrations and storage profiles.
- Document known issues and resolve every release-blocking defect.

### 1.0.0 — First stable release

- Publish only after every release gate above has been signed off.
- Stable quarantine and recovery contract.
- Bilingual interface, documentation and Home Assistant settings.
- Only explicitly user-selected entity, device and registry removal through official APIs.
- Safe migration of existing reports, plans and quarantine data.

### After 1.0

- More generic cache profiles with proven recovery behaviour.
- Better storage trends and estimated savings per integration.
- Optional notifications for expired quarantine and persistent entity problems.
- Additional languages through separate translation files.
- Consider entity deletion only if Home Assistant provides an official, verifiable and recoverable API.
