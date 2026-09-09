from fastapi import APIRouter, HTTPException
from ...api.schemas.schemas import EvaluationResultResponse
from ...core.logging import logger
from ...evaluation.runners.benchmark_runner import BenchmarkRunner
from ...evaluation.reports.generator import ReportGenerator
from ...core.config import settings
import uuid
from datetime import datetime

router = APIRouter(tags=["evaluation"])

benchmark_runner = BenchmarkRunner()
report_generator = ReportGenerator()


@router.post("/evaluate", response_model=EvaluationResultResponse)
async def run_evaluation():
    try:
        run_id = str(uuid.uuid4())
        logger.info("Starting evaluation", run_id=run_id)

        if not benchmark_runner.retrieval_methods:
            benchmark_runner.retrieval_methods = {
                "dense_only": benchmark_runner._simulate_dense,
                "bm25_only": benchmark_runner._simulate_bm25,
                "hybrid": benchmark_runner._simulate_hybrid,
                "hybrid+reranker": benchmark_runner._simulate_hybrid_reranker,
                "hybrid+expansion+reranker": benchmark_runner._simulate_hybrid_expansion_reranker,
            }

        ablation_results = await benchmark_runner.run_ablation()
        latency_stats = benchmark_runner.get_latency_stats()
        failure_analysis = benchmark_runner.get_failure_analysis()

        combined_results = {
            "summary": ablation_results.get("summary", {}),
            "experiments": ablation_results.get("experiments", {}),
            "latency": latency_stats,
            "ablation_results": ablation_results.get("ablation_results", ablation_results),
        }
        report_generator.save_reports(combined_results)

        return EvaluationResultResponse(
            run_id=run_id,
            timestamp=datetime.utcnow().isoformat(),
            total_queries=len(benchmark_runner.get_queries()),
            metrics=ablation_results,
            ablation_results=ablation_results,
            failure_analysis=failure_analysis,
            latency_stats=latency_stats,
        )
    except Exception as e:
        logger.error("Evaluation failed", error=str(e))
        raise HTTPException(status_code=500, detail=(str(e) if settings.debug else 'Request failed. Check server logs with the X-Request-ID header.'))


@router.get("/evaluation/results", response_model=EvaluationResultResponse)
async def get_evaluation_results():
    try:
        results = report_generator.load_latest_results()
        if not results:
            raise HTTPException(status_code=404, detail="No evaluation results found")
        return EvaluationResultResponse(
            run_id="loaded-from-file",
            timestamp=results.get("generated_at", ""),
            total_queries=sum(
                exp.get("query_count", 0)
                for exp in results.get("experiments", {}).values()
            ) // max(len(results.get("experiments", {})), 1),
            metrics=results.get("summary", {}),
            ablation_results=results.get("ablation_results", results.get("experiments", {})),
            failure_analysis=results.get("failure_analysis", {}),
            latency_stats=results.get("latency", {}),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to load evaluation results", error=str(e))
        raise HTTPException(status_code=500, detail=(str(e) if settings.debug else 'Request failed. Check server logs with the X-Request-ID header.'))
