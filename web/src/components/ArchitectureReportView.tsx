import type { ArchitectureReport } from "../api/types";
import { MermaidDiagram } from "./graph/MermaidDiagram";
import { SectionMarker } from "./SectionMarker";
import "./ArchitectureReportView.css";

export function ArchitectureReportView({ report }: { report: ArchitectureReport }) {
  return (
    <div className="arch-report">
      <SectionMarker index="III" label="Architecture Report" />

      <div className="card arch-report__summary">
        <p>{report.summary}</p>
        {report.layers.length > 0 && (
          <div className="arch-report__layers">
            {report.layers.map((layer, i) => (
              <span key={i} className="badge">
                {layer}
              </span>
            ))}
          </div>
        )}
      </div>

      <div className="arch-report__grid">
        <div className="card">
          <span className="mono-label accent">Components</span>
          <div className="arch-report__components">
            {report.components.map((c, i) => (
              <div key={i} className="arch-report__component">
                <strong>{c.name}</strong>
                <p>{c.responsibility}</p>
                <span className="mono-label">{c.node_ids.length} node(s)</span>
              </div>
            ))}
          </div>
        </div>

        <div className="card">
          <span className="mono-label accent">Data Flow</span>
          <p>{report.data_flow}</p>

          {report.external_integrations.length > 0 && (
            <>
              <span className="mono-label accent">External Integrations</span>
              <div className="arch-report__chips">
                {report.external_integrations.map((ext, i) => (
                  <span key={i} className="badge badge-outline">
                    {ext}
                  </span>
                ))}
              </div>
            </>
          )}
        </div>
      </div>

      {report.risks.length > 0 && (
        <div className="card arch-report__risks">
          <span className="mono-label accent">Risks</span>
          <ul>
            {report.risks.map((risk, i) => (
              <li key={i}>{risk}</li>
            ))}
          </ul>
        </div>
      )}

      {report.mermaid && (
        <div className="arch-report__mermaid">
          <span className="mono-label accent">Diagram</span>
          <MermaidDiagram source={report.mermaid} />
        </div>
      )}
    </div>
  );
}
