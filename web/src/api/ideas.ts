import { apiClient } from "./client";
import { demoDelay } from "./demo";
import { sampleIdeas } from "../fixtures/ideas";
import { isDemoMode } from "../lib/demoMode";
import type { ExpandRequest, ExpandResponse, ExportRequest, Idea, IdeasRequest, IdeasResponse } from "./types";

export async function postIdeas(body: IdeasRequest): Promise<IdeasResponse> {
  if (isDemoMode()) {
    const count = Math.max(1, Math.min(5, body.count || sampleIdeas.length));
    return demoDelay({
      run_id: `demo-run-${Date.now()}`,
      ideas: sampleIdeas.slice(0, count).map((idea, i) => ({ ...idea, pid: i + 1 })),
    });
  }
  return apiClient.post<IdeasResponse>("/ideas", body);
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
