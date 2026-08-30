import { useState, type FormEvent } from "react";
import { IdeaCard } from "../components/IdeaCard";
import { SectionMarker } from "../components/SectionMarker";
import { ErrorState, LoadingState } from "../components/StateBlocks";
import { useIdeaGeneration, type IdeaBatch } from "../hooks/useIdeaGeneration";
import type { IdeasRequest } from "../api/types";
import "./IdeasPage.css";

const EXAMPLES = [
  "A challenging backend project involving event-driven systems, payments, and AI that pushes my distributed-systems skills.",
  "Something with React and WebRTC — real-time collaboration, and I want to learn CRDTs properly.",
  "A beginner-friendly Python data project I can finish in a weekend and put on my resume.",
];

export function IdeasPage() {
  const [intent, setIntent] = useState("");
  const [refinementContext, setRefinementContext] = useState("");
  const [showRefinement, setShowRefinement] = useState(false);

  const [state, run] = useIdeaGeneration();

  const buildRequest = (refinement?: string, batches?: IdeaBatch[]): IdeasRequest => {
    const trimmed = intent.trim();
    const prior_ideas = batches?.flatMap((batch) =>
      batch.ideas.map((idea) => ({
        name: idea.name,
        problem_statement: idea.problem_statement,
      })),
    );
    return {
      intent: trimmed,
      tech_stack: trimmed,
      refinement_context: refinement?.trim() || undefined,
      prior_ideas: prior_ideas?.length ? prior_ideas : undefined,
    };
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!intent.trim()) return;
    run(buildRequest(), { append: false });
  };

  const handleGenerateMore = () => {
    if (!intent.trim()) return;
    const batches = state.status === "success" ? state.batches : [];
    run(buildRequest(showRefinement ? refinementContext : undefined, batches), { append: true });
  };

  const totalIdeas =
    state.status === "success"
      ? state.batches.reduce((n, b) => n + b.ideas.length, 0)
      : 0;

  return (
    <div className="ideas-page">
      <SectionMarker index="I" label="Generate Ideas" />
      <h1>What do you want to build?</h1>
      <p className="ideas-page__lede">
        Describe what you're after in plain language — a stack, a domain, the kind of challenge
        you want. Dev-Strom finds real-world problems from the live web and drafts two project
        opportunities per generation.
      </p>

      <form className="ideas-form card" onSubmit={handleSubmit}>
        <div className="field">
          <label htmlFor="intent">Your intent</label>
          <textarea
            id="intent"
            className="input ideas-form__intent"
            value={intent}
            onChange={(e) => setIntent(e.target.value)}
            placeholder="I'm looking for a challenging backend project involving event-driven systems, payments, and AI. I want something that pushes my distributed-systems skills."
            rows={5}
            required
          />
        </div>

        <div className="ideas-form__examples">
          <span className="mono-label">Try</span>
          {EXAMPLES.map((ex, i) => (
            <button
              key={i}
              type="button"
              className="ideas-form__chip"
              onClick={() => setIntent(ex)}
              title={ex}
            >
              {ex.length > 52 ? ex.slice(0, 52) + "…" : ex}
            </button>
          ))}
        </div>

        <div className="ideas-form__footer">
          <button
            type="submit"
            className="btn btn-primary"
            disabled={state.status === "loading" || !intent.trim()}
          >
            {state.status === "loading" ? "Generating…" : "Generate Ideas"}
          </button>
        </div>
      </form>

      {state.status === "success" && (
        <div className="ideas-form card ideas-form--more">
          <button
            type="button"
            className="ideas-form__toggle-refine"
            onClick={() => setShowRefinement((v) => !v)}
          >
            {showRefinement ? "Hide context" : "Add context (optional)"}
          </button>
          {showRefinement && (
            <div className="field">
              <label htmlFor="refinement">Refine this generation</label>
              <textarea
                id="refinement"
                className="input ideas-form__intent"
                value={refinementContext}
                onChange={(e) => setRefinementContext(e.target.value)}
                placeholder="e.g. focus on event-driven architecture, beginner-friendly, or serverless only"
                rows={3}
              />
            </div>
          )}
          <button
            type="button"
            className="btn btn-secondary"
            onClick={handleGenerateMore}
            disabled={!intent.trim()}
          >
            Generate more
          </button>
          {state.appendError && <p className="error-text">{state.appendError}</p>}
        </div>
      )}

      <div className="ideas-page__results ideas-page__results--scroll">
        {state.status === "loading" && (
          <LoadingState label="Searching for real-world problems and drafting opportunities" />
        )}
        {state.status === "error" && <ErrorState message={state.error} />}
        {state.status === "success" && (
          <>
            <hr className="hr" />
            <SectionMarker index="II" label={`${totalIdeas} Ideas`} />
            {state.batches.map((batch) => (
              <section key={batch.batchId} className="ideas-batch">
                <p className="ideas-batch__label mono-label">{batch.label}</p>
                <div className="ideas-grid">
                  {batch.ideas.map((idea) => (
                    <IdeaCard
                      key={`${batch.runId}-${idea.pid}`}
                      idea={idea}
                      runId={batch.runId}
                    />
                  ))}
                </div>
              </section>
            ))}
          </>
        )}
      </div>
    </div>
  );
}
