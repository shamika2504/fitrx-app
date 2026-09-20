export function niceTicks(max: number, count = 4): number[] {
  if (max <= 0) return [0];
  const rawStep = max / count;
  const magnitude = Math.pow(10, Math.floor(Math.log10(rawStep)));
  const residual = rawStep / magnitude;
  const niceResidual = residual >= 5 ? 10 : residual >= 2 ? 5 : residual >= 1 ? 2 : 1;
  const step = niceResidual * magnitude;
  const ticks: number[] = [];
  for (let v = 0; v <= max + step * 0.5; v += step) {
    ticks.push(Math.round(v * 100) / 100);
  }
  return ticks;
}

export function formatCompact(n: number): string {
  if (Math.abs(n) >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (Math.abs(n) >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return Number.isInteger(n) ? `${n}` : n.toFixed(1);
}

/**
 * The sleep-impact endpoint groups by exact float hours_sleep, which
 * produces dozens of near-duplicate buckets. Re-bucket into readable
 * sleep-duration bands for display. This averages the endpoint's
 * per-exact-value averages rather than the underlying rows, so it's an
 * approximation, not a weighted mean.
 */
export function bucketByHoursSleep<T extends { hours_sleep: number; avg_calories_burned: number }>(
  rows: T[],
): { label: string; value: number }[] {
  const bands: { label: string; min: number; max: number }[] = [
    { label: "<6h", min: -Infinity, max: 6 },
    { label: "6-7h", min: 6, max: 7 },
    { label: "7-8h", min: 7, max: 8 },
    { label: "8-9h", min: 8, max: 9 },
    { label: "9h+", min: 9, max: Infinity },
  ];
  return bands
    .map((band) => {
      const inBand = rows.filter(
        (r) => r.hours_sleep >= band.min && r.hours_sleep < band.max,
      );
      if (inBand.length === 0) return null;
      const avg =
        inBand.reduce((sum, r) => sum + r.avg_calories_burned, 0) /
        inBand.length;
      return { label: band.label, value: Math.round(avg * 10) / 10 };
    })
    .filter((b): b is { label: string; value: number } => b !== null);
}
