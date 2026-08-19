type MermaidAPI = typeof import("mermaid")["default"];

// mermaid is a large dependency (its diagram-type parsers are themselves
// code-split internally) — imported dynamically here so it's only pulled
// into a loaded chunk when a diagram actually needs to render, instead of
// bloating the app's main entry bundle.
let mermaidApi: MermaidAPI | null = null;

async function ensureInit(): Promise<MermaidAPI> {
  if (mermaidApi) return mermaidApi;
  const { default: mermaid } = await import("mermaid");
  mermaid.initialize({
    startOnLoad: false,
    theme: "dark",
    themeVariables: {
      background: "#18171c",
      primaryColor: "#211f26",
      primaryTextColor: "#fffaf3",
      primaryBorderColor: "#b8460d",
      lineColor: "#b8b2a6",
      secondaryColor: "#2a2830",
      tertiaryColor: "#18171c",
      fontFamily: "JetBrains Mono, IBM Plex Mono, monospace",
    },
    securityLevel: "strict",
  });
  mermaidApi = mermaid;
  return mermaid;
}

let counter = 0;

/** Renders a mermaid diagram source string to an SVG markup string. */
export async function renderMermaid(source: string): Promise<string> {
  const mermaid = await ensureInit();
  const id = `mermaid-${Date.now()}-${counter++}`;
  const { svg } = await mermaid.render(id, source);
  return svg;
}
