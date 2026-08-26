/**
 * DataTable Component - Reusable table with sorting, pagination, actions
 */

import { BaseComponent } from './BaseComponent.js';

export class DataTable extends BaseComponent {
  constructor(options = {}) {
    super({
      tag: 'div',
      className: 'data-table-container',
      ...options,
    });

    this.columns = options.columns || [];
    this.data = options.data || [];
    this.sortable = options.sortable !== false;
    this.pagination = options.pagination !== false;
    this.pageSize = options.pageSize || 25;
    this.currentPage = 1;
    this.sortColumn = null;
    this.sortDirection = 'asc';
    this.actions = options.actions || [];
    this.rowKey = options.rowKey || 'id';
    this.emptyMessage = options.emptyMessage || 'لا توجد بيانات';
    this.loading = false;
    this.totalItems = 0;
    this.totalPages = 1;
    this.onAction = options.onAction;
    this.fetchFn = options.fetchFn;
    this.filters = options.filters || {};
  }

  get defaultState() {
    return {
      data: [],
      loading: false,
      currentPage: 1,
      sortColumn: null,
      sortDirection: 'asc',
      totalItems: 0,
    };
  }

  async loadData(page = 1, params = {}) {
    if (!this.fetchFn) return;

    this.setState({ loading: true });

    try {
      const params = {
        page,
        per_page: this.pageSize,
        paged: 1,
        sort: this.sortColumn,
        direction: this.sortDirection,
        ...this.filters,
      };

      const response = await this.fetchFn(this.state.currentPage, params);

      this.data = response.items || response.data || response || [];
      this.totalItems = response.total || this.data.length;
      this.totalPages = response.pages || Math.ceil(this.totalItems / this.pageSize) || 1;
      this.currentPage = page;

      this.setState({
        data: this.data,
        loading: false,
        currentPage: page,
        totalItems: this.totalItems,
      });
    } catch (error) {
      this.setState({ loading: false });
      console.error('Failed to load data:', error);
    }
  }

  sort(column) {
    if (!this.sortable) return;

    if (this.sortColumn === column.key) {
      this.sortDirection = this.sortDirection === 'asc' ? 'desc' : 'asc';
    } else {
      this.sortColumn = column.key;
      this.sortDirection = 'asc';
    }

    if (this.fetchFn) {
      this.loadData(1);
    } else {
      // Client-side sort
      this.data.sort((a, b) => {
        const aVal = a[column.key];
        const bVal = b[column.key];
        const dir = this.sortDirection === 'asc' ? 1 : -1;
        if (aVal < bVal) return -1 * dir;
        if (aVal > bVal) return 1 * dir;
        return 0;
      });
      this.render();
    }
  }

  setPage(page) {
    if (page < 1 || page > this.totalPages) return;
    if (this.fetchFn) {
      this.loadData(page);
    } else {
      this.currentPage = page;
      this.render();
    }
  }

  setFilters(filters) {
    this.filters = { ...this.filters, ...filters };
    if (this.fetchFn) {
      this.loadData(1);
    }
  }

  handleAction(action, row) {
    if (this.onAction) {
      this.onAction(action, row);
    }
  }

  render() {
    if (this.loading) {
      return `
        <div class="table-wrapper">
          <table>
            <thead>
              <tr>${this.columns.map(c => `<th>${this.escapeHtml(c.label)}</th>`).join('')}
              ${this.actions.length ? '<th>الإجراءات</th>' : ''}
            </tr>
          </thead>
          <tbody>
            <tr><td colspan="${this.columns.length + (this.actions.length ? 1 : 0)}">
              <div class="loading"><div class="spinner"></div></div>
            </td></tr>
          </tbody>
        </table>
      </div>`;
    }

    if (!this.data.length) {
      return `
        <div class="table-wrapper">
          <table>
            <thead>
              <tr>${this.columns.map(c => `<th>${this.escapeHtml(c.label)}</th>`).join('')}
              ${this.actions.length ? '<th>الإجراءات</th>' : ''}
            </tr>
          </thead>
          <tbody>
            <tr><td colspan="${this.columns.length + (this.actions.length ? 1 : 0)}">
              <div class="empty-state">${this.escapeHtml(this.emptyMessage)}</div>
            </td></tr>
          </tbody>
        </table>
      </div>`;
    }

    return `
      <div class="table-wrapper">
        <table>
          <thead>
            <tr>
              ${this.columns.map(c => `
                <th ${c.sortable !== false && this.sortable ? 'class="sortable"' : ''}
                    data-sort="${this.escapeHtml(c.key)}"
                    style="${c.width ? `width:${c.width}` : ''}">
                  ${this.escapeHtml(c.label)}
                  ${c.sortable !== false && this.sortable && this.sortColumn === c.key
                    ? `<span class="sort-icon">${this.sortDirection === 'asc' ? '▲' : '▼'}</span>`
                    : ''}
                </th>
              `).join('')}
              ${this.actions.length ? '<th>الإجراءات</th>' : ''}
            </tr>
          </thead>
          <tbody>
            ${this.data.map(row => `
              <tr data-row-key="${row[this.rowKey]}">
                ${this.columns.map(c => `
                  <td>${this.renderCell(row, c)}</td>
                `).join('')}
                ${this.actions.length ? `
                  <td>
                    <div class="table-actions">
                      ${this.actions.map(a => `
                        <button class="btn btn-${a.variant || 'primary'} btn-sm"
                                data-action="${a.key}"
                                data-row-key="${row[this.rowKey]}"
                                ${a.confirm ? `data-confirm="${this.escapeHtml(a.confirm)}"` : ''}
                                ${a.condition && !a.condition(row) ? 'disabled style="display:none;"` : ''}>
                          ${this.escapeHtml(a.label)}
                        </button>
                      `).join('')}
                    </div>
                  </td>
                ` : ''}
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
      ${this.pagination && this.totalPages > 1 ? this.renderPagination() : ''}
    `;
  }

  renderCell(row, column) {
    if (column.render) {
      return column.render(row[column.key], row);
    }

    let value = row[column.key];
    if (value === null || value === undefined) return '—';

    if (column.type === 'currency') {
      return this.formatMoney(value);
    }
    if (column.type === 'date') {
      return this.formatDate(value);
    }
    if (column.type === 'boolean') {
      return value ? '<span class="badge badge-success">نعم</span>' : '<span class="badge badge-muted">لا</span>';
    }
    if (column.type === 'badge') {
      const variant = column.badgeVariant?.[value] || 'muted';
      return `<span class="badge badge-${variant}">${this.escapeHtml(value)}</span>`;
    }
    if (column.type === 'status') {
      const variant = column.statusVariant?.[value] || 'muted';
      return `<span class="badge badge-${variant}">${this.escapeHtml(value)}</span>`;
    }

    return this.escapeHtml(value);
  }

  renderPagination() {
    const pages = [];
    const maxVisible = 5;
    let start = Math.max(1, this.currentPage - Math.floor(maxVisible / 2));
    let end = Math.min(this.totalPages, start + maxVisible - 1);

    if (end - start + 1 < maxVisible) {
      start = Math.max(1, end - maxVisible + 1);
    }

    for (let i = start; i <= end; i++) {
      pages.push(`<button class="page-btn ${i === this.currentPage ? 'active' : ''}" data-page="${i}">${i}</button>`);
    }

    return `
      <div class="pagination">
        <button class="page-btn" data-page="1" ${this.currentPage === 1 ? 'disabled' : ''}>&laquo;</button>
        <button class="page-btn" data-page="${this.currentPage - 1}" ${this.currentPage === 1 ? 'disabled' : ''}>&lsaquo;</button>
        ${pages.join('')}
        <button class="page-btn" data-page="${this.currentPage + 1}" ${this.currentPage === this.totalPages ? 'disabled' : ''}>&rsaquo;</button>
        <button class="page-btn" data-page="${this.totalPages}" ${this.currentPage === this.totalPages ? 'disabled' : ''}>&raquo;</button>
        <span class="pagination-info">صفحة ${this.currentPage} من ${this.totalPages} (${this.totalItems} عنصر)</span>
      </div>
    `;
  }

  bindEvents() {
    if (!this.element) return;

    // Sort click
    this.element.querySelectorAll('th.sortable').forEach(th => {
      this.on(th, 'click', (e) => {
        const key = e.currentTarget.dataset.sort;
        const column = this.columns.find(c => c.key === key);
        if (column) this.sort(column);
      });
    });

    // Action buttons
    this.element.querySelectorAll('[data-action]').forEach(btn => {
      this.on(btn, 'click', (e) => {
        const actionKey = e.currentTarget.dataset.action;
        const rowKey = e.currentTarget.dataset.rowKey;
        const confirmMsg = e.currentTarget.dataset.confirm;

        const row = this.data.find(r => r[this.rowKey] == rowKey);
        if (!row) return;

        if (confirmMsg && !confirm(confirmMsg)) return;

        const action = this.actions.find(a => a.key === actionKey);
        if (action?.handler) {
          action.handler(row, this);
        } else {
          this.handleAction(actionKey, row);
        }
      });
    });

    // Pagination
    this.element.querySelectorAll('.page-btn[data-page]').forEach(btn => {
      this.on(btn, 'click', (e) => {
        const page = parseInt(e.currentTarget.dataset.page, 10);
        if (!isNaN(page)) this.setPage(page);
      });
    });
  }

  escapeHtml(text) {
    if (!text && text !== 0) return '';
    const div = document.createElement('div');
    div.textContent = String(text);
    return div.innerHTML;
  }

  formatMoney(value) {
    return new Intl.NumberFormat('ar-EG', {
      style: 'currency',
      currency: 'SAR',
      minimumFractionDigits: 2,
    }).format(value);
  }

  formatDate(value) {
    if (!value) return '—';
    const date = new Date(value);
    return date.toLocaleDateString('ar-EG');
  }
}

export default DataTable;