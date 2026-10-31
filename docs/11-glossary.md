# 11. Glossary

- **Factory** — the 15-stage pipeline (`factory.yml`, self-contained —
  its stage steps are inlined in the workflow file), consumed by ref.
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
  relative to the baseline; extracted as Gherkin into the oracle's topic
  structure — a delta's scenarios extend the existing topic file that covers
  them, a new file is created only for a topic no file yet covers, and no
  file is named after the issue.
- **Delta-scoped review** — the test-and-review stage's review judges the
  scenarios of the feature files a run changed, plus the scenarios the
  run's changed tests reference (a changed test is judged by the requirement
  it references; the suite still executes the whole oracle). The standing
  oracle is the accumulated set, so re-judging
  every scenario on every run grows with the repo's issue history and was
  the review step's unbounded runtime; the runs that added scenarios own
  their review. A run that changed no requirements and no referencing
  tests passes vacuously (the
  suite's full result stands, the empty verdict block is the answer); a run
  that DID change scenarios or has a referencing test with zero parseable
  verdicts still fails the
  stage — the oracle cannot be assumed green. The review runs on every
  iteration's output (red or green), and its full output — the reviewer's
  report: each verdict's evidence, the UNFULFILLED lines' "what's missing
  / what the fix must do", the note on what the tests don't cover — is
  mirrored per iteration into the state dir and fed into the fixer: the
  fix directive names it by path, the fixer reads it on demand
- **Oracle** — the Gherkin requirements under `requirements/` (15 files,
  161 scenarios), structured by topic: each file is named after the topic
  it covers, so a search for a topic targets that file instead of sweeping
  the whole oracle; the acceptance tests stage 10 runs, and the set the
  review stage judges — scoped to the feature files each run changed
- **Guard** — the shared "only X changed" check (one implementation,
  three call sites): collects working-tree changes against the stage
  baseline, compares them against the per-stage set, and repairs a
  violation with a pi call — the off-limits files named, told to be
  reverted, the stage's own work told to stay valid against the task its
  initial instructions gave it — instead of reverting by git and restarting
  the stage; the guard records a cleared repair in the state dir — the
  plan stage's check re-runs the plan stage's generation on it (any other
  change is reverted and the plan stage re-runs) while the other checks'
  stages complete without re-running; the repair loop is bounded by
  `MAX_LOOPS` (0 = no cap), and a
  cap exhausted without clearing the violation fails the stage with a
  report listing the violations.
- **Context contract** — the two disjoint slices (chapter 5): the
  extraction stage's `@`-file arguments (the arc42 markdown, `README.md`,
  the baseline diff — pi reads the named files as context before answering;
  the Gherkin oracle is not one of them — its directory is named in the
  instructions and pi reads the files it judges relevant on demand, a
  directory never being an `@`-argument) and the other stages'
  path-referenced files
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
  ref (the self-contained reusable workflow + the runtime tree its stage
  steps execute — the scripts and the pi prompt templates, embedded in
  the workflow file as a base64 tarball stage 1 materialises into the
  runner's temp dir, riding the trigger's artifact to every later stage
  job) — so the ref on the consumer's `uses:` line is the only pin a run
  makes (the `factory-ref` input is a legacy no-op), the ref selects the
  workflow file and its runtime tree as one version from the factory
  repo, a ref bump
  selects them as one version, and targets pinned to an older ref keep
  working — an upgrade is a one-line ref bump, and every published
  version — an older `vX.Y.Z` tag or a new single-number tag — is a
  stable ref. The factory project's own repo uses the same shape: it
  pins the public release line (a version tag of the MelvinKl line) —
  the dogfood exercises the published version its external targets get —
  while a run triggered in it works the triggered repo's own code; the
  pin selects the machinery, never the code, and no stage clones the
  factory repo at a second ref.
- **Satisfied no-op** — a re-run of work already on the branch: the
  model's empty answer with a non-empty diff against the run's baseline
  means the work is in place — the stage is green, not an error.
- **Skipped-not-failed** — where a capability the check needs (the
  Gherkin-parser port) is absent from the interpreter, the check reports
  a skip and exits clean instead of failing the suite.
