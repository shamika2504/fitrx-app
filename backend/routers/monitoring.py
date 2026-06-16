import asyncio
import os
from datetime import datetime, timezone

from fastapi import APIRouter
from google.cloud import bigquery

router = APIRouter()
bq_client = bigquery.Client(project=os.getenv("GCP_PROJECT_ID"))

_STATS_SQL = """
    SELECT
        COUNT(*)                                                        AS total_inferences,
        ROUND(AVG(latency_ms), 2)                                      AS avg_latency_ms,
        ROUND(AVG(LENGTH(recommendation)), 2)                          AS avg_recommendation_length,
        COUNTIF(
            generated_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
        )                                                              AS last_24h_inferences
    FROM `fitrx_warehouse.fact_recommendations`
"""

_TOOLS_SQL = """
    SELECT
        JSON_EXTRACT_SCALAR(tool_call, '$.tool') AS tool_name,
        COUNT(*)                                  AS call_count
    FROM `fitrx_warehouse.fact_recommendations`,
        UNNEST(JSON_EXTRACT_ARRAY(tool_calls_made)) AS tool_call
    WHERE tool_calls_made IS NOT NULL
      AND tool_calls_made != '[]'
    GROUP BY tool_name
"""


@router.get("/stats")
async def get_monitoring_stats():
    stats_rows, tools_rows = await asyncio.gather(
        asyncio.to_thread(lambda: list(bq_client.query(_STATS_SQL).result())),
        asyncio.to_thread(lambda: list(bq_client.query(_TOOLS_SQL).result())),
    )

    stats = dict(stats_rows[0]) if stats_rows else {}
    tools_dist = {
        row["tool_name"]: row["call_count"]
        for row in tools_rows
        if row["tool_name"]
    }

    return {
        "total_inferences": stats.get("total_inferences", 0),
        "avg_latency_ms": stats.get("avg_latency_ms", 0.0),
        "tools_called_distribution": tools_dist,
        "avg_recommendation_length": stats.get("avg_recommendation_length", 0.0),
        "last_24h_inferences": stats.get("last_24h_inferences", 0),
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }
