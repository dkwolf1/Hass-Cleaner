# Reference checks and Home Assistant Repairs

Development preview for Hass-Cleaner 1.1.0. Keep a complete backup and test on a non-critical installation first. This feature does not provide Spook feature parity or prove that anything is safe to delete.

## Two components

- **Hass-Cleaner app:** storage and registry review, cleanup preparation and execution. Displays a reference snapshot collected during each new scan.
- **Hass-Cleaner Companion integration:** runs inside Home Assistant Core, reads loaded configuration and maintains native Repairs. Checks after startup and every five minutes, including while the app is stopped. An app scan requests a fresh check.

The companion never changes automations, scripts, dashboards, entities or devices. Its only Home Assistant writes are its own Repairs issue metadata. It never executes templates or calls the actions it finds.

## Installation

1. Use the companion from the **same version** as the app. For this development preview, use the development branch rather than a previous release archive.
2. Copy the repository's `custom_components/hass_cleaner` directory into your Home Assistant configuration directory, resulting in `/config/custom_components/hass_cleaner/manifest.json`. Do not copy it into the app container or nest an extra `hass_cleaner` directory.
3. Restart **Home Assistant Core**, not just the app.
4. Open **Settings → Devices & services → Add integration** and search for **Hass-Cleaner Companion**. Confirm the setup screen. There are no tokens to enter.
5. Start/update Hass-Cleaner to the matching app version and run **New scan**. Open **Entities → Reference checks**.

The companion runtime adapter targets the Home Assistant 2026.9 APIs. Older versions have not been verified. It is not yet published in HACS. Installing/updating the app alone does not install/update the companion.

For a local installable ZIP, run `python tools/package_companion.py` from the repository root. Extract the ZIP into the Home Assistant configuration directory; it already contains the `custom_components/hass_cleaner` path. Review and back up any existing companion installation before replacing its files.

## What gets checked

### Part 1 implementation scope

All seven source families are now represented: automations, scripts, dashboards, scenes, groups, helpers/templates and energy/statistics configuration. This is static dependency checking, not complete interpretation of every custom integration or computed template. Live Home Assistant acceptance testing remains a release requirement.

- **Scenes:** runtime membership, including dynamically created scenes. An integration-provided scene without exposed members is explicitly unavailable.
- **Groups:** runtime legacy groups, configured group helpers and YAML group definitions (including list shorthand).
- **Helpers/templates:** config-entry data/options and relevant YAML sections/platforms, with includes/packages resolved by Home Assistant. Options-shadowed data values are excluded. Supported domains are listed in `custom_components/hass_cleaner/sources.py`: group, template, min/max, integral, utility meter, statistics, derivative, threshold, filter, history statistics, generic thermostat/hygrostat, switch-as-X, time-of-day, input helpers, counter, timer, schedule, random, trend and Bayesian helpers. Custom helper domains are not automatically interpreted.
- **Energy/statistics:** energy preferences, price entities, statistics dashboard cards and explicit Recorder entity filters. Statistics are checked against Recorder metadata (including external statistics), not against live entity states. Historical statistics can remain valid after the entity disappears. If Recorder cannot be read, verification is unknown and no missing-statistic Repair is created.
- YAML helper/template sources represent the **current saved configuration**, which can differ from loaded configuration until reloaded. UI helper sources identify their configuration-entry IDs; YAML paths identify configuration positions rather than source-file line numbers.
- Entity details show counts of matching source configurations by category. Repeated references in one source do not inflate that source count. The same entity can have both live-entity references and retained-statistics references.

| Source or target | Coverage |
|---|---|
| Loaded automations and scripts | Static entity, device, area and service/action targets, including nested actions and conditions |
| Device automations | Resolve known entity-registry UUIDs to entity IDs; flag missing UUIDs |
| Storage and YAML dashboards | Configuration loaded through Home Assistant, including standard entity lists and target fields |
| Templates | Parse literal calls such as `states('sensor.temperature')` and `states.sensor.temperature`, including standalone template definitions; never execute them |
| Existing entities | Registry entities plus runtime states; disabled entities are not considered missing merely because they have no state |
| Missing actions | Compared with currently registered Home Assistant services/actions after startup |

Each result includes a source name and ID, target type and ID, and a path such as `$.actions[0].target.entity_id`. Array indexes start at **0**. Paths identify positions in loaded configuration, not YAML file line numbers. The app supports pagination, all/missing filtering, per-source coverage, entity and bundle dependencies, and JSON/CSV/Markdown exports.

## Coverage and interpretation

- `completed` means the supported static check completed, **not** that the entire installation was exhaustively checked.
- Dynamic/computed templates, blueprint expansion, custom cards, dashboard strategies and unreadable sources limit coverage. Literal references can still be reported, but the source is marked partial.
- Not covered: arbitrary Python/custom-integration logic, unlisted helper domains, every YAML integration, indirect script/template semantics and every custom-card property. Label/floor targets and Recorder wildcard/domain filters mark limited coverage. This is not a general Home Assistant interpreter.
- Automations/scripts and runtime memberships use loaded configuration; YAML helpers/templates use the saved configuration. Reload changes before checking the running behaviour. Some sources that never loaded may not be discoverable; inspect Home Assistant's own configuration errors too.
- A registered but unavailable entity is **not missing**. An action that temporarily disappears during an integration reload can produce a temporary issue; recheck after the integration has recovered.
- Device and area targets can affect selected entities indirectly. They are shown as potential use, not proof that every selected entity is actually affected.
- Zero findings never proves that removal is safe. The backup choice and explicit user risk acceptance remain required by the normal cleanup workflow.

## Repairs workflow

Open **Settings → System → Repairs**. The companion groups missing targets into one stable issue per source, with up to 30 example paths. The app and exports contain the full findings.

1. Open the named automation, script or dashboard.
2. Correct the reference, restore the missing target, or remove the reference if it is no longer needed.
3. Reload YAML changes where needed. Wait up to five minutes, or request a new app scan.
4. The issue disappears when that source can be fully checked and no missing references remain. Verified removal of a source also resolves its issue after a complete check.

There is deliberately no automatic **Fix** button. Ignore intentional missing references using the normal Repairs controls. Repeated checks retain the same issue identity and do not reset ignored status. Home Assistant controls dismissal behaviour across its own upgrades; removing/reloading the companion removes its issues and can reset dismissal history.

An unreadable or partial source does not falsely resolve its previous issue. A previously reported issue may therefore remain until the source is fully readable or its remaining missing references are independently addressed and the source can be fully checked. This is shown as limited coverage in the app.

## Before registry cleanup

The preparation contains the selected objects' direct references and potential device/area dependencies, including the scan time. Review these before confirming. When the companion was available during preparation, the app rechecks references and current registry associations before the first removal command. A changed dependency or changed source coverage requires a new scan and review. An unavailable recheck stops execution without changing the registry.

If the companion was not available at preparation time, the app shows that limitation explicitly and retains the existing user-directed cleanup choice. The check is not an atomic Home Assistant transaction: avoid editing/reloading configuration while executing cleanup. No individual undo is available for registry removal; recovery may require a full backup.

## Privacy and troubleshooting

Only source names/IDs, target IDs, configuration paths, coverage and check time leave the companion. Full configurations, service payloads and template bodies are not exported. IDs and names can still reveal personal information: review reports before sharing them.

The WebSocket command `hass_cleaner/references` is administrator-only. The app uses its normally configured Supervisor authentication. No browser tokens or new secrets are required. If authentication is refused or the companion is missing, the normal registry/file scan continues and reference checks show **unavailable**, never a false all-clear.

If unavailable: verify installation path, restart Core, add the companion integration, check Core logs, and run a new app scan. Automatic/generated dashboards without a readable configuration may show limited coverage. No repairs from other integrations (including Spook) are deleted or modified. Running both can result in overlapping warnings.

## Validation before release

Local automated tests cover the analyzer, WebSocket bridge, HA adapter contracts, Repairs lifecycle, pagination, exports and cleanup revalidation. Contract tests mock Home Assistant interfaces; they do not demonstrate a successful live installation.

On a disposable Home Assistant 2026.9 instance:

1. Install/configure the companion and verify a clean startup with no repeated errors.
2. Add a test automation, script and manual dashboard referring to a deliberately nonexistent entity. Verify exact paths, three source issues, app results and English/Dutch text.
3. Correct a reference and reload it. Verify its issue resolves. Ignore another issue and verify repeated checks preserve the choice.
4. Check YAML dashboards, a disabled registered entity, a device trigger using a registry UUID, and a dynamic template. Confirm disabled entities are not missing and dynamic coverage is partial.
5. Temporarily make a test dashboard unreadable. Confirm its prior issue remains and the app shows limited coverage.
6. Prepare registry cleanup only for disposable test entities, change a dependency, and verify execution stops before any removal.
7. Restart Core, reload/remove the companion, and verify scheduled work and issue ownership behave correctly.
8. Stop/remove the companion and confirm the app still scans with an explicit unavailable reference status.
9. Create disposable scene/group/helper/template references. Check both UI-created helpers and YAML packages; verify a legacy group is listed once and changing a helper option removes the old dependency.
10. Verify an external statistic and a retained statistic whose entity no longer exists. They must not produce missing-entity Repairs. An actually missing statistic should produce a finding; unavailable Recorder access should instead show unknown verification.

## Nederlands kort

De zeven categorieën uit deel 1 zijn aangesloten, inclusief scènes, groepen, ondersteunde helpers, losse templates en energie/statistieken. Geldige historische/externe statistieken worden niet als verdwenen entiteit gemeld. Zonder Recorder is de statistiekcontrole expliciet onbekend. Niet alle aangepaste helpers of dynamische templates zijn interpreteerbaar; praktijktests blijven nodig voordat dit releaseklaar is.

- Installeer naast de app de **Hass-Cleaner Companion** in `/config/custom_components/hass_cleaner`, herstart Home Assistant Core en voeg de integratie toe via **Instellingen → Apparaten & diensten**.
- Start een nieuwe appscan. Onder **Entiteiten → Referentiecontrole** staan bronnen, doelen, exacte configuratiepaden en beperkte dekking.
- Meldingen staan bij **Instellingen → Systeem → Reparaties**. Corrigeer zelf de configuratie; de companion controleert iedere vijf minuten. Er wordt niets automatisch hersteld of verwijderd.
- App en companion zijn afzonderlijke onderdelen en moeten afzonderlijk worden bijgewerkt. Versie 1.1.0 is nog een ontwikkelversie; praktijktests zijn nodig.
- Geen verwijzingen gevonden betekent **niet** veilig verwijderen. Templates, blueprints, aangepaste kaarten en onleesbare bronnen kunnen gebruik verbergen. Maak een volledige back-up en controleer de gevolgen.
