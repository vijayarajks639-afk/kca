# KCA demo script — a click-by-click walkthrough

**Audience:** a non-technical presenter showing the KCA prototype to stakeholders.
**Duration:** ~12 minutes. **You do not need to touch a terminal during the demo** —
everything runs from the browser once the stack is started.

> One sentence to open with: *"KCA is a prototype of a federated enterprise-AI
> platform — one shared 'brain' the whole enterprise reuses, instead of a
> separate AI silo per department. Everything here runs on synthetic data."*

---

## 0. One-time setup (before the audience arrives)

Run these three commands once, then leave the browser tab open:

```
make up          # starts Postgres + Keycloak (Docker)
make migrate     # creates the database schema
make dashboard   # opens the Platform Explorer in your browser
```

In the Explorer's left sidebar:

1. Confirm **"Postgres connected"** shows green. (If it's red, wait a few seconds
   and click **Retry connection**.)
2. Click **Prepare demo data**. Wait for *"Demo data ready."* This loads the
   synthetic corpus and records both journeys use. It is safe to click again.

You're ready. The pages are listed in the sidebar in the order this script uses.

---

## 1. Five Planes — the whole platform on one screen  *(90 seconds)*

**Click:** `Five Planes` in the sidebar.

**Say:** *"The platform is one shared spine, organised as five planes. The green
banner at the top means every part of the codebase loads and runs right now —
this isn't a diagram, it's the live system."*

**Point at:**
- The banner: *"N/N packages import cleanly."*
- The **Model & Agent** plane's subtitle: **"L3 Reasoning · L4 Decision-proposal —
  the ONLY layers the LLM touches."**

**Say:** *"That last line is the whole safety story: the AI model only reasons and
proposes. It never owns the data, the memory, or the ability to act. Those stay
with the platform."*

---

## 2. DIP Contracts — two domains, one shape  *(90 seconds)*

**Click:** `DIP Contracts`.

**Say:** *"Each business domain plugs in through the same contract. On the left is
Credit Risk, on the right Operational Risk — two completely different areas,
identical contract shape."*

**Point at:** the green *"§8.2 fields: 20/20 present"* on both, and the
**Abstention rules** table.

**Say:** *"Every domain declares, up front, the situations where the AI must
refuse to answer. Refusing safely is a designed-in feature, not an afterthought.
Onboarding a new domain means writing one of these contracts — not building a new
platform."*

---

## 3. Journey A — a credit decline, explained  *(3 minutes)*

**Click:** `Journeys`. Leave **Domain = Credit Risk**, **Scenario = "Worked
decline explanation."** Click **Run journey**.

**Say:** *"This runs the real pipeline: it rebuilds the original decision, fetches
only the policies this user is allowed to see as they stood on the decision date,
re-computes the numbers with a deterministic rules engine, and only then asks the
model to write the explanation."*

**Point at, in order:**
- **Steps executed:** the seven steps `reconstruct → retrieve → rederive → draft →
  validate → filter → review`.
- The blue **assessment** box: *"Rules engine (authoritative): re-derived LTV 0.87,
  outcome 'decline' … No figure in the explanation is computed by the model."*
- The two columns: **Internal explanation** (what the reviewer sees, with
  citations) vs **Customer-facing wording** (the policy-approved letter).

**Say:** *"Two things to notice. First, every number came from the rules engine,
never the model. Second, the customer never sees the model's words — the outside
message is assembled from approved wording. And it ends at **human review**:
nothing goes out without a named person approving it."*

---

## 4. Journey B — the same spine, a different domain  *(90 seconds)*

**Still on `Journeys`:** switch **Domain = Operational Risk**, **Scenario =
"Worked incident investigation."** Click **Run journey**.

**Say:** *"Different domain, different data, different steps — but it's running on
the exact same platform spine. This is the payoff of not building one brain per
department."*

**Point at:** the materiality band in the assessment box, and that this journey
has **no customer-facing column** — *"an internal investigation has no customer
letter, and the platform reflects that."*

---

## 5. Abstention — watch it refuse  *(2 minutes)*

**Still on `Journeys`, Domain = Credit Risk.** Change **Scenario = "Trap · version
conflict."** Click **Run journey**.

**Say:** *"Here the model produced a fluent, confident answer — but it cited a
policy version that wasn't valid for this decision's date. The platform caught it
and refused."*

**Point at:** the amber **"⛔ Abstained — reason code `VERSION_CONFLICT`"** banner,
and that **there is no explanation shown** — *"no fluent guess reaches anyone."*

*(Optional, if asked "what else does it catch?")* Try **"Trap · unauthorised
requester"** → `UNAUTHORISED_SOURCE`, or **"Trap · unknown application"** →
`MISSING_DECISION_RECORD`. Each refuses with a specific, logged reason.

---

## 6. Ledger — the audit trail that can't be faked  *(2 minutes)*

**Click:** `Ledger`. Leave **"Credit decline (worked)"** selected. Click
**Run & record**.

**Say:** *"Every step was written to an append-only, tamper-evident log. This
is the auditor's view — and it's rebuilt entirely from the log, with no access to
the live systems."*

**Point at:**
- The green **"Chain verified"** banner.
- The **reconstruction report**: what the system knew, which policy was in force,
  which model was used, and the outcome.

**Then click:** **Tamper with one event.**

**Say:** *"I'll now secretly edit one recorded event."*

**Point at:** the red **"BROKEN ✅ (detected)"** result.

**Say:** *"The moment anything in the history is altered, the chain breaks and the
tampering is obvious. And to be clear — that edit happened only in memory for the
demo; the real log on disk is untouched and, by design, the platform's writer
account physically cannot edit or delete history."*

---

## 7. Router — the model can't wander off  *(60 seconds)*

**Click:** `Router`.

**Say:** *"When work is confidential, the platform decides which model to use and
where it may run — and confidential work is pinned inside the private cloud."*

**Point at:** the **Recorded routes** table — *"confidential reasoning → private
cloud"* — and the blue note that the external option (same model, with web
search) is **excluded before selection**, not merely discouraged.

---

## 8. Reuse — the business case, measured  *(60 seconds)*

**Click:** `Reuse`.

**Say:** *"Finally, the number that matters to a budget owner. When we added the
second domain, we measured how much of the platform it reused versus rebuilt."*

**Point at:** the **92.5% reused** / **8% marginal footprint** figures and the
**SUPPORTED** verdict.

**Close with:** *"The first domain pays to build the platform. Every domain after
that reuses more than nine-tenths of it and changes zero platform code. That is
the case for one shared brain instead of one per department."*

---

## Quick reference — what each scenario proves

| Page → scenario | What the audience sees |
|---|---|
| Journeys → Credit "Worked" | Full explanation; numbers from the rules engine; internal vs customer wording; ends at human review |
| Journeys → Op-risk "Worked" | The same spine running a second domain |
| Journeys → "Trap · version conflict" | A confident-but-wrong answer is caught and refused (`VERSION_CONFLICT`) |
| Journeys → "Trap · unauthorised requester" | Access is filtered before ranking (`UNAUTHORISED_SOURCE`) |
| Journeys → "Trap · unknown application" | Missing record → refuse, don't invent (`MISSING_DECISION_RECORD`) |
| Ledger → Run & record → Tamper | Append-only, hash-chained, tamper-evident audit trail |
| Router | Confidential work pinned to private cloud |
| Reuse | 91.6% reused when the 2nd domain was added |

## If something looks wrong

- **Sidebar shows "Postgres unreachable":** run `make up` and `make migrate`, then
  click **Retry connection**.
- **A Journey/Ledger page says "Demo data not loaded yet":** click **Prepare demo
  data** in the sidebar.
- **A journey shows an error box:** re-click **Prepare demo data** (it's safe to
  repeat) and run again.
