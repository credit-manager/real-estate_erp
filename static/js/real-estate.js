/* ============================================================
   Real Estate Module JavaScript — Full Tabbed Interface
   ============================================================ */

let allUnits = [];
let allProjects = [];
let allCustomers = [];
let allEmployees = [];
let allPlans = [];
let unitsList = null;
let currentPlan = null;
let currentInstallment = null;

let allBuildings = [];
let allFloors = [];
let allUnitTypes = [];
let allOwners = [];
let allReservations = [];
let allAllocations = [];
let allContracts = [];
let allCommissions = [];
let allDeliveries = [];
let allMaintenance = [];
let allShares = [];
let allPriceHistory = [];

const RE_API = "/api/realestate";

let _unitPrevPrice = null;

// ============ SCROLL LINKS ============
// عند الضغط على رابط تبويب يتم التمرير الناعم إلى القسم المقابل
function reSwitchTab(targetId) {
  document.querySelectorAll("#re-tabs a.tab-btn").forEach((l) => l.classList.toggle("on", l.getAttribute("href") === targetId));
  document.querySelectorAll("#re-tabs ~ .tab-content").forEach((sec) => sec.classList.toggle("active", ("#" + sec.id) === targetId));
  history.replaceState(null, "", targetId);
}
function reSetupTabs() {
  document.querySelectorAll("#re-tabs a.tab-btn").forEach((link) => {
    link.addEventListener("click", (e) => {
      e.preventDefault();
      const targetId = link.getAttribute("href");
      if (document.querySelector(targetId)) reSwitchTab(targetId);
    });
  });
}

document.addEventListener("DOMContentLoaded", async () => {
  reSetupTabs();
  const first = document.querySelector(".tab-content.active");
  reSwitchTab("#" + (first ? first.id : "re-units"));

  try {
    [allUnits, allProjects, allCustomers, allEmployees, allPlans] = await Promise.all([
      api.get("/api/units"),
      api.get("/api/projects"),
      api.get("/api/customers"),
      api.get("/api/employees"),
      api.get("/api/payment-plans"),
    ]);
await Promise.all([
loadBuildings(), loadFloors(), loadUnitTypes(), loadOwners(),
loadReservations(), loadAllocations(), loadContracts(),
loadCommissions(), loadBrokers(), loadDeliveries(), loadMaintenance(), loadShares(),
loadPriceHistory(),
loadScreenings(), loadMortgages(), loadAnalytics(),
loadFinancialYearOptions(),
]);
// خيارات مشاريع التحليلات
const apSel = document.getElementById("analytics-project");
if (apSel) {
  apSel.innerHTML = `<option value="">${t("common.all")}</option>` +
    (allProjects || []).map((p) => `<option value="${p.id}">${escapeHtml(p.name)}</option>`).join("");
  apSel.addEventListener("change", loadAnalytics);
}
    buildFinancialYearFilter("filter-year-plans");
    unitsList = new PagedList({
      fetch: (p) => {
        const all = filteredUnits();
        const total = all.length;
        const pages = Math.max(1, Math.ceil(total / p.perPage));
        const page = Math.min(p.page, pages);
        return {
          items: all.slice((page - 1) * p.perPage, page * p.perPage),
          total,
          page,
          pages,
          per_page: p.perPage,
        };
      },
      target: "units-table",
      controls: "units-pagination",
      colspan: 9,
      perPage: 25,
      empty: `<tr><td colspan="9"><div class="empty-state"><div class="empty-icon">🏠</div>${t("realestate.noUnits")}</div></td></tr>`,
      render: (rows) => rows.map(unitRowHTML).join(""),
    });
    renderUnits();
    renderSummary();
    populateProjectSelect();
    renderPlans();
    populateCommonSelects();

    document.getElementById("filter-status").addEventListener("change", renderUnits);
    document.getElementById("filter-search").addEventListener("input", renderUnits);
    document.getElementById("filter-year-plans").addEventListener("change", renderPlans);
    document.getElementById("filter-price-unit").addEventListener("change", loadPriceHistory);
    ["plan-unit", "plan-down", "plan-months"].forEach((id) => {
      const el = document.getElementById(id);
      if (el) {
        el.addEventListener("change", updatePlanSummary);
        el.addEventListener("input", updatePlanSummary);
      }
    });
  } catch (err) {
    console.error(err);
  }
});

// ============ HELPERS ============
function populateProjectSelect() {
  const select = document.getElementById("unit-project");
  if (!select) return;
  select.innerHTML = `<option value="">${t("realestate.selectProject")}</option>` +
    allProjects.map((p) => `<option value="${p.id}">${escapeHtml(p.name)}</option>`).join("");
}

function populateCommonSelects() {
  // Building modal project select
  const bp = document.getElementById("building-project");
  if (bp) bp.innerHTML = `<option value="">${t("common.choose")}</option>` + allProjects.map((p) => `<option value="${p.id}">${escapeHtml(p.name)}</option>`).join("");

  // Floor modal building select
  const fb = document.getElementById("floor-building");
  if (fb) fb.innerHTML = `<option value="">${t("common.choose")}</option>` + allBuildings.map((b) => `<option value="${b.id}">${escapeHtml(b.name)}</option>`).join("");

  // Unit selects for reservations/allocations/contracts/deliveries/maintenance/shares
  const unitOptions = allUnits.map((u) => `<option value="${u.id}">${escapeHtml(u.unit_code)}</option>`).join("");
  ["reservation-unit", "allocation-unit", "contract-unit", "delivery-unit", "maintenance-unit", "share-unit"].forEach((id) => {
    const sel = document.getElementById(id);
    if (sel) sel.innerHTML = `<option value="">${t("common.choose")}</option>` + unitOptions;
  });

  // Customer selects
  const custOptions = allCustomers.map((c) => `<option value="${c.id}">${escapeHtml(c.full_name)}</option>`).join("");
  ["reservation-customer", "allocation-customer", "contract-customer", "delivery-customer"].forEach((id) => {
    const sel = document.getElementById(id);
    if (sel) sel.innerHTML = `<option value="">${t("common.choose")}</option>` + custOptions;
  });

  // Employee selects (commissions + maintenance)
  const empOptions = allEmployees.map((e) => `<option value="${e.id}">${escapeHtml(e.full_name)}</option>`).join("");
  const ce = document.getElementById("commission-employee");
  if (ce) ce.innerHTML = `<option value="">${t("common.choose")}</option>` + empOptions;
  const ma = document.getElementById("maintenance-assigned");
  if (ma) ma.innerHTML = `<option value="">${t("common.choose")}</option>` + empOptions;

  // Owner select for shares
  const so = document.getElementById("share-owner");
  if (so) so.innerHTML = `<option value="">${t("common.choose")}</option>` + allOwners.map((o) => `<option value="${o.id}">${escapeHtml(o.full_name)}</option>`).join("");

  // Price history unit filter
  const pu = document.getElementById("filter-price-unit");
  if (pu && !pu.dataset.filled) {
    pu.innerHTML = `<option value="">${t("common.all")}</option>` + allUnits.map((u) => `<option value="${u.id}">${escapeHtml(u.unit_code)}</option>`).join("");
    pu.dataset.filled = "1";
  }
}

function closeModal(id) {
  document.getElementById(id).classList.remove("active");
}

window.closeModal = closeModal;

// Unit modal selects (building / dependent floor / unit type / owner)
function populateUnitSelects() {
  const bSel = document.getElementById("unit-building");
  if (bSel) {
    bSel.innerHTML = `<option value="">${t("common.choose")}</option>` + allBuildings.map((b) => `<option value="${b.id}">${escapeHtml(b.name)}</option>`).join("");
  }
  const tSel = document.getElementById("unit-type-select");
  if (tSel) {
    tSel.innerHTML = `<option value="">${t("common.choose")}</option>` + allUnitTypes.filter((x) => x.is_active !== false).map((x) => `<option value="${x.id}">${escapeHtml(x.name)}</option>`).join("");
  }
  const oSel = document.getElementById("unit-owner");
  if (oSel) {
    oSel.innerHTML = `<option value="">${t("common.choose")}</option>` + allOwners.map((o) => `<option value="${o.id}">${escapeHtml(o.full_name)}</option>`).join("");
  }
  if (bSel && !bSel.dataset.bound) {
    bSel.dataset.bound = "1";
    bSel.addEventListener("change", () => fillUnitFloorSelect(bSel.value, null));
  }
  fillUnitFloorSelect(bSel ? bSel.value : null, null);
}

const RE_STATUS_LABELS = {
  active: "status.active",
  pending: "status.pending",
  converted: "status.completed",
  cancelled: "status.cancelled",
  delivered: "status.delivered",
  paid: "status.paid",
  done: "status.completed",
  in_progress: "pval.in_progress",
  open: "pval.open",
  completed: "status.completed",
  draft: "pval.draft",
};

function reStatusBadge(s) {
  const cls = { active: "success", pending: "warning", converted: "info", cancelled: "danger", delivered: "success", paid: "success", done: "success", in_progress: "info", open: "warning", completed: "success", draft: "secondary" }[s] || "secondary";
  return `<span class="badge badge-${cls}">${t(RE_STATUS_LABELS[s] || s)}</span>`;
}

// ============ UNITS ============
function filteredUnits() {
  const status = document.getElementById("filter-status").value;
  const search = document.getElementById("filter-search").value.trim();
  return allUnits.filter((u) => {
    const sOk = !status || u.status === status;
    const searchOk = !search || (u.unit_code || "").includes(search);
    return sOk && searchOk;
  });
}

function unitRowHTML(u) {
  const project = allProjects.find((p) => p.id === u.project_id);
  const building = allBuildings.find((b) => b.id === u.building_id);
  return `
    <tr>
      <td><strong>${escapeHtml(u.unit_code)}</strong></td>
      <td style="color:var(--muted-foreground);">${building ? escapeHtml(building.name) : "—"}</td>
      <td style="color:var(--muted-foreground);">${project ? escapeHtml(project.name) : "—"}</td>
      <td style="color:var(--muted-foreground);">${tv(u.unit_type) || "—"}</td>
      <td>${u.area || 0} ${t("realestate.areaUnit")}</td>
      <td style="color:var(--muted-foreground);">${escapeHtml(u.floor || "—")}</td>
      <td><strong>${formatMoney(u.price)}</strong></td>
      <td>${statusBadge(u.status)}</td>
      <td>
        <div class="table-actions">
          ${canAction("realestate", "edit") ? `<button class="btn btn-secondary btn-sm" onclick='editUnit(${JSON.stringify(u)})'>${t("common.edit")}</button>` : ""}
          ${canAction("realestate", "delete") ? `<button class="btn btn-danger btn-sm" onclick="deleteUnit(${u.id})">${t("common.delete")}</button>` : ""}
        </div>
      </td>
    </tr>`;
}

function renderUnits() {
  if (!unitsList) return;
  unitsList.page = 1;
  unitsList.load();
}

function renderSummary() {
  const count = (s) => allUnits.filter((u) => u.status === s).length;
  animateCount(document.getElementById("unit-total"), allUnits.length, formatNumber);
  animateCount(document.getElementById("unit-available"), count("available"), formatNumber);
  animateCount(document.getElementById("unit-sold"), count("sold"), formatNumber);
  animateCount(document.getElementById("unit-rented"), count("rented"), formatNumber);
}

function exportUnits() {
  const headers = [t("realestate.colCode"), t("common.project"), t("common.type"), t("common.area"), t("common.floor"), t("common.price"), t("common.status")];
  const rows = allUnits.map((u) => {
    const project = allProjects.find((p) => p.id === u.project_id);
    return [u.unit_code, project ? project.name : "", tv(u.unit_type), u.area || 0, u.floor || "", u.price || 0, STATUS_LABELS[u.status] || u.status];
  });
  exportCSV("units.csv", headers, rows);
}

function openUnitModal() {
  document.getElementById("unit-modal-title").textContent = t("realestate.newUnit");
  _unitPrevPrice = null;
  document.getElementById("unit-id").value = "";
  ["unit-code", "unit-area", "unit-price"].forEach((id) => document.getElementById(id).value = "");
  ["unit-project", "unit-building", "unit-floor-select", "unit-type-select", "unit-owner"].forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.value = "";
  });
  document.getElementById("unit-status").value = "available";
  populateProjectSelect();
  populateUnitSelects();
  document.getElementById("unit-modal").classList.add("active");
}

function editUnit(u) {
  document.getElementById("unit-modal-title").textContent = t("realestate.editUnit");
  document.getElementById("unit-id").value = u.id;
  _unitPrevPrice = u.price || 0;
  document.getElementById("unit-code").value = u.unit_code || "";
  populateProjectSelect();
  populateUnitSelects();
  document.getElementById("unit-project").value = u.project_id || "";
  document.getElementById("unit-building").value = u.building_id || "";
  fillUnitFloorSelect(u.building_id, u.floor_id);
  document.getElementById("unit-type-select").value = u.unit_type_id || "";
  document.getElementById("unit-owner").value = u.owner_id || "";
  document.getElementById("unit-area").value = u.area || "";
  document.getElementById("unit-price").value = u.price || "";
  document.getElementById("unit-status").value = u.status || "available";
  document.getElementById("unit-modal").classList.add("active");
}

function fillUnitFloorSelect(buildingId, selectedFloorId) {
  const fs = document.getElementById("unit-floor-select");
  if (!fs) return;
  const floors = buildingId ? allFloors.filter((f) => f.building_id === Number(buildingId)) : [];
  fs.innerHTML = `<option value="">${t("common.choose")}</option>` + floors.map((f) => `<option value="${f.id}">${f.name || f.number}</option>`).join("");
  if (selectedFloorId) fs.value = selectedFloorId;
}

async function saveUnit() {
  const id = document.getElementById("unit-id").value;
  const prevPrice = parseFloat(document.getElementById("unit-price").value) || 0;
  const buildingSel = document.getElementById("unit-building");
  const floorSel = document.getElementById("unit-floor-select");
  const typeSel = document.getElementById("unit-type-select");
  const ownerSel = document.getElementById("unit-owner");
  const buildingId = parseInt(buildingSel.value) || null;
  const floorId = parseInt(floorSel.value) || null;
  const typeId = parseInt(typeSel.value) || null;
  const floorOption = floorSel.selectedOptions[0];
  const typeOption = typeSel.selectedOptions[0];
  const body = {
    unit_code: document.getElementById("unit-code").value,
    project_id: parseInt(document.getElementById("unit-project").value) || null,
    building_id: buildingId,
    floor_id: floorId,
    unit_type_id: typeId,
    owner_id: parseInt(ownerSel.value) || null,
    unit_type: typeOption ? typeOption.textContent : "",
    area: parseFloat(document.getElementById("unit-area").value) || 0,
    floor: floorOption ? floorOption.textContent : "",
    price: prevPrice,
    status: document.getElementById("unit-status").value,
  };
  if (id) body._prev_price = _unitPrevPrice;
  if (!body.unit_code) { showToast(t("realestate.codeRequired"), "warning"); return; }
  try {
    if (id) await api.put(`/api/units/${id}`, body);
    else await api.post("/api/units", body);
    showToast(t("common.saved"));
    closeModal("unit-modal");
    [allUnits, allPriceHistory] = await Promise.all([api.get("/api/units"), api.get(RE_API + "/price-history")]);
    renderUnits(); renderSummary(); loadPriceHistory(); populateCommonSelects();
  } catch (err) { showToast(err.message, "error"); }
}

async function deleteUnit(id) {
  if (!confirm(t("common.confirmDelete"))) return;
  try {
    await api.delete(`/api/units/${id}`);
    showToast(t("common.deleted"));
    allUnits = await api.get("/api/units");
    renderUnits(); renderSummary(); populateCommonSelects();
  } catch (err) { showToast(err.message, "error"); }
}

window.openUnitModal = openUnitModal;
window.editUnit = editUnit;
window.deleteUnit = deleteUnit;
window.saveUnit = saveUnit;

// ============ BUILDINGS ============
async function loadBuildings() {
  try {
    allBuildings = await api.get(RE_API + "/buildings");
    renderBuildings();
    populateCommonSelects();
  } catch (e) { toastError(e); }
}

function renderBuildings() {
  const tbody = document.getElementById("buildings-table");
  if (!allBuildings.length) {
    tbody.innerHTML = `<tr><td colspan="6"><div class="empty-state">${t("re.noBuildings")}</div></td></tr>`;
    return;
  }
  tbody.innerHTML = allBuildings.map((b) => {
    const project = allProjects.find((p) => p.id === b.project_id);
    return `<tr>
      <td><strong>${escapeHtml(b.code || "—")}</strong></td>
      <td>${escapeHtml(b.name)}</td>
      <td style="color:var(--muted-foreground);">${project ? escapeHtml(project.name) : "—"}</td>
      <td>${b.floors_count}</td>
      <td>${b.units_count}</td>
      <td><div class="table-actions">
        ${canAction("realestate", "edit") ? `<button class="btn btn-secondary btn-sm" onclick='editBuilding(${JSON.stringify(b)})'>${t("common.edit")}</button>` : ""}
        ${canAction("realestate", "delete") ? `<button class="btn btn-danger btn-sm" onclick="deleteBuilding(${b.id})">${t("common.delete")}</button>` : ""}
      </div></td></tr>`;
  }).join("");
}

function openBuildingModal() {
  document.getElementById("building-modal-title").textContent = t("re.newBuilding");
  document.getElementById("building-id").value = "";
  ["building-name", "building-code", "building-desc"].forEach((id) => document.getElementById(id).value = "");
  document.getElementById("building-floors").value = 0;
  document.getElementById("building-project").value = "";
  populateCommonSelects();
  document.getElementById("building-modal").classList.add("active");
}

function editBuilding(b) {
  document.getElementById("building-modal-title").textContent = t("re.editBuilding");
  document.getElementById("building-id").value = b.id;
  document.getElementById("building-name").value = b.name;
  document.getElementById("building-code").value = b.code || "";
  document.getElementById("building-floors").value = b.floors_count;
  populateCommonSelects();
  document.getElementById("building-project").value = b.project_id || "";
  document.getElementById("building-desc").value = b.description || "";
  document.getElementById("building-modal").classList.add("active");
}

async function saveBuilding() {
  const id = document.getElementById("building-id").value;
  const body = {
    name: document.getElementById("building-name").value,
    code: document.getElementById("building-code").value,
    project_id: parseInt(document.getElementById("building-project").value) || null,
    floors_count: parseInt(document.getElementById("building-floors").value) || 0,
    description: document.getElementById("building-desc").value,
  };
  if (!body.name) { showToast(t("re.buildingNameRequired"), "warning"); return; }
  try {
    if (id) await api.put(`${RE_API}/buildings/${id}`, body);
    else await api.post(RE_API + "/buildings", body);
    showToast(t("common.saved"));
    closeModal("building-modal");
    loadBuildings();
  } catch (err) { showToast(err.message, "error"); }
}

async function deleteBuilding(id) {
  if (!confirm(t("re.confirmDeleteBuilding"))) return;
  try {
    await api.delete(`${RE_API}/buildings/${id}`);
    showToast(t("common.deleted"));
    loadBuildings();
  } catch (err) { showToast(err.message, "error"); }
}

window.openBuildingModal = openBuildingModal;
window.editBuilding = editBuilding;
window.saveBuilding = saveBuilding;
window.deleteBuilding = deleteBuilding;

// ============ FLOORS ============
async function loadFloors() {
  try {
    allFloors = await api.get(RE_API + "/floors");
    renderFloors();
    populateCommonSelects();
  } catch (e) { toastError(e); }
}

function renderFloors() {
  const tbody = document.getElementById("floors-table");
  if (!allFloors.length) {
    tbody.innerHTML = `<tr><td colspan="5"><div class="empty-state">${t("re.noFloors")}</div></td></tr>`;
    return;
  }
  tbody.innerHTML = allFloors.map((f) => {
    const building = allBuildings.find((b) => b.id === f.building_id);
    return `<tr>
      <td><strong>${f.number}</strong></td>
      <td>${escapeHtml(f.name || "—")}</td>
      <td style="color:var(--muted-foreground);">${building ? escapeHtml(building.name) : "—"}</td>
      <td>${f.units_count}</td>
      <td><div class="table-actions">
        ${canAction("realestate", "edit") ? `<button class="btn btn-secondary btn-sm" onclick='editFloor(${JSON.stringify(f)})'>${t("common.edit")}</button>` : ""}
        ${canAction("realestate", "delete") ? `<button class="btn btn-danger btn-sm" onclick="deleteFloor(${f.id})">${t("common.delete")}</button>` : ""}
      </div></td></tr>`;
  }).join("");
}

function openFloorModal() {
  document.getElementById("floor-modal-title").textContent = t("re.newFloor");
  document.getElementById("floor-id").value = "";
  document.getElementById("floor-number").value = 1;
  ["floor-name", "floor-desc"].forEach((id) => document.getElementById(id).value = "");
  populateCommonSelects();
  document.getElementById("floor-building").value = "";
  document.getElementById("floor-modal").classList.add("active");
}

function editFloor(f) {
  document.getElementById("floor-modal-title").textContent = t("re.editFloor");
  document.getElementById("floor-id").value = f.id;
  document.getElementById("floor-number").value = f.number;
  document.getElementById("floor-name").value = f.name || "";
  populateCommonSelects();
  document.getElementById("floor-building").value = f.building_id || "";
  document.getElementById("floor-desc").value = f.description || "";
  document.getElementById("floor-modal").classList.add("active");
}

async function saveFloor() {
  const id = document.getElementById("floor-id").value;
  const buildingId = parseInt(document.getElementById("floor-building").value);
  if (!buildingId) { showToast(t("re.floorBuilding"), "warning"); return; }
  const body = {
    building_id: buildingId,
    number: parseInt(document.getElementById("floor-number").value) || 1,
    name: document.getElementById("floor-name").value,
    description: document.getElementById("floor-desc").value,
  };
  try {
    if (id) await api.put(`${RE_API}/floors/${id}`, body);
    else await api.post(RE_API + "/floors", body);
    showToast(t("common.saved"));
    closeModal("floor-modal");
    loadFloors();
  } catch (err) { showToast(err.message, "error"); }
}

async function deleteFloor(id) {
  if (!confirm(t("re.confirmDeleteFloor"))) return;
  try {
    await api.delete(`${RE_API}/floors/${id}`);
    showToast(t("common.deleted"));
    loadFloors();
  } catch (err) { showToast(err.message, "error"); }
}

window.openFloorModal = openFloorModal;
window.editFloor = editFloor;
window.saveFloor = saveFloor;
window.deleteFloor = deleteFloor;

// ============ UNIT TYPES ============
async function loadUnitTypes() {
  try {
    allUnitTypes = await api.get(RE_API + "/unit-types");
    renderUnitTypes();
  } catch (e) { toastError(e); }
}

function renderUnitTypes() {
  const tbody = document.getElementById("unit-types-table");
  if (!allUnitTypes.length) {
    tbody.innerHTML = `<tr><td colspan="5"><div class="empty-state">${t("re.noUnitTypes")}</div></td></tr>`;
    return;
  }
  tbody.innerHTML = allUnitTypes.map((u) => `<tr>
    <td><strong>${escapeHtml(u.name)}</strong></td>
    <td style="color:var(--muted-foreground);">${escapeHtml(u.code || "—")}</td>
    <td>${u.is_active ? `<span class="badge badge-success">${t("status.active")}</span>` : `<span class="badge badge-danger">${t("status.cancelled")}</span>`}</td>
    <td>${u.units_count}</td>
    <td><div class="table-actions">
      ${canAction("realestate", "edit") ? `<button class="btn btn-secondary btn-sm" onclick='editUnitType(${JSON.stringify(u)})'>${t("common.edit")}</button>` : ""}
      ${canAction("realestate", "delete") ? `<button class="btn btn-danger btn-sm" onclick="deleteUnitType(${u.id})">${t("common.delete")}</button>` : ""}
    </div></td></tr>`).join("");
}

function openUnitTypeModal() {
  document.getElementById("unit-type-modal-title").textContent = t("re.newUnitType");
  document.getElementById("unit-type-id").value = "";
  ["unit-type-name", "unit-type-code"].forEach((id) => document.getElementById(id).value = "");
  document.getElementById("unit-type-active").checked = true;
  document.getElementById("unit-type-modal").classList.add("active");
}

function editUnitType(u) {
  document.getElementById("unit-type-modal-title").textContent = t("re.editUnitType");
  document.getElementById("unit-type-id").value = u.id;
  document.getElementById("unit-type-name").value = u.name;
  document.getElementById("unit-type-code").value = u.code || "";
  document.getElementById("unit-type-active").checked = u.is_active;
  document.getElementById("unit-type-modal").classList.add("active");
}

async function saveUnitType() {
  const id = document.getElementById("unit-type-id").value;
  const body = { name: document.getElementById("unit-type-name").value, code: document.getElementById("unit-type-code").value, is_active: document.getElementById("unit-type-active").checked };
  if (!body.name) { showToast(t("re.unitTypeNameRequired"), "warning"); return; }
  try {
    if (id) await api.put(`${RE_API}/unit-types/${id}`, body);
    else await api.post(RE_API + "/unit-types", body);
    showToast(t("common.saved"));
    closeModal("unit-type-modal");
    loadUnitTypes();
  } catch (err) { showToast(err.message, "error"); }
}

async function deleteUnitType(id) {
  if (!confirm(t("re.confirmDeleteUnitType"))) return;
  try {
    await api.delete(`${RE_API}/unit-types/${id}`);
    showToast(t("common.deleted"));
    loadUnitTypes();
  } catch (err) { showToast(err.message, "error"); }
}

window.openUnitTypeModal = openUnitTypeModal;
window.editUnitType = editUnitType;
window.saveUnitType = saveUnitType;
window.deleteUnitType = deleteUnitType;

// ============ PRICING ============
async function loadPriceHistory() {
  try {
    const unitId = document.getElementById("filter-price-unit")?.value || "";
    const url = RE_API + "/price-history" + (unitId ? `?unit_id=${unitId}` : "");
    allPriceHistory = await api.get(url);
    renderPricing();
  } catch (e) { toastError(e); }
}

function renderPricing() {
  const tbody = document.getElementById("pricing-table");
  if (!allPriceHistory.length) {
    tbody.innerHTML = `<tr><td colspan="5"><div class="empty-state">${t("re.noPricing")}</div></td></tr>`;
    return;
  }
  tbody.innerHTML = allPriceHistory.map((p) => `<tr>
    <td><strong>${escapeHtml(p.unit_code || "—")}</strong></td>
    <td style="color:var(--muted-foreground);">${formatMoney(p.old_price)}</td>
    <td style="color:var(--primary);"><strong>${formatMoney(p.new_price)}</strong></td>
    <td style="color:var(--muted-foreground);">${p.change_date || "—"}</td>
    <td>${escapeHtml(p.reason || "—")}</td>
  </tr>`).join("");
}

// ============ RESERVATIONS ============
async function loadReservations() {
  try {
    allReservations = await api.get(RE_API + "/reservations");
    renderReservations();
  } catch (e) { toastError(e); }
}

function renderReservations() {
  const tbody = document.getElementById("reservations-table");
  if (!allReservations.length) {
    tbody.innerHTML = `<tr><td colspan="7"><div class="empty-state">${t("re.noReservations")}</div></td></tr>`;
    return;
  }
  tbody.innerHTML = allReservations.map((r) => `<tr>
    <td><strong>${escapeHtml(r.unit_code || "—")}</strong></td>
    <td style="color:var(--muted-foreground);">${escapeHtml(r.customer_name || "—")}</td>
    <td style="color:var(--muted-foreground);">${r.reserved_date || "—"}</td>
    <td style="color:var(--muted-foreground);">${r.expiry_date || "—"}</td>
    <td><strong>${formatMoney(r.deposit)}</strong></td>
    <td>${reStatusBadge(r.status)}</td>
    <td><div class="table-actions">
      ${r.status === "active" && canAction("realestate", "create") ? `<button class="btn btn-success btn-sm" onclick="convertReservation(${r.id})">${t("re.convertToContract")}</button>` : ""}
      ${canAction("realestate", "edit") ? `<button class="btn btn-secondary btn-sm" onclick='editReservation(${JSON.stringify(r)})'>${t("common.edit")}</button>` : ""}
      ${canAction("realestate", "delete") ? `<button class="btn btn-danger btn-sm" onclick="deleteReservation(${r.id})">${t("common.delete")}</button>` : ""}
    </div></td></tr>`).join("");
}

function openReservationModal() {
  document.getElementById("reservation-modal-title").textContent = t("re.newReservation");
  document.getElementById("reservation-id").value = "";
  ["reservation-unit", "reservation-customer"].forEach((id) => { const el = document.getElementById(id); if (el) el.value = ""; });
  document.getElementById("reservation-date").value = new Date().toISOString().slice(0, 10);
  document.getElementById("reservation-expiry").value = "";
  document.getElementById("reservation-deposit").value = "";
  document.getElementById("reservation-notes").value = "";
  populateCommonSelects();
  document.getElementById("reservation-modal").classList.add("active");
}

function editReservation(r) {
  document.getElementById("reservation-modal-title").textContent = t("re.editReservation");
  document.getElementById("reservation-id").value = r.id;
  populateCommonSelects();
  document.getElementById("reservation-unit").value = r.unit_id;
  document.getElementById("reservation-customer").value = r.customer_id || "";
  document.getElementById("reservation-date").value = r.reserved_date || new Date().toISOString().slice(0, 10);
  document.getElementById("reservation-expiry").value = r.expiry_date || "";
  document.getElementById("reservation-deposit").value = r.deposit;
  document.getElementById("reservation-notes").value = r.notes || "";
  document.getElementById("reservation-modal").classList.add("active");
}

async function saveReservation() {
  const id = document.getElementById("reservation-id").value;
  const unitId = parseInt(document.getElementById("reservation-unit").value);
  if (!unitId) { showToast(t("common.required"), "warning"); return; }
  const body = {
    unit_id: unitId,
    customer_id: parseInt(document.getElementById("reservation-customer").value) || null,
    reserved_date: document.getElementById("reservation-date").value,
    expiry_date: document.getElementById("reservation-expiry").value,
    deposit: parseFloat(document.getElementById("reservation-deposit").value) || 0,
    notes: document.getElementById("reservation-notes").value,
  };
  try {
    if (id) await api.put(`${RE_API}/reservations/${id}`, body);
    else await api.post(RE_API + "/reservations", body);
    showToast(t("common.saved"));
    closeModal("reservation-modal");
    loadReservations();
    allUnits = await api.get("/api/units");
    renderUnits(); renderSummary();
  } catch (err) { showToast(err.message, "error"); }
}

async function deleteReservation(id) {
  if (!confirm(t("re.confirmDeleteReservation"))) return;
  try {
    await api.delete(`${RE_API}/reservations/${id}`);
    showToast(t("common.deleted"));
    loadReservations();
    allUnits = await api.get("/api/units");
    renderUnits(); renderSummary();
  } catch (err) { showToast(err.message, "error"); }
}

async function convertReservation(id) {
  if (!confirm(t("re.convertToContract") + "?")) return;
  try {
    await api.post(`${RE_API}/reservations/${id}/convert`, {});
    showToast(t("re.reservationConverted"));
    loadReservations(); loadContracts();
    allUnits = await api.get("/api/units");
    renderUnits(); renderSummary();
  } catch (err) { showToast(err.message, "error"); }
}

window.openReservationModal = openReservationModal;
window.editReservation = editReservation;
window.saveReservation = saveReservation;
window.deleteReservation = deleteReservation;
window.convertReservation = convertReservation;

// ============ ALLOCATIONS ============
async function loadAllocations() {
  try {
    allAllocations = await api.get(RE_API + "/allocations");
    renderAllocations();
  } catch (e) { toastError(e); }
}

function renderAllocations() {
  const tbody = document.getElementById("allocations-table");
  if (!allAllocations.length) {
    tbody.innerHTML = `<tr><td colspan="5"><div class="empty-state">${t("re.noAllocations")}</div></td></tr>`;
    return;
  }
  tbody.innerHTML = allAllocations.map((a) => `<tr>
    <td><strong>${escapeHtml(a.unit_code || "—")}</strong></td>
    <td style="color:var(--muted-foreground);">${escapeHtml(a.customer_name || "—")}</td>
    <td style="color:var(--muted-foreground);">${a.allocated_date || "—"}</td>
    <td>${reStatusBadge(a.status)}</td>
    <td><div class="table-actions">
      ${a.status === "active" && canAction("realestate", "create") ? `<button class="btn btn-success btn-sm" onclick="convertAllocation(${a.id})">${t("re.convertToContract")}</button>` : ""}
      ${canAction("realestate", "edit") ? `<button class="btn btn-secondary btn-sm" onclick='editAllocation(${JSON.stringify(a)})'>${t("common.edit")}</button>` : ""}
      ${canAction("realestate", "delete") ? `<button class="btn btn-danger btn-sm" onclick="deleteAllocation(${a.id})">${t("common.delete")}</button>` : ""}
    </div></td></tr>`).join("");
}

function openAllocationModal() {
  document.getElementById("allocation-modal-title").textContent = t("re.newAllocation");
  document.getElementById("allocation-id").value = "";
  document.getElementById("allocation-unit").value = "";
  document.getElementById("allocation-customer").value = "";
  document.getElementById("allocation-date").value = new Date().toISOString().slice(0, 10);
  document.getElementById("allocation-notes").value = "";
  populateCommonSelects();
  document.getElementById("allocation-modal").classList.add("active");
}

function editAllocation(a) {
  document.getElementById("allocation-modal-title").textContent = t("re.editAllocation");
  document.getElementById("allocation-id").value = a.id;
  populateCommonSelects();
  document.getElementById("allocation-unit").value = a.unit_id;
  document.getElementById("allocation-customer").value = a.customer_id || "";
  document.getElementById("allocation-date").value = a.allocated_date || new Date().toISOString().slice(0, 10);
  document.getElementById("allocation-notes").value = a.notes || "";
  document.getElementById("allocation-modal").classList.add("active");
}

async function saveAllocation() {
  const id = document.getElementById("allocation-id").value;
  const unitId = parseInt(document.getElementById("allocation-unit").value);
  if (!unitId) { showToast(t("common.required"), "warning"); return; }
  const body = {
    unit_id: unitId,
    customer_id: parseInt(document.getElementById("allocation-customer").value) || null,
    allocated_date: document.getElementById("allocation-date").value,
    notes: document.getElementById("allocation-notes").value,
  };
  try {
    if (id) await api.put(`${RE_API}/allocations/${id}`, body);
    else await api.post(RE_API + "/allocations", body);
    showToast(t("common.saved"));
    closeModal("allocation-modal");
    loadAllocations();
    allUnits = await api.get("/api/units");
    renderUnits(); renderSummary();
  } catch (err) { showToast(err.message, "error"); }
}

async function deleteAllocation(id) {
  if (!confirm(t("re.confirmDeleteAllocation"))) return;
  try {
    await api.delete(`${RE_API}/allocations/${id}`);
    showToast(t("common.deleted"));
    loadAllocations();
    allUnits = await api.get("/api/units");
    renderUnits(); renderSummary();
  } catch (err) { showToast(err.message, "error"); }
}

async function convertAllocation(id) {
  if (!confirm(t("re.convertToContract") + "?")) return;
  try {
    await api.post(`${RE_API}/allocations/${id}/convert`, {});
    showToast(t("re.allocationConverted"));
    loadAllocations(); loadContracts();
    allUnits = await api.get("/api/units");
    renderUnits(); renderSummary();
  } catch (err) { showToast(err.message, "error"); }
}

window.openAllocationModal = openAllocationModal;
window.editAllocation = editAllocation;
window.saveAllocation = saveAllocation;
window.deleteAllocation = deleteAllocation;
window.convertAllocation = convertAllocation;

// ============ SALES CONTRACTS ============
async function loadContracts() {
  try {
    allContracts = await api.get(RE_API + "/sales-contracts");
    renderContracts();
    populateCommonSelects();
  } catch (e) { toastError(e); }
}

function renderContracts() {
  const tbody = document.getElementById("contracts-table");
  if (!allContracts.length) {
    tbody.innerHTML = `<tr><td colspan="8"><div class="empty-state">${t("re.noContracts")}</div></td></tr>`;
    return;
  }
  tbody.innerHTML = allContracts.map((c) => `<tr>
    <td><strong>${escapeHtml(c.contract_number)}</strong></td>
    <td style="color:var(--muted-foreground);">${escapeHtml(c.unit_code || "—")}</td>
    <td style="color:var(--muted-foreground);">${escapeHtml(c.customer_name || "—")}</td>
    <td><strong>${formatMoney(c.total_amount)}</strong></td>
    <td style="color:var(--muted-foreground);">${formatMoney(c.discount)}</td>
    <td style="color:var(--primary);"><strong>${formatMoney(c.net_amount)}</strong></td>
    <td>${reStatusBadge(c.status)}</td>
    <td><div class="table-actions">
      ${c.status === "active" && !c.payment_plan_id && canAction("realestate", "create") ? `<button class="btn btn-success btn-sm" onclick="generatePlanContract(${c.id})">${t("re.generatePlan")}</button>` : ""}
      ${c.status === "active" && canAction("realestate", "edit") ? `<button class="btn btn-success btn-sm" onclick="completeContract(${c.id})">${t("re.completeContract")}</button>` : ""}
      ${c.status === "active" && canAction("realestate", "edit") ? `<button class="btn btn-warning btn-sm" onclick="cancelContract(${c.id})">${t("re.cancelContract")}</button>` : ""}
      ${canAction("realestate", "edit") ? `<button class="btn btn-secondary btn-sm" onclick='editContract(${JSON.stringify(c)})'>${t("common.edit")}</button>` : ""}
      ${canAction("realestate", "delete") ? `<button class="btn btn-danger btn-sm" onclick="deleteContract(${c.id})">${t("common.delete")}</button>` : ""}
    </div></td></tr>`).join("");
}

function openContractModal() {
  document.getElementById("contract-modal-title").textContent = t("re.newContract");
  document.getElementById("contract-id").value = "";
  document.getElementById("contract-number").value = "";
  document.getElementById("contract-date").value = new Date().toISOString().slice(0, 10);
  document.getElementById("contract-unit").value = "";
  document.getElementById("contract-customer").value = "";
  document.getElementById("contract-total").value = "";
  document.getElementById("contract-discount").value = "";
  document.getElementById("contract-notes").value = "";
  populateCommonSelects();
  document.getElementById("contract-modal").classList.add("active");
}

function editContract(c) {
  document.getElementById("contract-modal-title").textContent = t("re.editContract");
  document.getElementById("contract-id").value = c.id;
  document.getElementById("contract-number").value = c.contract_number;
  document.getElementById("contract-date").value = c.contract_date || new Date().toISOString().slice(0, 10);
  populateCommonSelects();
  document.getElementById("contract-unit").value = c.unit_id;
  document.getElementById("contract-customer").value = c.customer_id || "";
  document.getElementById("contract-total").value = c.total_amount;
  document.getElementById("contract-discount").value = c.discount;
  document.getElementById("contract-notes").value = c.notes || "";
  document.getElementById("contract-modal").classList.add("active");
}

async function saveContract() {
  const id = document.getElementById("contract-id").value;
  const unitId = parseInt(document.getElementById("contract-unit").value);
  if (!unitId) { showToast(t("common.required"), "warning"); return; }
  const total = parseFloat(document.getElementById("contract-total").value) || 0;
  const discount = parseFloat(document.getElementById("contract-discount").value) || 0;
  const body = {
    unit_id: unitId,
    customer_id: parseInt(document.getElementById("contract-customer").value) || null,
    contract_number: document.getElementById("contract-number").value,
    contract_date: document.getElementById("contract-date").value,
    total_amount: total,
    discount: discount,
    net_amount: total - discount,
    notes: document.getElementById("contract-notes").value,
  };
  try {
    if (id) await api.put(`${RE_API}/sales-contracts/${id}`, body);
    else await api.post(RE_API + "/sales-contracts", body);
    showToast(t("common.saved"));
    closeModal("contract-modal");
    loadContracts();
    allUnits = await api.get("/api/units");
    renderUnits(); renderSummary();
  } catch (err) { showToast(err.message, "error"); }
}

async function deleteContract(id) {
  if (!confirm(t("re.confirmDeleteContract"))) return;
  try {
    await api.delete(`${RE_API}/sales-contracts/${id}`);
    showToast(t("common.deleted"));
    loadContracts();
    allUnits = await api.get("/api/units");
    renderUnits(); renderSummary();
  } catch (err) { showToast(err.message, "error"); }
}

async function completeContract(id) {
  if (!confirm(t("re.completeContract") + "?")) return;
  try {
    await api.post(`${RE_API}/sales-contracts/${id}/complete`, {});
    showToast(t("re.contractCompleted"));
    loadContracts();
  } catch (err) { showToast(err.message, "error"); }
}

async function cancelContract(id) {
  if (!confirm(t("re.cancelContract") + "?")) return;
  try {
    await api.post(`${RE_API}/sales-contracts/${id}/cancel`, {});
    showToast(t("re.contractCancelled"));
    loadContracts();
    allUnits = await api.get("/api/units");
    renderUnits(); renderSummary();
  } catch (err) { showToast(err.message, "error"); }
}

async function generatePlanContract(id) {
  const months = prompt(t("plans.months"), "12");
  if (!months || parseInt(months) <= 0) return;
  try {
    await api.post(`${RE_API}/sales-contracts/${id}/generate-plan`, { months: parseInt(months) });
    showToast(t("re.contractPlanGenerated"));
    loadContracts();
    allPlans = await api.get("/api/payment-plans");
    renderPlans();
  } catch (err) { showToast(err.message, "error"); }
}

window.openContractModal = openContractModal;
window.editContract = editContract;
window.saveContract = saveContract;
window.deleteContract = deleteContract;
window.completeContract = completeContract;
window.cancelContract = cancelContract;
window.generatePlanContract = generatePlanContract;

// ============ PAYMENT PLANS ============
let editingPlanId = null;
const PLAN_STRUCT_FIELDS = ["plan-unit", "plan-down", "plan-start", "plan-months", "plan-monthly", "plan-year"];

function renderPlans() {
  const year = selectedFinancialYear("filter-year-plans");
  const rows = year ? allPlans.filter((p) => p.financial_year_id === year) : allPlans;
  const tbody = document.getElementById("plans-table");
  if (!rows.length) {
    tbody.innerHTML = `<tr><td colspan="9"><div class="empty-state"><div class="empty-icon">💳</div>${t("plans.noPlans")}</div></td></tr>`;
    return;
  }
  tbody.innerHTML = rows.map((p) => {
    const unit = allUnits.find((u) => u.id === p.unit_id);
    const customer = allCustomers.find((c) => c.id === p.customer_id);
    return `
    <tr>
      <td><strong>${unit ? escapeHtml(unit.unit_code) : "—"}</strong>
        ${p.financial_year_name ? `<div class="table-sub">${t("financialYears.year")}: ${escapeHtml(p.financial_year_name)}</div>` : ""}
      </td>
      <td style="color:var(--muted-foreground);">${customer ? escapeHtml(customer.full_name) : "—"}</td>
      <td><strong>${moneyWithCurrency(p.total_amount, p)}</strong></td>
      <td style="color:var(--muted-foreground);">${moneyWithCurrency(p.down_payment, p)}</td>
      <td style="color:var(--emerald);">${moneyWithCurrency(p.paid, p)}</td>
      <td style="color:${p.balance > 0 ? "var(--amber)" : "var(--muted-foreground)"};"><strong>${moneyWithCurrency(p.balance, p)}</strong></td>
      <td style="color:var(--muted-foreground);">${p.months}</td>
      <td>${statusBadge(p.status)}</td>
      <td>
        <div class="table-actions">
          <button class="btn btn-secondary btn-sm" onclick="openInstallments(${p.id})">${t("plans.installments")}</button>
          ${canAction("realestate", "edit") ? `<button class="btn btn-secondary btn-sm" onclick="editPlan(${p.id})">${t("plans.editPlan")}</button>` : ""}
          ${canAction("realestate", "delete") ? `<button class="btn btn-danger btn-sm" onclick="deletePlan(${p.id})">${t("common.delete")}</button>` : ""}
        </div>
      </td>
    </tr>`;
  }).join("");
}

function populatePlanSelects() {
  const unitSelect = document.getElementById("plan-unit");
  const hasPlan = new Set(allPlans.map((p) => p.unit_id));
  const eligible = allUnits.filter((u) => u.status === "sold" || u.status === "reserved" || hasPlan.has(u.id));
  unitSelect.innerHTML = eligible.map((u) => `<option value="${u.id}">${escapeHtml(u.unit_code)}</option>`).join("") || `<option value="">${t("realestate.noUnits")}</option>`;
  const customerSelect = document.getElementById("plan-customer");
  customerSelect.innerHTML = `<option value="">${t("common.choose")}</option>` + allCustomers.map((c) => `<option value="${c.id}">${escapeHtml(c.full_name)}</option>`).join("");
}

function refreshPlanSummary(total, down, months, monthly) {
  const el = document.getElementById("plan-summary");
  el.textContent = t("plans.summary").replace("{total}", formatMoney(total)).replace("{down}", formatMoney(down)).replace("{months}", months).replace("{monthly}", formatMoney(monthly));
}

function updatePlanSummary() {
  const unit = allUnits.find((u) => u.id === parseInt(document.getElementById("plan-unit").value));
  const total = unit ? unit.price : 0;
  const down = parseFloat(document.getElementById("plan-down").value) || 0;
  const months = parseInt(document.getElementById("plan-months").value) || 0;
  const monthly = months > 0 && total > down ? (total - down) / months : 0;
  document.getElementById("plan-monthly").value = monthly ? monthly.toFixed(2) : "";
  refreshPlanSummary(total, down, months, monthly);
}

function openPlanModal() {
  editingPlanId = null;
  populatePlanSelects();
  ["plan-down", "plan-start", "plan-monthly"].forEach((id) => document.getElementById(id).value = "");
  document.getElementById("plan-months").value = 12;
  document.getElementById("plan-start").value = new Date().toISOString().slice(0, 10);
  fillFinancialYearSelect("plan-year");
  PLAN_STRUCT_FIELDS.forEach((id) => document.getElementById(id).disabled = false);
  document.getElementById("plan-modal-title").textContent = t("plans.newPlan");
  updatePlanSummary();
  document.getElementById("plan-modal").classList.add("active");
}

function editPlan(p) {
  editingPlanId = p.id;
  populatePlanSelects();
  document.getElementById("plan-unit").value = p.unit_id;
  document.getElementById("plan-customer").value = p.customer_id || "";
  document.getElementById("plan-down").value = p.down_payment;
  document.getElementById("plan-start").value = p.start_date || new Date().toISOString().slice(0, 10);
  document.getElementById("plan-months").value = p.months;
  document.getElementById("plan-monthly").value = p.monthly_amount;
  fillFinancialYearSelect("plan-year");
  document.getElementById("plan-year").value = p.financial_year_id || "";
  const locked = p.paid > 0;
  PLAN_STRUCT_FIELDS.forEach((id) => document.getElementById(id).disabled = locked);
  refreshPlanSummary(p.total_amount, p.down_payment, p.months, p.monthly_amount);
  document.getElementById("plan-modal-title").textContent = t("plans.editPlan");
  document.getElementById("plan-modal").classList.add("active");
}

async function savePlan() {
  const unit_id = parseInt(document.getElementById("plan-unit").value);
  if (!unit_id) { showToast(t("plans.unitRequired"), "warning"); return; }
  const body = {
    unit_id,
    customer_id: parseInt(document.getElementById("plan-customer").value) || null,
    down_payment: parseFloat(document.getElementById("plan-down").value) || 0,
    financial_year_id: financialYearValue("plan-year"),
    start_date: document.getElementById("plan-start").value,
    months: parseInt(document.getElementById("plan-months").value) || 1,
    monthly_amount: parseFloat(document.getElementById("plan-monthly").value) || 0,
  };
  try {
    if (editingPlanId) await api.put(`/api/payment-plans/${editingPlanId}`, body);
    else await api.post("/api/payment-plans", body);
    showToast(t("common.saved"));
    closeModal("plan-modal");
    [allPlans, allUnits] = await Promise.all([api.get("/api/payment-plans"), api.get("/api/units")]);
    renderPlans(); renderUnits(); renderSummary();
  } catch (err) { showToast(err.message, "error"); }
}

async function deletePlan(id) {
  if (!confirm(t("common.confirmDelete"))) return;
  try {
    await api.delete(`/api/payment-plans/${id}`);
    showToast(t("common.deleted"));
    allPlans = await api.get("/api/payment-plans");
    renderPlans();
  } catch (err) { showToast(err.message, "error"); }
}

// ===== Installments =====
function openInstallments(planId) {
  currentPlan = allPlans.find((p) => p.id === planId);
  if (!currentPlan) return;
  const unit = allUnits.find((u) => u.id === currentPlan.unit_id);
  document.getElementById("installments-modal-title").textContent = `${t("plans.installments")} — ${unit ? unit.unit_code : ""}`;
  const tbody = document.getElementById("installments-table");
  tbody.innerHTML = currentPlan.installments.map((i) => `
    <tr>
      <td>${i.installment_number}</td>
      <td><strong>${formatMoney(i.amount)}</strong></td>
      <td style="color:var(--muted-foreground);">${i.due_date || "—"}</td>
      <td style="color:var(--emerald);">${formatMoney(i.paid_amount)}</td>
      <td>${statusBadge(i.status)}</td>
      <td>${i.status === "paid" ? "" : (canAction("realestate", "edit") ? `<button class="btn btn-secondary btn-sm" onclick="openPayment(${i.id})">${t("plans.recordPayment")}</button>` : "")}</td>
    </tr>`).join("") || `<tr><td colspan="6"><div class="empty-state">${t("plans.noPlans")}</div></td></tr>`;
  document.getElementById("installments-modal").classList.add("active");
}

// ===== Payment =====
function openPayment(installmentId) {
  currentInstallment = currentPlan.installments.find((i) => i.id === installmentId);
  if (!currentInstallment) return;
  document.getElementById("payment-amount").value = currentInstallment.balance;
  document.getElementById("payment-date").value = new Date().toISOString().slice(0, 10);
  document.getElementById("payment-summary").textContent = `${t("plans.amount")}: ${formatMoney(currentInstallment.amount)} · ${t("plans.colBalance")}: ${formatMoney(currentInstallment.balance)}`;
  document.getElementById("payment-modal").classList.add("active");
}

async function savePayment() {
  if (!currentInstallment) return;
  const amount = parseFloat(document.getElementById("payment-amount").value) || 0;
  if (amount <= 0) { showToast(t("common.required"), "warning"); return; }
  const body = { paid_amount: amount, paid_date: document.getElementById("payment-date").value };
  try {
    await api.put(`/api/installments/${currentInstallment.id}`, body);
    showToast(t("plans.paymentSaved"));
    closeModal("payment-modal");
    allPlans = await api.get("/api/payment-plans");
    renderPlans();
    const unit = allUnits.find((u) => u.id === currentPlan.unit_id);
    const fresh = allPlans.find((p) => p.id === currentPlan.id);
    currentPlan = fresh;
    document.getElementById("installments-modal-title").textContent = `${t("plans.installments")} — ${unit ? unit.unit_code : ""}`;
    document.getElementById("installments-table").innerHTML = fresh.installments.map((i) => `
      <tr>
        <td>${i.installment_number}</td>
        <td><strong>${formatMoney(i.amount)}</strong></td>
        <td style="color:var(--muted-foreground);">${i.due_date || "—"}</td>
        <td style="color:var(--emerald);">${formatMoney(i.paid_amount)}</td>
        <td>${statusBadge(i.status)}</td>
        <td>${i.status === "paid" ? "" : (canAction("realestate", "edit") ? `<button class="btn btn-secondary btn-sm" onclick="openPayment(${i.id})">${t("plans.recordPayment")}</button>` : "")}</td>
      </tr>`).join("");
  } catch (err) { showToast(err.message, "error"); }
}

window.renderPlans = renderPlans;
window.openPlanModal = openPlanModal;
window.openInstallments = openInstallments;
window.openPayment = openPayment;
window.savePayment = savePayment;
window.savePlan = savePlan;
window.deletePlan = deletePlan;
window.editPlan = editPlan;

// ============ COMMISSIONS ============
async function loadCommissions() {
  try {
    allCommissions = await api.get(RE_API + "/commissions");
    renderCommissions();
    if (typeof updateBrokerKpis === "function") updateBrokerKpis();
  } catch (e) { toastError(e); }
}

function renderCommissions() {
  const tbody = document.getElementById("commissions-table");
  if (!allCommissions.length) {
    tbody.innerHTML = `<tr><td colspan="8"><div class="empty-state">${t("re.noCommissions")}</div></td></tr>`;
    return;
  }
  tbody.innerHTML = allCommissions.map((c) => `<tr>
    <td><strong>${escapeHtml(c.contract_number || "—")}</strong></td>
    <td style="color:var(--muted-foreground);">${escapeHtml(c.employee_name || "—")}${c.broker_name ? `<br><small>${t("re.commissionBroker")}: ${escapeHtml(c.broker_name)}</small>` : ""}</td>
    <td>${c.rate}%</td>
    <td><strong>${formatMoney(c.amount)}</strong></td>
    <td style="color:var(--muted-foreground);">${c.due_date || "—"}</td>
    <td style="color:var(--muted-foreground);">${c.paid_date || "—"}</td>
    <td>${reStatusBadge(c.status)}</td>
    <td><div class="table-actions">
      ${c.status === "pending" && canAction("realestate", "edit") ? `<button class="btn btn-success btn-sm" onclick="payCommission(${c.id})">${t("re.markPaid")}</button>` : ""}
      ${canAction("realestate", "edit") ? `<button class="btn btn-secondary btn-sm" onclick='editCommission(${JSON.stringify(c)})'>${t("common.edit")}</button>` : ""}
      ${canAction("realestate", "delete") ? `<button class="btn btn-danger btn-sm" onclick="deleteCommission(${c.id})">${t("common.delete")}</button>` : ""}
    </div></td></tr>`).join("");
}

function openCommissionModal() {
  document.getElementById("commission-modal-title").textContent = t("re.newCommission");
  document.getElementById("commission-id").value = "";
  document.getElementById("commission-contract-id").value = "";
  document.getElementById("commission-employee").value = "";
  document.getElementById("commission-broker").value = "";
  document.getElementById("commission-rate").value = "";
  document.getElementById("commission-amount").value = "";
  document.getElementById("commission-due").value = "";
  document.getElementById("commission-notes").value = "";
  populateCommonSelects();
  populateBrokerSelect();
  document.getElementById("commission-modal").classList.add("active");
}

async function populateBrokerSelect() {
  const sel = document.getElementById("commission-broker");
  if (!sel) return;
  if (!allBrokers.length) await loadBrokers();
  sel.innerHTML = `<option value="">${t("common.none") || "—"}</option>` +
    allBrokers.filter((b) => b.is_active).map((b) =>
      `<option value="${b.id}">${escapeHtml(b.name)}${b.agency_name ? " — " + escapeHtml(b.agency_name) : ""}</option>`).join("");
}

function editCommission(c) {
  document.getElementById("commission-modal-title").textContent = t("re.editCommission");
  document.getElementById("commission-id").value = c.id;
  document.getElementById("commission-contract-id").value = c.contract_id || "";
  populateCommonSelects();
  populateBrokerSelect().then(() => {
    document.getElementById("commission-broker").value = c.broker_id || "";
  });
  document.getElementById("commission-employee").value = c.employee_id || "";
  document.getElementById("commission-rate").value = c.rate;
  document.getElementById("commission-amount").value = c.amount;
  document.getElementById("commission-due").value = c.due_date || "";
  document.getElementById("commission-notes").value = c.notes || "";
  document.getElementById("commission-modal").classList.add("active");
}

async function saveCommission() {
  const id = document.getElementById("commission-id").value;
  const employeeId = parseInt(document.getElementById("commission-employee").value);
  const brokerId = parseInt(document.getElementById("commission-broker").value);
  if (!employeeId && !brokerId) { showToast(t("common.required"), "warning"); return; }
  const body = {
    contract_id: parseInt(document.getElementById("commission-contract-id").value) || null,
    employee_id: employeeId || null,
    broker_id: brokerId || null,
    rate: parseFloat(document.getElementById("commission-rate").value) || 0,
    amount: document.getElementById("commission-amount").value,
    due_date: document.getElementById("commission-due").value,
    notes: document.getElementById("commission-notes").value,
  };
  try {
    if (id) await api.put(`${RE_API}/commissions/${id}`, body);
    else await api.post(RE_API + "/commissions", body);
    showToast(t("common.saved"));
    closeModal("commission-modal");
    loadCommissions();
  } catch (err) { showToast(err.message, "error"); }
}

async function deleteCommission(id) {
  if (!confirm(t("re.confirmDeleteCommission"))) return;
  try {
    await api.delete(`${RE_API}/commissions/${id}`);
    showToast(t("common.deleted"));
    loadCommissions();
  } catch (err) { showToast(err.message, "error"); }
}

async function payCommission(id) {
  try {
    await api.post(`${RE_API}/commissions/${id}/pay`, {});
    showToast(t("re.commissionPaid"));
    loadCommissions();
  } catch (err) { showToast(err.message, "error"); }
}

window.openCommissionModal = openCommissionModal;
window.editCommission = editCommission;
window.saveCommission = saveCommission;
window.deleteCommission = deleteCommission;
window.payCommission = payCommission;

// ============ BROKERS (السماسرة العقارية) ============
let allBrokers = [];

async function loadBrokers() {
  try {
    allBrokers = await api.get(RE_API + "/brokers");
    renderBrokers();
    updateBrokerKpis();
  } catch (e) { toastError(e); }
}

function updateBrokerKpis() {
  const totalEl = document.getElementById("broker-total");
  const activeEl = document.getElementById("broker-active");
  if (!totalEl) return;
  totalEl.textContent = allBrokers.length;
  activeEl.textContent = allBrokers.filter((b) => b.is_active).length;
  const commEl = document.getElementById("broker-commissions");
  if (commEl && typeof allCommissions !== "undefined") {
    const brokerComms = allCommissions.filter((c) => c.broker_id);
    commEl.textContent = formatMoney(brokerComms.reduce((s, c) => s + (c.amount || 0), 0));
  }
}

function renderBrokers() {
  const tbody = document.getElementById("brokers-table");
  if (!tbody) return;
  if (!allBrokers.length) {
    tbody.innerHTML = `<tr><td colspan="7"><div class="empty-state">${t("re.noBrokers")}</div></td></tr>`;
    return;
  }
  tbody.innerHTML = allBrokers.map((b) => `<tr>
    <td><strong>${escapeHtml(b.name)}</strong></td>
    <td style="color:var(--muted-foreground);">${escapeHtml(b.agency_name || "—")}</td>
    <td style="color:var(--muted-foreground);">${escapeHtml(b.phone || "—")}</td>
    <td style="color:var(--muted-foreground);">${escapeHtml(b.email || "—")}</td>
    <td>${b.default_rate}%</td>
    <td>${b.is_active
      ? `<span class="badge badge-success">${t("re.brokerActive")}</span>`
      : `<span class="badge badge-muted">${t("re.brokerInactive")}</span>`}</td>
    <td><div class="table-actions">
      ${canAction("realestate", "edit") ? `<button class="btn btn-secondary btn-sm" onclick='editBroker(${JSON.stringify(b)})'>${t("common.edit")}</button>` : ""}
      ${canAction("realestate", "delete") ? `<button class="btn btn-danger btn-sm" onclick="deleteBroker(${b.id})">${t("common.delete")}</button>` : ""}
    </div></td></tr>`).join("");
}

function openBrokerModal() {
  document.getElementById("broker-modal-title").textContent = t("re.newBroker");
  document.getElementById("broker-id").value = "";
  document.getElementById("broker-name").value = "";
  document.getElementById("broker-agency").value = "";
  document.getElementById("broker-phone").value = "";
  document.getElementById("broker-email").value = "";
  document.getElementById("broker-idnumber").value = "";
  document.getElementById("broker-rate").value = "0";
  document.getElementById("broker-active").checked = true;
  document.getElementById("broker-notes").value = "";
  document.getElementById("broker-modal").classList.add("active");
}

function editBroker(b) {
  document.getElementById("broker-modal-title").textContent = t("re.editBroker");
  document.getElementById("broker-id").value = b.id;
  document.getElementById("broker-name").value = b.name || "";
  document.getElementById("broker-agency").value = b.agency_name || "";
  document.getElementById("broker-phone").value = b.phone || "";
  document.getElementById("broker-email").value = b.email || "";
  document.getElementById("broker-idnumber").value = b.id_number || "";
  document.getElementById("broker-rate").value = b.default_rate || 0;
  document.getElementById("broker-active").checked = !!b.is_active;
  document.getElementById("broker-notes").value = b.notes || "";
  document.getElementById("broker-modal").classList.add("active");
}

async function saveBroker() {
  const id = document.getElementById("broker-id").value;
  const name = document.getElementById("broker-name").value.trim();
  if (!name) { showToast(t("common.required"), "warning"); return; }
  const body = {
    name,
    agency_name: document.getElementById("broker-agency").value.trim(),
    phone: document.getElementById("broker-phone").value.trim(),
    email: document.getElementById("broker-email").value.trim(),
    id_number: document.getElementById("broker-idnumber").value.trim(),
    default_rate: parseFloat(document.getElementById("broker-rate").value) || 0,
    is_active: document.getElementById("broker-active").checked,
    notes: document.getElementById("broker-notes").value.trim(),
  };
  try {
    if (id) await api.put(`${RE_API}/brokers/${id}`, body);
    else await api.post(RE_API + "/brokers", body);
    showToast(t("common.saved"));
    closeModal("broker-modal");
    loadBrokers();
  } catch (err) { showToast(err.message, "error"); }
}

async function deleteBroker(id) {
  if (!confirm(t("re.confirmDeleteBroker"))) return;
  try {
    const res = await api.del(`${RE_API}/brokers/${id}`);
    showToast(res && res.deactivated ? t("re.brokerDeactivated") : t("common.deleted"));
    loadBrokers();
  } catch (err) { toastError(err); }
}

window.loadBrokers = loadBrokers;
window.openBrokerModal = openBrokerModal;
window.editBroker = editBroker;
window.saveBroker = saveBroker;
window.deleteBroker = deleteBroker;

// ============ ANALYTICS (تحليلات الإشغال) ============
async function loadAnalytics() {
  try {
    const pid = document.getElementById("analytics-project")?.value || "";
    const j = await api.get(RE_API + "/analytics/occupancy" + (pid ? `?project_id=${pid}` : ""));
    const o = j.overall || {};
    setText("an-total", o.total_units || 0);
    setText("an-available", o.available_units || 0);
    setText("an-occupancy", (o.occupancy_rate ?? 0) + "%");
    setText("an-vacancy", (o.vacancy_rate ?? 0) + "%");
    const tbody = document.getElementById("analytics-table");
    const rows = j.per_project || [];
    tbody.innerHTML = rows.length ? rows.map((p) => `<tr>
      <td><strong>${escapeHtml(p.project_name || "—")}</strong></td>
      <td>${p.total_units || 0}</td>
      <td>${p.occupied_units || 0}</td>
      <td><strong style="color:var(--primary);">${p.occupancy_rate || 0}%</strong></td>
    </tr>`).join("") : `<tr><td colspan="4"><div class="empty-state">${t("re.noData")}</div></td></tr>`;
  } catch (e) { toastError(e); }
}

function setText(id, v) {
  const el = document.getElementById(id);
  if (el) el.textContent = v;
}
window.loadAnalytics = loadAnalytics;

// ============ SCREENINGS (فحص الاستادة KYC) ============
let allScreenings = [];

async function loadScreenings() {
  try {
    const r = await api.get(RE_API + "/screenings");
    allScreenings = Array.isArray(r) ? r : (r.items || []);
    renderScreenings();
  } catch (e) { toastError(e); }
}

function renderScreenings() {
  const tbody = document.getElementById("screenings-table");
  if (!tbody) return;
  if (!allScreenings.length) {
    tbody.innerHTML = `<tr><td colspan="7"><div class="empty-state">${t("re.noScreenings")}</div></td></tr>`;
    return;
  }
  const creditBadge = (s) => ({
    good: "success", fair: "muted", bad: "danger", unknown: "muted",
  })[s] || "muted";
  tbody.innerHTML = allScreenings.map((s) => `<tr>
    <td><strong>${escapeHtml(s.customer_name || s.customer_id)}</strong></td>
    <td>${formatMoney(s.monthly_income)}</td>
    <td style="color:var(--muted-foreground);">${escapeHtml(s.employer || "—")}</td>
    <td><span class="badge badge-${creditBadge(s.credit_status)}">${t("re.credit_" + (s.credit_status || "unknown"))}</span></td>
    <td>${s.blacklist ? `<span class="badge badge-danger">${t("re.blacklist")}</span>` : "—"}</td>
    <td><span class="badge badge-${s.result === "approved" ? "success" : s.result === "rejected" ? "danger" : "muted"}">${t("re.result_" + (s.result || "pending"))}</span></td>
    <td><div class="table-actions">
      ${canAction("realestate", "delete") ? `<button class="btn btn-danger btn-sm" onclick="deleteScreening(${s.id})">${t("common.delete")}</button>` : ""}
    </div></td></tr>`).join("");
}

async function openScreeningModal() {
  await populateScreeningCustomers();
  ["screening-income", "screening-employer", "screening-notes"].forEach((id) =>
    document.getElementById(id).value = "");
  document.getElementById("screening-blacklist").checked = false;
  document.getElementById("screening-credit").value = "unknown";
  document.getElementById("screening-modal").classList.add("active");
}

async function populateScreeningCustomers() {
  let customers = [];
  try {
    const r = await api.get("/api/customers");
    customers = Array.isArray(r) ? r : (r.items || []);
  } catch (e) {}
  document.getElementById("screening-customer").innerHTML = customers.map((cu) =>
    `<option value="${cu.id}">${escapeHtml(cu.full_name)}</option>`).join("");
}

async function saveScreening() {
  const body = {
    customer_id: parseInt(document.getElementById("screening-customer").value) || null,
    monthly_income: parseFloat(document.getElementById("screening-income").value) || 0,
    employer: document.getElementById("screening-employer").value.trim(),
    credit_status: document.getElementById("screening-credit").value,
    blacklist: document.getElementById("screening-blacklist").checked,
    notes: document.getElementById("screening-notes").value.trim(),
  };
  if (!body.customer_id) { showToast(t("common.required"), "warning"); return; }
  try {
    await api.post(RE_API + "/screenings", body);
    showToast(t("common.saved"));
    closeModal("screening-modal");
    loadScreenings();
  } catch (err) { showToast(err.message, "error"); }
}

async function deleteScreening(id) {
  if (!confirm(t("re.confirmDeleteScreening"))) return;
  try {
    await api.del(`${RE_API}/screenings/${id}`);
    showToast(t("common.deleted"));
    loadScreenings();
  } catch (err) { toastError(err); }
}

window.openScreeningModal = openScreeningModal;
window.saveScreening = saveScreening;
window.deleteScreening = deleteScreening;

// ============ MORTGAGES (الرهون العقارية) ============
let allMortgages = [];

async function loadMortgages() {
  try {
    const r = await api.get(RE_API + "/mortgages");
    allMortgages = Array.isArray(r) ? r : (r.items || []);
    renderMortgages();
  } catch (e) { toastError(e); }
}

function renderMortgages() {
  const tbody = document.getElementById("mortgages-table");
  if (!tbody) return;
  if (!allMortgages.length) {
    tbody.innerHTML = `<tr><td colspan="8"><div class="empty-state">${t("re.noMortgages")}</div></td></tr>`;
    return;
  }
  tbody.innerHTML = allMortgages.map((m) => `<tr>
    <td><strong>${escapeHtml(m.unit_code || "—")}</strong></td>
    <td>${escapeHtml(m.lender_name)}</td>
    <td><strong>${formatMoney(m.loan_amount)}</strong></td>
    <td>${m.ltv_percent}%</td>
    <td>${m.interest_rate}%</td>
    <td style="color:var(--muted-foreground);">${escapeHtml(m.lien_number || "—")}</td>
    <td><span class="badge badge-${m.status === "active" ? "warning" : m.status === "settled" ? "success" : "danger"}">${t("re.mortgage_" + m.status)}</span></td>
    <td><div class="table-actions">
      ${m.status === "active" && canAction("realestate", "edit") ? `<button class="btn btn-success btn-sm" onclick="settleMortgage(${m.id})">${t("re.settle")}</button>` : ""}
      ${canAction("realestate", "delete") && m.status !== "active" ? `<button class="btn btn-danger btn-sm" onclick="deleteMortgage(${m.id})">${t("common.delete")}</button>` : ""}
    </div></td></tr>`).join("");
}

async function openMortgageModal() {
  const sel = document.getElementById("mortgage-unit");
  sel.innerHTML = (allUnits || []).map((u) =>
    `<option value="${u.id}">${escapeHtml(u.unit_code)}</option>`).join("");
  ["mortgage-lender", "mortgage-loan", "mortgage-ltv", "mortgage-interest",
   "mortgage-lien", "mortgage-notes"].forEach((id) => document.getElementById(id).value = "");
  document.getElementById("mortgage-start").valueAsDate = new Date();
  document.getElementById("mortgage-end").value = "";
  document.getElementById("mortgage-modal").classList.add("active");
}

async function saveMortgage() {
  const body = {
    unit_id: parseInt(document.getElementById("mortgage-unit").value) || null,
    lender_name: document.getElementById("mortgage-lender").value.trim(),
    loan_amount: parseFloat(document.getElementById("mortgage-loan").value) || 0,
    ltv_percent: parseFloat(document.getElementById("mortgage-ltv").value) || 0,
    interest_rate: parseFloat(document.getElementById("mortgage-interest").value) || 0,
    lien_number: document.getElementById("mortgage-lien").value.trim(),
    start_date: document.getElementById("mortgage-start").value,
    end_date: document.getElementById("mortgage-end").value,
    notes: document.getElementById("mortgage-notes").value.trim(),
  };
  if (!body.unit_id || !body.lender_name || !body.loan_amount) {
    showToast(t("common.required"), "warning"); return;
  }
  try {
    await api.post(RE_API + "/mortgages", body);
    showToast(t("common.saved"));
    closeModal("mortgage-modal");
    loadMortgages();
  } catch (err) { showToast(err.message, "error"); }
}

async function settleMortgage(id) {
  if (!confirm(t("re.confirmSettle"))) return;
  try {
    await api.post(`${RE_API}/mortgages/${id}/settle`, {});
    showToast(t("common.saved"));
    loadMortgages();
  } catch (err) { toastError(err); }
}

async function deleteMortgage(id) {
  if (!confirm(t("re.confirmDeleteMortgage"))) return;
  try {
    await api.del(`${RE_API}/mortgages/${id}`);
    showToast(t("common.deleted"));
    loadMortgages();
  } catch (err) { toastError(err); }
}

window.openMortgageModal = openMortgageModal;
window.saveMortgage = saveMortgage;
window.settleMortgage = settleMortgage;
window.deleteMortgage = deleteMortgage;

// ============ SNAGGING CHECKLIST (بنود المطابقة) ============
let currentDeliveryId = null;

async function openChecklist(deliveryId) {
  currentDeliveryId = deliveryId;
  const d = (allDeliveries || []).find((x) => x.id === deliveryId);
  document.getElementById("checklist-title").textContent =
    `${t("re.checklistTitle")} — ${d?.unit_code || deliveryId}`;
  await renderChecklist();
  document.getElementById("checklist-modal").classList.add("active");
}

async function renderChecklist() {
  const items = await api.get(`${RE_API}/deliveries/${currentDeliveryId}/items`);
  const tbody = document.getElementById("checklist-table");
  tbody.innerHTML = items.length ? items.map((i) => `<tr>
    <td>${escapeHtml(i.description)}${i.notes ? `<br><small style="color:var(--muted-foreground);">${escapeHtml(i.notes)}</small>` : ""}</td>
    <td><span class="badge badge-${i.status === "ok" || i.status === "fixed" ? "success" : i.status === "issue" ? "danger" : "muted"}">${t("re.snag_" + i.status)}</span></td>
    <td><div class="table-actions">
      ${canAction("realestate", "edit") ? `
        <button class="btn btn-success btn-sm" onclick="setItemStatus(${i.id},'ok')">✓</button>
        <button class="btn btn-warning btn-sm" onclick="setItemStatus(${i.id},'fixed')">🔧</button>
        <button class="btn btn-danger btn-sm" onclick="setItemStatus(${i.id},'issue')">✕</button>` : ""}
    </div></td></tr>`).join("")
    : `<tr><td colspan="3"><div class="empty-state">${t("re.noChecklistItems")}</div></td></tr>`;
}

async function addChecklistItem() {
  const desc = document.getElementById("checklist-new-desc").value.trim();
  if (!desc) { showToast(t("common.required"), "warning"); return; }
  try {
    await api.post(`${RE_API}/deliveries/${currentDeliveryId}/items`, { description: desc });
    document.getElementById("checklist-new-desc").value = "";
    renderChecklist();
  } catch (err) { toastError(err); }
}

async function setItemStatus(itemId, status) {
  try {
    await api.put(`${RE_API}/checklist/${itemId}`, { status });
    renderChecklist();
  } catch (err) { toastError(err); }
}

async function completeDeliveryFromModal() {
  try {
    await api.post(`${RE_API}/deliveries/${currentDeliveryId}/complete`, {});
    showToast(t("re.deliveryCompleted"));
    closeModal("checklist-modal");
    loadDeliveries();
  } catch (err) { toastError(err); }
}

window.openChecklist = openChecklist;
window.addChecklistItem = addChecklistItem;
window.setItemStatus = setItemStatus;
window.completeDeliveryFromModal = completeDeliveryFromModal;

// ============ DISTRIBUTE REVENUE (توزيع الإيرادات) ============
function openDistributeModal() {
  const sel = document.getElementById("distribute-unit");
  sel.innerHTML = (allUnits || []).map((u) =>
    `<option value="${u.id}">${escapeHtml(u.unit_code)}</option>`).join("");
  document.getElementById("distribute-amount").value = "";
  document.getElementById("distribute-result").textContent = "";
  document.getElementById("distribute-modal").classList.add("active");
}

async function runDistribute() {
  const unitId = parseInt(document.getElementById("distribute-unit").value) || null;
  const amount = parseFloat(document.getElementById("distribute-amount").value) || 0;
  if (!unitId || amount <= 0) { showToast(t("common.required"), "warning"); return; }
  const box = document.getElementById("distribute-result");
  try {
    const res = await api.post(`${RE_API}/units/${unitId}/distribute-revenue`, { amount });
    box.textContent = (res.distribution || [])
      .map((r) => `${r.owner_name || ("#" + r.owner_id)} (${r.share_percent}%) → ${formatMoney(r.amount)}`)
      .join("  |  ") + `   Σ ${formatMoney(res.total_distributed)}`;
    showToast(t("re.distributed"));
  } catch (err) { box.textContent = ""; showToast(err.message, "error"); }
}

window.openDistributeModal = openDistributeModal;
window.runDistribute = runDistribute;

// ============ OWNERS ============
async function loadOwners() {
  try {
    allOwners = await api.get(RE_API + "/owners");
    renderOwners();
    populateCommonSelects();
  } catch (e) { toastError(e); }
}

function renderOwners() {
  const tbody = document.getElementById("owners-table");
  if (!allOwners.length) {
    tbody.innerHTML = `<tr><td colspan="6"><div class="empty-state">${t("re.noOwners")}</div></td></tr>`;
    return;
  }
  tbody.innerHTML = allOwners.map((o) => `<tr>
    <td><strong>${escapeHtml(o.full_name)}</strong></td>
    <td style="color:var(--muted-foreground);">${escapeHtml(o.id_number || "—")}</td>
    <td style="color:var(--muted-foreground);">${escapeHtml(o.phone || "—")}</td>
    <td style="color:var(--muted-foreground);">${escapeHtml(o.email || "—")}</td>
    <td>${o.type === "company" ? `<span class="badge badge-info">${t("re.company")}</span>` : `<span class="badge badge-secondary">${t("re.individual")}</span>`}</td>
    <td><div class="table-actions">
      ${canAction("realestate", "edit") ? `<button class="btn btn-secondary btn-sm" onclick='editOwner(${JSON.stringify(o)})'>${t("common.edit")}</button>` : ""}
      ${canAction("realestate", "delete") ? `<button class="btn btn-danger btn-sm" onclick="deleteOwner(${o.id})">${t("common.delete")}</button>` : ""}
    </div></td></tr>`).join("");
}

function openOwnerModal() {
  document.getElementById("owner-modal-title").textContent = t("re.newOwner");
  document.getElementById("owner-id").value = "";
  ["owner-name", "owner-idnumber", "owner-phone", "owner-email", "owner-address"].forEach((id) => document.getElementById(id).value = "");
  document.getElementById("owner-type").value = "individual";
  document.getElementById("owner-modal").classList.add("active");
}

function editOwner(o) {
  document.getElementById("owner-modal-title").textContent = t("re.editOwner");
  document.getElementById("owner-id").value = o.id;
  document.getElementById("owner-name").value = o.full_name;
  document.getElementById("owner-idnumber").value = o.id_number || "";
  document.getElementById("owner-phone").value = o.phone || "";
  document.getElementById("owner-email").value = o.email || "";
  document.getElementById("owner-type").value = o.type || "individual";
  document.getElementById("owner-address").value = o.address || "";
  document.getElementById("owner-modal").classList.add("active");
}

async function saveOwner() {
  const id = document.getElementById("owner-id").value;
  const body = {
    full_name: document.getElementById("owner-name").value,
    id_number: document.getElementById("owner-idnumber").value,
    phone: document.getElementById("owner-phone").value,
    email: document.getElementById("owner-email").value,
    type: document.getElementById("owner-type").value,
    address: document.getElementById("owner-address").value,
  };
  if (!body.full_name) { showToast(t("re.ownerNameRequired"), "warning"); return; }
  try {
    if (id) await api.put(`${RE_API}/owners/${id}`, body);
    else await api.post(RE_API + "/owners", body);
    showToast(t("common.saved"));
    closeModal("owner-modal");
    loadOwners();
  } catch (err) { showToast(err.message, "error"); }
}

async function deleteOwner(id) {
  if (!confirm(t("re.confirmDeleteOwner"))) return;
  try {
    await api.delete(`${RE_API}/owners/${id}`);
    showToast(t("common.deleted"));
    loadOwners();
  } catch (err) { showToast(err.message, "error"); }
}

window.openOwnerModal = openOwnerModal;
window.editOwner = editOwner;
window.saveOwner = saveOwner;
window.deleteOwner = deleteOwner;

// ============ DELIVERIES ============
async function loadDeliveries() {
  try {
    allDeliveries = await api.get(RE_API + "/deliveries");
    renderDeliveries();
  } catch (e) { toastError(e); }
}

function renderDeliveries() {
  const tbody = document.getElementById("deliveries-table");
  if (!allDeliveries.length) {
    tbody.innerHTML = `<tr><td colspan="5"><div class="empty-state">${t("re.noDeliveries")}</div></td></tr>`;
    return;
  }
  tbody.innerHTML = allDeliveries.map((d) => `<tr>
    <td><strong>${escapeHtml(d.unit_code || "—")}</strong></td>
    <td style="color:var(--muted-foreground);">${escapeHtml(d.customer_name || "—")}</td>
    <td style="color:var(--muted-foreground);">${d.delivery_date || "—"}</td>
    <td>${reStatusBadge(d.status)}</td>
    <td><div class="table-actions">
      ${canAction("realestate", "edit") ? `<button class="btn btn-primary btn-sm" onclick="openChecklist(${d.id})">${t("re.checklistBtn")}</button>` : ""}
      ${canAction("realestate", "edit") ? `<button class="btn btn-secondary btn-sm" onclick='editDelivery(${JSON.stringify(d)})'>${t("common.edit")}</button>` : ""}
      ${canAction("realestate", "delete") ? `<button class="btn btn-danger btn-sm" onclick="deleteDelivery(${d.id})">${t("common.delete")}</button>` : ""}
    </div></td></tr>`).join("");
}

function openDeliveryModal() {
  document.getElementById("delivery-modal-title").textContent = t("re.newDelivery");
  document.getElementById("delivery-id").value = "";
  document.getElementById("delivery-unit").value = "";
  document.getElementById("delivery-customer").value = "";
  document.getElementById("delivery-date").value = new Date().toISOString().slice(0, 10);
  document.getElementById("delivery-notes").value = "";
  populateCommonSelects();
  document.getElementById("delivery-modal").classList.add("active");
}

function editDelivery(d) {
  document.getElementById("delivery-modal-title").textContent = t("re.editDelivery");
  document.getElementById("delivery-id").value = d.id;
  populateCommonSelects();
  document.getElementById("delivery-unit").value = d.unit_id;
  document.getElementById("delivery-customer").value = d.customer_id || "";
  document.getElementById("delivery-date").value = d.delivery_date || new Date().toISOString().slice(0, 10);
  document.getElementById("delivery-notes").value = d.notes || "";
  document.getElementById("delivery-modal").classList.add("active");
}

async function saveDelivery() {
  const id = document.getElementById("delivery-id").value;
  const unitId = parseInt(document.getElementById("delivery-unit").value);
  if (!unitId) { showToast(t("common.required"), "warning"); return; }
  const body = {
    unit_id: unitId,
    customer_id: parseInt(document.getElementById("delivery-customer").value) || null,
    delivery_date: document.getElementById("delivery-date").value,
    notes: document.getElementById("delivery-notes").value,
  };
  try {
    if (id) await api.put(`${RE_API}/deliveries/${id}`, body);
    else await api.post(RE_API + "/deliveries", body);
    showToast(t("common.saved"));
    closeModal("delivery-modal");
    loadDeliveries();
  } catch (err) { showToast(err.message, "error"); }
}

async function deleteDelivery(id) {
  if (!confirm(t("re.confirmDeleteDelivery"))) return;
  try {
    await api.delete(`${RE_API}/deliveries/${id}`);
    showToast(t("common.deleted"));
    loadDeliveries();
  } catch (err) { showToast(err.message, "error"); }
}

window.openDeliveryModal = openDeliveryModal;
window.editDelivery = editDelivery;
window.saveDelivery = saveDelivery;
window.deleteDelivery = deleteDelivery;

// ============ MAINTENANCE ============
async function loadMaintenance() {
  try {
    allMaintenance = await api.get(RE_API + "/maintenance");
    renderMaintenance();
  } catch (e) { toastError(e); }
}

function renderMaintenance() {
  const tbody = document.getElementById("maintenance-table");
  if (!allMaintenance.length) {
    tbody.innerHTML = `<tr><td colspan="7"><div class="empty-state">${t("re.noMaintenance")}</div></td></tr>`;
    return;
  }
  tbody.innerHTML = allMaintenance.map((m) => `<tr>
    <td><strong>${escapeHtml(m.unit_code || "—")}</strong></td>
    <td>${escapeHtml(m.issue_type || "—")}</td>
    <td style="color:var(--muted-foreground);">${m.request_date || "—"}</td>
    <td><strong>${formatMoney(m.cost)}</strong></td>
    <td style="color:var(--muted-foreground);">${escapeHtml(m.assignee_name || "—")}</td>
    <td>${reStatusBadge(m.status)}</td>
    <td><div class="table-actions">
      ${m.status === "open" && canAction("realestate", "edit") ? `<button class="btn btn-info btn-sm" onclick="startMaintenance(${m.id})">${t("re.startWork")}</button>` : ""}
      ${m.status === "in_progress" && canAction("realestate", "edit") ? `<button class="btn btn-success btn-sm" onclick="doneMaintenance(${m.id})">${t("re.markDone")}</button>` : ""}
      ${canAction("realestate", "edit") ? `<button class="btn btn-secondary btn-sm" onclick='editMaintenance(${JSON.stringify(m)})'>${t("common.edit")}</button>` : ""}
      ${canAction("realestate", "delete") ? `<button class="btn btn-danger btn-sm" onclick="deleteMaintenance(${m.id})">${t("common.delete")}</button>` : ""}
    </div></td></tr>`).join("");
}

function openMaintenanceModal() {
  document.getElementById("maintenance-modal-title").textContent = t("re.newMaintenance");
  document.getElementById("maintenance-id").value = "";
  document.getElementById("maintenance-unit").value = "";
  document.getElementById("maintenance-issue").value = "";
  document.getElementById("maintenance-date").value = new Date().toISOString().slice(0, 10);
  document.getElementById("maintenance-cost").value = "";
  document.getElementById("maintenance-assigned").value = "";
  document.getElementById("maintenance-desc").value = "";
  populateCommonSelects();
  document.getElementById("maintenance-modal").classList.add("active");
}

function editMaintenance(m) {
  document.getElementById("maintenance-modal-title").textContent = t("re.editMaintenance");
  document.getElementById("maintenance-id").value = m.id;
  populateCommonSelects();
  document.getElementById("maintenance-unit").value = m.unit_id;
  document.getElementById("maintenance-issue").value = m.issue_type || "";
  document.getElementById("maintenance-date").value = m.request_date || new Date().toISOString().slice(0, 10);
  document.getElementById("maintenance-cost").value = m.cost;
  document.getElementById("maintenance-assigned").value = m.assigned_to || "";
  document.getElementById("maintenance-desc").value = m.description || "";
  document.getElementById("maintenance-modal").classList.add("active");
}

async function saveMaintenance() {
  const id = document.getElementById("maintenance-id").value;
  const unitId = parseInt(document.getElementById("maintenance-unit").value);
  if (!unitId) { showToast(t("common.required"), "warning"); return; }
  const body = {
    unit_id: unitId,
    issue_type: document.getElementById("maintenance-issue").value,
    request_date: document.getElementById("maintenance-date").value,
    cost: parseFloat(document.getElementById("maintenance-cost").value) || 0,
    assigned_to: parseInt(document.getElementById("maintenance-assigned").value) || null,
    description: document.getElementById("maintenance-desc").value,
  };
  try {
    if (id) await api.put(`${RE_API}/maintenance/${id}`, body);
    else await api.post(RE_API + "/maintenance", body);
    showToast(t("common.saved"));
    closeModal("maintenance-modal");
    loadMaintenance();
  } catch (err) { showToast(err.message, "error"); }
}

async function deleteMaintenance(id) {
  if (!confirm(t("re.confirmDeleteMaintenance"))) return;
  try {
    await api.delete(`${RE_API}/maintenance/${id}`);
    showToast(t("common.deleted"));
    loadMaintenance();
  } catch (err) { showToast(err.message, "error"); }
}

async function startMaintenance(id) {
  try {
    await api.post(`${RE_API}/maintenance/${id}/start`, {});
    loadMaintenance();
  } catch (err) { showToast(err.message, "error"); }
}

async function doneMaintenance(id) {
  try {
    await api.post(`${RE_API}/maintenance/${id}/done`, {});
    showToast(t("re.maintenanceDone"));
    loadMaintenance();
  } catch (err) { showToast(err.message, "error"); }
}

window.openMaintenanceModal = openMaintenanceModal;
window.editMaintenance = editMaintenance;
window.saveMaintenance = saveMaintenance;
window.deleteMaintenance = deleteMaintenance;
window.startMaintenance = startMaintenance;
window.doneMaintenance = doneMaintenance;

// ============ SHARES ============
async function loadShares() {
  try {
    allShares = await api.get(RE_API + "/shares");
    renderShares();
  } catch (e) { toastError(e); }
}

function renderShares() {
  const tbody = document.getElementById("shares-table");
  if (!allShares.length) {
    tbody.innerHTML = `<tr><td colspan="5"><div class="empty-state">${t("re.noShares")}</div></td></tr>`;
    return;
  }
  tbody.innerHTML = allShares.map((s) => `<tr>
    <td><strong>${escapeHtml(s.unit_code || "—")}</strong></td>
    <td style="color:var(--muted-foreground);">${escapeHtml(s.owner_name || "—")}</td>
    <td><strong>${s.share_percent}%</strong></td>
    <td>${escapeHtml(s.notes || "—")}</td>
    <td><div class="table-actions">
      ${canAction("realestate", "edit") ? `<button class="btn btn-secondary btn-sm" onclick='editShare(${JSON.stringify(s)})'>${t("common.edit")}</button>` : ""}
      ${canAction("realestate", "delete") ? `<button class="btn btn-danger btn-sm" onclick="deleteShare(${s.id})">${t("common.delete")}</button>` : ""}
    </div></td></tr>`).join("");
}

function openShareModal() {
  document.getElementById("share-modal-title").textContent = t("re.newShare");
  document.getElementById("share-id").value = "";
  document.getElementById("share-unit").value = "";
  document.getElementById("share-owner").value = "";
  document.getElementById("share-percent").value = "";
  document.getElementById("share-notes").value = "";
  populateCommonSelects();
  document.getElementById("share-modal").classList.add("active");
}

function editShare(s) {
  document.getElementById("share-modal-title").textContent = t("re.editShare");
  document.getElementById("share-id").value = s.id;
  populateCommonSelects();
  document.getElementById("share-unit").value = s.unit_id;
  document.getElementById("share-owner").value = s.owner_id;
  document.getElementById("share-percent").value = s.share_percent;
  document.getElementById("share-notes").value = s.notes || "";
  document.getElementById("share-modal").classList.add("active");
}

async function saveShare() {
  const id = document.getElementById("share-id").value;
  const unitId = parseInt(document.getElementById("share-unit").value);
  const ownerId = parseInt(document.getElementById("share-owner").value);
  if (!unitId || !ownerId) { showToast(t("common.required"), "warning"); return; }
  const percent = parseFloat(document.getElementById("share-percent").value) || 0;
  const body = { unit_id: unitId, owner_id: ownerId, share_percent: percent, notes: document.getElementById("share-notes").value };
  try {
    // التحقق من مجموع الحصص لا يتجاوز 100%
    const existingTotal = allShares.filter((s) => s.unit_id === unitId && s.id != id).reduce((sum, s) => sum + s.share_percent, 0);
    if (existingTotal + percent > 100) { showToast(t("re.shareInvalid"), "warning"); return; }
    if (id) await api.put(`${RE_API}/shares/${id}`, body);
    else await api.post(RE_API + "/shares", body);
    showToast(t("common.saved"));
    closeModal("share-modal");
    loadShares();
  } catch (err) { showToast(err.message, "error"); }
}

async function deleteShare(id) {
  if (!confirm(t("re.confirmDeleteShare"))) return;
  try {
    await api.delete(`${RE_API}/shares/${id}`);
    showToast(t("common.deleted"));
    loadShares();
  } catch (err) { showToast(err.message, "error"); }
}

window.openShareModal = openShareModal;
window.editShare = editShare;
window.saveShare = saveShare;
window.deleteShare = deleteShare;

// ==================== المصروفات ====================

const EXPENSE_CATEGORIES = {
  utilities: 'كهرباء / مياه / غاز', salary: 'رواتب', maintenance: 'صيانة',
  marketing: 'تسويق', travel: 'سفر وتنقلات', office: 'مكتبية',
  insurance: 'تأمينات', tax: 'ضرائب', rent: 'إيجار', other: 'أخرى'
};

function openExpenseModal() {
  document.getElementById('mExpenseErr').style.display = 'none';
  document.getElementById('exp-desc').value = '';
  document.getElementById('exp-amount').value = '';
  document.getElementById('exp-date').value = new Date().toISOString().slice(0, 10);
  document.getElementById('exp-notes').value = '';
  document.getElementById('exp-recurring').checked = false;
  document.getElementById('exp-recurring-period-group').style.display = 'none';
  // Populate project select
  const sel = document.getElementById('exp-project');
  sel.innerHTML = '<option value="">' + t('pw.noProject') + '</option>' +
    (allProjects || []).map(p => `<option value="${p.id}">${escapeHtml(p.name)}</option>`).join('');
  document.getElementById('exp-recurring').onchange = function() {
    document.getElementById('exp-recurring-period-group').style.display = this.checked ? '' : 'none';
  };
  openModal('mExpense');
}
window.openExpenseModal = openExpenseModal;

async function saveExpense() {
  const errEl = document.getElementById('mExpenseErr');
  const desc = document.getElementById('exp-desc').value.trim();
  const amount = parseFloat(document.getElementById('exp-amount').value) || 0;
  if (!desc || amount <= 0) {
    errEl.textContent = t('exp.descAndAmountRequired');
    errEl.style.display = 'block';
    return;
  }
  try {
    const body = {
      project_id: document.getElementById('exp-project').value || null,
      category: document.getElementById('exp-category').value,
      description: desc,
      amount,
      expense_date: document.getElementById('exp-date').value || null,
      payment_method: document.getElementById('exp-payment').value,
      payee_type: document.getElementById('exp-payee-type').value || null,
      notes: document.getElementById('exp-notes').value,
      is_recurring: document.getElementById('exp-recurring').checked,
      recurring_period: document.getElementById('exp-recurring-period').value,
    };
    const resp = await fetch('/api/project-finance/expenses', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    if (!resp.ok) {
      const err = await resp.json();
      errEl.textContent = err.message || t('exp.saveError');
      errEl.style.display = 'block';
      return;
    }
    closeModal('mExpense');
    showToast(t('exp.saveSuccess'));
    loadExpenses();
  } catch (e) {
    errEl.textContent = t('exp.connectionError') + e.message;
    errEl.style.display = 'block';
  }
}
window.saveExpense = saveExpense;

async function loadExpenses() {
  const projectId = document.getElementById('exp-project-filter')?.value || '';
  const category = document.getElementById('exp-category-filter')?.value || '';
  let url = '/api/project-finance/expenses?';
  if (projectId) url += `project_id=${projectId}&`;
  if (category) url += `category=${category}&`;
  try {
    const resp = await fetch(url);
    if (!resp.ok) return;
    const data = await resp.json();
    // KPIs
    const totalAmount = data.reduce((s, e) => s + (e.amount || 0), 0);
    const recurringAmount = data.filter(e => e.is_recurring).reduce((s, e) => s + (e.amount || 0), 0);
    const kpiEl = document.getElementById('expense-kpis');
    if (kpiEl) {
      kpiEl.innerHTML = `
        <div class="kpi kpi-red"><div class="kpi-icon">💸</div><div class="kpi-label">${t('exp.totalExpenses')}</div><div class="kpi-value">${fmtNum(totalAmount)}</div></div>
        <div class="kpi kpi-yellow"><div class="kpi-icon">🔄</div><div class="kpi-label">${t('exp.recurringExpenses')}</div><div class="kpi-value">${fmtNum(recurringAmount)}</div></div>
        <div class="kpi kpi-blue"><div class="kpi-icon">📋</div><div class="kpi-label">${t('exp.expenseCount')}</div><div class="kpi-value">${data.length}</div></div>
      `;
    }
    // Populate project filter
    const pf = document.getElementById('exp-project-filter');
    if (pf && pf.options.length <= 1) {
      pf.innerHTML = '<option value="">' + t('exp.allProjects') + '</option>' +
        (allProjects || []).map(p => `<option value="${p.id}">${escapeHtml(p.name)}</option>`).join('');
    }
    // Table
    const tbody = document.querySelector('#expenses-table');
    if (!data.length) {
      tbody.innerHTML = '<tr><td colspan="10" style="text-align:center;color:var(--tx-muted);padding:20px">' + t('exp.noExpenses') + '</td></tr>';
      return;
    }
    tbody.innerHTML = data.map(e => `
      <tr>
        <td>${e.expense_date || ''}</td>
        <td><span class="badge badge-info">${EXPENSE_CATEGORIES[e.category] || e.category}</span></td>
        <td>${escapeHtml(e.description)}</td>
        <td>${e.project_name || '—'}</td>
        <td style="font-weight:600;color:var(--err)">${fmtNum(e.amount)}</td>
        <td>${e.payment_method === 'cash' ? t('exp.cash') : e.payment_method === 'bank' ? t('exp.bank') : t('exp.credit')}</td>
        <td>${e.payee_name || '—'}</td>
        <td>${e.is_recurring ? '<span class="badge badge-warning">🔄 ' + (e.recurring_period === 'monthly' ? t('exp.monthly') : e.recurring_period === 'quarterly' ? t('exp.quarterly') : t('exp.yearly')) + '</span>' : '—'}</td>
        <td>${e.journal_entry_id ? '<span class="badge badge-success">✅</span>' : '<span class="badge badge-danger">❌</span>'}</td>
        <td><button class="btn btn-ghost btn-sm" onclick="deleteExpense(${e.id})">🗑</button></td>
      </tr>
    `).join('');
  } catch (e) {
    console.error('Load expenses error:', e);
  }
}
window.loadExpenses = loadExpenses;

async function deleteExpense(id) {
  if (!confirm(t('exp.confirmDelete'))) return;
  try {
    await fetch(`/api/project-finance/expenses/${id}`, { method: 'DELETE' });
    showToast(t('exp.deleteSuccess'));
    loadExpenses();
  } catch (e) {
    alert(t('exp.deleteError'));
  }
}
window.deleteExpense = deleteExpense;

// ==================== مساعد إنشاء المشروع (Wizard) ====================

let pwState = { step: 1, projectId: null, buildings: [], floorsPerBuilding: {}, unitsConfig: {}, unitTypes: [] };

function openProjectWizard() {
  pwState = { step: 1, projectId: null, buildings: [], floorsPerBuilding: {}, unitsConfig: {} };
  pwShowStep(1);
  populatePwManagerSelect();
  openModal('mProjectWizard');
}

function populatePwManagerSelect() {
  const sel = document.getElementById('pw-manager');
  if (!sel) return;
  sel.innerHTML = '<option value="">' + t('pw.noManager') + '</option>';
  (allEmployees || []).forEach(e => {
    sel.innerHTML += `<option value="${e.id}">${e.full_name || e.name || ''}</option>`;
  });
}

function pwShowStep(n) {
  pwState.step = n;
  document.querySelectorAll('.pw-panel').forEach(p => { p.style.display = 'none'; });
  var target = n === 5 ? 'pw-panel-summary' : 'pw-panel' + n;
  var panel = document.getElementById(target);
  if (panel) panel.style.display = 'block';
  var prevBtn = document.getElementById('pw-prev');
  if (prevBtn) prevBtn.style.display = n === 1 ? 'none' : 'inline-flex';
  var nextBtn = document.getElementById('pw-next');
  if (!nextBtn) return;
  if (n === 4) {
    nextBtn.textContent = t('pw.createProject');
    nextBtn.className = 'btn btn-success';
  } else if (n === 5) {
    nextBtn.textContent = '\u2713 ' + t('pw.finish');
    nextBtn.className = 'btn btn-primary';
    if (prevBtn) prevBtn.style.display = 'none';
  } else {
    nextBtn.textContent = t('pw.next');
    nextBtn.className = 'btn btn-primary';
  }
  for (var i = 1; i <= 4; i++) {
    var stepEl = document.getElementById('pw-step' + i);
    if (!stepEl) continue;
    stepEl.classList.remove('active', 'done');
    if (i < n || n === 5) stepEl.classList.add('done');
    else if (i === n) stepEl.classList.add('active');
  }
  document.querySelectorAll('.pw-step-line').forEach(function(line, idx) {
    line.classList.toggle('done', idx < n - 1 || n === 5);
  });
}

function pwNext() {
  const s = pwState.step;
  if (s === 1) pwSaveStep1();
  else if (s === 2) pwSaveStep2AndGo();
  else if (s === 3) pwSaveStep3AndGo();
  else if (s === 4) pwCreateProject();
  else if (s === 5) { closeModal('mProjectWizard'); loadBuildings(); loadFloors(); loadUnits(); reLoadAnalytics(); }
}

function pwPrev() {
  if (pwState.step > 1) pwShowStep(pwState.step - 1);
}

async function pwSaveStep1() {
  const name = document.getElementById('pw-name').value.trim();
  if (!name) { alert(t('pw.projectNameRequired')); return; }
  try {
    const resp = await fetch('/api/projects', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': window.CSRF_TOKEN || '' },
      body: JSON.stringify({
        name,
        location: document.getElementById('pw-location').value,
        budget: parseFloat(document.getElementById('pw-budget').value) || 0,
        manager_id: document.getElementById('pw-manager').value || null,
        start_date: document.getElementById('pw-start').value || null,
        deadline: document.getElementById('pw-deadline').value || null,
        status: 'active',
        land_cost: parseFloat(document.getElementById('pw-land-cost').value) || 0,
        papers_cost: parseFloat(document.getElementById('pw-papers-cost').value) || 0,
        construction_cost: parseFloat(document.getElementById('pw-construction-cost').value) || 0,
        payment_method: document.getElementById('pw-payment-method').value || 'cash'
      })
    });
    if (!resp.ok) throw new Error('Failed');
    const data = await resp.json();
    pwState.projectId = data.id;
    allProjects.push(data);
    pwShowStep(2);
    pwGenerateBuildings();
  } catch (e) {
    alert(t('pw.projectCreateError') + e.message);
  }
}

function pwGenerateBuildings() {
  const count = parseInt(document.getElementById('pw-building-count').value) || 1;
  const list = document.getElementById('pw-buildings-list');
  let html = '';
  for (let i = 1; i <= count; i++) {
    html += `
      <div class="pw-card">
        <div class="pw-card-header"><span class="pw-card-title">🏢 ${t('pw.building')} ${i}</span></div>
        <div class="pw-card-grid">
          <div><label>${t('pw.buildingCode')}</label><input class="input" id="pw-bcode${i}" value="B${i}"></div>
          <div><label>${t('pw.buildingName')}</label><input class="input" id="pw-bname${i}" value="${t('pw.building')} ${i}"></div>
          <div><label>${t('pw.description')}</label><input class="input" id="pw-bdesc${i}" placeholder="${t('pw.optional')}"></div>
        </div>
      </div>`;
  }
  list.innerHTML = html;
}

async function pwSaveStep2AndGo() {
  const count = parseInt(document.getElementById('pw-building-count').value) || 1;
  const buildings = [];
  for (let i = 1; i <= count; i++) {
    buildings.push({
      code: document.getElementById(`pw-bcode${i}`).value,
      name: document.getElementById(`pw-bname${i}`).value,
      description: document.getElementById(`pw-bdesc${i}`).value,
    });
  }
  try {
    const resp = await fetch(`/api/projects/${pwState.projectId}/wizard/buildings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': window.CSRF_TOKEN || '' },
      body: JSON.stringify({ buildings })
    });
    if (!resp.ok) throw new Error('Failed');
    const data = await resp.json();
    pwState.buildings = data.buildings;
    pwShowStep(3);
    pwGenerateFloors();
  } catch (e) {
    alert(t('pw.buildingCreateError') + e.message);
  }
}

function pwGenerateFloors() {
  const list = document.getElementById('pw-floors-list');
  let html = '';
  pwState.buildings.forEach(b => {
    html += `
      <div class="pw-card">
        <div class="pw-card-header"><span class="pw-card-title">🏢 ${b.name} <span style="font-weight:400;color:var(--tx-muted)">(${b.code})</span></span></div>
        <div class="pw-card-grid-2">
          <div><label>${t('pw.floorsCount')}</label><input class="input" id="pw-floors-${b.id}" type="number" min="1" max="100" value="5"></div>
          <div></div>
        </div>
      </div>`;
  });
  list.innerHTML = html;
}

async function pwSaveStep3AndGo() {
  const floorsPerBuilding = {};
  pwState.buildings.forEach(b => {
    floorsPerBuilding[b.id] = parseInt(document.getElementById(`pw-floors-${b.id}`).value) || 5;
  });
  try {
    const resp = await fetch(`/api/projects/${pwState.projectId}/wizard/floors-bulk`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': window.CSRF_TOKEN || '' },
      body: JSON.stringify({ floors_per_building: floorsPerBuilding })
    });
    if (!resp.ok) throw new Error('Failed');
    pwState.floorsPerBuilding = floorsPerBuilding;
    pwShowStep(4);
    pwGenerateUnitsConfig();
  } catch (e) {
    alert(t('pw.floorCreateError') + e.message);
  }
}

function pwGenerateUnitsConfig() {
  const list = document.getElementById('pw-units-config');
  let html = '';
  pwState.buildings.forEach(b => {
    const floors = pwState.floorsPerBuilding[b.id] || 5;
    html += `
      <div class="pw-card">
        <div class="pw-card-header">
          <span class="pw-card-title">🏢 ${b.name} <span style="font-weight:400;color:var(--tx-muted)">— ${floors} ${t('pw.floors')}</span></span>
        </div>
        <div class="pw-card-grid-2">
          <div><label>${t('pw.unitsPerFloor')}</label><input class="input" id="pw-upf-${b.id}" type="number" min="1" max="20" value="4"></div>
          <div><label>${t('pw.unitType')}</label>
            <select class="input" id="pw-utype-${b.id}">
              <option value="">${t('pw.choose')}</option>
              ${(allUnitTypes || []).map(t => `<option value="${t.id}">${t.name}</option>`).join('')}
            </select>
          </div>
        </div>
        <div class="pw-card-grid-2">
          <div><label>${t('pw.area')}</label><input class="input" id="pw-area-${b.id}" type="number" value="150"></div>
          <div><label>${t('pw.price')}</label><input class="input" id="pw-price-${b.id}" type="number" value="500000"></div>
        </div>
        <div style="margin-top:4px"><label style="display:block;font-size:.68rem;font-weight:600;color:var(--tx-muted);margin-bottom:4px">${t('pw.codePrefix')}</label><input class="input" id="pw-prefix-${b.id}" placeholder="${t('pw.prefixPlaceholder')} A-${b.code}-"></div>
      </div>`;
  });
  list.innerHTML = html;
}

async function pwCreateProject() {
  const btn = document.getElementById('pw-next');
  btn.disabled = true;
  btn.textContent = t('pw.creating');

  let totalUnits = 0;
  const config = {};

  for (const b of pwState.buildings) {
    const upf = parseInt(document.getElementById(`pw-upf-${b.id}`).value) || 4;
    const utype = document.getElementById(`pw-utype-${b.id}`).value;
    const area = parseFloat(document.getElementById(`pw-area-${b.id}`).value) || 0;
    const price = parseFloat(document.getElementById(`pw-price-${b.id}`).value) || 0;
    const prefix = document.getElementById(`pw-prefix-${b.id}`).value;

    config[b.id] = { units_per_floor: upf, unit_type_id: utype || null, area, price, prefix: prefix || `B${b.id}-` };

    const floors = pwState.floorsPerBuilding[b.id] || 5;
    totalUnits += upf * floors;
  }

  try {
    const resp = await fetch(`/api/projects/${pwState.projectId}/wizard/units-all`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': window.CSRF_TOKEN || '' },
      body: JSON.stringify({ config })
    });
    if (!resp.ok) throw new Error('Failed');

    pwShowStep(5);
    const summaryResp = await fetch(`/api/projects/${pwState.projectId}/wizard/complete`);
    const summary = await summaryResp.json();

    document.getElementById('pw-summary-content').innerHTML = `
      <div class="pw-summary-wrap">
        <div class="pw-summary-icon">✅</div>
        <div class="pw-summary-title">${t('pw.projectCreatedSuccess')}</div>
        <div class="pw-summary-sub">${summary.project.name}</div>
        <div class="pw-summary-grid">
          <div class="pw-summary-stat"><div class="num">${summary.total_buildings}</div><div class="lbl">${t('pw.buildings')}</div></div>
          <div class="pw-summary-stat"><div class="num">${summary.total_floors}</div><div class="lbl">${t('pw.floors')}</div></div>
          <div class="pw-summary-stat"><div class="num">${summary.total_units}</div><div class="lbl">${t('pw.units')}</div></div>
        </div>
      </div>`;

    btn.textContent = '✓ ' + t('pw.finish');
    btn.disabled = false;
    btn.className = 'btn btn-primary';
  } catch (e) {
    alert(t('pw.unitCreateError') + e.message);
    btn.disabled = false;
    btn.textContent = t('pw.createProject');
  }
}

// ==================== تحليلات المشاريع المالية ====================

async function reLoadAnalytics() {
  try {
    const resp = await fetch('/api/project-finance/all-projects-summary');
    if (!resp.ok) return;
    const data = await resp.json();
    renderAllProjectsSummary(data);
    populateAnalyticsProjectSelect(data);
  } catch (e) {
    console.error('Analytics error:', e);
  }
}

function renderAllProjectsSummary(projects) {
  const kpiEl = document.getElementById('re-all-projects-kpis');
  if (!kpiEl) return;
  const totalProjects = projects.length;
  const totalUnits = projects.reduce((s, p) => s + p.total_units, 0);
  const totalRevenue = projects.reduce((s, p) => s + p.total_revenue, 0);
  const totalCosts = projects.reduce((s, p) => s + p.total_costs, 0);
  const totalProfit = projects.reduce((s, p) => s + p.net_profit, 0);
  const avgOccupancy = projects.length ? Math.round(projects.reduce((s, p) => s + p.occupancy_rate, 0) / projects.length) : 0;

  kpiEl.innerHTML = `
    <div class="kpi kpi-blue"><div class="kpi-icon">🏢</div><div class="kpi-label">${t('fin.projects')}</div><div class="kpi-value">${totalProjects}</div></div>
    <div class="kpi kpi-green"><div class="kpi-icon">🏠</div><div class="kpi-label">${t('fin.totalUnits')}</div><div class="kpi-value">${totalUnits}</div></div>
    <div class="kpi kpi-purple"><div class="kpi-icon">💰</div><div class="kpi-label">${t('fin.revenue')}</div><div class="kpi-value">${fmtNum(totalRevenue)}</div></div>
    <div class="kpi kpi-red"><div class="kpi-icon">📉</div><div class="kpi-label">${t('fin.costs')}</div><div class="kpi-value">${fmtNum(totalCosts)}</div></div>
    <div class="kpi" style="border-left:3px solid ${totalProfit >= 0 ? 'var(--ok)' : 'var(--err)'}"><div class="kpi-icon">${totalProfit >= 0 ? '📈' : '⚠️'}</div><div class="kpi-label">${t('fin.netProfit')}</div><div class="kpi-value" style="color:${totalProfit >= 0 ? 'var(--ok)' : 'var(--err)'}">${fmtNum(totalProfit)}</div></div>
    <div class="kpi kpi-yellow"><div class="kpi-icon">📊</div><div class="kpi-label">${t('fin.avgOccupancy')}</div><div class="kpi-value">${avgOccupancy}%</div></div>
  `;

  const tbody = document.querySelector('#re-all-projects-tbl tbody');
  if (!tbody) return;
  if (!projects.length) {
    tbody.innerHTML = '<tr><td colspan="10" style="text-align:center;color:var(--tx-muted);padding:20px">' + t('fin.noProjects') + '</td></tr>';
    return;
  }
  tbody.innerHTML = projects.map(p => `
    <tr style="cursor:pointer" onclick="reLoadProjectAnalytics(${p.id})">
      <td style="font-weight:600">${p.name}</td>
      <td>${reStatusBadge(p.status)}</td>
      <td>${p.total_units}</td>
      <td>${p.sold_units}</td>
      <td>${p.rented_units}</td>
      <td>${p.available_units}</td>
      <td><span style="color:${p.occupancy_rate > 70 ? 'var(--ok)' : p.occupancy_rate > 30 ? 'var(--warn)' : 'var(--err)'}">${p.occupancy_rate}%</span></td>
      <td style="color:var(--err)">${fmtNum(p.total_costs)}</td>
      <td style="color:var(--ok)">${fmtNum(p.total_revenue)}</td>
      <td style="font-weight:700;color:${p.net_profit >= 0 ? 'var(--ok)' : 'var(--err)'}">${fmtNum(p.net_profit)}</td>
    </tr>
  `).join('');
}

function populateAnalyticsProjectSelect(projects) {
  const sel = document.getElementById('re-analytics-project');
  if (!sel) return;
  const current = sel.value;
  sel.innerHTML = '<option value="">' + t('exp.allProjects') + '</option>';
  projects.forEach(p => {
    sel.innerHTML += `<option value="${p.id}">${p.name}</option>`;
  });
  if (current) sel.value = current;
}

async function reLoadProjectAnalytics(projectId) {
  if (!projectId) {
    document.getElementById('re-project-detail').style.display = 'none';
    document.getElementById('re-all-projects-kpis').style.display = '';
    document.querySelector('#re-all-projects-tbl').closest('.card').style.display = '';
    reLoadAnalytics();
    return;
  }
  document.getElementById('re-all-projects-kpis').style.display = 'none';
  document.querySelector('#re-all-projects-tbl').closest('.card').style.display = 'none';
  document.getElementById('re-project-detail').style.display = 'block';
  document.getElementById('re-analytics-project').value = projectId;

  try {
    const [sumResp, forecastResp] = await Promise.all([
      fetch(`/api/project-finance/summary?project_id=${projectId}`),
      fetch(`/api/project-finance/forecast?project_id=${projectId}`)
    ]);
    const sum = await sumResp.json();
    const forecast = await forecastResp.json();
    renderProjectDetail(sum, forecast);
  } catch (e) {
    console.error('Project analytics error:', e);
  }
}

function renderProjectDetail(sum, forecast) {
  const kpiEl = document.getElementById('re-project-kpis');
  kpiEl.innerHTML = `
    <div class="kpi kpi-blue"><div class="kpi-icon">🏢</div><div class="kpi-label">${t('fin.buildings')}</div><div class="kpi-value">${sum.buildings_count}</div></div>
    <div class="kpi kpi-green"><div class="kpi-icon">🏠</div><div class="kpi-label">${t('fin.units')}</div><div class="kpi-value">${sum.total_units}</div><div class="kpi-sub">${sum.sold_units} ${t('fin.sold')} · ${sum.rented_units} ${t('fin.rented')} · ${sum.available_units} ${t('fin.available')}</div></div>
    <div class="kpi kpi-yellow"><div class="kpi-icon">📊</div><div class="kpi-label">${t('fin.occupancy')}</div><div class="kpi-value">${sum.occupancy_rate}%</div></div>
    <div class="kpi kpi-red"><div class="kpi-icon">💸</div><div class="kpi-label">${t('fin.costs')}</div><div class="kpi-value">${fmtNum(sum.total_costs)}</div></div>
    <div class="kpi kpi-purple"><div class="kpi-icon">💰</div><div class="kpi-label">${t('fin.revenue')}</div><div class="kpi-value">${fmtNum(sum.total_revenue)}</div></div>
    <div class="kpi" style="border-left:3px solid ${sum.net_profit >= 0 ? 'var(--ok)' : 'var(--err)'}"><div class="kpi-icon">${sum.net_profit >= 0 ? '📈' : '⚠️'}</div><div class="kpi-label">${t('fin.netProfit')}</div><div class="kpi-value" style="color:${sum.net_profit >= 0 ? 'var(--ok)' : 'var(--err)'}">${fmtNum(sum.net_profit)}</div></div>
  `;

  const costEl = document.getElementById('re-cost-breakdown');
  const catLabels = { land: t('fin.catLand'), papers: t('fin.catPapers'), construction: t('fin.catConstruction'), equipment: t('fin.catEquipment'), labor: t('fin.catLabor'), engineering: t('fin.catEngineering'), operating: t('fin.catOperating'), marketing: t('fin.catMarketing'), other: t('fin.catOther') };
  const cats = sum.costs_by_category || {};
  const catEntries = Object.entries(cats);
  if (catEntries.length) {
    costEl.innerHTML = `
      <table class="tbl">
        <thead><tr><th>${t('fin.category')}</th><th>${t('fin.amount')}</th><th>${t('fin.percentage')}</th></tr></thead>
        <tbody>
          ${catEntries.map(([cat, amt]) => {
            const pct = sum.total_costs > 0 ? Math.round(amt / sum.total_costs * 100) : 0;
            return `<tr><td>${catLabels[cat] || cat}</td><td>${fmtNum(amt)}</td><td><div style="display:flex;align-items:center;gap:6px"><div style="width:80px;height:6px;border-radius:3px;background:var(--surface);overflow:hidden"><div style="width:${pct}%;height:100%;background:var(--ac);border-radius:3px"></div></div>${pct}%</div></td></tr>`;
          }).join('')}
        </tbody>
      </table>`;
  } else {
    costEl.innerHTML = '<div style="text-align:center;padding:16px;color:var(--tx-muted);font-size:.82rem">' + t('fin.noCosts') + '</div>';
  }

  const fcEl = document.getElementById('re-forecast-content');
  fcEl.innerHTML = `
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px">
      <div style="padding:14px;border-radius:var(--r-sm);background:var(--surface);text-align:center">
        <div style="font-size:.7rem;color:var(--tx-muted);margin-bottom:4px">${t('fin.dueInstallments')}</div>
        <div style="font-size:1.2rem;font-weight:700;color:var(--ac)">${fmtNum(forecast.expected_from_installments)}</div>
      </div>
      <div style="padding:14px;border-radius:var(--r-sm);background:var(--surface);text-align:center">
        <div style="font-size:.7rem;color:var(--tx-muted);margin-bottom:4px">${t('fin.rentalRevenue')}</div>
        <div style="font-size:1.2rem;font-weight:700;color:var(--ok)">${fmtNum(forecast.expected_rental_annual)}</div>
      </div>
      <div style="padding:14px;border-radius:var(--r-sm);background:var(--surface);text-align:center">
        <div style="font-size:.7rem;color:var(--tx-muted);margin-bottom:4px">${t('fin.recurringExpenses')}</div>
        <div style="font-size:1.2rem;font-weight:700;color:var(--err)">${fmtNum(forecast.expected_recurring_expenses)}</div>
      </div>
      <div style="padding:14px;border-radius:var(--r-sm);background:${forecast.projected_profit >= 0 ? 'var(--ok-light)' : 'var(--err-light)'};text-align:center">
        <div style="font-size:.7rem;color:var(--tx-muted);margin-bottom:4px">${t('fin.projectedProfit')}</div>
        <div style="font-size:1.2rem;font-weight:700;color:${forecast.projected_profit >= 0 ? 'var(--ok)' : 'var(--err)'}">${fmtNum(forecast.projected_profit)}</div>
      </div>
    </div>`;
}

function fmtNum(n) {
  return new Intl.NumberFormat('ar-EG', { maximumFractionDigits: 0 }).format(n || 0);
}