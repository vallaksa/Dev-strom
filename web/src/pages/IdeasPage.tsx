import { useState, type FormEvent } from "react";
import { IdeaCard } from "../components/IdeaCard";
import { SectionMarker } from "../components/SectionMarker";
import { ErrorState, LoadingState } from "../components/StateBlocks";
import { useIdeaGeneration } from "../hooks/useIdeaGeneration";
import "./IdeasPage.css";

const EXAMPLES = [
  "A challenging backend project involving event-driven systems, payments, and AI that pushes my distributed-systems skills.",
  "Something with React and WebRTC — real-time collaboration, and I want to learn CRDTs properly.",
  "A beginner-friendly Python data project I can finish in a weekend and put on my resume.",
];

export function IdeasPage() {
  const [intent, setIntent] = useState("");
  const [count, setCount] = useState(3);

  const [state, run] = useIdeaGeneration();

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    const trimmed = intent.trim();
    if (!trimmed) return;
    // Send `intent` (the NL-first input) and mirror it into `tech_stack` for
    // backward compatibility: a backend that predates the `intent` field still
    // requires tech_stack, and the new backend backfills tech_stack = intent
    // itself — so both branches behave identically and merge order is moot.
    run({ intent: trimmed, tech_stack: trimmed, count });
  };

  return (
    <div className="ideas-page">
      <SectionMarker index="I" label="Generate Ideas" />
      <h1>What do you want to build?</h1>
      <p className="ideas-page__lede">
        Describe what you're after in plain language — a stack, a domain, the kind of challenge
        you want. Dev-Strom infers the rest and drafts project opportunities that teach engineering,
        not just fill a repo.
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
          <label className="ideas-form__count field">
            <span>Ideas</span>
            <input
              id="count"
              type="number"
              min={1}
              max={5}
              className="input"
              value={count}
              onChange={(e) => setCount(Math.max(1, Math.min(5, Number(e.target.value) || 1)))}
            />
          </label>
          <button
            type="submit"
            className="btn btn-primary"
            disabled={state.status === "loading" || !intent.trim()}
          >
            {state.status === "loading" ? "Generating…" : "Generate Ideas"}
          </button>
        </div>
      </form>

      <div className="ideas-page__results">
        {state.status === "loading" && <LoadingState label="Understanding intent and drafting opportunities" />}
        {state.status === "error" && <ErrorState message={state.error} />}
        {state.status === "success" && (
          <>
            <hr className="hr" />
            <SectionMarker index="II" label={`${state.data.ideas.length} Ideas · ${state.data.run_id}`} />
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
