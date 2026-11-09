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
(`requirements/` — 16 files, 211 scenarios, structured by topic: each
file is named after the topic it covers) are sibling artefacts, not part of
this set: the plan is the build tracker, the oracle is the requirements
this code must fulfil (the factory's own stage 10 checks the implementation
against every one of the 211 scenarios).

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
### 2026-10-27 14:08 UTC — code-weaver run for issue #21
- result: success
- PR: 57
- **Total input tokens:** 279327
- **Total output tokens:** 189577
- **Total cost:** unpriced (model `Qwen3.8` has no rate entry — the owner extends the report's rate table)
- stages:
  - stage 1 trigger: issue #21 accepted (event issues, label gate passed)
  - stage 10 test-and-review: green — 9 scenarios fulfilled
  - stage 13 pr-gates: all 1 green
### 2026-10-27 22:21 UTC — code-weaver run for issue #23
- result: success
- PR: 61
- **Total input tokens:** 665165
- **Total output tokens:** 380301
- **Total cost:** unpriced (model `Qwen3.8` has no rate entry — the owner extends the report's rate table)
- stages:
  - stage 1 trigger: issue #23 accepted (event issues, label gate passed)
  - stage 10 test-and-review: green — 63 scenarios fulfilled
  - stage 13 pr-gates: all 1 green
### 2026-10-28 00:34 UTC — code-weaver run for issue #60
- result: success
- PR: 62
- **Total input tokens:** 428058
- **Total output tokens:** 178618
- **Total cost:** unpriced (model `Qwen3.8` has no rate entry — the owner extends the report's rate table)
- stages:
  - stage 1 trigger: issue #60 accepted (event issues, label gate passed)
  - stage 10 test-and-review: green — 9 scenarios fulfilled
  - stage 13 pr-gates: no PR-triggered workflow on this head (vacuously green)
### 2026-10-31 15:26 UTC — code-weaver run for issue #77
- result: success
- PR: 78
- **Total input tokens:** 307724
- **Total output tokens:** 132810
- **Total cost:** $0.3077 (model `Qwen3.8` @ $0.10/M input, $2.08/M output — rates from the repo file .pi/agent/models.json)
- stages:
  - stage 1 trigger: issue #77 accepted (event issues, label gate passed)
  - stage 10 test-and-review: green — 19 scenarios fulfilled
  - stage 13 pr-gates: all 1 green
### 2026-10-31 17:39 UTC — code-weaver run for issue #79
- result: success
- PR: 80
- **Total input tokens:** 347715
- **Total output tokens:** 187782
- **Total cost:** $0.4261 (model `Qwen3.8` @ $0.10/M input, $2.08/M output — rates from the repo file .pi/agent/models.json)
- stages:
  - stage 1 trigger: issue #79 accepted (event issues, label gate passed)
  - stage 10 test-and-review: green — 7 scenarios fulfilled
  - stage 13 pr-gates: all 1 green
### 2026-10-31 19:25 UTC — code-weaver run for issue #82
- result: success
- PR: 84
- **Total input tokens:** 297228
- **Total output tokens:** 130084
- **Total cost:** $0.3009 (model `Qwen3.8` @ $0.10/M input, $2.08/M output — rates from the repo file .pi/agent/models.json)
- stages:
  - stage 1 trigger: issue #82 accepted (event issues, label gate passed)
  - stage 10 test-and-review: green — 4 scenarios fulfilled
  - stage 13 pr-gates: all 1 green
### 2026-10-31 22:50 UTC — code-weaver run for issue #85
- result: success
- PR: 86
- **Total input tokens:** 570735
- **Total output tokens:** 274282
- **Total cost:** $0.6288 (model `Qwen3.8` @ $0.10/M input, $2.08/M output — rates from the repo file .pi/agent/models.json)
- stages:
  - stage 1 trigger: issue #85 accepted (event issues, label gate passed)
  - stage 10 test-and-review: green — 74 scenarios fulfilled
  - stage 13 pr-gates: all 1 green
### 2026-11-01 19:23 UTC — code-weaver run for issue #90
- result: failure
- PR: 91
- **Total input tokens:** 851700
- **Total output tokens:** 400470
- **Total cost:** $0.9199 (model `Qwen3.8` @ $0.10/M input, $2.08/M output — rates from the repo file .pi/agent/models.json)
- stages:
  - stage 1 trigger: issue #90 accepted (event issues, label gate passed)
  - stage 10 test-and-review: green — 73 scenarios fulfilled
### 2026-11-02 15:30 UTC — code-weaver run for issue #94
- result: success
- PR: 95
- **Total input tokens:** 636571
- **Total output tokens:** 245965
- **Total cost:** $0.5766 (model `Qwen3.8` @ $0.10/M input, $2.08/M output — rates from the repo file .pi/agent/models.json)
- stages:
  - stage 1 trigger: issue #94 accepted (event issues, label gate passed)
  - stage 8 implementation: step 1/4 done
  - stage 8 implementation: step 2/4 done
  - stage 8 implementation: step 3/4 done
  - stage 8 implementation: step 4/4 done
  - stage 8 implementation: stage complete
  - stage 10 test-and-review: green — 85 scenarios fulfilled
  - stage 13 pr-gates: all 1 green
### 2026-11-04 19:47 UTC — code-weaver run for issue #97
- result: success
- PR: 99
- **Total input tokens:** 778770
- **Total output tokens:** 302196
- **Total cost:** $0.7081 (model `Qwen3.8` @ $0.10/M input, $2.08/M output — rates from the repo file .pi/agent/models.json)
- stages:
  - stage 1 trigger: issue #97 accepted (event issues, label gate passed)
  - stage 8 implementation: step 1/6 done
  - stage 8 implementation: step 2/6 done
  - stage 8 implementation: step 3/6 done
  - stage 8 implementation: step 4/6 done
  - stage 8 implementation: step 5/6 done
  - stage 8 implementation: step 6/6 done
  - stage 8 implementation: stage complete
  - stage 10 test-and-review: green — 82 scenarios fulfilled
  - stage 13 pr-gates: all 1 green
### 2026-11-05 00:05 UTC — code-weaver run for issue #98
- result: success
- PR: 101
- **Total input tokens:** 779015
- **Total output tokens:** 359473
- **Total cost:** $0.8272 (model `Qwen3.8` @ $0.10/M input, $2.08/M output — rates from the repo file .pi/agent/models.json)
- stages:
  - stage 1 trigger: issue #98 accepted (event issues, label gate passed)
  - stage 8 implementation: step 1/6 done
  - stage 8 implementation: step 2/6 done
  - stage 8 implementation: step 3/6 done
  - stage 8 implementation: step 4/6 done
  - stage 8 implementation: step 5/6 done
  - stage 8 implementation: step 6/6 done
  - stage 8 implementation: stage complete
  - stage 10 test-and-review: green — 95 scenarios fulfilled
  - stage 13 pr-gates: all 1 green
### 2026-11-05 14:12 UTC — code-weaver run for issue #100
- result: success
- PR: 103
- **Total input tokens:** 839758
- **Total output tokens:** 470998
- **Total cost:** $1.0654 (model `Qwen3.8` @ $0.10/M input, $2.08/M output — rates from the repo file .pi/agent/models.json)
- stages:
  - stage 1 trigger: issue #100 accepted (event issues, label gate passed)
  - stage 8 implementation: step 1/5 done
  - stage 8 implementation: step 2/5 done
  - stage 8 implementation: step 3/5 done
  - stage 8 implementation: step 4/5 done
  - stage 8 implementation: step 5/5 done
  - stage 8 implementation: stage complete
  - stage 10 test-and-review: green — 78 scenarios fulfilled
  - stage 13 pr-gates: all 1 green
### 2026-11-06 09:33 UTC — code-weaver run for issue #104
- result: success
- PR: 105
- **Total input tokens:** 425917
- **Total output tokens:** 213698
- **Total cost:** $0.4880 (model `Qwen3.8` @ $0.10/M input, $2.08/M output — rates from the repo file .pi/agent/models.json)
- stages:
  - stage 1 trigger: issue #104 accepted (event issues, label gate passed)
  - stage 8 implementation: step 1/3 done
  - stage 8 implementation: step 2/3 done
  - stage 8 implementation: step 3/3 done
  - stage 8 implementation: stage complete
  - stage 10 test-and-review: green — 15 scenarios fulfilled
  - stage 13 pr-gates: all 1 green
### 2026-11-07 21:23 UTC — code-weaver run for issue #70
- result: success
- PR: 110
- **Total input tokens:** 1412042
- **Total output tokens:** 608023
- **Total cost:** $1.4089 (model `Qwen3.8` @ $0.10/M input, $2.08/M output — rates from the repo file .pi/agent/models.json)
- stages:
  - stage 1 trigger: issue #70 accepted (event issues, label gate passed)
  - stage 8 implementation: step 1/6 done
  - stage 8 implementation: step 2/6 done
  - stage 8 implementation: step 3/6 done
  - stage 8 implementation: step 4/6 done
  - stage 8 implementation: step 5/6 done
  - stage 8 implementation: step 6/6 done
  - stage 8 implementation: stage complete
  - stage 10 test-and-review: green — 121 scenarios fulfilled
  - stage 13 pr-gates: all 1 green
