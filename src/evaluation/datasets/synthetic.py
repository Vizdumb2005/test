import random
from dataclasses import dataclass, field
from typing import Any

from src.core.models import Chunk, Document, EvaluationSample

random.seed(42)

_ENTERPRISE_DOCUMENTS: list[dict[str, Any]] = [
    {
        "document_id": "doc_hr_001",
        "source": "https://internal.example.com/hr",
        "file_name": "remote_work_policy.pdf",
        "document_type": "policy",
        "text": (
            "The remote work policy requires employees to work from the office at least 3 days per week. "
            "Exceptions require VP approval and must be documented in HR systems. Remote workers must maintain "
            "a dedicated workspace with reliable internet (minimum 50 Mbps). Core collaboration hours are 10 AM "
            "to 3 PM in the employee's local timezone. Equipment stipends of up to $1,500 are available for home "
            "office setups. All remote employees must complete the annual security training by December 31."
        ),
        "metadata": {"department": "HR", "year": 2024},
    },
    {
        "document_id": "doc_hr_002",
        "source": "https://internal.example.com/hr",
        "file_name": "benefits_guide.pdf",
        "document_type": "policy",
        "text": (
            "Employees receive 15 days of paid time off in their first year, increasing to 20 days after three years. "
            "Health insurance covers medical, dental, and vision at 90% employee / 10% employer contribution. "
            "The 401(k) plan includes a 4% employer match. Parental leave provides 16 weeks fully paid for "
            "primary caregivers and 8 weeks for secondary caregivers. Tuition reimbursement covers up to $5,250 "
            "per year for job-related courses. Wellness benefits include a $500 annual gym stipend."
        ),
        "metadata": {"department": "HR", "year": 2024},
    },
    {
        "document_id": "doc_it_001",
        "source": "https://internal.example.com/it",
        "file_name": "incident_response_runbook.md",
        "document_type": "technical",
        "text": (
            "Incident response follows a 5-step process: (1) Detect via monitoring alerts, (2) Triage severity as P1/P2/P3, "
            "(3) Contain affected systems, (4) Eradicate root cause, (5) Recover with verification. P1 incidents require "
            "a response within 15 minutes and an update every 30 minutes. All incidents must be logged in Jira with severity, "
            "impact, and timeline. Communication goes to #incident-response on Slack and stakeholders via email."
        ),
        "metadata": {"department": "IT", "year": 2024},
    },
    {
        "document_id": "doc_it_002",
        "source": "https://internal.example.com/it",
        "file_name": "vpn_access_guide.md",
        "document_type": "technical",
        "text": (
            "VPN access uses Duo MFA with push notification. The VPN server address is vpn.example.com:443. "
            "Split tunneling is enabled for internal subnets 10.0.0.0/8 and 172.16.0.0/12. All connections are logged "
            "for 90 days. For issues, contact the IT help desk at ext. 4500. Mobile VPN is available via the Cisco AnyConnect app."
        ),
        "metadata": {"department": "IT", "year": 2024},
    },
    {
        "document_id": "doc_fin_001",
        "source": "https://internal.example.com/finance",
        "file_name": "expense_policy.pdf",
        "document_type": "policy",
        "text": (
            "Expense reports must be submitted within 30 days of the transaction. Receipts are required for any expense "
            "over $25. Meals are capped at $75 per day for domestic travel and $100 for international. Mileage reimbursement "
            "is $0.67 per mile. Alcohol expenses are not reimbursable. Approval is automatic under $500 and requires "
            "manager approval above $500. All expenses must be coded to the correct cost center."
        ),
        "metadata": {"department": "Finance", "year": 2024},
    },
    {
        "document_id": "doc_fin_002",
        "source": "https://internal.example.com/finance",
        "file_name": "budget_planning_cycle.md",
        "document_type": "process",
        "text": (
            "Annual budgeting begins in August with department heads submitting requests by September 15. Finance reviews "
            "and consolidates by October 15. Executive approval happens in November with final allocation communicated by "
            "December 1. Mid-year budget reforecasts are due June 30. Capital expenditures over $50,000 require a business "
            "case and CFO approval. Operating expenses are tracked monthly against the approved plan."
        ),
        "metadata": {"department": "Finance", "year": 2024},
    },
    {
        "document_id": "doc_legal_001",
        "source": "https://internal.example.com/legal",
        "file_name": "data_privacy_compliance.pdf",
        "document_type": "compliance",
        "text": (
            "All personal data must be processed in accordance with GDPR, CCPA, and HIPAA as applicable. Data minimization "
            "requires collecting only necessary fields. Retention periods are defined per record type with legal hold overriding "
            "standard deletion. Breach notification must occur within 72 hours to the DPO. Data subject access requests (DSARs) "
            "must be fulfilled within 30 days. Employees must complete annual privacy training."
        ),
        "metadata": {"department": "Legal", "year": 2024},
    },
    {
        "document_id": "doc_legal_002",
        "source": "https://internal.example.com/legal",
        "file_name": "vendor_contract_guidelines.md",
        "document_type": "compliance",
        "text": (
            "Vendor contracts must include data protection clauses, liability caps, and termination for convenience terms. "
            "All contracts over $100,000 require legal review. Contractors are limited to 18-month engagements with a 6-month "
            "cooling-off period before rehire. Open source licenses must be reviewed by Legal for compatibility. Contract renewals "
            "must be initiated 90 days before expiration."
        ),
        "metadata": {"department": "Legal", "year": 2024},
    },
    {
        "document_id": "doc_ops_001",
        "source": "https://internal.example.com/ops",
        "file_name": "facilities_booking.md",
        "document_type": "process",
        "text": (
            "Conference rooms are booked via the internal calendar system. Rooms up to 8 people can be booked 2 weeks in advance. "
            "Rooms over 8 people require Facilities approval 4 weeks in advance. Cancellations must be made 24 hours before the meeting. "
            "Audio/visual equipment requests must be submitted 48 hours in advance. Catering orders are handled by the admin team with 72-hour notice."
        ),
        "metadata": {"department": "Operations", "year": 2024},
    },
    {
        "document_id": "doc_ops_002",
        "source": "https://internal.example.com/ops",
        "file_name": "travel_policy.pdf",
        "document_type": "policy",
        "text": (
            "Travel must be booked through the approved travel portal. Flights should be booked 14 days in advance for best rates. "
            "Hotels are capped at $250 per night in major cities and $150 elsewhere. Ground transportation includes rideshare and rental cars. "
            "Travel insurance is required for international trips. Expense reports for travel must be submitted within 5 business days of return."
        ),
        "metadata": {"department": "Operations", "year": 2024},
    },
    {
        "document_id": "doc_it_003",
        "source": "https://internal.example.com/it",
        "file_name": "api_documentation.md",
        "document_type": "technical",
        "text": (
            "The internal API uses OAuth 2.0 with JWT tokens valid for 1 hour. Rate limits are 1000 requests per minute per service account. "
            "Endpoints return JSON with standard HTTP status codes. Pagination uses cursor-based tokens. All requests must include a "
            "Correlation-ID header for tracing. SDKs are available for Python, Node.js, and Go. API versioning follows semantic versioning with v1 and v2 available."
        ),
        "metadata": {"department": "IT", "year": 2024},
    },
    {
        "document_id": "doc_security_001",
        "source": "https://internal.example.com/security",
        "file_name": "security_awareness_guide.pdf",
        "document_type": "security",
        "text": (
            "Password requirements: minimum 16 characters, complexity mandatory, rotation every 90 days. MFA is required for all systems. "
            "Phishing simulations run quarterly. Report suspicious emails to security@example.com. USB drives must be encrypted and scanned. "
            "Social engineering awareness training is mandatory annually. Removable media policies prohibit use of unapproved devices."
        ),
        "metadata": {"department": "Security", "year": 2024},
    },
]


def _chunk_text(text: str, chunk_size: int = 800, overlap: int = 120) -> list[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk.strip())
        start = end - overlap
        if start >= len(text):
            break
    return chunks


def generate_synthetic_dataset(num_queries: int = 35) -> list[EvaluationSample]:
    query_templates: list[dict[str, Any]] = [
        {
            "query": "What is the remote work policy?",
            "relevant_document_ids": ["doc_hr_001"],
            "relevant_chunk_ids": ["doc_hr_001_chunk_0"],
            "expected_answer": "Employees must work from the office at least 3 days per week with VP approval required for exceptions.",
            "category": "exact_term",
            "difficulty": "easy",
        },
        {
            "query": "How many days of PTO do new hires get?",
            "relevant_document_ids": ["doc_hr_002"],
            "relevant_chunk_ids": ["doc_hr_002_chunk_0"],
            "expected_answer": "New hires receive 15 days of paid time off in their first year.",
            "category": "exact_term",
            "difficulty": "easy",
        },
        {
            "query": "What is the incident response process?",
            "relevant_document_ids": ["doc_it_001"],
            "relevant_chunk_ids": ["doc_it_001_chunk_0"],
            "expected_answer": "Incident response follows a 5-step process: detect, triage, contain, eradicate, recover.",
            "category": "keyword",
            "difficulty": "medium",
        },
        {
            "query": "How do I access the VPN?",
            "relevant_document_ids": ["doc_it_002"],
            "relevant_chunk_ids": ["doc_it_002_chunk_0"],
            "expected_answer": "VPN access uses Duo MFA at vpn.example.com:443 with split tunneling enabled.",
            "category": "keyword",
            "difficulty": "easy",
        },
        {
            "query": "What is the expense report deadline?",
            "relevant_document_ids": ["doc_fin_001"],
            "relevant_chunk_ids": ["doc_fin_001_chunk_0"],
            "expected_answer": "Expense reports must be submitted within 30 days of the transaction.",
            "category": "exact_term",
            "difficulty": "easy",
        },
        {
            "query": "When does the annual budgeting cycle start?",
            "relevant_document_ids": ["doc_fin_002"],
            "relevant_chunk_ids": ["doc_fin_002_chunk_0"],
            "expected_answer": "Annual budgeting begins in August with department heads submitting requests by September 15.",
            "category": "keyword",
            "difficulty": "medium",
        },
        {
            "query": "What are the data privacy compliance requirements?",
            "relevant_document_ids": ["doc_legal_001"],
            "relevant_chunk_ids": ["doc_legal_001_chunk_0"],
            "expected_answer": "All personal data must comply with GDPR, CCPA, and HIPAA. Data minimization and 72-hour breach notification are required.",
            "category": "semantic",
            "difficulty": "medium",
        },
        {
            "query": "What are the vendor contract guidelines?",
            "relevant_document_ids": ["doc_legal_002"],
            "relevant_chunk_ids": ["doc_legal_002_chunk_0"],
            "expected_answer": "Vendor contracts over $100,000 require legal review and must include data protection clauses and liability caps.",
            "category": "exact_term",
            "difficulty": "medium",
        },
        {
            "query": "How do I book a conference room?",
            "relevant_document_ids": ["doc_ops_001"],
            "relevant_chunk_ids": ["doc_ops_001_chunk_0"],
            "expected_answer": "Conference rooms are booked via the internal calendar system. Rooms up to 8 people can be booked 2 weeks in advance.",
            "category": "keyword",
            "difficulty": "easy",
        },
        {
            "query": "What is the travel policy for hotels?",
            "relevant_document_ids": ["doc_ops_002"],
            "relevant_chunk_ids": ["doc_ops_002_chunk_0"],
            "expected_answer": "Hotels are capped at $250 per night in major cities and $150 elsewhere.",
            "category": "keyword",
            "difficulty": "easy",
        },
        {
            "query": "What are the API rate limits?",
            "relevant_document_ids": ["doc_it_003"],
            "relevant_chunk_ids": ["doc_it_003_chunk_0"],
            "expected_answer": "Rate limits are 1000 requests per minute per service account.",
            "category": "exact_term",
            "difficulty": "medium",
        },
        {
            "query": "What are the password requirements?",
            "relevant_document_ids": ["doc_security_001"],
            "relevant_chunk_ids": ["doc_security_001_chunk_0"],
            "expected_answer": "Passwords must be minimum 16 characters with complexity and rotation every 90 days.",
            "category": "exact_term",
            "difficulty": "easy",
        },
        {
            "query": "What is the 401(k) employer match?",
            "relevant_document_ids": ["doc_hr_002"],
            "relevant_chunk_ids": ["doc_hr_002_chunk_0"],
            "expected_answer": "The 401(k) plan includes a 4% employer match.",
            "category": "acronym",
            "difficulty": "easy",
        },
        {
            "query": "What is the parental leave policy?",
            "relevant_document_ids": ["doc_hr_002"],
            "relevant_chunk_ids": ["doc_hr_002_chunk_0"],
            "expected_answer": "Parental leave provides 16 weeks fully paid for primary caregivers and 8 weeks for secondary caregivers.",
            "category": "keyword",
            "difficulty": "medium",
        },
        {
            "query": "How do I report a phishing email?",
            "relevant_document_ids": ["doc_security_001"],
            "relevant_chunk_ids": ["doc_security_001_chunk_0"],
            "expected_answer": "Report suspicious emails to security@example.com.",
            "category": "keyword",
            "difficulty": "easy",
        },
        {
            "query": "What is the equipment stipend for home office?",
            "relevant_document_ids": ["doc_hr_001"],
            "relevant_chunk_ids": ["doc_hr_001_chunk_0"],
            "expected_answer": "Equipment stipends of up to $1,500 are available for home office setups.",
            "category": "semantic",
            "difficulty": "medium",
        },
        {
            "query": "What is the data breach notification timeline?",
            "relevant_document_ids": ["doc_legal_001"],
            "relevant_chunk_ids": ["doc_legal_001_chunk_0"],
            "expected_answer": "Breach notification must occur within 72 hours to the DPO.",
            "category": "exact_term",
            "difficulty": "medium",
        },
        {
            "query": "When are mid-year budget reforecasts due?",
            "relevant_document_ids": ["doc_fin_002"],
            "relevant_chunk_ids": ["doc_fin_002_chunk_0"],
            "expected_answer": "Mid-year budget reforecasts are due June 30.",
            "category": "exact_term",
            "difficulty": "medium",
        },
        {
            "query": "What is the core collaboration hours requirement for remote workers?",
            "relevant_document_ids": ["doc_hr_001"],
            "relevant_chunk_ids": ["doc_hr_001_chunk_0"],
            "expected_answer": "Core collaboration hours are 10 AM to 3 PM in the employee's local timezone.",
            "category": "semantic",
            "difficulty": "medium",
        },
        {
            "query": "How long must VPN connections be logged?",
            "relevant_document_ids": ["doc_it_002"],
            "relevant_chunk_ids": ["doc_it_002_chunk_0"],
            "expected_answer": "All VPN connections are logged for 90 days.",
            "category": "exact_term",
            "difficulty": "medium",
        },
        {
            "query": "What is the approval threshold for expenses?",
            "relevant_document_ids": ["doc_fin_001"],
            "relevant_chunk_ids": ["doc_fin_001_chunk_0"],
            "expected_answer": "Approval is automatic under $500 and requires manager approval above $500.",
            "category": "exact_term",
            "difficulty": "easy",
        },
        {
            "query": "What is the meal reimbursement cap for international travel?",
            "relevant_document_ids": ["doc_fin_001"],
            "relevant_chunk_ids": ["doc_fin_001_chunk_0"],
            "expected_answer": "Meals are capped at $100 per day for international travel.",
            "category": "exact_term",
            "difficulty": "medium",
        },
        {
            "query": "How do I get help with VPN issues?",
            "relevant_document_ids": ["doc_it_002"],
            "relevant_chunk_ids": ["doc_it_002_chunk_0"],
            "expected_answer": "Contact the IT help desk at ext. 4500 for VPN issues.",
            "category": "keyword",
            "difficulty": "easy",
        },
        {
            "query": "What are the P1 incident response requirements?",
            "relevant_document_ids": ["doc_it_001"],
            "relevant_chunk_ids": ["doc_it_001_chunk_0"],
            "expected_answer": "P1 incidents require a response within 15 minutes and an update every 30 minutes.",
            "category": "acronym",
            "difficulty": "medium",
        },
        {
            "query": "What is the policy on alcohol reimbursement?",
            "relevant_document_ids": ["doc_fin_001"],
            "relevant_chunk_ids": ["doc_fin_001_chunk_0"],
            "expected_answer": "Alcohol expenses are not reimbursable.",
            "category": "exact_term",
            "difficulty": "easy",
        },
        {
            "query": "What is the data subject access request timeline?",
            "relevant_document_ids": ["doc_legal_001"],
            "relevant_chunk_ids": ["doc_legal_001_chunk_0"],
            "expected_answer": "Data subject access requests must be fulfilled within 30 days.",
            "category": "acronym",
            "difficulty": "medium",
        },
        {
            "query": "How far in advance must contract renewals be initiated?",
            "relevant_document_ids": ["doc_legal_002"],
            "relevant_chunk_ids": ["doc_legal_002_chunk_0"],
            "expected_answer": "Contract renewals must be initiated 90 days before expiration.",
            "category": "exact_term",
            "difficulty": "medium",
        },
        {
            "query": "What is the hotel cap for travel in New York?",
            "relevant_document_ids": ["doc_ops_002"],
            "relevant_chunk_ids": ["doc_ops_002_chunk_0"],
            "expected_answer": "Hotels are capped at $250 per night in major cities.",
            "category": "multi_hop",
            "difficulty": "hard",
        },
        {
            "query": "What is the Correlation-ID requirement for API requests?",
            "relevant_document_ids": ["doc_it_003"],
            "relevant_chunk_ids": ["doc_it_003_chunk_0"],
            "expected_answer": "All API requests must include a Correlation-ID header for tracing.",
            "category": "acronym",
            "difficulty": "medium",
        },
        {
            "query": "What is the capital expenditure approval process?",
            "relevant_document_ids": ["doc_fin_002"],
            "relevant_chunk_ids": ["doc_fin_002_chunk_0"],
            "expected_answer": "Capital expenditures over $50,000 require a business case and CFO approval.",
            "category": "keyword",
            "difficulty": "medium",
        },
        {
            "query": "What is the MFA requirement for VPN?",
            "relevant_document_ids": ["doc_it_002"],
            "relevant_chunk_ids": ["doc_it_002_chunk_0"],
            "expected_answer": "VPN access uses Duo MFA with push notification.",
            "category": "acronym",
            "difficulty": "easy",
        },
        {
            "query": "How long must incidents be logged in Jira?",
            "relevant_document_ids": ["doc_it_001"],
            "relevant_chunk_ids": ["doc_it_001_chunk_0"],
            "expected_answer": "All incidents must be logged in Jira with severity, impact, and timeline.",
            "category": "acronym",
            "difficulty": "medium",
        },
        {
            "query": "What is the gym stipend amount?",
            "relevant_document_ids": ["doc_hr_002"],
            "relevant_chunk_ids": ["doc_hr_002_chunk_0"],
            "expected_answer": "Wellness benefits include a $500 annual gym stipend.",
            "category": "exact_term",
            "difficulty": "easy",
        },
        {
            "query": "What is the maximum upload size for documents?",
            "relevant_document_ids": [],
            "relevant_chunk_ids": [],
            "expected_answer": "I do not know based on the provided context.",
            "category": "hard",
            "difficulty": "hard",
            "metadata": {"out_of_scope": True},
        },
        {
            "query": "What is the company stock ticker symbol?",
            "relevant_document_ids": [],
            "relevant_chunk_ids": [],
            "expected_answer": "I do not know based on the provided context.",
            "category": "hard",
            "difficulty": "hard",
            "metadata": {"out_of_scope": True},
        },
    ]

    samples: list[EvaluationSample] = []
    for idx, template in enumerate(query_templates[:num_queries]):
        samples.append(
            EvaluationSample(
                query=template["query"],
                relevant_document_ids=template["relevant_document_ids"],
                relevant_chunk_ids=template["relevant_chunk_ids"],
                expected_answer=template.get("expected_answer", ""),
                difficulty=template.get("difficulty", "medium"),
                category=template.get("category", "general"),
                metadata=template.get("metadata", {}),
            )
        )
    return samples


def build_chunks_from_documents(
    documents: list[Document],
    chunk_size: int = 800,
    overlap: int = 120,
) -> list[Chunk]:
    chunks: list[Chunk] = []
    for doc in documents:
        text_chunks = _chunk_text(doc.text, chunk_size=chunk_size, overlap=overlap)
        for chunk_idx, text in enumerate(text_chunks):
            chunks.append(
                Chunk(
                    chunk_id=f"{doc.document_id}_chunk_{chunk_idx}",
                    document_id=doc.document_id,
                    source=doc.source,
                    file_name=doc.file_name,
                    text=text,
                    chunk_index=chunk_idx,
                    metadata=doc.metadata,
                    document_type=doc.document_type,
                )
            )
    return chunks


def generate_documents() -> list[Document]:
    documents: list[Document] = []
    for item in _ENTERPRISE_DOCUMENTS:
        documents.append(
            Document(
                document_id=item["document_id"],
                source=item["source"],
                file_name=item["file_name"],
                document_type=item["document_type"],
                text=item["text"],
                metadata=item.get("metadata", {}),
            )
        )
    return documents
