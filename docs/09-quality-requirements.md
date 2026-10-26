# 9. Quality Requirements

- **Loop caps.** Every bounded loop (guard re-run, review-fix, gate-fix)
  respects `MAX_LOOPS` (default 5; **0 = no cap**) and the run's
  `MAX_TOTAL_TOKENS` budget (default 500,000; 0 = no budget); with all
  caps non-zero the pipeline is guaranteed to terminate. The resolved
  configuration is recorded in the workflow log for audit — never
  committed.
- **The pi call cap.** Each pi invocation runs under a 360-minute cap
  (overridable per call via `CW_PI_TIMEOUT`); a call cut off at the cap
  exits 124 — the stage treats it as a slow model (the iteration is
  consumed, the loop retries), never as a broken environment. A call that
  dies with no output is a dropped provider stream: retried, not fatal;
  only a failure that produced output fails the stage.
- **Skipped-not-failed.** The test suite runs on an interpreter without
  pytest (the `make test` target drives the stdlib-only runner in the
  tree); where the official Gherkin-parser port is absent from that
  interpreter, the oracle check is **skipped, not failed** — the
  validator reports the skip and exits 0, and the validator's own unit
  tests skip the parser-dependent cases rather than fail on the missing
  import.
- **Crash diagnostics.** Every stage entry point installs the shared
  crash hook: a stage that crashes persists its full traceback to the
  runner's durable diagnostic log and a one-line reason into the stage's
  artifact, so a human can read why a stage failed without the job log.
- **Executable oracle.** Every `.feature` under `requirements/` must parse
  with Cucumber's official Gherkin parser and carry at least one Scenario
  (a requirement-free feature is not executable); the trigger-contract
  tests pin the consumer workflow's `labeled`-only trigger and the
  stage-1 gate verbatim; the stage-contract tests pin the fixed stage
  contracts (the two context slices, the extraction guard shape, the
  consumer's owner/ref surface, the pi-generated PR body, the report
  fallback, the validator skip, the loop-cap defaults, the implement
  guard's plan-file precision).
- **Verdict discipline.** The review marks *every* scenario (none skipped,
  none invented); the parser tolerates observed format drift (em-dash
  separators, parenthetical qualifiers) but a zero-verdict review fails
  the stage — the oracle cannot be assumed green.
