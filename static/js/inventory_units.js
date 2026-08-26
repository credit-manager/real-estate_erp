let unitsData = [];

async function loadUnits() {
  try {
    const res = await api.get("/api/inventory/units");
    unitsData = res.units || [];
    renderUnits();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

function openUnitModal(unit) {
  document.getElementById("unit-id").value = unit ? unit.id : "";
  document.getElementById("unit-name").value = unit ? unit.name : "";
  document.getElementById("unit-code").value = unit ? (unit.code || "") : "";
  document.getElementById("unit-active").checked = unit ? unit.is_active : true;
  document.getElementById("unit-modal-title").textContent = unit ? invT("inventory.editUnit") : invT("inventory.addUnit");
  document.getElementById("unit-modal").classList.add("active");
}
window.openUnitModal = openUnitModal;

function closeUnitModal() {
  document.getElementById("unit-modal").classList.remove("active");
}
window.closeUnitModal = closeUnitModal;

function editUnit(unit) { openUnitModal(unit); }
window.editUnit = editUnit;

function renderUnits() {
  const tbody = document.getElementById("units-table");
  document.getElementById("units-count").textContent = `(${unitsData.length})`;
  document.getElementById("units-empty").style.display = unitsData.length ? "none" : "";
  tbody.innerHTML = unitsData.map((u) => `
    <tr>
      <td><b>${escapeHtml(u.name)}</b></td>
      <td>${escapeHtml(u.code || "—")}</td>
      <td>${u.items_count || 0}</td>
      <td>${invStatusBadge(u.is_active)}</td>
      <td>
        ${invCan("edit") ? `<button class="icon-btn" title="${invT("common.edit")}" onclick='editUnit(${JSON.stringify(u)})'>✏️</button>` : ""}
        ${invCan("delete") ? `<button class="icon-btn" title="${invT("common.delete")}" onclick="deleteUnit(${u.id})">🗑️</button>` : ""}
      </td>
    </tr>
  `).join("");
}
window.renderUnits = renderUnits;

async function saveUnit() {
  const id = document.getElementById("unit-id").value;
  const payload = {
    name: document.getElementById("unit-name").value.trim(),
    code: document.getElementById("unit-code").value.trim(),
    is_active: document.getElementById("unit-active").checked,
  };
  if (!payload.name) {
    showToast(invT("inventory.noUnits"), "error");
    return;
  }
  try {
    if (id) {
      await api.request(`/api/inventory/units/${id}`, "PUT", payload);
    } else {
      await api.request("/api/inventory/units", "POST", payload);
    }
    showToast(t("common.saved"));
    closeUnitModal();
    loadUnits();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}
window.saveUnit = saveUnit;

async function deleteUnit(id) {
  if (!confirm(t("inventory.confirmDelete"))) return;
  try {
    await api.request(`/api/inventory/units/${id}`, "DELETE");
    showToast(t("common.deleted"));
    loadUnits();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}
window.deleteUnit = deleteUnit;

loadUnits();
