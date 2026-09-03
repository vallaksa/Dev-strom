import { ApiError, apiClient } from "./client";
import { subscribeJob } from "./jobs";
import { demoDelay } from "./demo";
import { sampleIdeas } from "../fixtures/ideas";
import { isDemoMode } from "../lib/demoMode";
import type {
  ExpandRequest,
  ExpandResponse,
  ExportRequest,
  Idea,
  IdeasRequest,
  IdeasResponse,
  JobAcceptedResponse,
} from "./types";

/**
 * Generate ideas via the async job pipeline: POST /ideas?async=true → 202
 * {job_id, status}, then stream GET /jobs/{job_id}/events (SSE) until the
 * terminal `done` event carries the {ideas, run_id} result. This avoids the
 * long-held sync request that upstream proxies (Cloudflare Tunnel) kill with
 * 524s.
 *
 * Falls back to the synchronous call in exactly one case: the scheduling POST
 * itself returned 503, the backend's signal that the job runner is
 * unavailable and no job was created. Every other failure is surfaced. That
 * asymmetry is deliberate — once the scheduling request has left, a job may
 * already be running and burning an LLM call, and a blanket fallback would
 * quietly run the whole pipeline (and pay for it) a second time.
 */
export async function postIdeas(body: IdeasRequest): Promise<IdeasResponse> {
  if (isDemoMode()) {
    const count = Math.max(1, Math.min(5, body.count || sampleIdeas.length));
    return demoDelay(
      {
        run_id: "python-fastapi-react",
        ideas: sampleIdeas.slice(0, count).map((idea, i) => ({ ...idea, pid: i + 1 })),
      },
      1800,
    );
  }
  let accepted: JobAcceptedResponse | undefined;
  try {
    accepted = await apiClient.post<JobAcceptedResponse>("/ideas", body, {
      query: { async: true },
    });
  } catch (err) {
    // 503 is the one unambiguous "no job was created" signal, so the sync
    // path is safe. A network error (ApiError status 0) is NOT: the request
    // may well have reached the server and started a job, and we must not
    // run the pipeline twice on a guess.
    if (err instanceof ApiError && err.status === 503) {
      return apiClient.post<IdeasResponse>("/ideas", body);
    }
    throw err;
  }
  if (!accepted?.job_id) {
    throw new ApiError(502, "Job was scheduled but no job id came back.");
  }
  // Deliberately outside the try: a stream failure is a real job/pipeline
  // error and must never re-enter the fallback.
  return subscribeJob<IdeasResponse>(accepted.job_id);
}

export async function postExpand(body: ExpandRequest): Promise<ExpandResponse> {
  if (isDemoMode()) {
    const idea: Idea = sampleIdeas.find((i) => i.pid === body.pid) ?? sampleIdeas[0];
    const extended_plan = [
      ...idea.implementation_plan,
      "Add integration tests around the happy path end-to-end.",
      "Write a short design doc covering failure modes and rollout plan.",
      "Ship a v0 behind a feature flag and gather feedback before broad rollout.",
    ];
    return demoDelay({ idea, extended_plan });
  }
  return apiClient.post<ExpandResponse>("/expand", body);
}

export async function postExport(body: ExportRequest): Promise<string> {
  if (isDemoMode()) {
    const idea = sampleIdeas.find((i) => i.pid === body.pid) ?? sampleIdeas[0];
    const md = [
      `# ${idea.name}`,
      "",
      "## Problem Statement",
      idea.problem_statement,
      "",
      "## Why It Fits",
      ...idea.why_it_fits.map((b) => `- ${b}`),
      "",
      "## Real World Value",
      idea.real_world_value,
      "",
      "## Implementation Plan",
      ...idea.implementation_plan.map((b, i) => `${i + 1}. ${b}`),
      "",
      "_Exported from Dev-Strom demo mode._",
    ].join("\n");
    return demoDelay(md, 250);
  }
  return apiClient.postText("/export", body);
}
