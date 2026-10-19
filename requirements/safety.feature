# requirements/safety.feature
# Secrets handling, branch hygiene, mandatory loop caps, audit trail.

Feature: Secrets and safety
  As the operator of the factory
  I want the factory to be safe by default
  so that automated AI work can never compromise the target repo or run away

  @safety
  Scenario: GH_TOKEN is repo-scoped and never committed
    Given the factory needs GH_TOKEN to open PRs and comment on issues
    Then the token is a repo-scoped PAT or the built-in GITHUB_TOKEN
    And the token carries at least issues:write, pull-requests:write and contents:write
    And it is stored as a GitHub secret, never in the repo

  @safety
  Scenario: The LLM backend needs no secret
    Given the backend is the internal keyless llama-swap
    When the factory uses the pre-configured pi
    Then no API key secret is required
    And the backend configuration is a pre-requisite of the runner environment

  @safety
  Scenario: Every loop in the pipeline respects its cap
    Given the pipeline contains the guard re-run, review-fix and gate-fix loops
    Then every loop respects the configured cap
    And a cap of 0 means that loop is uncapped
    And the factory is guaranteed to terminate while all caps are non-zero

  @safety
  Scenario: Work only happens on the AI branch
    Given the factory is running for an issue
    Then all writes land on the branch ai/code-weaver/<issue_number>
    And the target repo's main branch is never modified by the factory

  @safety
  Scenario: A broken stage cannot corrupt the target branch
    Given a stage failed or a guard-rail reverted its output
    Then the target repo's main branch is untouched
    And the partial work stays on the AI branch, reviewable via the PR

  @safety
  Scenario: The factory tolerates arc42 structure variance
    Given a target project's arc42 markdown files use a different structure variant
    When the extraction stage runs
    Then the extraction prompt tolerates the structural difference
    And extraction proceeds on the readable parts

  @safety
  Scenario: An audit trail exists for human review
    Given the factory finished or failed a run
    Then per-iteration logs exist in the workflow log or an artifact, never committed to the repo
    And the arc42 docs carry an AI-activity section for the run
    And a human reviews the PR before merging

  @safety
  Scenario: A stage's results reach the later stages as workflow artifacts
    Given a stage has finished and recorded its results
    When the stage uploads its state as a workflow artifact and a later stage starts
    Then the later stage downloads that artifact and sees the previous stage's results
    And the hand-off relies only on workflow storage, never on the repo tree

  @safety
  Scenario: A crashed stage leaves a persistent diagnosis on the runner
    Given a stage's program crashed before its step finished
    When the run ends and its job log is no longer retrievable
    Then the stage's full traceback is written to the runner's diagnostic log
    And a one-line failure reason is carried in the stage's artifact
    And a human can read why the stage failed without the job log
