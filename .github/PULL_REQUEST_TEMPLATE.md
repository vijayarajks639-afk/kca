## Work package

WP-ID:
JIRA:

## What

<!-- one paragraph -->

## Acceptance criteria (from the WP card — all must be checked)

- [ ]
- [ ]
- [ ]

## Architecture rules checklist

- [ ] LLM stays in L3/L4 (no storage access, no direct execution)
- [ ] No LLM-computed regulated numbers
- [ ] Retrieval calls carry as_of + caller identity; permission filter pre-ranking, fail-closed
- [ ] Model calls recorded to ledger
- [ ] Cross-package calls via contracts/ schemas only
- [ ] No cloud SDK imports in core packages
- [ ] Tests included; eval gate green
