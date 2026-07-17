"""Canonical sample instances for every exported contract model.

Round-trip and export tests iterate these; adding a model to contracts/
without a sample here fails the completeness test.
"""

from datetime import UTC, date, datetime
from uuid import UUID

from kca.contracts import (
    Abstention,
    AbstentionReasonCode,
    AutonomyMode,
    AuthzDecision,
    CallerIdentity,
    DIPCapability,
    DIPContract,
    KnowledgeSourceRef,
    LayerBoundary,
    LedgerEvent,
    LedgerEventType,
    ModelRoute,
    RetrievalRequest,
    RetrievalResponse,
    RetrievedItem,
    SourceVersion,
    ValidationResult,
)

_AS_OF = date(2026, 3, 14)
_VALID = datetime(2026, 3, 14, 9, 30, tzinfo=UTC)
_RECORD = datetime(2026, 3, 14, 9, 30, 5, tzinfo=UTC)
_INFER = datetime(2026, 3, 14, 9, 30, 2, tzinfo=UTC)

CALLER = CallerIdentity(
    caller_id="u-4711",
    role="credit-analyst",
    purpose="credit-decision-review",
    jurisdiction="GB",
)

SAMPLES: dict[type, object] = {
    Abstention: Abstention(
        reason_code=AbstentionReasonCode.MISSING_DECISION_RECORD,
        detail="No decision record found for application 88231 as of 2026-03-14.",
    ),
    CallerIdentity: CALLER,
    AuthzDecision: AuthzDecision(
        caller_id="u-4711",
        role="credit-officer",
        purpose="credit-decision-review",
        jurisdiction="GB",
        policy_version="v1",
        allowed=True,
        decided_at=_VALID,
    ),
    SourceVersion: SourceVersion(source_id="policy/credit/uk-mortgage", version="2026.02"),
    KnowledgeSourceRef: KnowledgeSourceRef(
        source_id="policy/credit/uk-mortgage",
        description="UK mortgage underwriting policy",
    ),
    DIPCapability: DIPCapability(
        name="explain-decline",
        description="Explain a recorded credit decline decision",
        boundary=LayerBoundary.L3_REASONING,
    ),
    DIPContract: DIPContract(
        dip_id="dip-credit-risk",
        name="Credit Risk DIP",
        domain="credit-risk",
        owner="credit-risk-platform-team",
        contract_version="1.0.0",
        autonomy_mode=AutonomyMode.DECISION_SUPPORT,
        jurisdictions=["GB", "US"],
        capabilities=[
            DIPCapability(
                name="explain-decline",
                description="Explain a recorded credit decline decision",
                boundary=LayerBoundary.L3_REASONING,
            )
        ],
        knowledge_sources=[
            KnowledgeSourceRef(
                source_id="policy/credit/uk-mortgage",
                description="UK mortgage underwriting policy",
            )
        ],
        effective_from=_AS_OF,
    ),
    ModelRoute: ModelRoute(
        model="claude-sonnet-5",
        model_version="20260201",
        boundary=LayerBoundary.L3_REASONING,
    ),
    ValidationResult: ValidationResult(
        check="rederivation-match",
        passed=True,
        detail="rules-engine score 612 matches cited figure",
    ),
    LedgerEvent: LedgerEvent(
        event_id=UUID("0195f7a2-1111-7000-8000-000000000001"),
        event_type=LedgerEventType.MODEL_CALL,
        valid_time=_VALID,
        record_time=_RECORD,
        inference_time=_INFER,
        route=ModelRoute(
            model="claude-sonnet-5",
            model_version="20260201",
            boundary=LayerBoundary.L3_REASONING,
        ),
        retrieved_sources=[
            SourceVersion(source_id="policy/credit/uk-mortgage", version="2026.02")
        ],
        prompt_digest="a" * 64,
        output_digest="b" * 64,
        validation_results=[
            ValidationResult(check="rederivation-match", passed=True, detail=None)
        ],
        approver="reviewer-771",
        prev_hash="c" * 64,
        event_hash="d" * 64,
    ),
    RetrievalRequest: RetrievalRequest(
        request_id=UUID("0195f7a2-1111-7000-8000-000000000002"),
        query="Why was application 88231 declined?",
        as_of=_AS_OF,
        caller=CALLER,
        top_k=8,
    ),
    RetrievedItem: RetrievedItem(
        source_id="policy/credit/uk-mortgage",
        source_version="2026.02",
        content="Affordability threshold is 4.5x gross income.",
        score=0.87,
    ),
    RetrievalResponse: RetrievalResponse(
        request_id=UUID("0195f7a2-1111-7000-8000-000000000002"),
        as_of=_AS_OF,
        items=[
            RetrievedItem(
                source_id="policy/credit/uk-mortgage",
                source_version="2026.02",
                content="Affordability threshold is 4.5x gross income.",
                score=0.87,
            )
        ],
        abstention=None,
    ),
}
