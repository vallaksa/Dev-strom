import type { NodeType } from "../../api/types";
import { EDGE_TYPES } from "./edgeStyle";
import "./Legend.css";

const NODE_TYPES: NodeType[] = [
  "repo",
  "package",
  "module",
  "file",
  "class",
  "function",
  "external_dep",
  "service",
  "entrypoint",
];

export function Legend({
  activeTypes,
  onToggle,
  counts,
}: {
  activeTypes: Set<NodeType>;
  onToggle: (type: NodeType) => void;
  counts: Record<string, number>;
}) {
  return (
    <div className="graph-legend">
      <span className="mono-label" style={{ color: "var(--on-dark-2)" }}>
        Node Types
      </span>
      <div className="graph-legend__items">
        {NODE_TYPES.map((type) => (
          <button
            key={type}
            type="button"
            className={"graph-legend__item" + (activeTypes.has(type) ? " is-active" : "")}
            onClick={() => onToggle(type)}
          >
            <span className={`graph-legend__swatch graph-legend__swatch--${type}`} />
            {type.replace("_", " ")}
            <span className="graph-legend__count">{counts[type] ?? 0}</span>
          </button>
        ))}
      </div>

      <span className="mono-label" style={{ color: "var(--on-dark-2)", marginTop: "12px" }}>
        Edge Types
      </span>
      <div className="graph-legend__items">
        {EDGE_TYPES.map((type) => (
          <div key={type} className="graph-legend__item graph-legend__item--static">
            <span className={`graph-legend__line graph-legend__line--${type}`} />
            {type.replace("_", " ")}
          </div>
        ))}
      </div>
    </div>
  );
}
