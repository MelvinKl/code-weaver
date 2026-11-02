# 7. Runtime View

**Trigger.** A `labeled` issue event (the consumer workflow declares
`types: [labeled]` — opening or editing an issue schedules no run) or a
manual dispatch with `issue_number`. The trigger job resolves the run
configuration (issue number/title/body, the base ref+sha, the AI branch
name), records it as state files, and gates: the issue carries the
trigger label (default `ai-requirements`) — or it was dispatched — else
the run is idle (`factory idle`, `started=false`) and every downstream
job skips. Re-entrant triggers on the same issue are idempotent (an
in-progress run with the same issue number → a comment on the issue, exit
0).

**Stage flow.** Each job downloads the prior stages' state artifacts into
the state dir (`$RUNNER_TEMP/cw/`), where every value is a file — the
artifact is the stage-results channel (a job-outputs relay was observed
dropping a value for one downstream job while the next job received it;
`GITHUB_ENV`, fed by the trigger artifact's state files, is the per-job
in-process channel). The stage records its stage baseline (the branch
tip as the stage started) so its guard judges only that stage's work;
earlier stages' committed outputs are never off-limits. The two
consuming jobs (implement, review) additionally run the target's
dependency-install step — the command the optional `dependency-install`
input declares — after each of their checkouts of the AI branch and
before its stage, once per consuming job (a checkout replaces the
workspace, so a one-time install in one job's workspace cannot serve the
next job's replaced workspace); the step precedes the job's
stage-baseline recording, so the install's footprint is never counted as
the stage's work by the guard. Where the input is empty the step is a
no-op (it logs and exits without touching the workspace): a target that
declares nothing runs unchanged — the run is unchanged by the
mechanism's presence. The `implement` job additionally runs the
target's dependency-upgrade step — the optional `dependency-upgrade`
setting (the setting's default is `on`; a target turns it off through
its consumer workflow — a `dependency-upgrade: off` line in the
`with:` block, like `max-loops`) decides whether it runs — after its
checkout of the AI branch and before its stage step and its
stage-baseline recording, so the upgrade's footprint is never counted
as the implementation stage's work by the guard: the step runs before
the implementation stage. Where the setting is on and the target has
declared a `dependency-install` command, the stage upgrades the
project's dependencies to newer versions: the step runs that command
and commits the footprint to the AI branch — each job's checkout
replaces the
workspace, so the branch is the only documented cross-job channel the
footprint rides: the consuming stages (the implementation stage in the
same job, the `review` job, whose dependency-install step installs the
upgraded set for the `make test` suite run) work against an upgraded
project whose test suite still passes — the upgrade does not break the
project's current functionality. Where the setting is off — or no
command is declared — the step is a no-op (it guards on the value
relayed through the documented `CW_<name>` step-env idiom, chapter 3,
logs and exits without touching the workspace): the pipeline runs
without the dependency-upgrade stage, no other job gains a step, and
the run's stages, pull request and final status report are unchanged by
the upgrade's absence. The report job's
inlined status-report step draws its plumbing names across the same stash
boundary (chapter 6: the runtime tree in `$RUNNER_TEMP`): where the shared
module resolves from the stashed tree the step's `import common` binds the
body's five bare-name plumbing calls (the state dir, the state file, the
log, the gh api, the branch push) to the shared module's definitions; where
the module does not resolve on that runner, the step's `ImportError`
branch binds the same names to local fallback definitions in the step —
the body's calls are unchanged on both paths, and the reports the two
paths complete agree (one ledger, one set of numbers on both the PR body
and the issue comment). The stage's push: a completed stage's work is
committed and pushed to the AI branch as part of stage completion —
inside the stage machinery, not only the job-tail workflow step (the
step stays as the job's final sync; for stage work it is a redundant
no-op). The shared generation loop pushes the branch at its completion
points — after each clean iteration (the single-call stages' push at
stage completion; the implement stage's push after each completed step,
before the next step starts) and on the no-op exit path — the
dependency-upgrade step pushes after its own commit, and the review
stage pushes at its completion point (a no-op in the normal case, its
fix iterations already pushing per iteration). The push reuses the
factory's sanitised push idiom (the token rewritten out of the log, the
GIT_CONFIG hygiene) and resolves the branch name through the documented
stage-value channel (the `AI_BRANCH` job env every stage job writes, the
`CW_`/trigger-state fallback): an unresolvable branch (an idle run)
skips with a log line, a push that actually fails fails the stage (its
work would not be on the remote, and the next stage or a re-trigger
would lose it), and the push fires only after the guard has passed — a
violating iteration is never pushed, the remote branch stays at the last
completed clean state. The AI branch remains the documented cross-job
channel: each job's checkout of the branch materialises the work the
previous stages committed and pushed.

**Resume semantics.** A re-triggered run for an issue whose AI branch
already exists reuses that branch — every stage runs again from the
branch's current state (generated files are updated in place); only an
absent branch is cut fresh. For implementation work that is already on the
branch, an empty model response with no file changes is a *satisfied
no-op* (measured against the run's baseline), not a phantom retry.

**The review loop.** Stage 10 runs the target's suite (`make test`) — the
suite executes **every** scenario — then pi reviews the output against the
changed scenarios: the feature files this run modified are the review's
judgement scope, joined by the scenarios the run's changed tests reference
(a changed test is judged by the requirement it references — the references
are extracted from the changed tests' docstrings), because a target's
requirements dir accumulates one file per issue and re-judging the whole
oracle on every run would make the review unboundedly slow (the standing
oracle was judged in the runs that added it). The review runs on every
iteration's output, red or green — a red suite is never a pass, so the
review's own breakdown cannot hide one (and on a green suite the same
breakdown fails the stage: the oracle cannot be assumed green).
pi emits the `REVIEW-VERDICT` block (one `SCENARIO <file>::<name>: <verdict>`
line per scenario in scope — parsed from the response, or from a file the
model wrote (mirrored to the state dir, the repo copy removed)); a run that
changed no requirements and no referencing tests passes vacuously (the
suite's full result stands and
the empty block is the answer), while a run that DID change scenarios or has
a referencing test with zero parseable verdicts fails the stage — a silent
pass is impossible.
The reviewer's report — the review call's full output: each verdict's
evidence, the UNFULFILLED lines' "what's missing / what the fix must do",
the note on what the tests don't cover — is mirrored per iteration into the
state dir (→ artifact), and the fix directive names it by path: the fixer
reads it on demand, alongside the machine-parsed verdict summary and, for a
red suite, the raw output tail (a red iteration whose review breaks keeps
the fix loop running on the raw output). Unfulfilled verdicts and a red
suite build the fix directive; stage 11 commits the fix and re-runs stage
10, bounded by the loop caps; each iteration's log lands in the state dir
(→ artifact), never the repo tree.

**Failure paths.** A crashed stage persists its full traceback to the
runner's durable diagnostic log plus a one-line reason in the stage's
artifact (the job log dies with the run — a ghost run's logs are
unreachable from the API). The report job runs on success **and** failure
(`if: always()`): a run that died before the PR exists is still reported
— as a comment on the source issue, with the stage outcomes and a pointer
to the workflow run's artifacts; no report file is ever written into the
repo tree. The final status report lists the run's total input tokens,
total output tokens and total cost in every case — derived from the
per-call usage records in the state dir (each stage's artifact carries the
cumulative ledger), so a run that stopped early in a failed stage is
reported with the usage and cost of the pi calls made before the stop, and
a stage that never ran contributes nothing. The stage outcomes the report
lists render from the stages' recorded summary lines: a stage that is done
is reported "stage complete" (its per-step lines stay out of the outcome),
and a stage that will re-run — the implement stage's per-step
"step <k>/<n> done" lines recorded without a completion line — is reported
per step for each of its finished steps. The report stage re-reads the
PR after editing its body and keeps the pointer comment ("final status is
in the PR body") only where that completion verified; where it could not
be applied — the PR was already merged, or the edit was refused on both
write paths — the issue comment carries the full final status itself, so
the PR description and the issue comment never disagree on the run's
numbers. A run that succeeded has its source issue closed with the
completed state reason (the close is best-effort — a refusal is warned,
never fatal); a failed run leaves the issue open for a re-trigger.
