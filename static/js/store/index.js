/**
 * Global Store - Simple Reactive State Management
 * Lightweight alternative to Redux/Vuex for vanilla JS
 */

class Store {
  constructor(initialState = {}) {
    this.state = { ...initialState };
    this.listeners = new Map();
    this.middleware = [];
  }

  /**
   * Get state value by path (e.g., 'user.profile.name')
   */
  get(path) {
    if (!path) return this.state;
    return path.split('.').reduce((obj, key) => obj?.[key], this.state);
  }

  /**
   * Set state value by path
   */
  set(path, value) {
    if (!path) {
      this.state = { ...this.state, ...value };
      this.notify('');
      return;
    }

    const keys = path.split('.');
    const lastKey = keys.pop();
    let current = this.state;

    for (const key of keys) {
      if (!(key in current)) {
        current[key] = {};
      }
      current = current[key];
    }

    current[lastKey] = value;
    this.notify(path);
  }

  /**
   * Subscribe to state changes
   * @param {string} path - Path to watch (empty for all changes)
   * @param {Function} callback - Called with (newValue, oldValue, path)
   * @returns {Function} Unsubscribe function
   */
  subscribe(path, callback) {
    if (!this.listeners.has(path)) {
      this.listeners.set(path, new Set());
    }
    this.listeners.get(path).add(callback);

    // Return unsubscribe function
    return () => {
      this.listeners.get(path)?.delete(callback);
    };
  }

  /**
   * Notify listeners of state change
   */
  notify(path) {
    const newValue = this.get(path);
    // Notify exact path listeners
    this.listeners.get(path)?.forEach(cb => cb(this.get(path), path));
    // Notify root listeners
    if (path !== '') {
      this.listeners.get('')?.forEach(cb => cb(this.state, path));
    }
  }

  /**
   * Add middleware
   */
  use(middleware) {
    this.middleware.push(middleware);
  }

  /**
   * Apply middleware to action
   */
  async dispatch(action) {
    for (const mw of this.middleware) {
      await mw(action, this);
    }
  }

  /**
   * Reset store to initial state
   */
  reset(initialState = {}) {
    this.state = { ...initialState };
    this.notify('');
  }
}

// Create global store instance
export const store = new Store({
  user: null,
  permissions: {},
  settings: {},
  ui: {
    sidebarCollapsed: false,
    theme: 'light',
    language: 'ar',
    layout: 'vertical',
  },
  notifications: {
    unreadCount: 0,
    items: [],
  },
  loading: {
    global: false,
    requests: {},
  },
  cache: {},
});

// Selectors for common state
export const selectUser = () => store.get('user');
export const selectPermissions = () => store.get('permissions');
export const selectTheme = () => store.get('ui.theme');
export const selectLanguage = () => store.get('ui.language');
export const selectSidebarCollapsed = () => store.get('ui.sidebarCollapsed');
export const selectUnreadNotifications = () => store.get('notifications.unreadCount');

// Actions
export const actions = {
  setUser: (user) => store.set('user', user),
  setPermissions: (perms) => store.set('permissions', perms),
  setTheme: (theme) => store.set('ui.theme', theme),
  setLanguage: (lang) => store.set('ui.language', lang),
  toggleSidebar: () => store.set('ui.sidebarCollapsed', !store.get('ui.sidebarCollapsed')),
  setSidebarCollapsed: (collapsed) => store.set('ui.sidebarCollapsed', collapsed),
  setUnreadCount: (count) => store.set('notifications.unreadCount', count),
  addNotification: (notification) => {
    const items = store.get('notifications.items') || [];
    store.set('notifications.items', [notification, ...items].slice(0, 50));
    store.set('notifications.unreadCount', store.get('notifications.unreadCount') + 1);
  },
  markNotificationsRead: () => {
    store.set('notifications.unreadCount', 0);
  },
  setLoading: (key, loading) => store.set(`loading.requests.${key}`, loading),
  setGlobalLoading: (loading) => store.set('loading.global', loading),
  setCache: (key, data, ttl = 300000) => {
    store.set(`cache.${key}`, { data, expires: Date.now() + ttl });
  },
  getCache: (key) => {
    const cached = store.get(`cache.${key}`);
    if (!cached) return null;
    if (cached.expires < Date.now()) {
      return null;
    }
    return cached.data;
  },
};

// Persist UI state to localStorage
const STORAGE_KEY = 'dp-store-ui';
const persisted = localStorage.getItem(STORAGE_KEY);
if (persisted) {
  try {
    const saved = JSON.parse(persisted);
    if (saved.ui) store.set('ui', saved.ui);
  } catch (e) {
    console.warn('Failed to restore UI state:', e);
  }
}

// Persist on changes
store.subscribe('ui', (ui) => {
  localStorage.setItem(STORAGE_KEY, JSON.stringify({ ui }));
});

export default store;