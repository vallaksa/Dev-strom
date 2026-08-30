import { useState } from "react";
import { postExpand, postExport } from "../api/ideas";
import type { Idea } from "../api/types";
import { useAsyncAction } from "../hooks/useAsyncAction";
import "./IdeaCard.css";

function downloadMarkdown(filename: string, content: string) {
  const blob = new Blob([content], { type: "text/markdown" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export function IdeaCard({ idea, runId }: { idea: Idea; runId: string }) {
  const [expanded, setExpanded] = useState(false);
  const [expandState, runExpand] = useAsyncAction(postExpand);
  const [exportState, runExport] = useAsyncAction(postExport);

  const handleExpand = async () => {
    if (!expanded) {
      setExpanded(true);
      if (expandState.status !== "success") {
        await runExpand({ run_id: runId, pid: idea.pid });
      }
    } else {
      setExpanded(false);
    }
  };

  const handleExport = async () => {
    const md = await runExport({ run_id: runId, pid: idea.pid });
    if (md) {
      const slug = idea.name.replace(/\s+/g, "_").slice(0, 50);
      downloadMarkdown(`devstrom_${slug}.md`, md);
    }
  };

  // business_value may arrive as "" (not just absent) — treat blank as missing
  // and fall back to real_world_value.
  const value = idea.business_value?.trim() ? idea.business_value : idea.real_world_value;
  const hasChallenges = (idea.engineering_challenges?.length ?? 0) > 0;
  const hasTradeoffs = (idea.tradeoffs?.length ?? 0) > 0;

  return (
    <article className="idea-card card">
      <div className="idea-card__head">
        <span className="mono-label accent">PID {idea.pid}</span>
      </div>
      <h3>{idea.name}</h3>

      {idea.pitch && (
        <>
          <p className="idea-card__label mono-label accent">Pitch</p>
          <p>{idea.pitch}</p>
        </>
      )}

      <p className="idea-card__label mono-label">Real-World Problem</p>
      <p>{idea.problem_statement}</p>

      <p className="idea-card__label mono-label">Why It's Interesting</p>
      <ul>
        {idea.why_it_fits.map((point, i) => (
          <li key={i}>{point}</li>
        ))}
      </ul>

      {hasChallenges && (
        <>
          <p className="idea-card__label mono-label accent">Engineering Challenges</p>
          <ul className="idea-card__challenges">
            {idea.engineering_challenges!.map((c, i) => (
              <li key={i}>{c}</li>
            ))}
          </ul>
        </>
      )}

      {idea.architectural_intent && (
        <div className="idea-card__intent">
          <p className="idea-card__label mono-label accent">Architectural Intent</p>
          <p>{idea.architectural_intent}</p>
        </div>
      )}

      {hasTradeoffs && (
        <>
          <p className="idea-card__label mono-label">Tradeoffs</p>
          <ul className="idea-card__tradeoffs">
            {idea.tradeoffs!.map((t, i) => (
              <li key={i}>{t}</li>
            ))}
          </ul>
        </>
      )}

      <p className="idea-card__label mono-label">Real-World Value</p>
      <p>{value}</p>

      {(idea.implementation_plan?.length ?? 0) > 0 && (
        <>
          <p className="idea-card__label mono-label">Implementation Plan</p>
          <ol>
            {idea.implementation_plan!.map((step, i) => (
              <li key={i}>{step}</li>
            ))}
          </ol>
        </>
      )}

      {expanded && (
        <div className="idea-card__expansion">
          <hr className="hr" />
          {expandState.status === "success" &&
            (expandState.data.idea.implementation_plan?.length ?? 0) > 0 && (
              <>
                <p className="idea-card__label mono-label accent">Implementation Plan</p>
                <ol>
                  {expandState.data.idea.implementation_plan!.map((step, i) => (
                    <li key={i}>{step}</li>
                  ))}
                </ol>
              </>
            )}
          <p className="idea-card__label mono-label accent">Extended Plan</p>
          {expandState.status === "loading" && <span className="mono-label">Expanding&hellip;</span>}
          {expandState.status === "error" && <p className="error-text">{expandState.error}</p>}
          {expandState.status === "success" && (
            <ol>
              {expandState.data.extended_plan.map((step, i) => (
                <li key={i}>{step}</li>
              ))}
            </ol>
          )}
        </div>
      )}

      <div className="idea-card__actions">
        <button type="button" className="btn btn-secondary btn-sm" onClick={handleExpand}>
          {expanded ? "Collapse" : "Deepen Plan"}
        </button>
        <button
          type="button"
          className="btn btn-primary btn-sm"
          onClick={handleExport}
          disabled={exportState.status === "loading"}
        >
          {exportState.status === "loading" ? "Exporting…" : "Export"}
        </button>
      </div>
      {exportState.status === "error" && <p className="error-text">{exportState.error}</p>}
    </article>
  );
}
