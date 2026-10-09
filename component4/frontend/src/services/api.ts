import axios, { AxiosError, AxiosRequestConfig } from "axios";

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:5000/api/v1",
  timeout: 15000,
  headers: { "Content-Type": "application/json" },
});

export function apiMessage(error: unknown): string {
  if (error instanceof AxiosError) {
    if (!error.response) {
      return "The Flask API is unavailable. Start the backend and retry.";
    }
    return error.response.data?.error?.message || "The API request failed.";
  }
  return error instanceof Error ? error.message : "The request failed.";
}

export async function apiData<T>(config: AxiosRequestConfig): Promise<T> {
  const response = await api.request<{ data: T }>(config);
  return response.data.data;
}
