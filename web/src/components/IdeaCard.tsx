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

  return (
    <article className="idea-card card">
      <div className="idea-card__head">
        <span className="mono-label accent">PID {idea.pid}</span>
      </div>
      <h3>{idea.name}</h3>

      <p className="idea-card__label mono-label">Problem</p>
      <p>{idea.problem_statement}</p>

      <p className="idea-card__label mono-label">Why It Fits</p>
      <ul>
        {idea.why_it_fits.map((point, i) => (
          <li key={i}>{point}</li>
        ))}
      </ul>

      <p className="idea-card__label mono-label">Real-World Value</p>
      <p>{idea.real_world_value}</p>

      <p className="idea-card__label mono-label">Implementation Plan</p>
      <ol>
        {idea.implementation_plan.map((step, i) => (
          <li key={i}>{step}</li>
        ))}
      </ol>

      {expanded && (
        <div className="idea-card__expansion">
          <hr className="hr" />
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
          {expanded ? "Collapse" : "Expand"}
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
