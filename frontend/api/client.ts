import axios from "axios";

const BACKEND_URL =
  process.env.EXPO_PUBLIC_BACKEND_URL || "http://localhost:5000";
const API_KEY = process.env.EXPO_PUBLIC_API_KEY || "";

const apiClient = axios.create({
  baseURL: BACKEND_URL,
  headers: {
    "Content-Type": "application/json",
    ...(API_KEY ? { "X-API-Key": API_KEY } : {}),
  },
});

export interface StatusResponse {
  status: string;
}

export async function getStatus(): Promise<StatusResponse> {
  const res = await apiClient.get("/api/status");
  return res.data;
}

export default apiClient;
