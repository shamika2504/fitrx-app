from fastapi import APIRouter, HTTPException
from google.cloud import bigquery
from google.cloud import firestore
import os

router = APIRouter()
bq_client = bigquery.Client(project=os.getenv("GCP_PROJECT_ID"))
db = firestore.Client(project=os.getenv("GCP_PROJECT_ID"))

@router.get("/{participant_id}")
def get_recommendations(participant_id: int):
    docs = db.collection("recommendations") \
              .where("participant_id", "==", participant_id) \
              .order_by("created_at", direction=firestore.Query.DESCENDING) \
              .limit(5) \
              .stream()
    results = [doc.to_dict() for doc in docs]
    if not results:
        raise HTTPException(status_code=404, detail="No recommendations found for this user")
    return results


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
