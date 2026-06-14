import logging
import os
from contextlib import asynccontextmanager

import asyncpg
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from core.secrets import load_secrets, get_config
from routers import biometrics, recommendations, workout

logger = logging.getLogger(__name__)

PROJECT_ID = os.getenv("GCP_PROJECT_ID", "project-6ce813b2-674a-4d31-aad")


async def _create_pg_pool() -> asyncpg.Pool | None:
    """
    Create an asyncpg connection pool using the DSN from secrets.
    Returns None if unavailable — the recommendations agent falls back
    to BigQuery when the pool is None.
    """
    dsn = get_config().cloud_sql_dsn
    if not dsn:
        logger.warning("CLOUD_SQL_DSN not set — pgvector semantic search disabled")
        return None
    try:
        pool = await asyncpg.create_pool(dsn=dsn, min_size=2, max_size=10)
        logger.info("pgvector pool initialised (min=2 max=10)")
        return pool
    except Exception:
        logger.exception("pgvector pool init failed — semantic search disabled")
        return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    await load_secrets(PROJECT_ID)
    pool = await _create_pg_pool()
    recommendations.set_pg_pool(pool)
    yield
    if pool:
        await pool.close()
        logger.info("pgvector pool closed")


app = FastAPI(title="FitRx API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(workout.router,         prefix="/workout",         tags=["Workout"])
app.include_router(biometrics.router,      prefix="/biometrics",      tags=["Biometrics"])
app.include_router(recommendations.router, prefix="/recommendations",  tags=["Recommendations"])


@app.get("/health")
def health_check():
    return {"status": "ok"}
