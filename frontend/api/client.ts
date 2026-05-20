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

export interface MatchData {
  match_id: string;
  card_text: string;
  row_index: number;
  price: string | null;
  remaining_seconds: number;
  status: string;
}

export interface StatusResponse {
  status: string;
  has_pending_match: boolean;
  active_match: MatchData | null;
}

export async function getStatus(): Promise<StatusResponse> {
  const res = await apiClient.get("/api/status");
  return res.data;
}

export async function approveMatch(): Promise<{ status: string }> {
  const res = await apiClient.post("/api/approve");
  return res.data;
}

export async function denyMatch(): Promise<{ status: string }> {
  const res = await apiClient.post("/api/deny");
  return res.data;
}

export default apiClient;
