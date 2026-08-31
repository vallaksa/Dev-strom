import { Link, useParams } from "react-router-dom";
import { getRun } from "../api/history";
import { IdeaCard } from "../components/IdeaCard";
import { SectionMarker } from "../components/SectionMarker";
import { ErrorState, LoadingState } from "../components/StateBlocks";
import { useAsyncData } from "../hooks/useAsyncData";
import "./RunDetailPage.css";

export function RunDetailPage() {
  const { runId = "" } = useParams();
  const state = useAsyncData(() => getRun(runId), [runId]);

  return (
    <div className="run-detail-page">
      <Link to="/history" className="run-detail-page__back mono-label">
        &larr; Back to History
      </Link>
      <SectionMarker label="Run Detail" />
      <h1 className="run-detail-page__title">
        {state.status === "success" ? state.data.tech_stack : runId}
      </h1>

      {state.status === "loading" && <LoadingState label="Loading run" />}
      {state.status === "error" && <ErrorState message={state.error} onRetry={state.reload} />}

      {state.status === "success" && (
        <>
          <div className="card run-detail-page__meta">
            <div>
              <span className="mono-label">Intent</span>
              <p>{state.data.tech_stack}</p>
            </div>
            <div>
              <span className="mono-label">Created</span>
              <p>{new Date(state.data.created_at).toLocaleString()}</p>
            </div>
          </div>

          {Array.isArray(state.data.ideas) && state.data.ideas.length > 0 && (
            <div className="ideas-grid">
              {state.data.ideas.map((idea) => (
                <IdeaCard key={idea.pid} idea={idea} runId={runId} />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
