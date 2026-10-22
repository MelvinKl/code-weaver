# Code Weaver — Implementation Plan

**Oracle:** the Gherkin requirements in `requirements/` — 12 files, 102 scenarios.
**Rule of this plan:** the requirements win. Where this plan and a scenario disagree, one of them changes — they must never drift, because the factory's own stage 10 later checks the implementation against every scenario.

---

## 1. What we build

Not an application: **a set of reusable GitHub Actions** that lives in this repo and is
referenced **by ref** from a target project. The only code that ever changes per target
repo is a short workflow that names a ref and passes inputs — *reuse-by-ref:
“The factory is invoked as a reusable workflow”, “The target workflow stays short and
stable”*.

| Component | Path | Consumed as |
|---|---|---|
| Reusable workflow (the 15-stage pipeline) | `.github/workflows/factory.yml` | `uses: MelvinKl/code-weaver/.github/workflows/factory.yml@vX.Y.Z` |
| Composite actions | `.github/actions/{setup-pi,pi-run,baseline,guard-check,pr-open,pr-gates,report}/` | `uses: MelvinKl/code-weaver/.github/actions/<name>@vX.Y.Z` |
| pi prompt templates | `pi-prompts/{requirements,plan,implement,review}.md` | `--system-prompt @pi-prompts/<stage>.md` |
| Release machinery | `.github/workflows/release.yml` + semver tags `vX.Y.Z` | a ref bump = an upgrade |
| *(stretch — not currently in the Gherkin)* JS actions as an npm package | `package.json` (+ `node_modules/.github/actions/` after `npm ci`) | `uses: <pkg>/.github/actions/<name>@<ref>` — see §10, open item |

## 2. Repo layout (target state)

```
.github/
  workflows/
    factory.yml        # the pipeline: 15 logical stages, 9 jobs (§3)
    release.yml        # tag vX.Y.Z → GitHub release (immutable refs)
    house-ci.yml       # this repo's own lint/test (house-CI parity)
  actions/
    setup-pi/          # stage 2 — verify (never install) pi + backend + model
    pi-run/            # headless `pi --print` runner used by stages 4/6/8/10
    baseline/          # stage 3 — branch ai/<issue_number>, baseline ref + diff artifact
    guard-check/       # stages 5/7/9 — the one shared “only X changed” idiom
    pr-open/           # stage 12 — open the PR (body = final status report)
    pr-gates/          # stage 13 — wait for every PR-triggered workflow to be green
    report/            # stage 15 — PR body is the report; issue comment; arc42 activity
pi-prompts/
  requirements.md      plan.md      implement.md      review.md
requirements/          # ← the oracle (already on main)
PLAN.md   README.md   package.json (only with the stretch item)
```

## 3. The 15 stages, mapped to jobs

One reusable workflow, **9 jobs**, on the target repo's runner — a runner whose
environment **already has pi installed & configured** (a pre-requisite of the
environment; the factory never installs or configures it — *setup-pi* scenarios).
Guard/retry loops run inside the job that owns the generation stage (same checkout,
no state passing needed).

| Stage | Job | Implementation | Scenarios satisfied |
|---|---|---|---|
| 1 trigger | `trigger` | Fetch the issue (body + labels); gate on `ai-requirements-label` (default `ai-requirements`) **or** `workflow_dispatch` + `issue-number`. Idempotency: query in-progress `factory` runs with the same `issue-number` → comment “already running” on the issue, exit 0. | trigger: all 6 |
| 2 setup-pi | `setup-pi` | `command -v pi` → read the **pre-configured** pi environment (backend + configured model set; the action never writes it) → verify the selected `llm-model` is in the configured set → headless smoke check `pi --print` against that model → explicit failures: `pi not installed or configured on this runner` / `backend unreachable`; **no installation step exists**. | setup-pi: all 8; configuration: “LLM backend is a pre-requisite”; safety: “backend needs no secret” |
| 3 baseline | `baseline` | Branch **`ai/<issue_number>`** off the issue's base ref; record the baseline ref (base-branch head); snapshot the issue's changed-file diff as a **workflow artifact** (never into the repo tree). | requirement-extraction: “baseline captures the issue's change set”; safety: branch hygiene |
| 4 requirement-extraction | `extract` | `pi-run` with `pi-prompts/requirements.md`; context = `@requirements/ @README.md @docs/` + baseline diff + issue body. The prompt encodes: derive the **delta** against the baseline; write **valid Gherkin** (canonical keywords) to `requirements-dir`; tolerate arc42-markdown structure variance; empty issue body → write **nothing**, report “no delta requirements”, stop; re-run on unchanged input is idempotent. | requirement-extraction: all 6; safety: “tolerates arc42 structure variance” |
| 5 requirement-check | (in `extract`) | `guard-check <baseline-ref> --allow "<requirements-dir>"`; violation → revert off-limits files (`git checkout <ref> -- …` + `git clean`), **re-run stage 4**. | guard-rail: “clean stage passes”, “leaking stage is reverted and re-run”, “allowed set is per-stage” |
| 6 plan | `plan` | `pi-run` with `pi-prompts/plan.md`; context = `@requirements/**` + the arc42 markdown files + `@docs/`. The prompt: markdown plans under `plan-dir` — **one or more files may be combined**, but the plans must **cover every requirement change**; grounded in the documented architecture. | plan: “plans cover every requirement change”, “describes how”, “grounded in the current architecture” |
| 7 plan-check | (in `plan`) | `guard-check --allow "<plan-dir>"`; leak → revert + re-run stage 6. | plan: “the plan stage may only touch plans/” |
| 8 implement | `implement` | `pi-run` with `pi-prompts/implement.md`; context = plans + requirements. The prompt: implement the plans (code); generate tests; **update the arc42 markdown files under `doc-dir` so the set stays complete** (a repo without `doc-dir` keeps its top-level `PLAN.md` set complete); keep `README.md` current; **mark finished plan tasks done** (the plan is a live state tracker — the implement-check allows `plan-dir` and `PLAN.md` for it). | implement: “implemented as code”, “tests generated”, “arc42 updated and complete”, “README kept current”, “marks finished plan tasks as done” |
| 9 implement-check | (in `implement`) | `guard-check --allow "<src> <tests> <doc-dir> <plan-dir> PLAN.md README.md"` — the allow set **excludes `requirements-dir`** (it includes `plan-dir` — the plan tracks task state — and, for a repo without a `doc-dir`, the top-level `PLAN.md` that plays the same role); violation → revert + **loop back to stage 6** (not stage 8). | implement: “must not edit requirements”, “may mark plan tasks as done”, “allow set covers the repo's real layout”; guard-rail: “a requirement edited during implementation loops back to planning” |
| 10 test-and-review | `review` | Run the target's suite (`make test` — the target-repo contract wires `requirements/**.feature` into a Cucumber runner, so every Gherkin scenario is an executable acceptance test); then `pi-run` with `pi-prompts/review.md` → mark each scenario **fulfilled/unfulfilled** + produce the diff review. Each iteration's log → **workflow log / artifact only — never committed to the repo**. | test-and-review: “Gherkin runs as executable acceptance tests”, “each requirement checked for fulfilment”, “every iteration logged without touching the repo tree” |
| 11 fix loop | (in `review`) | While scenarios are unfulfilled: pi fix → commit → re-run stage 10. The loop respects `max-loops` (**0 = no cap**) and the token budget. | test-and-review: “failed scenario is fixed and re-reviewed”, “fix loop bounded by MAX_LOOPS”, “loop respects the token budget”; safety: “every loop respects its cap” |
| 12 pr-open | `pr` | Push `ai/<issue_number>`; `gh pr create` (head → `target-branch`); **the PR description is the final status report** — run status, source issue, every stage outcome (rendered from the stage-result state accumulated in workflow storage). | pr-and-gates: “a PR is opened against the target branch”, “PR body links back to the work” |
| 13 pr-gates | `gates` | Poll the GitHub API for **all** workflow runs triggered on the PR; succeed only when every one is green. | pr-and-gates: “all PR-triggered workflows must be green” |
| 14 gate-fix loop | (in `gates`) | A red gate → pi fix (the guard keeps in-PR fixes away from `requirements-dir`) → push → re-run stage 13; capped. **No merge call exists anywhere** — merge stays a human decision. | pr-and-gates: “failed gate is fixed and re-checked”, “gate loop bounded”, “merging stays a human decision” |
| 15 report | `report` | The final status **lives in the PR body** (updated if stage 12's snapshot changed); a summary comment on the source issue; an **AI-activity section appended to the arc42 markdown files** under `doc-dir` (a docs change on the AI branch — allowed by the implement allow set). Failed runs (died before stage 12): the failure summary goes to the issue comment; **no report file is ever written into the repo tree**. | reporting: all 4 |

## 4. Key mechanisms

### 4.1 The guard idiom — one script, three stages
*guard-rail: “all three checks share one shell idiom”*

```bash
# guard-check.sh <baseline-ref> <allowed-path>…
changed=$( { git diff --name-only "$BASELINE" -- .; git ls-files --others --exclude-standard; } | sort -u )
violations=()
for f in $changed; do
  case "/$f/" in
    $(for a in "$@"; do printf "/%s/ " "${a%/}"; done)*) : ;;        # under an allowed prefix
    *) violations+=("$f") ;;
  esac
done
[ "${#violations[@]}" -eq 0 ] && { echo "OK: only $* changed"; exit 0; }
git checkout "$BASELINE" -- "${violations[@]}"        # revert exactly the files that leaked
git clean -fdq -- $(printf '%s\n' "${violations[@]}" | xargs -r dirname | sort -u)
echo "REVERT: ${violations[*]}"
exit 1                                                 # the workflow re-runs the generation stage
```

### 4.2 Headless pi runner (`pi-run` action)
`pi --print --model "$LLM_MODEL" --system-prompt @pi-prompts/<stage>.md [--session-dir <scratch>]`,
with project context via `@<file>|<dir>` arguments. The LLM backend comes **only** from
the pi configuration that is a pre-requisite of the runner environment — the action
never passes or overrides it (*setup-pi: “backend configuration is a pre-requisite of
the environment”*). Model selection (`llm-model`) is the single adjustable LLM setting
and is validated in stage 2 (*setup-pi: “which configured model is used is
adjustable”*).

### 4.3 Loops & caps — 0 means no cap
*configuration: “a loop cap of 0 means no cap”; safety: “every loop in the pipeline
respects its cap”*

Every in-job loop: `for ((i = 0; ; i++))` with
`(( MAX_LOOPS > 0 && i >= MAX_LOOPS )) && break` — `MAX_LOOPS=0` uncaps it; the token
budget (`MAX_TOTAL_TOKENS`, same idiom) accumulates pi's per-invocation usage into a
workflow-log counter. Job `timeout-minutes` stays as the hard backstop. **The
termination guarantee holds while the caps are non-zero** (defaults 5 / 500 000).

### 4.4 Idempotency
*trigger: “re-entrant runs on the same issue do not duplicate work”*

The branch name **`ai/<issue_number>`** is the key: before any work, the `trigger` job
lists in-progress `factory` runs whose `issue-number` matches; one in progress →
comment on the issue + exit 0. Concurrent runs converge on the same branch.

### 4.5 The PR is the final report
*reporting: “the final status report is the PR”; “nothing under test-results/ is ever
committed”*

Stage results accumulate in workflow storage (env file / artifact) and are rendered
into the PR description at stage 12; stage 15 updates the body if anything changed and
comments on the issue. Iteration logs and the resolved configuration live in the
**workflow log / artifacts** — no report path is ever written into the repo tree.

## 5. Configuration surface — the reusable workflow's inputs
*configuration feature (all 10 scenarios)*

| Input | Default | Scenario |
|---|---|---|
| `issue-number` | from the issue event / dispatch input | trigger: “manual dispatch processes a named issue” |
| `ai-requirements-label` | `ai-requirements` | trigger: “trigger label is configurable” |
| `target-branch` | `main` | configuration: “target branch is configurable” |
| `requirements-dir` | `requirements/` | configuration: “artefact directories are configurable” (also drives the guard allow sets) |
| `plan-dir` | `plans/` | — |
| `doc-dir` | `docs/` | — |
| `llm-model` | `Ornith-1.5-35B-A3B` | configuration: “which configured model is used is adjustable” — must already be configured in the environment's pi config; the backend itself is a fixed pre-requisite (“LLM backend is a pre-requisite of the environment”) |
| `max-loops` | `5` | “loop caps are configurable” |
| `max-tokens` | `500000` | “a loop cap of 0 means no cap” |
| secret `GH_TOKEN` | — | safety: “GH_TOKEN is repo-scoped and never committed”; configuration: “secrets are never plain inputs” (passes via the reusable workflow's `secrets:` block only) |

All `with:` inputs map to job environment variables in `factory.yml`, and the resolved
configuration is recorded in the **workflow log** (not committed) — configuration:
“settings flow from workflow inputs to stage environment”.

## 6. What the target repo looks like (the only per-target code)

```yaml
# .github/workflows/code-weaver.yml — short & stable; names a ref, passes inputs
name: code-weaver
on:
  issues:            { types: [opened, edited, labeled] }
  workflow_dispatch: { inputs: { issue_number: { type: string } } }
permissions:        { contents: write, issues: write, pull-requests: write }
jobs:
  factory:
    runs-on: <runner whose environment has pi pre-installed & pre-configured>
    if: <label is ai-requirements> || <dispatched>
    uses: MelvinKl/code-weaver/.github/workflows/factory.yml@vX.Y.Z
    with:
      issue-number: ${{ github.event.issue.number || inputs.issue_number }}
      ai-requirements-label: ai-requirements
      target-branch: main
      llm-model: Ornith-1.5-35B-A3B  # which configured model to use
    secrets: { GH_TOKEN: ${{ secrets.GH_TOKEN }} }
```

An upgrade is **a ref bump in this one file** (reuse-by-ref: “an upgrade is a ref
bump”). `release.yml` tags semver `vX.Y.Z` and publishes a GitHub release; tags are
immutable, so **workflows pinned to an older ref keep working** (“every published
version is a stable ref”).

## 7. Traceability — every one of the 102 scenarios

| Feature | Scenario | Implemented by | Ticket |
|---|---|---|---|
| **trigger** | issue opened with the label starts the factory | `trigger` job label gate | CW-1 |
| | editing an issue to add the label starts the factory | same gate on `edited`/`labeled` events | CW-1 |
| | an issue without the label does not start the factory | negative path of the `if:` | CW-1 |
| | the trigger label is configurable | `ai-requirements-label` input → env | CW-1 |
| | a manual dispatch processes a named issue | `workflow_dispatch` + `issue-number` | CW-1 |
| | re-entrant runs on the same issue do not duplicate work | in-progress-run lock (§4.4) | CW-1 |
| **setup-pi** | pi is already on the runner | presence check, no install step | CW-2 |
| | the LLM backend configuration is a pre-requisite of the environment | action reads (never writes) the env's pi config | CW-2 |
| | which configured model is used is adjustable | `llm-model` validated against the configured set | CW-2 |
| | the setup stage verifies pi actually works | headless smoke check against the selected model | CW-2 |
| | pi runs headless | `pi-run` action (`--print`, no TUI) | CW-3 |
| | pi reads the project files as context | `@file`/`@dir` context in `pi-run` | CW-3 |
| | a missing or misconfigured pi fails the stage clearly | explicit error, non-zero exit, no install attempt | CW-2 |
| | an unreachable backend fails the stage clearly | backend reachability probe | CW-2 |
| **requirement-extraction** | the baseline captures the issue's change set | `baseline` action (ref + diff artifact) | CW-4 |
| | requirements are derived from the project itself | `requirements.md` prompt (arc42 md + diff + docs/README context) | CW-3 |
| | requirements are written as Gherkin files | prompt writes to `requirements-dir`; valid-Gherkin check | CW-3 |
| | Gherkin structure follows the canonical keywords | prompt template + parse validation | CW-3 |
| | an empty issue body does not produce invented requirements | prompt rule → write nothing, report “no delta requirements” | CW-3 |
| | re-running extraction on unchanged input is idempotent | deterministic prompt + input; no-op diff | CW-3 |
| **guard-rail** | a clean stage passes the guard | `guard-check` exits 0 | CW-5 |
| | a leaking stage is reverted and re-run | checkout/clean off-limits + re-run loop | CW-5 |
| | the allowed file set is per-stage | per-stage allow arguments | CW-5 |
| | a requirement edited during implementation loops back to planning | implement-check excludes `requirements-dir` → back to stage 6 | CW-5 |
| | guard re-runs are capped | loop counter + `max-loops` (0 = no cap) | CW-5, CW-11 |
| | all three checks share one shell idiom | one script, three call sites (§4.1) | CW-5 |
| **plan** | the plans cover every requirement change | `plan.md` prompt (coverage of all changes) | CW-3, CW-6 |
| | the plan describes how the requirements are fulfilled | prompt output contract (slices + file-level changes) | CW-3 |
| | the plan is grounded in the current architecture | arc42-markdown + `docs/` context | CW-3 |
| | the plan stage may only touch plans/ | plan-check guard | CW-5, CW-6 |
| **implement** | the plan is implemented as code | `implement.md` prompt | CW-3, CW-7 |
| | tests are generated for the new behaviour | prompt tests section | CW-7 |
| | the arc42 documentation is updated and complete | prompt updates the arc42 markdown under `doc-dir` | CW-7 |
| | the README is kept current | prompt | CW-7 |
| | implementation must not edit requirements | implement-check exclude set | CW-5, CW-7 |
| | the implement stage may mark plan tasks as done | implement-check allow set includes `plan-dir` (the plan tracks state) | CW-5, CW-7 |
| | the plan is handed to pi as its files | `dir_files()` expands the plan dir to file @-arguments (a dir argument crashes pi) | CW-3, CW-7 |
| | the allow set covers the repo's real layout | `source_dirs()` + explicit allow additions | CW-5, CW-7 |
| **test-and-review** | Gherkin scenarios run as executable acceptance tests | target's `make test` contract (Cucumber runner over `requirements/`) | CW-8 |
| | each requirement is checked for fulfilment | `review.md` prompt over the results | CW-3, CW-8 |
| | a failed scenario is fixed and re-reviewed | fix loop (§3, stage 11) | CW-8 |
| | the fix loop is bounded by MAX_LOOPS | loop counter (non-zero cap) | CW-8, CW-11 |
| | the loop respects the token budget | usage accumulator | CW-11 |
| | every iteration is logged without touching the repo tree | workflow log + artifact only | CW-8, CW-12 |
| **pr-and-gates** | a pull request is opened against the target branch | `pr-open` action (`gh pr create`, head `ai/<issue_number>`) | CW-9 |
| | the PR body links back to the work | body template (source issue + status report) | CW-9 |
| | all PR-triggered workflows must be green | `pr-gates` poller | CW-9 |
| | a failed gate is fixed and re-checked | gate-fix loop | CW-9 |
| | the gate loop is bounded | `max-loops` (0 = no cap) | CW-9, CW-11 |
| | merging stays a human decision | no merge call exists in the workflow | CW-9 |
| **reporting** | the final status report is the PR | PR description rendered from stage results (§4.5) | CW-10 |
| | the source issue is commented with the outcome | report-stage issue comment | CW-10 |
| | the arc42 documents the AI activity | AI-activity section in the arc42 markdown | CW-10 |
| | a failed run is reported too | failure path: issue summary, no repo file | CW-10 |
| **reuse-by-ref** | the factory is invoked as a reusable workflow | `factory.yml` under `.github/workflows/` | CW-1 |
| | the target workflow stays short and stable | consumer example (§6); no logic inlined | CW-14 |
| | composite actions are referenced by owner, repo and path | `.github/actions/*` | CW-1, CW-14 |
| | an upgrade is a ref bump | release tags; one-line consumer change | CW-14 |
| | every published version is a stable ref | `release.yml` semver tags, immutable | CW-14 |
| **configuration** | the trigger label is configurable | CW-1 |
| | the target branch is configurable | CW-1 |
| | the artefact directories are configurable | CW-1 (inputs drive the guard allow sets) |
| | the LLM backend is a pre-requisite of the environment | CW-2 |
| | which configured model is used is adjustable | CW-2 |
| | the action ref is configurable | the consumer's `uses:` line (documented) | CW-14 |
| | the loop caps are configurable | CW-11 |
| | a loop cap of 0 means no cap | CW-11 |
| | settings flow from workflow inputs to stage environment | `with:` → env mapping in `factory.yml` | CW-1 |
| | secrets are never plain inputs | `secrets:` block only | CW-12 |
| **safety** | GH_TOKEN is repo-scoped and never committed | secret handling (§5) | CW-12 |
| | the LLM backend needs no secret | env pre-requisite; URL/model only | CW-2 |
| | every loop in the pipeline respects its cap | §4.3 (0 = uncapped; guarantee while non-zero) | CW-11 |
| | work only happens on the AI branch | all writes on `ai/<issue_number>` | CW-12 |
| | a broken stage cannot corrupt the target branch | guard + branch isolation | CW-5, CW-12 |
| | the factory tolerates arc42 structure variance | extraction prompt (§3, stage 4) | CW-3 |
| | an audit trail exists for human review | workflow-log/artifact logs + arc42 AI-activity | CW-12, CW-10 |

## 8. Tickets (build order = dependency order)

| Ticket | Scope | Acceptance = scenarios |
|---|---|---|
| **CW-0** | *epic*: end-to-end reusable workflow + actions, all stages wired, first release tagged | all 102 |
| CW-1 | `factory.yml` skeleton: trigger job (label gate, dispatch, idempotency lock), `with:`→env mapping, permissions, job graph | trigger ×6; configuration: inputs flow, label, target branch, directories |
| CW-2 | `setup-pi` action: verify-never-install flow (presence; backend pre-requisite; model in configured set; smoke check; explicit failures) | setup-pi ×6 (of 8 — headless/context are CW-3); configuration: backend pre-requisite, model adjustable; safety: backend needs no secret |
| CW-3 | `pi-run` action + the four prompt templates (`requirements.md`, `plan.md`, `implement.md`, `review.md`) | setup-pi: headless, context; requirement-extraction: derive/Gherkin/no-invention/idempotent; plan: cover/describe/grounded; implement: all 5 generation scenarios (incl. plan state tracking); test-and-review: “each requirement checked”; safety: arc42 structure variance |
| CW-4 | `baseline` action: branch `ai/<issue_number>`, baseline ref, issue-diff artifact | requirement-extraction: baseline |
| CW-5 | `guard-check` idiom + the three check stages with their re-run loops | guard-rail ×6; implement: “must not edit requirements”; safety: “broken stage cannot corrupt” |
| CW-6 | plan stage + plan-check (combined plans covering every change) | plan ×4 |
| CW-7 | implement stage + implement-check (code, tests, arc42 markdown set complete, README, plan state tracking) | implement ×8 |
| CW-8 | test-and-review: Gherkin-oracle wiring (target `make test` contract), review, fix loop, per-iteration logging outside the repo tree | test-and-review ×6 |
| CW-9 | `pr-open` + `pr-gates` + gate-fix loop (PR `ai/<n>` → `target-branch`; PR body = report; all-gates-wait; no merge) | pr-and-gates ×6 |
| CW-10 | `report` stage (PR body = final status; issue comment; arc42 AI-activity section; failure path, no repo files) | reporting ×4 |
| CW-11 | loop caps & token budget (0 = no cap; guarantee while non-zero; job-timeout backstop) | safety: “every loop respects its cap”; configuration: caps; test-and-review: bounded/budget; guard-rail: re-runs capped; pr-and-gates: gate loop bounded |
| CW-12 | secrets & branch hygiene (repo-scoped `GH_TOKEN`; no secrets in inputs; writes only on `ai/<n>`; main never touched; audit trail in workflow log/artifacts) | safety: token, branch ×2, audit trail; configuration: secrets; test-and-review: logging outside tree |
| CW-13 | *(optional stretch)* JS actions published as an npm package — **not currently in the Gherkin**; becomes mandatory if the owner restores the “JS actions ship as npm packages” scenario (§10) | — (pending owner decision) |
| CW-14 | release & ref-bump machinery (`release.yml`, semver tags, immutable old refs) + documented target-repo example | reuse-by-ref ×5; configuration: “action ref is configurable” |
| CW-15 | repo scaffolding: README, house-CI workflow (ubuntu-latest, `uv`, `pytest` parity), `.gitignore` (+ `package.json` only if CW-13 lands) | repo-level |

## 9. Milestones

| M | Tickets | Done means |
|---|---|---|
| **M1** | CW-1, CW-2, CW-3 | a labelled issue gets a run that passes the setup-pi smoke on the selected configured model |
| **M2** | CW-4 – CW-7 | an issue with a change diff → valid Gherkin in `requirements/`, plans, implementation; all three guards green (leak → revert → re-run demonstrated) |
| **M3** | CW-8 – CW-12 | full run opens a PR from `ai/<n>` whose body is the status report; review-fix & gate-fix loops run with caps (0 = uncapped); failure path reports on the issue with zero repo files |
| **M4** | CW-14, CW-15 | first `vX.Y.Z` tag + release; target-repo example documented; house CI keeps this repo green |
| *(stretch)* | CW-13 | npm-package action mechanism — only if the owner restores the npm scenario |

## 10. Risks & open items

- **Gherkin as oracle** — green scenarios ≠ right behaviour (inherent to BDD); the
  review stage (pi reads the whole diff) is the second layer.
- **Runner environment is a pre-requisite** — pi installed & configured, backend
  reachable from the runner. Stage 2 fails explicitly; a target whose runner can't
  meet it simply doesn't run the factory.
- **Self-editing separation** — implement/gate allow sets exclude `requirements-dir`:
  intra-PR test fixes are fine, requirement edits are not (safety/guard-rail
  scenarios). The implement allow set **includes `plan-dir` and `PLAN.md`**:
  the plan is a live state tracker (finished tasks are marked done in the
  plan file; in a repo without a `docs/` dir the top-level `PLAN.md` is the
  arc42 set that tracks the same state), so those edits must survive the
  implement-check — reverting them would burn the loop budget re-fighting
  the same state update every iteration (the failed self-hosted run for
  issue #3 died exactly this way).
- **arc42 structure varies per target** — the extraction prompt tolerates the readable
  parts (safety scenario).
- **Open item for the owner** — the “JS actions ship as npm packages” scenario is **not
  on `main`** (it was in the original requirements commit and fell out of the PR #1
  re-slice). If that was deliberate, the plan stands as written (CW-13 stays an
  optional stretch). If it was accidental, say so and I'll restore it — CW-13 then
  becomes mandatory and the npm mechanism joins §2.
- *Fixed by the accompanying commit in this PR:* `pr-and-gates.feature`'s Background
  still read `ai/code-weaver/<issue_number>` while `trigger.feature` and
  `safety.feature` already read `ai/<issue_number>` (the explicit clarification);
  left as-is, `main` would be self-contradictory and the factory's own stage 10 would
  flag it.
