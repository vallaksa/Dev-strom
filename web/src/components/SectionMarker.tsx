/** Small uppercase eyebrow that labels a section, e.g. "Repository Intelligence". */
export function SectionMarker({ label }: { label: string }) {
  return <div className="section-marker">{label}</div>;
}
