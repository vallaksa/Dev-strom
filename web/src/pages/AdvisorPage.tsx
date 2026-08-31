import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { postAnalyze } from "../api/analyze";
import { RepoIntelligence } from "../components/repo/RepoIntelligence";
import { SectionMarker } from "../components/SectionMarker";
import { ErrorState, LoadingState } from "../components/StateBlocks";
import { notifyRunsChanged } from "../lib/runsStore";
import type { Analysis } from "../api/types";
import "./RepoIntelligencePage.css";

type InputMode = "repo_url" | "path";

const MODE_LABEL: Record<InputMode, string> = {
  repo_url: "Repository URL",
  path: "Local Path",
};

export function AdvisorPage() {
  const [mode, setMode] = useState<InputMode>("repo_url");
  const [url, setUrl] = useState("");
  const [path, setPath] = useState("");
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setAnalysis(null);
    setLoading(true);
    try {
      const result =
        mode === "path"
          ? path.trim() && (await postAnalyze({ path: path.trim() }))
          : url.trim() && (await postAnalyze({ repo_url: url.trim() }));
      if (result) {
        setAnalysis(result);
        notifyRunsChanged();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analysis failed.");
    } finally {
      setLoading(false);
    }
  };

  const submitDisabled =
    loading ||
    (mode === "repo_url" && !url.trim()) ||
    (mode === "path" && !path.trim());

  return (
    <div className="repo-intel-page">
      <SectionMarker label="Repository Intelligence" />
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
