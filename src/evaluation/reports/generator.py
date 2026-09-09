import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog

from src.core.models import MetricResult

logger = structlog.get_logger(__name__)


class ReportGenerationError(Exception):
    pass


class ReportGenerator:
    def __init__(self, output_dir: str | Path = "reports") -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(self, benchmark_results: dict[str, Any], ablation_results: Optional[dict[str, Any]] = None) -> dict[str, Path]:
        paths: dict[str, Path] = {}
        try:
            paths["benchmark_csv"] = self._write_benchmark_csv(benchmark_results)
            paths["benchmark_json"] = self._write_benchmark_json(benchmark_results)
            paths["benchmark_md"] = self._write_benchmark_md(benchmark_results)
            paths["ablation_csv"] = self._write_ablation_csv(ablation_results or benchmark_results.get("ablation_results", {}))
            paths["latency_json"] = self._write_latency_json(benchmark_results.get("latency", {}))
            logger.info("Reports generated", paths=list(paths.values()))
        except Exception as exc:
            logger.error("Report generation failed", error=str(exc))
            raise ReportGenerationError(f"Failed to generate reports: {exc}") from exc
        return paths

    def save_reports(self, benchmark_results: dict[str, Any], ablation_results: Optional[dict[str, Any]] = None) -> dict[str, Path]:
        return self.generate(benchmark_results, ablation_results)

    def load_latest_results(self) -> dict[str, Any]:
        json_path = self.output_dir / "benchmark.json"
        if not json_path.exists():
            raise FileNotFoundError(f"No benchmark results found at {json_path}")
        with json_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        logger.info("Loaded latest results", path=str(json_path))
        return data

    def _write_benchmark_csv(self, results: dict[str, Any]) -> Path:
        path = self.output_dir / "benchmark.csv"
        experiments = results.get("experiments", {})
        rows: list[dict[str, Any]] = []
        for method, data in experiments.items():
            metrics = data.get("metrics", {})
            row: dict[str, Any] = {"method": method}
            row.update({k: round(v, 4) if isinstance(v, float) else v for k, v in metrics.items()})
            rows.append(row)

        if not rows:
            rows = [{"method": "", "note": "no results"}]

        fieldnames = list(rows[0].keys())
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        logger.debug("Wrote benchmark CSV", path=str(path))
        return path

    def _write_benchmark_json(self, results: dict[str, Any]) -> Path:
        path = self.output_dir / "benchmark.json"
        payload = {
            "generated_at": datetime.utcnow().isoformat(),
            "summary": results.get("summary", {}),
            "experiments": results.get("experiments", {}),
            "latency": results.get("latency", {}),
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        logger.debug("Wrote benchmark JSON", path=str(path))
        return path

    def _write_benchmark_md(self, results: dict[str, Any]) -> Path:
        path = self.output_dir / "benchmark.md"
        lines = ["# Benchmark Report", ""]
        summary = results.get("summary", {})
        lines.append("## Summary")
        lines.append("")
        lines.append("| Method | Metric | Value |")
        lines.append("|--------|--------|-------|")
        for method, metrics in summary.items():
            for metric, value in metrics.items():
                lines.append(f"| {method} | {metric} | {value} |")
        lines.append("")

        experiments = results.get("experiments", {})
        if experiments:
            lines.append("## Experiment Details")
            lines.append("")
            for method, data in experiments.items():
                lines.append(f"### {method}")
                lines.append("")
                lines.append(f"- Queries: {data.get('query_count', 'N/A')}")
                lines.append(f"- Failures: {data.get('failure_count', 0)}")
                lines.append("")
                metrics = data.get("metrics", {})
                if metrics:
                    lines.append("| Metric | Value |")
                    lines.append("|--------|-------|")
                    for metric, value in metrics.items():
                        lines.append(f"| {metric} | {value} |")
                    lines.append("")

        latency = results.get("latency", {})
        if latency:
            lines.append("## Latency")
            lines.append("")
            lines.append("| Method | Mean (ms) | P50 (ms) | P95 (ms) | P99 (ms) |")
            lines.append("|--------|-----------|-----------|-----------|-----------|")
            for method, stats in latency.items():
                lines.append(
                    f"| {method} | {stats.get('mean', 'N/A')} | {stats.get('p50', 'N/A')} | "
                    f"{stats.get('p95', 'N/A')} | {stats.get('p99', 'N/A')} |"
                )
            lines.append("")

        path.write_text("\n".join(lines), encoding="utf-8")
        logger.debug("Wrote benchmark Markdown", path=str(path))
        return path

    def _write_ablation_csv(self, ablation_results: dict[str, Any]) -> Path:
        path = self.output_dir / "ablation.csv"
        rows: list[dict[str, Any]] = []
        for method, data in ablation_results.items():
            if not isinstance(data, dict):
                continue
            metrics = data.get("metrics", {})
            row: dict[str, Any] = {"method": method}
            row.update({k: round(v, 4) if isinstance(v, float) else v for k, v in metrics.items()})
            rows.append(row)

        if not rows:
            rows = [{"method": "", "note": "no ablation results"}]

        fieldnames = list(rows[0].keys())
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        logger.debug("Wrote ablation CSV", path=str(path))
        return path

    def _write_latency_json(self, latency: dict[str, Any]) -> Path:
        path = self.output_dir / "latency.json"
        payload = {
            "generated_at": datetime.utcnow().isoformat(),
            "latency": latency,
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        logger.debug("Wrote latency JSON", path=str(path))
        return path
