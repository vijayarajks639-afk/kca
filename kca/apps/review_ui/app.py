"""FastAPI layer over ReviewService (WP-17, extended in WP-17b).

Two surfaces over the one service:

- **JSON API** (`/queue`, `/cases/{id}`, POST disposition) — the programmatic
  interface; the reviewer identity is supplied explicitly in the body (used
  by tests and service-to-service callers).
- **Server-rendered UI** (`/login`, `/ui/queue`, `/ui/cases/{id}`, and its
  disposition form) — the human surface; the reviewer identity comes from the
  authenticated **session**, never a form field, so a browser can't
  self-assert a role. Login is a Keycloak direct-grant (see auth.py).

Both surfaces call the SAME `ReviewService`, so its gates (named reviewer,
authz fail-closed, amend re-screen) and ledger writes are identical however a
disposition arrives. This module stays thin: it only maps HTTP → service.
"""

from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware

from kca.apps.review_ui.auth import (
    Authenticator,
    keycloak_direct_grant,
    reviewer_from_claims,
)
from kca.apps.review_ui.service import (
    ReviewError,
    ReviewService,
    UnauthorisedReviewerError,
    UnknownCaseError,
    UnnamedReviewerError,
)
from kca.contracts import CallerIdentity

_TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


class DispositionRequest(BaseModel):
    action: str  # accept | amend | reject | escalate
    reviewer_id: str
    reviewer_role: str
    purpose: str = "credit_review"
    jurisdiction: str = "GB"
    amended_text: str | None = None


def create_app(
    service: ReviewService,
    *,
    authenticator: Authenticator | None = None,
    session_secret: str = "dev-only-review-secret",
) -> FastAPI:
    app = FastAPI(title="KCA review UI", version="0.2.0")
    app.add_middleware(SessionMiddleware, secret_key=session_secret)
    authenticate = authenticator or keycloak_direct_grant

    def _disposition(case_id, action, reviewer, amended_text):
        """Shared disposition path — maps the service's exceptions to HTTP."""
        try:
            return service.disposition(
                case_id, action, reviewer, amended_text=amended_text
            )
        except UnknownCaseError:
            raise HTTPException(status_code=404, detail=f"no case {case_id}") from None
        except UnnamedReviewerError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None
        except UnauthorisedReviewerError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from None
        except (ReviewError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None

    def _session_reviewer(request: Request) -> CallerIdentity | None:
        data = request.session.get("reviewer")
        return CallerIdentity(**data) if data else None

    # --- JSON API (body-supplied reviewer) ----------------------------------

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
        result = _disposition(case_id, body.action, reviewer, body.amended_text)
        return {
            "case_id": result.case_id,
            "action": result.action.value,
            "sent": result.sent,
            "approver": result.event.approver,
            "violations": [asdict(v) for v in result.violations],
            "event_hash": result.event.event_hash,
        }

    # --- server-rendered UI (session-supplied reviewer) ---------------------

    @app.get("/login", response_class=HTMLResponse)
    def login_form(request: Request):
        return _TEMPLATES.TemplateResponse(request, "login.html", {"reviewer": None})

    @app.post("/login")
    def login(request: Request, username: str = Form(...), password: str = Form(...)):
        claims = authenticate(username, password)
        if claims is None:
            return _TEMPLATES.TemplateResponse(
                request,
                "login.html",
                {"reviewer": None, "flash": "Login failed.", "flash_kind": "err"},
                status_code=401,
            )
        reviewer = reviewer_from_claims(username, claims)
        request.session["reviewer"] = reviewer.model_dump()
        return RedirectResponse("/ui/queue", status_code=303)

    @app.get("/logout")
    def logout(request: Request):
        request.session.clear()
        return RedirectResponse("/login", status_code=303)

    @app.get("/ui/queue", response_class=HTMLResponse)
    def ui_queue(request: Request):
        reviewer = _session_reviewer(request)
        if reviewer is None:
            return RedirectResponse("/login", status_code=303)
        return _TEMPLATES.TemplateResponse(
            request, "queue.html", {"reviewer": reviewer, "cases": service.queue()}
        )

    @app.get("/ui/cases/{case_id}", response_class=HTMLResponse)
    def ui_case(request: Request, case_id: str):
        reviewer = _session_reviewer(request)
        if reviewer is None:
            return RedirectResponse("/login", status_code=303)
        try:
            case = service.case(case_id)
        except UnknownCaseError:
            raise HTTPException(status_code=404, detail=f"no case {case_id}") from None
        return _TEMPLATES.TemplateResponse(
            request, "case.html", {"reviewer": reviewer, "case": case}
        )

    @app.post("/ui/cases/{case_id}/disposition", response_class=HTMLResponse)
    def ui_disposition(
        request: Request,
        case_id: str,
        action: str = Form(...),
        amended_text: str | None = Form(None),
    ):
        reviewer = _session_reviewer(request)
        if reviewer is None:
            return RedirectResponse("/login", status_code=303)
        # Identity comes from the session, NOT the form — a browser cannot
        # self-assert a reviewer role.
        result = _disposition(case_id, action, reviewer, amended_text)
        case = service.case(case_id)
        if result.sent:
            flash, kind = f"{action.capitalize()}ed and sent.", "ok"
        elif result.violations:
            cats = ", ".join(sorted({v.category for v in result.violations}))
            flash, kind = f"Amendment blocked ({cats}) — not sent.", "err"
        else:
            flash, kind = f"{action.capitalize()}ed.", "ok"
        return _TEMPLATES.TemplateResponse(
            request,
            "case.html",
            {"reviewer": reviewer, "case": case, "flash": flash, "flash_kind": kind},
        )

    return app
