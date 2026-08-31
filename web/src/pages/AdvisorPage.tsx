import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { getAnalyses, getAnalysis, postAnalyze } from "../api/analyze";
import { RepoIntelligence } from "../components/repo/RepoIntelligence";
import { SectionMarker } from "../components/SectionMarker";
import { EmptyState, ErrorState, LoadingState } from "../components/StateBlocks";
import { useAsyncData } from "../hooks/useAsyncData";
import type { Analysis } from "../api/types";
import "./RepoIntelligencePage.css";

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
  const [url, setUrl] = useState("");
  const [path, setPath] = useState("");
  const [runId, setRunId] = useState("");
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const pastAnalyses = useAsyncData(() => getAnalyses(50, 0), []);
  const analysisRows = pastAnalyses.status === "success" ? pastAnalyses.data.analyses : [];

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setAnalysis(null);
    setLoading(true);
    try {
      if (mode === "run_id") {
        if (!runId.trim()) return;
        setAnalysis(await getAnalysis(runId.trim()));
      } else if (mode === "path") {
        if (!path.trim()) return;
        setAnalysis(await postAnalyze({ path: path.trim() }));
      } else {
        if (!url.trim()) return;
        setAnalysis(await postAnalyze({ repo_url: url.trim() }));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analysis failed.");
    } finally {
      setLoading(false);
    }
  };

  const submitDisabled =
    loading ||
    (mode === "run_id" && !runId) ||
    (mode === "repo_url" && !url.trim()) ||
    (mode === "path" && !path.trim());

  return (
    <div className="repo-intel-page">
      <SectionMarker index="II" label="Repository Intelligence" />
      <h1>Analyze a repository.</h1>
      <p className="repo-intel-page__lede">
        Paste a GitHub URL or local path. Get the system-level map — services,
        dependencies, and evidence-backed findings with a live architecture graph.
      </p>

      <form className="card repo-intel-form" onSubmit={handleSubmit}>
        <div className="repo-intel-form__mode">
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

        <div className="field repo-intel-form__field">
          <label htmlFor="analyze-target">{MODE_LABEL[mode]}</label>
          {mode === "run_id" ? (
            pastAnalyses.status === "loading" ? (
              <LoadingState label="Loading past analyses" />
            ) : pastAnalyses.status === "error" ? (
              <ErrorState message={pastAnalyses.error} onRetry={pastAnalyses.reload} />
            ) : analysisRows.length === 0 ? (
              <EmptyState message="No past analyses yet — analyze a repository first." />
            ) : (
              <select
                id="analyze-target"
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
              id="analyze-target"
              className="input repo-intel-form__input"
              value={mode === "repo_url" ? url : path}
              onChange={(e) => (mode === "repo_url" ? setUrl(e.target.value) : setPath(e.target.value))}
              placeholder={mode === "path" ? "/path/to/repo" : "https://github.com/user/repository"}
              autoComplete="off"
              spellCheck={false}
              required
            />
          )}
        </div>

        <div className="repo-intel-form__actions">
          <button type="submit" className="btn btn-primary" disabled={submitDisabled}>
            {loading ? "Analyzing…" : "Analyze Repository"}
          </button>
        </div>
      </form>

      {loading && <LoadingState label="Cloning, parsing, and reasoning about the codebase" />}
      {error && <ErrorState message={error} />}

      {analysis?.status === "failed" && (
        <ErrorState message={analysis.summary || "Analysis failed."} />
      )}

      {analysis?.status === "complete" && (
        <div className="repo-intel-page__results">
          <hr className="hr" />
          <div className="repo-intel-page__permalink">
            <Link to={`/analysis/${analysis.run_id}`} className="mono-label">
              Permalink to this analysis &rarr;
            </Link>
          </div>
          <RepoIntelligence analysis={analysis} />
        </div>
      )}
    </div>
  );
}
