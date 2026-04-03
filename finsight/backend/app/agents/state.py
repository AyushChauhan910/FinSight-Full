from typing import TypedDict


class ResearchState(TypedDict, total=False):
    ticker: str
    company_name: str
    query: str
    retrieved_chunks: list[dict]
    sub_questions: list[str]
    draft_answer: str
    validated_answer: str
    numerical_facts: list[dict]
    inconsistencies: list[dict]
    report_sections: dict
    messages: list[dict]
    iteration_count: int
    max_iterations: int
