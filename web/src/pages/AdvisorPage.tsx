import { useState, type FormEvent } from "react";
import { getAnalyses } from "../api/analyze";
import { postAdvise } from "../api/advise";
import { AdvisorReportView } from "../components/AdvisorReportView";
import { SectionMarker } from "../components/SectionMarker";
import { EmptyState, ErrorState, LoadingState } from "../components/StateBlocks";
import { useAsyncAction } from "../hooks/useAsyncAction";
import { useAsyncData } from "../hooks/useAsyncData";
import type { AdviseRequest } from "../api/types";
import "./AdvisorPage.css";

type InputMode = "repo_url" | "path" | "run_id";

const MODE_LABEL: Record<InputMode, string> = {
  repo_url: "Repository URL",
  path: "Local Path",
  run_id: "Past analysis",
};

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

export function AdvisorPage() {
  const [mode, setMode] = useState<InputMode>("repo_url");
  const [url, setUrl] = useState("https://github.com/example-org/dev-strom");
  const [path, setPath] = useState("");
  const [runId, setRunId] = useState("");

  const pastAnalyses = useAsyncData(() => getAnalyses(50, 0), []);
  const [state, run] = useAsyncAction(postAdvise);

  const analysisRows = pastAnalyses.status === "success" ? pastAnalyses.data.analyses : [];

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    const body: AdviseRequest | null =
      mode === "repo_url"
        ? url.trim()
          ? { repo_url: url.trim() }
          : null
        : mode === "path"
          ? path.trim()
            ? { path: path.trim() }
            : null
          : runId.trim()
            ? { run_id: runId.trim() }
            : null;
    if (!body) return;
    run(body);
  };

  const submitDisabled =
    state.status === "loading" || (mode === "run_id" && !runId);

  return (
    <div className="advisor-page">
      <SectionMarker index="III" label="Advisor" />
      <h1>Get an architectural second opinion.</h1>
      <p className="advisor-page__lede">
        Point Dev-Strom at a repo (or reuse a prior analysis) and it will recommend
        concrete next moves, ranked by impact and effort.
      </p>

      <form className="card advisor-form" onSubmit={handleSubmit}>
        <div className="advisor-form__mode">
          {(Object.keys(MODE_LABEL) as InputMode[]).map((m) => (
            <button
              key={m}
              type="button"
              className={"btn btn-sm " + (mode === m ? "btn-primary" : "btn-secondary")}
              onClick={() => setMode(m)}
            >
              {MODE_LABEL[m]}
            </button>
          ))}
        </div>
        <div className="field advisor-form__input">
          <label htmlFor="advise-target">{MODE_LABEL[mode]}</label>
          {mode === "run_id" ? (
            pastAnalyses.status === "loading" ? (
              <LoadingState label="Loading past analyses" />
            ) : pastAnalyses.status === "error" ? (
              <ErrorState message={pastAnalyses.error} onRetry={pastAnalyses.reload} />
            ) : analysisRows.length === 0 ? (
              <EmptyState message="No past analyses yet — analyze a repository first." />
            ) : (
              <select
                id="advise-target"
                className="input"
                value={runId}
                onChange={(e) => setRunId(e.target.value)}
                required
              >
                <option value="">Select a past analysis</option>
                {analysisRows.map((a) => (
                  <option key={a.run_id} value={a.run_id}>
                    {a.run_id} · {formatDate(a.created_at)}
                  </option>
                ))}
              </select>
            )
          ) : (
            <input
              id="advise-target"
              className="input"
              value={mode === "repo_url" ? url : path}
              onChange={(e) => (mode === "repo_url" ? setUrl(e.target.value) : setPath(e.target.value))}
              placeholder={mode === "path" ? "/path/to/repo" : "https://github.com/org/repo"}
              required
            />
          )}
        </div>
        <button type="submit" className="btn btn-primary" disabled={submitDisabled}>
          {state.status === "loading" ? "Advising…" : "Get Recommendations"}
        </button>
      </form>

      {state.status === "loading" && <LoadingState label="Analyzing and drafting recommendations" />}
      {state.status === "error" && <ErrorState message={state.error} />}
      {state.status === "success" && (
        <>
          <div className="advisor-page__run-meta mono-label">{state.data.run_id}</div>
          <AdvisorReportView report={state.data.advisor_report} />
        </>
      )}
    </div>
  );
}
