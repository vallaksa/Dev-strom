import { useMemo, useState } from "react";
import {
  Background,
  BackgroundVariant,
  Controls,
  MarkerType,
  MiniMap,
  ReactFlow,
  ReactFlowProvider,
  type Edge as RFEdge,
  type Node as RFNode,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { GraphNode, NodeType, ProjectGraph } from "../../api/types";
import { layoutGraph } from "../../lib/graphLayout";
import { DetailPanel } from "./DetailPanel";
import { getEdgeStyle } from "./edgeStyle";
import { graphNodeTypes, type GraphNodeData } from "./GraphNode";
import { Legend } from "./Legend";
import "./CartographGraph.css";

const SYSTEM_TYPES: NodeType[] = [
  "repo",
  "service",
  "entrypoint",
  "external_dep",
];

function GraphInner({ graph }: { graph: ProjectGraph }) {
  const [activeTypes, setActiveTypes] = useState<Set<NodeType>>(new Set(SYSTEM_TYPES));
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const n of graph.nodes) c[n.type] = (c[n.type] ?? 0) + 1;
    return c;
  }, [graph.nodes]);

  const { nodes, edges } = useMemo(() => {
    const visibleIds = new Set(graph.nodes.filter((n) => activeTypes.has(n.type)).map((n) => n.id));

    const rfNodes: RFNode[] = graph.nodes
      .filter((n) => visibleIds.has(n.id))
      .map((n: GraphNode) => ({
        id: n.id,
        type: "entity",
        position: { x: 0, y: 0 },
        data: { node: n, dimmed: false } satisfies GraphNodeData,
        selected: n.id === selectedId,
      }));

    const rfEdges: RFEdge[] = graph.edges
      .filter((e) => visibleIds.has(e.source) && visibleIds.has(e.target))
      .map((e, i) => {
        const style = getEdgeStyle(e.type);
        return {
          id: `${e.source}->${e.target}-${e.type}-${i}`,
          source: e.source,
          target: e.target,
          type: "smoothstep",
          animated: style.animated,
          style: {
            stroke: style.stroke,
            strokeWidth: 1.5,
            strokeDasharray: style.dashed ? "5 4" : undefined,
          },
          markerEnd: { type: MarkerType.ArrowClosed, color: style.stroke, width: 14, height: 14 },
        };
      });

    return layoutGraph(rfNodes, rfEdges, "LR");
  }, [graph, activeTypes, selectedId]);

  const selectedNode = selectedId ? graph.nodes.find((n) => n.id === selectedId) ?? null : null;

  const toggleType = (type: NodeType) => {
    setActiveTypes((prev) => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type);
      else next.add(type);
      return next;
    });
  };

  return (
    <div className="carto-graph">
      <div className="carto-graph__canvas panel-dark">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={graphNodeTypes}
          onNodeClick={(_, node) => setSelectedId(node.id)}
          onPaneClick={() => setSelectedId(null)}
          fitView
          minZoom={0.1}
          maxZoom={2}
          proOptions={{ hideAttribution: true }}
        >
          <Background variant={BackgroundVariant.Dots} color="#35333a" gap={20} size={1} />
          <Controls showInteractive={false} />
          <MiniMap
            pannable
            zoomable
            maskColor="rgba(17,16,20,0.75)"
            nodeColor={(n) => {
              const data = n.data as unknown as GraphNodeData;
              return `var(--node-${data.node.type})`;
            }}
            style={{ background: "var(--canvas-2)" }}
          />
        </ReactFlow>
        <div className="carto-graph__legend-overlay">
          <Legend activeTypes={activeTypes} onToggle={toggleType} counts={counts} />
        </div>
      </div>

      {selectedNode && (
        <DetailPanel
          node={selectedNode}
          graph={graph}
          onClose={() => setSelectedId(null)}
          onSelectNode={(id) => setSelectedId(id)}
        />
      )}
    </div>
  );
}

export function CartographGraph({ graph }: { graph: ProjectGraph }) {
  return (
    <ReactFlowProvider>
      <GraphInner graph={graph} />
    </ReactFlowProvider>
  );
}
