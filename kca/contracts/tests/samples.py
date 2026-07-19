"""Canonical sample instances for every exported contract model.

Round-trip and export tests iterate these; adding a model to contracts/
without a sample here fails the completeness test.
"""

from datetime import UTC, date, datetime
from uuid import UUID

from kca.contracts import (
    Abstention,
    AbstentionReasonCode,
    AbstentionRule,
    AccessPolicyRef,
    AutonomyMode,
    AuthzDecision,
    CallerIdentity,
    DataContract,
    DIPCapability,
    DIPContract,
    DIPLifecycle,
    DIPLifecycleStatus,
    EvaluationGate,
    FreshnessSLO,
    GatewayResponse,
    GoldenSet,
    GoldenSetCase,
    KnowledgeSourceRef,
    LayerBoundary,
    LedgerEvent,
    LedgerEventType,
    ModelRoute,
    QualitySLO,
    ReconstructedDecision,
    RederivationResult,
    RederivationSnapshot,
    ResolutionContext,
    DataSensitivity,
    DeploymentBoundary,
    RetrievalRequest,
    RetrievalResponse,
    RetrievedItem,
    RouteDecision,
    RouteRequest,
    SemanticExtensionRef,
    SourceVersion,
    TermDefinition,
    TokenUsage,
    ToolCall,
    ToolGrant,
    ToolSpec,
    UsageMetrics,
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
    FreshnessSLO: FreshnessSLO(
        max_staleness_days=1,
        measured_from="latest knowledge_sources source_version publish date",
    ),
    QualitySLO: QualitySLO(
        metric="golden_set_pass_rate",
        threshold=0.95,
        measured_by="kca.evals golden-set runner (WP-18)",
    ),
    AccessPolicyRef: AccessPolicyRef(
        policy_version="v1",
        allowed_roles=["credit-officer", "domain-steward", "auditor"],
    ),
    EvaluationGate: EvaluationGate(golden_set_id="credit-risk-decline-v1", min_pass_rate=0.95),
    DIPLifecycle: DIPLifecycle(status=DIPLifecycleStatus.ACTIVE),
    SemanticExtensionRef: SemanticExtensionRef(
        sense_id="CreditRisk.Exposure",
        description="Exposure at Default (EAD)",
    ),
    DataContract: DataContract(
        dataset_id="knowstore.decision_records",
        description="Credit decision records (WP-04 synthetic)",
        primary_key="decision_id",
        freshness_slo=FreshnessSLO(max_staleness_days=1, measured_from="decided_at"),
        quality_checks=["not_null(decision_id)", "ltv >= 0", "score between 300 and 850"],
    ),
    ToolGrant: ToolGrant(
        tool_name="rederive_score",
        allowed_roles=["credit-officer", "auditor"],
        allowed_purposes=["credit-decision-review", "audit"],
    ),
    AbstentionRule: AbstentionRule(
        reason_code=AbstentionReasonCode.MISSING_DECISION_RECORD,
        trigger="No decision record exists for the requested application_id as of the "
        "caller's as_of date.",
    ),
    GoldenSetCase: GoldenSetCase(
        case_id="case-88231-decline-explanation",
        scenario="Explain why application app-88231 (customer cust-88231) was declined.",
        expected_reason_codes=[],
        expected_summary="LTV 87% exceeds policy v2 maximum 80% after 35% collateral haircut.",
    ),
    GoldenSet: GoldenSet(
        golden_set_id="credit-risk-decline-v1",
        dip_id="dip-credit-risk",
        cases=[
            GoldenSetCase(
                case_id="case-88231-decline-explanation",
                scenario="Explain why application app-88231 (customer cust-88231) was declined.",
                expected_reason_codes=[],
                expected_summary="LTV 87% exceeds policy v2 maximum 80% after 35% collateral "
                "haircut.",
            )
        ],
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
        freshness_slo=FreshnessSLO(
            max_staleness_days=1,
            measured_from="latest knowledge_sources source_version publish date",
        ),
        quality_slo=QualitySLO(
            metric="golden_set_pass_rate",
            threshold=0.95,
            measured_by="kca.evals golden-set runner (WP-18)",
        ),
        access_policy=AccessPolicyRef(
            policy_version="v1",
            allowed_roles=["credit-officer", "domain-steward", "auditor"],
        ),
        evaluation_gate=EvaluationGate(
            golden_set_id="credit-risk-decline-v1", min_pass_rate=0.95
        ),
        lifecycle=DIPLifecycle(status=DIPLifecycleStatus.ACTIVE),
        semantic_extensions=[
            SemanticExtensionRef(
                sense_id="CreditRisk.Exposure",
                description="Exposure at Default (EAD)",
            )
        ],
        data_contracts=[
            DataContract(
                dataset_id="knowstore.decision_records",
                description="Credit decision records (WP-04 synthetic)",
                primary_key="decision_id",
                freshness_slo=FreshnessSLO(max_staleness_days=1, measured_from="decided_at"),
                quality_checks=["not_null(decision_id)"],
            )
        ],
        tool_grants=[
            ToolGrant(
                tool_name="rederive_score",
                allowed_roles=["credit-officer", "auditor"],
                allowed_purposes=["credit-decision-review", "audit"],
            )
        ],
        abstention_rules=[
            AbstentionRule(
                reason_code=AbstentionReasonCode.MISSING_DECISION_RECORD,
                trigger="No decision record exists for the requested application_id as of "
                "the caller's as_of date.",
            )
        ],
        agent_instructions_ref="agent_instructions.md",
    ),
    ReconstructedDecision: ReconstructedDecision(
        application_id="app-88231",
        decision_id="dec-88231",
        customer_id="cust-88231",
        facility_id="fac-88231",
        decided_at=_AS_OF,
        policy_version="v2",
        policy_title="Credit policy v2 — tightened collateral treatment",
        policy_summary="Tightened: 80% max LTV, 35% collateral haircut, referral floor 600.",
        policy_max_ltv=0.80,
        policy_collateral_haircut=0.35,
        policy_referral_floor_score=600,
        facility_amount=226200.0,
        collateral_valuation=400000.0,
        credit_score=612,
        recorded_outcome="decline",
        recorded_ltv=0.87,
        reasons=[
            "LTV 87% exceeds policy v2 maximum 80% after 35% collateral haircut",
            "Credit score 612 above referral floor 600; decline is policy-driven",
        ],
    ),
    RederivationSnapshot: RederivationSnapshot(
        application_id="app-88231",
        facility_amount=226200.0,
        collateral_valuation=400000.0,
        policy_version="v2",
        max_ltv=0.80,
        collateral_haircut=0.35,
        referral_floor_score=600,
        credit_score=612,
        recorded_outcome="decline",
        recorded_ltv=0.87,
    ),
    RederivationResult: RederivationResult(
        application_id="app-88231",
        computed_ltv=0.87,
        computed_outcome="decline",
        recorded_ltv=0.87,
        recorded_outcome="decline",
        matched=True,
        abstention=None,
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
        route_decision=RouteDecision(
            request=RouteRequest(
                task_class="explain_decline",
                data_sensitivity=DataSensitivity.CONFIDENTIAL,
                required_capability="reasoning",
            ),
            profile="sonnet-reasoning",
            model="claude-sonnet-5",
            layer_boundary=LayerBoundary.L3_REASONING,
            deployment_boundary=DeploymentBoundary.PRIVATE_CLOUD,
            rules_version="v1",
            decided_at=_VALID,
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
        communication_sent="credit-decline explanation emailed to applicant 88231",
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
        valid_from=date(2026, 2, 1),
        valid_to=None,
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
                valid_from=date(2026, 2, 1),
                valid_to=None,
            )
        ],
        abstention=None,
    ),
    ResolutionContext: ResolutionContext(
        department="credit-risk",
        role="credit-officer",
        application="credit-decline-explanation",
    ),
    TermDefinition: TermDefinition(
        canonical_term="exposure",
        sense_id="CreditRisk.Exposure",
        domain="credit-risk",
        definition="Exposure at Default (EAD): expected gross exposure to a facility at default.",
        steward="credit-risk-domain-steward",
        effective_date=_AS_OF,
        unit="EAD",
        parent_sense_id="exposure",
    ),
    ToolSpec: ToolSpec(
        name="rederive_score",
        description="Re-derive the credit score deterministically via the rules engine.",
        input_schema={
            "type": "object",
            "properties": {"application_id": {"type": "string"}},
            "required": ["application_id"],
        },
    ),
    ToolCall: ToolCall(id="toolu_01", name="rederive_score", input={"application_id": "88231"}),
    TokenUsage: TokenUsage(
        input_tokens=1200, output_tokens=340, cache_read_input_tokens=1024,
        cache_creation_input_tokens=0,
    ),
    UsageMetrics: UsageMetrics(
        model="claude-sonnet-5",
        boundary=LayerBoundary.L3_REASONING,
        stop_reason="end_turn",
        usage=TokenUsage(input_tokens=1200, output_tokens=340),
    ),
    GatewayResponse: GatewayResponse(
        model="claude-sonnet-5",
        boundary=LayerBoundary.L3_REASONING,
        stop_reason="end_turn",
        text="The decline was driven by LTV 87% exceeding the 80% cap.",
        tool_calls=[],
        usage=TokenUsage(input_tokens=1200, output_tokens=340),
    ),
    RouteRequest: RouteRequest(
        task_class="explain_decline",
        data_sensitivity=DataSensitivity.CONFIDENTIAL,
        required_capability="reasoning",
        max_latency_ms=2000,
        max_cost_per_mtok=5.0,
    ),
    RouteDecision: RouteDecision(
        request=RouteRequest(
            task_class="explain_decline",
            data_sensitivity=DataSensitivity.CONFIDENTIAL,
            required_capability="reasoning",
        ),
        profile="sonnet-reasoning",
        model="claude-sonnet-5",
        layer_boundary=LayerBoundary.L3_REASONING,
        deployment_boundary=DeploymentBoundary.PRIVATE_CLOUD,
        rules_version="v1",
        decided_at=_VALID,
    ),
}
