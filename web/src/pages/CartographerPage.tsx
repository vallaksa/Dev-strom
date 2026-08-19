import { useState, type FormEvent } from "react";
import { postCartograph } from "../api/cartograph";
import { ArchitectureReportView } from "../components/ArchitectureReportView";
import { CartographGraph } from "../components/graph/CartographGraph";
import { SectionMarker } from "../components/SectionMarker";
import { ErrorState, LoadingState } from "../components/StateBlocks";
import { useAsyncAction } from "../hooks/useAsyncAction";
import "./CartographerPage.css";

type InputMode = "repo_url" | "path";

export function CartographerPage() {
  const [mode, setMode] = useState<InputMode>("repo_url");
  const [value, setValue] = useState("https://github.com/example-org/dev-strom");

  const [state, run] = useAsyncAction(postCartograph);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!value.trim()) return;
    run(mode === "repo_url" ? { repo_url: value.trim() } : { path: value.trim() });
  };

  return (
    <div className="cartographer-page">
      <SectionMarker index="II" label="Project Cartographer" />
      <h1>Map a repository&rsquo;s architecture.</h1>
      <p className="cartographer-page__lede">
        Point Dev-Strom at a repo and it will parse the codebase into a structural graph,
        then ask an LLM to summarize how it's put together.
      </p>

      <form className="card cartographer-form" onSubmit={handleSubmit}>
        <div className="cartographer-form__mode">
          <button
            type="button"
            className={"btn btn-sm " + (mode === "repo_url" ? "btn-primary" : "btn-secondary")}
            onClick={() => setMode("repo_url")}
          >
            Repo URL
          </button>
          <button
            type="button"
            className={"btn btn-sm " + (mode === "path" ? "btn-primary" : "btn-secondary")}
            onClick={() => setMode("path")}
          >
            Local Path
          </button>
        </div>
        <div className="field cartographer-form__input">
          <label htmlFor="repo-target">{mode === "repo_url" ? "Repository URL" : "Local Path"}</label>
          <input
            id="repo-target"
            className="input"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder={mode === "repo_url" ? "https://github.com/org/repo" : "/path/to/repo"}
            required
          />
        </div>
        <button type="submit" className="btn btn-primary" disabled={state.status === "loading"}>
          {state.status === "loading" ? "Mapping…" : "Map Repository"}
        </button>
      </form>

      {state.status === "loading" && <LoadingState label="Cloning, parsing, and analyzing" />}
      {state.status === "error" && <ErrorState message={state.error} />}

      {state.status === "success" && (
        <div className="cartographer-page__results">
          <hr className="hr" />
          <div className="cartographer-page__run-meta mono-label">
            Run {state.data.run_id} &middot; {state.data.project_graph.nodes.length} nodes &middot;{" "}
            {state.data.project_graph.edges.length} edges &middot;{" "}
            {state.data.project_graph.languages.join(", ") || "unknown language"}
          </div>

          <CartographGraph graph={state.data.project_graph} />

          <ArchitectureReportView report={state.data.architecture_report} />
        </div>
      )}
    </div>
  );
}
