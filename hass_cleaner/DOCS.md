# Hass-Cleaner

Storage auditing and user-directed cleanup for Home Assistant OS. Handle with care: review every selection and keep a complete Home Assistant backup. Availability states and observation periods are guidance, not proof that an object is unused.

## Getting started

1. Start the app, enable **Show in sidebar**, and open its interface.
2. Run **New scan**. Scanning does not change your Home Assistant files or registries.
3. Review **Scan results**, **Entities** and **Bundles**. Nothing is selected automatically.
4. Select what you want to change and choose **Prepare cleanup**. Preparation itself changes nothing.
5. Read the consequences and recovery advice. Choose whether to create/verify a backup, confirm one manually or proceed without one.
6. Confirm the separate execution step only when you understand the selection.

Registered entities can be selected; runtime-only states have no registry entry and are excluded. Filters and grouped temporary signals help you review large installations. Local choices to monitor, expect or defer a signal do not disable entities or change Home Assistant.

## File safety and recovery

- Protected system files cannot be selected. Personal and uncertain content requires additional risk acknowledgement.
- Before moving files, the whole selection is revalidated against current paths, types, sizes, modification times, checksums and classification.
- Selected files go to quarantine first. Restore checks SHA-256 and never overwrites an existing target file.
- Interrupted restore and purge operations are reconciled at startup. Damaged journals are reported, not replaced with empty history.
- Expired quarantine files are not deleted automatically. Permanent removal requires a separate confirmation.
- Use a full backup if recovery through quarantine is unavailable.

Python bytecode without matching source is a review item, not a safe candidate. Removing it can prevent a custom integration from loading.

## Entities and bundles

The app reads entity, device and area registries, configuration entries and current states through official Home Assistant APIs. Missing relationships and unavailable states need your interpretation.

Execution removes explicitly selected entity entries or device/config-entry relationships through official APIs. It does not delete areas or configuration entries themselves. Changes can break dashboards, scripts and automations; integrations may recreate objects. There is no individual registry undo: recovery requires a Home Assistant backup.

Registry execution records intent and per-command progress. An interrupted or uncertain outcome must be reviewed before trying again.

## Database

**Database** uses the official `recorder.purge` service. This permanently removes historical data, not current entities or devices. Choose the days to retain and confirm `PURGE`.

Repacking is off by default: it can require substantial processing and temporary disk space. Applying the Recorder filter also removes historical data excluded by the current Recorder configuration.

## Backups

Scanning and preparation do not require a backup. Before execution, a verified full backup is strongly recommended. The app can request one through Supervisor and reuse recent verification for up to 24 hours.

You may confirm a manually checked backup or deliberately continue without one. This requires explicit acknowledgement and is logged; it does not guarantee that changes can be undone.

## Exports and privacy

**Export** explains the available formats:

- **Markdown:** a readable summary with risks and recovery guidance, in the selected interface language.
- **CSV:** tabular results for filtering and sorting in a spreadsheet.
- **JSON:** complete structured results for technical investigation.

Readable reports limit large tables; JSON and CSV retain detailed results. User-defined names and technical identifiers are not translated. Technical exports can contain original diagnostic text.

Content previews expose structure and counts rather than raw secret values. Reports still contain potentially private paths, object names and identifiers: review them before sharing.

## Language and configuration

Choose **Automatic**, **English** or **Dutch** in **Settings → Interface language**, or in the Home Assistant App configuration. Automatic follows the first supported browser language preference and falls back to English; it does not independently read your Home Assistant account language.

Changed App configuration fields override the corresponding saved UI fields. Other UI choices remain unchanged. Saving in the app applies your new choices again. UI saves never rewrite Supervisor's options file.

If upgrading from an older version with no configuration baseline, newer Supervisor options take precedence once. Obsolete `deletion_mode` options are removed through Supervisor during startup when permitted.

## History and storage

Set the number of report sets to retain in **Settings**. Only Hass-Cleaner's own report filenames are managed. Completed scan data in memory is bounded independently of disk report retention.

**History → Clean start** clears local reports, observations, entity choices, comparison snapshots, preparations and completed operation history. Wait for running operations to finish first. It does not change Home Assistant or remove active quarantine files.

**Quarantine → Clear completed log** removes completed log entries while retaining active recovery records. Interrupted or uncertain registry outcomes remain available for review.

## Nederlands — kort

- Begin met **Nieuwe scan**; scannen en **Opschoning voorbereiden** wijzigen niets.
- Beoordeel zelf of bestanden, entiteiten en apparaten nog nodig zijn. Maak bij voorkeur een volledige Home Assistant-back-up.
- Bestanden gaan eerst naar quarantaine. Registerverwijdering heeft geen individuele herstelknop; daarvoor is een back-up nodig.
- Kies **Instellingen → Interfacetaal** voor Nederlands. Gewijzigde App-instellingen krijgen per veld voorrang; overige UI-keuzes blijven behouden.
- **Exporteren** biedt een leesbaar rapport, CSV voor filteren en JSON voor technische details. Controleer exports voordat je ze deelt.
- **Historie → Schone start** wist lokale historie zodra actieve bewerkingen klaar zijn. Actieve quarantaine en onzekere herstelgegevens blijven behouden.
