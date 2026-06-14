import asyncio
import json
import logging
import os
import time
from datetime import datetime, timezone

import asyncpg
from fastapi import APIRouter, HTTPException
from google.cloud import bigquery
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool
from langchain_google_vertexai import ChatVertexAI

from services.embedding_service import (
    retrieve_similar_recommendations,
    store_recommendation_embedding,
)

router = APIRouter()
logger = logging.getLogger(__name__)

PROJECT_ID = os.getenv("GCP_PROJECT_ID")
DATASET = "fitrx_warehouse"
TUNED_MODEL_ENDPOINT = (
    "projects/434489845366/locations/us-central1/endpoints/988584648428748800"
)

bq_client = bigquery.Client(project=PROJECT_ID)

llm = ChatVertexAI(
    model=TUNED_MODEL_ENDPOINT,
    project=PROJECT_ID,
    location="us-central1",
)

SYSTEM_PROMPT = (
    "You are FitRx, an expert personal fitness coach with access to real user data. "
    "Before giving advice, always call get_user_workout_history to understand recent "
    "training patterns, and call get_cached_recommendations to avoid repeating advice "
    "already given. Reference the user's actual numbers. "
    "Be specific, actionable, and motivating. Keep the response under 300 words."
)

# Pool is injected at startup by main.py lifespan via set_pg_pool()
_pg_pool: asyncpg.Pool | None = None


def set_pg_pool(pool: asyncpg.Pool | None) -> None:
    global _pg_pool
    _pg_pool = pool


# ── Tools ──────────────────────────────────────────────────────────────────────

@tool
async def get_user_workout_history(user_id: int, lookback_days: int = 30) -> str:
    """Fetch the user's recent workout sessions from BigQuery.

    Args:
        user_id: The participant ID to query.
        lookback_days: How many days of history to return (default 30).

    Returns:
        JSON with total_sessions and a list of workout records.
    """
    query = """
        SELECT
            CAST(date AS STRING)          AS date,
            activity_type,
            duration_minutes,
            intensity,
            ROUND(calories_burned, 2)     AS calories_burned,
            avg_heart_rate
        FROM `fitrx_warehouse.fact_workout_logs`
        WHERE participant_id = @user_id
          AND date >= DATE_SUB(CURRENT_DATE(), INTERVAL @lookback_days DAY)
        ORDER BY date DESC
        LIMIT 50
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("user_id", "INT64", user_id),
            bigquery.ScalarQueryParameter("lookback_days", "INT64", lookback_days),
        ]
    )
    rows = await asyncio.to_thread(
        lambda: list(bq_client.query(query, job_config=job_config).result())
    )
    workouts = [dict(r) for r in rows]
    logger.info(
        "tool=get_user_workout_history user_id=%s days=%s rows=%d",
        user_id, lookback_days, len(workouts),
    )
    return json.dumps(
        {"total_sessions": len(workouts), "workouts": workouts}, default=str
    )


@tool
async def get_cached_recommendations(user_id: int, query_context: str = "") -> str:
    """Retrieve the user's past AI coaching recommendations.

    Attempts pgvector cosine-similarity search first (semantic).
    Falls back to latest 5 rows from BigQuery if Cloud SQL is
    unavailable or returns no results.

    Args:
        user_id: The participant ID.
        query_context: Optional text to use as the semantic query.
            If empty, the fallback path is used directly.

    Returns:
        JSON with a 'source' field ('semantic' or 'fallback') and
        a 'results' list of past recommendation records.
    """
    # ── Semantic path ──────────────────────────────────────────
    if _pg_pool is not None and query_context.strip():
        try:
            results = await retrieve_similar_recommendations(
                _pg_pool, user_id, query_context, top_k=5
            )
            if results:
                logger.info(
                    "tool=get_cached_recommendations source=semantic user_id=%s results=%d",
                    user_id, len(results),
                )
                return json.dumps({"source": "semantic", "results": results}, default=str)
        except Exception as exc:
            logger.warning(
                "semantic_retrieval failed user_id=%s — falling back to BQ: %s",
                user_id, exc,
            )

    # ── BigQuery fallback ──────────────────────────────────────
    query = """
        SELECT
            CAST(generated_at AS STRING)  AS generated_at,
            activity_type,
            recommendation,
            stress_level,
            hours_sleep
        FROM `fitrx_warehouse.fact_recommendations`
        WHERE participant_id = @user_id
        ORDER BY generated_at DESC
        LIMIT 5
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("user_id", "INT64", user_id),
        ]
    )
    rows = await asyncio.to_thread(
        lambda: list(bq_client.query(query, job_config=job_config).result())
    )
    past = [dict(r) for r in rows]
    logger.info(
        "tool=get_cached_recommendations source=fallback user_id=%s rows=%d",
        user_id, len(past),
    )
    return json.dumps({"source": "fallback", "results": past}, default=str)


# ── Agent setup ────────────────────────────────────────────────────────────────

_tools = [get_user_workout_history, get_cached_recommendations]

_prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    ("human", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])

_agent = create_tool_calling_agent(llm, _tools, _prompt)

_executor = AgentExecutor(
    agent=_agent,
    tools=_tools,
    max_iterations=3,
    handle_parsing_errors=True,
    verbose=True,
    return_intermediate_steps=True,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _fetch_latest_session(participant_id: int) -> dict | None:
    query = """
        SELECT
            w.activity_type, w.calories_burned, w.duration_minutes,
            w.avg_heart_rate, w.intensity,
            b.hours_sleep, b.stress_level, b.bmi,
            b.fitness_level, b.resting_heart_rate
        FROM `fitrx_warehouse.fact_workout_logs` w
        JOIN `fitrx_warehouse.fact_biometrics` b
            ON w.participant_id = b.participant_id AND w.date = b.date
        WHERE w.participant_id = @participant_id
        ORDER BY w.date DESC
        LIMIT 1
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("participant_id", "INT64", participant_id)
        ]
    )
    rows = list(bq_client.query(query, job_config=job_config).result())
    return dict(rows[0]) if rows else None


def _extract_tool_calls(intermediate_steps: list) -> list[dict]:
    return [
        {
            "tool": action.tool,
            "input": action.tool_input,
            "output_preview": str(observation)[:300],
        }
        for action, observation in intermediate_steps
    ]


async def _log_agent_run(
    participant_id: int,
    metrics: dict | None,
    question: str,
    tool_calls: list[dict],
    final_response: str,
    latency_ms: float,
) -> None:
    def _f(v):
        return float(v) if v is not None else None

    def _i(v):
        return int(v) if v is not None else None

    row = {
        "participant_id": participant_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "activity_type": metrics.get("activity_type") if metrics else None,
        "calories_burned": _f(metrics.get("calories_burned")) if metrics else None,
        "duration_minutes": _f(metrics.get("duration_minutes")) if metrics else None,
        "avg_heart_rate": _f(metrics.get("avg_heart_rate")) if metrics else None,
        "intensity": metrics.get("intensity") if metrics else None,
        "hours_sleep": _f(metrics.get("hours_sleep")) if metrics else None,
        "stress_level": _i(metrics.get("stress_level")) if metrics else None,
        "bmi": _f(metrics.get("bmi")) if metrics else None,
        "fitness_level": _f(metrics.get("fitness_level")) if metrics else None,
        "resting_heart_rate": _f(metrics.get("resting_heart_rate")) if metrics else None,
        "prompt": question,
        "recommendation": final_response,
        "model_endpoint": TUNED_MODEL_ENDPOINT,
        "tool_calls_made": json.dumps(tool_calls),
        "latency_ms": round(latency_ms, 2),
    }
    errors = await asyncio.to_thread(
        lambda: bq_client.insert_rows_json(
            f"{bq_client.project}.{DATASET}.fact_recommendations", [row]
        )
    )
    if errors:
        logger.error("bq_insert_errors: %s", errors)

    # Grow the semantic index — store new recommendation embedding if pool is up
    if _pg_pool is not None:
        try:
            await store_recommendation_embedding(
                _pg_pool, participant_id, final_response
            )
        except Exception as exc:
            logger.warning("embedding_store failed (non-fatal): %s", exc)


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.get("/{participant_id}")
async def get_recommendations(
    participant_id: int,
    question: str = "Based on my recent workouts and health metrics, what should I focus on?",
):
    start = time.monotonic()
    logger.info(
        "agent_run=start participant_id=%s question=%r pg_pool=%s",
        participant_id, question, "up" if _pg_pool else "down",
    )

    metrics = await asyncio.to_thread(lambda: _fetch_latest_session(participant_id))
    if not metrics:
        raise HTTPException(status_code=404, detail="No session data found")

    user_input = f"My participant_id is {participant_id}. {question}"

    try:
        result = await _executor.ainvoke({"input": user_input})
    except Exception as exc:
        logger.exception("agent_run=failed participant_id=%s", participant_id)
        raise HTTPException(status_code=500, detail=f"Agent error: {exc}")

    latency_ms = (time.monotonic() - start) * 1000
    final_response = result.get("output", "")
    tool_calls = _extract_tool_calls(result.get("intermediate_steps", []))

    logger.info(
        "agent_run=complete participant_id=%s tools=%s latency_ms=%.0f",
        participant_id, [t["tool"] for t in tool_calls], latency_ms,
    )

    asyncio.create_task(
        _log_agent_run(
            participant_id, metrics, user_input,
            tool_calls, final_response, latency_ms,
        )
    )

    return {
        "participant_id": participant_id,
        "metrics": metrics,
        "recommendation": final_response,
        "tools_called": [t["tool"] for t in tool_calls],
        "latency_ms": round(latency_ms),
    }


@router.get("/latest-metrics/{participant_id}")
async def get_latest_metrics(participant_id: int):
    query = """
        SELECT
            w.activity_type,
            ROUND(AVG(w.calories_burned), 2)   AS avg_calories,
            ROUND(AVG(b.hours_sleep), 2)        AS avg_sleep,
            ROUND(AVG(b.stress_level), 2)       AS avg_stress,
            ROUND(AVG(b.resting_heart_rate), 2) AS avg_resting_hr
        FROM `fitrx_warehouse.fact_workout_logs` w
        JOIN `fitrx_warehouse.fact_biometrics` b
            ON w.participant_id = b.participant_id AND w.date = b.date
        WHERE w.participant_id = @participant_id
          AND w.date >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
        GROUP BY w.activity_type
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("participant_id", "INT64", participant_id)
        ]
    )
    results = await asyncio.to_thread(
        lambda: list(bq_client.query(query, job_config=job_config).result())
    )
    return [dict(row) for row in results]
