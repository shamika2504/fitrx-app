export function StatTile({
  label,
  value,
  sub,
  compact = false,
}: {
  label: string;
  value: string;
  sub?: string;
  /** Smaller value text — for secondary/technical panels that shouldn't compete for attention. */
  compact?: boolean;
}) {
  return (
    <div
      className={`rounded-lg border border-[var(--border)] bg-[var(--surface)] ${
        compact ? "px-3 py-2" : "px-4 py-3"
      }`}
    >
      <div className="text-xs text-[var(--text-muted)]">{label}</div>
      <div
        className={`mt-1 font-semibold text-[var(--text-primary)] ${
          compact ? "text-base" : "text-2xl"
        }`}
      >
        {value}
      </div>
      {sub ? (
        <div className="mt-0.5 text-xs text-[var(--text-secondary)]">{sub}</div>
      ) : null}
    </div>
  );
}
