"""Benchmark job runner: executes the real benchmark script in the background.

POST /api/benchmark/run -> {job_id, status: queued/running}
GET  /api/benchmark/jobs/{job_id} -> status, progress hint, log tail
GET  /api/benchmark/jobs -> recent jobs

The job runs `python -m scripts.benchmark` (real Qdrant/BM25/models) as a
subprocess so long CPU-heavy runs never block the API event loop. If Qdrant
is unreachable the job fails fast with actionable log output.
"""

from __future__ import annotations

import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.core.config import settings
from src.core.logging import logger

router = APIRouter(tags=["evaluation"])


class BenchmarkRunRequest(BaseModel):
    num_queries: int = Field(default=35, ge=1, le=200)
    runs: int = Field(default=1, ge=1, le=5)
    rebuild_index: bool = False
    device: Optional[str] = Field(default=None, pattern="^(cpu|cuda)?$")
    dense_top_k: Optional[int] = Field(default=None, ge=1, le=50)
    sparse_top_k: Optional[int] = Field(default=None, ge=1, le=50)
    rerank_top_k: Optional[int] = Field(default=None, ge=1, le=20)
    fusion_method: Optional[str] = Field(default=None, pattern="^(rrf|weighted)?$")
    enable_query_expansion: Optional[bool] = None


@dataclass
class Job:
    job_id: str
    params: dict[str, Any]
    status: str = "queued"  # queued | running | succeeded | failed
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    return_code: Optional[int] = None
    log_lines: list[str] = field(default_factory=list)
    error: Optional[str] = None


_jobs: dict[str, Job] = {}
_jobs_lock = threading.Lock()
_MAX_LOG = 500


def _append(job: Job, line: str) -> None:
    job.log_lines.append(line.rstrip())
    if len(job.log_lines) > _MAX_LOG:
        del job.log_lines[: len(job.log_lines) - _MAX_LOG]


def _run_job(job: Job) -> None:
    job.status = "running"
    job.started_at = time.time()
    p = job.params
    cmd = [sys.executable, "-m", "scripts.benchmark",
           "--num-queries", str(p["num_queries"]), "--runs", str(p["runs"]), "--quiet"]
    if p.get("rebuild_index"):
        cmd.append("--rebuild-index")
    if p.get("device"):
        cmd += ["--device", p["device"]]
    logger.info("benchmark_job_start", job_id=job.job_id, cmd=" ".join(cmd))
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, bufsize=1)
        assert proc.stdout is not None
        for line in proc.stdout:
            _append(job, line)
        proc.wait()
        job.return_code = proc.returncode
        job.status = "succeeded" if proc.returncode == 0 else "failed"
        if proc.returncode != 0:
            job.error = f"Benchmark exited with code {proc.returncode}. See logs."
    except Exception as exc:
        job.status = "failed"
        job.error = str(exc)[:500]
        _append(job, f"[job error] {exc}")
    finally:
        job.finished_at = time.time()
        logger.info("benchmark_job_done", job_id=job.job_id, status=job.status)


def _public(job: Job) -> dict[str, Any]:
    elapsed = (job.finished_at or time.time()) - (job.started_at or job.created_at)
    return {
        "job_id": job.job_id, "status": job.status, "params": job.params,
        "created_at": job.created_at, "elapsed_seconds": round(elapsed, 1),
        "return_code": job.return_code, "error": job.error,
        "log_tail": job.log_lines[-80:],
    }


@router.post("/api/benchmark/run")
async def start_benchmark_run(body: BenchmarkRunRequest) -> dict[str, Any]:
    with _jobs_lock:
        active = [j for j in _jobs.values() if j.status in {"queued", "running"}]
        if len(active) >= 2:
            raise HTTPException(status_code=429, detail="A benchmark is already running. Wait for it to finish.")
        job = Job(job_id=f"bench_{uuid.uuid4().hex[:12]}", params=body.model_dump())
        _jobs[job.job_id] = job
    thread = threading.Thread(target=_run_job, args=(job,), daemon=True)
    thread.start()
    return {"job_id": job.job_id, "status": job.status,
            "message": "Benchmark started in background. Poll GET /api/benchmark/jobs/{job_id}."}


@router.get("/api/benchmark/jobs/{job_id}")
async def benchmark_job(job_id: str) -> dict[str, Any]:
    job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Unknown benchmark job.")
    return _public(job)


@router.get("/api/benchmark/jobs")
async def benchmark_jobs() -> dict[str, Any]:
    jobs = sorted(_jobs.values(), key=lambda j: j.created_at, reverse=True)[:20]
    return {"total": len(_jobs), "jobs": [_public(j) for j in jobs],
            "note": "In-memory job history for this process. Reports land in reports/ on success."}
