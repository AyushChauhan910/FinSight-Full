import logging
import traceback
import uuid

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from app.agents.nodes import (
    analyst_node,
    query_decomposer_node,
    report_generator_node,
    retriever_node,
    validator_node,
)
from app.agents.report_format import build_structured_report
from app.agents.state import ResearchState
from pydantic import BaseModel

logger = logging.getLogger(__name__)


def _minimal_report(answer: str, ticker: str) -> dict:
    return {
        "executive_summary": (answer or "")[:1200] or f"No analysis available for {ticker}.",
        "key_metrics": [],
        "risk_factors": [],
        "yoy_analysis": [],
        "investment_thesis": {"bull_case": [], "bear_case": []},
    }


class AgentResult(BaseModel):
    answer: str
    report: dict
    report_markdown: str
    citations: list[dict]
    iterations_used: int
    tokens_used: int


def _should_retry(state: ResearchState) -> str:
    inconsistencies = state.get("inconsistencies", [])
    iteration = state.get("iteration_count", 0)
    max_iter = state.get("max_iterations", 3)

    if inconsistencies and iteration < max_iter:
        return "analyst"
    return "report_generator"


def _build_graph() -> StateGraph:
    graph = StateGraph(ResearchState)

    graph.add_node("query_decomposer", query_decomposer_node)
    graph.add_node("retriever", retriever_node)
    graph.add_node("analyst", analyst_node)
    graph.add_node("validator", validator_node)
    graph.add_node("report_generator", report_generator_node)

    graph.set_entry_point("query_decomposer")

    graph.add_edge("query_decomposer", "retriever")
    graph.add_edge("retriever", "analyst")
    graph.add_edge("analyst", "validator")

    graph.add_conditional_edges(
        "validator",
        _should_retry,
        {
            "analyst": "analyst",
            "report_generator": "report_generator",
        },
    )

    graph.add_edge("report_generator", END)

    return graph


_compiled_graph = None


def _get_compiled_graph():
    global _compiled_graph
    if _compiled_graph is None:
        checkpointer = MemorySaver()
        raw_graph = _build_graph()
        _compiled_graph = raw_graph.compile(checkpointer=checkpointer)
    return _compiled_graph


class FinSightAgent:
    async def run(self, ticker: str, query: str) -> AgentResult:
        graph = _get_compiled_graph()

        initial_state: ResearchState = {
            "ticker": ticker.upper(),
            "query": query,
            "retrieved_chunks": [],
            "sub_questions": [],
            "draft_answer": "",
            "validated_answer": "",
            "numerical_facts": [],
            "inconsistencies": [],
            "report_sections": {},
            "messages": [],
            "iteration_count": 0,
            "max_iterations": 3,
        }

        thread_id = str(uuid.uuid4())
        config = {"configurable": {"thread_id": thread_id}}

        logger.info("Starting agent for %s: %s", ticker, query)

        total_tokens = 0
        final_state: ResearchState = {}

        try:
            async for event in graph.astream(initial_state, config=config):
                for node_name, state_update in event.items():
                    logger.debug("Node %s completed", node_name)
                    if isinstance(state_update, dict):
                        final_state.update(state_update)
        except KeyError as e:
            tb = traceback.format_exc()
            logger.error("KeyError in graph execution for %s: %s\n%s", ticker, e, tb)
            msg = f"KeyError during analysis: {str(e)}\n\nTraceback:\n{tb}"
            return AgentResult(
                answer=msg,
                report=_minimal_report(msg, ticker),
                report_markdown="",
                citations=[],
                iterations_used=0,
                tokens_used=0,
            )
        except Exception as e:
            tb = traceback.format_exc()
            logger.error("Graph execution failed for %s: %s\n%s", ticker, e, tb)
            msg = f"Error during analysis: {str(e)}\n\nTraceback:\n{tb}"
            return AgentResult(
                answer=msg,
                report=_minimal_report(msg, ticker),
                report_markdown="",
                citations=[],
                iterations_used=0,
                tokens_used=0,
            )

        answer = final_state.get("validated_answer", "") or final_state.get(
            "draft_answer", ""
        )

        report_sections = final_state.get("report_sections", {}) or {}
        report_parts = []
        section_titles = {
            "executive_summary": "Executive Summary",
            "key_metrics": "Key Metrics",
            "risk_factors": "Risk Factors",
            "yoy_analysis": "Year-over-Year Analysis",
            "investment_thesis": "Investment Thesis",
        }
        for key, title in section_titles.items():
            content = report_sections.get(key, "")
            if content:
                report_parts.append(f"## {title}\n\n{content}")
        report_markdown = "\n\n".join(report_parts) if report_parts else answer

        structured_report = build_structured_report(
            report_sections, ticker, answer
        )

        citations: list[dict] = []
        for i, chunk in enumerate(final_state.get("retrieved_chunks", []), start=1):
            meta = chunk.get("metadata") or {}
            citations.append({
                "chunk_id": str(i),
                "text": (chunk.get("text") or "")[:4000],
                "metadata": {
                    "ticker": meta.get("ticker", ticker),
                    "form_type": meta.get("form_type", "N/A"),
                    "filing_date": meta.get("filing_date", "N/A"),
                    "section": meta.get("section", "N/A"),
                },
            })

        iterations = final_state.get("iteration_count", 1)

        result = AgentResult(
            answer=answer,
            report=structured_report,
            report_markdown=report_markdown,
            citations=citations[:20],
            iterations_used=iterations,
            tokens_used=total_tokens,
        )

        logger.info(
            "Agent completed for %s in %d iterations, %d citations",
            ticker,
            iterations,
            len(citations),
        )

        return result
