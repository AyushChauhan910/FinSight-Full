import logging
import re
import uuid
from typing import Any

from langchain_text_splitters import RecursiveCharacterTextSplitter
from pydantic import BaseModel

logger = logging.getLogger(__name__)

SECTION_PATTERNS: dict[str, re.Pattern[str]] = {
    "Risk Factors": re.compile(
        r"(?:item\s*1a[\.\s]*:?[\s]*risk\s*factors|"
        r"risk\s*factors)",
        re.IGNORECASE,
    ),
    "MD&A": re.compile(
        r"(?:item\s*7[\.\s]*:?[\s]*management.s\s*discussion\s*and\s*analysis|"
        r"management.s\s*discussion\s*and\s*analysis\s*of\s*financial\s*(?:condition|results))",
        re.IGNORECASE,
    ),
    "Financial Statements": re.compile(
        r"(?:item\s*8[\.\s]*:?[\s]*financial\s*statements|"
        r"consolidated\s*balance\s*sheets|"
        r"consolidated\s*statements?\s*of\s*(?:income|operations|earnings))",
        re.IGNORECASE,
    ),
    "Business Overview": re.compile(
        r"(?:item\s*1[\.\s]*:?[\s]*(?:business|description\s*of\s*(?:the\s*)?business)|"
        r"business\s*overview)",
        re.IGNORECASE,
    ),
}

BOILERPLATE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^table\s+of\s+contents?$", re.IGNORECASE),
    re.compile(r"^signatures?\s*$", re.IGNORECASE),
    re.compile(r"^exhibit\s+index$", re.IGNORECASE),
    re.compile(r"^exhibit\s+\d+", re.IGNORECASE),
    re.compile(r"^pursuant\s+to\s+(?:section|the)", re.IGNORECASE),
    re.compile(r"^date:\s*\w+", re.IGNORECASE),
    re.compile(r"^signature\s+page$", re.IGNORECASE),
]

MIN_BOILERPLATE_LINES = 5


class ChunkMetadata(BaseModel):
    ticker: str
    form_type: str
    filing_date: str
    section: str
    token_count: int


class DocumentChunk(BaseModel):
    chunk_id: str
    text: str
    metadata: ChunkMetadata


class DocumentProcessor:
    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
    ):
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

    def _detect_section(self, text: str) -> str:
        for section_name, pattern in SECTION_PATTERNS.items():
            if pattern.search(text):
                return section_name
        return "General"

    def _estimate_tokens(self, text: str) -> int:
        return max(1, len(text) // 4)

    def _filter_boilerplate(self, text: str) -> str:
        lines = text.split("\n")
        filtered: list[str] = []
        i = 0

        while i < len(lines):
            line = lines[i].strip()
            is_boilerplate = False

            for pattern in BOILERPLATE_PATTERNS:
                if pattern.search(line):
                    is_boilerplate = True
                    break

            if is_boilerplate:
                skip_count = 0
                j = i + 1
                while j < len(lines) and skip_count < MIN_BOILERPLATE_LINES:
                    if lines[j].strip():
                        skip_count += 1
                    j += 1
                i = j
                continue

            if line:
                filtered.append(line)
            i += 1

        return "\n".join(filtered)

    def chunk_document(
        self,
        text: str,
        ticker: str,
        form_type: str,
        filing_date: str,
    ) -> list[DocumentChunk]:
        logger.info(
            "Processing document for %s %s (%s), %d chars",
            ticker,
            form_type,
            filing_date,
            len(text),
        )

        cleaned = self._filter_boilerplate(text)

        raw_chunks = self._splitter.split_text(cleaned)
        logger.info("Split into %d raw chunks", len(raw_chunks))

        chunks: list[DocumentChunk] = []
        for chunk_text in raw_chunks:
            chunk_text = chunk_text.strip()
            if not chunk_text:
                continue

            section = self._detect_section(chunk_text)
            token_count = self._estimate_tokens(chunk_text)

            chunk = DocumentChunk(
                chunk_id=str(uuid.uuid4()),
                text=chunk_text,
                metadata=ChunkMetadata(
                    ticker=ticker.upper(),
                    form_type=form_type,
                    filing_date=filing_date,
                    section=section,
                    token_count=token_count,
                ),
            )
            chunks.append(chunk)

        logger.info(
            "Created %d document chunks for %s %s",
            len(chunks),
            ticker,
            form_type,
        )
        return chunks
