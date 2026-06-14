import logging

import asyncpg
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536

_openai_client: AsyncOpenAI | None = None


def _get_openai_client() -> AsyncOpenAI:
    global _openai_client
    if _openai_client is None:
        from core.secrets import get_config
        api_key = get_config().openai_api_key
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY secret is not set")
        _openai_client = AsyncOpenAI(api_key=api_key)
    return _openai_client


def _vec_str(embedding: list[float]) -> str:
    """Convert a float list to pgvector text format: [0.1,0.2,...]"""
    return "[" + ",".join(str(v) for v in embedding) + "]"


async def generate_embedding(text: str) -> list[float]:
    """Generate a 1536-dim embedding via OpenAI text-embedding-3-small."""
    resp = await _get_openai_client().embeddings.create(
        model=EMBEDDING_MODEL,
        input=text[:8191],
    )
    return resp.data[0].embedding


async def store_recommendation_embedding(
    pool: asyncpg.Pool,
    participant_id: int,
    recommendation_text: str,
) -> None:
    """Generate embedding for recommendation_text and persist to pgvector table."""
    embedding = await generate_embedding(recommendation_text)
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO recommendation_embeddings
                (participant_id, recommendation_text, embedding)
            VALUES ($1, $2, $3::vector)
            """,
            participant_id,
            recommendation_text,
            _vec_str(embedding),
        )
    logger.info(
        "embedding_stored participant_id=%s text_len=%d",
        participant_id, len(recommendation_text),
    )


async def retrieve_similar_recommendations(
    pool: asyncpg.Pool,
    participant_id: int,
    query_text: str,
    top_k: int = 5,
) -> list[dict]:
    """
    Run cosine similarity search against recommendation_embeddings
    filtered by participant_id. Returns top_k most similar past
    recommendations ordered by descending similarity.
    """
    query_embedding = await generate_embedding(query_text)
    vec = _vec_str(query_embedding)

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                recommendation_text,
                created_at::TEXT            AS created_at,
                1 - (embedding <=> $1::vector) AS similarity
            FROM recommendation_embeddings
            WHERE participant_id = $2
            ORDER BY embedding <=> $1::vector
            LIMIT $3
            """,
            vec,
            participant_id,
            top_k,
        )
    results = [dict(r) for r in rows]
    logger.info(
        "semantic_retrieval participant_id=%s query_len=%d results=%d",
        participant_id, len(query_text), len(results),
    )
    return results
