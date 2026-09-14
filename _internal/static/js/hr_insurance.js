/* Payroll - Insurance */

async function loadInsurance() {
  try {
    const settings = await api.get("/api/payroll/settings");
    document.getElementById("ins-employee-rate").value = settings.insurance_employee_rate || 0;
    document.getElementById("ins-employer-rate").value = settings.insurance_employer_rate || 0;
    document.getElementById("ins-ceiling").value = settings.insurance_ceiling || 0;
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

async function saveSettings() {
  const body = {
    insurance_employee_rate: parseFloat(document.getElementById("ins-employee-rate").value) || 0,
    insurance_employer_rate: parseFloat(document.getElementById("ins-employer-rate").value) || 0,
    insurance_ceiling: parseFloat(document.getElementById("ins-ceiling").value) || 0,
  };
  try {
    await api.put("/api/payroll/settings", body);
    showToast(t("payroll.settingsSaved"));
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

window.saveSettings = saveSettings;

loadInsurance();
