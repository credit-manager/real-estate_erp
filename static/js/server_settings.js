(function () {
  "use strict";

  const T = window.T || {};
  const lt = (k) => (T[k] !== undefined && T[k] !== null ? T[k] : k);

  const wrap = document.getElementById("settings-form-wrap");
  const loading = document.getElementById("settings-loading");
  const msg = document.getElementById("settings-msg");
  const portInput = document.getElementById("settings-port");
  const passInput = document.getElementById("settings-access-password");
  const autoStartInput = document.getElementById("settings-autostart");
  const saveBtn = document.getElementById("settings-save");
  const addrList = document.getElementById("settings-addresses");

  if (!wrap) return;

  function showMsg(text, kind) {
    msg.textContent = text;
    msg.className = "settings-msg " + (kind || "");
    msg.style.display = "block";
  }

  function hideMsg() {
    msg.style.display = "none";
  }

  function renderAddresses(addresses, port) {
    addrList.innerHTML = "";
    const ips = (addresses && addresses.length) ? addresses : [];
    if (!ips.length) {
      addrList.innerHTML = '<div class="form-hint">-</div>';
      return;
    }
    ips.forEach((ip) => {
      const row = document.createElement("div");
      row.className = "settings-address-row";

      const link = document.createElement("code");
      link.className = "settings-address-url";
      link.textContent = "http://" + ip + ":" + port;

      const copy = document.createElement("button");
      copy.type = "button";
      copy.className = "btn btn-ghost btn-sm";
      copy.textContent = lt("serverSettings.copy");
      copy.addEventListener("click", () => {
        const url = "http://" + ip + ":" + port;
        const done = () => {
          copy.textContent = lt("serverSettings.copied");
          setTimeout(() => (copy.textContent = lt("serverSettings.copy")), 1500);
        };
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(url).then(done).catch(done);
        } else {
          const ta = document.createElement("textarea");
          ta.value = url;
          document.body.appendChild(ta);
          ta.select();
          try { document.execCommand("copy"); } catch (e) {}
          document.body.removeChild(ta);
          done();
        }
      });

      row.appendChild(link);
      row.appendChild(copy);
      addrList.appendChild(row);
    });
  }

  async function load() {
    try {
      const res = await fetch("/api/server-settings");
      const data = await res.json();
      if (!data.success) throw new Error("failed");
      portInput.value = data.port;
      passInput.value = "";
      passInput.placeholder = data.access_password_set ? "••••••••" : "";
      autoStartInput.checked = !!data.auto_start;
      renderAddresses(data.network_addresses, data.port);

      var geminiKey = document.getElementById("settings-gemini-key");
      var geminiModel = document.getElementById("settings-gemini-model");
      if (geminiKey) geminiKey.placeholder = data.gemini_api_key_set ? "••••••••" : "";
      if (geminiModel) geminiModel.value = data.gemini_model || "gemini-2.0-flash";

      loading.style.display = "none";
      wrap.style.display = "";
    } catch (err) {
      loading.textContent = lt("serverSettings.error");
    }
  }

  if (saveBtn) {
    saveBtn.addEventListener("click", async () => {
      saveBtn.disabled = true;
      const original = saveBtn.textContent;
      saveBtn.textContent = lt("serverSettings.saving");
      hideMsg();
      try {
        const port = parseInt(portInput.value, 10);
        const body = {
          port: port,
          auto_start: autoStartInput.checked,
        };
        // أرسل كلمة المرور فقط عند كتابة واحدة جديدة (لا نرسل القيمة الحالية أبداً)
        if (passInput.value.trim() !== "") {
          body.access_password = passInput.value;
        }
        const res = await fetch("/api/server-settings", {
          method: "POST",
          headers: { "Content-Type": "application/json", ...(window.CSRF_TOKEN ? { "X-CSRF-Token": window.CSRF_TOKEN } : {}) },
          body: JSON.stringify(body),
        });
        const data = await res.json();
        if (data.success) {
          if (data.port_changed) {
            showMsg(lt("serverSettings.savedRestart"), "settings-msg-warn");
            renderAddresses(null, portInput.value);
            const restartBtn = document.createElement("button");
            restartBtn.type = "button";
            restartBtn.className = "btn btn-primary";
            restartBtn.textContent = lt("serverSettings.restart");
            restartBtn.addEventListener("click", async () => {
              const rh = {};
              if (window.CSRF_TOKEN) rh["X-CSRF-Token"] = window.CSRF_TOKEN;
              await fetch("/api/server-restart", { method: "POST", headers: rh });
            });
            msg.appendChild(restartBtn);
          } else {
            showMsg(lt("serverSettings.saved"), "settings-msg-ok");
            renderAddresses(null, portInput.value);
          }
        } else {
          showMsg(lt("serverSettings.error"), "settings-msg-error");
        }
      } catch (err) {
        showMsg(lt("serverSettings.error"), "settings-msg-error");
      }
      saveBtn.disabled = false;
      saveBtn.textContent = original;
    });
  }

  var saveAiBtn = document.getElementById("settings-save-ai");
  if (saveAiBtn) {
    saveAiBtn.addEventListener("click", async function () {
      saveAiBtn.disabled = true;
      var orig = saveAiBtn.textContent;
      saveAiBtn.textContent = lt("serverSettings.saving");
      hideMsg();
      try {
        var body = {};
        var geminiKey = document.getElementById("settings-gemini-key");
        var geminiModel = document.getElementById("settings-gemini-model");
        if (geminiKey && geminiKey.value.trim() !== "") {
          body.gemini_api_key = geminiKey.value.trim();
        }
        if (geminiModel) body.gemini_model = geminiModel.value;
        var res = await fetch("/api/server-settings", {
          method: "POST",
          headers: { "Content-Type": "application/json", ...(window.CSRF_TOKEN ? { "X-CSRF-Token": window.CSRF_TOKEN } : {}) },
          body: JSON.stringify(body),
        });
        var data = await res.json();
        if (data.success) {
          showMsg(lt("serverSettings.saved"), "settings-msg-ok");
          if (geminiKey) geminiKey.placeholder = "••••••••";
        } else {
          showMsg(lt("serverSettings.error"), "settings-msg-error");
        }
      } catch (err) {
        showMsg(lt("serverSettings.error"), "settings-msg-error");
      }
      saveAiBtn.disabled = false;
      saveAiBtn.textContent = orig;
    });
  }

  load();
})();
