import argparse
import asyncio
import sys
import time
from pathlib import Path

import structlog

from src.evaluation.datasets.synthetic import generate_synthetic_dataset
from src.evaluation.reports.generator import ReportGenerator
from src.evaluation.runners.benchmark_runner import BenchmarkRunner

logger = structlog.get_logger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Run RAG benchmark with timing")
    parser.add_argument(
        "--num-queries",
        type=int,
        default=35,
        help="Number of queries to evaluate",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="reports",
        help="Directory to save reports",
    )
    parser.add_argument(
        "--ablation",
        action="store_true",
        help="Run ablation study",
    )
    args = parser.parse_args()

    dataset = generate_synthetic_dataset(args.num_queries)
    runner = BenchmarkRunner(num_queries=args.num_queries)
    generator = ReportGenerator(output_dir=args.output_dir)

    wall_start = time.perf_counter()

    if args.ablation:
        logger.info("Starting timed ablation benchmark", num_queries=args.num_queries)
        results = asyncio.run(runner.run_ablation(dataset))
    else:
        logger.info("Starting timed benchmark", num_queries=args.num_queries)
        results = asyncio.run(runner.run(dataset))

    wall_ms = (time.perf_counter() - wall_start) * 1000

    generator.save_reports(results)

    summary = results.get("summary", {})
    print("\n" + "=" * 60)
    print("BENCHMARK RESULTS (with timing)")
    print("=" * 60)
    for method, metrics in summary.items():
        print(f"\n{method}:")
        for metric, value in metrics.items():
            print(f"  {metric}: {value:.4f}")

    latency = results.get("latency", {})
    if latency:
        print("\nLatency:")
        for method, stats in latency.items():
            mean = stats.get("mean")
            p50 = stats.get("p50")
            p95 = stats.get("p95")
            p99 = stats.get("p99")
            print(f"  {method}: mean={mean:.2f}ms, p50={p50:.2f}ms, p95={p95:.2f}ms, p99={p99:.2f}ms")

    print(f"\nTotal wall time: {wall_ms:.2f}ms")

    failure = runner.get_failure_analysis()
    if failure.get("total_failures", 0) > 0:
        print(f"Failures: {failure['total_failures']} / {failure['total_queries_run']}")

    print("=" * 60 + "\n")
    logger.info("Timed benchmark complete", wall_ms=round(wall_ms, 2), output_dir=args.output_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
