import json
import logging
import os
import re
import time

from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.prompts import (
    ANALYST_PROMPT,
    QUERY_DECOMPOSER_PROMPT,
    REPORT_GENERATOR_PROMPT,
    VALIDATOR_PROMPT,
)
from app.agents.state import ResearchState
from app.agents.report_format import split_report_by_markdown_headers
from app.agents.tools import (
    calculate_yoy_change,
    fetch_current_price,
    retrieve_financial_data,
    validate_number,
)
from app.ingestion.vector_store import VectorStoreManager, get_shared_instance

load_dotenv()

logger = logging.getLogger(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

_llm: ChatGroq | None = None
def _get_vs() -> VectorStoreManager:
    return get_shared_instance()


def _get_llm() -> ChatGroq:
    global _llm
    if _llm is None:
        _llm = ChatGroq(
            model="llama-3.3-70b-versatile",
            api_key=GROQ_API_KEY,
            temperature=0,
            max_tokens=4096,
        )
    return _llm


def _strip_json_fences(content: str) -> str:
    content = content.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        if lines[-1].strip() == "```":
            content = "\n".join(lines[1:-1]).strip()
        elif len(lines) > 1:
            content = "\n".join(lines[1:]).strip()
    return content


def _extract_between_tags(text: str, tag: str) -> str | None:
    pattern = rf"<{tag}>(.*?)</{tag}>"
    match = re.search(pattern, text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return None


def query_decomposer_node(state: ResearchState) -> ResearchState:
    llm = _get_llm()

    formatted = QUERY_DECOMPOSER_PROMPT.format_messages(
        company_name=state.get("company_name", state["ticker"]),
        ticker=state["ticker"],
        query=state["query"],
    )

    response = llm.invoke(formatted)
    content = _strip_json_fences(response.content)

    try:
        sub_questions = json.loads(content)
    except json.JSONDecodeError:
        sub_questions = [state["query"]]

    if not isinstance(sub_questions, list):
        sub_questions = [state["query"]]

    sub_questions = sub_questions[:5]

    logger.info(
        "Decomposed query for %s into %d sub-questions",
        state["ticker"],
        len(sub_questions),
    )

    return {
        **state,
        "sub_questions": sub_questions,
        "iteration_count": state.get("iteration_count", 0),
    }


def retriever_node(state: ResearchState) -> ResearchState:
    ticker = state["ticker"]
    sub_questions = state.get("sub_questions", [state["query"]])

    vs = _get_vs()
    all_chunks: dict[str, dict] = {}

    for question in sub_questions:
        try:
            retrieved = vs.similarity_search(
                query=question,
                ticker=ticker,
                k=5,
                filter_section=None,
                use_mmr=True,
            )
            logger.info(
                "Retrieved %d chunks for question: %s",
                len(retrieved),
                question[:50],
            )
            for rc in retrieved:
                key = (rc.chunk_id or "").strip() or f"hash_{hash(rc.text) & 0xFFFFFFFF:x}"
                if key in all_chunks:
                    continue
                meta = dict(rc.metadata) if rc.metadata else {}
                all_chunks[key] = {
                    "chunk_id": rc.chunk_id or key,
                    "text": rc.text,
                    "metadata": meta,
                    "source_question": question,
                }
        except Exception as e:
            logger.error("Retrieval failed for question '%s': %s", question, e)

    chunks_list = list(all_chunks.values())
    logger.info(
        "Retrieved %d unique chunks for %s",
        len(chunks_list),
        ticker,
    )

    return {**state, "retrieved_chunks": chunks_list}


def analyst_node(state: ResearchState) -> ResearchState:
    llm = _get_llm()
    chunks = state.get("retrieved_chunks", [])

    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        context_parts.append(f"[Doc {i}]: {chunk['text']}")
    context = "\n\n".join(context_parts)

    formatted = ANALYST_PROMPT.format_messages(
        company_name=state.get("company_name", state["ticker"]),
        ticker=state["ticker"],
        query=state["query"],
        context=context,
    )

    response = llm.invoke(formatted)
    content = response.content

    numerical_facts = []
    facts_json = _extract_between_tags(content, "numerical_facts")
    if facts_json:
        try:
            parsed = json.loads(facts_json)
            if isinstance(parsed, list):
                for item in parsed:
                    numerical_facts.append({
                        "claim": item.get("claim", ""),
                        "doc_id": item.get("doc_id", ""),
                        "value": item.get("value"),
                        "unit": item.get("unit", ""),
                        "verified": False,
                    })
                content = re.sub(
                    r"<numerical_facts>.*?</numerical_facts>",
                    "",
                    content,
                    flags=re.DOTALL,
                ).strip()
        except json.JSONDecodeError:
            logger.warning("Failed to parse numerical_facts JSON block")

    logger.info(
        "Analyst produced %d chars with %d numerical facts for %s",
        len(content),
        len(numerical_facts),
        state["ticker"],
    )

    return {
        **state,
        "draft_answer": content,
        "numerical_facts": numerical_facts,
    }


def validator_node(state: ResearchState) -> ResearchState:
    ticker = state["ticker"]
    numerical_facts = state.get("numerical_facts", [])
    inconsistencies: list[dict] = []

    for fact in numerical_facts:
        if not isinstance(fact, dict):
            continue
        if fact.get("verified"):
            continue

        claim = fact.get("claim", "")
        if not claim:
            continue

        try:
            result_str = validate_number.invoke({
                "claim": claim,
                "ticker": ticker,
            })
            validation = json.loads(result_str)

            if validation.get("status") == "UNVERIFIABLE":
                inconsistencies.append({
                    "claim": claim,
                    "issue": "Could not verify against source documents",
                    "source_text": "",
                })
                continue

            source_text = validation.get("source_text", "")

            formatted = VALIDATOR_PROMPT.format_messages(
                claim=claim,
                ticker=ticker,
                source_text=source_text,
            )

            llm = _get_llm()
            llm_response = llm.invoke(formatted)
            llm_result_str = _strip_json_fences(llm_response.content)

            try:
                llm_result = json.loads(llm_result_str)
                if not llm_result.get("is_accurate", True):
                    inconsistencies.append({
                        "claim": claim,
                        "issue": llm_result.get("discrepancy", "Accuracy check failed"),
                        "corrected_value": llm_result.get("corrected_value"),
                        "confidence": llm_result.get("confidence", "unknown"),
                        "source_text": llm_result.get("source_reference", ""),
                    })
            except json.JSONDecodeError:
                pass

        except Exception as e:
            logger.error("Validation failed for claim '%s': %s", claim, e)

    for fact in numerical_facts:
        if isinstance(fact, dict):
            fact["verified"] = True

    iteration = state.get("iteration_count", 0) + 1
    max_iter = state.get("max_iterations", 3)

    should_reiterate = len(inconsistencies) > 0 and iteration < max_iter

    if should_reiterate:
        logger.warning(
            "Found %d inconsistencies for %s, re-running analyst (iteration %d/%d)",
            len(inconsistencies),
            ticker,
            iteration,
            max_iter,
        )
        return {
            **state,
            "numerical_facts": numerical_facts,
            "inconsistencies": inconsistencies,
            "iteration_count": iteration,
        }

    logger.info(
        "Validation complete for %s: %d inconsistencies found",
        ticker,
        len(inconsistencies),
    )

    return {
        **state,
        "numerical_facts": numerical_facts,
        "inconsistencies": inconsistencies,
        "validated_answer": state.get("draft_answer", ""),
        "iteration_count": iteration,
    }


def report_generator_node(state: ResearchState) -> ResearchState:
    llm = _get_llm()

    answer = state.get("validated_answer", state.get("draft_answer", ""))
    query = state["query"]
    ticker = state["ticker"]
    company = state.get("company_name", ticker)
    inconsistencies = state.get("inconsistencies", [])

    inconsistency_text = ""
    if inconsistencies:
        items = "\n".join(f"- {inc['claim']}: {inc['issue']}" for inc in inconsistencies)
        inconsistency_text = f"Data inconsistencies found:\n{items}"

    formatted = REPORT_GENERATOR_PROMPT.format_messages(
        company_name=company,
        ticker=ticker,
        query=query,
        analyst_report=answer,
        inconsistencies=inconsistency_text,
    )

    response = llm.invoke(formatted)
    report = response.content

    report_sections = split_report_by_markdown_headers(report)
    for key in (
        "executive_summary",
        "key_metrics",
        "risk_factors",
        "yoy_analysis",
        "investment_thesis",
    ):
        report_sections.setdefault(key, "")
        report_sections[key] = (report_sections.get(key) or "").strip()

    logger.info("Generated structured report for %s", ticker)

    return {
        **state,
        "report_sections": report_sections,
    }
