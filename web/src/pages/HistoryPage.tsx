import { useNavigate } from "react-router-dom";
import { getHistory } from "../api/history";
import { SectionMarker } from "../components/SectionMarker";
import { EmptyState, ErrorState, LoadingState } from "../components/StateBlocks";
import { useAsyncData } from "../hooks/useAsyncData";
import "./HistoryPage.css";

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

export function HistoryPage() {
  const state = useAsyncData(() => getHistory(20, 0), []);
  const navigate = useNavigate();

  return (
    <div className="history-page">
      <SectionMarker index="IV" label="Run History" />
      <h1>Past runs.</h1>
      <p className="history-page__lede">Every idea-generation, cartograph, and advisor run, most recent first.</p>

      {state.status === "loading" && <LoadingState label="Loading history" />}
      {state.status === "error" && <ErrorState message={state.error} onRetry={state.reload} />}
      {state.status === "success" && state.data.runs.length === 0 && (
        <EmptyState message="No runs yet. Generate some ideas or map a repo to see them here." />
      )}

      {state.status === "success" && state.data.runs.length > 0 && (
        <div className="card history-table-wrap">
          <table className="history-table">
            <thead>
              <tr>
                <th>Run ID</th>
                <th>Tech Stack</th>
                <th>Domain</th>
                <th>Level</th>
                <th>Count</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {state.data.runs.map((run) => (
                <tr key={run.run_id} onClick={() => navigate(`/history/${run.run_id}`)}>
                  <td className="mono-cell">{run.run_id.slice(0, 12)}&hellip;</td>
                  <td>{run.tech_stack}</td>
                  <td>{run.domain || "—"}</td>
                  <td>{run.level || "—"}</td>
                  <td>{run.count}</td>
                  <td>{formatDate(run.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
