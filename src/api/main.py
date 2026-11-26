# main.py
"""FastAPI app — instrumented with Prometheus, exposes all layer endpoints."""
from fastapi import FastAPI
from src.observability.prometheus_metrics import instrument_app
from src.api.routers import monitoring, oee, maintenance, quality, energy, assistant, twin

app = FastAPI(title="NeuroPlant AI API")
instrument_app(app)
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
        "http://localhost:8501",
        "http://127.0.0.1:8501",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
# ── Routers registered AFTER middleware ──
from src.api.routers import (
    monitoring, oee, maintenance, alerts,
    energy, quality, twin, assistant,
)
app.include_router(monitoring.router)
app.include_router(oee.router)
app.include_router(maintenance.router)
app.include_router(alerts.router)
app.include_router(energy.router)
app.include_router(quality.router)
app.include_router(twin.router)          # ← this must be present
app.include_router(assistant.router)

@app.get("/health")
def health_check():
    return {"status": "healthy"}

@app.on_event("startup")
async def _debug_routes():
    print("=== REGISTERED ROUTES ===")
    for r in app.routes:
        if hasattr(r, "path"):
            print(f"  {r.path}")
    print("=== END ===")