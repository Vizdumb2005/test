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

        ablation_results = benchmark_runner.run_ablation()
        latency_stats = benchmark_runner.get_latency_stats()
        failure_analysis = benchmark_runner.get_failure_analysis()

        report_generator.save_reports(
            run_id=run_id,
            ablation_results=ablation_results,
            latency_stats=latency_stats,
            failure_analysis=failure_analysis,
        )

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
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/evaluation/results", response_model=EvaluationResultResponse)
async def get_evaluation_results():
    try:
        results = report_generator.load_latest_results()
        if not results:
            raise HTTPException(status_code=404, detail="No evaluation results found")
        return EvaluationResultResponse(**results)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to load evaluation results", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
