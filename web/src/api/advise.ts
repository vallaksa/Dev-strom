import { apiClient } from "./client";
import { demoDelay } from "./demo";
import { sampleAdvisorReport } from "../fixtures/advisorReport";
import { isDemoMode } from "../lib/demoMode";
import type { AdviseRequest, AdviseResponse } from "./types";

const DEMO_RUN_ID = "example-org-dev-strom-advice";

export async function postAdvise(body: AdviseRequest): Promise<AdviseResponse> {
  if (isDemoMode()) {
    return demoDelay({ run_id: DEMO_RUN_ID, advisor_report: sampleAdvisorReport }, 700);
  }
  return apiClient.post<AdviseResponse>("/advise", body);
}

export async function getAdviseRun(runId: string): Promise<AdviseResponse> {
  if (isDemoMode()) {
    return demoDelay({ run_id: runId, advisor_report: sampleAdvisorReport });
  }
  return apiClient.get<AdviseResponse>(`/advise/${encodeURIComponent(runId)}`);
}
