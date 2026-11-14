# requirements/safety.feature
# Secrets handling, branch hygiene, mandatory loop caps, audit trail,
# the README's prominent warning to use the factory in private repos only
# (issue 77 — anyone who can create/tag issues can start runs that consume
# tokens and create cost for the repo).

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
    When the setup stage configures pi for the run from the run's provided model configuration
    Then no API key secret is required
    And the backend configuration is provided for the run via a GitHub secret, not a pre-requisite of the runner environment

  @safety
  Scenario: Every loop in the pipeline respects its cap
    Given the pipeline contains the guard repair, review-fix and gate-fix loops
    Then every bounded loop is bounded by its iteration cap alone
    And a cap of 0 means that loop is uncapped
    And the factory is guaranteed to terminate while all remaining loop caps are non-zero

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
  Scenario: A completed stage's work is committed and pushed to the AI branch
    Given a factory stage has finished its work on the AI branch
    When the stage completes and the run proceeds to the next stage
    Then the stage's changes are committed to the AI branch and the branch is pushed
    And a run terminated after that stage loses none of the completed stage's work

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

  @safety
  Scenario: A stage resolves its inputs without trusting the runner's env plumbing
    Given a runner that breaks the env plumbing — a composite action whose inner steps receive neither the with:→INPUT_* binding nor the job-level GITHUB_ENV values
    When a stage job starts and the stage code resolves one of its inputs
    Then the value comes from the action input, the CW_<name> job env, or the trigger artifact's state files — which exist regardless
    And the stage proceeds with its values as on a runner that binds them correctly
    And the with: mappings stay declared for portability to a healthy runner
    And a stage job may not take trigger values from the job-outputs relay
    And the stage fails with a precise error only if all three sources are absent

  Scenario: A stage locates its code without the runner's action var
    Given a runner whose composite action inner steps leave GITHUB_ACTION_PATH unset
    When a stage module, a shared helper or a composite run line needs the shared scripts directory or a sibling action
    Then it locates the actions directory from its own file location, with the runner's action var as the first choice where the runner sets it
    And the import of the shared modules succeeds, the sibling actions and the stage script resolve to real paths, and the run line starts the stage module from its real location

  @safety
  Scenario: The README carries a prominent warning at its top
    Given the factory's README.md
    When the opening of the README is read
    Then a warning is presented there at the top, before the description of the factory
    And the warning sits above the workflow's usage and consumption sections
    And it advises using the code-weaver workflow only in a private repo
    And it states that everyone who can create or tag issues can create a workflow run of the factory
    And it states that such a run consumes tokens and creates cost for the repo

  @safety
  Scenario: Every stage job of the pipeline trusts the workspace for git before any later step runs git in it
    Given a runner whose workspace the runner process does not own (a re-provisioned runner, a squashed share mount)
    And the checkout step's safe.directory shim lives in a temporary HOME that exists for that step alone
    When a later step of the job runs git against the workspace — the stage's branch cut, fetch, commit or push
    Then that step's git reads the workspace's safe.directory entry from the runner user's own global git configuration
    And a stage script's git children carry the workspace's safe.directory entry in their own managed environment, beside the runner user's home and the current working directory
    And the children's git works whatever the runner user's global git configuration holds
    And no step of the job dies with "detected dubious ownership" on that runner
    And a write that cannot land (a runner user whose home is unwritable) warns and continues — the job must never die on the trust
