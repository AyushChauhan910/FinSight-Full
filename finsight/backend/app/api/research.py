import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from app.agents.graph import FinSightAgent
from app.agents.mlflow_tracker import MLflowTracker
from app.ingestion.pipeline import IngestionPipeline
from app.models import (
    AgentResultResponse,
    CitationItem,
    IngestRequest,
    IngestResponse,
    IngestStatusResponse,
    IngestionResultResponse,
    JobStatus,
    ResearchQueryRequest,
    ResearchReportRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/research", tags=["research"])

_jobs: dict[str, dict] = {}

DEFAULT_REPORT_QUERY = (
    "Generate a comprehensive analyst report covering business overview, "
    "financial performance, key risks, and YoY trends"
)


async def _run_ingestion(job_id: str, ticker: str, years: int, vector_store=None):
    _jobs[job_id]["status"] = JobStatus.RUNNING
    _jobs[job_id]["progress"] = "Starting ingestion..."

    def update_progress(msg: str):
        _jobs[job_id]["progress"] = msg

    try:
        pipeline = IngestionPipeline(vector_store=vector_store)
        result = await pipeline.ingest_company(
            ticker,
            years,
            max_filings=5,
            progress_callback=update_progress,
        )

        tracker = MLflowTracker()
        tracker.log_ingestion_run(
            ticker=ticker,
            filings_processed=result.filings_processed,
            chunks_created=result.chunks_created,
            tokens_embedded=result.tokens_embedded,
            duration_seconds=result.duration_seconds,
        )

        _jobs[job_id]["status"] = JobStatus.COMPLETED
        _jobs[job_id]["progress"] = "Completed"
        _jobs[job_id]["result"] = IngestionResultResponse(
            ticker=result.ticker,
            filings_processed=result.filings_processed,
            chunks_created=result.chunks_created,
            tokens_embedded=result.tokens_embedded,
            duration_seconds=result.duration_seconds,
        )

    except Exception as e:
        logger.exception("Ingestion failed for %s", ticker)
        _jobs[job_id]["status"] = JobStatus.FAILED
        _jobs[job_id]["error"] = str(e)


@router.post("/ingest", response_model=IngestResponse)
async def ingest_company(ingest_request: IngestRequest, background_tasks: BackgroundTasks, http_request: Request):
    job_id = str(uuid.uuid4())
    _jobs[job_id] = {
        "status": JobStatus.QUEUED,
        "ticker": ingest_request.ticker.upper(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    vector_store = getattr(http_request.app.state, "vector_store", None)
    background_tasks.add_task(
        _run_ingestion, job_id, ingest_request.ticker, ingest_request.years, vector_store
    )

    logger.info("Queued ingestion job %s for %s", job_id, ingest_request.ticker)

    return IngestResponse(job_id=job_id, status=JobStatus.QUEUED)


@router.get("/status/{job_id}", response_model=IngestStatusResponse)
async def get_ingest_status(job_id: str):
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return IngestStatusResponse(
        job_id=job_id,
        status=job["status"],
        progress=job.get("progress"),
        result=job.get("result"),
        error=job.get("error"),
    )


@router.post("/query")
async def research_query(request: ResearchQueryRequest):
    ticker = request.ticker.upper()
    agent = FinSightAgent()

    logger.info("Running research query for %s: %s", ticker, request.query[:100])

    try:
        result = await agent.run(ticker, request.query)

        tracker = MLflowTracker()
        tracker.log_agent_run(
            ticker=ticker,
            query=request.query,
            model="llama-3.3-70b-versatile",
            tokens_in=0,
            tokens_out=result.tokens_used,
            latency_ms=0,
            retrieval_precision_proxy=0.0,
            iterations_used=result.iterations_used,
        )

        return AgentResultResponse(
            answer=result.answer,
            report=result.report,
            citations=[CitationItem(**c) for c in result.citations],
            iterations_used=result.iterations_used,
            tokens_used=result.tokens_used,
        )

    except Exception as e:
        logger.exception("Research query failed for %s", ticker)
        raise HTTPException(status_code=500, detail=str(e))


def _agent_result_to_payload(result) -> dict:
    return {
        "answer": result.answer,
        "report": result.report,
        "citations": result.citations,
        "iterations_used": result.iterations_used,
        "tokens_used": result.tokens_used,
    }


@router.post("/report")
async def generate_report(request: ResearchReportRequest):
    ticker = request.ticker.upper()
    agent = FinSightAgent()

    logger.info("Generating full report for %s", ticker)

    try:
        result = await agent.run(ticker, DEFAULT_REPORT_QUERY)

        tracker = MLflowTracker()
        tracker.log_agent_run(
            ticker=ticker,
            query=DEFAULT_REPORT_QUERY,
            model="llama-3.3-70b-versatile",
            tokens_in=0,
            tokens_out=result.tokens_used,
            latency_ms=0,
            retrieval_precision_proxy=0.0,
            iterations_used=result.iterations_used,
        )

        return AgentResultResponse(
            answer=result.answer,
            report=result.report,
            citations=[CitationItem(**c) for c in result.citations],
            iterations_used=result.iterations_used,
            tokens_used=result.tokens_used,
        )

    except Exception as e:
        logger.exception("Report generation failed for %s", ticker)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stream")
async def stream_research(ticker: str, query: str):
    ticker = ticker.upper()

    async def event_generator():
        agent = FinSightAgent()

        try:
            yield {
                "event": "status",
                "data": json.dumps({"message": "Starting research...", "ticker": ticker}),
            }

            result = await agent.run(ticker, query)

            md = (result.report_markdown or "").strip()
            if md:
                for part in md.split("## "):
                    if not part.strip():
                        continue
                    yield {
                        "event": "chunk",
                        "data": json.dumps({"content": "## " + part}),
                    }
                    await asyncio.sleep(0.05)
            else:
                yield {
                    "event": "chunk",
                    "data": json.dumps({"content": result.answer[:8000]}),
                }

            yield {
                "event": "citations",
                "data": json.dumps({"citations": result.citations}),
            }

            yield {
                "event": "done",
                "data": json.dumps(_agent_result_to_payload(result)),
            }

        except Exception as e:
            logger.exception("Streaming failed for %s", ticker)
            yield {
                "event": "stream_error",
                "data": json.dumps({"error": str(e)}),
            }

    return EventSourceResponse(event_generator())


@router.get("/stream-events")
async def stream_research_events(ticker: str, query: str):
    ticker = ticker.upper()

    async def event_generator():
        from langchain_core.callbacks import AsyncCallbackHandler

        class SSEHandler(AsyncCallbackHandler):
            def __init__(self, queue: asyncio.Queue):
                self.queue = queue

            async def on_llm_new_token(self, token: str, **kwargs):
                await self.queue.put({"event": "token", "data": json.dumps({"content": token})})

        queue: asyncio.Queue = asyncio.Queue()
        handler = SSEHandler(queue)

        async def run_agent():
            agent = FinSightAgent()
            return await agent.run(ticker, query)

        agent_task = asyncio.create_task(run_agent())

        yield {
            "event": "status",
            "data": json.dumps({"message": "Research started", "ticker": ticker}),
        }

        while not agent_task.done():
            try:
                event = await asyncio.wait_for(queue.get(), timeout=0.1)
                yield event
            except asyncio.TimeoutError:
                pass

        result = await agent_task

        yield {
            "event": "result",
            "data": json.dumps({
                "answer": result.answer,
                "report": result.report,
                "citations": result.citations,
                "iterations_used": result.iterations_used,
                "tokens_used": result.tokens_used,
            }),
        }

        yield {
            "event": "done",
            "data": json.dumps({"status": "complete"}),
        }

    return EventSourceResponse(event_generator())
