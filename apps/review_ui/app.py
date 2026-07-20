"""FastAPI layer over ReviewService (WP-17) — queue + case view + disposition.

Thin by design: every rule (named reviewer, authz fail-closed, amend
re-screen, ledger write) lives in service.py and is enforced identically no
matter how the service is driven; this module only maps HTTP to it. The
reviewer's identity arrives in the disposition body and is passed straight
into the service's gates — an unnamed or unauthorised reviewer gets 4xx and
nothing is recorded.
"""

from dataclasses import asdict

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from apps.review_ui.service import (
    ReviewError,
    ReviewService,
    UnauthorisedReviewerError,
    UnknownCaseError,
    UnnamedReviewerError,
)
from kca.contracts import CallerIdentity


class DispositionRequest(BaseModel):
    action: str  # accept | amend | reject | escalate
    reviewer_id: str
    reviewer_role: str
    purpose: str = "credit_review"
    jurisdiction: str = "GB"
    amended_text: str | None = None


def create_app(service: ReviewService) -> FastAPI:
    app = FastAPI(title="KCA review UI", version="0.1.0")

    @app.get("/queue")
    def queue() -> list[dict]:
        return [
            {
                "case_id": c.case_id,
                "application_id": c.application_id,
                "outcome": c.decision.recorded_outcome,
                "decided_at": c.decision.decided_at.isoformat(),
                "status": c.status,
            }
            for c in service.queue()
        ]

    @app.get("/cases/{case_id}")
    def case_view(case_id: str) -> dict:
        try:
            c = service.case(case_id)
        except UnknownCaseError:
            raise HTTPException(status_code=404, detail=f"no case {case_id}") from None
        return {
            "case_id": c.case_id,
            "application_id": c.application_id,
            "status": c.status,
            "evidence": {
                "decision": c.decision.model_dump(mode="json"),
                "sources": [i.model_dump(mode="json") for i in c.retrieved.items],
            },
            "draft": {
                "internal_text": c.draft.text,
                "citations": c.draft.cited_source_versions,
            },
            "external": {
                "text": c.filtered.external_text,
                "filter_policy_version": c.filtered.policy_version,
                "reasons_used": list(c.filtered.reasons_used),
            },
            "validation": {
                "executed_steps": list(c.trace),
                "validate_step_passed": "validate" in c.trace,
            },
        }

    @app.post("/cases/{case_id}/disposition")
    def disposition(case_id: str, body: DispositionRequest) -> dict:
        reviewer = CallerIdentity(
            caller_id=body.reviewer_id,
            role=body.reviewer_role,
            purpose=body.purpose,
            jurisdiction=body.jurisdiction,
        )
        try:
            result = service.disposition(
                case_id, body.action, reviewer, amended_text=body.amended_text
            )
        except UnknownCaseError:
            raise HTTPException(status_code=404, detail=f"no case {case_id}") from None
        except UnnamedReviewerError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        except UnauthorisedReviewerError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from None
        except (ReviewError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        return {
            "case_id": result.case_id,
            "action": result.action.value,
            "sent": result.sent,
            "approver": result.event.approver,
            "violations": [asdict(v) for v in result.violations],
            "event_hash": result.event.event_hash,
        }

    return app
