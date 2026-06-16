#!/usr/bin/env python3
"""
FitRx Vertex AI Model Monitoring Setup

Step 1 — Enables prediction request/response logging on the fine-tuned endpoint.
          Raw payloads land in BigQuery: fitrx_monitoring.endpoint_prediction_logs

Step 2 — Creates the fitrx_monitoring BigQuery dataset.

Step 3 — Runs a drift check comparing the last 7 days against a 30-day baseline
          using fact_recommendations. Flags metrics that exceed the drift threshold.

Note: Vertex AI Model Monitoring's built-in skew/drift is designed for tabular
models. For generative AI fine-tuned endpoints, GCP's recommended pattern is:
endpoint prediction logging → BigQuery → scheduled drift queries (this script).

Usage:
    cd FitRx
    export GCP_PROJECT_ID=project-6ce813b2-674a-4d31-aad
    python monitoring/setup_monitoring.py
"""

import os
import sys
from datetime import datetime, timezone

from google.cloud import bigquery
from google.cloud.aiplatform_v1 import EndpointServiceClient
from google.cloud.aiplatform_v1.types import (
    Endpoint as EndpointProto,
    PredictRequestResponseLoggingConfig,
    BigQueryDestination,
)
from google.protobuf import field_mask_pb2

# ── Config ─────────────────────────────────────────────────────────────────────

PROJECT_ID        = os.getenv("GCP_PROJECT_ID", "project-6ce813b2-674a-4d31-aad")
LOCATION          = "us-central1"
ENDPOINT_ID       = "988584648428748800"
ENDPOINT_NAME     = f"projects/{PROJECT_ID}/locations/{LOCATION}/endpoints/{ENDPOINT_ID}"
MONITORING_DATASET       = "fitrx_monitoring"
PREDICTION_LOGS_TABLE    = "endpoint_prediction_logs"
SOURCE_TABLE      = f"`{PROJECT_ID}.fitrx_warehouse.fact_recommendations`"
DRIFT_THRESHOLD   = 0.3   # normalized z-score; 0.3 ≈ 30% deviation from baseline

# ── Step 1: Enable endpoint prediction logging ─────────────────────────────────

def enable_prediction_logging() -> None:
    """Stream every request/response payload to BigQuery."""
    print(f"[1/3] Enabling prediction logging on endpoint {ENDPOINT_ID} ...")

    client = EndpointServiceClient(
        client_options={"api_endpoint": f"{LOCATION}-aiplatform.googleapis.com"}
    )

    logging_config = PredictRequestResponseLoggingConfig(
        enabled=True,
        sampling_rate=1.0,
        bigquery_destination=BigQueryDestination(
            output_uri=(
                f"bq://{PROJECT_ID}.{MONITORING_DATASET}.{PREDICTION_LOGS_TABLE}"
            )
        ),
    )

    endpoint = EndpointProto(
        name=ENDPOINT_NAME,
        predict_request_response_logging_config=logging_config,
    )

    client.update_endpoint(
        endpoint=endpoint,
        update_mask=field_mask_pb2.FieldMask(
            paths=["predict_request_response_logging_config"]
        ),
    )
    print(
        f"    Logging enabled → "
        f"bq://{PROJECT_ID}.{MONITORING_DATASET}.{PREDICTION_LOGS_TABLE}"
    )


# ── Step 2: Create monitoring dataset ─────────────────────────────────────────

def create_monitoring_dataset() -> None:
    print(f"[2/3] Creating BigQuery dataset {MONITORING_DATASET} ...")
    bq = bigquery.Client(project=PROJECT_ID)
    ds = bigquery.Dataset(f"{PROJECT_ID}.{MONITORING_DATASET}")
    ds.location = "US"
    bq.create_dataset(ds, exists_ok=True)
    print(f"    Dataset ready: {PROJECT_ID}.{MONITORING_DATASET}")


# ── Step 3: Drift check queries ────────────────────────────────────────────────

_METRIC_DRIFT_SQL = f"""
WITH baseline AS (
    SELECT
        AVG(LENGTH(prompt))            AS avg_input_len,
        STDDEV(LENGTH(prompt))         AS std_input_len,
        AVG(LENGTH(recommendation))    AS avg_output_len,
        STDDEV(LENGTH(recommendation)) AS std_output_len,
        AVG(latency_ms)                AS avg_latency_ms,
        STDDEV(latency_ms)             AS std_latency_ms
    FROM {SOURCE_TABLE}
    WHERE generated_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
      AND generated_at <  TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7  DAY)
),
recent AS (
    SELECT
        AVG(LENGTH(prompt))         AS avg_input_len,
        AVG(LENGTH(recommendation)) AS avg_output_len,
        AVG(latency_ms)             AS avg_latency_ms,
        COUNT(*)                    AS inference_count
    FROM {SOURCE_TABLE}
    WHERE generated_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
)
SELECT
    r.inference_count,
    ROUND(r.avg_input_len,  1) AS recent_input_len,
    ROUND(r.avg_output_len, 1) AS recent_output_len,
    ROUND(r.avg_latency_ms, 1) AS recent_latency_ms,
    ROUND(b.avg_input_len,  1) AS baseline_input_len,
    ROUND(b.avg_output_len, 1) AS baseline_output_len,
    ROUND(b.avg_latency_ms, 1) AS baseline_latency_ms,
    ROUND(SAFE_DIVIDE(ABS(r.avg_input_len  - b.avg_input_len),  NULLIF(b.std_input_len,  0)), 3) AS input_drift_score,
    ROUND(SAFE_DIVIDE(ABS(r.avg_output_len - b.avg_output_len), NULLIF(b.std_output_len, 0)), 3) AS output_drift_score,
    ROUND(SAFE_DIVIDE(ABS(r.avg_latency_ms - b.avg_latency_ms), NULLIF(b.std_latency_ms, 0)), 3) AS latency_drift_score
FROM recent r, baseline b
"""

_TOOLS_DRIFT_SQL = f"""
WITH baseline AS (
    SELECT JSON_EXTRACT_SCALAR(t, '$.tool') AS tool_name, COUNT(*) AS cnt
    FROM {SOURCE_TABLE},
        UNNEST(JSON_EXTRACT_ARRAY(tool_calls_made)) AS t
    WHERE generated_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
      AND generated_at <  TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7  DAY)
    GROUP BY tool_name
),
recent AS (
    SELECT JSON_EXTRACT_SCALAR(t, '$.tool') AS tool_name, COUNT(*) AS cnt
    FROM {SOURCE_TABLE},
        UNNEST(JSON_EXTRACT_ARRAY(tool_calls_made)) AS t
    WHERE generated_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)
    GROUP BY tool_name
)
SELECT
    COALESCE(r.tool_name, b.tool_name)          AS tool_name,
    COALESCE(r.cnt, 0)                           AS recent_count,
    COALESCE(b.cnt, 0)                           AS baseline_count,
    ROUND(SAFE_DIVIDE(
        ABS(COALESCE(r.cnt, 0) - COALESCE(b.cnt, 0)),
        NULLIF(COALESCE(b.cnt, 0), 0)
    ), 3)                                        AS relative_change
FROM recent r FULL OUTER JOIN baseline b USING (tool_name)
ORDER BY tool_name
"""


def run_drift_check() -> list[str]:
    """Returns list of alert strings; empty list = all clear."""
    print(f"[3/3] Running drift check (threshold = {DRIFT_THRESHOLD}) ...")
    bq     = bigquery.Client(project=PROJECT_ID)
    alerts = []

    # ── Distribution metrics ──────────────────────────────────────────────────
    rows = list(bq.query(_METRIC_DRIFT_SQL).result())
    if not rows:
        print("    No data in fact_recommendations yet — skipping.")
        return alerts

    r = dict(rows[0])
    print(f"\n    Inferences (last 7 days): {r['inference_count']}")
    print(f"\n    {'Metric':<28} {'Recent':>10} {'Baseline':>10} {'Score':>8}  Status")
    print(f"    {'-'*68}")

    checks = [
        ("Input length  (chars)", "recent_input_len",  "baseline_input_len",  "input_drift_score"),
        ("Output length (chars)", "recent_output_len", "baseline_output_len", "output_drift_score"),
        ("Latency       (ms)",    "recent_latency_ms", "baseline_latency_ms", "latency_drift_score"),
    ]
    for label, rk, bk, dk in checks:
        score  = r.get(dk) or 0.0
        status = "ALERT ⚠" if score > DRIFT_THRESHOLD else "OK ✓"
        print(
            f"    {label:<28} {str(r.get(rk,'N/A')):>10} "
            f"{str(r.get(bk,'N/A')):>10} {score:>8.3f}  {status}"
        )
        if score > DRIFT_THRESHOLD:
            alerts.append(f"{label.strip()} drift score {score:.3f} > {DRIFT_THRESHOLD}")

    # ── Tool usage distribution ───────────────────────────────────────────────
    print(f"\n    {'Tool':<38} {'Recent':>8} {'Baseline':>10} {'Change':>8}  Status")
    print(f"    {'-'*72}")
    for trow in bq.query(_TOOLS_DRIFT_SQL).result():
        t      = dict(trow)
        change = t.get("relative_change") or 0.0
        name   = t.get("tool_name") or "unknown"
        status = "ALERT ⚠" if change > DRIFT_THRESHOLD else "OK ✓"
        print(
            f"    {name:<38} {t.get('recent_count',0):>8} "
            f"{t.get('baseline_count',0):>10} {change:>8.2%}  {status}"
        )
        if change > DRIFT_THRESHOLD:
            alerts.append(f"Tool '{name}' usage shifted by {change:.0%}")

    return alerts


# ── Alert config summary ───────────────────────────────────────────────────────

def print_alert_config(alerts: list[str]) -> None:
    print("\n" + "=" * 62)
    if alerts:
        print(f"⚠  {len(alerts)} ALERT(S) DETECTED:")
        for a in alerts:
            print(f"   • {a}")
    else:
        print("✓  All metrics within threshold — no drift detected.")

    print(f"\nAlert configuration:")
    print(f"  Drift threshold  : {DRIFT_THRESHOLD} (normalized z-score)")
    print(f"  Comparison window: last 7 days vs days 8–30 baseline")
    print(f"  Monitoring signal: fitrx_warehouse.fact_recommendations")
    print(f"  Payload logs     : {MONITORING_DATASET}.{PREDICTION_LOGS_TABLE}")
    print(f"  Timestamp        : {datetime.now(timezone.utc).isoformat()}")

    print(f"\nTo schedule daily drift checks (Cloud Scheduler):")
    print(f"  gcloud scheduler jobs create http fitrx-drift-monitor \\")
    print(f"    --location=us-central1 \\")
    print(f"    --schedule='0 8 * * *' \\")
    print(f"    --uri=https://fitrx-backend-x4vxklwvvq-uc.a.run.app/monitoring/stats \\")
    print(f"    --time-zone=UTC")
    print("=" * 62)


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    try:
        create_monitoring_dataset()
        enable_prediction_logging()
        alerts = run_drift_check()
        print_alert_config(alerts)
        sys.exit(1 if alerts else 0)
    except Exception as exc:
        print(f"\nFATAL: {exc}", file=sys.stderr)
        sys.exit(1)
