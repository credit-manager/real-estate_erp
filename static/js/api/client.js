/**
 * API Client Module - Modern ES Module
 * Handles all HTTP requests with CSRF protection, error handling, and i18n
 */

// Default configuration
const DEFAULT_CONFIG = {
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
  },
};

// CSRF token getter
function getCsrfToken() {
  return document.querySelector('meta[name="csrf-token"]')?.content ||
         window.CSRF_TOKEN ||
         '';
}

// Error class for API errors
export class ApiError extends Error {
  constructor(message, status, errorKey, data) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.errorKey = errorKey;
    this.data = data;
  }
}

// Toast notification function
function showToast(message, type = 'info') {
  if (window.showToast) {
    window.showToast(message, type);
  } else {
    console.log(`[${type.toUpperCase()}] ${message}`);
  }
}

// Main API client
class ApiClient {
  constructor(config = {}) {
    this.config = { ...DEFAULT_CONFIG, ...config };
    this.interceptors = {
      request: [],
      response: [],
    };
  }

  // Add request interceptor
  addRequestInterceptor(fn) {
    this.interceptors.request.push(fn);
  }

  // Add response interceptor
  addResponseInterceptor(fn) {
    this.interceptors.response.push(fn);
  }

  // Build URL with query params
  buildUrl(endpoint, params = {}) {
    const url = new URL(`${this.config.baseURL}${endpoint}`, window.location.origin);
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        url.searchParams.append(key, value);
      }
    });
    return url.toString();
  }

  // Main request method
  async request(method, endpoint, options = {}) {
    const url = this.buildUrl(endpoint, options.params);
    const csrfToken = getCsrfToken();

    const headers = {
      ...this.config.headers,
      ...options.headers,
    };

    // Add CSRF token for state-changing methods
    if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method.toUpperCase())) {
      headers['X-CSRF-Token'] = csrfToken;
    }

    // Apply request interceptors
    let finalOptions = { method, headers, ...options };
    for (const interceptor of this.interceptors.request) {
      finalOptions = await interceptor(finalOptions) || finalOptions;
    }

    // Make request
    try {
      const response = await fetch(finalOptions.url || url, {
        method: finalOptions.method,
        headers: finalOptions.headers,
        body: finalOptions.body ? JSON.stringify(finalOptions.body) : undefined,
        credentials: 'same-origin',
        signal: finalOptions.signal,
      });

      // Apply response interceptors
      let responseData = response;
      for (const interceptor of this.interceptors.response) {
        responseData = await interceptor(responseData) || responseData;
      }

      // Handle non-ok responses
      if (!responseData.ok) {
        let errorData;
        try {
          errorData = await responseData.json();
        } catch {
          errorData = { message: responseData.statusText };
        }
        throw new ApiError(
          errorData.message || `HTTP ${responseData.status}`,
          responseData.status,
          errorData.error_key,
          errorData
        );
      }

      return responseData.json();
    } catch (error) {
      if (error instanceof ApiError) throw error;
      throw new ApiError(error.message || 'Network error', 0, 'network.error');
    }
  }

  // Convenience methods
  get(endpoint, options = {}) {
    return this.request('GET', endpoint, options);
  }

  post(endpoint, data, options = {}) {
    return this.request('POST', endpoint, { ...options, body: data });
  }

  put(endpoint, data, options = {}) {
    return this.request('PUT', endpoint, { ...options, body: data });
  }

  patch(endpoint, data, options = {}) {
    return this.request('PATCH', endpoint, { ...options, body: data });
  }

  delete(endpoint, options = {}) {
    return this.request('DELETE', endpoint, options);
  }
}

// Create singleton instance
export const api = new ApiClient();

// Add default response interceptor for error handling
api.addResponseInterceptor(async (response) => {
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new ApiError(
      errorData.message || `HTTP ${response.status}`,
      response.status,
      errorData.error_key,
      errorData
    );
  }
  return response;
});

// Add default request interceptor for auth
api.addRequestInterceptor(async (options) => {
  // Add timestamp to prevent caching for GET requests
  if (options.method === 'GET' && !options.params?.['_t']) {
    options.params = { ...options.params, _t: Date.now() };
  }
  return options;
});

// Helper functions for common patterns
export async function fetchWithPagination(endpoint, page = 1, perPage = 25, params = {}) {
  return api.get(endpoint, {
    params: { ...params, page, per_page: perPage, paged: 1 },
  });
}

export async function fetchAll(endpoint, params = {}) {
  return api.get(endpoint, { params: { ...params, paged: 0 } });
}

// Export for backward compatibility
export default api;