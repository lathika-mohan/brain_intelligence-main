import { AxiosRequestConfig } from "axios";
import { axiosInstance } from "./axios";

/**
 * Interceptors are now attached once, centrally, inside `./axios.ts`
 * (Section 7 wiring). We intentionally do NOT call `setupInterceptors()`
 * here anymore — doing so from both modules would double-register the
 * request/response interceptors on the shared instance.
 */

/**
 * Thin, typed wrapper around the shared axios instance.
 *
 * Kept generic (`T = any`) and returning the raw `response.data` — matching
 * the calling convention already used across `src/services/*.service.ts` —
 * rather than forcing every caller to unwrap an `ApiResponse<T>` envelope.
 * When the backend *does* respond with the `{ success, data, message,
 * timestamp }` envelope from `@/types`, callers can simply type the call as
 * `apiClient.get<ApiResponse<Asset[]>>(...)`.
 */
export const apiClient = {
  get: async <T = unknown>(url: string, config?: AxiosRequestConfig): Promise<T> => {
    const response = await axiosInstance.get<T>(url, config);
    return response.data;
  },
  post: async <T = unknown>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> => {
    const response = await axiosInstance.post<T>(url, data, config);
    return response.data;
  },
  put: async <T = unknown>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> => {
    const response = await axiosInstance.put<T>(url, data, config);
    return response.data;
  },
  patch: async <T = unknown>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> => {
    const response = await axiosInstance.patch<T>(url, data, config);
    return response.data;
  },
  delete: async <T = unknown>(url: string, config?: AxiosRequestConfig): Promise<T> => {
    const response = await axiosInstance.delete<T>(url, config);
    return response.data;
  },
};
