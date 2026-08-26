import { apiClient } from "./client";
import { demoDelay } from "./demo";
import { sampleAnalysis } from "../fixtures/analysis";
import { isDemoMode } from "../lib/demoMode";
import type { Analysis, AnalyzeRequest } from "./types";

/**
 * POST /analyze — deterministic ingestion + evidence-first analysis of a repo.
 * Returns the unified Analysis domain object that powers the Repository
 * Intelligence view. Async variant (?async=true -> job polling) is deferred to
 * the caller; this is the synchronous path.
 */
export async function postAnalyze(body: AnalyzeRequest): Promise<Analysis> {
  if (isDemoMode()) {
    return demoDelay(
      {
        ...sampleAnalysis,
        repository: {
          ...sampleAnalysis.repository,
          url: body.repo_url ?? sampleAnalysis.repository.url,
          root_path: body.path ?? sampleAnalysis.repository.root_path,
        },
      },
      800,
    );
  }
  return apiClient.post<Analysis>("/analyze", body);
}

/** GET /analyze/{id} — reload a previously computed Analysis (e.g. from History). */
export async function getAnalysis(id: string): Promise<Analysis> {
  if (isDemoMode()) {
    return demoDelay({ ...sampleAnalysis, id });
  }
  return apiClient.get<Analysis>(`/analyze/${encodeURIComponent(id)}`);
}
