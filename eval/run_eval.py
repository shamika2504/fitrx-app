#!/usr/bin/env python3
"""
FitRx Model Evaluation — Fine-tuned Gemini 2.5 Flash vs Base Gemini 2.5 Flash

Usage:
    pip install google-genai tqdm
    export GCP_PROJECT_ID=project-6ce813b2-674a-4d31-aad
    python eval/run_eval.py

Results are saved incrementally — safe to interrupt and resume.
"""

import asyncio
import json
import os
import re
import time
from pathlib import Path

from google import genai
from google.genai import types
from tqdm import tqdm

# ── Config ────────────────────────────────────────────────────────────────────

PROJECT_ID = os.getenv("GCP_PROJECT_ID", "project-6ce813b2-674a-4d31-aad")
LOCATION = "us-central1"

BASE_MODEL = "gemini-2.5-flash"
FINETUNED_ENDPOINT = (
    "projects/434489845366/locations/us-central1/endpoints/988584648428748800"
)

MAX_TOKENS = 500
MAX_RETRIES = 3
MAX_CONCURRENT = 3   # semaphore keeps API rate under control

EVAL_DIR = Path(__file__).parent
TEST_CASES_PATH = EVAL_DIR / "test_cases.json"
RESULTS_PATH = EVAL_DIR / "results.json"
SUMMARY_PATH = EVAL_DIR / "summary.txt"

SYSTEM_PROMPT = (
    "You are FitRx, a personal fitness coach. "
    "Analyze the user's health and workout metrics and give specific, actionable advice. "
    "Always reference the user's actual numbers in your response."
)

JUDGE_TEMPLATE = """\
You are an expert evaluator of AI fitness coaching responses.

User Context:
{user_context}

Question: {question}

Ideal Response Criteria:
{criteria}

Response to evaluate:
{response}

Score this response on each dimension from 1 to 5:
- relevance: Does it directly address the user's specific question?
- personalization: Does it reference the user's actual context, metrics, or history?
- actionability: Does it provide a specific, concrete, implementable recommendation?
- criteria_coverage: How many of the ideal_response_criteria are addressed? (1=none met, 5=all met)

You MUST respond with exactly this JSON structure and nothing else. No markdown fences, no explanation:
{{"relevance": 4, "personalization": 3, "actionability": 5, "criteria_coverage": 4}}

Replace the example numbers above with your actual scores.
"""

# ── Client ────────────────────────────────────────────────────────────────────

client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)
_semaphore = asyncio.Semaphore(MAX_CONCURRENT)

GENERATION_CONFIG = types.GenerateContentConfig(
    max_output_tokens=MAX_TOKENS,
    system_instruction=SYSTEM_PROMPT,
)

JUDGE_CONFIG = types.GenerateContentConfig(
    max_output_tokens=500,
    thinking_config=types.ThinkingConfig(thinking_budget=0),
)


# ── Core async helpers ────────────────────────────────────────────────────────

async def with_retry(coro_fn, max_retries: int = MAX_RETRIES):
    last_exc = None
    for attempt in range(max_retries):
        try:
            return await coro_fn()
        except Exception as exc:
            last_exc = exc
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
    raise last_exc


async def _generate(model: str, prompt: str, config) -> tuple[str, float]:
    async with _semaphore:
        start = time.monotonic()
        response = await with_retry(
            lambda: client.aio.models.generate_content(
                model=model,
                contents=prompt,
                config=config,
            )
        )
        latency_ms = (time.monotonic() - start) * 1000
        return response.text, latency_ms


def _build_prompt(case: dict) -> str:
    ctx = case["user_context"]
    workouts = ", ".join(ctx.get("recent_workouts", []))
    bio = ctx.get("biometrics", {})
    bio_str = ", ".join(f"{k}: {v}" for k, v in bio.items())
    goal = ctx.get("goal", "general fitness")
    return (
        f"Recent workouts: {workouts}\n"
        f"Biometrics: {bio_str}\n"
        f"Goal: {goal}\n\n"
        f"Question: {case['question']}"
    )


def _parse_scores(text: str) -> dict:
    # Strip markdown fences if present
    text = re.sub(r"```(?:json)?", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[^{}]+\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    print(f"  [warn] judge parse failed, raw: {repr(text[:120])}")
    return {"relevance": 0, "personalization": 0, "actionability": 0, "criteria_coverage": 0}


async def _judge(case: dict, response_text: str) -> dict:
    criteria_str = "\n".join(f"- {c}" for c in case["ideal_response_criteria"])
    prompt = JUDGE_TEMPLATE.format(
        user_context=json.dumps(case["user_context"], indent=2),
        question=case["question"],
        criteria=criteria_str,
        response=response_text,
    )
    text, _ = await _generate(BASE_MODEL, prompt, JUDGE_CONFIG)
    return _parse_scores(text)


# ── Incremental save / resume ─────────────────────────────────────────────────

def _load_results() -> dict:
    if RESULTS_PATH.exists():
        with open(RESULTS_PATH) as f:
            return json.load(f)
    return {}


def _save_result(results: dict, case_id: int, result: dict) -> None:
    results[str(case_id)] = result
    with open(RESULTS_PATH, "w") as f:
        json.dump(results, f, indent=2)


# ── Per-case evaluation ───────────────────────────────────────────────────────

async def evaluate_case(case: dict, results: dict) -> dict:
    case_key = str(case["id"])
    if case_key in results:
        return results[case_key]

    prompt = _build_prompt(case)

    # Call both models concurrently
    (base_text, base_lat), (ft_text, ft_lat) = await asyncio.gather(
        _generate(BASE_MODEL, prompt, GENERATION_CONFIG),
        _generate(FINETUNED_ENDPOINT, prompt, GENERATION_CONFIG),
    )

    # Judge both responses concurrently
    base_scores, ft_scores = await asyncio.gather(
        _judge(case, base_text),
        _judge(case, ft_text),
    )

    result = {
        "id": case["id"],
        "question": case["question"],
        "base": {
            "response": base_text,
            "scores": base_scores,
            "latency_ms": round(base_lat),
        },
        "finetuned": {
            "response": ft_text,
            "scores": ft_scores,
            "latency_ms": round(ft_lat),
        },
    }

    _save_result(results, case["id"], result)
    return result


# ── Summary ───────────────────────────────────────────────────────────────────

def generate_summary(results: dict) -> str:
    dims = ["relevance", "personalization", "actionability", "criteria_coverage"]

    base_by_dim: dict[str, list] = {d: [] for d in dims}
    ft_by_dim: dict[str, list]   = {d: [] for d in dims}
    base_lats, ft_lats = [], []

    for r in results.values():
        for d in dims:
            base_by_dim[d].append(r["base"]["scores"].get(d, 0))
            ft_by_dim[d].append(r["finetuned"]["scores"].get(d, 0))
        base_lats.append(r["base"]["latency_ms"])
        ft_lats.append(r["finetuned"]["latency_ms"])

    n = len(results)
    base_avg  = {d: sum(base_by_dim[d]) / n for d in dims}
    ft_avg    = {d: sum(ft_by_dim[d]) / n   for d in dims}

    base_overall = sum(base_avg.values()) / len(dims)
    ft_overall   = sum(ft_avg.values())   / len(dims)
    overall_pct  = ((ft_overall - base_overall) / base_overall) * 100 if base_overall else 0

    lines = [
        "=" * 62,
        "FitRx Model Evaluation Summary",
        f"Test cases: {n}  |  Score range per dimension: 1–5",
        "=" * 62,
        "",
        f"Fine-tuned model scored {overall_pct:+.1f}% vs base model overall",
        f"  Overall avg:  fine-tuned {ft_overall:.2f}  vs  base {base_overall:.2f}",
        "",
        "Per-dimension breakdown:",
    ]

    for d in dims:
        pct = ((ft_avg[d] - base_avg[d]) / base_avg[d]) * 100 if base_avg[d] else 0
        label = d.replace("_", " ").capitalize()
        lines.append(
            f"  {label:<24} fine-tuned {ft_avg[d]:.2f}  base {base_avg[d]:.2f}  ({pct:+.1f}%)"
        )

    avg_base_lat = sum(base_lats) / len(base_lats)
    avg_ft_lat   = sum(ft_lats)   / len(ft_lats)

    lines += [
        "",
        "Latency (avg):",
        f"  Fine-tuned: {avg_ft_lat:.0f} ms",
        f"  Base:       {avg_base_lat:.0f} ms",
        "=" * 62,
    ]

    return "\n".join(lines)


# ── Rescore (re-judge existing responses without re-generating) ───────────────

async def rescore_all():
    """Re-run only the judge calls on already-generated responses."""
    with open(TEST_CASES_PATH) as f:
        test_cases = json.load(f)

    results = _load_results()
    cases_by_id = {str(c["id"]): c for c in test_cases}

    if not results:
        print("No results.json found — run without --rescore first.")
        return

    print(f"Rescoring {len(results)} existing cases (judge calls only)...")

    with tqdm(total=len(results), desc="Rescoring", unit="case") as pbar:
        for case_key, result in list(results.items()):
            case = cases_by_id[case_key]
            base_scores, ft_scores = await asyncio.gather(
                _judge(case, result["base"]["response"]),
                _judge(case, result["finetuned"]["response"]),
            )
            result["base"]["scores"] = base_scores
            result["finetuned"]["scores"] = ft_scores
            _save_result(results, result["id"], result)
            pbar.update(1)
            pbar.set_postfix({"id": result["id"]})

    summary = generate_summary(results)
    print("\n" + summary)
    with open(SUMMARY_PATH, "w") as f:
        f.write(summary)
    print(f"\nFull results → {RESULTS_PATH}")
    print(f"Summary      → {SUMMARY_PATH}")


# ── Main ──────────────────────────────────────────────────────────────────────

async def main():
    import sys
    rescore = "--rescore" in sys.argv

    if rescore:
        await rescore_all()
        return

    with open(TEST_CASES_PATH) as f:
        test_cases = json.load(f)

    results = _load_results()
    remaining = [c for c in test_cases if str(c["id"]) not in results]

    print(
        f"Loaded {len(test_cases)} test cases. "
        f"{len(results)} already complete, {len(remaining)} to run."
    )
    if not remaining:
        print("All cases already evaluated — generating summary.")
    else:
        with tqdm(total=len(remaining), desc="Evaluating", unit="case") as pbar:
            for case in remaining:
                await evaluate_case(case, results)
                pbar.update(1)
                pbar.set_postfix({"id": case["id"]})

    summary = generate_summary(results)
    print("\n" + summary)

    with open(SUMMARY_PATH, "w") as f:
        f.write(summary)

    print(f"\nFull results → {RESULTS_PATH}")
    print(f"Summary      → {SUMMARY_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
