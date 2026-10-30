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
- **Runner environment** — no pre-installed or pre-configured pi is a
  pre-requisite: the setup stage installs pi for the run and configures it
  for the workflow run from the run's provided harness, failing explicitly
  where it cannot (an install or configuration that cannot complete, an
  unreachable backend, a provided configuration without a backend URL).
  The `gh` CLI is a runner pre-requisite, and the runner user must own
  `~/.config`. Ghost bindings
  on this runner build (a `GITHUB_ENV` write not reaching the next
  step's expression; a composite `with:` never materialising as
  `INPUT_*`) are contained by the `CW_*`/state-file relay — but a re-run
  is pinned to the run's commit and cannot pick up a later workflow
  fix: only the next triggered run carries a workflow change.
- **Self-editing separation** — the implement guard's deny set excludes
  `requirements-dir`: intra-PR test fixes are fine, requirement edits are
  not (they loop back to the plan stage). The guard runs inverted — the
  implementation's lane is everything except the protected set (requirements
  and the plans dir), with exactly the current issue's plan file re-allowed
  over it (the plan is a live state tracker); any other issue's plan file is
  off-limits (implement: “implementation may only edit the current
  issue's plan”). Inversion is the field-proven shape: a whitelist
  snapshotted at stage start used to revert a brand-new `tests/` dir (or
  `docs/` set, top-level `Makefile`) the implementation had just created,
  every iteration (run 40735387017 on the syncer target, which started
  without a `tests/` dir) — the implementation has the job to implement
  the tests, and the guard's job is to protect the protected set.
- **Open item for the owner (oracle wording tension)** — with the
  implement guard now running inverted (deny = {requirements, plans}; the
  current issue's plan file re-allowed), `guard-rail.feature`'s “the
  allowed file set is per-stage” line — “the implement-check allows
  everything except requirements/ and the other issues' plans” — and
  `implement.feature`'s “implementation may only edit the current
  issue's plan” say the same thing: the stricter implement pin is what the
  guard enforces. The implement stage stays walled off from the oracle
  (its guard reverts requirement edits and loops back to planning).
- **Extraction delta shape** — the guard keeps the delta inside the
  requirements dir; inside it, the stage pins the topic placement: a
  delta's scenarios extend the existing topic file that covers their topic
  (a merely changed file is not a violation), a new file is created only for
  a topic no file yet covers (named after the topic, never after the issue),
  and a changed existing file that no longer parses — or a deleted topic
  file — is reverted and the stage re-runs. A delta that supersedes a
  standing scenario updates that scenario in place (the oracle is the single
  source of truth) and reports the change — the review stage judges it.
- **Open item for the owner (trigger scenario superseded by #20)** —
  `trigger.feature`'s standing scenario "Issue opened with the label
  starts the factory" (When: "the issue *carries* the label
  `ai-requirements`") no longer holds: under the `labeled`-only consumer
  trigger that issue #20 declared (README example, the repo's own
  `.github/workflows/code-weaver.yml`, and
  `labeled-only-trigger.feature`), an issue *opened* with the
  label attached schedules no run at all. The consistent rewording,
  specified in `plans/20.md` (Task 5 — the plan is the carrying text):
  rename the scenario to "An opened issue starts the factory once the
  label is added" and change the When step to "the label
  `ai-requirements` is *added* to the issue"; the Then steps (the factory
  runs and records the issue number and the issue body) are unchanged —
  the outcome now rides the `labeled` event. In run #20 the factory did not
  make that edit: `requirements/` was read-only to every stage (the extract
  guard then pinned exactly one new file; the implement guard still reverts
  requirement edits and loops back to planning), so the contradiction was
  reported, not edited. The placement change lifts the extraction stage's
  read-only pin, so a follow-up run touching the trigger topic can now make
  it; until then the oracle stands as #20 reported it. Meanwhile `PLAN.md`
  §7 already cites the post-change
  scenario name (the one-file-behind state the review stage is the
  designated resolver of). The owner's follow-up is the rename + When
  edit in `requirements/trigger.feature` (a follow-up issue).
- **Open item for the owner (four standing scenarios superseded by
  #43)** — the issue-43 delta's header
  (`cost-and-token-usage.feature`) declares four standing
  scenarios superseded — run #43 reported them in its stage reply instead of
  editing (at the time requirements/ was read-only to the extraction
  stage; the placement change lifts that pin):
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
  with the “a cap of 0 means that loop is uncapped” line staying. In run
  #43 the factory did not make that edit: at the time `requirements/` was
  read-only to every stage, so per the rule then in force the contradiction
  was reported, not edited. The placement change lifts the extraction
  stage's read-only pin, so the rewording above can now land in the three
  files, by the owner or a follow-up run. `PLAN.md` — where the
  arc42 set lives in a target without a `docs/` dir — is not in this repo's
  tree, so this entry stands alone. The owner's follow-up is the
  rewording above in `requirements/configuration.feature`,
  `requirements/test-and-review.feature` and
  `requirements/safety.feature` (a follow-up issue).
- **Cost rates come from the run's model configuration** — the report
  stage derives the run's total cost from the recorded usage, keyed on
  the run's resolved `llm-model` setting (the only documented adjustable
  LLM setting; its resolved value rides the trigger's resolved-config state
  the report job downloads), at the rates the run's model configuration
  declares for that model — the `cost` object of the model's entry in the
  configuration the setup stage materialises (a non-empty `PI_MODELS`
  secret wins over the repo file `.pi/agent/models.json`; the report job
  resolves the same provider and lists the source it read the rates from,
  so the cost is auditable against the run's own configuration). A
  target's model configuration with no `cost` entry for its model is listed
  as *unpriced* in the report (the usage totals are listed regardless) —
  the owner adds the model's cost rates to the target's `models.json` (or
  the `PI_MODELS` secret) when a new model joins its configured set.
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
