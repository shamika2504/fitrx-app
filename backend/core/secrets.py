"""
Secrets loader — fetches credentials from GCP Secret Manager with
os.environ fallback so the app still runs locally with a .env file.

Secret names in Secret Manager:
  fitrx-cloud-sql-dsn   → CLOUD_SQL_DSN
  fitrx-openai-api-key  → OPENAI_API_KEY

GCP_PROJECT_ID is not a secret; it must be set as a plain env var
(it is needed to bootstrap Secret Manager itself).
"""

import logging
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_SECRET_NAMES = {
    "cloud_sql_dsn": ("fitrx-cloud-sql-dsn", "CLOUD_SQL_DSN"),
    "openai_api_key": ("fitrx-openai-api-key", "OPENAI_API_KEY"),
}


@dataclass
class AppConfig:
    cloud_sql_dsn: str | None
    openai_api_key: str | None


_config: AppConfig | None = None


def get_config() -> AppConfig:
    if _config is None:
        raise RuntimeError("Secrets not initialised — call load_secrets() in app lifespan")
    return _config


async def _fetch_from_secret_manager(secret_id: str, project_id: str) -> str:
    from google.cloud import secretmanager_v1  # imported lazily — not needed locally

    client = secretmanager_v1.SecretManagerServiceAsyncClient()
    name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
    response = await client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")


async def _resolve(field: str, project_id: str) -> str | None:
    secret_id, env_var = _SECRET_NAMES[field]

    # Local dev: env var takes precedence
    val = os.getenv(env_var)
    if val:
        logger.debug("secret %s resolved from env var %s", field, env_var)
        return val

    # Production: fetch from Secret Manager
    try:
        val = await _fetch_from_secret_manager(secret_id, project_id)
        logger.info("secret %s resolved from Secret Manager", field)
        return val
    except Exception as exc:
        logger.warning("could not fetch secret %s from Secret Manager: %s", field, exc)
        return None


async def load_secrets(project_id: str) -> AppConfig:
    """
    Fetch all application secrets and cache them in the module-level
    _config singleton. Called once at app startup inside the lifespan.
    """
    global _config

    cloud_sql_dsn = await _resolve("cloud_sql_dsn", project_id)
    openai_api_key = await _resolve("openai_api_key", project_id)

    _config = AppConfig(
        cloud_sql_dsn=cloud_sql_dsn,
        openai_api_key=openai_api_key,
    )

    # Log presence/absence without revealing values
    logger.info(
        "secrets loaded | cloud_sql_dsn=%s openai_api_key=%s",
        "set" if cloud_sql_dsn else "MISSING",
        "set" if openai_api_key else "MISSING",
    )
    return _config
