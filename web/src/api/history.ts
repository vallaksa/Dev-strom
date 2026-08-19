import { apiClient } from "./client";
import { demoDelay } from "./demo";
import { sampleHistoryResponse, sampleIdeasResponse } from "../fixtures/ideas";
import { isDemoMode } from "../lib/demoMode";
import type { HistoryResponse, RunDetail } from "./types";

export async function getHistory(limit = 20, offset = 0): Promise<HistoryResponse> {
  if (isDemoMode()) {
    return demoDelay({ ...sampleHistoryResponse, limit, offset });
  }
  return apiClient.get<HistoryResponse>("/history", { limit, offset });
}

export async function getRun(runId: string): Promise<RunDetail> {
  if (isDemoMode()) {
    const run = sampleHistoryResponse.runs.find((r) => r.run_id === runId) ?? sampleHistoryResponse.runs[0];
    return demoDelay({
      ...run,
      ideas: sampleIdeasResponse.ideas,
    });
  }
  return apiClient.get<RunDetail>(`/runs/${encodeURIComponent(runId)}`);
}
