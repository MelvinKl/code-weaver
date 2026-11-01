# Code Weaver

> **Warning — read before you use the factory in a target repo.**
>
> This warning is addressed to the maintainers of the repo a factory
> run targets. It states three things you need before you consume the
> workflow — where the workflow should be used, who can start a
> factory run, and what a run consumes:
>
> 1. **Use the code-weaver workflow only in a private repo.** A run is
>    started from the target repo's own issue surface, and a public
>    repo's issue surface is public: hosting the workflow there hands
>    run-starting to the people in point 2, at the cost of point 3.
> 2. **Everyone who can create or tag issues in the target repo can
>    create a workflow run of the factory.** A `labeled` issue event
>    with the trigger label — or a manual dispatch with an issue number
>    — starts a run; the trigger's only gate is the label, and it does
>    not ask who added it.
> 3. **Such a run consumes tokens and creates cost for the repo.**
>    Every pi call the run makes spends tokens billed against the run's
>    model configuration; the run's total cost and token usage are what
>    the final report lists, on the PR and the issue.

An **AI software factory that creates programs** — driven entirely by
[GitHub Actions](https://github.com/features/actions), not a service. A
maintainer adds the `ai-requirements` label to an issue in a target project, and
this repo's reusable workflow takes over:

1. **trigger** — a label addition to an issue (or a manual dispatch with
   an issue number) starts a run; re-entrant triggers on the same issue are
   idempotent;
2. **setup-pi** — installs pi for the run and configures it for the
   workflow run: every later pi invocation in the run uses that installed
   copy, and the stage materialises the run's provided harness — the model
   configuration, the additional packages, the MCP configuration, the
   extension's environment variables — resolving each element's provider
   (a non-empty GitHub secret wins over the named repo file) into the agent
   directory the run's pi invocations resolve (`~/.pi/agent/`, or
   `PI_CODING_AGENT_DIR`). No pre-installed or pre-configured pi is a
   pre-requisite of the runner environment — the stage installs and
   configures pi itself, and fails explicitly where it cannot; the only
   adjustable LLM setting is which configured model the run uses (the
   backend is the one in the run's provided model configuration, not a
   property of the runner);
3. **baseline** — cuts the AI branch `ai/code-weaver/<issue>` and records the
   baseline;
4. **requirement-extraction** — pi derives the **delta requirements** from the
   project itself (the arc42 markdown + the issue + the change-set diff) and
   writes them as **Gherkin** into `requirements/` — the project context is
   handed to pi in two parts: the arc42 markdown, `README.md` and the
   baseline diff as `@`-file arguments, which pi reads as context before
   answering, and the oracle as the requirements directory named in the
   instructions — pi reads the files it judges relevant from it on demand
   (a directory is never an `@`-argument); arc42
   structure variance is tolerated (extraction proceeds on the readable
   parts); the result is the delta placed by topic — the existing topic
   file extended in place, a new file only for a topic no file yet covers,
   never named after an issue — a changed existing file that no longer
   parses is a guard violation, reverted and re-run — an empty body writes
   nothing and the factory stops cleanly there, where the target has a
   requirements directory; a first run on a target without one derives the
   full requirements set from the project's code, documentation and tests
   and creates the directory; the result is validated with Cucumber's
   official parser (skipped-not-failed where the parser port is absent);
5. **requirement check** — the shared guard: only the requirements dir may
   have changed (and the delta's shape is pinned to the topic placement —
   extended existing topic files, new files only for uncovered topics,
   never named after an issue); a change outside the allowed set is a
   guard repair — the guard calls pi to revert the off-limits files in
   place and keeps the stage's own work valid; the stage is not re-run;
6. **plan** — markdown plan(s) under `plans/`, covering **every** requirement
   change, grounded in the arc42 documentation (the `docs/` set — the
   top-level `PLAN.md` where a target has no doc dir); the instructions
   carry the delta — which requirement files changed and what those files
   changed — the files ride the path-referenced context (read on demand,
   never embedded; the whole oracle is not injected into the planner) — and
   where the run's delta is the brownfield shape (every changed requirement
   file new against the baseline — the extraction created the requirements
   directory, so the baseline knows none of them), the instructions attach
   the brownfield scope: the plan names the extracted scenarios it must
   cover and scopes its steps to adjusting the tests to reference those
   scenarios — no plan step implements code;
7. **plan check** — same guard idiom — a change outside the one allowed
   plan file is reverted by the guard's pi call and the plan stage re-runs
   (the guard re-checks the re-run; only the plan file is left changed; a
   clean plan stage completes without re-running);
8. **implement** — code, generated tests (a test that implements a Gherkin
   scenario cites it in its docstring as `<feature file>::<scenario name>`;
   a correctness-only test cites nothing — the reference is the join the
   review stage and the suite read), the arc42 docs kept complete, README
   current — and, where the plan is a brownfield plan, the run adjusts the
   tests without implementing code: no source code changes (the changed
   files are the tests and the issue's plan file), the existing tests are
   adjusted to reference the requirements they describe, and each adjusted
   test that implements a scenario cites it in its docstring as
   `<feature file>::<scenario name>`;
9. **implement check** — same guard, run INVERTED: the implementation's
   lane is everything EXCEPT the protected set (requirements and plans) —
   it has the job to implement the tests, and the guard must not re-litigate
   where the implementation creates its new code or test dirs (a whitelist
   snapshotted at stage start used to revert a brand-new `tests/` dir every
   iteration); inside the denied sets, exactly the current issue's plan file
   is re-allowed (the plan is a live state tracker: finished steps are
   marked done) — never another issue's plan; a requirement edited
   here **is repaired in place — the guard's pi call reverts it; the stage
   is not re-run** (no loop back to the plan stage);
10. **test-and-review** — the target's test suite (`make test`) runs every
    Gherkin scenario as an acceptance test; the review runs on every
    iteration's output (red or green), and pi marks each scenario of the
    feature files this run changed — plus the scenarios the run's changed
    tests reference (a changed test is judged by the requirement it
    references) — fulfilled/unfulfilled (the delta scope —
    re-judging the whole accumulated oracle every run is the unbounded work
    the review must not do) and notes anything the tests don't cover that
    affects those scenarios; its full output is the reviewer's report,
    mirrored per iteration into the state dir (artifact);
11. **fix loop** — the fix directive carries the reviewer's report (named
    by path — the fixer reads it on demand) alongside the unfulfilled
    verdicts and, for a red suite, the raw output tail; unfulfilled or red
    → pi fixes → re-run, bounded by the loop caps;
12. **open the PR** — from `ai/code-weaver/<issue>` against the target branch;
    **the PR body is generated by pi from the requirements, the plan and the
    review and describes the issue the run implements** (a template assembles
    the same description as the fallback if the pi call produces nothing —
    the issue, its plan, the scenarios the run changed; the resolved
    configuration stays in the workflow log) — the body is the status report;
13. **PR gates** — every workflow run triggered on the PR must be green;
14. **gate-fix loop** — a red gate gets fixed and re-polled, bounded;
15. **final status report** — the PR body is completed (and verified on the
    PR — where it could not be applied, the issue comment carries the full
    final status itself, so the description and the comment never disagree
    on the run's usage numbers), the source issue is commented and closed
    when the run succeeded (a failed run leaves it open), and an AI-activity
    section lands in the arc42 docs (the `docs/` set — a target without a doc
    dir gets it in its top-level arc42 markdown).

**Merging is never the factory's job.** It opens the PR, closes the issue
behind it, and stops.

## Consume it (by ref — never copy-paste)

In the target repo, `.github/workflows/code-weaver.yml`:

```yaml
name: code-weaver
on:
  issues:            # only a label addition starts a run — opening or editing no longer fires it
    types: [labeled]
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
    uses: MelvinKl/code-weaver/.github/workflows/factory.yml@7
    with:
      issue-number: ${{ github.event.issue.number || inputs.issue_number }}
      ai-requirements-label: ai-requirements
      target-branch: main
      llm-model: Ornith-1.5-35B-A3B  # which configured model — the one adjustable LLM setting
      runner: <label of the runner the stage jobs run on — pi is installed & configured for the run by stage 2>
      dependency-install: make install  # the command that installs the target project's dependencies — omit the line where the target needs no such step (the run is unchanged)
    secrets:
      GH_TOKEN: ${{ secrets.GH_TOKEN }}   # repo-scoped; never a plain input
      # the run's pi harness providers — optional: an unset secret arrives
      # empty and stage 2 treats it as an absent provider (the repo's
      # .pi/agent/models.json, .pi/settings.json and .pi/mcp.json are the
      # fallbacks); never a plain input
      PI_MODELS: ${{ secrets.PI_MODELS }}
      PI_SETTINGS: ${{ secrets.PI_SETTINGS }}
      PI_MCP: ${{ secrets.PI_MCP }}
      PI_EXTENSION_ENV: ${{ secrets.PI_EXTENSION_ENV }}
```

**Why the consumer pins once.** GitHub fetches only the called
workflow's file — the runner never checks the factory repo into the
target's workspace — so the called ref is not visible to the stage
jobs. The old answer relayed the ref as a `factory-ref` input (a second
pin beside the `uses:` line) and had each stage job clone the factory
repo at it; the restored-and-improved answer carries the answer in the
file instead: the workflow's runtime tree (the stage scripts, the
shared scripts, the pi prompt templates) is **embedded in the workflow
file** — a base64 tarball in stage 1's first step, which materialises
it into the runner's temp dir before any checkout replaces the
workspace, and the trigger's artifact carries it to every later stage
job's first step (that upload opts into hidden files — the tree lives
under the hidden .github/ directory, which the artifact API would
otherwise drop). No run fetches the factory repo, and no stage reads
the `factory-ref` input (a legacy no-op, still declared so an older
consumer's `with:` block stays schema-valid): the ref on the `uses:`
line is the only version selection a run makes — one ref selects the
workflow file and its runtime tree as one version.

The `GH_TOKEN` secret holds the token every factory stage authenticates with
— it must be a token that **can read the target repo** (its user/app a member
of the owning org; a fine-grained PAT scoped to *this* repository). Stage 1
verifies this up front: a missing, dead or wrongly-scoped token fails within
seconds with the exact cause in the log — not as an opaque red checkout.

**Upgrading is a ref bump** in that `uses:` line — and that is the only
pin: the file at the ref carries the runtime tree its steps execute (the
scripts, the pi prompt templates) embedded in it, so the ref selects the
reusable workflow — self-contained, its stage steps inlined in the
workflow file and its runtime tree embedded in the file — as one version
from the factory repo; a ref bump selects the whole version.
**Every published version is a stable ref**: a push to the factory's `main`
branch publishes the next single increasing number as a GitHub release;
targets pinned to an older ref keep working. A push whose changed files
are confined to the consumer workflow publishes no release (no tag, no
release, no number spent — the version it would have carried is
unchanged), and a release's notes name the changes since the predecessor
release — the first commit only where there is no predecessor — and are
never empty for a release that publishes changes.

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
| `max-loops` | `5` | fix/guard loop cap per stage — **`0` = no cap** |
| `runner` | `ubuntu-latest` | runner label the stage jobs run on (pi is installed & configured for the run by stage 2 — not a pre-requisite of the runner's environment) |
| `workflow-name` | `code-weaver` | the target's workflow file name (idempotency query) |
| `dependency-install` | *(empty)* | the command the run's pipeline runs to install the target project's dependencies — executed in the jobs whose stages consume them (the implementation, the test-and-review's suite run), after each job's checkout and before its stage; empty = no such step, the run is unchanged |
| `factory-ref` | *(empty)* | **legacy no-op** — still declared so a `with:` block written for an older version of this file stays schema-valid; no stage reads it anymore: the runtime tree is embedded in the workflow file, so the ref on the `uses:` line is the only pin a run makes (the factory project's own repo pins the public release line too — a run triggered in it works the code of the repo it was triggered in, and the dogfood exercises the published version its external targets get, chapter 8) |

The **LLM backend is provided for the run** — via a GitHub secret or the
repo file `.pi/agent/models.json`. The runner's pre-existing user-level
configuration is replaced for the run, never what the invocation
resolves. Stage 2 installs pi for the run, resolves the harness providers
(a non-empty GitHub secret wins over the named repo file), writes the
harness into the agent directory the invocation resolves, then verifies —
backend reachability → the model in the set the stage wrote → a headless
smoke check of the installed pi — and fails with an explicit message if
any of that is missing.

**The run's pi harness is provided per run.** Each element rides a GitHub
secret in the consumer workflow's `secrets:` block (the four optional
provider secrets of the example above; `GH_TOKEN` stays the only required
one), a non-empty secret winning over the named repo file:

| harness element | GitHub secret | repo file |
|---|---|---|
| the model configuration — the run's LLM backend is defined in it | `PI_MODELS` | `.pi/agent/models.json` |
| the additional-packages settings | `PI_SETTINGS` | `.pi/settings.json` |
| the MCP configuration | `PI_MCP` | `.pi/mcp.json` |
| the extension's environment variables — a `.env`-style secret, such as the ones `.pi/extensions/pi-jev-config.ts` carries | `PI_EXTENSION_ENV` | — (the secret is the provider) |

An empty or absent settings provider leaves pi without additional
packages, and an absent MCP provider means the run's pi runs without MCP
servers; the stage clears an element without a provider from the agent
directory rather than inheriting the runner's pre-existing user-level
configuration.

**The target's dependencies are installed by the run, where the target
declares it.** The optional `dependency-install` input (the consumption
example above shows the declaration — one line in the `with:` block)
names the command the run's pipeline runs to install the target
project's dependencies: the run executes it in the jobs whose stages
consume them — the implementation stage and the test-and-review stage's
suite run — after each of those jobs' checkout of the AI branch and
before its stage, so both stages see an environment the project's
dependencies are installed in (a checkout replaces the workspace, so
the step runs once per consuming job). A target that leaves the input
empty (the default) runs unchanged: the step is a no-op that logs and
exits without touching the workspace, and the run is unchanged by the
mechanism's presence.

The `gh` CLI is the factory's surviving runner pre-requisite (the trigger,
pr-open and gates stages shell out to it); one hygiene rule keeps it
working: the runner **user** must own `~/.config` — a root-owned
`~/.config` (left behind by an installer that ran as root) makes every
token-bearing `gh` invocation die with `permission denied`, because gh
initialises its config under that directory. Field case: on the ct133
runner this made the gates job's `Resolve the PR's head sha` step fail
while every job scheduled to a healthy runner ran fine; `chown
runner:runner ~/.config` on the runner fixed it without touching the
factory.

## Repository layout

```
.github/
  workflows/
    factory.yml        the 15-stage pipeline as one self-contained, self-carrying reusable workflow (the stage steps inlined in the file; the runtime tree embedded in it as a base64 tarball — one ref is one version; no composite actions)
    house-ci.yml       this repo's own gate (uv; compile+YAML+oracle+pytest)
    release.yml        push to main → next single increasing number → GitHub release (a push whose changed files are confined to the consumer workflow publishes no release — no tag, no number spent; the ref targets pin; the default GITHUB_TOKEN publishes the tag on main's HEAD — no special token)
  actions/
    <stage>/           the stage's python script — the stage's STEPS are inlined in factory.yml (the workflow is self-contained: no composite actions to reference, no own-action ref for the release to rewrite, no runtime tree for a stage job to fetch — the file carries it embedded); each dir holds the script its inlined stage step runs
    setup-pi/          stage 2 — install pi for the run + write the provided harness + backend/model checks
    pi-run/            one headless `pi --print` run (the stage primitive)
    baseline/          stage 3 — branch ai/code-weaver/<issue> + baseline ref
    guard-check/       THE one shared "only X changed" guard script (the stages call it in-process)
    extract-stage/     stages 4+5 — extraction + requirement check
    plan-stage/        stages 6+7 — planning + plan check
    implement-stage/   stages 8+9 — implementation + implement check
    review-stage/     stages 10+11 — test oracle + review + fix loop
    pr-open/           stage 12 — push & open the PR (body = report)
    gates-stage/       stages 13+14 — all PR-triggered workflows green
    report/            stage 15 — PR body = final status (verified); issue comment + close on success; arc42 activity
  scripts/
    common.py          shared plumbing (state dir, caps, guard, pi, git)
    stages.py          the shared generation/review loop machinery
    gherkin-validate.py  Cucumber-official-parser Gherkin validation
    release-number.py  the release flow's number, guard and skip computations (release.yml pipes the remote's tag list in for the next single increasing number, the tag lines into the one-tag-per-commit guard, and the push's changed files into the pre-publish skip — confined to the consumer workflow → no release published)
    embed-runtime.py   the release pipeline's rewrite of factory.yml — embeds the runtime tree in the file (`make embed`; the release flow gates publication on its freshness)
pi-prompts/            the pi prompt templates (requirements, plan, implement, review, pr-body)
requirements/          the Gherkin oracle for THIS repo (16 files, 180 scenarios)
docs/                  the arc42 set — one chapter per file (01–11); 01 carries the AI-activity section
tests/                 unit tests (the validator + stage contracts)
PLAN.md                the implementation plan this code implements
```

## Requirements

`requirements/` holds **180 Gherkin scenarios** — the oracle this
implementation satisfies. The files are **structured by topic, not by
issue**: each file is named after the topic it covers, so a search for a
topic targets that topic's file instead of sweeping the whole oracle — and
house CI rejects any feature file named after an issue number, so the
structure holds for every file the factory creates or edits. House CI
validates them with Cucumber's official parser on every push/PR; in a target
repo the test-and-review stage runs them as executable acceptance tests.

## What this is *not*

- not a long-running service — a workflow you trigger on an issue;
- not a merger — the PR it opens waits on a human;
- not a pre-requisite of the runner environment — the setup stage installs
  and configures pi for the run itself, and says so explicitly where it
  cannot.
