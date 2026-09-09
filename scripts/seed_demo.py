"""Seed demo corpus: ingest synthetic enterprise docs so the UI works immediately.

Usage:
    make demo            # or: python -m scripts.seed_demo [--rebuild]

Loads bundled synthetic documents via the real IngestionPipeline, rebuilds
the BM25 sidecar index state implicitly through ingestion, and verifies
Qdrant reachability. Never touches evaluation methodology.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

DATA_DIR = Path("data/raw")
DOCS = {
    "sla_policy.md": """# SLA Policy — Incident Response

## P1 incidents
P1 (severity-1) incidents have a 15-minute acknowledgement SLA and a 4-hour
resolution target. The response team must acknowledge a P1 page within 15
minutes, 24/7.

## Escalation
A severity-1 incident is escalated to the on-call engineering manager after
30 minutes without acknowledgement, and to the CTO after 60 minutes. All
escalations are logged in the incident tracker.

## P2/P3
P2 incidents: 1-hour acknowledgement, 24-hour resolution. P3: next business day.
""",
    "billing_policy.md": """# Billing Policy — Invoices

## Overdue invoices
When an invoice becomes overdue (30 days past due), the account is flagged
and a reminder is sent. After 60 days overdue, service is suspended pending
payment. A 1.5% monthly late fee applies to balances over 60 days overdue.

## Disputes
Invoice disputes must be filed within 15 days of issuance through the billing
portal. Disputed amounts are excluded from late fees while under review.
""",
    "security_policy.md": """# Security Policy — Audit Logging

## Retention
Audit logs are retained for 365 days in immutable storage. Security event
logs (authentication, access control changes) are retained for 2 years.

## Incident response
The response team must acknowledge a reported security event within 1 hour.
Critical vulnerabilities (CVSS >= 9.0) must be patched within 72 hours.
""",
    "remote_work.md": """# Remote Work Policy

Employees may work remotely up to 3 days per week with manager approval.
Core collaboration hours are 10:00–15:00 in the employee's local timezone.
All remote work requires a secure VPN connection for internal systems.
""",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed demo corpus for Enterprise RAG Intelligence")
    parser.add_argument("--rebuild", action="store_true", help="Clear collection before seeding (requires Qdrant)")
    args = parser.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for name, text in DOCS.items():
        (DATA_DIR / name).write_text(text)
    print(f"Wrote {len(DOCS)} demo documents to {DATA_DIR}/")

    # Verify Qdrant reachability (honest, non-fatal message).
    try:
        from qdrant_client import QdrantClient
        from src.core.config import settings

        client = QdrantClient(url=settings.qdrant_url, timeout=5)
        client.get_collections()
        print(f"Qdrant reachable at {settings.qdrant_url}")
    except Exception as exc:
        print(f"WARNING: Qdrant not reachable ({exc}). Start it with: docker compose up -d qdrant")
        print("Documents were written to data/raw/ and can be ingested once Qdrant is up:")
        print("  make ingest")
        return 0

    from src.ingestion.pipeline import IngestionPipeline

    pipeline = IngestionPipeline()
    total = 0
    for name in DOCS:
        chunks = pipeline.ingest(str(DATA_DIR / name), {"demo": True})
        total += len(chunks)
        print(f"  {name}: {len(chunks)} chunks")
    print(f"Seeded {total} chunks. Open the UI and ask a question.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
