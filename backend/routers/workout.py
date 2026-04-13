from fastapi import APIRouter, HTTPException
from google.cloud import bigquery
import os

router = APIRouter()
client = bigquery.Client(project=os.getenv("GCP_PROJECT_ID"))

@router.get("/summary/{participant_id}")
def get_workout_summary(participant_id: int):
    query = """
        SELECT
            activity_type,
            COUNT(*) as total_sessions,
            ROUND(AVG(calories_burned), 2) as avg_calories,
            ROUND(AVG(duration_minutes), 2) as avg_duration,
            ROUND(AVG(avg_heart_rate), 2) as avg_heart_rate
        FROM `fitrx_warehouse.fact_workout_logs`
        WHERE participant_id = @participant_id
        GROUP BY activity_type
        ORDER BY total_sessions DESC
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("participant_id", "INT64", participant_id)
        ]
    )
    results = client.query(query, job_config=job_config).result()
    return [dict(row) for row in results]


@router.get("/trend/{participant_id}")
def get_calorie_trend(participant_id: int):
    query = """
        SELECT
            date,
            ROUND(AVG(calories_burned), 2) as calories_burned,
            activity_type,
            duration_minutes
        FROM `fitrx_warehouse.fact_workout_logs`
        WHERE participant_id = @participant_id
        ORDER BY date ASC
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("participant_id", "INT64", participant_id)
        ]
    )
    results = client.query(query, job_config=job_config).result()
    return [dict(row) for row in results]
