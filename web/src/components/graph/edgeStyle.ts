import type { EdgeType } from "../../api/types";

interface EdgeStyleSpec {
  stroke: string;
  dashed?: boolean;
  animated?: boolean;
}

const EDGE_STYLES: Record<EdgeType, EdgeStyleSpec> = {
  contains: { stroke: "var(--edge-contains)" },
  imports: { stroke: "var(--edge-imports)" },
  calls: { stroke: "var(--edge-calls)", animated: true },
  depends_on: { stroke: "var(--edge-depends_on)", dashed: true },
  exposes: { stroke: "var(--edge-exposes)" },
  reads_writes: { stroke: "var(--edge-reads_writes)", dashed: true },
};

export function getEdgeStyle(type: EdgeType) {
  return EDGE_STYLES[type] ?? { stroke: "var(--on-dark-2)" };
}

export const EDGE_TYPES: EdgeType[] = ["contains", "imports", "calls", "depends_on", "exposes", "reads_writes"];
