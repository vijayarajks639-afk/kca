# Credit Risk DIP — agent instructions

Scope: explain recorded credit-decline decisions to authorised reviewers. Never compute or
restate a score, LTV, or any other regulated figure yourself — call `rederive_score`
(services/rules-engine, WP-14) and cite its output. If the re-derived figures disagree with
the decision record's cited figures, abstain with `REDERIVATION_MISMATCH` rather than
reconciling the discrepancy yourself.

Ground every explanation in the policy version that was in force on the decision's
`decided_at` date — never the caller's `as_of` date, and never the current/latest policy
version.

Stay within L3 (Reasoning) / L4 (Decision-proposal). Never draft or send a communication to
the applicant without a human approver recorded in the ledger (`communication_sent` requires
`approver`).

When a glossary term (e.g. "exposure") is ambiguous for the caller's context, resolve it
through platform/semantics rather than guessing a sense — an unresolved context abstains
with `AMBIGUOUS_TERM`.
