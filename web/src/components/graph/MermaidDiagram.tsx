import { useEffect, useRef, useState } from "react";
import { renderMermaid } from "../../lib/mermaidRender";
import { ErrorState, LoadingState } from "../StateBlocks";
import "./MermaidDiagram.css";

export function MermaidDiagram({ source }: { source: string }) {
  const [svg, setSvg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    setSvg(null);
    setError(null);
    if (!source.trim()) {
      setError("No mermaid diagram was returned for this report.");
      return;
    }
    renderMermaid(source)
      .then((markup) => {
        if (!cancelled) setSvg(markup);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to render diagram.");
      });
    return () => {
      cancelled = true;
    };
  }, [source]);

  if (error) return <ErrorState message={error} />;
  if (!svg) return <LoadingState label="Rendering diagram" />;

  return <div ref={containerRef} className="mermaid-diagram" dangerouslySetInnerHTML={{ __html: svg }} />;
}
