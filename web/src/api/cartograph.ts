import { apiClient } from "./client";
import { demoDelay } from "./demo";
import { sampleArchitectureReport } from "../fixtures/architectureReport";
import { sampleProjectGraph } from "../fixtures/projectGraph";
import { isDemoMode } from "../lib/demoMode";
import type { CartographRequest, CartographResponse } from "./types";

const DEMO_RUN_ID = "example-org-dev-strom";

export async function postCartograph(body: CartographRequest): Promise<CartographResponse> {
  if (isDemoMode()) {
    return demoDelay(
      {
        run_id: DEMO_RUN_ID,
        project_graph: { ...sampleProjectGraph, repo_url: body.repo_url ?? sampleProjectGraph.repo_url },
        architecture_report: sampleArchitectureReport,
      },
      700,
    );
  }
  return apiClient.post<CartographResponse>("/cartograph", body);
}

export async function getCartographRun(runId: string): Promise<CartographResponse> {
  if (isDemoMode()) {
    return demoDelay({
      run_id: runId,
      project_graph: sampleProjectGraph,
      architecture_report: sampleArchitectureReport,
    });
  }
  return apiClient.get<CartographResponse>(`/cartograph/${encodeURIComponent(runId)}`);
}
