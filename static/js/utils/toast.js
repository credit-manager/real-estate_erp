/**
 * Toast Notification Utility - Modern ES Module
 * Provides consistent toast notifications across the application
 */

let toastContainer = null;
const TOAST_TYPES = ['success', 'error', 'warning', 'info'];

/**
 * Initialize toast container
 */
function initToastContainer() {
  if (toastContainer) return toastContainer;

  toastContainer = document.createElement('div');
  toastContainer.className = 'toast-container';
  toastContainer.setAttribute('role', 'region');
  toastContainer.setAttribute('aria-label', 'Notifications');
  toastContainer.setAttribute('aria-live', 'polite');
  document.body.appendChild(toastContainer);

  return toastContainer;
}

/**
 * Show a toast notification
 * @param {string} message - Message to display
 * @param {string} type - Type: 'success', 'error', 'warning', 'info'
 * @param {number} duration - Duration in ms (default: 3500)
 */
export function showToast(message, type = 'info', duration = 3500) {
  if (!TOAST_TYPES.includes(type)) type = 'info';

  const container = initToastContainer();

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.setAttribute('role', 'alert');
  toast.setAttribute('aria-live', 'assertive');

  // Icon based on type
  const icons = {
    success: '<svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg>',
    error: '<svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/></svg>',
    warning: '<svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor"><path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z"/></svg>',
    info: '<svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z"/></svg>',
  };

  toast.innerHTML = `
    <div class="toast-icon">${icons[type]}</div>
    <div class="toast-message">${escapeHtml(message)}</div>
    <button class="toast-close" aria-label="Close">&times;</button>
  `;

  // Close button handler
  toast.querySelector('.toast-close').addEventListener('click', () => {
    removeToast(toast);
  });

  container.appendChild(toast);

  // Auto remove
  setTimeout(() => removeToast(toast), duration);

  // Animate in
  requestAnimationFrame(() => {
    toast.classList.add('show');
  });

  return toast;
}

/**
 * Remove toast with animation
 */
function removeToast(toast) {
  if (!toast || !toast.parentElement) return;

  toast.classList.add('hide');
  toast.addEventListener('transitionend', () => {
    if (toast.parentElement) {
      toast.parentElement.removeChild(toast);
    }
  }, { once: true });
}

/**
 * Show success toast
 */
export function toastSuccess(message, duration) {
  return showToast(message, 'success', duration);
}

/**
 * Show error toast
 */
export function toastError(message, duration) {
  return showToast(message, 'error', duration);
}

/**
 * Show warning toast
 */
export function toastWarning(message, duration) {
  return showToast(message, 'warning', duration);
}

/**
 * Show info toast
 */
export function toastInfo(message, duration) {
  return showToast(message, 'info', duration);
}

/**
 * Escape HTML to prevent XSS
 */
export function escapeHtml(text) {
  if (!text) return '';
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

/**
 * Clear all toasts
 */
export function clearToasts() {
  if (toastContainer) {
    toastContainer.innerHTML = '';
  }
}

// Make available globally for backward compatibility
if (typeof window !== 'undefined') {
  window.showToast = showToast;
  window.toastSuccess = toastSuccess;
  window.toastError = toastError;
  window.toastWarning = toastWarning;
  window.toastInfo = toastInfo;
  window.escapeHtml = escapeHtml;
  window.clearToasts = clearToasts;
}