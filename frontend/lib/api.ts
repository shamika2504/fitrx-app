const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ??
  "https://fitrx-backend-434489845366.us-central1.run.app";

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`${path} → HTTP ${res.status} ${body}`.trim());
  }
  return res.json() as Promise<T>;
}

export interface WorkoutSummaryRow {
  activity_type: string;
  total_sessions: number;
  avg_calories: number;
  avg_duration: number;
  avg_heart_rate: number;
}

export interface CalorieTrendRow {
  date: string;
  calories_burned: number;
  activity_type: string;
  duration_minutes: number;
}

export interface BiometricsOverviewRow {
  date: string;
  weight_kg: number;
  bmi: number;
  resting_heart_rate: number;
  hours_sleep: number;
  stress_level: number;
  hydration_level: number;
  fitness_level: number;
}

export interface SleepImpactRow {
  hours_sleep: number;
  avg_calories_burned: number;
}

export interface RecommendationResponse {
  participant_id: number;
  metrics: Record<string, unknown>;
  recommendation: string;
  tools_called: string[];
  latency_ms: number;
}

export interface MonitoringStats {
  total_inferences: number;
  avg_latency_ms: number;
  tools_called_distribution: Record<string, number>;
  avg_recommendation_length: number;
  last_24h_inferences: number;
  last_updated: string;
}

export const api = {
  base: API_BASE,
  workoutSummary: (id: number) =>
    getJSON<WorkoutSummaryRow[]>(`/workout/summary/${id}`),
  calorieTrend: (id: number) =>
    getJSON<CalorieTrendRow[]>(`/workout/trend/${id}`),
  biometricsOverview: (id: number) =>
    getJSON<BiometricsOverviewRow[]>(`/biometrics/overview/${id}`),
  sleepImpact: (id: number) =>
    getJSON<SleepImpactRow[]>(`/biometrics/sleep-impact/${id}`),
  recommendation: (id: number, question?: string) =>
    getJSON<RecommendationResponse>(
      `/recommendations/${id}${question ? `?question=${encodeURIComponent(question)}` : ""}`,
    ),
  monitoringStats: () => getJSON<MonitoringStats>(`/monitoring/stats`),
};
