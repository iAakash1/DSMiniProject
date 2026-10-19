export function EmptyState({ message }: { message: string }) {
  return <div className="empty-state">{message}</div>;
}

export function ErrorState({ message }: { message: string }) {
  return <div className="error-state">Could not reach the control API: {message}</div>;
}

export function LoadingState() {
  return <div className="empty-state">Loading…</div>;
}
