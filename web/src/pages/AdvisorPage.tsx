import { useState, type FormEvent } from "react";
import { postAdvise } from "../api/advise";
import { AdvisorReportView } from "../components/AdvisorReportView";
import { SectionMarker } from "../components/SectionMarker";
import { ErrorState, LoadingState } from "../components/StateBlocks";
import { useAsyncAction } from "../hooks/useAsyncAction";
import type { AdviseRequest } from "../api/types";
import "./AdvisorPage.css";

type InputMode = "repo_url" | "path" | "run_id";

const MODE_LABEL: Record<InputMode, string> = {
  repo_url: "Repository URL",
  path: "Local Path",
  run_id: "Existing Cartograph Run ID",
};

export function AdvisorPage() {
  const [mode, setMode] = useState<InputMode>("repo_url");
  const [value, setValue] = useState("https://github.com/example-org/dev-strom");

  const [state, run] = useAsyncAction(postAdvise);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    const trimmed = value.trim();
    if (!trimmed) return;
    const body: AdviseRequest =
      mode === "repo_url" ? { repo_url: trimmed } : mode === "path" ? { path: trimmed } : { run_id: trimmed };
    run(body);
  };

  return (
    <div className="advisor-page">
      <SectionMarker index="III" label="Advisor" />
      <h1>Get an architectural second opinion.</h1>
      <p className="advisor-page__lede">
        Point Dev-Strom at a repo (or reuse a prior Cartographer run) and it will
        recommend concrete next moves, ranked by impact and effort.
      </p>

      <form className="card advisor-form" onSubmit={handleSubmit}>
        <div className="advisor-form__mode">
          {(Object.keys(MODE_LABEL) as InputMode[]).map((m) => (
            <button
              key={m}
              type="button"
              className={"btn btn-sm " + (mode === m ? "btn-primary" : "btn-secondary")}
              onClick={() => setMode(m)}
            >
              {MODE_LABEL[m]}
            </button>
          ))}
        </div>
        <div className="field advisor-form__input">
          <label htmlFor="advise-target">{MODE_LABEL[mode]}</label>
          <input
            id="advise-target"
            className="input"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder={mode === "run_id" ? "e.g. 8c1e2f9a-…" : "https://github.com/org/repo"}
            required
          />
        </div>
        <button type="submit" className="btn btn-primary" disabled={state.status === "loading"}>
          {state.status === "loading" ? "Advising…" : "Get Recommendations"}
        </button>
      </form>

      {state.status === "loading" && <LoadingState label="Analyzing and drafting recommendations" />}
      {state.status === "error" && <ErrorState message={state.error} />}
      {state.status === "success" && (
        <>
          <div className="advisor-page__run-meta mono-label">Run {state.data.run_id}</div>
          <AdvisorReportView report={state.data.advisor_report} />
        </>
      )}
    </div>
  );
}
