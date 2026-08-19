import { Handle, Position, type NodeProps } from "@xyflow/react";
import type { GraphNode as GraphNodeModel, NodeType } from "../../api/types";
import "./GraphNode.css";

const TYPE_GLYPH: Record<NodeType, string> = {
  repo: "◆",
  package: "▤",
  module: "▭",
  file: "▯",
  class: "⬡",
  function: "○",
  external_dep: "⇢",
  service: "▣",
  entrypoint: "▶",
};

export type GraphNodeData = {
  node: GraphNodeModel;
  dimmed?: boolean;
};

export function GraphNodeComponent({ data, selected }: NodeProps) {
  const { node, dimmed } = data as unknown as GraphNodeData;
  return (
    <div
      className={
        `graph-node graph-node--${node.type}` +
        (selected ? " is-selected" : "") +
        (dimmed ? " is-dimmed" : "")
      }
    >
      <Handle type="target" position={Position.Left} />
      <div className="graph-node__glyph">{TYPE_GLYPH[node.type]}</div>
      <div className="graph-node__body">
        <span className="graph-node__type mono-label">{node.type.replace("_", " ")}</span>
        <span className="graph-node__label">{node.label}</span>
      </div>
      <Handle type="source" position={Position.Right} />
    </div>
  );
}

export const graphNodeTypes = { entity: GraphNodeComponent };
