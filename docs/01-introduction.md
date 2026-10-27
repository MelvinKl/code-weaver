# 1. Introduction

**Code Weaver** is an AI software factory that creates programs — driven
entirely by [GitHub Actions](https://github.com/features/actions), not a
service. A maintainer adds the trigger label (default
`ai-requirements`) to an issue in a target project, and the factory's
reusable workflow takes over: it derives the delta requirements from the
project itself, plans them, implements them with a headless `pi` agent,
tests and reviews the result against the Gherkin oracle, opens a pull
request, and waits at the human gate. **Merging is never the factory's
job.**

The factory code lives in this repo and is referenced **by ref** from a
target project: the only code that ever changes per target is a short
workflow that names a ref and passes inputs. An upgrade is a one-line ref
bump; every published tag stays a stable ref (chapters 4 and 8).

This arc42 set is the set of markdown files under `docs/` — one chapter
per file (01–11). A target repo that has no `docs/` directory keeps its
arc42 set in its top-level `PLAN.md` instead; the factory's context
builders and the report stage fall back to that file, so the contract
holds for both shapes.

The repository's implementation plan (`PLAN.md`) and the Gherkin oracle
(`requirements/` — 14 files, 130 scenarios) are sibling artefacts, not
part of this set: the plan is the build tracker, the oracle is the
requirements this code must fulfil (the factory's own stage 10 checks the
implementation against every one of the 130 scenarios).

## AI activity (code-weaver)

### 2026-10-25 — code-weaver run for issue #20
- result: in progress — stages 1–11 executed; the stage-10 review marked
  ten standing scenarios UNFULFILLED and the stage-11 fix loop recorded
  its resolution (the `docs/` set created here, the extract stage's
  `@`-file context slice, the one-new-file/no-existing-edit extraction
  guard, the pi-generated PR body, the `MelvinKl`/version-tag consumer
  ref, the parser-port skipped-not-failed validator)
- PR: opened after the fix loop goes green
- stages: trigger, setup-pi, baseline, extraction, planning,
  implementation, test-and-review all ran; fix loop iteration 0 in flight
### 2026-10-26 01:41 UTC — code-weaver run for issue #20
- result: failure
- PR: 48
- stages:
  - stage 1 trigger: issue #20 accepted (event workflow_dispatch, label gate passed)
  - stage 10 test-and-review: green — 121 scenarios fulfilled
### 2026-10-26 23:27 UTC — code-weaver run for issue #43
- result: failure
- PR: 52
- **Total input tokens:** 198348
- **Total output tokens:** 99391
- **Total cost:** unpriced (model `Qwen3.8` has no rate entry — the owner extends the report's rate table)
- stages:
  - stage 1 trigger: issue #43 accepted (event issues, label gate passed)
  - stage 10 test-and-review: green — 9 scenarios fulfilled
