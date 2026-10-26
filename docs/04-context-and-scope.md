# 4. Context & Scope

**Target repo.** Any GitHub repo whose runner environment has `pi`
pre-installed and pre-configured. The target installs the factory by
adding ONE short workflow (`.github/workflows/code-weaver.yml`) that
names a ref and passes inputs:

```yaml
jobs:
  factory:
    uses: MelvinKl/code-weaver/.github/workflows/factory.yml@v0.1.0
    with: { issue-number: …, ai-requirements-label: ai-requirements,
            target-branch: main, llm-model: …, runner: … }
    secrets: { GH_TOKEN: ${{ secrets.GH_TOKEN }} }
```

The consumer workflow is the **only per-target code** — it stays short
and stable (it declares the `labeled`-only issue trigger plus a manual
dispatch; opening or editing an issue schedules no run), carries no
pipeline logic, and references the factory by owner, repo, path and ref.
The oracle pins the owner (`MelvinKl`) and a **version tag** — a moving
branch ref is not a stable ref.

**In scope** — the 15-stage pipeline (chapter 5/6): trigger, setup-pi,
baseline, requirement-extraction (+ requirement check), planning (+ plan
check), implementation (+ implement check), test-and-review (+ fix
loop), PR open, PR gates (+ gate-fix loop), final status report.

**Out of scope** — the optional "JS actions ship as an npm package"
stretch (it is not on the Gherkin oracle's `main`; it becomes mandatory
only if the owner restores that scenario, per `PLAN.md` §10); long-running
services; installing or configuring `pi` inside CI.
