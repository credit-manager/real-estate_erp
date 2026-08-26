/**
 * Main Application Entry Point - Modern ES Module
 * Replaces static/js/app.js with modular architecture
 */

import { api } from '../api/client.js';
import { store, actions } from '../store/index.js';
import { showToast, escapeHtml, formatMoney, formatDate, formatNumber } from '../utils/toast.js';
import { BaseComponent } from '../components/BaseComponent.js';
import { DataTable } from '../components/DataTable.js';

// Initialize global state from server-rendered data
function initializeGlobals() {
  // Language and translations
  window.LANG = window.LANG || 'ar';
  window.T = window.T || {};
  window.PERMS = window.PERMS || {};
  window.APP_SETTINGS = window.APP_SETTINGS || {};
  window.CSRF_TOKEN = window.CSRF_TOKEN || '';
  window.LOCALE = window.LANG === 'ar' ? 'ar-EG' : 'en-US';

  // Initialize store with server data
  if (window.T) {
    store.set('settings.translations', window.T);
  }
  if (window.PERMS) {
    store.set('permissions', window.PERMS);
  }
  if (window.APP_SETTINGS) {
    store.set('settings.app', window.APP_SETTINGS);
  }
  if (window.LANG) {
    store.set('ui.language', window.LANG);
    document.documentElement.lang = window.LANG;
    document.documentElement.dir = window.LANG === 'ar' ? 'rtl' : 'ltr';
  }
  if (window.APP_SETTINGS?.theme) {
    store.set('ui.theme', window.APP_SETTINGS.theme);
    document.documentElement.dataset.theme = window.APP_SETTINGS.theme;
  }
}

// Global API functions (backward compatibility)
window.api = api;
window.store = store;
window.actions = actions;
window.showToast = showToast;
window.escapeHtml = escapeHtml;
window.formatMoney = formatMoney;
window.formatDate = formatDate;
window.formatNumber = formatNumber;
window.t = (key) => window.T[key] || key;
window.tv = (value) => window.VALUE_LABELS?.[value] || value;
window.canAction = (module, action) => {
  const perms = store.get('permissions');
  return perms[module]?.[action] === true;
};

// Utility functions
function debounce(fn, delay) {
  let timeoutId;
  return (...args) => {
    clearTimeout(timeoutId);
    timeoutId = setTimeout(() => fn(...args), delay);
  };
}

function throttle(fn, limit) {
  let inThrottle;
  return (...args) => {
    if (!inThrottle) {
      fn(...args);
      inThrottle = true;
      setTimeout(() => inThrottle = false, limit);
    }
  };
}

// DOM Ready initialization
document.addEventListener('DOMContentLoaded', async () => {
  initializeGlobals();

  // Initialize theme
  applyTheme(store.get('ui.theme') || 'light');

  // Initialize sidebar
  initSidebar();

  // Initialize horizontal nav
  initHorizontalNav();

  // Initialize global search
  initGlobalSearch();

  // Initialize AI panel
  initAI();

  // Initialize notifications
  initNotifications();

  // Initialize language switcher
  initLanguageSwitcher();

  // Initialize layout toggle
  initLayoutToggle();

  // Initialize voice input
  initVoiceInput();

  // Page-specific initialization
  const page = document.body.dataset.page;
  if (page) {
    await initPage(page);
  }
});

/**
 * Apply theme
 */
function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  localStorage.setItem('dp-theme', theme);
}

/**
 * Sidebar initialization
 */
function initSidebar() {
  const sidebar = document.getElementById('sidebar');
  const toggle = document.getElementById('sidebar-toggle');
  const closeBtn = document.getElementById('sidebar-close');

  if (!sidebar || !toggle) return;

  // Restore collapsed state
  const collapsed = store.get('ui.sidebarCollapsed');
  if (collapsed) {
    sidebar.classList.add('collapsed');
    document.body.classList.add('sidebar-collapsed');
  }

  toggle.addEventListener('click', () => {
    const collapsed = sidebar.classList.toggle('collapsed');
    document.body.classList.toggle('sidebar-collapsed');
    actions.setSidebarCollapsed(collapsed);
  });

  if (closeBtn) {
    closeBtn.addEventListener('click', () => {
      sidebar.classList.add('collapsed');
      document.body.classList.add('sidebar-collapsed');
      actions.setSidebarCollapsed(true);
    });
  }

  // Nav group toggles
  document.querySelectorAll('.nav-group-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const group = btn.dataset.group;
      const expanded = btn.getAttribute('aria-expanded') === 'true';
      btn.setAttribute('aria-expanded', !expanded);
      const list = document.querySelector(`.nav-group-list[data-group="${group}"]`);
      if (list) {
        list.style.display = expanded ? 'none' : 'block';
      }
      // Persist
      const groups = JSON.parse(localStorage.getItem('dp-nav-groups') || '{}');
      groups[group] = !expanded;
      localStorage.setItem('dp-nav-groups', JSON.stringify(groups));
    });
  });

  // Restore nav group states
  const savedGroups = JSON.parse(localStorage.getItem('dp-nav-groups') || '{}');
  Object.entries(savedGroups).forEach(([group, expanded]) => {
    const btn = document.querySelector(`.nav-group-btn[data-group="${group}"]`);
    const list = document.querySelector(`.nav-group-list[data-group="${group}"]`);
    if (btn && list) {
      btn.setAttribute('aria-expanded', expanded);
      list.style.display = expanded ? 'block' : 'none';
    }
  });
}

/**
 * Horizontal navigation
 */
function initHorizontalNav() {
  const hnav = document.getElementById('hnav');
  if (!hnav) return;

  const indicator = hnav.querySelector('.hnav-indicator');
  const items = hnav.querySelectorAll('.hnav-item');

  function updateIndicator(activeItem) {
    if (!indicator || !activeItem) return;
    const rect = activeItem.getBoundingClientRect();
    const hnavRect = hnav.getBoundingClientRect();
    indicator.style.width = `${activeItem.offsetWidth}px`;
    indicator.style.transform = `translateX(${activeItem.offsetLeft}px)`;
  }

  // Set initial active
  const activeItem = hnav.querySelector('.hnav-item.active') || hnav.querySelector('.hnav-item');
  if (activeItem) updateIndicator(activeItem);

  items.forEach(item => {
    item.addEventListener('click', (e) => {
      // Allow default link behavior for navigation
      items.forEach(i => i.classList.remove('active'));
      item.classList.add('active');
      updateIndicator(item);
    });

    // Hover effect
    item.addEventListener('mouseenter', () => updateIndicator(item));
    item.addEventListener('mouseleave', () => {
      const active = hnav.querySelector('.hnav-item.active');
      if (active) updateIndicator(active);
    });
  });

  // Window resize
  window.addEventListener('resize', () => {
    const active = hnav.querySelector('.hnav-item.active');
    if (active) updateIndicator(active);
  });
}

/**
 * Global search
 */
function initGlobalSearch() {
  const input = document.getElementById('global-search-input');
  const results = document.getElementById('global-search-results');
  if (!input || !results) return;

  const debouncedSearch = debounce(async (query) => {
    if (!query.trim()) {
      results.style.display = 'none';
      return;
    }

    try {
      const data = await api.get('/api/search', { params: { q: query, limit: 8 } });
      renderSearchResults(data, results);
      results.style.display = 'block';
    } catch (error) {
      console.error('Search failed:', error);
    }
  }, 250);

  input.addEventListener('input', (e) => debouncedSearch(e.target.value));
  input.addEventListener('focus', () => debouncedSearch(input.value));

  document.addEventListener('click', (e) => {
    if (!e.target.closest('.global-search')) {
      results.style.display = 'none';
    }
  });

  input.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      results.style.display = 'none';
      input.blur();
    }
    if (e.key === 'Enter') {
      const firstLink = results.querySelector('a');
      if (firstLink) {
        firstLink.click();
      }
    }
  });
}

function renderSearchResults(data, container) {
  if (!data || !Object.keys(data).length) {
    container.innerHTML = '<div class="search-empty">لا توجد نتائج</div>';
    return;
  }

  let html = '';
  for (const [type, items] of Object.entries(data)) {
    if (!items?.length) continue;
    html += `<div class="search-group"><h4>${type}</h4><ul>`;
    items.slice(0, 8).forEach(item => {
      const label = item.name || item.full_name || item.unit_code || item.contract_number || JSON.stringify(item);
      html += `<li><a href="${getItemUrl(type, item)}">${escapeHtml(label)}</a></li>`;
    });
    html += '</ul></div>';
  }
  container.innerHTML = html || '<div class="search-empty">لا توجد نتائج</div>';
}

function getItemUrl(type, item) {
  const urls = {
    customers: `/customers?id=${item.id}`,
    suppliers: `/procurement?supplier=${item.id}`,
    projects: `/projects?id=${item.id}`,
    units: `/real-estate?unit=${item.id}`,
    invoices: `/finance?invoice=${item.id}`,
    employees: `/hr?employee=${item.id}`,
    rentals: `/rentals?contract=${item.id}`,
    sales_orders: `/sales?order=${item.id}`,
    returns: `/sales?return=${item.id}`,
  };
  return urls[type] || '#';
}

/**
 * AI Panel
 */
function initAI() {
  const panel = document.getElementById('ai-search-panel');
  const input = document.getElementById('ai-search-input');
  const btn = document.getElementById('ai-search-btn');
  const results = document.getElementById('ai-search-results');
  if (!panel || !input || !btn || !results) return;

  let isOpen = false;

  function toggle() {
    isOpen = !isOpen;
    panel.style.display = isOpen ? 'block' : 'none';
    if (isOpen) {
      input.focus();
    }
  }

  btn.addEventListener('click', toggle);

  document.addEventListener('click', (e) => {
    if (!e.target.closest('.ai-search')) {
      isOpen = false;
      panel.style.display = 'none';
    }
  });

  input.addEventListener('keydown', async (e) => {
    if (e.key === 'Enter' && input.value.trim()) {
      const question = input.value.trim();
      input.value = '';
      results.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

      try {
        const response = await api.post('/api/ai/query', { question });
        renderAIResults(response, results);
      } catch (error) {
        results.innerHTML = `<div class="alert alert-error">${escapeHtml(error.message)}</div>`;
      }
    }
    if (e.key === 'Escape') {
      isOpen = false;
      panel.style.display = 'none';
    }
  });
}

function renderAIResults(response, container) {
  if (!response.success) {
    container.innerHTML = `<div class="alert alert-error">${escapeHtml(response.message)}</div>`;
    return;
  }

  const { type, answer, data, columns } = response.data;

  switch (type) {
    case 'text':
      container.innerHTML = `<div class="ai-answer">${escapeHtml(answer)}</div>`;
      break;
    case 'count':
      container.innerHTML = `<div class="ai-answer">${escapeHtml(answer)}: <strong>${data}</strong></div>`;
      break;
    case 'sum':
      container.innerHTML = `<div class="ai-answer">${escapeHtml(answer)}: <strong>${formatMoney(data)}</strong></div>`;
      break;
    case 'sql':
      if (data && data.length) {
        const headers = columns || Object.keys(data[0]);
        let html = `<div class="ai-answer">${escapeHtml(answer)}</div><table><thead><tr>`;
        headers.forEach(h => html += `<th>${escapeHtml(h)}</th>`);
        html += '</tr></thead><tbody>';
        data.forEach(row => {
          html += '<tr>';
          headers.forEach(h => html += `<td>${escapeHtml(row[h])}</td>`);
          html += '</tr>';
        });
        html += '</tbody></table>';
        container.innerHTML = html;
      } else {
        container.innerHTML = '<div class="ai-answer">لا توجد نتائج</div>';
      }
      break;
    case 'search':
      if (data && data.length) {
        let html = `<div class="ai-answer">${escapeHtml(answer)}</div><ul>`;
        data.forEach(item => {
          const label = item.name || item.full_name || item.unit_code || JSON.stringify(item);
          html += `<li>${escapeHtml(label)}</li>`;
        });
        html += '</ul>';
        container.innerHTML = html;
      } else {
        container.innerHTML = '<div class="ai-answer">لا توجد نتائج</div>';
      }
      break;
    case 'dashboard':
      let html = `<div class="ai-answer">${escapeHtml(answer)}</div>`;
      if (data) {
        Object.entries(data).forEach(([key, value]) => {
          html += `<div class="dashboard-stat"><span>${escapeHtml(key)}</span><strong>${escapeHtml(value)}</strong></div>`;
        });
      }
      container.innerHTML = html;
      break;
    default:
      container.innerHTML = `<div class="ai-answer">${escapeHtml(answer)}</div>`;
  }
}

/**
 * Notifications
 */
async function initNotifications() {
  const bell = document.getElementById('notifications-bell');
  const dropdown = document.getElementById('notif-dropdown');
  const badge = document.getElementById('notif-badge');
  const list = document.getElementById('notif-list');

  if (!bell || !dropdown) return;

  async function fetchNotifications() {
    try {
      const data = await api.get('/api/notifications');
      const items = Array.isArray(data) ? data : (data.items || []);
      const unread = items.filter(n => !n.read).length;

      if (badge) {
        badge.textContent = unread > 9 ? '9+' : unread;
        badge.style.display = unread > 0 ? 'flex' : 'none';
      }
      actions.setUnreadCount(unread);

      if (list) {
        list.innerHTML = items.slice(0, 10).map(n => `
          <a href="${n.link || '#'}" class="notif-item ${n.read ? '' : 'unread'}">
            <div class="notif-icon">${getNotifIcon(n.type)}</div>
            <div class="notif-content">
              <div class="notif-title">${escapeHtml(n.title)}</div>
              <div class="notif-message">${escapeHtml(n.message)}</div>
              <div class="notif-time">${formatRelativeTime(n.created_at)}</div>
            </div>
          </a>
        `).join('') || '<div class="notif-empty">لا توجد إشعارات</div>';
      }
    } catch (error) {
      console.error('Failed to fetch notifications:', error);
    }
  }

  async function markRead() {
    try {
      await api.post('/api/notifications/read');
      fetchNotifications();
    } catch (error) {
      console.error('Failed to mark notifications read:', error);
    }
  }

  bell.addEventListener('click', (e) => {
    e.stopPropagation();
    dropdown.classList.toggle('show');
    if (dropdown.classList.contains('show')) {
      fetchNotifications();
      markRead();
    }
  });

  document.addEventListener('click', (e) => {
    if (!e.target.closest('.notifications-dropdown')) {
      dropdown.classList.remove('show');
    }
  });

  // Initial fetch
  fetchNotifications();

  // Poll every 60 seconds
  setInterval(fetchNotifications, 60000);
}

function getNotifIcon(type) {
  const icons = {
    payment: '<svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79"/></svg>',
    contract: '<svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor"><path d="M14 2H6c-1.1 0-1.99.9-1.99 2L4 20c0 1.1.89 2 1.99 2H18c1.1 0 2-.9 2-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H11z"/></svg>',
    maintenance: '<svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor"><path d="M19.14 12.94c.04-.31.06-.63.06-.94 0-.31-.02-.63-.06-.94l2.03-1.58c.18-.14.23-.41.12-.61l-1.92-3.32c-.12-.22-.37-.29-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.59-.94l-.36-2.54c-.04-.24-.24-.41-.48-.41h-3.84c-.24 0-.43.17-.47.41l-.36 2.54c-.56.24-1.09.56-1.59.94l-2.39-.96c-.22-.07-.47 0-.59.22L2.74 8.87c-.12.2-.07.47.12.61l2.03 1.58c-.04.31-.06.63-.06.94s.02.63.06.94l-2.03 1.58c-.18.14-.23.41-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.59.94l.36 2.54c.04.24.24.41.48.41h3.84c.24 0 .43-.17.47-.41l.36-2.54c.56-.24 1.09-.56 1.59-.94l2.39.96c.22.07.47 0 .59-.22l1.92-3.32c.11-.2.06-.47-.12-.61l-2.01-1.58zM12 15.6c-1.93 0-3.5-1.57-3.5-3.5s1.57-3.5 3.5-3.5 3.5 1.57 3.5 3.5-1.57 3.5-3.5 3.5z"/></svg>',
    default: '<svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z"/></svg>',
  };
  return icons[type] || icons.default;
}

function formatRelativeTime(dateString) {
  const date = new Date(dateString);
  const now = new Date();
  const diff = Math.floor((now - date) / 1000);

  if (diff < 60) return 'الآن';
  if (diff < 3600) return `منذ ${Math.floor(diff / 60)} دقيقة`;
  if (diff < 86400) return `منذ ${Math.floor(diff / 3600)} ساعة`;
  if (diff < 604800) return `منذ ${Math.floor(diff / 86400)} يوم`;
  return date.toLocaleDateString('ar-EG');
}

/**
 * Language Switcher
 */
function initLanguageSwitcher() {
  const btn = document.getElementById('lang-toggle');
  const menu = document.getElementById('lang-menu');
  if (!btn || !menu) return;

  btn.addEventListener('click', (e) => {
    e.stopPropagation();
    menu.classList.toggle('show');
  });

  document.addEventListener('click', (e) => {
    if (!e.target.closest('.lang-switcher')) {
      menu.classList.remove('show');
    }
  });

  menu.querySelectorAll('[data-lang]').forEach(item => {
    item.addEventListener('click', async (e) => {
      e.preventDefault();
      const lang = e.currentTarget.dataset.lang;
      try {
        await api.post(`/api/language/${lang}`);
        window.location.reload();
      } catch (error) {
        showToast('فشل تغيير اللغة', 'error');
      }
    });
  });

  document.addEventListener('click', (e) => {
    if (!e.target.closest('.lang-switcher')) {
      menu.classList.remove('show');
    }
  });
}

/**
 * Layout Toggle
 */
function initLayoutToggle() {
  const btn = document.getElementById('layout-toggle');
  if (!btn) return;

  const savedLayout = localStorage.getItem('dp-layout') || 'vertical';
  document.body.classList.toggle('layout-horizontal', savedLayout === 'horizontal');
  btn.setAttribute('aria-pressed', savedLayout === 'horizontal');

  btn.addEventListener('click', () => {
    const isHorizontal = document.body.classList.toggle('layout-horizontal');
    localStorage.setItem('dp-layout', isHorizontal ? 'horizontal' : 'vertical');
    btn.setAttribute('aria-pressed', isHorizontal);
  });
}

/**
 * Voice Input
 */
function initVoiceInput() {
  const btn = document.getElementById('voice-btn');
  const input = document.getElementById('global-search-input') || document.getElementById('ai-search-input');
  if (!btn || !input) return;

  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    btn.style.display = 'none';
    return;
  }

  const recognition = new SpeechRecognition();
  recognition.lang = store.get('ui.language') === 'ar' ? 'ar-SA' : 'en-US';
  recognition.continuous = false;
  recognition.interimResults = true;

  let isRecording = false;

  recognition.onresult = (e) => {
    const transcript = Array.from(e.results)
      .map(r => r[0].transcript)
      .join('');
    input.value = transcript;
    // Trigger input event for search
    input.dispatchEvent(new Event('input', { bubbles: true }));
  };

  recognition.onerror = (e) => {
    console.warn('Speech recognition error:', e.error);
    stopRecording();
  };

  recognition.onend = () => {
    stopRecording();
  };

  function startRecording() {
    if (isRecording) return;
    isRecording = true;
    btn.classList.add('recording');
    btn.setAttribute('aria-pressed', 'true');
    try {
      recognition.start();
    } catch (e) {
      console.warn('Speech recognition start failed:', e);
      stopRecording();
    }
  }

  function stopRecording() {
    isRecording = false;
    btn.classList.remove('recording');
    btn.setAttribute('aria-pressed', 'false');
  }

  btn.addEventListener('click', () => {
    if (isRecording) {
      recognition.stop();
    } else {
      startRecording();
    }
  });
}

/**
 * Page-specific initialization
 */
async function initPage(page) {
  switch (page) {
    case 'real-estate':
      await import('../components/RealEstatePage.js');
      break;
    case 'rentals':
      await import('../pages/RentalsPage.js');
      break;
    case 'accounting':
      await import('../pages/AccountingPage.js');
      break;
    case 'hr':
      await import('../pages/HRPage.js');
      break;
    case 'projects':
      await import('../pages/ProjectsPage.js');
      break;
    case 'inventory':
      await import('../pages/InventoryPage.js');
      break;
    case 'crm':
      await import('../pages/CRMPage.js');
      break;
    default:
      break;
  }
}

// Export for use in other modules
export { api, store, actions, showToast, escapeHtml, formatMoney, formatDate, formatNumber, debounce, throttle };
export { store as default };

// Re-export utilities for backward compatibility
window.t = (key) => window.T?.[key] || key;
window.can = (module, action) => {
  const perms = store.get('permissions');
  return perms[module]?.[action] === true;
};