import type { AdvisorReport, Recommendation, RecommendationCategory } from "../api/types";
import "./AdvisorReportView.css";

const CATEGORY_LABEL: Record<RecommendationCategory, string> = {
  feature: "Feature",
  refactor: "Refactor",
  tech_debt: "Tech Debt",
  risk: "Risk",
  test: "Test",
  security: "Security",
  performance: "Performance",
  docs: "Docs",
};

function groupByCategory(recs: Recommendation[]): [RecommendationCategory, Recommendation[]][] {
  const map = new Map<RecommendationCategory, Recommendation[]>();
  for (const rec of recs) {
    const list = map.get(rec.category) ?? [];
    list.push(rec);
    map.set(rec.category, list);
  }
  return Array.from(map.entries());
}

function RecommendationCard({ rec }: { rec: Recommendation }) {
  return (
    <div className="rec-card">
      <div className="rec-card__head">
        <h4>{rec.title}</h4>
        <div className="rec-card__badges">
          <span className={`badge badge-${rec.impact}`}>Impact: {rec.impact}</span>
          <span className={`badge badge-${rec.effort}`}>Effort: {rec.effort}</span>
        </div>
      </div>
      <p className="rec-card__rationale">{rec.rationale}</p>
      {rec.suggested_steps.length > 0 && (
        <>
          <span className="mono-label">Suggested Steps</span>
          <ol>
            {rec.suggested_steps.map((step, i) => (
              <li key={i}>{step}</li>
            ))}
          </ol>
        </>
      )}
      {rec.affected_node_ids.length > 0 && (
        <div className="rec-card__affected">
          <span className="mono-label">Affected</span>
          <div className="rec-card__chips">
            {rec.affected_node_ids.map((id) => (
              <span key={id} className="badge badge-outline">
                {id}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export function AdvisorReportView({ report }: { report: AdvisorReport }) {
  const grouped = groupByCategory(report.recommendations);

  return (
    <div className="advisor-report">
      <div className="card">
        <p>{report.summary}</p>
        {report.tech_stack.length > 0 && (
          <div className="advisor-report__chips">
            {report.tech_stack.map((t, i) => (
              <span key={i} className="badge">
                {t}
              </span>
            ))}
          </div>
        )}
      </div>

      <div className="advisor-report__columns">
        <div className="card">
          <span className="mono-label accent">Quick Wins</span>
          <ul>
            {report.quick_wins.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </div>
        <div className="card">
          <span className="mono-label accent">Strategic Bets</span>
          <ul>
            {report.strategic_bets.map((b, i) => (
              <li key={i}>{b}</li>
            ))}
          </ul>
        </div>
      </div>

      <div className="advisor-report__recs">
        <span className="mono-label accent">Recommendations</span>
        {grouped.map(([category, recs]) => (
          <div key={category} className="advisor-report__group">
            <h3 className="advisor-report__group-title">
              {CATEGORY_LABEL[category]} <span className="mono-label">({recs.length})</span>
            </h3>
            <div className="advisor-report__group-recs">
              {recs.map((rec) => (
                <RecommendationCard key={rec.id} rec={rec} />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
