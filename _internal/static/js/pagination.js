/* ============================================================
   Dynamic Pro ERP - Shared pagination helper
   Works with the backend helper (utils/pagination.py):
   - Requests ?paged=1&page=N&per_page=M
   - Handles both the envelope {items,total,page,per_page,pages}
     and a plain (already-capped) array response.
   ============================================================ */

class PagedList {
  constructor(opts) {
    this.url = opts.url || "";
    this.params = opts.params || {};
    this.render = opts.render || (() => "");
    this.empty = opts.empty || "";
    this.targetEl = document.getElementById(opts.target);
    this.controlsEl = document.getElementById(opts.controls);
    this.colspan = opts.colspan || 7;
    this.perPage = opts.perPage || 25;
    this.fetch = opts.fetch || null;
    this.page = 1;
    this.pages = 1;
    this.total = 0;
    this.currentRows = [];
    this.onLoad = opts.onLoad || null;
    this.loading = false;
    this._onControlsChange = null;
    this._onSizeChange = null;
  }

  _pageParams() {
    const raw = typeof this.params === "function" ? this.params() : this.params;
    const extra = Object.entries(raw || {})
      .filter(([, v]) => v !== "" && v !== null && v !== undefined)
      .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`)
      .join("&");
    return { page: this.page, perPage: this.perPage, extra, raw: raw || {} };
  }

  _buildUrl() {
    const sep = this.url.indexOf("?") === -1 ? "?" : "&";
    const raw = typeof this.params === "function" ? this.params() : this.params;
    const extra = Object.entries(raw || {})
      .filter(([, v]) => v !== "" && v !== null && v !== undefined)
      .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`)
      .join("&");
    let url = `${this.url}${sep}paged=1&page=${this.page}&per_page=${this.perPage}`;
    if (extra) url += "&" + extra;
    return url;
  }

  async load() {
    if (this.loading) return;
    this.loading = true;
    if (this.targetEl) {
      this.targetEl.innerHTML = `<tr><td colspan="${this.colspan}"><div class="loading"><div class="spinner"></div></div></td></tr>`;
    }
    try {
      let data;
      if (this.fetch) {
        data = await this.fetch(this._pageParams());
      } else {
        data = await api.get(this._buildUrl());
      }
      if (Array.isArray(data)) {
        this.currentRows = data;
        this.total = data.length;
        this.pages = 1;
        this.page = 1;
      } else {
        this.currentRows = data.items || [];
        this.total = data.total || 0;
        this.pages = data.pages || 1;
        this.page = data.page || 1;
      }
      if (this.onLoad) this.onLoad(data);
      this._render();
    } catch (e) {
      if (this.targetEl) {
        this.targetEl.innerHTML = `<tr><td colspan="${this.colspan}"><div class="empty-state">${escapeHtml((e && e.message) || t("common.error"))}</div></td></tr>`;
      }
      throw e;
    } finally {
      this.loading = false;
    }
  }

  goto(page) {
    page = parseInt(page, 10) || 1;
    if (page < 1 || page > this.pages || page === this.page) return;
    this.page = page;
    this.load();
  }

  setPerPage(n) {
    n = parseInt(n, 10) || this.perPage;
    if (n === this.perPage) return;
    this.perPage = n;
    this.page = 1;
    this.load();
  }

  refresh() { return this.load(); }

  _render() {
    if (this.targetEl) {
      this.targetEl.innerHTML = this.currentRows.length
        ? this.render(this.currentRows)
        : (this.empty || `<tr><td colspan="${this.colspan}"><div class="empty-state">${t("pagination.noResults")}</div></td></tr>`);
    }
    if (this.controlsEl) this._renderControls();
  }

  _renderControls() {
    const pages = Math.max(this.pages, 1);
    const page = Math.min(Math.max(this.page, 1), pages);
    const prevDisabled = page <= 1;
    const nextDisabled = page >= pages;

    const win = 2;
    const start = Math.max(1, page - win);
    const end = Math.min(pages, page + win);
    let nums = "";
    if (start > 1) nums += `<button type="button" class="pg-btn" data-pg="1">1</button>`;
    if (start > 2) nums += `<span class="pg-ellipsis">…</span>`;
    for (let p = start; p <= end; p++) {
      nums += `<button type="button" class="pg-btn${p === page ? " active" : ""}" data-pg="${p}">${p}</button>`;
    }
    if (end < pages - 1) nums += `<span class="pg-ellipsis">…</span>`;
    if (end < pages) nums += `<button type="button" class="pg-btn" data-pg="${pages}">${pages}</button>`;

    const sizes = [10, 25, 50, 100, 200]
      .map((s) => `<option value="${s}" ${s === this.perPage ? "selected" : ""}>${s}</option>`)
      .join("");

    this.controlsEl.innerHTML = `
      <div class="pagination-bar">
        <span class="pg-info">${t("pagination.total")}: <strong>${formatNumber(this.total)}</strong>
          <span class="pg-sep">•</span> ${t("pagination.page")} ${page} ${t("pagination.of")} ${pages}</span>
        <div class="pg-btns">
          <button type="button" class="pg-btn" data-pg="${page - 1}" ${prevDisabled ? "disabled" : ""}>${t("pagination.prev")}</button>
          ${nums}
          <button type="button" class="pg-btn" data-pg="${page + 1}" ${nextDisabled ? "disabled" : ""}>${t("pagination.next")}</button>
        </div>
        <label class="pg-size-label">${t("pagination.perPage")}
          <select class="pg-size">${sizes}</select>
        </label>
      </div>`;

    if (this._onControlsChange) this.controlsEl.removeEventListener("click", this._onControlsChange);
    this._onControlsChange = (e) => {
      const btn = e.target.closest(".pg-btn");
      if (btn && !btn.disabled) this.goto(btn.dataset.pg);
    };
    this.controlsEl.addEventListener("click", this._onControlsChange);

    if (this._onSizeChange) this.controlsEl.removeEventListener("change", this._onSizeChange);
    this._onSizeChange = (e) => {
      if (e.target.classList.contains("pg-size")) this.setPerPage(e.target.value);
    };
    this.controlsEl.addEventListener("change", this._onSizeChange);
  }
}

window.PagedList = PagedList;
