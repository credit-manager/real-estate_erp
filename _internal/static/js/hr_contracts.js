/* HR Contracts */
let contractsData = [];
let contractEmployees = [];

const CONTRACT_TYPES = { full_time: "hr.empFullTime", part_time: "hr.empPartTime", fixed_term: "hr.empFixedTerm", probation: "hr.contractPending" };

async function loadContracts() {
  try {
    const [contracts, emps] = await Promise.all([
      api.get("/api/hr/contracts"),
      api.get("/api/hr/employees"),
    ]);
    contractsData = contracts;
    contractEmployees = emps;
    document.getElementById("contract-employee").innerHTML =
      `<option value="">${t("common.select")}</option>` +
      emps.map((e) => `<option value="${e.id}">${escapeHtml(e.full_name)}</option>`).join("");
    renderContracts();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

function renderContracts() {
  const tbody = document.getElementById("contracts-table");
  document.getElementById("contracts-count").textContent = `(${contractsData.length})`;
  document.getElementById("contracts-empty").style.display = contractsData.length ? "none" : "";
  tbody.innerHTML = contractsData.map((c) => `
    <tr>
      <td><b>${escapeHtml(c.contract_number || "—")}</b></td>
      <td>${escapeHtml(c.employee_name || "—")}</td>
      <td>${CONTRACT_TYPES[c.contract_type] ? t(CONTRACT_TYPES[c.contract_type]) : escapeHtml(c.contract_type)}</td>
      <td>${formatDate(c.start_date)}</td>
      <td>${formatDate(c.end_date)}</td>
      <td><b>${formatMoney(c.salary)}</b></td>
      <td>${hrStatusBadge(c.status)}</td>
      <td>${hrActionButtons("Contract", c, "openContractModal", "deleteContract")}</td>
    </tr>`).join("");
}

function openContractModal(contract) {
  document.getElementById("contract-modal-title").textContent = contract ? t("hr.editContract") : t("hr.addContract");
  document.getElementById("contract-id").value = contract ? contract.id : "";
  document.getElementById("contract-employee").value = contract ? (contract.employee_id || "") : "";
  document.getElementById("contract-number").value = contract ? (contract.contract_number || "") : "";
  document.getElementById("contract-type").value = contract ? (contract.contract_type || "full_time") : "full_time";
  document.getElementById("contract-status").value = contract ? (contract.status || "active") : "active";
  document.getElementById("contract-start-date").value = contract ? (contract.start_date || "") : "";
  document.getElementById("contract-end-date").value = contract ? (contract.end_date || "") : "";
  document.getElementById("contract-salary").value = contract ? (contract.salary || "") : "";
  document.getElementById("contract-hours").value = contract ? (contract.working_hours || 8) : 8;
  document.getElementById("contract-notes").value = contract ? (contract.notes || "") : "";
  document.getElementById("contract-modal").classList.add("active");
}

function closeContractModal() {
  document.getElementById("contract-modal").classList.remove("active");
}

async function saveContract() {
  const id = document.getElementById("contract-id").value;
  const body = {
    employee_id: document.getElementById("contract-employee").value || null,
    contract_number: document.getElementById("contract-number").value.trim(),
    contract_type: document.getElementById("contract-type").value,
    status: document.getElementById("contract-status").value,
    start_date: document.getElementById("contract-start-date").value || null,
    end_date: document.getElementById("contract-end-date").value || null,
    salary: parseFloat(document.getElementById("contract-salary").value) || 0,
    working_hours: parseFloat(document.getElementById("contract-hours").value) || 8,
    notes: document.getElementById("contract-notes").value.trim(),
  };
  if (!body.employee_id) { showToast(t("hr.employeeRequired"), "warning"); return; }
  try {
    if (id) await api.put(`/api/hr/contracts/${id}`, body);
    else await api.post("/api/hr/contracts", body);
    showToast(t("hr.saved"));
    closeContractModal();
    loadContracts();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

async function deleteContract(id) {
  if (!confirm(t("hr.confirmDelete"))) return;
  try {
    await api.delete(`/api/hr/contracts/${id}`);
    showToast(t("hr.deleted"));
    loadContracts();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

window.openContractModal = openContractModal;
window.closeContractModal = closeContractModal;
window.saveContract = saveContract;
window.deleteContract = deleteContract;

loadContracts();
