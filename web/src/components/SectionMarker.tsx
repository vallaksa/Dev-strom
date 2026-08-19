/** October-style numbered/roman-numeral section marker, e.g. "I. Overview". */
export function SectionMarker({ index, label }: { index: string; label: string }) {
  return (
    <div className="section-marker" data-index={index}>
      {label}
    </div>
  );
}
