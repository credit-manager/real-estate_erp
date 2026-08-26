let suppliersData = [];

async function loadSuppliers() {
  try {
    const res = await api.get("/api/inventory/suppliers");
    suppliersData = res.suppliers || [];
    renderSuppliers();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

function openSupplierModal(sup) {
  document.getElementById("supplier-id").value = sup ? sup.id : "";
  document.getElementById("supplier-company").value = sup ? sup.company_name : "";
  document.getElementById("supplier-category").value = sup ? (sup.category || "") : "";
  document.getElementById("supplier-phone").value = sup ? (sup.phone || "") : "";
  document.getElementById("supplier-email").value = sup ? (sup.email || "") : "";
  document.getElementById("supplier-address").value = sup ? (sup.address || "") : "";
  document.getElementById("supplier-modal-title").textContent = sup ? invT("inventory.editSupplier") : invT("inventory.addSupplier");
  document.getElementById("supplier-modal").classList.add("active");
}
window.openSupplierModal = openSupplierModal;

function closeSupplierModal() {
  document.getElementById("supplier-modal").classList.remove("active");
}
window.closeSupplierModal = closeSupplierModal;

function editSupplier(sup) { openSupplierModal(sup); }
window.editSupplier = editSupplier;

function renderSuppliers() {
  const q = (document.getElementById("supplier-search").value || "").trim().toLowerCase();
  const list = q ? suppliersData.filter((s) =>
    (s.company_name + " " + (s.contact_name || "") + " " + (s.category || "")).toLowerCase().includes(q)) : suppliersData;
  const tbody = document.getElementById("suppliers-table");
  document.getElementById("suppliers-count").textContent = `(${list.length})`;
  document.getElementById("suppliers-empty").style.display = list.length ? "none" : "";
  tbody.innerHTML = list.map((s) => `
    <tr>
      <td><b>${escapeHtml(s.company_name)}</b>${s.contact_name ? `<div class="table-sub">${escapeHtml(s.contact_name)}</div>` : ""}</td>
      <td>${escapeHtml(s.category || "—")}</td>
      <td>${escapeHtml(s.phone || "—")}</td>
      <td>${escapeHtml(s.email || "—")}</td>
      <td>${escapeHtml(s.address || "—")}</td>
      <td>
        ${invCan("edit") ? `<button class="icon-btn" title="${invT("common.edit")}" onclick='editSupplier(${JSON.stringify(s)})'>✏️</button>` : ""}
        ${invCan("delete") ? `<button class="icon-btn" title="${invT("common.delete")}" onclick="deleteSupplier(${s.id})">🗑️</button>` : ""}
      </td>
    </tr>
  `).join("");
}
window.renderSuppliers = renderSuppliers;

async function saveSupplier() {
  const id = document.getElementById("supplier-id").value;
  const payload = {
    company_name: document.getElementById("supplier-company").value.trim(),
    category: document.getElementById("supplier-category").value.trim(),
    phone: document.getElementById("supplier-phone").value.trim(),
    email: document.getElementById("supplier-email").value.trim(),
    address: document.getElementById("supplier-address").value.trim(),
  };
  if (!payload.company_name) {
    showToast(invT("inventory.noSuppliers"), "error");
    return;
  }
  try {
    if (id) {
      await api.request(`/api/inventory/suppliers/${id}`, "PUT", payload);
    } else {
      await api.request("/api/inventory/suppliers", "POST", payload);
    }
    showToast(t("common.saved"));
    closeSupplierModal();
    loadSuppliers();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}
window.saveSupplier = saveSupplier;

async function deleteSupplier(id) {
  if (!confirm(t("inventory.confirmDelete"))) return;
  try {
    await api.request(`/api/inventory/suppliers/${id}`, "DELETE");
    showToast(t("common.deleted"));
    loadSuppliers();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}
window.deleteSupplier = deleteSupplier;

loadSuppliers();
