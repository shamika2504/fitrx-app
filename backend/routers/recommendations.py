from fastapi import APIRouter, HTTPException
from google.cloud import bigquery
from google import genai
from google.genai import types
import os

router = APIRouter()
bq_client = bigquery.Client(project=os.getenv("GCP_PROJECT_ID"))

TUNED_MODEL_ENDPOINT = "projects/434489845366/locations/us-central1/endpoints/988584648428748800"
SYSTEM_PROMPT = (
    "You are FitRx, a personal fitness coach. "
    "Analyze the user's health and workout metrics and give specific, actionable advice. "
    "Always reference the user's actual numbers in your response."
)

genai_client = genai.Client(
    vertexai=True,
    project=os.getenv("GCP_PROJECT_ID"),
    location="us-central1",
)


def _fetch_latest_session(participant_id: int) -> dict | None:
    query = """
        SELECT
            w.activity_type,
            w.calories_burned,
            w.duration_minutes,
            w.avg_heart_rate,
            w.intensity,
            b.hours_sleep,
            b.stress_level,
            b.bmi,
            b.fitness_level,
            b.resting_heart_rate
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


def _build_prompt(m: dict) -> str:
    return (
        f"Here are my stats from today's session: I did {int(m['duration_minutes'])} minutes of "
        f"{m['activity_type']} at {m['intensity']} intensity, burned {float(m['calories_burned']):.1f} calories, "
        f"and my average heart rate was {int(m['avg_heart_rate'])} bpm. "
        f"I slept {float(m['hours_sleep']):.1f} hours last night, my stress level is {int(m['stress_level'])}/10, "
        f"and my BMI is {float(m['bmi']):.1f}. What should I focus on?"
    )


@router.get("/{participant_id}")
def get_recommendations(participant_id: int):
    metrics = _fetch_latest_session(participant_id)
    if not metrics:
        raise HTTPException(status_code=404, detail="No session data found for this participant")

    response = genai_client.models.generate_content(
        model=TUNED_MODEL_ENDPOINT,
        contents=_build_prompt(metrics),
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
        ),
    )

    return {
        "participant_id": participant_id,
        "metrics": metrics,
        "recommendation": response.text,
    }


@router.get("/latest-metrics/{participant_id}")
def get_latest_metrics(participant_id: int):
    query = """
        SELECT
            w.activity_type,
            ROUND(AVG(w.calories_burned), 2) as avg_calories,
            ROUND(AVG(b.hours_sleep), 2) as avg_sleep,
            ROUND(AVG(b.stress_level), 2) as avg_stress,
            ROUND(AVG(b.resting_heart_rate), 2) as avg_resting_hr
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
    results = bq_client.query(query, job_config=job_config).result()
    return [dict(row) for row in results]
