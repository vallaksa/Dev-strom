import type { GraphEdge, GraphNode, ProjectGraph } from "../../api/types";
import "./DetailPanel.css";

function labelFor(graph: ProjectGraph, id: string): string {
  return graph.nodes.find((n) => n.id === id)?.label ?? id;
}

export function DetailPanel({
  node,
  graph,
  onClose,
  onSelectNode,
}: {
  node: GraphNode;
  graph: ProjectGraph;
  onClose: () => void;
  onSelectNode: (id: string) => void;
}) {
  const outgoing: GraphEdge[] = graph.edges.filter((e) => e.source === node.id);
  const incoming: GraphEdge[] = graph.edges.filter((e) => e.target === node.id);
  const imports = outgoing.filter((e) => e.type === "imports");
  const importedBy = incoming.filter((e) => e.type === "imports");

  return (
    <aside className="detail-panel">
      <div className="detail-panel__head">
        <span className={`detail-panel__type mono-label`}>{node.type.replace("_", " ")}</span>
        <button type="button" className="detail-panel__close" onClick={onClose} aria-label="Close">
          &times;
        </button>
      </div>

      <h3 className="detail-panel__title">{node.label}</h3>

      {node.path && <p className="detail-panel__path mono-label">{node.path}</p>}
      {node.language && <span className="badge badge-outline">{node.language}</span>}

      {node.summary && <p className="detail-panel__summary">{node.summary}</p>}

      {imports.length > 0 && (
        <div className="detail-panel__section">
          <span className="mono-label accent">Imports ({imports.length})</span>
          <ul>
            {imports.map((e) => (
              <li key={e.target}>
                <button className="detail-panel__link" onClick={() => onSelectNode(e.target)}>
                  {labelFor(graph, e.target)}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {importedBy.length > 0 && (
        <div className="detail-panel__section">
          <span className="mono-label accent">Imported By ({importedBy.length})</span>
          <ul>
            {importedBy.map((e) => (
              <li key={e.source}>
                <button className="detail-panel__link" onClick={() => onSelectNode(e.source)}>
                  {labelFor(graph, e.source)}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {(outgoing.length > 0 || incoming.length > 0) && (
        <div className="detail-panel__section">
          <span className="mono-label accent">All Relationships</span>
          <ul>
            {outgoing.map((e, i) => (
              <li key={`out-${i}`}>
                <span className="detail-panel__edge-type">{e.type}</span> &rarr;{" "}
                <button className="detail-panel__link" onClick={() => onSelectNode(e.target)}>
                  {labelFor(graph, e.target)}
                </button>
              </li>
            ))}
            {incoming.map((e, i) => (
              <li key={`in-${i}`}>
                <button className="detail-panel__link" onClick={() => onSelectNode(e.source)}>
                  {labelFor(graph, e.source)}
                </button>{" "}
                &rarr; <span className="detail-panel__edge-type">{e.type}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {Object.keys(node.meta).length > 0 && (
        <div className="detail-panel__section">
          <span className="mono-label accent">Meta</span>
          <pre className="detail-panel__meta">{JSON.stringify(node.meta, null, 2)}</pre>
        </div>
      )}
    </aside>
  );
}
