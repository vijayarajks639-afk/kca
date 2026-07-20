"""Case stores for the review queue (WP-17b).

Two interchangeable backings behind one Protocol, injected into
ReviewService so its gates and ledger behaviour are untouched by where cases
live:

- InMemoryCaseStore — the WP-17 default, kept for the pure (no-DB) tests.
- PostgresCaseStore — durable: a case enqueued by one process survives a
  restart and is dispositioned by another (review.review_cases, migration
  0006). Serialises the case's contract/dataclass artifacts to jsonb and
  rebuilds them on read.

Serialisation is total and lossless: ReconstructedDecision and
RetrievalResponse are Pydantic (model_dump/model_validate); ExplanationDraft
and FilterResult are frozen dataclasses rebuilt field-for-field.
"""

from typing import Protocol

import psycopg
from psycopg.types.json import Json

from kca.apps.review_ui.service import ReviewCase
from kca.contracts import ReconstructedDecision
from kca.contracts.retrieval import RetrievalResponse
from kca.platform.orchestrator.filters import FilterResult
from kca.platform.orchestrator.journeys import ExplanationDraft


class CaseStore(Protocol):
    def add(self, case: ReviewCase) -> None: ...
    def get(self, case_id: str) -> ReviewCase | None: ...
    def list_pending(self) -> list[ReviewCase]: ...
    def set_status(self, case_id: str, status: str) -> None: ...


class InMemoryCaseStore:
    """Process-local dict — the WP-17 behaviour, lost on restart."""

    def __init__(self) -> None:
        self._cases: dict[str, ReviewCase] = {}

    def add(self, case: ReviewCase) -> None:
        self._cases[case.case_id] = case

    def get(self, case_id: str) -> ReviewCase | None:
        return self._cases.get(case_id)

    def list_pending(self) -> list[ReviewCase]:
        return [c for c in self._cases.values() if c.status == "pending"]

    def set_status(self, case_id: str, status: str) -> None:
        self._cases[case_id].status = status


def _serialise(case: ReviewCase) -> dict:
    return {
        "decision": case.decision.model_dump(mode="json"),
        "retrieved": case.retrieved.model_dump(mode="json"),
        "draft": {
            "text": case.draft.text,
            "cited_source_versions": case.draft.cited_source_versions,
        },
        "filtered": {
            "internal_text": case.filtered.internal_text,
            "external_text": case.filtered.external_text,
            "policy_version": case.filtered.policy_version,
            "reasons_used": list(case.filtered.reasons_used),
        },
        "trace": list(case.trace),
    }


def _deserialise(
    case_id: str, application_id: str, status: str, payload: dict
) -> ReviewCase:
    return ReviewCase(
        case_id=case_id,
        application_id=application_id,
        decision=ReconstructedDecision.model_validate(payload["decision"]),
        retrieved=RetrievalResponse.model_validate(payload["retrieved"]),
        draft=ExplanationDraft(
            text=payload["draft"]["text"],
            cited_source_versions=payload["draft"]["cited_source_versions"],
        ),
        filtered=FilterResult(
            internal_text=payload["filtered"]["internal_text"],
            external_text=payload["filtered"]["external_text"],
            policy_version=payload["filtered"]["policy_version"],
            reasons_used=tuple(payload["filtered"]["reasons_used"]),
        ),
        trace=tuple(payload["trace"]),
        status=status,
    )


class PostgresCaseStore:
    """Durable backing over review.review_cases."""

    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    def add(self, case: ReviewCase) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO review.review_cases
                    (case_id, application_id, status, decision, retrieved,
                     draft, filtered, trace)
                VALUES (%(case_id)s, %(application_id)s, %(status)s,
                        %(decision)s, %(retrieved)s, %(draft)s, %(filtered)s,
                        %(trace)s)
                """,
                self._row_params(case),
            )
        self._conn.commit()

    def get(self, case_id: str) -> ReviewCase | None:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT application_id, status, decision, retrieved, draft, "
                "filtered, trace FROM review.review_cases WHERE case_id = %s",
                (case_id,),
            )
            row = cur.fetchone()
        if row is None:
            return None
        application_id, status, decision, retrieved, draft, filtered, trace = row
        return _deserialise(
            case_id,
            application_id,
            status,
            {
                "decision": decision,
                "retrieved": retrieved,
                "draft": draft,
                "filtered": filtered,
                "trace": trace,
            },
        )

    def list_pending(self) -> list[ReviewCase]:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT case_id, application_id, status, decision, retrieved, "
                "draft, filtered, trace FROM review.review_cases "
                "WHERE status = 'pending' ORDER BY created_at"
            )
            rows = cur.fetchall()
        cases = []
        for case_id, application_id, status, decision, retrieved, draft, filtered, trace in rows:
            cases.append(
                _deserialise(
                    case_id,
                    application_id,
                    status,
                    {
                        "decision": decision,
                        "retrieved": retrieved,
                        "draft": draft,
                        "filtered": filtered,
                        "trace": trace,
                    },
                )
            )
        return cases

    def set_status(self, case_id: str, status: str) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                "UPDATE review.review_cases SET status = %s WHERE case_id = %s",
                (status, case_id),
            )
        self._conn.commit()

    @staticmethod
    def _row_params(case: ReviewCase) -> dict:
        payload = _serialise(case)
        return {
            "case_id": case.case_id,
            "application_id": case.application_id,
            "status": case.status,
            "decision": Json(payload["decision"]),
            "retrieved": Json(payload["retrieved"]),
            "draft": Json(payload["draft"]),
            "filtered": Json(payload["filtered"]),
            "trace": Json(payload["trace"]),
        }
