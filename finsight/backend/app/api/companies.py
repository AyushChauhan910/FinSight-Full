import logging
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.ingestion.vector_store import get_shared_instance
from app.models import CompanyListResponse, CompanyStatsResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/companies", tags=["companies"])


def _get_chroma_client():
    import chromadb
    persist_dir = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
    return chromadb.PersistentClient(path=persist_dir)


def _get_collection_stats_safe(ticker: str) -> dict | None:
    """Get collection stats using raw ChromaDB — no embedding model needed."""
    try:
        client = _get_chroma_client()
        collection_name = f"finsight_{ticker.lower()}"
        try:
            collection = client.get_collection(collection_name)
        except Exception:
            return None

        count = collection.count()
        if count == 0:
            return None

        all_docs = collection.get(include=["metadatas"])
        total_tokens = 0
        filing_dates: set[str] = set()
        form_types: set[str] = set()
        sections: set[str] = set()
        for meta in all_docs.get("metadatas", []):
            if meta:
                total_tokens += meta.get("token_count", 0)
                if meta.get("filing_date"):
                    filing_dates.add(meta["filing_date"])
                if meta.get("form_type"):
                    form_types.add(meta["form_type"])
                if meta.get("section"):
                    sections.add(meta["section"])

        return {
            "document_count": count,
            "total_tokens": total_tokens,
            "filing_dates": sorted(filing_dates),
            "form_types": sorted(form_types),
            "sections": sorted(sections),
        }
    except Exception as e:
        logger.warning("Failed to get stats for %s: %s", ticker, e)
    return None


@router.get("/", response_model=CompanyListResponse)
async def list_companies():
    try:
        client = _get_chroma_client()
        collections = client.list_collections()

        tickers = set()
        for col in collections:
            if col.name.startswith("finsight_"):
                ticker = col.name.replace("finsight_", "").upper()
                tickers.add(ticker)

        companies = []
        for ticker in sorted(tickers):
            stats = _get_collection_stats_safe(ticker)
            if stats:
                companies.append(
                    CompanyStatsResponse(
                        ticker=ticker,
                        document_count=stats["document_count"],
                        total_tokens=stats["total_tokens"],
                        filing_dates=stats["filing_dates"],
                        form_types=stats["form_types"],
                        sections=stats["sections"],
                    )
                )

        return CompanyListResponse(companies=companies)

    except Exception as e:
        logger.error("Failed to list companies: %s", e)
        return CompanyListResponse(companies=[])


@router.get("/{ticker}/stats", response_model=CompanyStatsResponse)
async def get_company_stats(ticker: str):
    ticker = ticker.upper()

    try:
        stats = _get_collection_stats_safe(ticker)

        if not stats:
            raise HTTPException(
                status_code=404,
                detail=f"No data found for {ticker}. Run ingestion first.",
            )

        return CompanyStatsResponse(
            ticker=ticker,
            document_count=stats["document_count"],
            total_tokens=stats["total_tokens"],
            filing_dates=stats["filing_dates"],
            form_types=stats["form_types"],
            sections=stats["sections"],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get stats for %s: %s", ticker, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{ticker}")
async def delete_company(ticker: str):
    ticker = ticker.upper()

    try:
        vs = get_shared_instance()
        vs.delete_company(ticker)
        return {"message": f"Deleted all data for {ticker}"}

    except Exception as e:
        logger.error("Failed to delete %s: %s", ticker, e)
        raise HTTPException(status_code=500, detail=str(e))
