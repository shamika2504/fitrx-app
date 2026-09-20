export function Card({
  title,
  subtitle,
  children,
  accent = false,
  dense = false,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  /** Visually heavier — for the one card that should read as the hero. */
  accent?: boolean;
  /** Visually lighter/smaller — for secondary, technical-detail sections. */
  dense?: boolean;
}) {
  return (
    <section
      className={`rounded-xl border bg-[var(--surface)] ${
        accent
          ? "border-[var(--border)] border-l-4 border-l-[var(--series-1)] p-6"
          : dense
            ? "border-[var(--border)] p-4"
            : "border-[var(--border)] p-5"
      }`}
    >
      <h2
        className={
          accent
            ? "text-base font-semibold text-[var(--text-primary)]"
            : dense
              ? "text-xs font-semibold text-[var(--text-secondary)]"
              : "text-sm font-semibold text-[var(--text-primary)]"
        }
      >
        {title}
      </h2>
      {subtitle ? (
        <p className="mt-0.5 text-xs text-[var(--text-secondary)]">{subtitle}</p>
      ) : null}
      <div className={dense ? "mt-3" : "mt-4"}>{children}</div>
    </section>
  );
}

export function CardSkeleton({ height = 220 }: { height?: number }) {
  return (
    <div
      className="animate-pulse rounded-lg bg-[var(--gridline)]/50"
      style={{ height }}
    />
  );
}

export function ErrorNote({ message }: { message: string }) {
  return (
    <div className="rounded-md border border-[var(--status-critical)]/30 bg-[var(--status-critical)]/10 px-3 py-2 text-sm text-[var(--status-critical)]">
      {message}
    </div>
  );
}
