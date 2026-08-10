const state = {
  scan: null,
  items: [],
  settings: null,
  registryAudit: null,
  status: null,
  activeBundle: null,
  latestPlan: null,
  selected: new Set(),
  pollTimer: null,
};

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

function apiUrl(path) {
  const current = window.location.pathname;
  const base = current.endsWith("/") ? current : current.substring(0, current.lastIndexOf("/") + 1);
  return `${base}${path.replace(/^\//, "")}`;
}

async function api(path, options = {}) {
  const response = await fetch(apiUrl(path), {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
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
    www_assets: "WWW-asset",
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
  updateRetentionVisibility();
  renderPolicy();
}

function renderPolicy() {
  if (!state.settings) return;
  const quarantine = state.settings.deletion_mode === "quarantine";
  $("#policy-title").textContent = quarantine ? `${state.settings.retention_days} dagen herstelbaar` : "Direct permanent verwijderen";
  $("#policy-description").textContent = quarantine ? "Verplaatsen naar beveiligde quarantaine" : "Extra waarschuwing en back-upvraag verplicht";
}

async function startScan() {
  try {
    state.selected.clear();
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

function finishScan(scan) {
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
  state.registryAudit = scan.registry_audit || null;
  $$(".report-action").forEach((button) => button.classList.remove("hidden"));
  $("#scan-state").textContent = "Voltooid";
  $("#scan-empty strong").textContent = `${scan.visited_files} bestanden gecontroleerd`;
  $("#scan-empty p").textContent = `${state.items.length} gerapporteerd · ${scan.ignored_files || 0} volgens beleid genegeerd. De scan heeft niets gewijzigd.`;
  renderMetrics(scan);
  renderResults();
  renderRegistryAudit();
  showToast("Veilige scan voltooid");
}

function renderMetrics(scan) {
  $("#safe-size").textContent = formatBytes(scan.totals.safe);
  $("#review-size").textContent = formatBytes(scan.totals.review);
  $("#protected-size").textContent = formatBytes(scan.totals.protected);
  $("#total-size").textContent = formatBytes(scan.totals.safe + scan.totals.review);
  $("#safe-count").textContent = `${scan.counts.safe} kandidaten`;
  $("#review-count").textContent = `${scan.counts.review} handmatig beoordelen`;
  $("#protected-count").textContent = `${scan.counts.protected} beschermd`;
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
    const advanced = Boolean(state.settings?.advanced_mode || $("#advanced-mode").checked);
    const disabled = item.risk === "protected" || (item.risk === "review" && !advanced) ? "disabled" : "";
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
  $("#registry-message").textContent = `${summary.entities_total || 0} entities en ${summary.devices_total || 0} apparaten read-only gecontroleerd.`;
  $("#registry-entities-total").textContent = summary.entities_total || 0;
  $("#registry-unlinked-total").textContent = summary.bundles_total || 0;
  $("#registry-review-total").textContent = summary.review_findings || 0;
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

function renderBundles() {
  const list = $("#bundle-list");
  const filter = $("#registry-severity-filter").value;
  const query = $("#bundle-search").value.trim().toLowerCase();
  const bundles = (state.registryAudit?.bundles || []).filter((bundle) => {
    if (filter === "review" && !bundle.review_count) return false;
    if (filter === "devices" && !bundle.devices.length) return false;
    if (filter === "entities" && !bundle.entities.length) return false;
    if (!query) return true;
    const haystack = [bundle.title, bundle.domain, ...bundle.devices.map((item) => item.name), ...bundle.entities.map((item) => item.entity_id)].join(" ").toLowerCase();
    return haystack.includes(query);
  });
  if (!bundles.length) {
    list.innerHTML = '<div class="table-empty panel">Geen bundels binnen dit filter.</div>';
    return;
  }
  list.innerHTML = bundles.map((bundle) => {
    const devicePreview = bundle.devices.slice(0, 3).map((item) => `<span>${escapeHtml(item.name)}</span>`).join("");
    const warning = bundle.review_count
      ? `<span class="risk-chip review">${bundle.review_count} beoordelen</span>`
      : `<span class="risk-chip info">${escapeHtml(bundle.advice?.evidence_label || "Meer bewijs nodig")}</span>`;
    return `<article class="panel bundle-card">
      <div class="bundle-main">
        <div class="bundle-icon">${escapeHtml((bundle.domain || "?").slice(0, 2).toUpperCase())}</div>
        <div class="bundle-copy"><div class="eyebrow">${escapeHtml(bundle.domain || "ONBEKEND")} · ${escapeHtml(bundle.state)}</div><h3>${escapeHtml(bundle.title)}</h3><p>${bundle.devices.length} apparaten · ${bundle.entities.length} entities</p><div class="device-preview">${devicePreview}${bundle.devices.length > 3 ? `<span>+${bundle.devices.length - 3}</span>` : ""}</div></div>
      </div>
      <div class="bundle-actions">${warning}<button class="button button-primary bundle-review" data-bundle-id="${escapeHtml(bundle.id)}">Bundel beoordelen</button></div>
    </article>`;
  }).join("");
  $$(".bundle-review", list).forEach((button) => button.addEventListener("click", () => openBundle(button.dataset.bundleId)));
}

async function openBundle(bundleId) {
  const bundle = (state.registryAudit?.bundles || []).find((item) => item.id === bundleId);
  if (!bundle) return;
  state.activeBundle = bundle;
  $("#bundle-dialog-title").textContent = bundle.title;
  $("#bundle-dialog-summary").textContent = `${bundle.devices.length} apparaten en ${bundle.entities.length} entities. ${bundle.review_count} waarschuwingen.`;
  $("#bundle-advice").innerHTML = renderAdvice(bundle.advice || {});
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

function renderLocalBundleDetails(bundle) {
  const devices = bundle.devices.length
    ? bundle.devices.map((device) => `<li><strong>${escapeHtml(device.name)}</strong><small>${device.entity_ids.length} entities${device.child_device_ids.length ? ` · ${device.child_device_ids.length} onderliggende apparaten` : ""}</small></li>`).join("")
    : "<li>Geen apparaten in deze bundel</li>";
  const loose = bundle.entities.filter((entity) => !entity.device_id);
  return `<details class="bundle-details" open><summary>Apparaten (${bundle.devices.length})</summary><ul>${devices}</ul></details>
    <details class="bundle-details"><summary>Losse entities (${loose.length})</summary><ul>${loose.slice(0, 100).map((entity) => `<li><strong>${escapeHtml(entity.name)}</strong><small>${escapeHtml(entity.entity_id)}</small></li>`).join("") || "<li>Geen losse entities</li>"}</ul></details>`;
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
  return `<div class="evidence-banner ${escapeHtml(advice.evidence_level || "insufficient")}"><span>Bewijsniveau</span><strong>${escapeHtml(advice.evidence_label || "Meer bewijs nodig")}</strong></div>
    <section class="advice-section"><h3>Wat is dit?</h3><p>${escapeHtml(advice.summary || "Geen beschrijving beschikbaar.")}</p></section>
    <section class="advice-section"><h3>Veilige inhoudspreview</h3><pre>${escapeHtml(JSON.stringify(preview, null, 2))}</pre><small>Waarden die gevoelig kunnen zijn worden niet opgenomen.</small></section>
    <section class="advice-grid"><div><h3>Wat kan er gebeuren?</h3><ul>${consequences}</ul></div><div><h3>Hoe herstel je dit?</h3><ul>${recovery}</ul></div></section>
    <section class="advice-section first-step"><h3>Aanbevolen eerste stap</h3><p>${escapeHtml(advice.recommended_first_step || "Niet wijzigen zonder aanvullende controle.")}</p></section>`;
}

function showPlan(response) {
  state.latestPlan = response;
  const summary = response.plan?.summary || {};
  $("#plan-dialog-summary").textContent = `${summary.file_count || 0} bestanden en ${summary.bundle_count || 0} bundels vastgelegd. Uitvoerbare acties: ${summary.executable_actions || 0}.`;
  $("#plan-dialog").showModal();
  showToast(response.message || "Dry-runplan opgeslagen");
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
  $("#purge-dialog").showModal();
}

async function startPurgeBackup() {
  const button = $("#purge-backup-button");
  button.disabled = true;
  try {
    await api("api/backups", { method: "POST", body: "{}" });
    showToast("Back-up gestart. Wacht op voltooiing in Home Assistant en vink daarna de bevestiging aan.");
    button.textContent = "Back-up gestart - controleer voltooiing";
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
  button.textContent = state.selected.size ? `Dry-run voorbereiden (${state.selected.size})` : "Dry-run voorbereiden";
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
  const text = `${chosen.length} bestanden in dry-run · ${reviewCount} buiten de veilige marge · 0 uitvoerbare acties`;
  $("#dialog-summary").textContent = text;
  $("#cleanup-dialog").showModal();
}

async function confirmPlan() {
  const button = $("#confirm-plan");
  button.disabled = true;
  try {
    button.textContent = "Dry-run voorbereiden...";
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
    button.textContent = "Dry-runplan maken";
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
  $("#prepare-button").addEventListener("click", openCleanupDialog);
  $("#save-settings").addEventListener("click", saveSettings);
  $("#confirm-plan").addEventListener("click", confirmPlan);
  $("#bundle-plan-button").addEventListener("click", addBundleToPlan);
  $("#open-purge-dialog").addEventListener("click", openPurgeDialog);
  $("#purge-backup-button").addEventListener("click", startPurgeBackup);
  $("#confirm-purge").addEventListener("click", executePurge);
  $("#advanced-mode").addEventListener("change", () => {
    if (!$("#advanced-mode").checked) {
      state.items.filter((item) => item.risk === "review").forEach((item) => state.selected.delete(item.id));
    }
    renderResults();
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
  await Promise.allSettled([loadStatus(), loadSettings(), loadPurgeHistory()]);
  try {
    const latest = await api("api/scans/latest");
    if (latest.status && latest.status !== "never_run") {
      state.scan = latest;
      if (latest.status === "queued" || latest.status === "running") {
        showScanProgress(latest);
        pollScan(latest.id);
      } else {
        finishScan(latest);
      }
    }
  } catch (error) {
    showToast(error.message, true);
  }
}

init();
