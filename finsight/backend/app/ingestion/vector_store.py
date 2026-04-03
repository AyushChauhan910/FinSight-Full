import logging
import os
from pathlib import Path

import mlflow
from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from pydantic import BaseModel

from app.ingestion.document_processor import DocumentChunk

load_dotenv()

logger = logging.getLogger(__name__)

_shared_instance: "VectorStoreManager | None" = None


def get_shared_instance() -> "VectorStoreManager":
    """Return the process-wide singleton VectorStoreManager.
    The embedding model is loaded exactly once on first call.
    """
    global _shared_instance
    if _shared_instance is None:
        _shared_instance = VectorStoreManager()
    return _shared_instance

CHROMA_PERSIST_DIR = Path(os.getenv("CHROMA_PERSIST_DIR", "./chroma_db"))
OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"
OPENAI_COST_PER_1K_TOKENS = 0.00002


class RetrievedChunk(BaseModel):
    chunk_id: str
    text: str
    metadata: dict
    relevance_score: float


class VectorStoreManager:
    def __init__(self):
        self._embeddings = HuggingFaceEmbeddings(
            model_name="BAAI/bge-small-en-v1.5",
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True}
        )
        CHROMA_PERSIST_DIR.mkdir(parents=True, exist_ok=True)
        self._persist_dir = str(CHROMA_PERSIST_DIR)

    def _collection_name(self, ticker: str) -> str:
        return f"finsight_{ticker.lower()}"

    def _get_store(self, ticker: str) -> Chroma:
        return Chroma(
            collection_name=self._collection_name(ticker),
            embedding_function=self._embeddings,
            persist_directory=self._persist_dir,
        )

    def upsert_chunks(self, chunks: list[DocumentChunk]) -> dict:
        if not chunks:
            return {"upserted": 0, "tokens_embedded": 0, "cost_usd": 0.0}

        ticker = chunks[0].metadata.ticker
        store = self._get_store(ticker)

        texts = [c.text for c in chunks]
        ids = [c.chunk_id for c in chunks]
        metadatas = [
            {
                "ticker": c.metadata.ticker,
                "form_type": c.metadata.form_type,
                "filing_date": c.metadata.filing_date,
                "section": c.metadata.section,
                "token_count": c.metadata.token_count,
                "chunk_id": c.chunk_id,
            }
            for c in chunks
        ]

        total_tokens = sum(c.metadata.token_count for c in chunks)
        cost_usd = (total_tokens / 1000) * OPENAI_COST_PER_1K_TOKENS

        store.add_texts(texts=texts, metadatas=metadatas, ids=ids)

        logger.info(
            "Upserted %d chunks for %s (%d tokens, $%.6f)",
            len(chunks),
            ticker,
            total_tokens,
            cost_usd,
        )

        try:
            with mlflow.start_run(nested=True):
                mlflow.log_metric("tokens_embedded", total_tokens)
                mlflow.log_metric("embedding_cost_usd", cost_usd)
                mlflow.log_metric("chunks_upserted", len(chunks))
                mlflow.set_tag("ticker", ticker)
        except Exception:
            logger.debug("MLflow logging skipped (no active run)")

        return {
            "upserted": len(chunks),
            "tokens_embedded": total_tokens,
            "cost_usd": cost_usd,
        }

    def similarity_search(
        self,
        query: str,
        ticker: str,
        k: int = 8,
        filter_section: str | None = None,
        use_mmr: bool = False,
    ) -> list[RetrievedChunk]:
        store = self._get_store(ticker)

        search_kwargs: dict = {"k": k}
        if filter_section:
            search_kwargs["filter"] = {"section": filter_section}

        if use_mmr:
            search_kwargs["fetch_k"] = k * 4
            search_kwargs["lambda_mult"] = 0.5
            retriever = store.as_retriever(
                search_type="mmr",
                search_kwargs=search_kwargs,
            )
        else:
            retriever = store.as_retriever(
                search_type="similarity",
                search_kwargs=search_kwargs,
            )

        docs = retriever.invoke(query)

        results: list[RetrievedChunk] = []
        for doc in docs:
            score = doc.metadata.pop("relevance_score", 0.0)
            chunk_id = doc.metadata.pop("chunk_id", "")
            results.append(
                RetrievedChunk(
                    chunk_id=chunk_id,
                    text=doc.page_content,
                    metadata=doc.metadata,
                    relevance_score=score,
                )
            )

        logger.info(
            "Retrieved %d chunks for query on %s (mmr=%s)",
            len(results),
            ticker,
            use_mmr,
        )
        return results

    def get_collection_stats(self, ticker: str) -> dict:
        store = self._get_store(ticker)
        collection = store._collection
        count = collection.count()

        if count == 0:
            return {
                "document_count": 0,
                "total_tokens": 0,
                "filing_dates": [],
                "form_types": [],
                "sections": [],
            }

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

    def delete_company(self, ticker: str) -> None:
        store = self._get_store(ticker)
        collection = store._collection
        count = collection.count()
        collection.delete(where={})
        logger.info("Deleted %d documents for %s", count, ticker)
