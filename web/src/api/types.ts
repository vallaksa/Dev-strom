/**
 * Domain types mirroring the Dev-Strom FastAPI backend contracts
 * (app/cartographer/model.py, app/models/dto.py, app/services/*).
 *
 * Keep these in sync with the Python pydantic models — this file is the
 * single source of truth for shapes consumed on the frontend.
 */

// ── Ideas ────────────────────────────────────────────────────────────────

export interface IdeasRequest {
  /**
   * Natural-language description of what the user wants to build. The backend
   * infers stack, domain, level, and complexity from this text — the caller no
   * longer supplies those as structured fields.
   */
  intent: string;
  count?: number; // 1-5, optional; backend defaults
  // ── Deprecated structured inputs (kept optional for backward compatibility
  //    with older backends and persisted history) ──
  tech_stack?: string;
  domain?: string;
  level?: string;
  enable_multi_query?: boolean;
}

export interface Idea {
  pid: number;
  name: string;
  problem_statement: string;
  why_it_fits: string[];
  real_world_value: string;
  implementation_plan: string[];
  // ── Engineering-intelligence fields (additive; may be absent on older runs) ──
  /** Concrete engineering problems this project forces you to solve. */
  engineering_challenges?: string[];
  /** Why the architecture would be shaped this way — the design reasoning. */
  architectural_intent?: string;
  /** Design tradeoffs the builder accepts (what you gain vs. give up). */
  tradeoffs?: string[];
  /** Business/real-world payoff; UI falls back to real_world_value when absent. */
  business_value?: string;
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

// ── Repository Analysis (unified Analysis domain model) ──────────────────
// Mirrors the backend's `Analysis.model_dump(mode="json")` produced by
// analyze_repository(). This is the evidence-first contract that powers the
// Repository Intelligence 4-tab view. See app/models/domain.py (Apollo).

export type FindingCategory =
  | "architecture"
  | "design"
  | "scalability"
  | "reliability"
  | "security"
  | "performance"
  | "maintainability"
  | "testing"
  | "product";

export type Severity = "critical" | "high" | "medium" | "low" | "info";

export type RecommendationType =
  | "product"
  | "engineering"
  | "scalability"
  | "reliability"
  | "security"
  | "developer_experience";

export type DependencyEcosystem = "pypi" | "npm" | "go" | "maven" | "unknown";

/** A concrete, located citation backing a finding — the trust layer. */
export interface Evidence {
  file: string | null;
  line_start: number | null;
  line_end: number | null;
  symbol: string | null;
  snippet: string | null;
  explanation: string;
}

export interface AnalysisFinding {
  id: string;
  repository_id: string;
  category: FindingCategory;
  title: string;
  description: string;
  confidence: number; // 0.0–1.0
  severity: Severity;
  evidence: Evidence[];
}

export interface AnalysisRecommendation {
  id: string;
  finding_id: string | null; // links back to the motivating finding
  type: RecommendationType;
  title: string;
  description: string;
  impact: ImpactLevel;
  effort: EffortLevel;
  priority: number; // 1-based; 1 = do first
}

export interface Dependency {
  name: string;
  ecosystem: DependencyEcosystem;
  source: string;
  version: string | null;
}

export interface AnalysisRepository {
  id: string;
  url: string | null;
  root_path: string;
  commit_sha: string | null;
  language: string | null;
  languages: string[];
  dependencies: Dependency[];
  entrypoints: string[];
  file_count: number;
  loc: number;
  created_at: string;
}

export interface Analysis {
  /**
   * Persisted row id — the key History reloads against (GET /analyze/{run_id}).
   * Distinct from the inner analysis `id`.
   */
  run_id: string;
  id: string;
  status: "complete" | "failed";
  summary: string;
  created_at: string;
  repository: AnalysisRepository;
  findings: AnalysisFinding[];
  recommendations: AnalysisRecommendation[];
  /**
   * Full structural ProjectGraph built deterministically during ingestion —
   * same shape as CartographResponse.project_graph, so it renders directly in
   * the interactive graph. Null when no graph was produced.
   */
  graph?: ProjectGraph | null;
  /** Optional architecture diagram (Mermaid) fallback. Additive; may be null. */
  mermaid?: string | null;
}

export interface AnalyzeRequest {
  repo_url?: string;
  path?: string;
}

/** Row shape for the analysis history list (GET /analyses). */
export interface AnalysisSummary {
  run_id: string;
  repo_url: string | null;
  language: string | null;
  status: "complete" | "failed";
  finding_count: number;
  recommendation_count: number;
  created_at: string;
}

export interface AnalysisHistoryResponse {
  analyses: AnalysisSummary[];
  limit: number;
  offset: number;
}

// ── Health ───────────────────────────────────────────────────────────────

export interface HealthResponse {
  status: string;
  database?: string;
}
