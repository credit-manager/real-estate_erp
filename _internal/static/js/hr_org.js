/* HR Org Chart */
async function loadOrgChart() {
  try {
    const data = await api.get("/api/hr/org-chart");
    const depts = data.departments || [];
    const emps = data.employees || [];
    const container = document.getElementById("org-chart");
    document.getElementById("org-empty").style.display = depts.length ? "none" : "";

    container.innerHTML = depts.map((d) => {
      const deptEmps = emps.filter((e) => e.department_id === d.id);
      const managers = deptEmps.filter((e) => e.manager_id === null);
      const members = deptEmps.filter((e) => e.manager_id !== null);
      const empCard = (e, isMgr) => `
        <div class="org-member">
          <div class="org-avatar">${escapeHtml((e.full_name || "?").charAt(0))}</div>
          <div class="org-info">
            <b>${escapeHtml(e.full_name)}</b>
            <span>${escapeHtml(e.position_name || "")}${isMgr ? " · " + t("hr.deptManager") : ""}</span>
          </div>
        </div>`;
      return `
        <div class="org-dept">
          <div class="org-dept-header">
            <div class="org-dept-icon">🏢</div>
            <div>
              <b>${escapeHtml(d.name)}</b>
              <span>${deptEmps.length} ${t("hr.employeesCount")}</span>
            </div>
          </div>
          <div class="org-members">
            ${managers.map((e) => empCard(e, true)).join("")}
            ${members.map((e) => empCard(e, false)).join("")}
          </div>
        </div>`;
    }).join("");
  } catch (e) {
    showToast(e.message || t("common.error"), "error");
  }
}

loadOrgChart();
