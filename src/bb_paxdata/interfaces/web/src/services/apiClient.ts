const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// Dispatched globally whenever ANY API call returns 401 Unauthorized.
// The auth layer listens for this to trigger logout/redirect.
export const UNAUTHORIZED_EVENT = 'paxdata:unauthorized';

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

class ApiClient {
  private async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const url = `${API_BASE}${path}`;

    // Auto-inject JWT auth token from localStorage if present
    const token = localStorage.getItem('paxdata_token');
    const headers = new Headers(options.headers || {});

    if (token && !headers.has('Authorization')) {
      headers.set('Authorization', `Bearer ${token}`);
    }

    if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
      headers.set('Content-Type', 'application/json');
    }

    const response = await fetch(url, {
      ...options,
      headers,
    });

    if (!response.ok) {
      // Global 401 handler — dispatch event so auth layer can logout/redirect.
      if (response.status === 401) {
        window.dispatchEvent(new CustomEvent(UNAUTHORIZED_EVENT, { detail: { path } }));
      }

      const errorText = await response.text();
      let errorMessage = 'Sistemsel bir hata oluştu';
      try {
        const errorJson = JSON.parse(errorText);
        errorMessage = errorJson.detail || errorJson.message || errorMessage;
      } catch {
        errorMessage = errorText || errorMessage;
      }
      throw new ApiError(errorMessage, response.status);
    }

    if (response.status === 204) {
      return {} as T;
    }

    return response.json();
  }

  get<T>(path: string, options?: RequestInit): Promise<T> {
    return this.request<T>(path, { ...options, method: 'GET' });
  }

  post<T>(path: string, body: unknown, options?: RequestInit): Promise<T> {
    return this.request<T>(path, {
      ...options,
      method: 'POST',
      body: JSON.stringify(body),
    });
  }

  put<T>(path: string, body: unknown, options?: RequestInit): Promise<T> {
    return this.request<T>(path, {
      ...options,
      method: 'PUT',
      body: JSON.stringify(body),
    });
  }

  delete<T>(path: string, options?: RequestInit): Promise<T> {
    return this.request<T>(path, { ...options, method: 'DELETE' });
  }
}

export const apiClient = new ApiClient();
