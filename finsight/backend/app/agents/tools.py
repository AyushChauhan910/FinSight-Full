import json
import logging

import yfinance as yf
from langchain_core.tools import tool

from app.ingestion.vector_store import VectorStoreManager, get_shared_instance

logger = logging.getLogger(__name__)

def _get_vs() -> VectorStoreManager:
    return get_shared_instance()


@tool
def retrieve_financial_data(ticker: str, query: str, section: str = "") -> str:
    """Retrieve relevant financial document chunks from SEC filings for a company.
    Use this to find specific financial data, metrics, or disclosures.
    Args:
        ticker: Stock ticker symbol (e.g., AAPL, MSFT)
        query: The specific financial question or data point to search for
        section: Optional section filter (Risk Factors, MD&A, Financial Statements, Business Overview)
    """
    try:
        vs = _get_vs()
        filter_section = section if section else None
        chunks = vs.similarity_search(
            query=query,
            ticker=ticker,
            k=5,
            filter_section=filter_section,
            use_mmr=True,
        )

        if not chunks:
            return f"No relevant documents found for {ticker} with query: {query}"

        results = []
        for i, chunk in enumerate(chunks, 1):
            results.append(
                f"[Doc {i}] (Section: {chunk.metadata.get('section', 'N/A')}, "
                f"Date: {chunk.metadata.get('filing_date', 'N/A')}):\n{chunk.text}"
            )

        return "\n\n".join(results)

    except Exception as e:
        logger.error("Error retrieving financial data: %s", e)
        return f"Error retrieving data for {ticker}: {str(e)}"


@tool
def calculate_yoy_change(current: float, previous: float) -> str:
    """Calculate year-over-year percentage change between two values.
    Args:
        current: The current period value
        previous: The previous period value
    """
    if previous == 0:
        return "Cannot calculate YoY change: previous value is zero"

    change = ((current - previous) / abs(previous)) * 100
    direction = "up" if change >= 0 else "down"
    arrow = "\u2b06\ufe0f" if change >= 0 else "\u2b07\ufe0f"

    return f"{arrow} {direction} {abs(change):.2f}% (from {previous:,.2f} to {current:,.2f})"


@tool
def validate_number(claim: str, ticker: str) -> str:
    """Validate a numerical claim against SEC filing data.
    Use this to verify that a specific number or metric is accurate.
    Args:
        claim: The numerical claim to verify (e.g., "Revenue was $394.3 billion in 2024")
        ticker: Stock ticker symbol
    """
    try:
        vs = _get_vs()
        chunks = vs.similarity_search(
            query=claim,
            ticker=ticker,
            k=3,
            use_mmr=False,
        )

        if not chunks:
            return json.dumps({
                "claim": claim,
                "status": "UNVERIFIABLE",
                "reason": "No source documents found to verify this claim",
            })

        combined_text = "\n".join(c.text for c in chunks)
        return json.dumps({
            "claim": claim,
            "status": "NEEDS_REVIEW",
            "source_text": combined_text[:2000],
            "documents_checked": len(chunks),
        })

    except Exception as e:
        logger.error("Error validating number: %s", e)
        return json.dumps({
            "claim": claim,
            "status": "ERROR",
            "reason": str(e),
        })


@tool
def fetch_current_price(ticker: str) -> str:
    """Fetch the current stock price and basic market statistics for a company.
    Args:
        ticker: Stock ticker symbol (e.g., AAPL, MSFT)
    """
    try:
        stock = yf.Ticker(ticker)
        info = stock.info

        price = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose")
        market_cap = info.get("marketCap")
        pe_ratio = info.get("trailingPE")
        week_52_high = info.get("fiftyTwoWeekHigh")
        week_52_low = info.get("fiftyTwoWeekLow")
        volume = info.get("volume") or info.get("regularMarketVolume")
        avg_volume = info.get("averageVolume")
        dividend_yield = info.get("dividendYield")

        result = {
            "ticker": ticker.upper(),
            "current_price": price,
            "market_cap": market_cap,
            "pe_ratio": pe_ratio,
            "52_week_high": week_52_high,
            "52_week_low": week_52_low,
            "volume": volume,
            "average_volume": avg_volume,
            "dividend_yield": f"{dividend_yield * 100:.2f}%" if dividend_yield else "N/A",
        }

        return json.dumps(result, default=str)

    except Exception as e:
        logger.error("Error fetching price for %s: %s", ticker, e)
        return json.dumps({
            "ticker": ticker.upper(),
            "error": str(e),
        })
