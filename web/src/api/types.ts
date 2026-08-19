/**
 * Domain types mirroring the Dev-Strom FastAPI backend contracts
 * (app/cartographer/model.py, app/models/dto.py, app/services/*).
 *
 * Keep these in sync with the Python pydantic models — this file is the
 * single source of truth for shapes consumed on the frontend.
 */

// ── Ideas ────────────────────────────────────────────────────────────────

export interface IdeasRequest {
  tech_stack: string;
  domain?: string;
  level?: string;
  enable_multi_query?: boolean;
  count: number; // 1-5
}

export interface Idea {
  pid: number;
  name: string;
  problem_statement: string;
  why_it_fits: string[];
  real_world_value: string;
  implementation_plan: string[];
}

export interface IdeasResponse {
  run_id: string;
  ideas: Idea[];
}

export interface ExpandRequest {
  run_id: string;
  pid: number;
}

export interface ExpandResponse {
  idea: Idea;
  extended_plan: string[];
}

export interface ExportRequest {
  run_id: string;
  pid: number;
}

// ── History ──────────────────────────────────────────────────────────────

export interface HistoryRun {
  run_id: string;
  tech_stack: string;
  domain?: string | null;
  level?: string | null;
  count: number;
  created_at: string;
}

export interface HistoryResponse {
  runs: HistoryRun[];
  limit: number;
  offset: number;
}

export interface RunDetail {
  run_id: string;
  tech_stack: string;
  domain?: string | null;
  level?: string | null;
  count: number;
  created_at: string;
  ideas: Idea[];
  [key: string]: unknown;
}

// ── Project Cartographer ────────────────────────────────────────────────

export type NodeType =
  | "repo"
  | "package"
  | "module"
  | "file"
  | "class"
  | "function"
  | "external_dep"
  | "service"
  | "entrypoint";

export interface GraphNode {
  id: string;
  type: NodeType;
  label: string;
  path?: string;
  language?: string;
  summary?: string;
  meta: Record<string, unknown>;
}

export type EdgeType =
  | "contains"
  | "imports"
  | "calls"
  | "depends_on"
  | "exposes"
  | "reads_writes";

export interface GraphEdge {
  source: string;
  target: string;
  type: EdgeType;
  meta: Record<string, unknown>;
}

export interface ProjectGraph {
  repo_url?: string;
  root_path: string;
  languages: string[];
  nodes: GraphNode[];
  edges: GraphEdge[];
  entrypoints: string[];
  manifests: Record<string, unknown>;
  stats: Record<string, unknown>;
}

export interface ArchitectureComponent {
  name: string;
  responsibility: string;
  node_ids: string[];
}

export interface ArchitectureReport {
  summary: string;
  components: ArchitectureComponent[];
  layers: string[];
  data_flow: string;
  external_integrations: string[];
  mermaid: string;
  risks: string[];
}

export interface CartographRequest {
  repo_url?: string;
  path?: string;
}

export interface CartographResponse {
  run_id: string;
  project_graph: ProjectGraph;
  architecture_report: ArchitectureReport;
}

// ── Advisor ──────────────────────────────────────────────────────────────

export type RecommendationCategory =
  | "feature"
  | "refactor"
  | "tech_debt"
  | "risk"
  | "test"
  | "security"
  | "performance"
  | "docs";

export type ImpactLevel = "high" | "medium" | "low";
export type EffortLevel = "high" | "medium" | "low";

export interface Recommendation {
  id: string;
  category: RecommendationCategory;
  title: string;
  rationale: string;
  impact: ImpactLevel;
  effort: EffortLevel;
  affected_node_ids: string[];
  suggested_steps: string[];
}

export interface AdvisorReport {
  summary: string;
  tech_stack: string[];
  recommendations: Recommendation[];
  quick_wins: string[];
  strategic_bets: string[];
}

export interface AdviseRequest {
  repo_url?: string;
  path?: string;
  run_id?: string;
}

export interface AdviseResponse {
  run_id: string;
  advisor_report: AdvisorReport;
}

// ── Health ───────────────────────────────────────────────────────────────

export interface HealthResponse {
  status: string;
  database?: string;
}
