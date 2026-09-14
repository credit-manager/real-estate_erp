/* Payroll - Taxes */

async function loadTaxes() {
  try {
    const [settings, brackets] = await Promise.all([
      api.get("/api/payroll/settings"),
      api.get("/api/payroll/tax-brackets"),
    ]);
    document.getElementById("tax-exempt").value = settings.tax_exempt || 0;
    renderBrackets(brackets);
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

function renderBrackets(brackets) {
  document.getElementById("brackets-count").textContent = `(${brackets.length})`;
  document.getElementById("brackets-empty").style.display = brackets.length ? "none" : "";
  document.getElementById("brackets-table").innerHTML = brackets.map((b) => `
    <tr>
      <td>${prMoney(b.from_amount)}</td>
      <td>${b.to_amount === null ? "∞" : prMoney(b.to_amount)}</td>
      <td><b>${b.rate}%</b></td>
      <td>${prActionButtons("Bracket", b, "openBracketModal", "deleteBracket")}</td>
    </tr>`).join("");
}

function openBracketModal(bracket) {
  document.getElementById("bracket-modal-title").textContent = bracket ? t("payroll.editBracket") : t("payroll.addBracket");
  document.getElementById("bracket-id").value = bracket ? bracket.id : "";
  document.getElementById("bracket-from").value = bracket ? (bracket.from_amount || "") : "";
  document.getElementById("bracket-to").value = bracket && bracket.to_amount !== null ? bracket.to_amount : "";
  document.getElementById("bracket-rate").value = bracket ? (bracket.rate || "") : "";
  document.getElementById("bracket-modal").classList.add("active");
}

function closeBracketModal() {
  document.getElementById("bracket-modal").classList.remove("active");
}

async function saveBracket() {
  const id = document.getElementById("bracket-id").value;
  const body = {
    from_amount: parseFloat(document.getElementById("bracket-from").value) || 0,
    to_amount: document.getElementById("bracket-to").value === "" ? null : (parseFloat(document.getElementById("bracket-to").value) || 0),
    rate: parseFloat(document.getElementById("bracket-rate").value) || 0,
  };
  try {
    if (id) await api.put(`/api/payroll/tax-brackets/${id}`, body);
    else await api.post("/api/payroll/tax-brackets", body);
    showToast(t("payroll.saved"));
    closeBracketModal();
    loadTaxes();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

async function deleteBracket(id) {
  if (!confirm(t("payroll.confirmDelete"))) return;
  try {
    await api.delete(`/api/payroll/tax-brackets/${id}`);
    showToast(t("payroll.deleted"));
    loadTaxes();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

async function saveSettings() {
  const body = {
    tax_exempt: parseFloat(document.getElementById("tax-exempt").value) || 0,
  };
  try {
    await api.put("/api/payroll/settings", body);
    showToast(t("payroll.settingsSaved"));
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

window.openBracketModal = openBracketModal;
window.closeBracketModal = closeBracketModal;
window.saveBracket = saveBracket;
window.deleteBracket = deleteBracket;
window.saveSettings = saveSettings;

loadTaxes();
