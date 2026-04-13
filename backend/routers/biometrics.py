from fastapi import APIRouter
from google.cloud import bigquery
import os

router = APIRouter()
client = bigquery.Client(project=os.getenv("GCP_PROJECT_ID"))

@router.get("/overview/{participant_id}")
def get_biometrics_overview(participant_id: int):
    query = """
        SELECT
            date,
            weight_kg,
            bmi,
            resting_heart_rate,
            hours_sleep,
            stress_level,
            hydration_level,
            fitness_level
        FROM `fitrx_warehouse.fact_biometrics`
        WHERE participant_id = @participant_id
        ORDER BY date DESC
        LIMIT 30
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("participant_id", "INT64", participant_id)
        ]
    )
    results = client.query(query, job_config=job_config).result()
    return [dict(row) for row in results]


@router.get("/sleep-impact/{participant_id}")
def get_sleep_impact(participant_id: int):
    query = """
        SELECT
            b.hours_sleep,
            ROUND(AVG(w.calories_burned), 2) as avg_calories_burned
        FROM `fitrx_warehouse.fact_biometrics` b
        JOIN `fitrx_warehouse.fact_workout_logs` w
            ON b.participant_id = w.participant_id AND b.date = w.date
        WHERE b.participant_id = @participant_id
        GROUP BY b.hours_sleep
        ORDER BY b.hours_sleep ASC
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("participant_id", "INT64", participant_id)
        ]
    )
    results = client.query(query, job_config=job_config).result()
    return [dict(row) for row in results]
