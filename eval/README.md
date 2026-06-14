# FitRx Model Evaluation

Compares the fine-tuned Gemini 2.5 Flash model against the base Gemini 2.5 Flash
on 30 held-out fitness coaching test cases. Produces a quantified improvement
percentage suitable for resume and portfolio use.

## Setup

```bash
pip install google-genai tqdm
export GCP_PROJECT_ID=project-6ce813b2-674a-4d31-aad
```

You must be authenticated with GCP:
```bash
gcloud auth application-default login
```

## Run

```bash
cd /path/to/FitRx
python eval/run_eval.py
```

The script is safe to interrupt — results are saved after every completed case.
Re-running picks up from where it left off.

## Output files

| File | Contents |
|------|----------|
| `eval/results.json` | Full per-case scores, responses, and latencies for both models |
| `eval/summary.txt` | Aggregated % improvement across all dimensions |

## How scoring works

Each response is scored 1–5 on four dimensions by a separate Gemini judge call:

| Dimension | What it measures |
|-----------|-----------------|
| **Relevance** | Does the response directly address the user's question? |
| **Personalization** | Does it reference the user's actual metrics, history, and goal? |
| **Actionability** | Does it give a specific, implementable recommendation? |
| **Criteria coverage** | How many of the ideal response criteria are met? |

The judge is the base Gemini 2.5 Flash model with `response_mime_type="application/json"`
to guarantee parseable output. Using the base model as judge intentionally avoids
self-serving bias — if the fine-tuned model is genuinely better, it will score
higher even with a neutral judge.

## How to read the summary

```
Fine-tuned model scored +18.3% vs base model overall
  Overall avg:  fine-tuned 4.12  vs  base 3.48

Per-dimension breakdown:
  Relevance               fine-tuned 4.20  base 3.80  (+10.5%)
  Personalization         fine-tuned 4.40  base 3.20  (+37.5%)   ← biggest gain
  Actionability           fine-tuned 4.10  base 3.60  (+13.9%)
  Criteria coverage       fine-tuned 3.80  base 3.30  (+15.2%)
```

Personalization is expected to show the largest improvement because the fine-tuning
dataset was specifically designed to produce responses that reference the user's
actual metrics.

## Test case diversity

30 cases spanning:
- **Goals**: weight loss, muscle gain, endurance, recovery, flexibility, body recomp
- **Fitness levels**: beginner (10), intermediate (10), advanced (10)
- **Question types**: daily workout selection, nutrition advice, progress assessment,
  injury prevention, recovery guidance

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GCP_PROJECT_ID` | Yes | GCP project ID (defaults to `project-6ce813b2-674a-4d31-aad`) |

No OpenAI key needed — all calls go through Vertex AI.

## Estimated cost

- 30 cases × 4 API calls each (base, fine-tuned, judge×2) = 120 calls
- 500 max tokens per generation call, 200 per judge call
- Estimated total: **< $1.50** at current Vertex AI pricing
