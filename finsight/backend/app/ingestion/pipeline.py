import asyncio
import logging
import time
from collections.abc import Callable
from datetime import datetime, timedelta

from pydantic import BaseModel

from app.ingestion.document_processor import DocumentProcessor
from app.ingestion.sec_fetcher import SECFetcher
from app.ingestion.vector_store import VectorStoreManager

logger = logging.getLogger(__name__)


class IngestionResult(BaseModel):
    ticker: str
    filings_processed: int
    chunks_created: int
    tokens_embedded: int
    duration_seconds: float


class IngestionPipeline:
    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        vector_store: VectorStoreManager | None = None,
    ):
        self._processor = DocumentProcessor(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        self._vector_store = vector_store if vector_store is not None else VectorStoreManager()

    async def ingest_company(
        self,
        ticker: str,
        years: int = 3,
        max_filings: int = 5,
        progress_callback: Callable[[str], None] | None = None,
    ) -> IngestionResult:
        start = time.monotonic()
        ticker = ticker.upper().strip()

        logger.info("Starting ingestion for %s (last %d years)", ticker, years)

        if progress_callback:
            progress_callback("Fetching filing list from SEC EDGAR...")

        async with SECFetcher() as fetcher:
            current_year = datetime.now().year
            start_year = current_year - years

            all_filings = await fetcher.get_filings(
                ticker=ticker,
                form_types=["10-K", "10-Q"],
                limit=years * 5,
            )

            cutoff_date = f"{start_year}-01-01"
            filings = [f for f in all_filings if f.filing_date >= cutoff_date]

            filings = filings[:max_filings]

            logger.info(
                "Processing %d filings for %s since %s (limited to %d)",
                len(filings),
                ticker,
                cutoff_date,
                max_filings,
            )

            if progress_callback:
                progress_callback(f"Found {len(filings)} filings to process")

            all_chunks = []
            total_tokens = 0

            for i, filing in enumerate(filings):
                try:
                    if progress_callback:
                        progress_callback(
                            f"Processing filing {i + 1}/{len(filings)}: "
                            f"{filing.form_type} ({filing.filing_date})"
                        )

                    text = await fetcher.download_filing(filing)
                    chunks = self._processor.chunk_document(
                        text=text,
                        ticker=ticker,
                        form_type=filing.form_type,
                        filing_date=filing.filing_date,
                    )

                    if chunks:
                        if progress_callback:
                            progress_callback(
                                f"Embedding {len(chunks)} chunks for "
                                f"{filing.form_type} ({filing.filing_date})"
                            )

                        stats = self._vector_store.upsert_chunks(chunks)
                        total_tokens += stats["tokens_embedded"]
                        all_chunks.extend(chunks)

                except Exception as e:
                    logger.exception(
                        "Failed to process %s %s for %s",
                        filing.form_type,
                        filing.filing_date,
                        ticker,
                    )

        duration = time.monotonic() - start

        result = IngestionResult(
            ticker=ticker,
            filings_processed=len(filings),
            chunks_created=len(all_chunks),
            tokens_embedded=total_tokens,
            duration_seconds=round(duration, 2),
        )

        logger.info(
            "Completed ingestion for %s: %d filings, %d chunks, %.2fs",
            result.ticker,
            result.filings_processed,
            result.chunks_created,
            result.duration_seconds,
        )

        return result

    async def ingest_batch(
        self,
        tickers: list[str],
        years: int = 3,
    ) -> list[IngestionResult]:
        semaphore = asyncio.Semaphore(5)

        async def _limited(ticker: str) -> IngestionResult:
            async with semaphore:
                return await self.ingest_company(ticker, years)

        tasks = [_limited(t) for t in tickers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        output: list[IngestionResult] = []
        for ticker, result in zip(tickers, results):
            if isinstance(result, Exception):
                logger.error("Batch ingestion failed for %s: %s", ticker, result)
                output.append(
                    IngestionResult(
                        ticker=ticker.upper(),
                        filings_processed=0,
                        chunks_created=0,
                        tokens_embedded=0,
                        duration_seconds=0.0,
                    )
                )
            else:
                output.append(result)

        return output
