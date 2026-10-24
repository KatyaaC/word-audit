"""Standalone service for Katya's backend pieces (auth + Layer A).

Run:  uvicorn main:app --reload --port 8000

In the integrated build, Sudiksha's FastAPI app includes these two routers
instead and this file is only used for local development.
"""
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from bt_auth import router as auth_router
from layer_a.router import router as layer_a_router

app = FastAPI(title="WordAudit: auth and Layer A", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(layer_a_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
