# Frontend Visual QA

This checklist protects the blue-white brand experience for the core AI interview training flow.

## Visual Goals

- Blue-white, low-noise product feel.
- Clear information hierarchy with generous spacing.
- White rounded cards, subtle borders, and soft shadows.
- Primary CTAs are easy to identify.
- Logo and global navigation are consistent across signed-in pages.
- Mobile pages remain usable with no horizontal overflow.

## Core Pages

- `/login`
- `/practice`
- `/mock`
- `/session/{id}`
- `/report/{id}`
- `/wrong-book`

## Automated Smoke Coverage

The visual smoke test is `frontend/tests/e2e/visual-smoke.spec.ts`.

It verifies:

- Core page title, logo or product name, and primary CTA are visible.
- Desktop screenshots are captured at `1440x1000`.
- Mobile screenshots are captured at `390x844`.
- Each covered page has no horizontal overflow.
- No pixel-level snapshot comparison is used.

## Screenshot Output

Screenshots are written under:

```text
frontend/test-results/visual/
```

Expected files:

- `login-desktop.png`
- `practice-desktop.png`
- `mock-desktop.png`
- `session-desktop.png`
- `report-desktop.png`
- `wrong-book-desktop.png`
- `practice-mobile.png`
- `mock-mobile.png`
- `session-mobile.png`
- `report-mobile.png`
- `wrong-book-mobile.png`

## Local Commands

Run all E2E tests:

```bash
cd frontend
npm run test:e2e
```

Run only visual smoke tests:

```bash
cd frontend
npm run test:e2e:visual
```

Run the full local CI gate from the repository root:

```powershell
.\scripts\ci-local.ps1 -SkipDocker -SkipSecretScan
```

## Manual Acceptance Checklist

- Logo is clear, not stretched, and visually aligned with surrounding content.
- Primary CTA stands out from secondary actions.
- Page copy is natural Chinese and matches the training-loop product direction.
- Card spacing, border radius, and shadow treatment feel consistent.
- Global navigation can return users to 今日训练 from core signed-in pages.
- Mobile layout is readable and does not require horizontal scrolling.
- Loading, empty, and error states are friendly and actionable.
- Session and report pages clearly communicate the next step.
- Wrong-book and mock interview pages keep users inside the training loop.

## CI Artifact

GitHub Actions uploads `frontend/test-results/visual/` as `frontend-visual-screenshots` after the frontend E2E step. The artifact is evidence for visual review, not a strict approval gate.
