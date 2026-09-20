import { Card } from "@/components/Card";

const DIMENSIONS = [
  { label: "Relevance", delta: "+7.2%" },
  { label: "Personalization", delta: "+7.1%" },
  { label: "Actionability", delta: "+6.8%" },
  { label: "Criteria coverage", delta: "+6.5%" },
];

export function ModelPerformance() {
  return (
    <Card
      dense
      title="Model performance"
      subtitle="Fine-tuned vs. base Gemini, blind-judged on 30 held-out scenarios"
    >
      <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
        <div>
          <span className="text-2xl font-semibold text-[var(--status-good)]">
            +6.9%
          </span>
          <span className="ml-2 text-xs text-[var(--text-muted)]">
            overall (3.89 vs 3.64)
          </span>
        </div>
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-[var(--text-secondary)]">
          {DIMENSIONS.map((d) => (
            <span key={d.label}>
              {d.label} <span className="text-[var(--status-good)]">{d.delta}</span>
            </span>
          ))}
        </div>
      </div>
    </Card>
  );
}
