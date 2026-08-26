async function loadInventoryHome() {
  try {
    const res = await api.get("/api/inventory/meta");
    const m = res || {};
    animateCount(document.getElementById("inv-warehouses"), m.warehouses_count ?? 0);
    animateCount(document.getElementById("inv-items"), m.items_count ?? 0);
    document.getElementById("inv-value").textContent = formatMoney(m.stock_value ?? 0);
    animateCount(document.getElementById("inv-low"), m.low_stock_count ?? 0);
    animateCount(document.getElementById("inv-expired"), m.expired_batches_count ?? 0);
  } catch (e) {
    showToast(t("common.error"), "error");
  }
}

document.addEventListener("DOMContentLoaded", loadInventoryHome);
