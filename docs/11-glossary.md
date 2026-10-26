# 11. Glossary

- **Factory** — the 15-stage pipeline (`factory.yml` + the composite
  actions), consumed by ref.
- **Stage** — one logical unit of the factory (15 of them; 9 GitHub
  jobs, several bundling consecutive stages).
- **Consumer workflow** — the target repo's short
  `.github/workflows/code-weaver.yml`: names the factory ref, passes
  inputs, carries the `labeled`-only trigger; the only per-target code.
- **AI branch** — `ai/code-weaver/<issue_number>`; the only branch the
  factory writes to.
- **Baseline** — the trigger's base sha (the target branch's head) plus
  the issue's change-set diff, recorded as state files; the reference
  every guard check measures against.
- **Delta requirements** — the requirement change an issue implies,
  relative to the baseline; extracted as Gherkin into exactly one new
  file named after the issue.
- **Oracle** — the Gherkin requirements under `requirements/` (13 files,
  121 scenarios); the acceptance tests stage 10 runs and the review
  stage judges.
- **Guard** — the shared "only X changed" check (one implementation,
  three call sites): collects working-tree changes against the stage
  baseline, allows the per-stage set, reverts exactly the off-limits
  files and re-runs the stage.
- **Context contract** — the two disjoint slices (chapter 5): the
  extraction stage's `@`-file arguments (pi reads the named files as
  context before answering) and the other stages' path-referenced files
  (contents never embedded; pi reads on demand with its read tool).
- **State dir / artifacts** — `$RUNNER_TEMP/cw/`: every stage value is a
  file; the dirs travel as workflow artifacts between jobs and are never
  committed to the repo tree.
- **arc42 set** — the markdown documentation: the `docs/` files (one
  chapter per file) — or, for a target without a `docs/` dir, its
  top-level `PLAN.md`.
- **AI-activity section** — the `## AI activity (code-weaver)` section
  the report stage appends to the first arc42 file (chapter 1 in this
  repo) after each run.
- **Reuse by ref** — the factory lives in this repo and is referenced by
  ref (reusable workflow + composite actions + prompt templates); an
  upgrade is a one-line ref bump, and every published `vX.Y.Z` tag is a
  stable ref.
- **Satisfied no-op** — a re-run of work already on the branch: the
  model's empty answer with a non-empty diff against the run's baseline
  means the work is in place — the stage is green, not an error.
- **Skipped-not-failed** — where a capability the check needs (the
  Gherkin-parser port) is absent from the interpreter, the check reports
  a skip and exits clean instead of failing the suite.
