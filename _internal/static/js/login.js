const LOGIN_LANG = window.LANG || window.DEFAULT_LANG || "ar";
const LT = window.T || {};

function lt(key) {
  if (LT[key] !== undefined && LT[key] !== null) return LT[key];
  return key;
}

function setLoginLanguage(lang) {
  fetch("/api/language/" + lang, { method: "POST" }).then(() => {
    window.location.reload();
  });
}

const langToggle = document.getElementById("lang-toggle");
if (langToggle) {
  langToggle.addEventListener("click", () => {
    setLoginLanguage(LOGIN_LANG === "ar" ? "en" : "ar");
  });
}

const loginThemeToggle = document.getElementById("theme-toggle");
if (loginThemeToggle) {
  loginThemeToggle.addEventListener("click", () => {
    const cur = localStorage.getItem("dp-theme") || "light";
    const next = cur === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem("dp-theme", next); } catch (e) {}
    window.location.reload();
  });
}

// Sync icon with the actual (client-side) theme
(function syncLoginTheme() {
  const dark = (localStorage.getItem("dp-theme") || "light") === "dark";
  const btn = document.getElementById("theme-toggle");
  if (!btn) return;
  const darkIcon = btn.querySelector(".theme-icon-dark");
  const lightIcon = btn.querySelector(".theme-icon-light");
  if (darkIcon) darkIcon.style.display = dark ? "none" : "";
  if (lightIcon) lightIcon.style.display = dark ? "" : "none";
  btn.title = dark ? lt("common.light") : lt("common.dark");
})();

// إظهار حقل كلمة مرور الخادم إذا كان مطلوبًا
(function initAccessPassword() {
  fetch("/api/server-info")
    .then((r) => r.json())
    .then((info) => {
      if (info && info.access_password_required) {
        const group = document.getElementById("access-password-group");
        const input = document.getElementById("access-password");
        if (group) group.style.display = "";
        if (input) input.required = true;
      }
    })
    .catch(() => {});
})();

document.getElementById("login-form").addEventListener("submit", async (e) => {
  e.preventDefault();

  const username = document.getElementById("username").value;
  const password = document.getElementById("password").value;
  const accessPassword = document.getElementById("access-password").value;
  const errorBox = document.getElementById("login-error");
  const btn = document.getElementById("login-btn");

  errorBox.style.display = "none";
  btn.disabled = true;
  btn.textContent = lt("login.loggingIn");

  try {
    const res = await fetch("/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password, access_password: accessPassword }),
    });

    const data = await res.json();

    if (data.success) {
      window.location.href = data.user && data.user.must_change_password
        ? "/change-password"
        : "/dashboard";
    } else {
      errorBox.textContent = data.message || lt("login.invalid");
      errorBox.style.display = "block";
      btn.disabled = false;
      btn.textContent = lt("common.login");
    }
  } catch (err) {
    errorBox.textContent = lt("login.serverError");
    errorBox.style.display = "block";
    btn.disabled = false;
    btn.textContent = lt("common.login");
  }
});

// Password visibility toggle
(function initPasswordToggles() {
  document.querySelectorAll(".pw-toggle").forEach(function(btn) {
    btn.addEventListener("click", function() {
      var wrap = btn.closest(".pw-wrap");
      var input = wrap ? wrap.querySelector("input") : null;
      if (!input) return;
      var isPassword = input.type === "password";
      input.type = isPassword ? "text" : "password";
      btn.classList.toggle("visible", isPassword);
      input.focus();
    });
  });
})();
