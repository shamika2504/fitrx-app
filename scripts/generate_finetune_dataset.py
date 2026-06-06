import json
import random
import csv
import os

INPUT_CSV = os.path.join(os.path.dirname(__file__), "../data/health_fitness_dataset.csv")
OUTPUT_JSONL = os.path.join(os.path.dirname(__file__), "../data/finetune_dataset.jsonl")

SYSTEM_PROMPT = (
    "You are FitRx, a personal fitness coach. "
    "Analyze the user's health and workout metrics and give specific, actionable advice. "
    "Always reference the user's actual numbers in your response."
)

def classify_sleep(hours):
    if hours >= 8:
        return "excellent", "great recovery — keep this up"
    elif hours >= 7:
        return "good", "solid sleep, supporting your recovery well"
    elif hours >= 6:
        return "below optimal", "try to add 30-60 more minutes of sleep for better recovery"
    else:
        return "poor", "seriously impacting your recovery — prioritize sleep this week"

def classify_stress(level):
    if level <= 3:
        return "low"
    elif level <= 6:
        return "moderate"
    else:
        return "high"

def classify_bmi(bmi):
    if bmi < 18.5:
        return "underweight"
    elif bmi < 25:
        return "healthy range"
    elif bmi < 30:
        return "slightly above healthy range"
    else:
        return "above healthy range"

def generate_example(row):
    try:
        activity = row.get("activity_type", "workout")
        calories = float(row.get("calories_burned", 0))
        duration = int(row.get("duration_minutes", 0))
        intensity = row.get("intensity", "Moderate")
        heart_rate = int(row.get("avg_heart_rate", 0))
        sleep = float(row.get("hours_sleep", 0))
        stress = int(row.get("stress_level", 0))
        bmi = float(row.get("bmi", 0))
        steps = int(row.get("daily_steps", 0))
        fitness_level = float(row.get("fitness_level", 0))
        resting_hr = float(row.get("resting_heart_rate", 0))
    except (ValueError, TypeError):
        return None

    sleep_label, sleep_advice = classify_sleep(sleep)
    stress_label = classify_stress(stress)
    bmi_label = classify_bmi(bmi)

    user_message = (
        f"Here are my stats from today's session: I did {duration} minutes of {activity} "
        f"at {intensity} intensity, burned {calories:.1f} calories, and my average heart rate was {heart_rate} bpm. "
        f"I slept {sleep:.1f} hours last night, my stress level is {stress}/10, "
        f"I walked {steps:,} steps today, and my BMI is {bmi:.1f}. What should I focus on?"
    )

    recovery_note = ""
    if resting_hr > 75:
        recovery_note = f" Your resting heart rate of {resting_hr:.0f} bpm is elevated — this may indicate incomplete recovery or high stress load."

    training_tip = ""
    if activity == "HIIT" and sleep < 7:
        training_tip = f" I'd suggest replacing one HIIT session this week with a Zone 2 cardio session (easy pace, HR under 130 bpm) to allow your body to recover."
    elif activity == "Yoga" and stress > 6:
        training_tip = f" Since your stress is {stress_label}, your Yoga sessions are well-chosen — continue prioritizing them and add 5 minutes of breathing work post-session."
    elif activity == "Running":
        training_tip = f" For running at your fitness level ({fitness_level:.1f}), aim to keep two of your weekly runs at easy pace (conversational) and one at tempo effort."
    elif activity == "Weight Training":
        training_tip = f" Ensure you are hitting each muscle group with at least 48 hours rest between sessions for optimal adaptation."

    steps_note = ""
    if steps < 5000:
        steps_note = " Your daily steps are low — aim for at least 7,000 steps on rest days to support cardiovascular health."
    elif steps > 10000:
        steps_note = f" Great step count of {steps:,} — this non-exercise activity adds up significantly over time."

    assistant_message = (
        f"Based on your session data: {duration} minutes of {intensity.lower()} {activity} "
        f"with an average HR of {heart_rate} bpm looks {'strong' if heart_rate > 130 else 'controlled'} for your fitness level. "
        f"Your sleep is {sleep_label} ({sleep:.1f} hrs) — {sleep_advice}."
        f"{recovery_note}"
        f" Your stress level is {stress_label} at {stress}/10"
        f"{' — consider adding a 10-minute wind-down routine tonight' if stress > 6 else ', which is manageable'}. "
        f"BMI of {bmi:.1f} puts you in the {bmi_label}."
        f"{training_tip}"
        f"{steps_note}"
        f" Keep tracking consistently — patterns over 2+ weeks will reveal your best recovery and performance windows."
    )

    return {
        "systemInstruction": {
            "parts": [{"text": SYSTEM_PROMPT}]
        },
        "contents": [
            {"role": "user", "parts": [{"text": user_message}]},
            {"role": "model", "parts": [{"text": assistant_message}]}
        ]
    }

def main():
    examples = []

    with open(INPUT_CSV, newline="", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        rows = list(reader)

    random.shuffle(rows)
    rows = rows[:600]

    for row in rows:
        example = generate_example(row)
        if example:
            examples.append(example)
        if len(examples) >= 500:
            break

    with open(OUTPUT_JSONL, "w", encoding="utf-8") as f:
        for example in examples:
            f.write(json.dumps(example) + "\n")

    print(f"Generated {len(examples)} fine-tuning examples -> {OUTPUT_JSONL}")

if __name__ == "__main__":
    main()
