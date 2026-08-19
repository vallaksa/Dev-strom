import dagre from "dagre";
import type { Edge as RFEdge, Node as RFNode } from "@xyflow/react";

const NODE_WIDTH = 220;
const NODE_HEIGHT = 64;

/**
 * Lays out React Flow nodes/edges left-to-right with dagre, mutating
 * positions only (types/data are passed through untouched). Returns new
 * arrays so React Flow re-renders.
 */
export function layoutGraph(
  nodes: RFNode[],
  edges: RFEdge[],
  direction: "LR" | "TB" = "LR",
): { nodes: RFNode[]; edges: RFEdge[] } {
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: direction, nodesep: 48, ranksep: 96, marginx: 32, marginy: 32 });

  for (const node of nodes) {
    g.setNode(node.id, { width: NODE_WIDTH, height: NODE_HEIGHT });
  }
  for (const edge of edges) {
    g.setEdge(edge.source, edge.target);
  }

  dagre.layout(g);

  const laidOutNodes = nodes.map((node) => {
    const pos = g.node(node.id);
    return {
      ...node,
      position: { x: pos.x - NODE_WIDTH / 2, y: pos.y - NODE_HEIGHT / 2 },
    };
  });

  return { nodes: laidOutNodes, edges };
}

export { NODE_WIDTH, NODE_HEIGHT };
