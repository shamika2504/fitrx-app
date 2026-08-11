# FitRx

**An AI fitness coach that reasons over your real training data** — not a chatbot with a fitness persona bolted on. FitRx pairs a fine-tuned Gemini model with a tool-calling agent that queries your actual workout history and biometrics before it says a word of advice, deployed as a production FastAPI service on GCP with full CI/CD and model drift monitoring.

## What it does

Ask `GET /recommendations/{participant_id}` a question — *"Should I do cardio or strength today?"* — and instead of a generic answer, the agent:

1. Pulls your last 30 days of workouts from BigQuery
2. Checks past recommendations already given (via semantic search, so it doesn't repeat itself)
3. Reasons over both with a **fine-tuned Gemini 2.5 Flash** model
4. Returns specific, numbers-referencing advice — under 300 words, grounded in your actual heart rate, sleep, and training load

Every inference is logged, embedded for future retrieval, and fed back into a drift-monitoring pipeline that watches the model's behavior over time.

## Why it's interesting

This isn't a CRUD app with an LLM call stapled on. It's a small but complete **applied ML system**:

| Stage | What's implemented |
|---|---|
| **Data** | 687K-row synthetic health/fitness dataset → curated into a 500-example instruction-tuning set |
| **Fine-tuning** | Supervised fine-tuning of Gemini 2.5 Flash on Vertex AI (`scripts/trigger_finetuning.py`) |
| **Evaluation** | LLM-as-judge harness scoring fine-tuned vs. base model across 4 dimensions on 30 held-out cases — **fine-tuned model wins by +6.9% overall**, +7.1% on personalization |
| **Serving** | Async FastAPI + LangChain tool-calling agent hitting the tuned Vertex AI endpoint |
| **Retrieval** | pgvector (Cloud SQL) cosine-similarity search over past recommendations, with automatic BigQuery fallback |
| **Monitoring** | Endpoint prediction logging + scheduled drift checks (z-score on input/output length, latency, and tool-usage distribution) |
| **CI/CD** | GitHub Actions → Docker → Cloud Run, authenticated via Workload Identity Federation (no long-lived service account keys) |
| **Secrets** | GCP Secret Manager in production, `.env` fallback for local dev |

## Architecture

```
                         ┌─────────────────────┐
  Client ── HTTP ──────► │   FastAPI (Cloud Run) │
                         └──────────┬────────────┘
                                    │
                 ┌──────────────────┼──────────────────┐
                 ▼                  ▼                  ▼
          /workout, /biometrics   /recommendations    /monitoring
          (BigQuery reads)             │              (stats + drift)
                                       ▼
                        LangChain tool-calling agent
                         ┌──────────────┴──────────────┐
                         ▼                              ▼
              get_user_workout_history        get_cached_recommendations
                  (BigQuery)                  (pgvector semantic search,
                                                BigQuery fallback)
                         │                              │
                         └──────────────┬───────────────┘
                                        ▼
                     Fine-tuned Gemini 2.5 Flash (Vertex AI)
                                        │
                                        ▼
                    Response logged → BigQuery + embedded → pgvector
```

## Tech stack

- **Backend**: Python, FastAPI, `asyncio`/`asyncpg`, Uvicorn
- **AI/ML**: LangChain (tool-calling agents), Vertex AI (fine-tuning + serving), OpenAI embeddings (`text-embedding-3-small`)
- **Data**: Google BigQuery (warehouse + logging), Cloud SQL Postgres with `pgvector` (semantic retrieval)
- **Infra**: Docker, Cloud Run, Artifact Registry, GCP Secret Manager, Workload Identity Federation
- **CI/CD**: GitHub Actions (build, push, deploy, automated health check)

## API surface

| Endpoint | Description |
|---|---|
| `GET /recommendations/{id}` | Core agentic endpoint — generates a personalized coaching recommendation |
| `GET /recommendations/latest-metrics/{id}` | Rolling 7-day activity averages |
| `GET /workout/summary/{id}` | Per-activity totals and averages |
| `GET /workout/trend/{id}` | Calorie burn trend over time |
| `GET /biometrics/overview/{id}` | Recent weight, BMI, sleep, stress, HR |
| `GET /biometrics/sleep-impact/{id}` | Correlates sleep hours with calorie burn |
| `GET /monitoring/stats` | Inference volume, latency, tool-usage distribution |
| `GET /health` | Liveness check |

## Project layout

```
backend/
  main.py                    FastAPI app, lifespan-managed secrets + pgvector pool
  core/secrets.py            Secret Manager loader with local .env fallback
  routers/                   workout, biometrics, recommendations, monitoring
  services/embedding_service.py   OpenAI embeddings + pgvector read/write
scripts/
  generate_finetune_dataset.py    Raw CSV → instruction-tuning JSONL
  trigger_finetuning.py           Vertex AI SFT job launcher
eval/
  run_eval.py                LLM-as-judge evaluation (fine-tuned vs. base)
  results.json / summary.txt Quantified before/after model comparison
monitoring/
  setup_monitoring.py        Prediction logging + drift detection setup
.github/workflows/deploy.yml Build → push → Cloud Run deploy → health check
```

## Running locally

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env   # fill in GCP_PROJECT_ID (and optionally CLOUD_SQL_DSN, OPENAI_API_KEY)
uvicorn main:app --reload
```

Without `CLOUD_SQL_DSN`/`OPENAI_API_KEY` set, the app runs fine — semantic search and embedding storage are skipped gracefully in favor of the BigQuery fallback path.

## Evaluation results

30 held-out coaching scenarios (beginner/intermediate/advanced, spanning weight loss, muscle gain, endurance, recovery), scored 1–5 by an independent Gemini judge on relevance, personalization, actionability, and criteria coverage:

```
Fine-tuned model scored +6.9% vs base model overall
  Relevance          +7.2%
  Personalization    +7.1%
  Actionability       +6.8%
  Criteria coverage   +6.5%
```

See `eval/README.md` for full methodology.
