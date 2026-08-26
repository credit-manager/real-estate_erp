/* Journal entries */
let journalMeta = null;
let currentEntryId = null;
let journalList = null;

async function loadMeta() {
  try {
    journalMeta = await api.get("/accounting/api/meta");
    fillYearSelect("journal-year", journalMeta.years);
    const yearSel = document.getElementById("jv-year");
    yearSel.innerHTML = `<option value="">${t("common.select")}</option>` +
      journalMeta.years.map((y) => `<option value="${y.id}">${escapeHtml(y.name)}</option>`).join("");
  } catch (e) { toastError(e); }
}

function journalParams() {
  const p = {};
  const year = document.getElementById("journal-year").value;
  const start = document.getElementById("journal-start").value;
  const end = document.getElementById("journal-end").value;
  if (year) p.year_id = year;
  if (start) p.start = start;
  if (end) p.end = end;
  return p;
}

function journalRowHTML(e) {
  return `
    <tr>
      <td><strong>${escapeHtml(e.entry_number)}</strong></td>
      <td>${formatDate(e.date)}</td>
      <td>${escapeHtml(e.description || "")}
        ${e.source && e.source !== "manual" ? `<div class="table-sub">${escapeHtml(t("accounting.source." + e.source))}</div>` : ""}
      </td>
      <td>${e.source && e.source !== "manual" ? `<span class="badge badge-info">${escapeHtml(t("accounting.source." + e.source))}</span>` : `<span class="badge">${t("accounting.manual")}</span>`}</td>
      <td>${fmtMoney(e.total_debit)}</td>
      <td>${fmtMoney(e.total_credit)}</td>
      <td>
        <div class="table-actions">
          <button class="btn btn-outline btn-sm" onclick='viewEntry(${JSON.stringify(e)})'>${t("common.view")}</button>
          ${canAction("accounting", "delete") && e.source === "manual" ? `<button class="btn btn-danger btn-sm" onclick="deleteEntry(${e.id})">${t("common.delete")}</button>` : ""}
        </div>
      </td>
    </tr>`;
}

async function loadJournal() {
  if (!journalList) return;
  journalList.page = 1;
  await journalList.load();
}

function openJournalModal() {
  currentEntryId = null;
  document.getElementById("jv-date").value = new Date().toISOString().slice(0, 10);
  document.getElementById("jv-desc").value = "";
  const lines = document.getElementById("jv-lines");
  lines.innerHTML = lineRowHTML();
  recalcLines();
  document.getElementById("journal-modal").classList.add("active");
}

function closeJournalModal() { document.getElementById("journal-modal").classList.remove("active"); }

function lineRowHTML(line) {
  line = line || {};
  return `
    <div class="jv-line">
      <select class="lv-account">${accountOptions(journalMeta ? journalMeta.accounts : [], null, false)}</select>
      <select class="lv-cc">${costCenterOptions(journalMeta ? journalMeta.cost_centers : [])}</select>
      <input type="number" class="lv-debit" min="0" step="0.01" value="${line.debit || ""}" placeholder="${t("accounting.debit")}">
      <input type="number" class="lv-credit" min="0" step="0.01" value="${line.credit || ""}" placeholder="${t("accounting.credit")}">
      <input type="text" class="lv-desc" placeholder="${t("common.description")}">
      <button type="button" class="btn btn-danger btn-sm" onclick="removeLine(this)">✕</button>
    </div>`;
}

function addLine() {
  const lines = document.getElementById("jv-lines");
  lines.insertAdjacentHTML("beforeend", lineRowHTML());
  bindLineEvents(lines.lastElementChild);
  recalcLines();
}

function removeLine(btn) {
  const row = btn.closest(".jv-line");
  row.remove();
  recalcLines();
}

function bindLineEvents(row) {
  row.querySelectorAll(".lv-debit, .lv-credit").forEach((inp) => {
    inp.addEventListener("input", recalcLines);
  });
}

function recalcLines() {
  let dr = 0, cr = 0;
  document.querySelectorAll("#jv-lines .jv-line").forEach((row) => {
    const d = parseFloat(row.querySelector(".lv-debit").value) || 0;
    const c = parseFloat(row.querySelector(".lv-credit").value) || 0;
    dr += d; cr += c;
  });
  document.getElementById("jv-total-dr").textContent = fmtMoney(dr);
  document.getElementById("jv-total-cr").textContent = fmtMoney(cr);
  const badge = document.getElementById("jv-balance-badge");
  const balanced = Math.abs(dr - cr) < 0.005 && dr > 0;
  badge.textContent = balanced ? (dr > 0 ? "✓ " + t("accounting.balanced") : "") : t("accounting.notBalanced");
  badge.style.color = balanced ? "var(--success)" : "var(--red)";
}

async function saveJournal() {
  const date = document.getElementById("jv-date").value;
  const lines = [];
  document.querySelectorAll("#jv-lines .jv-line").forEach((row) => {
    lines.push({
      account_id: parseInt(row.querySelector(".lv-account").value) || null,
      cost_center_id: parseInt(row.querySelector(".lv-cc").value) || null,
      debit: parseFloat(row.querySelector(".lv-debit").value) || 0,
      credit: parseFloat(row.querySelector(".lv-credit").value) || 0,
      description: (row.querySelector(".lv-desc").value || "").trim(),
    });
  });
  if (!date) { showToast(t("accounting.dateRequired"), "warning"); return; }
  const body = {
    date,
    financial_year_id: parseInt(document.getElementById("jv-year").value) || null,
    description: document.getElementById("jv-desc").value.trim(),
    lines,
  };
  try {
    await api.post("/accounting/api/journal", body);
    showToast(t("common.savedSuccess"));
    closeJournalModal();
    if (journalList) { journalList.page = 1; journalList.refresh(); }
  } catch (e) { toastError(e); }
}

function viewEntry(e) {
  currentEntryId = e.id;
  document.getElementById("jv-view-title").textContent = `${t("accounting.viewEntry")} - ${e.entry_number}`;
  const rows = e.lines.map((l) => `
    <tr>
      <td>${escapeHtml(l.account_code || "")}</td>
      <td>${escapeHtml(l.account_name || "")}</td>
      <td>${l.cost_center_name ? escapeHtml(l.cost_center_name) : "—"}</td>
      <td>${fmtMoney(l.debit)}</td>
      <td>${fmtMoney(l.credit)}</td>
      <td>${escapeHtml(l.description || "")}</td>
    </tr>`).join("");
  document.getElementById("jv-view-body").innerHTML = `
    <div class="form-row" style="margin-bottom:12px;">
      <div class="form-group"><label>${t("accounting.date")}</label><div>${formatDate(e.date)}</div></div>
      <div class="form-group"><label>${t("accounting.financialYear")}</label><div>${escapeHtml(e.financial_year_name || "—")}</div></div>
    </div>
    <div class="form-group"><label>${t("common.description")}</label><div>${escapeHtml(e.description || "—")}</div></div>
    <table class="modal-table">
      <thead><tr>
        <th>${t("accounting.code")}</th><th>${t("common.name")}</th><th>${t("accounting.costCenter")}</th>
        <th>${t("accounting.debit")}</th><th>${t("accounting.credit")}</th><th>${t("common.description")}</th>
      </tr></thead>
      <tbody>${rows}</tbody>
      <tfoot><tr>
        <td colspan="3">${t("accounting.totals")}</td>
        <td><strong>${fmtMoney(e.total_debit)}</strong></td>
        <td><strong>${fmtMoney(e.total_credit)}</strong></td>
        <td></td>
      </tr></tfoot>
    </table>`;
  document.getElementById("jv-reverse-btn").style.display = canAction("accounting", "create") ? "" : "none";
  document.getElementById("jv-view-modal").classList.add("active");
}

function closeViewModal() { document.getElementById("jv-view-modal").classList.remove("active"); }

async function reverseEntry() {
  if (!currentEntryId) return;
  if (!confirm(t("accounting.confirmReverse"))) return;
  try {
    await api.post(`/accounting/api/journal/${currentEntryId}/reverse`);
    showToast(t("common.savedSuccess"));
    closeViewModal();
    if (journalList) { journalList.page = 1; journalList.refresh(); }
  } catch (e) { toastError(e); }
}

async function deleteEntry(id) {
  if (!confirm(t("accounting.confirmDelete"))) return;
  try {
    await api.delete(`/accounting/api/journal/${id}`);
    showToast(t("common.deleted"));
    if (journalList) journalList.refresh();
  } catch (e) { toastError(e); }
}

window.openJournalModal = openJournalModal;
window.closeJournalModal = closeJournalModal;
window.addLine = addLine;
window.removeLine = removeLine;
window.saveJournal = saveJournal;
window.viewEntry = viewEntry;
window.closeViewModal = closeViewModal;
window.reverseEntry = reverseEntry;
window.deleteEntry = deleteEntry;
window.loadJournal = loadJournal;

document.addEventListener("DOMContentLoaded", () => {
  journalList = new PagedList({
    url: "/accounting/api/journal",
    params: journalParams,
    target: "journal-table",
    controls: "journal-pagination",
    colspan: 7,
    perPage: 25,
    render: (rows) => rows.map(journalRowHTML).join(""),
  });
  loadMeta();
  loadJournal();
});
