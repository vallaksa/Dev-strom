/** Shared loading / error / empty states used across pages. */

export function LoadingState({ label = "Loading" }: { label?: string }) {
  return (
    <div className="state-block">
      <div className="spinner" />
      <span className="mono-label">{label}&hellip;</span>
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="state-block card">
      <span className="mono-label accent">Error</span>
      <p className="error-text">{message}</p>
      {onRetry && (
        <button type="button" className="btn btn-secondary btn-sm" onClick={onRetry}>
          Retry
        </button>
      )}
    </div>
  );
}

export function EmptyState({ message }: { message: string }) {
  return (
    <div className="state-block">
      <p style={{ color: "var(--ink-3)" }}>{message}</p>
    </div>
  );
}
