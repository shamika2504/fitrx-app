"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { useAsync } from "@/lib/useAsync";
import { Card, CardSkeleton, ErrorNote } from "@/components/Card";
import { StatTile } from "@/components/StatTile";
import { BarChart } from "@/components/BarChart";
import { LineChart } from "@/components/LineChart";
import { ModelPerformance } from "@/components/ModelPerformance";
import { bucketByHoursSleep } from "@/lib/chart-utils";

const DEFAULT_QUESTION =
  "Based on my recent workouts and health metrics, what should I focus on?";

const SUGGESTED_PROMPTS = [
  "What should I focus on this week?",
  "Is my recovery on track?",
  "How does my sleep affect my performance?",
  "Am I overtraining?",
];

export default function Home() {
  const [participantId, setParticipantId] = useState(1);
  const [inputValue, setInputValue] = useState("1");
  const [question, setQuestion] = useState(DEFAULT_QUESTION);
  const [askedQuestion, setAskedQuestion] = useState(DEFAULT_QUESTION);

  function loadParticipant(id: number) {
    setInputValue(String(id));
    setParticipantId(id);
  }

  function askPrompt(prompt: string) {
    setQuestion(prompt);
    setAskedQuestion(prompt);
  }

  const summary = useAsync(
    () => api.workoutSummary(participantId),
    [participantId],
  );
  const trend = useAsync(
    () => api.calorieTrend(participantId),
    [participantId],
  );
  const biometrics = useAsync(
    () => api.biometricsOverview(participantId),
    [participantId],
  );
  const sleepImpact = useAsync(
    () => api.sleepImpact(participantId),
    [participantId],
  );
  const recommendation = useAsync(
    () => api.recommendation(participantId, askedQuestion),
    [participantId, askedQuestion],
  );
  const monitoring = useAsync(() => api.monitoringStats(), []);

  const latest = biometrics.data?.[0];

  return (
    <div className="mx-auto max-w-5xl px-6 py-10">
      <header className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-[var(--text-primary)]">
            FitRx
          </h1>
          <p className="mt-1 text-sm text-[var(--text-secondary)]">
            AI fitness coach — agentic recommendations grounded in real workout
            and biometric data
          </p>
        </div>
        <div className="flex flex-col items-end gap-1">
          <form
            className="flex items-center gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              const n = parseInt(inputValue, 10);
              if (!Number.isNaN(n) && n > 0) setParticipantId(n);
            }}
          >
            <label className="text-xs text-[var(--text-muted)]" htmlFor="pid">
              Participant ID
            </label>
            <input
              id="pid"
              className="w-20 rounded-md border border-[var(--border)] bg-[var(--surface)] px-2 py-1 text-sm text-[var(--text-primary)]"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              inputMode="numeric"
              placeholder="1-3000"
            />
            <button
              type="submit"
              className="rounded-md bg-[var(--series-1)] px-3 py-1 text-sm font-medium text-white"
            >
              Load
            </button>
            <button
              type="button"
              onClick={() => loadParticipant(1)}
              className="rounded-md border border-[var(--border)] px-3 py-1 text-sm font-medium text-[var(--text-primary)]"
            >
              Try demo
            </button>
          </form>
          <p className="text-xs text-[var(--text-muted)]">
            Any ID from 1-3000 works — try a few to see different profiles
          </p>
        </div>
      </header>

      <div className="grid gap-6">
        <ModelPerformance />

        <Card
          accent
          title="AI recommendation"
          subtitle="Agent calls real tools (BigQuery + semantic search) before responding"
        >
          <form
            className="mb-2 flex flex-wrap gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              setAskedQuestion(question);
            }}
          >
            <input
              className="min-w-0 flex-1 rounded-md border border-[var(--border)] bg-[var(--page)] px-3 py-2 text-sm text-[var(--text-primary)]"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
            />
            <button
              type="submit"
              className="rounded-md border border-[var(--border)] px-3 py-2 text-sm font-medium text-[var(--text-primary)]"
            >
              Ask
            </button>
          </form>

          <div className="mb-4 flex flex-wrap gap-2">
            {SUGGESTED_PROMPTS.map((p) => (
              <button
                key={p}
                type="button"
                onClick={() => askPrompt(p)}
                className="rounded-full border border-[var(--border)] px-3 py-1 text-xs text-[var(--text-secondary)] hover:border-[var(--series-1)] hover:text-[var(--text-primary)]"
              >
                {p}
              </button>
            ))}
          </div>

          {recommendation.loading && (
            <div className="flex items-center gap-2 text-sm text-[var(--text-secondary)]">
              <span className="h-3 w-3 animate-spin rounded-full border-2 border-[var(--series-1)] border-t-transparent" />
              Agent is running two sequential tool calls (BigQuery + semantic
              search) before the model reasons over the result — typically
              5-10s end to end.
            </div>
          )}
          {recommendation.error && (
            <ErrorNote message={recommendation.error} />
          )}
          {recommendation.data && (
            <div>
              <p className="whitespace-pre-wrap text-sm leading-relaxed text-[var(--text-primary)]">
                {recommendation.data.recommendation}
              </p>
              <div className="mt-4 flex flex-wrap items-center gap-2 text-xs text-[var(--text-muted)]">
                <span>{recommendation.data.latency_ms}ms</span>
                {recommendation.data.tools_called.map((t) => (
                  <span
                    key={t}
                    className="rounded-full border border-[var(--border)] px-2 py-0.5"
                  >
                    {t}
                  </span>
                ))}
              </div>
            </div>
          )}
        </Card>

        <div className="grid gap-6 md:grid-cols-2">
          <Card
            title="Avg calories by activity"
            subtitle="Relative index, dataset units (not literal kcal)"
          >
            {summary.loading && <CardSkeleton />}
            {summary.error && <ErrorNote message={summary.error} />}
            {summary.data && (
              <BarChart
                data={summary.data.map((r) => ({
                  label: r.activity_type,
                  value: r.avg_calories,
                }))}
              />
            )}
          </Card>

          <Card title="Calorie trend" subtitle="Per-session index over time">
            {trend.loading && <CardSkeleton />}
            {trend.error && <ErrorNote message={trend.error} />}
            {trend.data && (
              <LineChart
                data={trend.data.map((r) => ({
                  x: r.date,
                  value: r.calories_burned,
                }))}
              />
            )}
          </Card>
        </div>

        <Card title="Latest biometrics" subtitle="Most recent recorded session">
          {biometrics.loading && <CardSkeleton height={80} />}
          {biometrics.error && <ErrorNote message={biometrics.error} />}
          {latest && (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <StatTile label="Weight" value={`${latest.weight_kg} kg`} />
              <StatTile label="BMI" value={`${latest.bmi}`} />
              <StatTile
                label="Resting HR"
                value={`${latest.resting_heart_rate} bpm`}
              />
              <StatTile label="Sleep" value={`${latest.hours_sleep} hrs`} />
              <StatTile label="Stress" value={`${latest.stress_level}/10`} />
              <StatTile
                label="Hydration"
                value={`${latest.hydration_level}L`}
                sub="typical range 1.5-3.5L"
              />
              <StatTile
                label="Fitness score"
                value={`${latest.fitness_level}`}
                sub="dataset scale, 0-22"
              />
              <StatTile label="Date" value={latest.date} />
            </div>
          )}
        </Card>

        <Card
          title="Sleep vs. calorie burn"
          subtitle="Calorie-burn index grouped by sleep-duration band"
        >
          {sleepImpact.loading && <CardSkeleton />}
          {sleepImpact.error && <ErrorNote message={sleepImpact.error} />}
          {sleepImpact.data && (
            <BarChart data={bucketByHoursSleep(sleepImpact.data)} />
          )}
        </Card>

        <Card
          dense
          title="Model monitoring (technical)"
          subtitle="Live inference volume, latency, and tool usage across all participants"
        >
          {monitoring.loading && <CardSkeleton height={120} />}
          {monitoring.error && <ErrorNote message={monitoring.error} />}
          {monitoring.data && (
            <div className="grid gap-4">
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                <StatTile
                  compact
                  label="Total inferences"
                  value={`${monitoring.data.total_inferences}`}
                />
                <StatTile
                  compact
                  label="Avg latency"
                  value={`${monitoring.data.avg_latency_ms}ms`}
                />
                <StatTile
                  compact
                  label="Last 24h"
                  value={`${monitoring.data.last_24h_inferences}`}
                />
                <StatTile
                  compact
                  label="Avg response length"
                  value={`${monitoring.data.avg_recommendation_length}`}
                  sub="characters"
                />
              </div>
              {Object.keys(monitoring.data.tools_called_distribution).length >
                0 && (
                <div>
                  <p className="mb-2 text-xs text-[var(--text-muted)]">
                    Tool call distribution
                  </p>
                  <BarChart
                    data={Object.entries(
                      monitoring.data.tools_called_distribution,
                    ).map(([label, value]) => ({ label, value }))}
                  />
                </div>
              )}
            </div>
          )}
        </Card>
      </div>

      <footer className="mt-10 text-center text-xs text-[var(--text-muted)]">
        Backend: {api.base}
      </footer>
    </div>
  );
}
