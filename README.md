# Code Weaver

An **AI software factory that creates programs** — driven entirely by
[GitHub Actions](https://github.com/features/actions), not a service. A
maintainer edits an issue labelled `ai-requirements` in a target project, and
this repo's reusable workflow takes over:

1. **trigger** — the labelled issue (or a manual dispatch with an issue
   number) starts a run; re-entrant triggers on the same issue are
   idempotent;
2. **setup-pi** — verifies `pi` is **pre-installed & pre-configured** in the
   runner environment (the LLM backend is a fixed pre-requisite; the only
   adjustable LLM setting is which configured model is used). The factory
   verifies — it never installs;
3. **baseline** — cuts the AI branch `ai/code-weaver/<issue>` and records the
   baseline;
4. **requirement-extraction** — pi derives the **delta requirements** from the
   project itself (the arc42 markdown + the issue + the change-set diff) and
   writes them as **Gherkin** into `requirements/` — one new file named after
   the issue (existing files untouched), an empty body writes nothing, and the
   result is validated with Cucumber's official parser;
5. **requirement check** — the shared guard: only the requirements dir may
   have changed (and the delta's shape is pinned: at most one new file named
   after the issue);
6. **plan** — markdown plan(s) under `plans/`, covering **every** requirement
   change, grounded in the arc42 documentation;
7. **plan check** — same guard idiom;
8. **implement** — code, generated tests, the arc42 docs kept complete, README
   current;
9. **implement check** — same guard (its allow set also covers the plan dir
   — the plan is a live state tracker: finished tasks are marked done); a
   requirement edited here **loops back to the plan stage**;
10. **test-and-review** — the target's test suite (`make test`) runs every
    Gherkin scenario as an acceptance test; pi marks each scenario
    fulfilled/unfulfilled and reviews the diff;
11. **fix loop** — unfulfilled → pi fixes → re-run, bounded by the loop caps;
12. **open the PR** — from `ai/code-weaver/<issue>` against the target branch;
    **the PR body is the status report**;
13. **PR gates** — every workflow run triggered on the PR must be green;
14. **gate-fix loop** — a red gate gets fixed and re-polled, bounded;
15. **final status report** — the PR body is completed, the source issue is
    commented, and an AI-activity section lands in the arc42 docs.

**Merging is never the factory's job.** It opens the PR and stops.

## Consume it (by ref — never copy-paste)

In the target repo, `.github/workflows/code-weaver.yml`:

```yaml
name: code-weaver
on:
  issues:            # editing an issue to add the label starts a run
    types: [opened, edited, labeled]
  workflow_dispatch:
    inputs:
      issue_number: { description: Issue to process, type: string, required: false }
permissions:
  contents: write
  issues: write
  pull-requests: write
jobs:
  factory:
    # a reusable-workflow job may only carry `uses`/`with`/`secrets` — a
    # `runs-on:` here makes the file schema-invalid. Choose the runner
    # through the factory's `runner` input instead.
    uses: MelvinsPersonalProjects/code-weaver/.github/workflows/factory.yml@v0.1.0
    with:
      issue-number: ${{ github.event.issue.number || inputs.issue_number }}
      ai-requirements-label: ai-requirements
      target-branch: main
      llm-model: Ornith-1.5-35B-A3B  # which configured model — the one adjustable LLM setting
      runner: <label of a runner whose environment has pi pre-installed & configured>
    secrets:
      GH_TOKEN: ${{ secrets.GH_TOKEN }}   # repo-scoped; never a plain input
```

The `GH_TOKEN` secret holds the token every factory stage authenticates with
— it must be a token that **can read the target repo** (its user/app a member
of the owning org; a fine-grained PAT scoped to *this* repository). Stage 1
verifies this up front: a missing, dead or wrongly-scoped token fails within
seconds with the exact cause in the log — not as an opaque red checkout.

**Upgrading is a ref bump** in that one `uses:` line — a reusable workflow
(plus the composite actions and pi prompt templates it references, all from
this repo). **Every published version is a stable ref**: tag `vX.Y.Z` →
GitHub release; targets pinned to an older ref keep working.

## Inputs

| input | default | meaning |
|---|---|---|
| `issue-number` | *(the triggering issue)* | which issue to process |
| `ai-requirements-label` | `ai-requirements` | the trigger label |
| `target-branch` | `main` | PR base branch |
| `requirements-dir` | `requirements` | where Gherkin requirements live |
| `plan-dir` | `plans` | where plans live |
| `doc-dir` | `docs` | where the arc42 markdown files live |
| `llm-model` | `Ornith-1.5-35B-A3B` | which **configured** model pi uses |
| `max-loops` | `25` | fix/guard loop cap per stage — **`0` = no cap** |
| `max-tokens` | `5000000` | token budget across the run — **`0` = no cap** |
| `runner` | `ubuntu-latest` | runner label (its environment must carry the pi pre-configuration) |
| `workflow-name` | `code-weaver` | the target's workflow file name (idempotency query) |

The **LLM backend is not an input** — it is a pre-requisite of the runner's
pi configuration, fixed. Stage 2 verifies presence → configuration →
reachability → configured-model set → a headless smoke check, and fails with
an explicit message if any of that is missing.

The `gh` CLI is the factory's second runner pre-requisite (the trigger,
pr-open and gates stages shell out to it). One hygiene rule keeps it working:
the runner **user** must own `~/.config` — a root-owned `~/.config` (left
behind by an installer that ran as root) makes every token-bearing `gh`
invocation die with `permission denied`, because gh initialises its config
under that directory. Field case: on the ct133 runner this made the gates
job's `Resolve the PR's head sha` step fail while every job scheduled to a
healthy runner ran fine; `chown runner:runner ~/.config` on the runner fixed
it without touching the factory.

## Repository layout

```
.github/
  workflows/
    factory.yml        the 15-stage pipeline as one reusable workflow
    house-ci.yml       this repo's own gate (uv; compile+YAML+oracle+pytest)
    release.yml        tag vX.Y.Z → GitHub release (the ref targets pin)
  actions/
    setup-pi/          stage 2 — verify (never install) pi + backend + model
    pi-run/            one headless `pi --print` run (the stage primitive)
    baseline/          stage 3 — branch ai/code-weaver/<issue> + baseline ref
    guard-check/       THE one shared "only X changed" guard script
    extract-stage/     stages 4+5 — extraction + requirement check
    plan-stage/        stages 6+7 — planning + plan check
    implement-stage/   stages 8+9 — implementation + implement check
    review-stage/     stages 10+11 — test oracle + review + fix loop
    pr-open/           stage 12 — push & open the PR (body = report)
    gates-stage/       stages 13+14 — all PR-triggered workflows green
    report/            stage 15 — PR body = final status; issue comment; arc42 activity
  scripts/
    common.py          shared plumbing (state dir, caps, guard, pi, git)
    stages.py          the shared generation/review loop machinery
    gherkin-validate.py  Cucumber-official-parser Gherkin validation
pi-prompts/            the four pi prompt templates
requirements/          the Gherkin oracle for THIS repo (102 scenarios)
tests/                 unit tests (the validator)
PLAN.md                the implementation plan this code implements
```

## Requirements

`requirements/` holds **102 Gherkin scenarios** — the oracle this
implementation satisfies. House CI validates them with Cucumber's official
parser on every push/PR; in a target repo the test-and-review stage runs them
as executable acceptance tests.

## What this is *not*

- not a long-running service — a workflow you trigger on an issue;
- not a merger — the PR it opens waits on a human;
- not an installer — it assumes a runner environment where pi is ready, and
  says so loudly when it is not.
