import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import mlflow
from dotenv import load_dotenv

from app.agents.prompts import PROMPT_VERSION

load_dotenv()

logger = logging.getLogger(__name__)

MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "./mlruns")

EXPERIMENT_NAME = "finsight-agent"


class MLflowTracker:
    def __init__(self):
        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
        mlflow.set_experiment(EXPERIMENT_NAME)

    def log_run(
        self,
        run_name: str,
        params: dict | None = None,
        metrics: dict | None = None,
    ) -> str:
        params = params or {}
        metrics = metrics or {}

        with mlflow.start_run(run_name=run_name) as run:
            mlflow.set_tag("prompt_version", PROMPT_VERSION)
            mlflow.set_tag("run_timestamp", datetime.now(timezone.utc).isoformat())

            for key, value in params.items():
                mlflow.log_param(key, value)

            for key, value in metrics.items():
                if isinstance(value, (int, float)):
                    mlflow.log_metric(key, value)

            run_id = run.info.run_id

        logger.info("Logged run %s (id=%s) to MLflow", run_name, run_id)
        return run_id

    def log_agent_run(
        self,
        ticker: str,
        query: str,
        model: str,
        tokens_in: int,
        tokens_out: int,
        latency_ms: float,
        retrieval_precision_proxy: float,
        iterations_used: int,
    ) -> str:
        run_name = f"agent_{ticker}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

        params = {
            "ticker": ticker,
            "query": query[:500],
            "model": model,
            "prompt_version": PROMPT_VERSION,
        }

        metrics = {
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "total_tokens": tokens_in + tokens_out,
            "latency_ms": latency_ms,
            "retrieval_precision_proxy": retrieval_precision_proxy,
            "iterations_used": iterations_used,
        }

        return self.log_run(run_name, params, metrics)

    def log_ingestion_run(
        self,
        ticker: str,
        filings_processed: int,
        chunks_created: int,
        tokens_embedded: int,
        duration_seconds: float,
    ) -> str:
        run_name = f"ingest_{ticker}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

        params = {
            "ticker": ticker,
            "prompt_version": PROMPT_VERSION,
        }

        metrics = {
            "filings_processed": filings_processed,
            "chunks_created": chunks_created,
            "tokens_embedded": tokens_embedded,
            "duration_seconds": duration_seconds,
        }

        return self.log_run(run_name, params, metrics)

    def get_run_history(
        self,
        ticker: str | None = None,
        max_results: int = 50,
    ) -> list[dict]:
        experiment = mlflow.get_experiment_by_name(EXPERIMENT_NAME)
        if not experiment:
            return []

        filter_string = ""
        if ticker:
            filter_string = f"params.ticker = '{ticker}'"

        runs = mlflow.search_runs(
            experiment_ids=[experiment.experiment_id],
            filter_string=filter_string,
            max_results=max_results,
            order_by=["start_time DESC"],
        )

        results = []
        for _, row in runs.iterrows():
            results.append({
                "run_id": row.get("run_id", ""),
                "run_name": row.get("tags.mlflow.runName", ""),
                "start_time": str(row.get("start_time", "")),
                "status": row.get("status", ""),
                "prompt_version": row.get("tags.prompt_version", ""),
                "metrics": {
                    k.replace("metrics.", ""): v
                    for k, v in row.items()
                    if k.startswith("metrics.") and v is not None
                },
                "params": {
                    k.replace("params.", ""): v
                    for k, v in row.items()
                    if k.startswith("params.") and v is not None
                },
            })

        return results
