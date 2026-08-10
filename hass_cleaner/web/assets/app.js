const state = {
  scan: null,
  items: [],
  settings: null,
  registryAudit: null,
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
    const pill = $("#mode-pill");
    pill.classList.add("online");
    pill.innerHTML = `<i></i>${status.mode === "home_assistant" ? "Home Assistant verbonden" : "Lokale ontwikkelmodus"}`;
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
    const disabled = item.risk !== "safe" ? "disabled" : "";
    const checked = state.selected.has(item.id) ? "checked" : "";
    return `<label class="result-row">
      <input type="checkbox" data-item-id="${item.id}" ${disabled} ${checked} aria-label="Selecteer ${escapeHtml(item.path)}">
      <span class="result-path"><strong>${escapeHtml(item.path.split("/").pop())}</strong><small title="${escapeHtml(item.path)}">${escapeHtml(item.path)}</small></span>
      <span>${escapeHtml(categoryLabel(item.category))}</span>
      <span class="risk-chip ${item.risk}">${escapeHtml(riskLabel(item.risk))}</span>
      <span>${formatBytes(item.size_bytes)}</span>
    </label>`;
  }).join("");
  $$('input[data-item-id]', body).forEach((input) => input.addEventListener("change", () => {
    input.checked ? state.selected.add(input.dataset.itemId) : state.selected.delete(input.dataset.itemId);
    updatePrepareButton();
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
    return;
  }

  const summary = audit.summary || {};
  $("#registry-state").textContent = "Voltooid";
  $("#registry-message").textContent = `${summary.entities_total || 0} entities en ${summary.devices_total || 0} apparaten read-only gecontroleerd.`;
  $("#registry-entities-total").textContent = summary.entities_total || 0;
  $("#registry-unlinked-total").textContent = summary.entities_without_device || 0;
  $("#registry-review-total").textContent = summary.review_findings || 0;
  $("#registry-unavailable-total").textContent = summary.unavailable_states || 0;

  const filter = $("#registry-severity-filter").value;
  const findings = (audit.findings || []).filter((item) => filter === "all" || item.severity === filter);
  if (!findings.length) {
    body.innerHTML = '<div class="table-empty">Geen registerbevindingen binnen dit filter.</div>';
    return;
  }
  body.innerHTML = findings.map((item) => `<div class="registry-row">
    <span class="result-path"><strong>${escapeHtml(item.name || item.subject_id)}</strong><small title="${escapeHtml(item.subject_id)}">${escapeHtml(item.subject_type)} · ${escapeHtml(item.subject_id)}</small></span>
    <span>${escapeHtml(registryCategoryLabel(item.category))}</span>
    <span class="risk-chip ${item.severity}">${item.severity === "review" ? "Beoordeling" : "Informatief"}</span>
    <span class="registry-reason">${escapeHtml(item.reason)}</span>
  </div>`).join("");
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
  const mode = state.settings?.deletion_mode || "quarantine";
  const text = mode === "quarantine"
    ? `${state.selected.size} bestanden · ${state.settings.retention_days} dagen herstelbaar`
    : `${state.selected.size} bestanden · direct permanent verwijderen`;
  $("#dialog-summary").textContent = text;
  $("#cleanup-dialog").showModal();
}

async function confirmPlan() {
  const choice = $('input[name="backup-choice"]:checked').value;
  const button = $("#confirm-plan");
  button.disabled = true;
  try {
    if (choice === "create") {
      button.textContent = "Back-up starten...";
      await api("api/backups", { method: "POST", body: "{}" });
      showToast("Home Assistant-back-up is gestart");
    }
    button.textContent = "Dry-run voorbereiden...";
    const plan = await api("api/plans/preview", {
      method: "POST",
      body: JSON.stringify({
        backup_choice: choice,
        deletion_mode: state.settings.deletion_mode,
        retention_days: state.settings.retention_days,
        selected_ids: [...state.selected],
      }),
    });
    $("#cleanup-dialog").close();
    showToast(plan.message);
  } catch (error) {
    showToast(error.message, true);
  } finally {
    button.disabled = false;
    button.textContent = "Back-up en dry-run starten";
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
  $("#registry-severity-filter").addEventListener("change", renderRegistryAudit);
  $("#prepare-button").addEventListener("click", openCleanupDialog);
  $("#save-settings").addEventListener("click", saveSettings);
  $("#confirm-plan").addEventListener("click", confirmPlan);
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
  await Promise.allSettled([loadStatus(), loadSettings()]);
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
