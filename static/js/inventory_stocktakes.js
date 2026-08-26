let stocktakesData = [];
let stocktakeWarehouses = [];
let currentStocktake = null;

async function loadStocktakes() {
  try {
    const [stRes, whRes] = await Promise.all([
      api.get("/api/inventory/stocktakes"),
      api.get("/api/inventory/warehouses"),
    ]);
    stocktakesData = stRes.stocktakes || [];
    stocktakeWarehouses = whRes.warehouses || [];
    const whSel = document.getElementById("st-warehouse");
    whSel.innerHTML = stocktakeWarehouses.map((w) =>
      `<option value="${w.id}">${escapeHtml(w.name)}</option>`).join("");
    renderStocktakes();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

function openStocktakeModal() {
  document.getElementById("st-date").value = new Date().toISOString().slice(0, 10);
  document.getElementById("st-notes").value = "";
  document.getElementById("stocktake-modal").classList.add("active");
}
window.openStocktakeModal = openStocktakeModal;

function closeStocktakeModal() {
  document.getElementById("stocktake-modal").classList.remove("active");
}
window.closeStocktakeModal = closeStocktakeModal;

async function createStocktake() {
  const payload = {
    warehouse_id: document.getElementById("st-warehouse").value,
    take_date: document.getElementById("st-date").value || null,
    notes: document.getElementById("st-notes").value.trim(),
  };
  try {
    const res = await api.request("/api/inventory/stocktakes", "POST", payload);
    showToast(t("common.saved"));
    closeStocktakeModal();
    await loadStocktakes();
    if (res.stocktake) viewStocktake(res.stocktake.id);
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}
window.createStocktake = createStocktake;

function renderStocktakes() {
  const tbody = document.getElementById("stocktakes-table");
  document.getElementById("stocktakes-count").textContent = `(${stocktakesData.length})`;
  document.getElementById("stocktakes-empty").style.display = stocktakesData.length ? "none" : "";
  tbody.innerHTML = stocktakesData.map((st) => `
    <tr>
      <td><b>${escapeHtml(st.take_number)}</b></td>
      <td>${escapeHtml(st.warehouse_name || "—")}</td>
      <td>${st.take_date ? formatDate(st.take_date) : "—"}</td>
      <td>${(st.items || []).length}</td>
      <td>${invBadge(st.status)}</td>
      <td>
        <button class="icon-btn" title="${invT("inventory.viewStock")}" onclick="viewStocktake(${st.id})">👁️</button>
        ${st.status === "draft" && invCan("delete")
          ? `<button class="icon-btn" title="${invT("common.delete")}" onclick="deleteStocktake(${st.id})">🗑️</button>`
          : ""}
      </td>
    </tr>
  `).join("");
}
window.renderStocktakes = renderStocktakes;

function viewStocktake(id) {
  const st = stocktakesData.find((x) => x.id === id);
  if (!st) return;
  currentStocktake = st;
  document.getElementById("take-detail-title").textContent =
    `${st.take_number} — ${st.warehouse_name || ""}`;
  const tbody = document.getElementById("take-items");
  tbody.innerHTML = (st.items || []).map((line) => `
    <tr>
      <td>${escapeHtml(line.item_name || "—")}</td>
      <td>${formatNumber(line.system_qty)}</td>
      <td>
        ${st.status === "draft" && invCan("edit")
          ? `<input type="number" class="form-input" style="width:100px;" value="${line.counted_qty}"
               onchange="updateCountedQty(${st.id}, ${line.item_id}, this.value)">`
          : formatNumber(line.counted_qty)}
      </td>
      <td style="font-weight:600;${line.diff_qty ? "color:var(--danger);" : ""}">${formatNumber(line.diff_qty)}</td>
    </tr>
  `).join("");
  document.getElementById("take-complete-btn").style.display =
    (st.status === "draft" && invCan("edit")) ? "" : "none";
  document.getElementById("take-detail-modal").classList.add("active");
}
window.viewStocktake = viewStocktake;

function closeTakeDetail() {
  document.getElementById("take-detail-modal").classList.remove("active");
}
window.closeTakeDetail = closeTakeDetail;

async function updateCountedQty(takeId, itemId, value) {
  try {
    await api.request(`/api/inventory/stocktakes/${takeId}`, "PUT", {
      item_id: itemId,
      counted_qty: parseFloat(value) || 0,
    });
    await loadStocktakes();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}
window.updateCountedQty = updateCountedQty;

async function completeStocktake() {
  if (!currentStocktake) return;
  if (!confirm(invT("inventory.completeStocktake"))) return;
  try {
    await api.request(`/api/inventory/stocktakes/${currentStocktake.id}`, "PUT", { status: "completed" });
    showToast(t("common.saved"));
    closeTakeDetail();
    await loadStocktakes();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}
window.completeStocktake = completeStocktake;

async function deleteStocktake(id) {
  if (!confirm(t("inventory.confirmDelete"))) return;
  try {
    await api.request(`/api/inventory/stocktakes/${id}`, "DELETE");
    showToast(t("common.deleted"));
    loadStocktakes();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}
window.deleteStocktake = deleteStocktake;

loadStocktakes();
