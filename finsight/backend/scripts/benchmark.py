import asyncio
import json
import logging
import os
import re
import sys
import time
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path

import dotenv

dotenv.load_dotenv()

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.agents.graph import FinSightAgent
from app.ingestion.vector_store import VectorStoreManager

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

SCRIPT_DIR = Path(__file__).parent
QA_DATASET_PATH = SCRIPT_DIR / "qa_dataset.json"
RESULTS_PATH = SCRIPT_DIR / "benchmark_results.json"


@dataclass
class QuestionResult:
    question: str
    ground_truth: str
    predicted: str
    exact_match: bool
    fuzzy_score: float
    numerical_accuracy: bool
    latency_ms: float
    error: str | None = None


@dataclass
class BenchmarkResult:
    method: str
    total_questions: int
    exact_match_accuracy: float
    fuzzy_match_accuracy: float
    numerical_accuracy: float
    avg_latency_ms: float
    total_latency_ms: float
    per_question: list[QuestionResult] = field(default_factory=list)


def extract_numbers(text: str) -> list[float]:
    pattern = r"[\$]?(\d+(?:\.\d+)?)\s*(?:billion|million|B|M|%)?"
    matches = re.findall(pattern, text, re.IGNORECASE)
    numbers = []
    for m in matches:
        try:
            numbers.append(float(m))
        except ValueError:
            continue
    return numbers


def numbers_within_tolerance(pred: str, truth: str, tolerance: float = 0.02) -> bool:
    pred_nums = extract_numbers(pred)
    truth_nums = extract_numbers(truth)

    if not truth_nums:
        return True

    for t_num in truth_nums:
        if t_num == 0:
            continue
        matched = False
        for p_num in pred_nums:
            if abs(p_num - t_num) / abs(t_num) <= tolerance:
                matched = True
                break
        if not matched:
            return False
    return True


def exact_match(predicted: str, ground_truth: str, aliases: list[str] | None = None) -> bool:
    pred_clean = predicted.lower().strip()
    truth_clean = ground_truth.lower().strip()

    if truth_clean in pred_clean:
        return True

    if aliases:
        for alias in aliases:
            if alias.lower().strip() in pred_clean:
                return True

    return False


def fuzzy_score(predicted: str, ground_truth: str) -> float:
    pred_nums = extract_numbers(predicted)
    truth_nums = extract_numbers(ground_truth)

    if truth_nums and pred_nums:
        ratio = SequenceMatcher(
            None,
            " ".join(f"{n:.2f}" for n in pred_nums),
            " ".join(f"{n:.2f}" for n in truth_nums),
        ).ratio()
        return ratio

    return SequenceMatcher(None, predicted.lower(), ground_truth.lower()).ratio()


class RAGBenchmark:
    def __init__(self):
        self.vs = VectorStoreManager()
        self.agent = FinSightAgent()
        self.dataset = self._load_dataset()

    def _load_dataset(self) -> list[dict]:
        with open(QA_DATASET_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    def evaluate_naive_rag(self, questions: list[dict] | None = None) -> BenchmarkResult:
        if questions is None:
            questions = self.dataset

        results: list[QuestionResult] = []

        logger.info("Running naive RAG evaluation on %d questions", len(questions))

        for i, qa in enumerate(questions):
            question = qa["question"]
            ground_truth = qa["answer"]
            aliases = qa.get("answer_aliases", [])
            section = qa.get("section", "")

            start = time.perf_counter()
            try:
                chunks = self.vs.similarity_search(
                    query=question,
                    ticker="AAPL",
                    k=5,
                    filter_section=section if section else None,
                    use_mmr=False,
                )

                if chunks:
                    predicted = chunks[0].text[:1000]
                else:
                    predicted = "No relevant documents found"

                error = None
            except Exception as e:
                predicted = ""
                error = str(e)
                logger.error("Naive RAG error on question %d: %s", i, e)

            elapsed = (time.perf_counter() - start) * 1000

            em = exact_match(predicted, ground_truth, aliases)
            fs = fuzzy_score(predicted, ground_truth)
            na = numbers_within_tolerance(predicted, ground_truth)

            results.append(
                QuestionResult(
                    question=question,
                    ground_truth=ground_truth,
                    predicted=predicted[:200],
                    exact_match=em,
                    fuzzy_score=fs,
                    numerical_accuracy=na,
                    latency_ms=elapsed,
                    error=error,
                )
            )

            logger.info(
                "Naive RAG [%d/%d] EM=%s FUZZY=%.2f NA=%s",
                i + 1,
                len(questions),
                em,
                fs,
                na,
            )

        return self._aggregate_results("Naive RAG", results)

    async def evaluate_finsight(self, questions: list[dict] | None = None) -> BenchmarkResult:
        if questions is None:
            questions = self.dataset

        results: list[QuestionResult] = []

        logger.info("Running FinSight evaluation on %d questions", len(questions))

        for i, qa in enumerate(questions):
            question = qa["question"]
            ground_truth = qa["answer"]
            aliases = qa.get("answer_aliases", [])

            # Rate limit delay for Groq free tier (6000 tokens/min)
            if i > 0:
                time.sleep(1)

            start = time.perf_counter()
            try:
                agent_result = await self.agent.run("AAPL", question)
                predicted = agent_result.answer
                error = None
            except Exception as e:
                predicted = ""
                error = str(e)
                logger.error("FinSight error on question %d: %s", i, e)

            elapsed = (time.perf_counter() - start) * 1000

            em = exact_match(predicted, ground_truth, aliases)
            fs = fuzzy_score(predicted, ground_truth)
            na = numbers_within_tolerance(predicted, ground_truth)

            results.append(
                QuestionResult(
                    question=question,
                    ground_truth=ground_truth,
                    predicted=predicted[:500],
                    exact_match=em,
                    fuzzy_score=fs,
                    numerical_accuracy=na,
                    latency_ms=elapsed,
                    error=error,
                )
            )

            logger.info(
                "FinSight [%d/%d] EM=%s FUZZY=%.2f NA=%s",
                i + 1,
                len(questions),
                em,
                fs,
                na,
            )

        return self._aggregate_results("FinSight Agent", results)

    def _aggregate_results(self, method: str, results: list[QuestionResult]) -> BenchmarkResult:
        total = len(results)
        if total == 0:
            return BenchmarkResult(
                method=method,
                total_questions=0,
                exact_match_accuracy=0.0,
                fuzzy_match_accuracy=0.0,
                numerical_accuracy=0.0,
                avg_latency_ms=0.0,
                total_latency_ms=0.0,
                per_question=results,
            )

        em_count = sum(1 for r in results if r.exact_match)
        fuzzy_avg = sum(r.fuzzy_score for r in results) / total
        na_count = sum(1 for r in results if r.numerical_accuracy)
        avg_latency = sum(r.latency_ms for r in results) / total
        total_latency = sum(r.latency_ms for r in results)

        return BenchmarkResult(
            method=method,
            total_questions=total,
            exact_match_accuracy=round(em_count / total * 100, 1),
            fuzzy_match_accuracy=round(fuzzy_avg * 100, 1),
            numerical_accuracy=round(na_count / total * 100, 1),
            avg_latency_ms=round(avg_latency, 1),
            total_latency_ms=round(total_latency, 1),
            per_question=results,
        )

    def save_results(self, naive: BenchmarkResult, finsight: BenchmarkResult):
        output = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "ticker": "AAPL",
            "dataset_size": len(self.dataset),
            "results": {
                "naive_rag": {
                    "method": naive.method,
                    "total_questions": naive.total_questions,
                    "exact_match_accuracy": naive.exact_match_accuracy,
                    "fuzzy_match_accuracy": naive.fuzzy_match_accuracy,
                    "numerical_accuracy": naive.numerical_accuracy,
                    "avg_latency_ms": naive.avg_latency_ms,
                    "total_latency_ms": naive.total_latency_ms,
                },
                "finsight": {
                    "method": finsight.method,
                    "total_questions": finsight.total_questions,
                    "exact_match_accuracy": finsight.exact_match_accuracy,
                    "fuzzy_match_accuracy": finsight.fuzzy_match_accuracy,
                    "numerical_accuracy": finsight.numerical_accuracy,
                    "avg_latency_ms": finsight.avg_latency_ms,
                    "total_latency_ms": finsight.total_latency_ms,
                },
            },
            "improvement": {
                "exact_match": round(
                    finsight.exact_match_accuracy - naive.exact_match_accuracy, 1
                ),
                "fuzzy_match": round(
                    finsight.fuzzy_match_accuracy - naive.fuzzy_match_accuracy, 1
                ),
                "numerical": round(
                    finsight.numerical_accuracy - naive.numerical_accuracy, 1
                ),
            },
            "per_question": [
                {
                    "question": r.question,
                    "ground_truth": r.ground_truth,
                    "naive_exact_match": naive.per_question[i].exact_match if i < len(naive.per_question) else None,
                    "finsight_exact_match": r.exact_match,
                    "naive_fuzzy": naive.per_question[i].fuzzy_score if i < len(naive.per_question) else None,
                    "finsight_fuzzy": r.fuzzy_score,
                }
                for i, r in enumerate(finsight.per_question)
            ],
        }

        with open(RESULTS_PATH, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2)

        logger.info("Results saved to %s", RESULTS_PATH)


def print_results_table(naive: BenchmarkResult, finsight: BenchmarkResult):
    col_w = 18
    header = f"{'Metric':<25} {'Naive RAG':>{col_w}} {'FinSight':>{col_w}} {'Improvement':>{col_w}}"
    separator = "-" * (25 + col_w * 3 + 3)

    print("\n" + "=" * len(header))
    print("  FINSIGHT BENCHMARK RESULTS")
    print(f"  Dataset: Apple (AAPL) 10-K 2023 | Questions: {naive.total_questions}")
    print("=" * len(header))
    print()
    print(header)
    print(separator)
    print(
        f"{'Exact Match Accuracy':<25} {naive.exact_match_accuracy:>{col_w - 1}.1f}% {finsight.exact_match_accuracy:>{col_w - 1}.1f}% {finsight.exact_match_accuracy - naive.exact_match_accuracy:>+{col_w - 1}.1f}%"
    )
    print(
        f"{'Fuzzy Match Score':<25} {naive.fuzzy_match_accuracy:>{col_w - 1}.1f}% {finsight.fuzzy_match_accuracy:>{col_w - 1}.1f}% {finsight.fuzzy_match_accuracy - naive.fuzzy_match_accuracy:>+{col_w - 1}.1f}%"
    )
    print(
        f"{'Numerical Accuracy':<25} {naive.numerical_accuracy:>{col_w - 1}.1f}% {finsight.numerical_accuracy:>{col_w - 1}.1f}% {finsight.numerical_accuracy - naive.numerical_accuracy:>+{col_w - 1}.1f}%"
    )
    print(
        f"{'Avg Latency (ms)':<25} {naive.avg_latency_ms:>{col_w}.1f} {finsight.avg_latency_ms:>{col_w}.1f} {finsight.avg_latency_ms - naive.avg_latency_ms:>+{col_w}.1f}"
    )
    print(separator)
    print()

    resume_exact = f"{finsight.exact_match_accuracy:.0f}% answer accuracy vs {naive.exact_match_accuracy:.0f}% naive RAG baseline"
    print(f"  RESUME METRIC: {resume_exact}")
    print()


async def main():
    print("\n  Starting FinSight Benchmark...")
    print("  Ensure AAPL data is ingested before running.\n")

    benchmark = RAGBenchmark()

    subset_size = min(15, len(benchmark.dataset))
    import random
    random.seed(42)
    test_questions = random.sample(benchmark.dataset, subset_size)

    print(f"  Evaluating {subset_size} questions (random subset for speed)...\n")

    print("  [1/2] Running Naive RAG baseline...")
    naive_result = benchmark.evaluate_naive_rag(test_questions)

    print(f"\n  [2/2] Running FinSight Agent...")
    finsight_result = await benchmark.evaluate_finsight(test_questions)

    print_results_table(naive_result, finsight_result)

    benchmark.save_results(naive_result, finsight_result)

    return naive_result, finsight_result


if __name__ == "__main__":
    asyncio.run(main())
