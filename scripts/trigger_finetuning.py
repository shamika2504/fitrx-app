import time
import vertexai
from vertexai.tuning import sft

PROJECT_ID = "project-6ce813b2-674a-4d31-aad"
LOCATION = "us-central1"
TRAINING_DATA = "gs://fitrx-finetune-data/finetune_dataset.jsonl"
MODEL_DISPLAY_NAME = "fitrx-gemini-finetuned"

vertexai.init(project=PROJECT_ID, location=LOCATION)

try:
    sft_tuning_job = sft.train(
        source_model="gemini-2.5-flash",
        train_dataset=TRAINING_DATA,
        epochs=3,
        learning_rate_multiplier=1.0,
        tuned_model_display_name=MODEL_DISPLAY_NAME,
    )

    print(f"Fine-tuning job started: {sft_tuning_job.resource_name}")
    print(f"Job ID: {sft_tuning_job.name}")
    print("\nWaiting for job to complete (this may take 30-60 minutes)...")

    while sft_tuning_job.state.name not in ("SUCCEEDED", "FAILED", "CANCELLED"):
        print(f"Job status: {sft_tuning_job.state.name} — checking again in 60s...")
        time.sleep(60)
        sft_tuning_job = sft.SupervisedTuningJob(sft_tuning_job.resource_name)

    print(f"Job status: {sft_tuning_job.state.name}")

    if sft_tuning_job.state.name == "SUCCEEDED":
        tuned_model_id = sft_tuning_job.tuned_model_endpoint_name
        print(f"\nFine-tuning completed successfully!")
        print(f"Tuned model endpoint: {tuned_model_id}")
        with open("tuned_model_id.txt", "w") as f:
            f.write(tuned_model_id)
        print("Saved model endpoint to tuned_model_id.txt")
    else:
        print(f"Job ended with status: {sft_tuning_job.state}")

except Exception as e:
    print(f"Error: {e}")
