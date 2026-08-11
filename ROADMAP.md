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
| 0.9.0 | Huidige release candidate | Supervisor-back-upverificatie, hersteltest, bewaartermijn, expliciete verwijdering na verval en aangescherpte Recorder-purge. |

### Vereist vóór 1.0

- 0.9.0 bouwen en installeren via de echte GitHub/GHCR-workflow.
- Volledige back-up starten en voltooiing op Home Assistant OS verifiëren.
- Eén bewezen veilig testbestand naar quarantaine verplaatsen.
- Hersteltest uitvoeren en hetzelfde bestand werkelijk terugplaatsen.
- Controleren dat een gewijzigd bestand, ontbrekende back-up en verkeerde bevestiging worden geblokkeerd.
- Recorder-purge met een kleine, veilige testinstelling controleren.
- Interface testen op desktop en mobiel.
- Volledige Ingress-interface in Nederlands en Engels aanbieden.
- Minimaal enkele gebruikerstests uitvoeren met verschillende integraties en opslagprofielen.
- Bekende problemen documenteren en alle releaseblokkerende fouten oplossen.

### 1.0.0 — Eerste stabiele versie

- Alleen publiceren wanneer alle bovenstaande releasecriteria zijn afgetekend.
- Stabiel quarantaine- en herstelcontract.
- Tweetalige interface, documentatie en Home Assistant-instellingen.
- Geen automatische entity-, apparaat- of registerverwijdering.
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
| 0.9.0 | Current release candidate | Supervisor backup verification, restore testing, retention, explicit post-expiry deletion and a stricter Recorder purge. |

### Required before 1.0

- Build and install 0.9.0 through the real GitHub/GHCR workflow.
- Start a full backup and verify completion on Home Assistant OS.
- Move one proven-safe test file into quarantine.
- Run the restore test and restore that file to its original location.
- Confirm that changed files, missing backup evidence and incorrect confirmations are blocked.
- Validate Recorder purge with a small and safe test configuration.
- Test the interface on desktop and mobile.
- Provide the complete Ingress interface in Dutch and English.
- Run user tests across several integrations and storage profiles.
- Document known issues and resolve every release-blocking defect.

### 1.0.0 — First stable release

- Publish only after every release gate above has been signed off.
- Stable quarantine and recovery contract.
- Bilingual interface, documentation and Home Assistant settings.
- No automatic entity, device or registry deletion.
- Safe migration of existing reports, plans and quarantine data.

### After 1.0

- More generic cache profiles with proven recovery behaviour.
- Better storage trends and estimated savings per integration.
- Optional notifications for expired quarantine and persistent entity problems.
- Additional languages through separate translation files.
- Consider entity deletion only if Home Assistant provides an official, verifiable and recoverable API.
