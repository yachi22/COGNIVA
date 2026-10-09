import axios, { InternalAxiosRequestConfig } from "axios";

// Base URL: In production, read VITE_API_BASE_URL; in local development with Vite proxy, fallback to '/api/v1'
const rawBaseUrl = import.meta.env.VITE_API_BASE_URL || "/api/v1";
const API_BASE_URL = rawBaseUrl.replace(/\/+$/, "");

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
  timeout: 30000,
});

// Request interceptor: automatically inject Bearer token from localStorage
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem("cogniva_token");
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor: handle 401 Unauthorized cleanly
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      // Clear token if expired or unauthorized
      const hadToken = localStorage.getItem("cogniva_token");
      if (hadToken && !error.config.url?.includes("/auth/login")) {
        localStorage.removeItem("cogniva_token");
        // Dispatch custom event for AuthContext to react without page reload
        window.dispatchEvent(new Event("cogniva:unauthorized"));
      }
    }
    return Promise.reject(error);
  }
);

export interface HealthResponse {
  status: string;
  app?: string;
  version?: string;
  environment?: string;
}

export const checkHealth = async (): Promise<HealthResponse> => {
  const response = await apiClient.get<HealthResponse>("/health");
  return response.data;
};

export default apiClient;
