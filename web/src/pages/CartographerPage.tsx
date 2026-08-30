import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { postAnalyze } from "../api/analyze";
import { RepoIntelligence } from "../components/repo/RepoIntelligence";
import { SectionMarker } from "../components/SectionMarker";
import { ErrorState, LoadingState } from "../components/StateBlocks";
import { useAsyncAction } from "../hooks/useAsyncAction";
import "./CartographerPage.css";

export function CartographerPage() {
  const [url, setUrl] = useState("");
  const [showPath, setShowPath] = useState(false);
  const [path, setPath] = useState("");

  const [state, run] = useAsyncAction(postAnalyze);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (showPath) {
      if (!path.trim()) return;
      run({ path: path.trim() });
    } else {
      if (!url.trim()) return;
      run({ repo_url: url.trim() });
    }
  };

  const loading = state.status === "loading";

  return (
    <div className="cartographer-page">
      <SectionMarker index="II" label="Repository Intelligence" />
      <h1>Analyze a repository.</h1>
      <p className="cartographer-page__lede">
        Paste a GitHub URL. Dev-Strom maps services and architecture patterns at the
        distributed-systems level — not every class and function.
      </p>

      <form className="card cartographer-form" onSubmit={handleSubmit}>
        {!showPath ? (
          <div className="field cartographer-form__field">
            <label htmlFor="repo-url">Repository URL</label>
            <input
              id="repo-url"
              className="input cartographer-form__url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://github.com/user/repository"
              autoComplete="off"
              spellCheck={false}
              required
            />
          </div>
        ) : (
          <div className="field cartographer-form__field">
            <label htmlFor="repo-path">Local Path</label>
            <input
              id="repo-path"
              className="input cartographer-form__url"
              value={path}
              onChange={(e) => setPath(e.target.value)}
              placeholder="/path/to/repo"
              autoComplete="off"
              spellCheck={false}
              required
            />
          </div>
        )}

        <div className="cartographer-form__actions">
          <button type="submit" className="btn btn-primary" disabled={loading}>
            {loading ? "Analyzing…" : "Analyze Repository"}
          </button>
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={() => setShowPath((v) => !v)}
          >
            {showPath ? "Use a URL instead" : "Analyze a local path instead"}
          </button>
        </div>
      </form>

      {loading && <LoadingState label="Cloning, parsing, and reasoning about the codebase" />}
      {state.status === "error" && <ErrorState message={state.error} />}

      {state.status === "success" && state.data.status === "failed" && (
        <ErrorState message={state.data.summary || "Analysis failed."} />
      )}

      {state.status === "success" && state.data.status === "complete" && (
        <div className="cartographer-page__results">
          <hr className="hr" />
          <div className="cartographer-page__permalink">
            <Link to={`/analysis/${state.data.run_id}`} className="mono-label">
              Permalink to this analysis &rarr;
            </Link>
          </div>
          <RepoIntelligence analysis={state.data} />
        </div>
      )}
    </div>
  );
}
