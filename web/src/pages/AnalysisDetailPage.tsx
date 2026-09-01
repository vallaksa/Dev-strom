import { useNavigate, useParams } from "react-router-dom";
import { getAnalysis } from "../api/analyze";
import { RepoIntelligence } from "../components/repo/RepoIntelligence";
import { SectionMarker } from "../components/SectionMarker";
import { ErrorState, LoadingState } from "../components/StateBlocks";
import { useAsyncData } from "../hooks/useAsyncData";
import "./RunDetailPage.css"; // shared .run-detail-page__back link style

export function AnalysisDetailPage() {
  const { runId = "" } = useParams();
  const navigate = useNavigate();
  const state = useAsyncData(() => getAnalysis(runId), [runId]);

  return (
    <div className="analysis-detail-page">
      <button
        type="button"
        onClick={() => navigate(-1)}
        className="run-detail-page__back mono-label"
      >
        &larr; Back
      </button>
      <SectionMarker label="Repository Intelligence" />

      {state.status === "loading" && <LoadingState label="Loading analysis" />}
      {state.status === "error" && <ErrorState message={state.error} onRetry={state.reload} />}

      {state.status === "success" && state.data.status === "failed" && (
        <ErrorState message={state.data.summary || "This analysis did not complete."} />
      )}

      {state.status === "success" && state.data.status === "complete" && (
        <RepoIntelligence analysis={state.data} />
      )}
    </div>
  );
}
