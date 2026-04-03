import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

import mlflow
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import companies, research
from app.ingestion.vector_store import get_shared_instance

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "./mlruns")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting FinSight API...")

    Path(CHROMA_PERSIST_DIR).mkdir(parents=True, exist_ok=True)
    Path(MLFLOW_TRACKING_URI).mkdir(parents=True, exist_ok=True)

    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment("finsight-agent")
    logger.info("MLflow tracking URI: %s", MLFLOW_TRACKING_URI)

    app.state.vector_store = get_shared_instance()
    logger.info("ChromaDB initialized at %s", CHROMA_PERSIST_DIR)

    logger.info("FinSight API ready")

    yield

    logger.info("Shutting down FinSight API...")


app = FastAPI(
    title="FinSight API",
    description="AI-powered financial research platform using SEC filings",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(research.router)
app.include_router(companies.router)


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "finsight-api"}


@app.get("/")
async def root():
    return {
        "name": "FinSight API",
        "version": "1.0.0",
        "docs": "/docs",
    }
