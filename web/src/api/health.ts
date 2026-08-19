import { apiClient } from "./client";
import type { HealthResponse } from "./types";

export const getHealth = () => apiClient.get<HealthResponse>("/health");
export const getReady = () => apiClient.get<HealthResponse>("/ready");
