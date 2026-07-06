# Contributing

This project is governed by the product and architecture baseline in
[`docs/AI_INTERVIEW_AGENT_DESIGN.md`](docs/AI_INTERVIEW_AGENT_DESIGN.md).

Every change must start from that document:

1. Identify the related design section and acceptance criteria.
2. Keep the implementation scoped to the current PR objective.
3. Do not add features that do not serve the interview training loop.
4. Do not introduce user-private data without binding it to `current_user.id`.
5. Do not bypass backend authorization or the frontend API client.
6. Update `contracts/api` samples whenever request or response shapes change.
7. Add or update tests for changed behavior.
8. Record local verification in the PR.

Before pushing a PR, run the local quality gate when practical:

```powershell
.\scripts\ci-local.ps1
```

Use `-SkipDocker`, `-SkipE2E`, or `-SkipSecretScan` only when the required local
runtime is not available, and note the skipped step in the PR.

If Playwright browsers are not installed locally, run this once before the full
quality gate:

```powershell
cd frontend
npx playwright install chromium
```

Default PR sequence:

1. User isolation and auth boundaries.
2. Unified frontend API client.
3. Backend session state machine.
4. Interview workspace.
5. Structured reports.
6. Training dashboard and `PracticePlan`.
7. Async admin jobs.
8. Engineering hardening and observability.

If a proposed change cannot clearly map to the design baseline, pause and update
the design before writing code.
