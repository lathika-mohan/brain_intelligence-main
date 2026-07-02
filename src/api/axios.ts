import axios, { AxiosInstance } from "axios";
import { requestInterceptor, responseInterceptor, errorInterceptor } from "./interceptors";

const baseURL = process.env.NEXT_PUBLIC_API_URL || "/api/v1";

export const axiosInstance: AxiosInstance = axios.create({
  baseURL,
  // Bumped to 30s (spec) — industrial backend calls (telemetry batch
  // pulls, SHAP explainability, GraphRAG traversal) can legitimately run
  // longer than the previous 10s default.
  timeout: 30000,
  headers: {
    "Content-Type": "application/json",
    Accept: "application/json",
  },
});

// Wire the decoupled interceptors (Section 7) directly onto the shared
// instance so every consumer — apiClient and any raw axiosInstance usage —
// gets the auth header injection + normalized error handling for free.
axiosInstance.interceptors.request.use(requestInterceptor, (error) => Promise.reject(error));
axiosInstance.interceptors.response.use(responseInterceptor, errorInterceptor);

// Default export retained for drop-in compatibility with the spec, which
// imports this module as `import instance from './axios'`.
export default axiosInstance;
