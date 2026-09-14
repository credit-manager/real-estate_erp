/* ============================================================
   Profile Module JavaScript
   ============================================================ */

async function saveProfile() {
  const body = {
    full_name: document.getElementById("pf-name").value,
    email: document.getElementById("pf-email").value,
  };
  if (!body.full_name) { showToast(t("users.fullNameRequired"), "warning"); return; }
  try {
    await api.put("/api/users/profile", body);
    showToast(t("profile.saved"));
    setTimeout(() => window.location.reload(), 700);
  } catch (err) { showToast(err.message, "error"); }
}

async function changePassword() {
  const current = document.getElementById("pf-current").value;
  const newPw = document.getElementById("pf-new").value;
  const confirm = document.getElementById("pf-confirm").value;
  if (!current) { showToast(t("profile.currentPassword") + " *", "warning"); return; }
  if (newPw !== confirm) { showToast(t("profile.passwordMismatch"), "warning"); return; }
  if (newPw.length < 6) { showToast(t("profile.passwordShort"), "warning"); return; }
  try {
    await api.put("/api/users/profile/password", {
      current_password: current,
      new_password: newPw,
    });
    showToast(t("profile.passwordChanged"));
    ["pf-current", "pf-new", "pf-confirm"].forEach((id) => document.getElementById(id).value = "");
  } catch (err) { showToast(err.message, "error"); }
}

window.saveProfile = saveProfile;
window.changePassword = changePassword;
