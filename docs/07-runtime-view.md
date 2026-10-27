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
earlier stages' committed outputs are never off-limits.

**Resume semantics.** A re-triggered run for an issue whose AI branch
already exists reuses that branch — every stage runs again from the
branch's current state (generated files are updated in place); only an
absent branch is cut fresh. For implementation work that is already on the
branch, an empty model response with no file changes is a *satisfied
no-op* (measured against the run's baseline), not a phantom retry.

**The review loop.** Stage 10 runs the target's suite (`make test`) — the
suite executes **every** scenario — then pi reviews the output against the
changed scenarios: the feature files this run modified are the review's
judgement scope, because a target's requirements dir accumulates one file
per issue and re-judging the whole oracle on every run would make the review
unboundedly slow (the standing oracle was judged in the runs that added it).
pi emits the `REVIEW-VERDICT` block (one `SCENARIO <file>::<name>: <verdict>`
line per changed scenario — parsed from the response, or from a file the
model wrote (mirrored to the state dir, the repo copy removed)); a run that
changed no requirements passes vacuously (the suite's full result stands and
the empty block is the answer), while a run that DID change scenarios with
zero parseable verdicts fails the stage — a silent pass is impossible.
Unfulfilled scenarios build the fix directive; stage 11 commits the fix and
re-runs stage 10, bounded by the loop caps; each iteration's log lands in the
state dir (→ artifact), never the repo tree.

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
a stage that never ran contributes nothing.
