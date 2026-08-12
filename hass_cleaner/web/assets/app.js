const state = {
  scan: null,
  items: [],
  settings: null,
  registryAudit: null,
  guidance: null,
  status: null,
  activeBundle: null,
  activeEntity: null,
  latestPlan: null,
  selected: new Set(),
  selectedEntities: new Set(),
  entityGroupOpen: new Map(),
  visibleEntityIds: [],
  pollTimer: null,
  csrfToken: "",
  backupEvidenceToken: "",
  backupVerified: false,
  scanFullLoaded: false,
  fullScanPromise: null,
};

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const MAX_BUNDLE_DEVICE_DETAILS = 100;

function apiUrl(path) {
  const current = window.location.pathname;
  const base = current.endsWith("/") ? current : current.substring(0, current.lastIndexOf("/") + 1);
  return `${base}${path.replace(/^\//, "")}`;
}

async function api(path, options = {}) {
  const method = String(options.method || "GET").toUpperCase();
  const response = await fetch(apiUrl(path), {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(method !== "GET" && state.csrfToken ? { "X-Hass-Cleaner-CSRF": state.csrfToken } : {}),
      ...(options.headers || {}),
    },
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
  return payload;
}

function showToast(message, error = false) {
  const toast = $("#toast");
  toast.textContent = message;
  toast.classList.toggle("error", error);
  toast.classList.add("show");
  window.setTimeout(() => toast.classList.remove("show"), 3600);
}

function activateTab(name) {
  $$(".tab").forEach((tab) => tab.classList.toggle("active", tab.dataset.tab === name));
  $$(".view").forEach((view) => view.classList.toggle("active", view.id === `view-${name}`));
  if (["results", "entities", "registry"].includes(name)) loadFullScan();
  if (name === "quarantine") loadQuarantine();
}

function formatBytes(bytes) {
  if (!Number.isFinite(bytes) || bytes <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const value = bytes / 1024 ** index;
  return `${value >= 10 || index === 0 ? value.toFixed(0) : value.toFixed(1)} ${units[index]}`;
}

function riskLabel(risk) {
  return { safe: "Veilig", review: "Beoordeling", protected: "Beschermd" }[risk] || risk;
}

function categoryLabel(category) {
  return {
    python_cache: "Python-cache",
    python_cache_without_source: "Python-cache zonder bron",
    editor_artifact: "Editorrestant",
    temporary_or_backup: "Tijdelijk / back-up",
    old_log: "Oud logbestand",
    custom_components: "Custom component",
    frontend_package: "HACS/frontendpakket",
    www_asset_inventory: "Dashboard-/webbestand",
    integration_cache_candidate: "Mogelijke integratiecache",
    brand_cache: "Home Assistant-pictogramcache",
    personal_media: "Persoonlijke media",
    database: "Database",
    core_configuration: "Kernconfiguratie",
    home_assistant_storage: ".storage",
    symlink: "Symbolische link",
  }[category] || category;
}

function registryCategoryLabel(category) {
  return {
    entity_without_device: "Entity zonder apparaat",
    missing_device_reference: "Ontbrekend apparaat",
    missing_area_reference: "Ontbrekend gebied",
    missing_config_entry_reference: "Ontbrekende config-entry",
    missing_parent_device_reference: "Ontbrekend bovenliggend apparaat",
    entity_not_loaded: "Entity niet geladen",
    disabled_entity: "Uitgeschakelde entity",
    device_without_entities: "Apparaat zonder entities",
    empty_area: "Leeg gebied",
  }[category] || category;
}

async function loadStatus() {
  try {
    const status = await api("api/status");
    state.status = status;
    state.csrfToken = status.csrf_token || "";
    const pill = $("#mode-pill");
    pill.classList.add("online");
    pill.innerHTML = `<i></i>${status.mode === "home_assistant" ? "Home Assistant verbonden" : "Lokale ontwikkelmodus"}`;
    const purgeAvailability = $("#purge-availability");
    purgeAvailability.textContent = status.recorder_purge_enabled ? "Beschikbaar" : "Alleen in Home Assistant";
    purgeAvailability.classList.toggle("success", status.recorder_purge_enabled);
    $("#open-purge-dialog").disabled = !status.recorder_purge_enabled;
  } catch (error) {
    $("#mode-pill").innerHTML = "<i></i>Niet verbonden";
  }
}

async function loadSettings() {
  state.settings = await api("api/settings");
  $("#min-temp-age").value = state.settings.min_temp_age_days;
  $("#min-log-age").value = state.settings.min_log_age_days;
  $("#retention-days").value = state.settings.retention_days;
  $("#retention-value").textContent = state.settings.retention_days;
  const selected = $(`input[name="deletion-mode"][value="${state.settings.deletion_mode}"]`);
  if (selected) selected.checked = true;
  $("#advanced-mode").checked = Boolean(state.settings.advanced_mode);
  $("#report-retention-count").value = state.settings.report_retention_count || 10;
  renderAdvancedVisibility();
  updateRetentionVisibility();
  renderPolicy();
}

function renderPolicy() {
  if (!state.settings) return;
  const quarantine = state.settings.deletion_mode === "quarantine";
  $("#policy-title").textContent = quarantine ? `${state.settings.retention_days} dagen herstelbaar` : "Direct permanent verwijderen";
  $("#policy-description").textContent = quarantine ? "Verplaatsen naar beveiligde quarantaine" : "Extra waarschuwing en back-upvraag verplicht";
}

function renderAdvancedVisibility() {
  const visible = Boolean(state.settings?.advanced_mode || $("#advanced-mode")?.checked);
  $(".raw-inventory")?.classList.toggle("hidden", !visible);
  $$(".technical-action").forEach((item) => item.classList.toggle("hidden", !visible));
}

async function startScan() {
  try {
    state.selected.clear();
    state.scanFullLoaded = false;
    const scan = await api("api/scans", { method: "POST", body: "{}" });
    state.scan = scan;
    showScanProgress(scan);
    pollScan(scan.id);
  } catch (error) {
    showToast(error.message, true);
  }
}

function showScanProgress(scan) {
  $("#scan-empty").classList.add("hidden");
  $("#scan-progress").classList.remove("hidden");
  $("#scan-state").textContent = scan.status === "queued" ? "In wachtrij" : "Bezig";
  $("#progress-detail").textContent = `${scan.visited_files || 0} bestanden bekeken${scan.current_path ? ` · ${scan.current_path}` : ""}`;
}

function pollScan(id) {
  window.clearTimeout(state.pollTimer);
  state.pollTimer = window.setTimeout(async () => {
    try {
      const scan = await api(`api/scans/${id}`);
      state.scan = scan;
      if (scan.status === "queued" || scan.status === "running") {
        showScanProgress(scan);
        pollScan(id);
      } else {
        finishScan(scan);
      }
    } catch (error) {
      showToast(error.message, true);
    }
  }, 450);
}

function finishScan(scan, showCompletionToast = true) {
  $("#scan-progress").classList.add("hidden");
  $("#scan-empty").classList.remove("hidden");
  if (scan.status === "failed") {
    $("#scan-state").textContent = "Mislukt";
    $("#scan-empty strong").textContent = "Scan kon niet worden voltooid";
    $("#scan-empty p").textContent = scan.error;
    showToast(scan.error, true);
    return;
  }
  state.items = scan.items || [];
  state.scan = scan;
  state.scanFullLoaded = true;
  state.registryAudit = scan.registry_audit || null;
  state.guidance = scan.cleanup_guidance || null;
  $$(".report-action").forEach((button) => button.classList.remove("hidden"));
  $("#scan-state").textContent = "Voltooid";
  $("#scan-empty strong").textContent = `${scan.visited_files} bestanden gecontroleerd`;
  $("#scan-empty p").textContent = `${state.items.length} gerapporteerd · ${scan.ignored_files || 0} volgens beleid genegeerd. De scan heeft niets gewijzigd.`;
  renderMetrics(scan);
  renderRecipes();
  renderResults();
  renderRegistryAudit();
  populateEntityFilters();
  renderEntities();
  $("#select-all-safe").disabled = !(state.guidance?.safe_recipes || []).length;
  loadScanHistory();
  if (showCompletionToast) showToast("Veilige scan voltooid");
}

function finishScanSummary(scan) {
  state.scan = scan;
  state.scanFullLoaded = false;
  state.registryAudit = scan.registry_audit || null;
  state.guidance = scan.cleanup_guidance || null;
  $("#scan-progress").classList.add("hidden");
  $("#scan-empty").classList.remove("hidden");
  $$(".report-action").forEach((button) => button.classList.remove("hidden"));
  $("#scan-state").textContent = "Voltooid";
  $("#scan-empty strong").textContent = `${scan.visited_files || 0} bestanden gecontroleerd`;
  const reported = Object.values(scan.counts || {}).reduce((total, value) => total + Number(value || 0), 0);
  $("#scan-empty p").textContent = `${reported} gerapporteerd · ${scan.ignored_files || 0} volgens beleid genegeerd. Details worden pas geopend wanneer nodig.`;
  renderMetrics(scan);
}

async function loadFullScan() {
  if (!state.scan?.id || state.scanFullLoaded || state.scan.status !== "completed") return;
  if (state.fullScanPromise) return state.fullScanPromise;
  state.fullScanPromise = (async () => {
    try {
      const full = await api(`api/scans/${state.scan.id}`);
      finishScan(full, false);
    } catch (error) {
      showToast(error.message, true);
    } finally {
      state.fullScanPromise = null;
    }
  })();
  return state.fullScanPromise;
}

function renderMetrics(scan) {
  const guidance = scan.cleanup_guidance || {};
  const safeRecipes = guidance.safe_recipes || [];
  const investigate = guidance.investigation_recipes || [];
  $("#safe-size").textContent = formatBytes(guidance.safe_total_bytes || 0);
  $("#review-size").textContent = formatBytes(guidance.investigation_total_bytes || 0);
  $("#protected-size").textContent = formatBytes(guidance.inventory_total_bytes || 0);
  $("#total-size").textContent = formatBytes(guidance.safe_total_bytes || 0);
  $("#safe-count").textContent = `${safeRecipes.length} veilige recepten`;
  $("#review-count").textContent = `${investigate.length} zelf beoordelen`;
  $("#protected-count").textContent = "Systeeminventaris · behouden";
}

function renderRecipes() {
  const list = $("#recipe-list");
  const guidance = state.guidance;
  if (!guidance) {
    list.innerHTML = '<div class="table-empty panel">Voer eerst een scan uit.</div>';
    return;
  }
  const recipes = [...(guidance.safe_recipes || []), ...(guidance.investigation_recipes || [])];
  list.innerHTML = recipes.length ? recipes.map((recipe) => {
    const passed = Boolean(recipe.gate_passed);
    const selectedAll = recipe.item_ids?.length && recipe.item_ids.every((id) => state.selected.has(id));
    const gates = (recipe.gates || []).map((gate) => `<li class="${gate.passed ? "passed" : "failed"}"><strong>${gate.passed ? "✓" : "!"}</strong><span>${escapeHtml(gate.explanation)}</span></li>`).join("");
    const samples = (recipe.sample_paths || []).map((path) => `<li>${escapeHtml(path)}</li>`).join("");
    const producers = (recipe.producer_groups || []).map((group) => `<li><strong>${escapeHtml(group.producer)}</strong><span>${group.file_count} bestanden · ${formatBytes(group.size_bytes)}</span></li>`).join("");
    return `<article class="panel recipe-card ${passed ? "recipe-safe" : "recipe-review"}">
      <div class="recipe-main"><div class="eyebrow">${passed ? "VEILIG RECEPT" : recipe.kind === "personal" ? "PERSOONLIJKE INHOUD" : "EERST ONDERZOEKEN"}</div><h3>${escapeHtml(recipe.title)}</h3><p>${escapeHtml(recipe.description)}</p><small>${recipe.file_count} bestanden · ${formatBytes(recipe.size_bytes)} · producer: ${escapeHtml(recipe.producer)}</small></div>
      <div class="recipe-gates"><strong>Veiligheidscontrole</strong><ul>${gates}</ul></div>
      <details><summary>Producenten, voorbeelden en advies</summary><ul class="producer-groups">${producers}</ul><ul class="sample-paths">${samples}</ul><p>${escapeHtml(recipe.recommendation)}</p></details>
      <div class="recipe-action"><span class="risk-chip ${passed ? "safe" : "review"}">${passed ? "Aanbevolen" : "Eigen beoordeling"}</span><button class="button button-primary recipe-select" data-recipe-id="${escapeHtml(recipe.id)}">${selectedAll ? "Uit opruimplan verwijderen" : "Aan opruimplan toevoegen"}</button></div>
    </article>`;
  }).join("") : '<div class="table-empty panel">Geen opruimrecepten gevonden. Je systeeminventaris blijft behouden.</div>';
  $$(".recipe-select", list).forEach((button) => button.addEventListener("click", () => selectRecipe(button.dataset.recipeId, button)));
  const inventory = guidance.inventory || [];
  $("#inventory-summary").innerHTML = inventory.length ? inventory.map((item) => `<span><strong>${item.count}</strong> ${escapeHtml(categoryLabel(item.category))} · ${formatBytes(item.size_bytes)}</span>`).join("") : "Geen beschermde inventaris gevonden.";
}

function selectRecipe(recipeId, button) {
  const recipes = [...(state.guidance?.safe_recipes || []), ...(state.guidance?.investigation_recipes || [])];
  const recipe = recipes.find((item) => item.id === recipeId);
  if (!recipe?.selectable_for_dry_run) return;
  const allSelected = recipe.item_ids.every((id) => state.selected.has(id));
  recipe.item_ids.forEach((id) => allSelected ? state.selected.delete(id) : state.selected.add(id));
  button.textContent = allSelected ? "Aan opruimplan toevoegen" : "Uit opruimplan verwijderen";
  renderResults();
}

function selectAllSafe() {
  const ids = (state.guidance?.safe_recipes || []).flatMap((recipe) => recipe.item_ids || []);
  const allSelected = ids.length && ids.every((id) => state.selected.has(id));
  ids.forEach((id) => allSelected ? state.selected.delete(id) : state.selected.add(id));
  $("#select-all-safe").textContent = allSelected ? "Alles veilig selecteren" : "Veilige selectie wissen";
  renderRecipes();
  renderResults();
}

function renderResults() {
  const body = $("#results-body");
  const filter = $("#risk-filter").value;
  const items = state.items.filter((item) => filter === "all" || item.risk === filter);
  if (!items.length) {
    body.innerHTML = '<div class="table-empty">Geen bestanden binnen dit filter.</div>';
    updatePrepareButton();
    return;
  }
  body.innerHTML = items.map((item) => {
    const disabled = item.risk === "safe" ? "" : "disabled";
    const checked = state.selected.has(item.id) ? "checked" : "";
    return `<label class="result-row">
      <input type="checkbox" data-item-id="${item.id}" ${disabled} ${checked} aria-label="Selecteer ${escapeHtml(item.path)}">
      <span class="result-path"><button type="button" class="file-advice-link" data-advice-id="${item.id}">${escapeHtml(item.path.split("/").pop())}</button><small title="${escapeHtml(item.path)}">${escapeHtml(item.path)}</small></span>
      <span class="item-category">${escapeHtml(categoryLabel(item.category))}<small>${escapeHtml(item.advice?.evidence_label || "Niet beoordeeld")}</small></span>
      <span class="risk-chip ${item.risk}">${escapeHtml(riskLabel(item.risk))}</span>
      <span>${formatBytes(item.size_bytes)}</span>
    </label>`;
  }).join("");
  $$('input[data-item-id]', body).forEach((input) => input.addEventListener("change", () => {
    input.checked ? state.selected.add(input.dataset.itemId) : state.selected.delete(input.dataset.itemId);
    updatePrepareButton();
  }));
  $$(".file-advice-link", body).forEach((button) => button.addEventListener("click", (event) => {
    event.preventDefault();
    openFileAdvice(button.dataset.adviceId);
  }));
  updatePrepareButton();
}

function renderRegistryAudit() {
  const audit = state.registryAudit;
  const body = $("#registry-results-body");
  if (!audit || audit.status !== "completed") {
    $("#registry-state").textContent = audit?.status === "failed" ? "Mislukt" : "Niet beschikbaar";
    $("#registry-message").textContent = audit?.error || "Voer de scan uit binnen Home Assistant.";
    body.innerHTML = '<div class="table-empty">Geen registergegevens beschikbaar.</div>';
    $("#bundle-list").innerHTML = '<div class="table-empty panel">Geen bundelgegevens beschikbaar.</div>';
    return;
  }

  const summary = audit.summary || {};
  $("#registry-state").textContent = "Voltooid";
  $("#registry-message").textContent = `${summary.entities_total || 0} geregistreerde entities, ${summary.state_only_entities || 0} runtime-only states en ${summary.devices_total || 0} apparaten read-only gecontroleerd. ${summary.long_unavailable_entities || 0} langdurig onbeschikbaar; ${summary.temporarily_unavailable_entities || 0} voorlopig alleen informatief.`;
  $("#registry-entities-total").textContent = summary.entities_total || 0;
  $("#registry-unlinked-total").textContent = summary.bundles_total || 0;
  $("#registry-review-total").textContent = summary.anomalies_total || 0;
  $("#registry-unavailable-total").textContent = summary.unavailable_states || 0;

  renderBundles();
  const allFindings = audit.findings || [];
  const reviewFindings = allFindings.filter((item) => item.severity === "review");
  const informationalFindings = allFindings.filter((item) => item.severity !== "review").slice(0, 250);
  const findings = [...reviewFindings, ...informationalFindings];
  if (!findings.length) {
    body.innerHTML = '<div class="table-empty">Geen registerbevindingen binnen dit filter.</div>';
    return;
  }
  const limitedNotice = findings.length < allFindings.length
    ? `<div class="registry-limit">${allFindings.length - findings.length} aanvullende informatieve regels staan volledig in het downloadbare rapport.</div>`
    : "";
  body.innerHTML = limitedNotice + findings.map((item) => `<div class="registry-row">
    <span class="result-path"><strong>${escapeHtml(item.name || item.subject_id)}</strong><small title="${escapeHtml(item.subject_id)}">${escapeHtml(item.subject_type)} · ${escapeHtml(item.subject_id)}</small></span>
    <span>${escapeHtml(registryCategoryLabel(item.category))}</span>
    <span class="risk-chip ${item.severity}">${item.severity === "review" ? "Beoordeling" : "Informatief"}</span>
    <span class="registry-reason">${escapeHtml(item.reason)}</span>
  </div>`).join("");
}

function entityStatusLabel(status) {
  return {
    available: "Beschikbaar",
    temporarily_unavailable: "Tijdelijk onbeschikbaar",
    long_unavailable: "Langdurig onbeschikbaar",
    temporarily_unknown: "Tijdelijk onbekend",
    long_unknown: "Langdurig onbekend",
    temporarily_problem: "Tijdelijke probleemstatus",
    long_problem: "Langdurige probleemstatus",
    not_loaded: "Niet geladen",
    broken_reference: "Kapotte verwijzing",
    disabled_by_user: "Uitgeschakeld door gebruiker",
    disabled_by_integration: "Standaard uitgeschakeld door integratie",
    disabled_by_config_entry: "Uitgeschakeld via config-entry",
  }[status] || status;
}

function entityDurationLabel(item) {
  if (item.status === "broken_reference") return "Direct aangetoond";
  if (!item.watch && !item.attention) return "Niet van toepassing";
  if ((item.observations || 0) <= 1 && (item.duration_seconds || 0) <= 0) return "Eerste meting";
  if ((item.duration_seconds || 0) < 3600) return "< 1 uur gevolgd";
  if ((item.duration_seconds || 0) < 86400) return `${Math.max(1, Math.floor((item.duration_seconds || 0) / 3600))} uur gevolgd`;
  return `${item.duration_days || 0} dagen`;
}

function entityDiffLabel(value) {
  return {
    baseline: "nulmeting",
    new: "nieuw",
    changed: "gewijzigd",
    recovered: "hersteld",
    unchanged: "ongewijzigd",
  }[value] || value || "geen vergelijking";
}

function entityStatusBreakdown(items) {
  const counts = items.reduce((result, item) => {
    const key = String(item.status || "");
    result[key] = (result[key] || 0) + 1;
    return result;
  }, {});
  const matching = (part) => Object.entries(counts)
    .filter(([key]) => key.includes(part))
    .reduce((sum, [, count]) => sum + count, 0);
  const unavailable = matching("unavailable");
  const unknown = matching("unknown");
  const problem = matching("problem");
  const other = items.length - unavailable - unknown - problem;
  return [
    unavailable ? `<span class="signal-pill unavailable">${unavailable} unavailable</span>` : "",
    unknown ? `<span class="signal-pill unknown">${unknown} unknown</span>` : "",
    problem ? `<span class="signal-pill problem">${problem} problem</span>` : "",
    other ? `<span class="signal-pill other">${other} overig</span>` : "",
  ].filter(Boolean).join("");
}

function renderEntityChanges(changes) {
  const target = $("#entity-change-summary");
  if (!target) return;
  if (changes.baseline) {
    target.textContent = "Deze scan is de nulmeting. Vanaf de volgende scan worden nieuw, hersteld en gewijzigd apart getoond.";
    return;
  }
  const counts = changes.counts || {};
  target.textContent = `${counts.new || 0} nieuw · ${counts.changed || 0} gewijzigd · ${counts.recovered || 0} hersteld · ${counts.removed || 0} verdwenen`;
}

function populateEntityFilters() {
  const items = state.registryAudit?.entity_workspace?.items || [];
  const integration = $("#entity-integration-filter");
  const area = $("#entity-area-filter");
  const currentIntegration = integration.value;
  const currentArea = area.value;
  const integrations = [...new Set(items.map((item) => item.integration).filter(Boolean))].sort();
  const areas = [...new Set(items.map((item) => item.area_name || item.area_id).filter(Boolean))].sort();
  integration.innerHTML = '<option value="all">Alle integraties</option>' + integrations.map((value) => `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`).join("");
  area.innerHTML = '<option value="all">Alle ruimtes</option>' + areas.map((value) => `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`).join("");
  if (integrations.includes(currentIntegration)) integration.value = currentIntegration;
  if (areas.includes(currentArea)) area.value = currentArea;
}

function filteredEntities() {
  const workspace = state.registryAudit?.entity_workspace;
  if (!workspace) return [];
  const query = $("#entity-search").value.trim().toLowerCase();
  const statusFilter = $("#entity-status-filter").value;
  const integration = $("#entity-integration-filter").value;
  const area = $("#entity-area-filter").value;
  const days = Math.max(0, Number($("#entity-days-filter").value) || 0);
  return (workspace.items || []).filter((item) => {
    const status = String(item.status);
    if (statusFilter === "problems" && ((!item.attention && !item.watch) || item.muted_by_decision)) return false;
    if (statusFilter === "attention" && !item.attention) return false;
    if (statusFilter === "watch" && !item.watch) return false;
    if (statusFilter === "muted" && !item.muted_by_decision) return false;
    if (statusFilter === "unavailable" && !status.includes("unavailable")) return false;
    if (statusFilter === "unknown" && !status.includes("unknown")) return false;
    if (statusFilter === "disabled" && !status.startsWith("disabled_by_")) return false;
    if (statusFilter === "state_only" && item.registry_entry !== false) return false;
    if (statusFilter === "problem" && !status.includes("problem")) return false;
    if (!["all", "problems", "attention", "watch", "muted", "unavailable", "unknown", "problem", "disabled", "state_only"].includes(statusFilter) && status !== statusFilter) return false;
    if (integration !== "all" && item.integration !== integration) return false;
    if (area !== "all" && (item.area_name || item.area_id) !== area) return false;
    if ((item.duration_days || 0) < days) return false;
    if (!query) return true;
    return [item.entity_id, item.name, item.device_name, item.device_id, item.integration, item.area_name, item.raw_state].join(" ").toLowerCase().includes(query);
  });
}

function entityGroupKey(item, mode) {
  if (mode === "integration") return item.integration || "Geen integratie";
  if (mode === "status") return entityStatusLabel(item.status);
  if (mode === "none") return "Alle resultaten";
  return item.device_name || (item.device_id ? item.device_id : "Zonder apparaat");
}

function renderEntities() {
  const workspace = state.registryAudit?.entity_workspace;
  const list = $("#entity-list");
  if (!workspace) {
    list.innerHTML = '<div class="table-empty panel">Voer eerst een scan uit.</div>';
    return;
  }
  $("#entity-registered").textContent = workspace.summary?.registered_total || 0;
  $("#entity-state-only").textContent = workspace.summary?.state_only_total || 0;
  $("#entity-attention").textContent = workspace.summary?.attention_visible ?? workspace.summary?.attention ?? 0;
  $("#entity-disabled").textContent = workspace.summary?.disabled || 0;
  $("#entity-selectable").textContent = workspace.summary?.temporary_visible ?? workspace.summary?.temporary_signals ?? 0;
  const thresholds = workspace.persistence_thresholds || {};
  $("#entity-duration-note").textContent = `De duur gebruikt Home Assistant last_changed wanneer beschikbaar; anders start Hass-Cleaner een eigen meting. Actie nodig volgt na ${thresholds.long_days || 30} dagen, of ${thresholds.repeated_observations || 3} scans verspreid over minimaal ${thresholds.repeated_days || 7} dagen.`;
  renderEntityChanges(workspace.changes || {});
  const items = filteredEntities();
  state.visibleEntityIds = items.filter((item) => item.selectable_for_plan).map((item) => item.entity_id);
  $("#entity-result-summary").textContent = `${items.length} resultaten · ${state.selectedEntities.size} geselecteerd · jij beslist na advies en back-upkeuze`;
  if (!items.length) {
    const temporary = workspace.summary?.temporary_visible ?? workspace.summary?.temporary_signals ?? 0;
    if ($("#entity-status-filter").value === "attention" && temporary) {
      list.innerHTML = `<div class="table-empty panel entity-empty-safe"><strong>Geen entiteiten binnen het huidige aandachtsfilter</strong><p>${temporary} tijdelijke signalen worden gevolgd. Open die groep om zelf entities te selecteren en de risico's te beoordelen.</p><button class="button button-ghost" id="entity-show-watch">Tijdelijke signalen gegroepeerd bekijken</button></div>`;
      $("#entity-show-watch").addEventListener("click", () => {
        $("#entity-status-filter").value = "watch";
        $("#entity-group-filter").value = "integration";
        renderEntities();
      });
    } else {
      list.innerHTML = '<div class="table-empty panel">Geen entiteiten binnen deze filters.</div>';
    }
    updateEntityButtons();
    return;
  }
  const mode = $("#entity-group-filter").value;
  const groups = new Map();
  items.forEach((item) => {
    const key = entityGroupKey(item, mode);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(item);
  });
  list.innerHTML = [...groups.entries()].map(([title, members]) => {
    const selectable = members.filter((item) => item.selectable_for_plan);
    const allSelected = selectable.length && selectable.every((item) => state.selectedEntities.has(item.entity_id));
    const attention = members.filter((item) => item.attention).length;
    const temporary = members.filter((item) => item.watch).length;
    const open = state.entityGroupOpen.has(title)
      ? state.entityGroupOpen.get(title)
      : attention > 0 || mode === "none";
    const maxDuration = members.reduce((maximum, item) => Math.max(maximum, Number(item.duration_seconds) || 0), 0);
    const maxObservations = members.reduce((maximum, item) => Math.max(maximum, Number(item.observations) || 0), 0);
    const evidenceItem = {...members[0], duration_seconds: maxDuration, observations: maxObservations};
    const rows = members.map((item) => `<label class="entity-row">
      <input type="checkbox" data-entity-id="${escapeHtml(item.entity_id)}" ${item.selectable_for_plan ? "" : "disabled"} ${state.selectedEntities.has(item.entity_id) ? "checked" : ""}>
      <button type="button" class="entity-detail" data-entity-detail="${escapeHtml(item.entity_id)}"><strong>${escapeHtml(item.name || item.entity_id)}</strong><small>${escapeHtml(item.entity_id)}</small></button>
      <span><strong>${escapeHtml(item.device_name || "Zonder apparaat")}</strong><small>${escapeHtml(item.integration || "Onbekende integratie")}${item.area_name ? ` · ${escapeHtml(item.area_name)}` : ""}</small></span>
      <span class="risk-chip ${item.attention ? "review" : "info"}">${escapeHtml(entityStatusLabel(item.status))}<small>${item.registry_entry === false ? "runtime-only" : item.muted_by_decision ? "lokaal gedempt" : ""}</small></span>
      <span class="entity-duration">${escapeHtml(entityDurationLabel(item))}<small>${item.observations || 0} meting(en) · ${escapeHtml(entityDiffLabel(item.diff_status))}</small></span>
    </label>`).join("");
    const groupAction = selectable.length
      ? `<button class="link-button entity-group-toggle" data-group="${escapeHtml(title)}">${allSelected ? "Groep wissen" : "Groep selecteren"}</button>`
      : '<span class="signal-note">Alleen volgen</span>';
    return `<details class="panel entity-group" data-entity-group="${escapeHtml(title)}" ${open ? "open" : ""}><summary><div class="entity-group-title"><span class="entity-group-caret">›</span><div><h3>${escapeHtml(title)}</h3><p>${members.length} entiteiten · ${attention} actie nodig · ${temporary} tijdelijk · maximaal ${escapeHtml(entityDurationLabel(evidenceItem))} / ${maxObservations} meting(en)</p></div></div><div class="entity-group-summary">${entityStatusBreakdown(members)}${groupAction}</div></summary><div class="entity-group-rows">${rows}</div></details>`;
  }).join("");
  $$("details.entity-group", list).forEach((details) => details.addEventListener("toggle", () => {
    state.entityGroupOpen.set(details.dataset.entityGroup, details.open);
  }));
  $$('input[data-entity-id]', list).forEach((input) => input.addEventListener("change", () => {
    input.checked ? state.selectedEntities.add(input.dataset.entityId) : state.selectedEntities.delete(input.dataset.entityId);
    renderEntities();
  }));
  $$(".entity-group-toggle", list).forEach((button) => button.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    const members = items.filter((item) => entityGroupKey(item, mode) === button.dataset.group && item.selectable_for_plan);
    const allSelected = members.every((item) => state.selectedEntities.has(item.entity_id));
    members.forEach((item) => allSelected ? state.selectedEntities.delete(item.entity_id) : state.selectedEntities.add(item.entity_id));
    renderEntities();
  }));
  $$(".entity-detail", list).forEach((button) => button.addEventListener("click", () => openEntity(button.dataset.entityDetail)));
  updateEntityButtons();
}

function updateEntityButtons() {
  $("#entity-select-visible").disabled = !state.visibleEntityIds.length;
  $("#entity-plan-button").disabled = !state.selectedEntities.size;
  $("#entity-plan-button").textContent = state.selectedEntities.size ? `Opruimplan bekijken (${state.selectedEntities.size})` : "Opruimplan bekijken";
}

async function openEntity(entityId) {
  const item = (state.registryAudit?.entity_workspace?.items || []).find((candidate) => candidate.entity_id === entityId);
  if (!item) return;
  state.activeEntity = item;
  $("#entity-dialog-title").textContent = item.name || item.entity_id;
  $("#entity-dialog-summary").textContent = `${item.entity_id} · ${entityStatusLabel(item.status)} · ${entityDurationLabel(item)}${item.registry_entry === false ? " · runtime-only" : ""}`;
  const signals = Object.keys(item.connectivity_signals || {}).length ? escapeHtml(JSON.stringify(item.connectivity_signals)) : "Geen integratiespecifieke signalen";
  $("#entity-dialog-content").innerHTML = `<section class="advice-section"><h3>Beoordeling</h3><p>${escapeHtml(item.reason)}</p><p><strong>Nog nodig:</strong> ${escapeHtml(item.evidence_needed || "Controleer duur, herhaalde metingen en officiële relaties.")}</p><p>Lokale keuze: <strong>${escapeHtml(item.decision || "follow")}</strong>${item.decision_until ? ` tot ${escapeHtml(new Date(item.decision_until).toLocaleString("nl-NL"))}` : ""}</p></section><section class="advice-grid"><div><h3>Herkomst</h3><ul><li>Entityregister: ${item.registry_entry === false ? "geen item (runtime-only)" : "aanwezig"}</li><li>Integratie: ${escapeHtml(item.integration || "onbekend")}</li><li>Apparaat: ${escapeHtml(item.device_name || "niet gekoppeld")}</li><li>Ruimte: ${escapeHtml(item.area_name || "niet ingesteld")}</li><li>Uitgeschakeld door: ${escapeHtml(item.disabled_by || "niemand")}</li></ul></div><div><h3>Waarneming</h3><ul><li>Home Assistant-state: ${escapeHtml(item.raw_state ?? "geen")}</li><li>HA meldt sinds: ${escapeHtml(item.last_changed ? new Date(item.last_changed).toLocaleString("nl-NL") : "onbekend")}</li><li>Hass-Cleaner meet sinds: ${escapeHtml(item.first_observed ? new Date(item.first_observed).toLocaleString("nl-NL") : "eerste meting")}</li><li>Duurbron: ${item.duration_source === "home_assistant" ? "Home Assistant last_changed" : "opeenvolgende Hass-Cleaner-scans"}</li><li>Opeenvolgende metingen: ${item.observations || 0}</li><li>Signalen: ${signals}</li></ul></div></section><section class="advice-section" id="entity-related"><h3>Officiële relaties</h3><p>Relaties ophalen...</p></section>`;
  $("#entity-dialog").showModal();
  try {
    const response = await api("api/related", { method: "POST", body: JSON.stringify({ item_type: "entity", item_id: entityId }) });
    const groups = Object.entries(response.related || {}).filter(([, ids]) => ids.length);
    $("#entity-related").innerHTML = `<h3>Officiële relaties</h3>${groups.length ? `<ul>${groups.map(([type, ids]) => `<li>${escapeHtml(type)}: ${escapeHtml(ids.slice(0, 12).join(", "))}${ids.length > 12 ? " …" : ""}</li>`).join("")}</ul>` : "<p>Geen relaties gevonden. Dat is nog geen verwijderbewijs.</p>"}`;
  } catch (error) {
    $("#entity-related").innerHTML = `<h3>Officiële relaties</h3><p>Niet beschikbaar: ${escapeHtml(error.message)}</p>`;
  }
}

async function saveEntityDecision(action) {
  if (!state.activeEntity) return;
  try {
    const result = await api("api/entity-decisions", {method: "POST", body: JSON.stringify({entity_id: state.activeEntity.entity_id, action})});
    state.activeEntity.decision = action;
    state.activeEntity.muted_by_decision = action === "expected" || action.startsWith("snooze_");
    if (result.summary) state.scan.registry_audit.entity_workspace.summary = result.summary;
    $("#entity-dialog").close();
    renderEntities();
    showToast("Lokale entitykeuze opgeslagen; Home Assistant is niet gewijzigd");
  } catch (error) {
    showToast(error.message, true);
  }
}

async function createEntityPlan() {
  try {
    const response = await api("api/plans/preview", { method: "POST", body: JSON.stringify({ selected_entity_ids: [...state.selectedEntities] }) });
    showPlan(response);
  } catch (error) {
    showToast(error.message, true);
  }
}

function renderBundles() {
  const list = $("#bundle-list");
  const filter = $("#registry-severity-filter").value;
  const query = $("#bundle-search").value.trim().toLowerCase();
  const anomalies = state.registryAudit?.anomalies || [];
  const anomalyByBundle = new Map(anomalies.map((item) => [item.bundle_id, item]));
  const bundles = (state.registryAudit?.bundles || []).filter((bundle) => {
    if (filter === "attention" && !anomalyByBundle.has(bundle.id)) return false;
    if (filter === "review" && !bundle.review_count) return false;
    if (filter === "devices" && !bundle.devices.length) return false;
    if (filter === "entities" && !bundle.entities.length) return false;
    if (!query) return true;
    const haystack = [bundle.title, bundle.domain, ...bundle.devices.map((item) => item.name), ...bundle.entities.map((item) => item.entity_id)].join(" ").toLowerCase();
    return haystack.includes(query);
  });
  if (!bundles.length) {
    list.innerHTML = '<div class="table-empty panel">Geen concrete aandachtspunten gevonden. Gezonde bundels staan onder “Alle bundels”.</div>';
    return;
  }
  list.innerHTML = bundles.map((bundle) => {
    const anomaly = anomalyByBundle.get(bundle.id);
    const devicePreview = bundle.devices.slice(0, 3).map((item) => `<span>${escapeHtml(item.name)}</span>`).join("");
    const warning = anomaly
      ? `<span class="risk-chip review">Eigen beoordeling</span>`
      : bundle.review_count
      ? `<span class="risk-chip review">${bundle.review_count} beoordelen</span>`
      : `<span class="risk-chip info">Eigen beoordeling</span>`;
    return `<article class="panel bundle-card">
      <div class="bundle-main">
        <div class="bundle-icon">${escapeHtml((bundle.domain || "?").slice(0, 2).toUpperCase())}</div>
        <div class="bundle-copy"><div class="eyebrow">${escapeHtml(bundle.domain || "ONBEKEND")} · ${escapeHtml(bundle.state)}</div><h3>${escapeHtml(bundle.title)}</h3><p>${bundle.devices.length} apparaten · ${bundle.entities.length} entities</p>${anomaly ? `<p class="bundle-anomaly">${escapeHtml(anomaly.summary)}</p><p class="bundle-evidence">Bewijs: ${escapeHtml(anomaly.evidence_summary || "aanvullende controle vereist")}</p>` : ""}<div class="device-preview">${devicePreview}${bundle.devices.length > 3 ? `<span>+${bundle.devices.length - 3}</span>` : ""}</div></div>
      </div>
      <div class="bundle-actions">${warning}<button class="button button-primary bundle-review" data-bundle-id="${escapeHtml(bundle.id)}">Bundel beoordelen</button></div>
    </article>`;
  }).join("");
  $$(".bundle-review", list).forEach((button) => button.addEventListener("click", () => openBundle(button.dataset.bundleId)));
}

async function openBundle(bundleId) {
  const bundle = (state.registryAudit?.bundles || []).find((item) => item.id === bundleId);
  if (!bundle) return;
  const anomaly = (state.registryAudit?.anomalies || []).find((item) => item.bundle_id === bundleId);
  state.activeBundle = bundle;
  $("#bundle-dialog-title").textContent = bundle.title;
  $("#bundle-dialog-summary").textContent = `${bundle.devices.length} apparaten en ${bundle.entities.length} entities. ${anomaly ? "1 registerafwijking voor eigen beoordeling." : `${bundle.review_count} waarschuwingen.`}`;
  const generalAdvice = renderAdvice(bundle.advice || {});
  $("#bundle-advice").innerHTML = anomaly
    ? `${renderAnomalyAdvice(anomaly)}<details class="general-bundle-advice"><summary>Algemene bundelanalyse tonen</summary>${generalAdvice}</details>`
    : generalAdvice;
  const related = $("#bundle-related");
  related.innerHTML = renderLocalBundleDetails(bundle);
  $("#bundle-dialog").showModal();
  if (!bundle.config_entry_id) return;
  related.insertAdjacentHTML("afterbegin", '<div class="related-loading">Officiële Home Assistant-relaties ophalen...</div>');
  try {
    const response = await api("api/related", { method: "POST", body: JSON.stringify({ item_type: "config_entry", item_id: bundle.config_entry_id }) });
    const groups = Object.entries(response.related || {}).filter(([, ids]) => ids.length);
    const graph = groups.length
      ? groups.map(([type, ids]) => `<div class="related-group"><strong>${escapeHtml(type)}</strong><span>${ids.length}</span><small>${escapeHtml(ids.slice(0, 8).join(", "))}${ids.length > 8 ? " ..." : ""}</small></div>`).join("")
      : '<div class="related-loading">Geen extra relaties gevonden.</div>';
    related.innerHTML = graph + renderLocalBundleDetails(bundle);
  } catch (error) {
    related.querySelector(".related-loading").textContent = `Relatiezoekactie niet beschikbaar: ${error.message}`;
  }
}

function renderAnomalyAdvice(anomaly) {
  const consequences = (anomaly.possible_consequences || []).map((value) => `<li>${escapeHtml(value)}</li>`).join("") || "<li>Gevolgen zijn nog niet volledig vastgesteld.</li>";
  const recovery = (anomaly.recovery_steps || []).map((value) => `<li>${escapeHtml(value)}</li>`).join("") || "<li>Maak eerst een volledige Home Assistant-back-up.</li>";
  const samples = [...(anomaly.sample_device_ids || []), ...(anomaly.sample_entity_ids || [])];
  return `<section class="anomaly-advice"><div class="evidence-banner insufficient"><span>Registerafwijking</span><strong>Beoordeel zelf</strong></div><section class="advice-section"><h3>${escapeHtml(anomaly.title || "Registerafwijking")}</h3><p>${escapeHtml(anomaly.summary || "")}</p><p><strong>Waarneming:</strong> ${escapeHtml(anomaly.evidence_summary || "Aanvullende controle vereist.")}</p><p><strong>Advies:</strong> ${escapeHtml(anomaly.evidence_needed || "Controleer de officiële relaties en het actuele gebruik.")}</p><p><strong>Risico:</strong> ${escapeHtml(anomaly.risk_summary || "Wijzigen kan onverwachte gevolgen hebben.")}</p></section>${samples.length ? `<section class="advice-section"><h3>Voorbeelden uit het register</h3><code class="sample-identifiers">${escapeHtml(samples.join(" · "))}</code></section>` : ""}<section class="advice-grid"><div><h3>Wat kan er gebeuren?</h3><ul>${consequences}</ul></div><div><h3>Hoe herstel je dit?</h3><ul>${recovery}</ul></div></section><section class="advice-section first-step"><h3>Aanbevolen controle</h3><p>${escapeHtml(anomaly.recommended_first_step || "Controleer dit voor uitvoering.")}</p></section></section>`;
}

function renderLocalBundleDetails(bundle) {
  const visibleDevices = bundle.devices.slice(0, MAX_BUNDLE_DEVICE_DETAILS);
  const devices = bundle.devices.length
    ? visibleDevices.map((device) => `<li><strong>${escapeHtml(device.name)}</strong><small>${device.entity_ids.length} entities${device.child_device_ids.length ? ` · ${device.child_device_ids.length} onderliggende apparaten` : ""}</small></li>`).join("")
    : "<li>Geen apparaten in deze bundel</li>";
  const omittedDevices = Math.max(0, bundle.devices.length - visibleDevices.length);
  const loose = bundle.entities.filter((entity) => !entity.device_id);
  const availability = bundle.entities.filter((entity) => entity.availability_status && entity.availability_status !== "available");
  return `<details class="bundle-details" open><summary>Apparaten (${bundle.devices.length})</summary><ul>${devices}${omittedDevices ? `<li class="bundle-omitted"><strong>Nog ${omittedDevices} apparaten</strong><small>De volledige inventaris staat in JSON en CSV; de interface begrenst deze lijst voor snelheid.</small></li>` : ""}</ul></details>
    <details class="bundle-details"><summary>Losse entities (${loose.length})</summary><ul>${loose.slice(0, 100).map((entity) => `<li><strong>${escapeHtml(entity.name)}</strong><small>${escapeHtml(entity.entity_id)}</small></li>`).join("") || "<li>Geen losse entities</li>"}</ul></details>
    <details class="bundle-details"><summary>Beschikbaarheid (${availability.length})</summary><ul>${availability.slice(0, 100).map((entity) => `<li><strong>${escapeHtml(entity.name)}</strong><small>${escapeHtml(entity.entity_id)} · ${escapeHtml(availabilityLabel(entity.availability_status))}${entity.health_duration_days !== undefined ? ` · ${entity.health_duration_days} dagen` : ""}</small></li>`).join("") || "<li>Geen beschikbaarheidsproblemen</li>"}</ul></details>`;
}

function availabilityLabel(status) {
  if (status === "temporarily_unavailable") return "tijdelijk onbeschikbaar";
  if (status === "long_unavailable") return "langdurig onbeschikbaar";
  if (status === "temporarily_unknown") return "tijdelijk onbekend";
  if (status === "long_unknown") return "langdurig onbekend";
  if (status === "temporarily_problem") return "tijdelijke probleemstatus";
  if (status === "long_problem") return "langdurige probleemstatus";
  if (status === "not_loaded") return "niet geladen";
  if (String(status).startsWith("disabled_by_")) return `uitgeschakeld door ${String(status).slice(12)}`;
  return status;
}

async function addBundleToPlan() {
  if (!state.activeBundle) return;
  try {
    const plan = await api("api/plans/preview", { method: "POST", body: JSON.stringify({ selected_bundle_ids: [state.activeBundle.id] }) });
    $("#bundle-dialog").close();
    showPlan(plan);
  } catch (error) {
    showToast(error.message, true);
  }
}

function openFileAdvice(itemId) {
  const item = state.items.find((candidate) => candidate.id === itemId);
  if (!item) return;
  $("#file-advice-title").textContent = item.path.split("/").pop();
  $("#file-advice-path").textContent = item.path;
  $("#file-advice-content").innerHTML = renderAdvice(item.advice || {});
  $("#file-advice-dialog").showModal();
}

function renderAdvice(advice) {
  const consequences = (advice.possible_consequences || []).map((value) => `<li>${escapeHtml(value)}</li>`).join("") || "<li>Geen gevolgadvies beschikbaar.</li>";
  const recovery = (advice.recovery_steps || []).map((value) => `<li>${escapeHtml(value)}</li>`).join("") || "<li>Hersteladvies ontbreekt; niet uitvoeren.</li>";
  const preview = advice.content_preview || {};
  return `<div class="evidence-banner ${escapeHtml(advice.evidence_level || "insufficient")}"><span>Risico-indicatie</span><strong>${escapeHtml(advice.evidence_label || "Eigen beoordeling")}</strong></div>
    <section class="advice-section"><h3>Wat is dit?</h3><p>${escapeHtml(advice.summary || "Geen beschrijving beschikbaar.")}</p></section>
    <section class="advice-section"><h3>Veilige inhoudspreview</h3><pre>${escapeHtml(JSON.stringify(preview, null, 2))}</pre><small>Waarden die gevoelig kunnen zijn worden niet opgenomen.</small></section>
    <section class="advice-grid"><div><h3>Wat kan er gebeuren?</h3><ul>${consequences}</ul></div><div><h3>Hoe herstel je dit?</h3><ul>${recovery}</ul></div></section>
    <section class="advice-section first-step"><h3>Aanbevolen eerste stap</h3><p>${escapeHtml(advice.recommended_first_step || "Niet wijzigen zonder aanvullende controle.")}</p></section>`;
}

function showPlan(response) {
  state.latestPlan = response;
  const summary = response.plan?.summary || {};
  $("#plan-dialog-summary").textContent = `${summary.file_count || 0} bestanden, ${summary.bundle_count || 0} bundels en ${summary.entity_count || 0} entiteiten vastgelegd. Uitvoerbare acties: ${summary.executable_actions || 0}.`;
  const hasFiles = Number(summary.file_count || 0) > 0;
  const registryCount = Number(summary.entity_count || 0) + Number(summary.device_count || 0);
  $("#open-quarantine-execution").classList.toggle("hidden", !hasFiles);
  $("#open-quarantine-execution").disabled = !(hasFiles && state.status?.quarantine_enabled);
  $("#open-registry-execution").classList.toggle("hidden", !registryCount);
  $("#open-registry-execution").disabled = !registryCount;
  $("#plan-execution-title").textContent = hasFiles && registryCount ? "Bestands- en registeracties beschikbaar" : hasFiles ? "Bestandsquarantaine beschikbaar" : "Registeropschoning beschikbaar";
  $("#plan-execution-note").textContent = hasFiles
    ? "Een back-up is sterk aanbevolen. Ieder bestand wordt vlak vóór verplaatsing opnieuw gecontroleerd."
    : "Entities en apparaten zijn registerobjecten. De gebruiker kan ze na advies, back-upkeuze en zware bevestiging verwijderen.";
  $("#plan-dialog").showModal();
  showToast(response.message || "Veilig opruimplan opgeslagen");
}

function openQuarantineExecution() {
  $("#quarantine-confirmation").value = "";
  $("#quarantine-risk-ack").checked = false;
  const hasReview = (state.latestPlan?.plan?.files || []).some((item) => item.risk === "review");
  $("#quarantine-content-risk-row").classList.toggle("hidden", !hasReview);
  $("#quarantine-content-risk-ack").checked = !hasReview;
  $('input[name="quarantine-backup-choice"][value="verified"]').checked = true;
  renderBackupEvidence();
  updateQuarantineChoice();
  $("#plan-dialog").close();
  $("#quarantine-dialog").showModal();
}

function renderBackupEvidence() {
  if (state.backupVerified) {
    $("#quarantine-backup-status").textContent = "Recente back-up is voltooid en geverifieerd; je hoeft geen nieuwe te maken.";
  } else if (state.backupEvidenceToken) {
    $("#quarantine-backup-status").textContent = "Er is een recente back-upaanvraag. Controleer de status; opnieuw aanmaken is niet nodig.";
  } else {
    $("#quarantine-backup-status").textContent = "Nog geen recente back-upaanvraag gevonden. Een back-up is sterk aanbevolen.";
  }
  $("#quarantine-verify-button").disabled = !state.backupEvidenceToken || state.backupVerified;
}

async function loadBackupEvidence() {
  try {
    const response = await api("api/backups/evidence");
    const recent = (response.items || []).find((item) => {
      const age = Date.now() - new Date(item.requested_at).getTime();
      return age >= 0 && age <= 24 * 60 * 60 * 1000 && ["accepted", "running", "completed"].includes(item.status);
    });
    if (recent) {
      state.backupEvidenceToken = recent.token || "";
      state.backupVerified = recent.status === "completed";
    }
    renderBackupEvidence();
  } catch (_) {
    // Evidence is optional and must not block the interface.
  }
}

async function startQuarantineBackup() {
  const button = $("#quarantine-backup-button");
  button.disabled = true;
  try {
    const response = await api("api/backups", { method: "POST", body: "{}" });
    state.backupEvidenceToken = response.evidence?.token || "";
    state.backupVerified = false;
    renderBackupEvidence();
  } catch (error) {
    showToast(error.message, true);
  } finally {
    button.disabled = false;
  }
}

async function verifyQuarantineBackup() {
  try {
    const response = await api(`api/backups/${state.backupEvidenceToken}/verify`, { method: "POST", body: "{}" });
    state.backupVerified = response.status === "completed";
    const evidence = response.evidence || {};
    $("#quarantine-backup-status").textContent = state.backupVerified
      ? `Back-up voltooid en geverifieerd${evidence.backup_name ? `: ${evidence.backup_name}` : ""}.`
      : `Back-upstatus: ${response.status || "onbekend"}${evidence.job_progress ? ` (${evidence.job_progress}%)` : ""}.`;
    updateQuarantineExecuteButton();
  } catch (error) {
    showToast(error.message, true);
  }
}

function updateQuarantineExecuteButton() {
  const choice = $('input[name="quarantine-backup-choice"]:checked').value;
  const backupAccepted = choice === "verified" ? state.backupVerified : $("#quarantine-risk-ack").checked;
  const contentAccepted = $("#quarantine-content-risk-ack").checked;
  $("#confirm-quarantine").disabled = !(backupAccepted && contentAccepted && $("#quarantine-confirmation").value === "QUARANTAINE");
}

function updateQuarantineChoice() {
  const choice = $('input[name="quarantine-backup-choice"]:checked').value;
  const manual = choice !== "verified";
  $("#quarantine-risk-row").classList.toggle("hidden", !manual);
  $("#quarantine-risk-text").textContent = choice === "manual"
    ? "Ik bevestig dat ik zelf een recente, voltooide en bruikbare back-up in Home Assistant heb gecontroleerd."
    : "Ik begrijp dat ik zonder volledige Home Assistant-back-up doorga en accepteer het extra herstelrisico.";
  updateQuarantineExecuteButton();
}

async function executeQuarantine() {
  const button = $("#confirm-quarantine");
  button.disabled = true;
  try {
    const response = await api("api/quarantine", { method: "POST", body: JSON.stringify({
      plan_id: state.latestPlan?.plan?.id,
      backup_evidence_token: state.backupEvidenceToken,
      backup_choice: $('input[name="quarantine-backup-choice"]:checked').value,
      risk_acknowledged: $("#quarantine-risk-ack").checked,
      content_risk_acknowledged: $("#quarantine-content-risk-ack").checked,
      confirmation: $("#quarantine-confirmation").value,
    }) });
    $("#quarantine-dialog").close();
    state.selected.clear();
    showToast(`${response.operation?.files?.length || 0} bestanden veilig naar quarantaine verplaatst`);
    activateTab("quarantine");
  } catch (error) {
    showToast(error.message, true);
  } finally {
    updateQuarantineExecuteButton();
  }
}

function openRegistryExecution() {
  const summary = state.latestPlan?.plan?.summary || {};
  const total = Number(summary.entity_count || 0) + Number(summary.device_count || 0);
  $("#registry-execution-summary").textContent = `${summary.entity_count || 0} entiteiten en ${summary.device_count || 0} apparaten worden definitief uit hun Home Assistant-registerrelatie verwijderd.`;
  $("#registry-confirmation-label").innerHTML = `Typ <strong>VERWIJDER ${total}</strong> ter bevestiging`;
  $("#registry-confirmation").value = "";
  $("#registry-risk-ack").checked = false;
  $('input[name="registry-backup-choice"][value="verified"]').checked = true;
  updateRegistryExecuteButton();
  $("#plan-dialog").close();
  $("#registry-execution-dialog").showModal();
}

function updateRegistryExecuteButton() {
  const summary = state.latestPlan?.plan?.summary || {};
  const total = Number(summary.entity_count || 0) + Number(summary.device_count || 0);
  const choice = $('input[name="registry-backup-choice"]:checked').value;
  const backupAccepted = choice === "verified" ? state.backupVerified : true;
  $("#confirm-registry-cleanup").disabled = !(backupAccepted && $("#registry-risk-ack").checked && $("#registry-confirmation").value === `VERWIJDER ${total}`);
}

async function startRegistryBackup() {
  try {
    const response = await api("api/backups", { method: "POST", body: "{}" });
    state.backupEvidenceToken = response.evidence?.token || "";
    state.backupVerified = false;
    showToast("Back-up gestart; controleer de status zodra Home Assistant klaar is");
  } catch (error) { showToast(error.message, true); }
  updateRegistryExecuteButton();
}

async function verifyRegistryBackup() {
  try {
    const response = await api(`api/backups/${state.backupEvidenceToken}/verify`, { method: "POST", body: "{}" });
    state.backupVerified = response.status === "completed";
    showToast(state.backupVerified ? "Back-up voltooid en geverifieerd" : `Back-upstatus: ${response.status}`);
  } catch (error) { showToast(error.message, true); }
  updateRegistryExecuteButton();
}

async function executeRegistryCleanup() {
  const button = $("#confirm-registry-cleanup");
  button.disabled = true;
  try {
    const response = await api("api/registry-cleanup", { method: "POST", body: JSON.stringify({
      plan_id: state.latestPlan?.plan?.id,
      backup_evidence_token: state.backupEvidenceToken,
      backup_choice: $('input[name="registry-backup-choice"]:checked').value,
      risk_acknowledged: $("#registry-risk-ack").checked,
      confirmation: $("#registry-confirmation").value,
    }) });
    $("#registry-execution-dialog").close();
    state.selectedEntities.clear();
    showToast(`${response.operation?.completed?.length || 0} registeracties voltooid; start een nieuwe scan`);
  } catch (error) { showToast(error.message, true); }
  updateRegistryExecuteButton();
}

async function loadQuarantine() {
  const target = $("#quarantine-list");
  try {
    const response = await api("api/quarantine");
    const operations = response.items || [];
    const rows = operations.flatMap((operation) => (operation.files || []).map((file) => ({ operation, file })));
    target.innerHTML = rows.length ? rows.map(({ operation, file }) => {
      const expired = new Date(operation.expires_at).getTime() <= Date.now();
      return `<div class="history-row"><span class="risk-chip ${file.status === "quarantined" ? (expired ? "review" : "safe") : "info"}">${escapeHtml(file.status)}</span><div><strong>${escapeHtml(file.original_path)}</strong><small>${formatBytes(file.size_bytes)} · ${expired ? "bewaartermijn verstreken" : `bewaard tot ${new Date(operation.expires_at).toLocaleString("nl-NL")}`} · checksum ${escapeHtml(String(file.sha256 || "").slice(0, 12))}</small></div>${file.status === "quarantined" ? `<button class="button button-ghost quarantine-test" data-operation="${operation.id}" data-file="${file.id}">Hersteltest</button><button class="button button-primary quarantine-restore" data-operation="${operation.id}" data-file="${file.id}">Herstellen</button>${expired ? `<button class="button button-danger quarantine-purge" data-operation="${operation.id}" data-file="${file.id}">Definitief verwijderen</button>` : ""}` : ""}</div>`;
    }).join("") : '<div class="table-empty">Nog geen bestanden in quarantaine.</div>';
    $$(".quarantine-test", target).forEach((button) => button.addEventListener("click", () => testQuarantineRestore(button.dataset.operation, button.dataset.file)));
    $$(".quarantine-restore", target).forEach((button) => button.addEventListener("click", () => restoreQuarantine(button.dataset.operation, button.dataset.file)));
    $$(".quarantine-purge", target).forEach((button) => button.addEventListener("click", () => purgeQuarantine(button.dataset.operation, button.dataset.file)));
  } catch (error) {
    target.innerHTML = `<div class="table-empty">${escapeHtml(error.message)}</div>`;
  }
}

async function testQuarantineRestore(operation, file) {
  try {
    await api(`api/quarantine/${operation}/${file}/test`, { method: "POST", body: "{}" });
    showToast("Hersteltest geslaagd: bestand is leesbaar en checksum klopt");
    await loadQuarantine();
  } catch (error) { showToast(error.message, true); }
}

async function restoreQuarantine(operation, file) {
  if (window.prompt("Typ HERSTEL om dit bestand terug te plaatsen") !== "HERSTEL") return;
  try {
    await api(`api/quarantine/${operation}/${file}/restore`, { method: "POST", body: JSON.stringify({ confirmation: "HERSTEL" }) });
    showToast("Bestand veilig teruggeplaatst");
    await loadQuarantine();
  } catch (error) { showToast(error.message, true); }
}

async function purgeQuarantine(operation, file) {
  if (window.prompt("De bewaartermijn is verstreken. Typ VERWIJDER voor definitieve verwijdering") !== "VERWIJDER") return;
  try {
    await api(`api/quarantine/${operation}/${file}/purge`, { method: "POST", body: JSON.stringify({ confirmation: "VERWIJDER" }) });
    showToast("Verlopen quarantainebestand definitief verwijderd");
    await loadQuarantine();
  } catch (error) { showToast(error.message, true); }
}

function downloadPlan(format) {
  const path = state.latestPlan?.downloads?.[format];
  if (!path) {
    showToast("Maak eerst een impactplan", true);
    return;
  }
  window.location.assign(apiUrl(path));
}

async function loadPurgeHistory() {
  try {
    const response = await api("api/recorder/purges");
    const items = response.items || [];
    $("#purge-history").innerHTML = items.length ? items.map((item) => `<div class="history-row"><span class="risk-chip ${item.status === "accepted" ? "safe" : "review"}">${escapeHtml(item.status)}</span><div><strong>${item.keep_days} dagen bewaard${item.repack ? " · herverpakt" : ""}</strong><small>${new Date(item.requested_at).toLocaleString("nl-NL")}</small></div></div>`).join("") : '<div class="table-empty compact">Nog geen purgeactie uitgevoerd.</div>';
  } catch (error) {
    $("#purge-history").innerHTML = `<div class="table-empty compact">${escapeHtml(error.message)}</div>`;
  }
}

function openPurgeDialog() {
  const keepDays = Number($("#purge-keep-days").value);
  if (!Number.isInteger(keepDays) || keepDays < 1 || keepDays > 365) {
    showToast("Kies 1 tot en met 365 dagen", true);
    return;
  }
  const extras = [$("#purge-repack").checked ? "database herverpakken" : "niet herverpakken", $("#purge-apply-filter").checked ? "filters toepassen" : "filters niet toepassen"];
  $("#purge-dialog-summary").textContent = `Alle Recorder-historie ouder dan ${keepDays} dagen wordt permanent verwijderd; ${extras.join("; ")}.`;
  $("#purge-confirmation").value = "";
  $("#purge-backup-confirmed").checked = false;
  state.backupEvidenceToken = "";
  $("#purge-backup-button").textContent = "Eerst volledige back-up starten";
  $("#purge-dialog").showModal();
}

async function startPurgeBackup() {
  const button = $("#purge-backup-button");
  button.disabled = true;
  try {
    if (state.backupEvidenceToken) {
      const verified = await api(`api/backups/${state.backupEvidenceToken}/verify`, { method: "POST", body: "{}" });
      const complete = verified.status === "completed";
      $("#purge-backup-confirmed").checked = complete;
      button.textContent = complete ? "Back-up voltooid en geverifieerd" : `Back-upstatus controleren (${verified.evidence?.job_progress || 0}%)`;
      showToast(complete ? "Back-up is voltooid en geverifieerd" : "Back-up is nog bezig");
      return;
    }
    const response = await api("api/backups", { method: "POST", body: "{}" });
    state.backupEvidenceToken = response.evidence?.token || "";
    $("#purge-backup-confirmed").checked = false;
    showToast("Back-up gestart. Klik opnieuw om de voltooiing te verifiëren.");
    button.textContent = "Back-upstatus controleren";
  } catch (error) {
    showToast(error.message, true);
  } finally {
    button.disabled = false;
  }
}

async function executePurge() {
  const button = $("#confirm-purge");
  button.disabled = true;
  button.textContent = "Purge aanvragen...";
  try {
    await api("api/recorder/purge", { method: "POST", body: JSON.stringify({
      keep_days: Number($("#purge-keep-days").value),
      repack: $("#purge-repack").checked,
      apply_filter: $("#purge-apply-filter").checked,
      backup_confirmed: $("#purge-backup-confirmed").checked,
      backup_evidence_token: state.backupEvidenceToken,
      confirmation: $("#purge-confirmation").value,
    }) });
    $("#purge-dialog").close();
    showToast("Recorder-purge is door Home Assistant geaccepteerd");
    await loadPurgeHistory();
  } catch (error) {
    showToast(error.message, true);
  } finally {
    button.disabled = false;
    button.textContent = "Recorder-purge uitvoeren";
  }
}

function updatePrepareButton() {
  const button = $("#prepare-button");
  button.disabled = state.selected.size === 0;
  button.textContent = state.selected.size ? `Opruimplan bekijken (${state.selected.size})` : "Opruimplan bekijken";
}

async function loadScanHistory() {
  const target = $("#scan-history");
  if (!target) return;
  try {
    const response = await api("api/scans/history");
    const items = response.items || [];
    target.innerHTML = items.length ? items.map((item) => {
      const changes = item.entity_changes?.counts || {};
      return `<div class="history-row"><span class="risk-chip info">Scan</span><div><strong>${item.visited_files || 0} bestanden · ${item.entity_summary?.attention_visible || 0} actie nodig</strong><small>${new Date(item.finished_at).toLocaleString("nl-NL")} · ${changes.new || 0} nieuw · ${changes.recovered || 0} hersteld · ${changes.changed || 0} gewijzigd</small></div></div>`;
    }).join("") : '<div class="table-empty">Nog geen voltooide scans opgeslagen.</div>';
  } catch (error) {
    target.innerHTML = `<div class="table-empty">${escapeHtml(error.message)}</div>`;
  }
}

async function clearLocalHistory() {
  const confirmation = window.prompt("Typ WIS HISTORIE voor een schone lokale start. Home Assistant zelf wordt niet gewijzigd.");
  if (confirmation !== "WIS HISTORIE") return;
  try {
    await api("api/history/clear", { method: "POST", body: JSON.stringify({ confirmation }) });
    state.scan = null;
    state.plan = null;
    state.selected.clear();
    state.selectedEntities.clear();
    state.selectedBundles.clear();
    await loadScanHistory();
    showToast("Lokale scan-, meet-, plan-, register- en Recorder-historie gewist");
    window.setTimeout(() => window.location.reload(), 500);
  } catch (error) { showToast(error.message, true); }
}

async function clearQuarantineHistory() {
  const confirmation = window.prompt("Typ WIS LOGBOEK. Actieve quarantainebestanden en hun herstelgegevens blijven behouden.");
  if (confirmation !== "WIS LOGBOEK") return;
  try {
    const response = await api("api/quarantine/history/clear", { method: "POST", body: JSON.stringify({ confirmation }) });
    await loadQuarantine();
    showToast(`${response.removed || 0} afgeronde quarantainelogboeken gewist`);
  } catch (error) { showToast(error.message, true); }
}

function downloadReport(extension) {
  if (!state.scan?.id) {
    showToast("Voer eerst een scan uit", true);
    return;
  }
  window.location.assign(apiUrl(`api/reports/${state.scan.id}.${extension}`));
}

function updateRetentionVisibility() {
  const mode = $('input[name="deletion-mode"]:checked').value;
  $("#retention-control").classList.toggle("hidden", mode !== "quarantine");
}

async function saveSettings() {
  const payload = {
    min_temp_age_days: Number($("#min-temp-age").value),
    min_log_age_days: Number($("#min-log-age").value),
    deletion_mode: $('input[name="deletion-mode"]:checked').value,
    retention_days: Number($("#retention-days").value),
    advanced_mode: $("#advanced-mode").checked,
    report_retention_count: Number($("#report-retention-count").value),
  };
  try {
    state.settings = await api("api/settings", { method: "POST", body: JSON.stringify(payload) });
    renderPolicy();
    showToast("Instellingen opgeslagen");
  } catch (error) {
    showToast(error.message, true);
  }
}

function openCleanupDialog() {
  const chosen = state.items.filter((item) => state.selected.has(item.id));
  const reviewCount = chosen.filter((item) => item.risk === "review").length;
  const text = `${chosen.length} bestanden in het veilige opruimplan · ${reviewCount} buiten de veilige marge · 0 uitvoerbare acties`;
  $("#dialog-summary").textContent = text;
  $("#cleanup-dialog").showModal();
}

async function confirmPlan() {
  const button = $("#confirm-plan");
  button.disabled = true;
  try {
    button.textContent = "Opruimplan voorbereiden...";
    const plan = await api("api/plans/preview", {
      method: "POST",
      body: JSON.stringify({
        backup_choice: "not_required_for_dry_run",
        deletion_mode: state.settings.deletion_mode,
        retention_days: state.settings.retention_days,
        selected_ids: [...state.selected],
      }),
    });
    $("#cleanup-dialog").close();
    showPlan(plan);
  } catch (error) {
    showToast(error.message, true);
  } finally {
    button.disabled = false;
    button.textContent = "Opruimplan opslaan";
  }
}

function escapeHtml(value) {
  return String(value).replace(/[&<>'"]/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
  })[character]);
}

function bindEvents() {
  $$(".tab").forEach((tab) => tab.addEventListener("click", () => activateTab(tab.dataset.tab)));
  $$('[data-tab-jump]').forEach((button) => button.addEventListener("click", () => activateTab(button.dataset.tabJump)));
  $("#scan-button").addEventListener("click", startScan);
  $("#hero-scan-button").addEventListener("click", startScan);
  $("#risk-filter").addEventListener("change", renderResults);
  $("#registry-severity-filter").addEventListener("change", renderBundles);
  $("#bundle-search").addEventListener("input", renderBundles);
  ["#entity-search", "#entity-days-filter"].forEach((selector) => $(selector).addEventListener("input", renderEntities));
  ["#entity-status-filter", "#entity-integration-filter", "#entity-area-filter", "#entity-group-filter"].forEach((selector) => $(selector).addEventListener("change", renderEntities));
  $("#entity-select-visible").addEventListener("click", () => {
    const allSelected = state.visibleEntityIds.length && state.visibleEntityIds.every((id) => state.selectedEntities.has(id));
    state.visibleEntityIds.forEach((id) => allSelected ? state.selectedEntities.delete(id) : state.selectedEntities.add(id));
    renderEntities();
  });
  $("#entity-plan-button").addEventListener("click", createEntityPlan);
  $("#prepare-button").addEventListener("click", openCleanupDialog);
  $("#select-all-safe").addEventListener("click", selectAllSafe);
  $("#save-settings").addEventListener("click", saveSettings);
  $("#confirm-plan").addEventListener("click", confirmPlan);
  $("#open-quarantine-execution").addEventListener("click", openQuarantineExecution);
  $("#open-registry-execution").addEventListener("click", openRegistryExecution);
  $("#quarantine-backup-button").addEventListener("click", startQuarantineBackup);
  $("#quarantine-verify-button").addEventListener("click", verifyQuarantineBackup);
  $("#quarantine-confirmation").addEventListener("input", updateQuarantineExecuteButton);
  $$("input[name=\"quarantine-backup-choice\"]").forEach((input) => input.addEventListener("change", updateQuarantineChoice));
  $("#quarantine-risk-ack").addEventListener("change", updateQuarantineExecuteButton);
  $("#quarantine-content-risk-ack").addEventListener("change", updateQuarantineExecuteButton);
  $("#confirm-quarantine").addEventListener("click", executeQuarantine);
  $("#registry-backup-button").addEventListener("click", startRegistryBackup);
  $("#registry-verify-button").addEventListener("click", verifyRegistryBackup);
  $("#registry-risk-ack").addEventListener("change", updateRegistryExecuteButton);
  $("#registry-confirmation").addEventListener("input", updateRegistryExecuteButton);
  $$('input[name="registry-backup-choice"]').forEach((input) => input.addEventListener("change", updateRegistryExecuteButton));
  $("#confirm-registry-cleanup").addEventListener("click", executeRegistryCleanup);
  $("#clear-scan-history").addEventListener("click", clearLocalHistory);
  $("#clear-quarantine-history").addEventListener("click", clearQuarantineHistory);
  $("#bundle-plan-button").addEventListener("click", addBundleToPlan);
  $("#open-purge-dialog").addEventListener("click", openPurgeDialog);
  $("#purge-backup-button").addEventListener("click", startPurgeBackup);
  $("#confirm-purge").addEventListener("click", executePurge);
  $$(".entity-decision").forEach((button) => button.addEventListener("click", () => saveEntityDecision(button.dataset.decision)));
  $("#advanced-mode").addEventListener("change", () => {
    if (!$("#advanced-mode").checked) {
      state.items.filter((item) => item.risk === "review").forEach((item) => state.selected.delete(item.id));
    }
    renderResults();
    renderAdvancedVisibility();
  });
  $$(".plan-download").forEach((button) => button.addEventListener("click", () => downloadPlan(button.dataset.format)));
  $$('[data-close-dialog]').forEach((button) => button.addEventListener("click", () => $("#" + button.dataset.closeDialog).close()));
  $$(".report-action").forEach((button) => button.addEventListener("click", () => downloadReport(button.dataset.report)));
  $$('input[name="deletion-mode"]').forEach((input) => input.addEventListener("change", updateRetentionVisibility));
  $("#retention-days").addEventListener("input", (event) => {
    $("#retention-value").textContent = event.target.value;
    const percent = ((Number(event.target.value) - 1) / 9) * 100;
    event.target.style.background = `linear-gradient(90deg,var(--accent) 0 ${percent}%,#30323a ${percent}%)`;
  });
}

async function init() {
  bindEvents();
  await loadStatus();
  await Promise.allSettled([loadSettings(), loadPurgeHistory(), loadScanHistory(), loadQuarantine(), loadBackupEvidence()]);
  try {
    const latest = await api("api/scans/latest?summary=1");
    if (latest.status && latest.status !== "never_run") {
      state.scan = latest;
      if (latest.status === "queued" || latest.status === "running") {
        showScanProgress(latest);
        pollScan(latest.id);
      } else {
        finishScanSummary(latest);
      }
    }
  } catch (error) {
    showToast(error.message, true);
  }
}

init();
