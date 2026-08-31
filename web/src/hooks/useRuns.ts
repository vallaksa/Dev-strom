import { useSyncExternalStore } from "react";
import { getAnalyses } from "../api/analyze";
import { getHistory } from "../api/history";
import { getRunsRevision, subscribeRuns } from "../lib/runsStore";
import type { AnalysisSummary, HistoryRun } from "../api/types";
import { useAsyncData } from "./useAsyncData";

export interface RunsData {
  ideas: HistoryRun[];
  analyses: AnalysisSummary[];
}

/**
 * The sidebar's data source: idea runs (`GET /history`) and repo analyses
 * (`GET /analyses`), fetched together and refreshed whenever
 * `notifyRunsChanged()` fires. `/analyses` is an optional backend feature —
 * if it errors we still return the idea runs rather than failing the panel.
 */
export function useRuns() {
  const revision = useSyncExternalStore(subscribeRuns, getRunsRevision, getRunsRevision);

  return useAsyncData<RunsData>(async () => {
    const [history, analyses] = await Promise.all([
      getHistory(50, 0),
      getAnalyses(50, 0).catch(() => ({ analyses: [], limit: 50, offset: 0 })),
    ]);
    return { ideas: history.runs, analyses: analyses.analyses };
  }, [revision]);
}
