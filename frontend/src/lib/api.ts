import axios, {
  type AxiosError,
  type AxiosRequestConfig,
  type InternalAxiosRequestConfig,
} from "axios";

import { API_URL } from "../config";
import { useAuthStore } from "../store/auth";
import type { LoginRequest, RegisterRequest, Token, User } from "../types/auth";

/** Endpoint map — paths live here only, not in pages. */
export const endpoints = {
  register: `${API_URL}/auth/register`,
  login: `${API_URL}/auth/login`,
  refresh: `${API_URL}/auth/refresh`,
  logout: `${API_URL}/auth/logout`,
  confirmEnrollment: `${API_URL}/devices/confirm`,
} as const;

// withCredentials lets the browser send/receive the HttpOnly refresh cookie.
const api = axios.create({ baseURL: API_URL, withCredentials: true });

// Attach the access token to every request.
api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().accessToken;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Single-flight refresh so concurrent 401s trigger one refresh call.
let refreshPromise: Promise<string> | null = null;

async function refreshAccessToken(): Promise<string> {
  // The refresh token is an HttpOnly cookie, so there is no request body —
  // we only need the browser to include the cookie (withCredentials).
  const { data } = await axios.post<Token>(endpoints.refresh, null, {
    withCredentials: true,
  });
  useAuthStore.getState().setTokens(data);
  return data.access_token;
}

interface RetriableConfig extends InternalAxiosRequestConfig {
  _retry?: boolean;
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const config = error.config as RetriableConfig | undefined;
    const isAuthCall = Boolean(
      config?.url?.includes("/auth/login") ||
        config?.url?.includes("/auth/refresh"),
    );

    if (error.response?.status === 401 && config && !config._retry && !isAuthCall) {
      config._retry = true;
      try {
        refreshPromise = refreshPromise ?? refreshAccessToken();
        const token = await refreshPromise;
        config.headers.Authorization = `Bearer ${token}`;
        return api(config);
      } catch (refreshError) {
        useAuthStore.getState().clear();
        window.location.assign("/login");
        return Promise.reject(refreshError);
      } finally {
        refreshPromise = null;
      }
    }
    return Promise.reject(error);
  },
);

export const authApi = {
  register: (body: RegisterRequest): Promise<User> =>
    api.post<User>(endpoints.register, body).then((r) => r.data),
  login: (body: LoginRequest): Promise<Token> =>
    api.post<Token>(endpoints.login, body).then((r) => r.data),
  logout: (): Promise<void> =>
    api.post(endpoints.logout).then(() => undefined),
};

export interface ConfirmEnrollmentResponse {
  status: string;
  detail: string;
  installation_id?: string;
}

export const deviceApi = {
  confirmEnrollment: (token: string): Promise<ConfirmEnrollmentResponse> =>
    api
      .post<ConfirmEnrollmentResponse>(endpoints.confirmEnrollment, { token })
      .then((r) => r.data),
};

export default api;

export type { AxiosRequestConfig };
