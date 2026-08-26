/* HR Loans */
let loansData = [];
let loanEmployees = [];

async function loadLoans() {
  try {
    const [loans, emps] = await Promise.all([
      api.get("/api/hr/loans"),
      api.get("/api/hr/employees"),
    ]);
    loansData = loans;
    loanEmployees = emps;
    document.getElementById("loan-employee").innerHTML =
      `<option value="">${t("common.select")}</option>` +
      emps.map((e) => `<option value="${e.id}">${escapeHtml(e.full_name)}</option>`).join("");
    renderLoans();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

function renderLoans() {
  const tbody = document.getElementById("loans-table");
  document.getElementById("loans-count").textContent = `(${loansData.length})`;
  document.getElementById("loans-empty").style.display = loansData.length ? "none" : "";
  tbody.innerHTML = loansData.map((l) => `
    <tr>
      <td><b>${escapeHtml(l.employee_name || "—")}</b></td>
      <td>${formatDate(l.loan_date)}</td>
      <td><b>${formatMoney(l.amount)}</b></td>
      <td>${l.interest_rate || 0}%</td>
      <td>${formatMoney(l.total)}</td>
      <td>${formatMoney(l.installment_amount)}</td>
      <td style="color:var(--amber);">${formatMoney(l.remaining)}</td>
      <td>${hrStatusBadge(l.status)}</td>
      <td>${hrActionButtons("Loan", l, "openLoanModal", "deleteLoan")}</td>
    </tr>`).join("");
}

function openLoanModal(loan) {
  document.getElementById("loan-modal-title").textContent = loan ? t("hr.editLoan") : t("hr.addLoan");
  document.getElementById("loan-id").value = loan ? loan.id : "";
  document.getElementById("loan-employee").value = loan ? (loan.employee_id || "") : "";
  document.getElementById("loan-amount").value = loan ? (loan.amount || "") : "";
  document.getElementById("loan-interest").value = loan ? (loan.interest_rate || "") : "";
  document.getElementById("loan-date").value = loan ? (loan.loan_date || "") : "";
  document.getElementById("loan-installments").value = loan ? (loan.installments || 1) : 1;
  document.getElementById("loan-installment-amount").value = loan ? (loan.installment_amount || "") : "";
  document.getElementById("loan-paid").value = loan ? (loan.paid_amount || 0) : 0;
  document.getElementById("loan-status").value = loan ? (loan.status || "open") : "open";
  document.getElementById("loan-reason").value = loan ? (loan.reason || "") : "";
  document.getElementById("loan-modal").classList.add("active");
}

function closeLoanModal() {
  document.getElementById("loan-modal").classList.remove("active");
}

async function saveLoan() {
  const id = document.getElementById("loan-id").value;
  const body = {
    employee_id: document.getElementById("loan-employee").value || null,
    amount: parseFloat(document.getElementById("loan-amount").value) || 0,
    interest_rate: parseFloat(document.getElementById("loan-interest").value) || 0,
    loan_date: document.getElementById("loan-date").value || null,
    installments: parseInt(document.getElementById("loan-installments").value) || 1,
    installment_amount: parseFloat(document.getElementById("loan-installment-amount").value) || 0,
    paid_amount: parseFloat(document.getElementById("loan-paid").value) || 0,
    status: document.getElementById("loan-status").value,
    reason: document.getElementById("loan-reason").value.trim(),
  };
  if (!body.employee_id) { showToast(t("hr.employeeRequired"), "warning"); return; }
  try {
    if (id) await api.put(`/api/hr/loans/${id}`, body);
    else await api.post("/api/hr/loans", body);
    showToast(t("hr.saved"));
    closeLoanModal();
    loadLoans();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

async function deleteLoan(id) {
  if (!confirm(t("hr.confirmDelete"))) return;
  try {
    await api.delete(`/api/hr/loans/${id}`);
    showToast(t("hr.deleted"));
    loadLoans();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

window.openLoanModal = openLoanModal;
window.closeLoanModal = closeLoanModal;
window.saveLoan = saveLoan;
window.deleteLoan = deleteLoan;

loadLoans();
