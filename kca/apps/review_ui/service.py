"""ReviewService — the framework-free core of the review UI (WP-17).

Cases enter the queue from a journey run that paused APPROVAL_REQUIRED; the
case carries everything the reviewer sees (evidence, internal draft with its
citation spine, both filter artifacts, the executed trace). Four
dispositions — accept / amend / reject / escalate — each by a NAMED
reviewer:

- The reviewer gate fails closed twice before anything is recorded: an
  unnamed reviewer (blank caller_id or role) and an unauthorised one
  (platform/authz denies the role/purpose/jurisdiction triple) are both
  refused outright — no ledger write, no state change.
- Every disposition that passes the gate writes a HUMAN_REVIEW event to the
  hash-chained ledger with the reviewer's identity in `approver`
  (criterion 1). "If it isn't in the ledger, it didn't happen."
- Amended text re-runs automated validation BEFORE send (criterion 2): the
  WP-16 filter's forbidden-content screen (whose no-figures rule subsumes
  numeric fidelity — no digit can appear in customer-facing text at all).
  A failing amendment is still ledgered — reviewer identity plus the failed
  check — but `communication_sent` stays empty and the case stays pending
  for re-amendment. There is no path that sends screened-out text.

Composes only other packages' public services and contract shapes
(LedgerRepository.append, AuthzService.decide, ExplanationPolicyFilter.screen
— CLAUDE.md rule 5); the web layer over this lives in app.py.
"""

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from kca.contracts import CallerIdentity, ReconstructedDecision
from kca.contracts.ledger import LedgerEvent, LedgerEventType, ValidationResult
from kca.platform.authz.service import AuthzService
from kca.platform.orchestrator.filters import ExplanationPolicyFilter, ForbiddenMatch
from kca.platform.orchestrator.journey import JourneyResult, StepStatus


class ReviewError(Exception):
    """Base for review failures."""


class UnnamedReviewerError(ReviewError):
    """A disposition without a named reviewer (blank caller_id or role) is
    refused before anything is recorded."""


class UnauthorisedReviewerError(ReviewError):
    """platform/authz denied the reviewer — fail closed, nothing recorded."""


class UnknownCaseError(ReviewError):
    """No pending case with that id."""


class Disposition(StrEnum):
    ACCEPT = "accept"
    AMEND = "amend"
    REJECT = "reject"
    ESCALATE = "escalate"


@dataclass
class ReviewCase:
    """One queue entry — everything the case view shows. `status` moves from
    'pending' to the disposition that closed it."""

    case_id: str
    application_id: str
    decision: ReconstructedDecision  # evidence
    draft: object  # ExplanationDraft: internal text + cited_source_versions
    retrieved: object  # RetrievalResponse: the evidence sources
    filtered: object  # FilterResult: internal + external artifacts
    trace: tuple[str, ...]  # executed steps — proof validation ran and passed
    status: str = "pending"


@dataclass(frozen=True)
class DispositionResult:
    case_id: str
    action: Disposition
    sent: bool
    event: LedgerEvent  # the HUMAN_REVIEW event as stored (hash-chained)
    violations: tuple[ForbiddenMatch, ...] = field(default_factory=tuple)


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class ReviewService:
    def __init__(
        self,
        ledger: object,  # LedgerRepository: .append(LedgerEvent) -> LedgerEvent
        *,
        authz: AuthzService | None = None,
        explanation_filter: ExplanationPolicyFilter | None = None,
        case_store: object | None = None,  # CaseStore (WP-17b); None -> in-memory
    ) -> None:
        self._ledger = ledger
        self._authz = authz or AuthzService()
        self._filter = explanation_filter or ExplanationPolicyFilter()
        # The queue's storage is injectable (WP-17b): the default keeps the
        # WP-17 in-memory behaviour (and its no-DB tests); PostgresCaseStore
        # makes the queue survive a restart. Storage is the ONLY thing that
        # varies — the gates and ledger writes below are identical either way.
        if case_store is None:
            from kca.apps.review_ui.store import InMemoryCaseStore  # noqa: PLC0415

            case_store = InMemoryCaseStore()
        self._store = case_store

    # --- queue ---------------------------------------------------------------

    def enqueue(self, result: JourneyResult, *, application_id: str) -> ReviewCase:
        """Admit a journey run that paused for review into the queue."""
        if result.status is not StepStatus.APPROVAL_REQUIRED:
            raise ValueError(
                f"only APPROVAL_REQUIRED journeys enter review; got {result.status}"
            )
        case = ReviewCase(
            case_id=f"case-{application_id}-{uuid4().hex[:8]}",
            application_id=application_id,
            decision=result.data["decision"],
            draft=result.data["draft"],
            retrieved=result.data["retrieved"],
            filtered=result.data["filtered"],
            trace=result.trace,
        )
        self._store.add(case)
        return case

    def queue(self) -> list[ReviewCase]:
        return self._store.list_pending()

    def case(self, case_id: str) -> ReviewCase:
        found = self._store.get(case_id)
        if found is None:
            raise UnknownCaseError(case_id)
        return found

    # --- dispositions --------------------------------------------------------

    def disposition(
        self,
        case_id: str,
        action: Disposition | str,
        reviewer: CallerIdentity,
        *,
        amended_text: str | None = None,
    ) -> DispositionResult:
        case = self.case(case_id)
        action = Disposition(action)
        if case.status != "pending":
            raise ReviewError(f"case {case_id} already dispositioned: {case.status}")

        # Named reviewer, fail closed — refused before anything is recorded.
        if not reviewer.caller_id.strip() or not reviewer.role.strip():
            raise UnnamedReviewerError(
                "dispositions require a named reviewer (caller_id and role)"
            )
        if not self._authz.decide(reviewer).allowed:
            raise UnauthorisedReviewerError(
                f"{reviewer.caller_id} ({reviewer.role}/{reviewer.purpose}/"
                f"{reviewer.jurisdiction}) is not authorised to review"
            )

        if action is Disposition.AMEND and not (amended_text or "").strip():
            raise ValueError("amend requires amended_text")

        violations: tuple[ForbiddenMatch, ...] = ()
        sent = False
        sent_text: str | None = None
        checks: list[ValidationResult] = []

        if action is Disposition.ACCEPT:
            sent, sent_text = True, case.filtered.external_text
        elif action is Disposition.AMEND:
            # Criterion 2: amended text re-runs automated validation BEFORE
            # send — the WP-16 screen, whose no-figures rule subsumes numeric
            # fidelity. Failing text is never sent.
            violations = tuple(self._filter.screen(amended_text))
            checks.append(
                ValidationResult(
                    check="amended_text_rescreen",
                    passed=not violations,
                    detail=(
                        "; ".join(f"{v.category}: {v.matched_text!r}" for v in violations)
                        or None
                    ),
                )
            )
            if not violations:
                sent, sent_text = True, amended_text
        # REJECT / ESCALATE send nothing.

        now = datetime.now(UTC)
        checks.insert(
            0,
            ValidationResult(
                check=f"review_disposition:{action.value}",
                passed=not violations,
                detail=f"case {case.case_id}, application {case.application_id}",
            ),
        )
        event = LedgerEvent(
            event_id=uuid4(),
            event_type=LedgerEventType.HUMAN_REVIEW,
            valid_time=now,
            record_time=now,
            approver=f"{reviewer.caller_id}:{reviewer.role}",
            output_digest=_digest(sent_text) if sent_text is not None else None,
            communication_sent=(
                f"credit-decline explanation sent for application "
                f"{case.application_id}"
                + (" (amended by reviewer)" if action is Disposition.AMEND else "")
                if sent
                else None
            ),
            validation_results=checks,
        )
        stored = self._ledger.append(event)

        closed_status = {
            Disposition.ACCEPT: "accepted",
            Disposition.AMEND: "amended",
            Disposition.REJECT: "rejected",
            Disposition.ESCALATE: "escalated",
        }
        if sent or action in (Disposition.REJECT, Disposition.ESCALATE):
            self._store.set_status(case.case_id, closed_status[action])
        # a failed amendment leaves the case pending for re-amendment

        return DispositionResult(
            case_id=case.case_id,
            action=action,
            sent=sent,
            event=stored,
            violations=violations,
        )
