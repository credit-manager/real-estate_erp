/* Payroll - End of Service */
let eosEmployees = [];
let eosCalculated = false;

async function loadEos() {
  try {
    const [records, emps, settings] = await Promise.all([
      api.get("/api/payroll/end-of-service"),
      api.get("/api/hr/employees"),
      api.get("/api/payroll/settings"),
    ]);
    eosEmployees = emps;
    document.getElementById("eos-employee").innerHTML =
      `<option value="">${t("common.select")}</option>` + prEmployeesOptions(emps);
    document.getElementById("eos-per-year").value = settings.gratuity_per_year_days || 0;
    document.getElementById("eos-after-five").value = settings.gratuity_after_five_days || 0;
    renderEos(records);
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

function renderEos(records) {
  document.getElementById("eos-count").textContent = `(${records.length})`;
  document.getElementById("eos-empty").style.display = records.length ? "none" : "";
  document.getElementById("eos-table").innerHTML = records.map((r) => `
    <tr>
      <td><b>${escapeHtml(r.employee_name || "—")}</b></td>
      <td>${formatDate(r.hire_date)}</td>
      <td>${formatDate(r.end_date)}</td>
      <td>${r.service_years}</td>
      <td>${r.gratuity_days}</td>
      <td>${prAmountCell(r.gratuity_amount)}</td>
      <td>${prStatusBadge(r.status)}</td>
      <td>${prActionButtons("Eos", r, "openEosModal", "deleteEos")}</td>
    </tr>`).join("");
}

function openEosModal(record) {
  eosCalculated = false;
  document.getElementById("eos-modal-title").textContent = record ? t("payroll.editEos") : t("payroll.addEos");
  document.getElementById("eos-id").value = record ? record.id : "";
  document.getElementById("eos-employee").value = record ? (record.employee_id || "") : "";
  document.getElementById("eos-hire").value = record ? (record.hire_date || "") : "";
  document.getElementById("eos-end").value = record ? (record.end_date || "") : "";
  document.getElementById("eos-years").value = record ? (record.service_years || "") : "";
  document.getElementById("eos-days").value = record ? (record.gratuity_days || "") : "";
  document.getElementById("eos-base").value = record ? (record.base_salary || "") : "";
  document.getElementById("eos-amount").value = record ? (record.gratuity_amount || "") : "";
  document.getElementById("eos-status").value = record ? (record.status || "draft") : "draft";
  document.getElementById("eos-notes").value = record ? (record.notes || "") : "";
  document.getElementById("eos-preview").textContent = "";
  document.getElementById("eos-modal").classList.add("active");
}

function closeEosModal() {
  document.getElementById("eos-modal").classList.remove("active");
}

async function calculateEos() {
  const employeeId = document.getElementById("eos-employee").value;
  if (!employeeId) { showToast(t("payroll.employeeRequired"), "warning"); return; }
  const emp = eosEmployees.find((e) => e.id == employeeId);
  try {
    const res = await api.post("/api/payroll/end-of-service/calculate", {
      employee_id: parseInt(employeeId, 10),
      end_date: document.getElementById("eos-end").value || null,
      hire_date: document.getElementById("eos-hire").value || null,
    });
    document.getElementById("eos-hire").value = res.hire_date || "";
    document.getElementById("eos-end").value = res.end_date || "";
    document.getElementById("eos-years").value = res.service_years;
    document.getElementById("eos-days").value = res.gratuity_days;
    document.getElementById("eos-base").value = res.base_salary;
    document.getElementById("eos-amount").value = res.gratuity_amount;
    document.getElementById("eos-preview").textContent =
      `${t("payroll.gratuityAmount")}: ${prMoney(res.gratuity_amount)} — ${t("payroll.gratuityDays")}: ${res.gratuity_days}`;
    eosCalculated = true;
    showToast(t("payroll.eosCalculated"));
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

async function saveEos() {
  const id = document.getElementById("eos-id").value;
  const body = {
    employee_id: document.getElementById("eos-employee").value || null,
    hire_date: document.getElementById("eos-hire").value || null,
    end_date: document.getElementById("eos-end").value || null,
    service_years: parseFloat(document.getElementById("eos-years").value) || 0,
    gratuity_days: parseFloat(document.getElementById("eos-days").value) || 0,
    base_salary: parseFloat(document.getElementById("eos-base").value) || 0,
    gratuity_amount: parseFloat(document.getElementById("eos-amount").value) || 0,
    status: document.getElementById("eos-status").value,
    notes: document.getElementById("eos-notes").value.trim(),
    auto_calculate: !id && eosCalculated,
  };
  if (!body.employee_id) { showToast(t("payroll.employeeRequired"), "warning"); return; }
  try {
    if (id) await api.put(`/api/payroll/end-of-service/${id}`, body);
    else await api.post("/api/payroll/end-of-service", body);
    showToast(t("payroll.saved"));
    closeEosModal();
    loadEos();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

async function deleteEos(id) {
  if (!confirm(t("payroll.confirmDelete"))) return;
  try {
    await api.delete(`/api/payroll/end-of-service/${id}`);
    showToast(t("payroll.deleted"));
    loadEos();
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

async function saveSettings() {
  const body = {
    gratuity_per_year_days: parseFloat(document.getElementById("eos-per-year").value) || 0,
    gratuity_after_five_days: parseFloat(document.getElementById("eos-after-five").value) || 0,
  };
  try {
    await api.put("/api/payroll/settings", body);
    showToast(t("payroll.settingsSaved"));
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

window.openEosModal = openEosModal;
window.closeEosModal = closeEosModal;
window.saveEos = saveEos;
window.deleteEos = deleteEos;
window.calculateEos = calculateEos;
window.saveSettings = saveSettings;

loadEos();
