import type { ReactNode } from "react";
import { Link, useMatch } from "react-router-dom";
import { EmptyState, ErrorState, LoadingState } from "../StateBlocks";
import { useRuns } from "../../hooks/useRuns";
import { useSidebar } from "../../hooks/useSidebar";
import type { RunGroup } from "../../lib/sidebar";
import type { AnalysisSummary, HistoryRun } from "../../api/types";

function relativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const diff = Date.now() - then;
  const min = Math.round(diff / 60_000);
  if (min < 1) return "just now";
  if (min < 60) return `${min}m ago`;
  const hr = Math.round(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const day = Math.round(hr / 24);
  if (day < 30) return `${day}d ago`;
  return new Date(iso).toLocaleDateString();
}

function repoLabel(url: string | null): string {
  if (!url) return "local path";
  const clean = url.replace(/\.git$/, "").replace(/\/$/, "");
  const parts = clean.split("/").filter(Boolean);
  return parts.slice(-2).join("/") || clean;
}

function IdeaGlyph() {
  return (
    <svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true">
      <path
        d="M12 3a6 6 0 0 0-3.5 10.9c.5.4.8.9.9 1.5l.2 1.1h4.8l.2-1.1c.1-.6.4-1.1.9-1.5A6 6 0 0 0 12 3Z"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
      />
      <path d="M10 20h4M10.5 22h3" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}

function AnalysisGlyph() {
  return (
    <svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true">
      <circle cx="11" cy="11" r="6" fill="none" stroke="currentColor" strokeWidth="1.6" />
      <path d="m20 20-4.5-4.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}

function Chevron({ open }: { open: boolean }) {
  return (
    <svg
      className={"run-list__chevron" + (open ? " is-open" : "")}
      viewBox="0 0 24 24"
      width="12"
      height="12"
      aria-hidden="true"
    >
      <path d="m9 6 6 6-6 6" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

function Group({
  id,
  label,
  count,
  children,
}: {
  id: RunGroup;
  label: string;
  count: number;
  children: ReactNode;
}) {
  const { isGroupCollapsed, toggleGroup } = useSidebar();
  const open = !isGroupCollapsed(id);
  return (
    <section className="run-list__group">
      <button
        type="button"
        className="run-list__heading"
        aria-expanded={open}
        onClick={() => toggleGroup(id)}
      >
        <Chevron open={open} />
        <span className="mono-label">{label}</span>
        <span className="run-list__count">{count}</span>
      </button>
      {open && children}
    </section>
  );
}

function RunRow({
  to,
  active,
  glyph,
  title,
  meta,
}: {
  to: string;
  active: boolean;
  glyph: ReactNode;
  title: string;
  meta: string;
}) {
  return (
    <Link to={to} className={"run-row" + (active ? " is-active" : "")} title={title}>
      <span className="run-row__glyph">{glyph}</span>
      <span className="run-row__body">
        <span className="run-row__title">{title}</span>
        <span className="run-row__meta">{meta}</span>
      </span>
    </Link>
  );
}

export function RunList() {
  const runs = useRuns();
  const ideaMatch = useMatch("/history/:runId");
  const analysisMatch = useMatch("/analysis/:runId");
  const activeIdea = ideaMatch?.params.runId ?? null;
  const activeAnalysis = analysisMatch?.params.runId ?? null;

  if (runs.status === "loading") return <LoadingState label="Loading runs" />;
  if (runs.status === "error") {
    return <ErrorState message={runs.error} onRetry={runs.reload} />;
  }

  const ideas: HistoryRun[] = runs.data.ideas;
  const analyses: AnalysisSummary[] = runs.data.analyses;

  if (ideas.length === 0 && analyses.length === 0) {
    return <EmptyState message="No runs yet. Generate ideas or analyze a repo." />;
  }

  return (
    <div className="run-list">
      {analyses.length > 0 && (
        <Group id="analyses" label="Repo Analyses" count={analyses.length}>
          {analyses.map((a) => (
            <RunRow
              key={a.run_id}
              to={`/analysis/${a.run_id}`}
              active={a.run_id === activeAnalysis}
              glyph={<AnalysisGlyph />}
              title={repoLabel(a.repo_url)}
              meta={
                a.status === "failed"
                  ? `failed · ${relativeTime(a.created_at)}`
                  : `${a.finding_count} findings · ${relativeTime(a.created_at)}`
              }
            />
          ))}
        </Group>
      )}

      {ideas.length > 0 && (
        <Group id="ideas" label="Ideas" count={ideas.length}>
          {ideas.map((run) => (
            <RunRow
              key={run.run_id}
              to={`/history/${run.run_id}`}
              active={run.run_id === activeIdea}
              glyph={<IdeaGlyph />}
              title={run.tech_stack || run.run_id}
              meta={relativeTime(run.created_at)}
            />
          ))}
        </Group>
      )}
    </div>
  );
}
