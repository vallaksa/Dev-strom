import { useNavigate } from "react-router-dom";
import { getAnalyses } from "../api/analyze";
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

function repoLabel(url: string | null): string {
  if (!url) return "local path";
  const clean = url.replace(/\.git$/, "").replace(/\/$/, "");
  const parts = clean.split("/").filter(Boolean);
  return parts.slice(-2).join("/") || clean;
}

export function HistoryPage() {
  const ideas = useAsyncData(() => getHistory(20, 0), []);
  const analyses = useAsyncData(() => getAnalyses(20, 0), []);
  const navigate = useNavigate();

  // Analyses are an optional backend feature — if the endpoint isn't available
  // yet, silently omit the section rather than surfacing an error.
  const analysisRows = analyses.status === "success" ? analyses.data.analyses : [];

  return (
    <div className="history-page">
      <SectionMarker index="IV" label="Run History" />
      <h1>Past runs.</h1>
      <p className="history-page__lede">
        Every idea-generation and repository-analysis run, most recent first.
      </p>

      {analysisRows.length > 0 && (
        <section className="history-section">
          <h2 className="history-section__title">Repository Analyses</h2>
          <div className="card history-table-wrap">
            <table className="history-table">
              <thead>
                <tr>
                  <th>Run</th>
                  <th>Repository</th>
                  <th>Language</th>
                  <th>Status</th>
                  <th>Findings</th>
                  <th>Recs</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {analysisRows.map((a) => (
                  <tr key={a.run_id} onClick={() => navigate(`/analysis/${a.run_id}`)}>
                    <td className="mono-cell">{a.run_id}</td>
                    <td>{repoLabel(a.repo_url)}</td>
                    <td>{a.language || "—"}</td>
                    <td>
                      <span className={`badge ${a.status === "failed" ? "badge-high" : "badge-accent"}`}>
                        {a.status}
                      </span>
                    </td>
                    <td>{a.finding_count}</td>
                    <td>{a.recommendation_count}</td>
                    <td>{formatDate(a.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <section className="history-section">
        <h2 className="history-section__title">Idea Runs</h2>

        {ideas.status === "loading" && <LoadingState label="Loading history" />}
        {ideas.status === "error" && <ErrorState message={ideas.error} onRetry={ideas.reload} />}
        {ideas.status === "success" && ideas.data.runs.length === 0 && (
          <EmptyState message="No runs yet. Generate some ideas or analyze a repo to see them here." />
        )}

        {ideas.status === "success" && ideas.data.runs.length > 0 && (
          <div className="card history-table-wrap">
            <table className="history-table">
              <thead>
                <tr>
                  <th>Run</th>
                  <th>Intent</th>
                  <th>Count</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {ideas.data.runs.map((run) => (
                  <tr key={run.run_id} onClick={() => navigate(`/history/${run.run_id}`)}>
                    <td className="mono-cell">{run.run_id}</td>
                    <td className="history-table__intent">{run.tech_stack}</td>
                    <td>{run.count}</td>
                    <td>{formatDate(run.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
