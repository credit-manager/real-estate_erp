/* ============================================================
   Backup Module JavaScript
   ============================================================ */

function exportBackup() {
  fetch("/api/backup/export", { method: "GET" })
    .then((res) => {
      if (!res.ok) throw new Error(t("common.error"));
      return res.blob();
    })
    .then((blob) => {
      const a = document.createElement("a");
      const url = URL.createObjectURL(blob);
      a.href = url;
      a.download = `backup_${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "_")}.json`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      showToast(t("backup.exportDone"));
    })
    .catch(() => showToast(t("common.error"), "error"));
}

function importBackup() {
  const file = document.getElementById("backup-file").files[0];
  if (!file) { showToast(t("backup.fileRequired"), "warning"); return; }
  if (!confirm(t("backup.confirmImport"))) return;
  const formData = new FormData();
  formData.append("file", file);
  const h = {};
  if (window.CSRF_TOKEN) h["X-CSRF-Token"] = window.CSRF_TOKEN;
  fetch("/api/backup/import", { method: "POST", body: formData, headers: h })
    .then(async (res) => {
      const data = await res.json();
      if (!res.ok) throw new Error(t(data.error_key) || data.message || t("backup.restoreFailed"));
      showToast(t("backup.importDone"));
      setTimeout(() => window.location.href = "/dashboard", 1200);
    })
    .catch((err) => showToast(err.message, "error"));
}

window.exportBackup = exportBackup;
window.importBackup = importBackup;

// ===== Automatic backup settings =====

async function loadBackupSettings() {
  try {
    const data = await api.get("/api/backup/settings");
    const s = data.settings || {};
    document.getElementById("backup-auto-enabled").checked = !!s.backup_auto_enabled;
    document.getElementById("backup-auto-interval").value = s.backup_auto_interval_days || 1;
    document.getElementById("backup-auto-keep").value = s.backup_auto_keep || 10;
    document.getElementById("backup-auto-folder").value = s.backup_auto_folder || "";
    const last = s.backup_auto_last;
    document.getElementById("backup-auto-last").textContent =
      t("backup.autoLast") + ": " + (last ? last.replace("T", " ").slice(0, 19) : "—");
  } catch (err) { showToast(err.message, "error"); }
}

async function saveBackupSettings() {
  const body = {
    backup_auto_enabled: document.getElementById("backup-auto-enabled").checked,
    backup_auto_interval_days: parseInt(document.getElementById("backup-auto-interval").value) || 1,
    backup_auto_keep: parseInt(document.getElementById("backup-auto-keep").value) || 10,
    backup_auto_folder: document.getElementById("backup-auto-folder").value.trim(),
  };
  try {
    await api.post("/api/backup/settings", body);
    showToast(t("common.saved"));
    loadBackupSettings();
  } catch (err) { showToast(err.message, "error"); }
}

window.saveBackupSettings = saveBackupSettings;

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", loadBackupSettings);
} else {
  loadBackupSettings();
}
