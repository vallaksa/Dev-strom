import { useState, type FormEvent } from "react";
import { postIdeas } from "../api/ideas";
import { IdeaCard } from "../components/IdeaCard";
import { SectionMarker } from "../components/SectionMarker";
import { ErrorState, LoadingState } from "../components/StateBlocks";
import { useAsyncAction } from "../hooks/useAsyncAction";
import "./IdeasPage.css";

const LEVELS = ["", "beginner", "intermediate", "advanced"];

export function IdeasPage() {
  const [techStack, setTechStack] = useState("Python, FastAPI, React");
  const [domain, setDomain] = useState("");
  const [level, setLevel] = useState("");
  const [count, setCount] = useState(3);
  const [multiQuery, setMultiQuery] = useState(false);

  const [state, run] = useAsyncAction(postIdeas);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    run({
      tech_stack: techStack,
      domain: domain || undefined,
      level: level || undefined,
      enable_multi_query: multiQuery,
      count,
    });
  };

  return (
    <div className="ideas-page">
      <SectionMarker index="I" label="Idea Generator" />
      <h1>What should you build next?</h1>
      <p className="ideas-page__lede">
        Describe a stack and Dev-Strom will draft scoped project ideas with a problem
        statement, rationale, real-world value, and an implementation plan.
      </p>

      <form className="ideas-form card" onSubmit={handleSubmit}>
        <div className="ideas-form__grid">
          <div className="field">
            <label htmlFor="tech-stack">Tech Stack</label>
            <input
              id="tech-stack"
              className="input"
              value={techStack}
              onChange={(e) => setTechStack(e.target.value)}
              placeholder="e.g. Python, FastAPI, React"
              required
            />
          </div>
          <div className="field">
            <label htmlFor="domain">Domain (optional)</label>
            <input
              id="domain"
              className="input"
              value={domain}
              onChange={(e) => setDomain(e.target.value)}
              placeholder="e.g. developer tools"
            />
          </div>
          <div className="field">
            <label htmlFor="level">Level (optional)</label>
            <select id="level" className="input" value={level} onChange={(e) => setLevel(e.target.value)}>
              {LEVELS.map((l) => (
                <option key={l} value={l}>
                  {l ? l[0].toUpperCase() + l.slice(1) : "Any"}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="count">Count (1&ndash;5)</label>
            <input
              id="count"
              type="number"
              min={1}
              max={5}
              className="input"
              value={count}
              onChange={(e) => setCount(Math.max(1, Math.min(5, Number(e.target.value) || 1)))}
            />
          </div>
        </div>

        <label className="ideas-form__checkbox">
          <input type="checkbox" checked={multiQuery} onChange={(e) => setMultiQuery(e.target.checked)} />
          <span className="mono-label">Enable multi-query web search</span>
        </label>

        <button type="submit" className="btn btn-primary" disabled={state.status === "loading"}>
          {state.status === "loading" ? "Generating…" : "Generate Ideas"}
        </button>
      </form>

      <div className="ideas-page__results">
        {state.status === "loading" && <LoadingState label="Generating ideas" />}
        {state.status === "error" && <ErrorState message={state.error} />}
        {state.status === "success" && (
          <>
            <hr className="hr" />
            <SectionMarker index="II" label={`${state.data.ideas.length} Ideas · Run ${state.data.run_id.slice(0, 8)}`} />
            <div className="ideas-grid">
              {state.data.ideas.map((idea) => (
                <IdeaCard key={idea.pid} idea={idea} runId={state.data.run_id} />
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
