# 4. Context & Scope

**Target repo.** Any GitHub repo — no pre-installed or pre-configured pi
is a pre-requisite of its runner environment (the factory's setup stage
installs pi for the run and configures it for the workflow run; the
run's harness providers ride the consumer workflow's `secrets:` block).
The target installs the factory by adding ONE short workflow
(`.github/workflows/code-weaver.yml`) that names a ref, passes inputs and
the harness-provider secrets:

```yaml
jobs:
  factory:
    uses: MelvinKl/code-weaver/.github/workflows/factory.yml@7
    with: { issue-number: …, ai-requirements-label: ai-requirements,
            target-branch: main, llm-model: …, runner: … }
    secrets: { GH_TOKEN: ${{ secrets.GH_TOKEN }}, … }
```

The `secrets:` block also carries the run's four optional
harness-provider secrets (`PI_MODELS`, `PI_SETTINGS`, `PI_MCP`,
`PI_EXTENSION_ENV` — the run's pi harness, chapter 8); a provider value
never appears in a `with:` input or a committed file.

The consumer workflow is the **only per-target code** — it stays short
and stable (it declares the `labeled`-only issue trigger plus a manual
dispatch; opening or editing an issue schedules no run), carries no
pipeline logic, and references the factory by owner, repo, path and ref
— one pin: the file at the ref carries its runtime tree embedded, so no
second ref accompanies it. The oracle pins the owner (`MelvinKl`) and a
**version tag** — a moving branch ref is not a stable ref. The one
declared exception is the factory project's own repo (chapter 8): its
consumer workflow pins the public release line — a version tag of the
MelvinKl line — like its external targets; a run triggered in it checks
and works the code of the repo it was triggered in, while the machinery
it works with is the published version — the dogfood exercises what its
external targets get.

**In scope** — the 15-stage pipeline (chapter 5/6): trigger, setup-pi,
baseline, requirement-extraction (+ requirement check), planning (+ plan
check), implementation (+ implement check), test-and-review (+ fix
loop), PR open, PR gates (+ gate-fix loop), final status report.

**Out of scope** — the optional "JS actions ship as an npm package"
stretch (it is not on the Gherkin oracle's `main`; it becomes mandatory
only if the owner restores that scenario, per `PLAN.md` §10); long-running
services. Installing and configuring pi inside CI is **in scope** — it is
the factory's own setup stage, run for every run.
