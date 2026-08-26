/**
 * Base Component Class - Foundation for UI Components
 * Provides lifecycle, event handling, and rendering utilities
 */

export class BaseComponent {
  constructor(options = {}) {
    this.element = null;
    this.options = { ...this.defaultOptions, ...options };
    this.children = [];
    this.eventListeners = new Map();
    this.isMounted = false;
    this.props = options.props || {};
    this.state = { ...this.defaultState, ...options.initialState };
  }

  get defaultOptions() {
    return {
      tag: 'div',
      className: '',
      attributes: {},
    };
  }

  get defaultState() {
    return {};
  }

  /**
   * Create the component element
   */
  createElement() {
    this.element = document.createElement(this.options.tag);
    if (this.options.className) {
      this.element.className = this.options.className;
    }
    Object.entries(this.options.attributes).forEach(([key, value]) => {
      this.element.setAttribute(key, value);
    });
    return this.element;
  }

  /**
   * Render the component - override in subclasses
   */
  render() {
    return '';
  }

  /**
   * Mount component to DOM
   * @param {HTMLElement|string} target - Target element or selector
   */
  mount(target) {
    const container = typeof target === 'string'
      ? document.querySelector(target)
      : target;

    if (!container) {
      throw new Error(`Mount target not found: ${target}`);
    }

    if (!this.element) {
      this.createElement();
    }

    this.element.innerHTML = this.render();
    container.appendChild(this.element);
    this.isMounted = true;
    this.onMount();
    this.bindEvents();
    return this;
  }

  /**
   * Called after component is mounted
   */
  onMount() {}

  /**
   * Bind event listeners
   */
  bindEvents() {}

  /**
   * Add event listener with automatic cleanup
   * @param {EventTarget} target
   * @param {string} event
   * @param {Function} handler
   * @param {Object} options
   */
  on(target, event, handler, options) {
    target.addEventListener(event, handler, options);
    if (!this.eventListeners.has(target)) {
      this.eventListeners.set(target, []);
    }
    this.eventListeners.get(target).push({ event, handler, options });
  }

  /**
   * Remove event listener
   */
  off(target, event, handler) {
    target.removeEventListener(event, handler);
    const listeners = this.eventListeners.get(target);
    if (listeners) {
      const index = listeners.findIndex(l => l.event === event && l.handler === handler);
      if (index > -1) listeners.splice(index, 1);
    }
  }

  /**
   * Update component state and re-render
   */
  setState(newState) {
    this.state = { ...this.state, ...newState };
    if (this.isMounted) {
      this.update();
    }
  }

  /**
   * Update component DOM
   */
  update() {
    if (!this.element) return;
    const newHtml = this.render();
    if (this.element.innerHTML !== newHtml) {
      this.element.innerHTML = newHtml;
      this.bindEvents();
    }
  }

  /**
   * Find child element within component
   */
  $(selector) {
    return this.element?.querySelector(selector);
  }

  $$(selector) {
    return this.element?.querySelectorAll(selector) || [];
  }

  /**
   * Emit custom event
   */
  emit(eventName, detail = {}) {
    if (this.element) {
      this.element.dispatchEvent(new CustomEvent(eventName, {
        detail,
        bubbles: true,
        composed: true,
      }));
    }
  }

  /**
   * Listen for custom event
   */
  onCustom(eventName, handler) {
    if (this.element) {
      this.element.addEventListener(eventName, handler);
      // Track for cleanup
      if (!this.eventListeners.has(this.element)) {
        this.eventListeners.set(this.element, []);
      }
      this.eventListeners.get(this.element).push({ event: eventName, handler });
    }
  }

  /**
   * Unmount and cleanup
   */
  destroy() {
    // Remove event listeners
    this.eventListeners.forEach((listeners, target) => {
      listeners.forEach(({ event, handler, options }) => {
        target.removeEventListener(event, handler, options);
      });
    });
    this.eventListeners.clear();

    // Destroy children
    this.children.forEach(child => child.destroy());
    this.children = [];

    // Remove from DOM
    if (this.element?.parentElement) {
      this.element.parentElement.removeChild(this.element);
    }
    this.element = null;
    this.isMounted = false;
  }
}

/**
 * Functional component helper
 */
export function createComponent(renderFn, options = {}) {
  return class extends BaseComponent {
    render() {
      return renderFn(this.props, this.state);
    }
    constructor(props = {}) {
      super({ ...options, props });
    }
  };
}

// Utility for creating elements with JSX-like syntax
export function h(tag, props = {}, ...children) {
  const element = document.createElement(tag);
  Object.entries(props).forEach(([key, value]) => {
    if (key === 'className' || key === 'class') {
      element.className = value;
    } else if (key.startsWith('on') && typeof value === 'function') {
      const event = key.slice(2).toLowerCase();
      element.addEventListener(event, value);
    } else if (key === 'style' && typeof value === 'object') {
      Object.assign(element.style, value);
    } else if (key === 'dataset' && typeof value === 'object') {
      Object.entries(value).forEach(([k, v]) => {
        element.dataset[k] = v;
      });
    } else if (typeof value === 'boolean') {
      if (value) element.setAttribute(key, '');
    } else if (value != null) {
      element.setAttribute(key, value);
    }
  });

  children.flat().forEach(child => {
    if (child instanceof Node) {
      element.appendChild(child);
    } else if (child != null) {
      element.appendChild(document.createTextNode(String(child)));
    }
  });

  return element;
}

export default BaseComponent;