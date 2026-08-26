import { useMemo, useState } from "react";
import type {
  Analysis,
  AnalysisFinding,
  AnalysisRecommendation,
  Dependency,
  Evidence,
  ImpactLevel,
  Severity,
} from "../../api/types";
import { CartographGraph } from "../graph/CartographGraph";
import { MermaidDiagram } from "../graph/MermaidDiagram";
import { EmptyState } from "../StateBlocks";
import "./RepoIntelligence.css";

type Tab = "overview" | "architecture" | "design" | "improvements";

const TABS: { id: Tab; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "architecture", label: "Architecture" },
  { id: "design", label: "Design" },
  { id: "improvements", label: "Improvements" },
];

const CATEGORY_LABEL: Record<string, string> = {
  architecture: "Architecture",
  design: "Design",
  scalability: "Scalability",
  reliability: "Reliability",
  security: "Security",
  performance: "Performance",
  maintainability: "Maintainability",
  testing: "Testing",
  product: "Product",
};

function repoName(a: Analysis): string {
  const url = a.repository.url;
  if (url) {
    const clean = url.replace(/\.git$/, "").replace(/\/$/, "");
    return clean.split("/").slice(-1)[0] || clean;
  }
  return a.repository.root_path.split("/").filter(Boolean).slice(-1)[0] || "repository";
}

export function RepoIntelligence({ analysis }: { analysis: Analysis }) {
  const [tab, setTab] = useState<Tab>("overview");

  return (
    <div className="repo-intel">
      <div className="repo-intel__header">
        <div>
          <span className="mono-label">Repository</span>
          <h2 className="repo-intel__title">{repoName(analysis)}</h2>
        </div>
        <div className="repo-intel__status">
          <span className="badge badge-accent">Analysis complete</span>
          <span className="mono-label repo-intel__runid">Run {analysis.run_id.slice(0, 12)}</span>
        </div>
      </div>

      <div className="repo-intel__tabs" role="tablist">
        {TABS.map((t) => (
          <button
            key={t.id}
            role="tab"
            aria-selected={tab === t.id}
            className={"repo-intel__tab" + (tab === t.id ? " is-active" : "")}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="repo-intel__panel">
        {tab === "overview" && <OverviewTab analysis={analysis} />}
        {tab === "architecture" && <ArchitectureTab analysis={analysis} />}
        {tab === "design" && <DesignTab findings={analysis.findings} />}
        {tab === "improvements" && (
          <ImprovementsTab recommendations={analysis.recommendations} findings={analysis.findings} />
        )}
      </div>
    </div>
  );
}

// ── Overview ────────────────────────────────────────────────────────────────

function OverviewTab({ analysis }: { analysis: Analysis }) {
  const { repository: repo } = analysis;
  return (
    <div className="repo-intel__overview">
      <div className="card">
        <span className="mono-label accent">What This System Does</span>
        <p className="repo-intel__summary">{analysis.summary}</p>
      </div>

      <div className="repo-intel__facts">
        <Fact label="Languages" value={repo.languages.join(", ") || repo.language || "—"} />
        <Fact label="Files" value={repo.file_count.toLocaleString()} />
        <Fact label="Lines of Code" value={repo.loc.toLocaleString()} />
        <Fact label="Dependencies" value={String(repo.dependencies.length)} />
      </div>

      <div className="repo-intel__overview-cols">
        <div className="card">
          <span className="mono-label accent">Findings</span>
          <p className="repo-intel__count">
            {analysis.findings.length} evidence-backed observation
            {analysis.findings.length === 1 ? "" : "s"}
          </p>
          <SeveritySummary findings={analysis.findings} />
        </div>
        <div className="card">
          <span className="mono-label accent">Entrypoints</span>
          {repo.entrypoints.length > 0 ? (
            <ul className="repo-intel__mono-list">
              {repo.entrypoints.map((e) => (
                <li key={e}>{e}</li>
              ))}
            </ul>
          ) : (
            <p className="repo-intel__muted">None detected.</p>
          )}
        </div>
      </div>

      {repo.commit_sha && (
        <div className="repo-intel__commit mono-label">
          commit {repo.commit_sha.slice(0, 12)}
        </div>
      )}
    </div>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="repo-intel__fact card">
      <span className="repo-intel__fact-value">{value}</span>
      <span className="mono-label">{label}</span>
    </div>
  );
}

function SeveritySummary({ findings }: { findings: AnalysisFinding[] }) {
  const counts = findings.reduce<Record<string, number>>((acc, f) => {
    acc[f.severity] = (acc[f.severity] ?? 0) + 1;
    return acc;
  }, {});
  const order: Severity[] = ["critical", "high", "medium", "low", "info"];
  const present = order.filter((s) => counts[s]);
  if (present.length === 0) return null;
  return (
    <div className="repo-intel__chips">
      {present.map((s) => (
        <span key={s} className={`badge repo-intel__sev repo-intel__sev--${s}`}>
          {s} · {counts[s]}
        </span>
      ))}
    </div>
  );
}

// ── Architecture ─────────────────────────────────────────────────────────────

function ArchitectureTab({ analysis }: { analysis: Analysis }) {
  const { repository: repo, graph, mermaid } = analysis;
  const byEcosystem = useMemo(() => {
    const map = new Map<string, Dependency[]>();
    for (const d of repo.dependencies) {
      const list = map.get(d.ecosystem) ?? [];
      list.push(d);
      map.set(d.ecosystem, list);
    }
    return Array.from(map.entries());
  }, [repo.dependencies]);

  return (
    <div className="repo-intel__architecture">
      {/* Curated component-level diagram (headline) with the interactive,
          file/module-level structural graph beneath it — different altitudes,
          both informative. Falls back gracefully when either is absent. */}
      {mermaid ? (
        <div className="card">
          <span className="mono-label accent">Architecture Diagram</span>
          <MermaidDiagram source={mermaid} />
        </div>
      ) : graph ? (
        <CartographGraph graph={graph} />
      ) : (
        <EmptyState message="No architecture diagram was produced for this run." />
      )}

      {mermaid && graph && (
        <div className="repo-intel__structural">
          <span className="mono-label accent">Structural Graph</span>
          <CartographGraph graph={graph} />
        </div>
      )}

      <div className="card">
        <span className="mono-label accent">Entrypoints</span>
        {repo.entrypoints.length > 0 ? (
          <ul className="repo-intel__mono-list">
            {repo.entrypoints.map((e) => (
              <li key={e}>{e}</li>
            ))}
          </ul>
        ) : (
          <p className="repo-intel__muted">None detected.</p>
        )}
      </div>

      <div className="card">
        <span className="mono-label accent">Dependencies</span>
        {byEcosystem.length === 0 && <p className="repo-intel__muted">No dependencies detected.</p>}
        {byEcosystem.map(([eco, deps]) => (
          <div key={eco} className="repo-intel__eco">
            <span className="mono-label">{eco}</span>
            <div className="repo-intel__deps">
              {deps.map((d) => (
                <span key={d.name} className="badge badge-outline" title={d.source}>
                  {d.name}
                  {d.version ? ` ${d.version}` : ""}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Design (evidence-first findings) ─────────────────────────────────────────

function DesignTab({ findings }: { findings: AnalysisFinding[] }) {
  if (findings.length === 0) {
    return <EmptyState message="No findings were produced for this run." />;
  }
  return (
    <div className="repo-intel__design">
      <span className="mono-label accent">Findings &amp; Design Decisions</span>
      <div className="repo-intel__findings">
        {findings.map((f) => (
          <FindingCard key={f.id} finding={f} />
        ))}
      </div>
    </div>
  );
}

function FindingCard({ finding }: { finding: AnalysisFinding }) {
  return (
    <div className="repo-intel__finding card">
      <div className="repo-intel__finding-head">
        <div className="repo-intel__finding-titles">
          <span className="badge badge-outline">{CATEGORY_LABEL[finding.category] ?? finding.category}</span>
          <h4>{finding.title}</h4>
        </div>
        <span className={`badge repo-intel__sev repo-intel__sev--${finding.severity}`}>{finding.severity}</span>
      </div>

      <p>{finding.description}</p>

      <ConfidenceMeter value={finding.confidence} />

      {finding.evidence.length > 0 && (
        <div className="repo-intel__evidence">
          <span className="mono-label">Evidence</span>
          {finding.evidence.map((ev, i) => (
            <EvidenceBlock key={i} evidence={ev} />
          ))}
        </div>
      )}
    </div>
  );
}

function ConfidenceMeter({ value }: { value: number }) {
  const pct = Math.max(0, Math.min(1, value)) * 100;
  const tone = value >= 0.75 ? "high" : value >= 0.5 ? "med" : "low";
  return (
    <div className="repo-intel__confidence" title={`Confidence ${(value * 100).toFixed(0)}%`}>
      <span className="mono-label">Confidence</span>
      <div className="repo-intel__meter">
        <div className={`repo-intel__meter-fill repo-intel__meter-fill--${tone}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="repo-intel__confidence-num">{(value * 100).toFixed(0)}%</span>
    </div>
  );
}

function evidenceLocation(ev: Evidence): string | null {
  if (!ev.file) return ev.symbol ?? null;
  let loc = ev.file;
  if (ev.line_start != null) {
    loc += `:${ev.line_start}`;
    if (ev.line_end != null && ev.line_end !== ev.line_start) loc += `-${ev.line_end}`;
  }
  if (ev.symbol) loc += ` · ${ev.symbol}`;
  return loc;
}

function EvidenceBlock({ evidence }: { evidence: Evidence }) {
  const loc = evidenceLocation(evidence);
  return (
    <div className="repo-intel__evidence-item">
      {loc && <code className="repo-intel__evidence-loc">{loc}</code>}
      {evidence.snippet && (
        <pre className="repo-intel__snippet panel-dark dark-scroll">
          <code>{evidence.snippet}</code>
        </pre>
      )}
      <p className="repo-intel__evidence-why">{evidence.explanation}</p>
    </div>
  );
}

// ── Improvements ─────────────────────────────────────────────────────────────

const IMPACT_ORDER: ImpactLevel[] = ["high", "medium", "low"];
const IMPACT_LABEL: Record<ImpactLevel, string> = {
  high: "High Impact",
  medium: "Medium Impact",
  low: "Low Impact",
};

function ImprovementsTab({
  recommendations,
  findings,
}: {
  recommendations: AnalysisRecommendation[];
  findings: AnalysisFinding[];
}) {
  const findingTitle = useMemo(() => {
    const m = new Map<string, string>();
    for (const f of findings) m.set(f.id, f.title);
    return m;
  }, [findings]);

  if (recommendations.length === 0) {
    return <EmptyState message="No recommendations were produced for this run." />;
  }

  const grouped = IMPACT_ORDER.map(
    (impact) =>
      [impact, recommendations.filter((r) => r.impact === impact).sort((a, b) => a.priority - b.priority)] as [
        ImpactLevel,
        AnalysisRecommendation[],
      ],
  ).filter(([, list]) => list.length > 0);

  return (
    <div className="repo-intel__improvements">
      {grouped.map(([impact, recs]) => (
        <section key={impact} className="repo-intel__impact-group">
          <div className="repo-intel__impact-head">
            <span className={`badge badge-${impact}`}>{IMPACT_LABEL[impact]}</span>
            <span className="mono-label">
              {recs.length} recommendation{recs.length === 1 ? "" : "s"}
            </span>
          </div>
          <ol className="repo-intel__rec-list">
            {recs.map((rec) => (
              <RecItem
                key={rec.id}
                rec={rec}
                motivatedBy={rec.finding_id ? findingTitle.get(rec.finding_id) : undefined}
              />
            ))}
          </ol>
        </section>
      ))}
    </div>
  );
}

function RecItem({ rec, motivatedBy }: { rec: AnalysisRecommendation; motivatedBy?: string }) {
  return (
    <li className="repo-intel__rec card">
      <div className="repo-intel__rec-head">
        <div className="repo-intel__rec-titles">
          <span className="repo-intel__rec-priority">#{rec.priority}</span>
          <h4>{rec.title}</h4>
        </div>
        <div className="repo-intel__rec-badges">
          <span className="badge badge-outline">{rec.type.replace(/_/g, " ")}</span>
          <span className={`badge badge-${rec.effort}`}>Effort: {rec.effort}</span>
        </div>
      </div>
      <p className="repo-intel__rec-rationale">{rec.description}</p>
      {motivatedBy && (
        <p className="repo-intel__rec-link mono-label">
          ↳ addresses finding: <span>{motivatedBy}</span>
        </p>
      )}
    </li>
  );
}
