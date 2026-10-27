# 10. Risks & Open Items

- **Gherkin as oracle** — green scenarios ≠ right behaviour (inherent to
  BDD); the review stage (pi judges the changed scenarios) is the second
  layer.
  The residual risk is a *verdict* drift (the judge calls a scenario
  fulfilled that the code does not meet) — inherent to a model as judge;
  the bounded fix loop is the containment.
- **The oracle's two context slices** — setup-pi pins `@`-file arguments
  for `requirements/`, `README.md`, `docs/`; configuration pins
  path-referenced, never-embedded files. The fix re-sliced the two onto
  disjoint stage boundaries (chapter 5): extraction is the `@`-file
  slice; plan/implement/review/pr-body are the path-referenced slice. An
  oracle edit that re-couples them contradicts itself again.
- **Runner environment is a pre-requisite** — pi installed & configured,
  backend reachable; stage 2 fails explicitly. The `gh` CLI is the second
  pre-requisite, and the runner user must own `~/.config`. Ghost bindings
  on this runner build (a `GITHUB_ENV` write not reaching the next
  step's expression; a composite `with:` never materialising as
  `INPUT_*`) are contained by the `CW_*`/state-file relay — but a re-run
  is pinned to the run's commit and cannot pick up a later workflow
  fix: only the next triggered run carries a workflow change.
- **Self-editing separation** — implement/gate allow sets exclude
  `requirements-dir`: intra-PR test fixes are fine, requirement edits are
  not (they loop back to the plan stage). The implement allow set excludes
  the plan dir and re-allows only the current issue's plan file (the plan
  is a live state tracker) and, for a repo without a `docs/` dir, the
  top-level `PLAN.md` that plays the arc42-set role; any other issue's
  plan file is off-limits (implement: “implementation may only edit the
  current issue's plan”).
- **Open item for the owner (oracle wording tension)** — with the
  implement guard now file-precise (plan dir excluded; only the current
  issue's plan file re-allowed), `guard-rail.feature`'s “the allowed file
  set is per-stage” line — “the implement-check allows src/, tests/,
  docs/, `plans/` and README.md” — reads as the whole plan dir, while
  `implement.feature`'s “implementation may only edit the current
  issue's plan” pins the tighter separation. The stricter implement pin is
  what the guard enforces, and the guard-rail line stays satisfied (the
  current plan file lives under `plans/`). `requirements/` is read-only to
  the factory, so reconciling the two lines is the owner's call — a
  requirement that cannot be fulfilled is reported, not rewritten.
- **Extraction delta shape** — the guard pins exactly one new file named
  after the issue, and no existing feature file may differ from the
  baseline (a changed existing file is reverted and the stage re-runs). A
  delta that genuinely contradicts an existing scenario is reported in
  the model's reply and resolved by the review stage — the oracle stays
  the single source of truth.
- **Open item for the owner (trigger scenario superseded by #20)** —
  `trigger.feature`'s standing scenario "Issue opened with the label
  starts the factory" (When: "the issue *carries* the label
  `ai-requirements`") no longer holds: under the `labeled`-only consumer
  trigger that issue #20 declared (README example, the repo's own
  `.github/workflows/code-weaver.yml`, and
  `issue-20-labeled-only-trigger.feature`), an issue *opened* with the
  label attached schedules no run at all. The consistent rewording,
  specified in `plans/20.md` (Task 5 — the plan is the carrying text):
  rename the scenario to "An opened issue starts the factory once the
  label is added" and change the When step to "the label
  `ai-requirements` is *added* to the issue"; the Then steps (the factory
  runs and records the issue number and the issue body) are unchanged —
  the outcome now rides the `labeled` event. The factory does not make
  that edit: `requirements/` is read-only to every stage (the extract
  guard pins exactly one new file; the implement guard reverts
  requirement edits and loops back to planning), so per the rule above the
  contradiction is reported, not edited, and the oracle stays the single
  source of truth. Meanwhile `PLAN.md` §7 already cites the post-change
  scenario name (the one-file-behind state the review stage is the
  designated resolver of). The owner's follow-up is the rename + When
  edit in `requirements/trigger.feature` (a follow-up issue).
- **Open item for the owner (four standing scenarios superseded by
  #43)** — the issue-43 delta's header
  (`issue-43-cost-and-token-usage.feature`) declares four standing
  scenarios superseded, “reported in the stage reply, not edited here —
  requirements/ is read-only to the extraction stage”:
  `configuration.feature`’s “The loop caps are configurable” and “A loop
  cap of 0 means no cap” (both Givens pin “the defaults are MAX_LOOPS 5
  and MAX_TOTAL_TOKENS 500000”); `test-and-review.feature`’s “The loop
  respects the token budget” (the cumulative-spend, budget-exhaustion
  stop); `safety.feature`’s “Every loop in the pipeline respects its cap”
  (wording). The consistent rewording, specified in `plans/43.md`
  (Task 4 — the plan is the carrying text, which the PR body and the
  final status report carry to the owner): `configuration.feature`
  “The loop caps are configurable” — Given becomes “the default is
  MAX_LOOPS 5”, When becomes “a target lowers or raises it”, the Then is
  unchanged; “A loop cap of 0 means no cap” — the Given drops the “and
  MAX_TOTAL_TOKENS 500000” conjunct, the Then drops the “setting
  MAX_TOTAL_TOKENS to 0 removes the token budget” step, and “the resolved
  configuration records the removed caps” stays (about max-loops);
  `test-and-review.feature` “The loop respects the token budget” — the
  scenario is deleted outright (its requirement is superseded by the
  delta’s “The bounded loops stop on success or their iteration cap, not
  on token spend”); `safety.feature` “Every loop in the pipeline respects
  its cap” — the Then lines reword to the delta’s form, “every bounded
  loop is bounded by its iteration cap alone” / “the factory is
  guaranteed to terminate while all remaining loop caps are non-zero”,
  with the “a cap of 0 means that loop is uncapped” line staying. The
  factory does not make that edit: `requirements/` is read-only to every
  stage, so per the rule above the contradiction is reported, not edited,
  and the oracle stays the single source of truth. `PLAN.md` — where the
  arc42 set lives in a target without a `docs/` dir — is not in this
  repo’s tree, so this entry stands alone. The owner’s follow-up is the
  rewording above in `requirements/configuration.feature`,
  `requirements/test-and-review.feature` and
  `requirements/safety.feature` (a follow-up issue).
- **Cost rate table covers only known models** — the report stage derives
  the run's total cost from the recorded usage, keyed on the run's
  resolved `llm-model` setting (the only documented adjustable LLM
  setting; its resolved value rides the trigger's resolved-config state
  the report job downloads), via a small per-model rate table in
  `.github/actions/report/action.yml`; the table covers only known models,
  and a target's model with no rate entry is listed as *unpriced* in the
  report (the usage totals are listed regardless) — the owner extends the
  table when a new model joins the runner's configured set.
- **arc42 structure varies per target** — the extraction prompt
  tolerates the structural difference: extraction proceeds on the
  readable parts; a missing, renamed or reordered chapter is never a
  reason to fail.
- **Repo transfer** — the oracle pins the consumer's `uses:` to the
  `MelvinKl` owner; if the repo is ever transferred to another owner/org,
  the oracle (or the pinned ref, via GitHub's redirect) must be the
  surface that changes.
- **Open item for the owner** — the "JS actions ship as npm packages"
  scenario is not on `main` (it fell out of the PR #1 re-slice). If
  deliberate, the plan stands (the npm mechanism stays an optional
  stretch); if accidental, the owner says so and the scenario returns.
