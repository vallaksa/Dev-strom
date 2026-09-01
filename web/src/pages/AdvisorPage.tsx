import { useState } from "react";
import { Link } from "react-router-dom";
import { postAnalyze } from "../api/analyze";
import { AnalyzeForm } from "../components/repo/AnalyzeForm";
import { RepoIntelligence } from "../components/repo/RepoIntelligence";
import { SectionMarker } from "../components/SectionMarker";
import { ErrorState, LoadingState } from "../components/StateBlocks";
import { notifyRunsChanged } from "../lib/runsStore";
import type { Analysis, AnalyzeRequest } from "../api/types";
import "./RepoIntelligencePage.css";

export function AdvisorPage() {
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleAnalyze = async (request: AnalyzeRequest) => {
    setError(null);
    setAnalysis(null);
    setLoading(true);
    try {
      const result = await postAnalyze(request);
      setAnalysis(result);
      notifyRunsChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analysis failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="repo-intel-page">
      <SectionMarker label="Repository Intelligence" />
      <h1>Analyze a repository.</h1>
      <p className="repo-intel-page__lede">
        Paste a GitHub URL or local path. Get the system-level map — services,
        dependencies, and evidence-backed findings with a live architecture graph.
      </p>

      <AnalyzeForm busy={loading} onAnalyze={handleAnalyze} />

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
