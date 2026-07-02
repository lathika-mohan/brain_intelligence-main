import {
  InternalAxiosRequestConfig,
  AxiosResponse,
  AxiosError,
  AxiosInstance,
} from "axios";
import { storage } from "@/utils/storage";
import { AUTH_TOKEN_KEY } from "@/utils/constants";

/**
 * Section 7 — Decoupled Network Layer
 *
 * These three named interceptors match the enterprise spec 1:1
 * (`requestInterceptor` / `responseInterceptor` / `errorInterceptor`) so any
 * external tooling or docs that reference them by name keep working.
 *
 * They are wired into the existing IOB `axiosInstance` (see `./axios.ts`)
 * instead of a throwaway instance, and reuse the repo's SSR-safe
 * `storage` utility + shared `AUTH_TOKEN_KEY` constant rather than calling
 * `window.localStorage` directly, keeping a single source of truth for the
 * token key across the app.
 */
export function requestInterceptor(
  config: InternalAxiosRequestConfig
): InternalAxiosRequestConfig {
  const token = storage.get(AUTH_TOKEN_KEY);
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
}

export function responseInterceptor(response: AxiosResponse): AxiosResponse {
  return response;
}

export function errorInterceptor(error: AxiosError): Promise<never> {
  if (error.response) {
    // Retain the enterprise-grade diagnostic logging from the existing
    // IOB interceptor while normalizing the rejection into a real Error
    // carrying the backend-provided message (spec behavior).
    if (error.response.status === 401) {
      console.warn("[API] Unauthorized session. Token expired or invalid.");
    } else if (error.response.status >= 500) {
      console.error("[API] Enterprise Server Error:", error.message);
    }

    const data = error.response.data as { message?: string } | undefined;
    return Promise.reject(
      new Error(data?.message || "Industrial backend connection timeout or failure.")
    );
  }

  return Promise.reject(error);
}

/**
 * Legacy adapter kept for backwards compatibility with any code still
 * importing `setupInterceptors(axiosInstance)` from earlier in the project
 * history. Internally it now just attaches the three named interceptors
 * above, so behavior is identical either way you wire it up.
 */
export const setupInterceptors = (axiosInstance: AxiosInstance): void => {
  axiosInstance.interceptors.request.use(requestInterceptor, (error: AxiosError) =>
    Promise.reject(error)
  );
  axiosInstance.interceptors.response.use(responseInterceptor, errorInterceptor);
};
