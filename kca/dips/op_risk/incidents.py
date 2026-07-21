"""Incident record + reconstruction reader (op-risk DIP asset).

The op-risk analogue of platform/knowstore's DecisionReconstructionRepository —
but it lives HERE, under the DIP, because reading this domain's own declared
dataset (knowstore.op_risk_incidents, a data_contract in dip.json) is domain
logic the DIP brings itself. `IncidentRecord` is a DIP-local shape (plain
Pydantic, not a registered contract) since nothing outside op-risk consumes it,
so the contracts registry is untouched.
"""

from datetime import date

import psycopg
from pydantic import BaseModel


class IncidentRecord(BaseModel):
    incident_id: str
    occurred_at: date
    category: str
    severity: str
    description: str
    jurisdiction: str
    loss_amount: float


class IncidentReconstructionRepository:
    """Reconstructs one incident from knowstore.op_risk_incidents (the DIP's own
    data_contract). Returns None for an unknown incident — the journey turns
    that into a MISSING_DECISION_RECORD abstention, never a fabricated incident."""

    def __init__(self, conn: psycopg.Connection) -> None:
        self._conn = conn

    def reconstruct(self, incident_id: str) -> IncidentRecord | None:
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT incident_id, occurred_at, category, severity, description, "
                "jurisdiction, loss_amount FROM knowstore.op_risk_incidents "
                "WHERE incident_id = %s",
                (incident_id,),
            )
            row = cur.fetchone()
        if row is None:
            return None
        incident_id, occurred_at, category, severity, description, jurisdiction, loss = row
        return IncidentRecord(
            incident_id=incident_id,
            occurred_at=occurred_at,
            category=category,
            severity=severity,
            description=description,
            jurisdiction=jurisdiction,
            loss_amount=float(loss),
        )
