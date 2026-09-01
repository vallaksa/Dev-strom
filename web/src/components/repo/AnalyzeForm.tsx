import { useState, type FormEvent } from "react";
import type { AnalyzeRequest } from "../../api/types";
import "./AnalyzeForm.css";

type InputMode = "repo_url" | "path";

const MODE_LABEL: Record<InputMode, string> = {
  repo_url: "Repository URL",
  path: "Local Path",
};

/**
 * The Repository Intelligence input card: mode switch + target field +
 * submit. Owns only its own form state; the parent runs the analysis.
 */
export function AnalyzeForm({
  busy,
  onAnalyze,
}: {
  busy: boolean;
  onAnalyze: (request: AnalyzeRequest) => void;
}) {
  const [mode, setMode] = useState<InputMode>("repo_url");
  const [url, setUrl] = useState("");
  const [path, setPath] = useState("");

  const value = mode === "repo_url" ? url : path;
  const disabled = busy || !value.trim();

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (disabled) return;
    onAnalyze(mode === "repo_url" ? { repo_url: url.trim() } : { path: path.trim() });
  };

  return (
    <form className="card analyze-form" onSubmit={handleSubmit}>
      <div className="analyze-form__mode">
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

      <div className="field analyze-form__field">
        <label htmlFor="analyze-target">{MODE_LABEL[mode]}</label>
        <input
          id="analyze-target"
          className="input analyze-form__input"
          value={value}
          onChange={(e) => (mode === "repo_url" ? setUrl(e.target.value) : setPath(e.target.value))}
          placeholder={mode === "path" ? "/path/to/repo" : "https://github.com/user/repository"}
          autoComplete="off"
          spellCheck={false}
          required
        />
      </div>

      <div className="analyze-form__actions">
        <button type="submit" className="btn btn-primary" disabled={disabled}>
          {busy ? "Analyzing…" : "Analyze Repository"}
        </button>
      </div>
    </form>
  );
}
