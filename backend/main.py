from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
load_dotenv()
from routers import workout, biometrics, recommendations

app = FastAPI(title="FitRx API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(workout.router, prefix="/workout", tags=["Workout"])
app.include_router(biometrics.router, prefix="/biometrics", tags=["Biometrics"])
app.include_router(recommendations.router, prefix="/recommendations", tags=["Recommendations"])

@app.get("/health")
def health_check():
    return {"status": "ok"}
