import asyncio
import json
import logging
import os
import re
from pathlib import Path
from urllib.parse import quote

import httpx
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()

logger = logging.getLogger(__name__)

DATA_DIR = Path("./data/raw")
SEC_SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_USER_AGENT = os.getenv("SEC_USER_AGENT", "FinSight contact@finsight.ai")

_ticker_to_cik: dict[str, str] = {}


class FilingMetadata(BaseModel):
    ticker: str
    cik: str
    form_type: str
    filing_date: str
    accession_number: str
    url: str


class RateLimiter:
    def __init__(self, max_per_second: int = 10):
        self._semaphore = asyncio.Semaphore(max_per_second)
        self._interval = 1.0 / max_per_second

    async def acquire(self):
        async with self._semaphore:
            await asyncio.sleep(self._interval)


class SECFetcher:
    def __init__(self):
        self._rate_limiter = RateLimiter(max_per_second=10)
        self._headers = {
            "User-Agent": SEC_USER_AGENT,
            "Accept": "application/json",
        }
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(
            headers=self._headers,
            timeout=30.0,
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, *args):
        if self._client:
            await self._client.aclose()
            self._client = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("SECFetcher must be used as an async context manager")
        return self._client

    async def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        await self._rate_limiter.acquire()
        client = self._get_client()
        response = await client.request(method, url, **kwargs)
        response.raise_for_status()
        return response

    async def _load_ticker_mapping(self) -> dict[str, str]:
        global _ticker_to_cik
        if _ticker_to_cik:
            return _ticker_to_cik

        response = await self._request("GET", SEC_COMPANY_TICKERS_URL)
        data = response.json()

        for entry in data.values():
            ticker = entry.get("ticker", "").upper()
            cik = str(entry.get("cik_str", ""))
            if ticker and cik:
                _ticker_to_cik[ticker] = cik

        logger.info("Loaded %d ticker-to-CIK mappings", len(_ticker_to_cik))
        return _ticker_to_cik

    async def get_cik(self, ticker: str) -> str:
        ticker = ticker.upper().strip()

        mapping = await self._load_ticker_mapping()

        if ticker in mapping:
            cik = mapping[ticker]
            logger.info("Resolved ticker %s to CIK %s", ticker, cik)
            return cik

        raise ValueError(f"Could not find CIK for ticker: {ticker}")

    async def get_filings(
        self,
        ticker: str,
        form_types: list[str] | None = None,
        limit: int = 10,
    ) -> list[FilingMetadata]:
        if form_types is None:
            form_types = ["10-K", "10-Q"]

        cik = await self.get_cik(ticker)
        cik_padded = cik.zfill(10)

        url = SEC_SUBMISSIONS_URL.format(cik=cik_padded)
        response = await self._request("GET", url)
        data = response.json()

        recent = data.get("filings", {}).get("recent", {})
        if not recent:
            logger.warning("No filings found for %s", ticker)
            return []

        filings: list[FilingMetadata] = []
        form_list = recent.get("form", [])
        date_list = recent.get("filingDate", [])
        accession_list = recent.get("accessionNumber", [])
        primary_docs = recent.get("primaryDocument", [])

        for i in range(len(form_list)):
            if form_list[i] not in form_types:
                continue

            accession = accession_list[i].replace("-", "")
            doc = primary_docs[i]
            filing_url = (
                f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{doc}"
            )

            filings.append(
                FilingMetadata(
                    ticker=ticker.upper(),
                    cik=cik,
                    form_type=form_list[i],
                    filing_date=date_list[i],
                    accession_number=accession_list[i],
                    url=filing_url,
                )
            )

            if len(filings) >= limit:
                break

        logger.info(
            "Found %d filings for %s (limited to %d)", len(filings), ticker, limit
        )
        return filings

    def _cache_path(self, ticker: str, accession_number: str) -> Path:
        return DATA_DIR / ticker.upper() / f"{accession_number}.txt"

    def _is_cached(self, ticker: str, accession_number: str) -> bool:
        return self._cache_path(ticker, accession_number).exists()

    def _read_cache(self, ticker: str, accession_number: str) -> str | None:
        path = self._cache_path(ticker, accession_number)
        if path.exists():
            logger.info("Cache hit for %s / %s", ticker, accession_number)
            return path.read_text(encoding="utf-8")
        return None

    def _write_cache(self, ticker: str, accession_number: str, text: str):
        path = self._cache_path(ticker, accession_number)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        logger.info("Cached %s / %s to %s", ticker, accession_number, path)

    def _strip_html(self, raw: str) -> str:
        try:
            soup = BeautifulSoup(raw, "lxml")
        except Exception:
            soup = BeautifulSoup(raw, "html.parser")

        for tag in soup(["script", "style", "head", "meta", "link"]):
            tag.decompose()

        text = soup.get_text(separator="\n")

        lines = text.split("\n")
        cleaned = []
        for line in lines:
            stripped = line.strip()
            if stripped:
                cleaned.append(stripped)

        text = "\n".join(cleaned)

        text = re.sub(r"\n{3,}", "\n\n", text)

        return text.strip()

    async def download_filing(self, filing: FilingMetadata) -> str:
        cached = self._read_cache(filing.ticker, filing.accession_number)
        if cached is not None:
            return cached

        logger.info(
            "Downloading %s %s for %s from %s",
            filing.form_type,
            filing.filing_date,
            filing.ticker,
            filing.url,
        )

        response = await self._request("GET", filing.url)
        raw = response.text

        text = self._strip_html(raw)

        self._write_cache(filing.ticker, filing.accession_number, text)

        logger.info(
            "Downloaded and parsed %s %s for %s (%d chars)",
            filing.form_type,
            filing.filing_date,
            filing.ticker,
            len(text),
        )

        return text
