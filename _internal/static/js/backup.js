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

// ===== Cloud backup settings (WebDAV / S3) =====

async function loadCloudSettings() {
  try {
    const data = await api.get("/api/backup/cloud");
    const s = data.settings || {};
    document.getElementById("backup-cloud-enabled").checked = !!s.backup_cloud_enabled;
    document.getElementById("backup-cloud-type").value = s.backup_cloud_type === "s3" ? "s3" : "webdav";
    document.getElementById("backup-cloud-url").value = s.backup_cloud_url || "";
    document.getElementById("backup-cloud-user").value = s.backup_cloud_user || "";
    document.getElementById("backup-cloud-region").value = s.backup_cloud_region || "";
    document.getElementById("backup-cloud-bucket").value = s.backup_cloud_bucket || "";
    document.getElementById("backup-cloud-secret").value = "";
    document.getElementById("backup-cloud-secret-hint").textContent = s.backup_cloud_secret_set
      ? t("backup.cloudSecretHintSet")
      : t("backup.cloudSecretHint");
    toggleCloudBucket();
    const last = [];
    if (s.backup_cloud_last_status) last.push(t("backup.cloudStatus") + ": " + (s.backup_cloud_last_status === "ok" ? t("backup.cloudOk") : t("backup.cloudError")));
    if (s.backup_cloud_last_at) last.push(s.backup_cloud_last_at.replace("T", " ").slice(0, 19));
    if (s.backup_cloud_last_error) last.push(s.backup_cloud_last_error);
    document.getElementById("backup-cloud-last").textContent = last.join(" — ");
  } catch (err) { showToast(err.message, "error"); }
}

function toggleCloudBucket() {
  const isS3 = document.getElementById("backup-cloud-type").value === "s3";
  const g = document.getElementById("backup-cloud-bucket-group");
  if (g) g.style.display = isS3 ? "" : "none";
}

async function saveCloudSettings(test) {
  const body = {
    backup_cloud_enabled: document.getElementById("backup-cloud-enabled").checked,
    backup_cloud_type: document.getElementById("backup-cloud-type").value,
    backup_cloud_url: document.getElementById("backup-cloud-url").value.trim(),
    backup_cloud_user: document.getElementById("backup-cloud-user").value.trim(),
    backup_cloud_secret: document.getElementById("backup-cloud-secret").value.trim(),
    backup_cloud_bucket: document.getElementById("backup-cloud-bucket").value.trim(),
    backup_cloud_region: document.getElementById("backup-cloud-region").value.trim(),
    action: test ? "test" : ""
  };
  try {
    const data = await api.post("/api/backup/cloud", body);
    if (test) showToast(t("backup.cloudTestDone") + (data.detail ? " " + data.detail : ""), "success");
    else showToast(t("common.saved"));
    loadCloudSettings();
  } catch (err) { showToast(err.message || t("backup.cloudTestFailed"), "error"); }
}

window.saveCloudSettings = saveCloudSettings;
document.getElementById("backup-cloud-type") && document.getElementById("backup-cloud-type").addEventListener("change", toggleCloudBucket);

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", function () { loadBackupSettings(); loadCloudSettings(); });
} else {
  loadBackupSettings();
  loadCloudSettings();
}
