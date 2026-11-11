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
    And the backend configuration is provided for the run via a GitHub secret or a repo file, not a pre-requisite of the runner environment

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
  Scenario: Stage inputs reach stage code even on a runner that breaks composite input binding
    Given a runner whose composite action steps never receive with: values as INPUT_* env
    When the factory passes each stage value in the job env as CW_<name> beside the with: mapping
    Then the stage code resolves each input as INPUT_<name> falling back to CW_<name>
    And the stage proceeds with its values as on a runner that binds them correctly
    And the with: mappings stay declared for portability to a healthy runner

  Scenario: Stage values ride the trigger artifact, not the job-outputs relay
    # the job-outputs relay has been observed dropping a value for one
    # downstream job while the very next job received it (issue-number
    # present in baseline, missing in extract); GITHUB_ENV, fed by the
    # trigger artifact's state files, is the per-job, in-process channel
    Given the trigger stage resolved the run configuration
    When any later stage job starts
    Then the job's values come from the trigger artifact's state files
    And steps after the state read see them in the process environment
    And no stage job may take trigger values from the job-outputs relay

  Scenario: A stage resolves its inputs without trusting the runner's env plumbing
    # on this runner build a composite action's inner steps receive neither
    # the with:→INPUT_* binding nor the job-level GITHUB_ENV values, so the
    # stage code resolves each input as INPUT_<name>, then CW_<name>, then
    # the trigger artifact's state files — which exist regardless
    Given a stage starts on a runner that breaks the env plumbing
    When the stage code resolves one of its inputs
    Then the value comes from the action input, the CW env, or a state file
    And the stage fails with a precise error only if all three are absent

  Scenario: A stage resolves its own code location without the runner's action vars
    # this runner build leaves GITHUB_ACTION_PATH unset inside a composite
    # action's inner steps, so a stage module locates the shared scripts from
    # its own file path, with the action var as the first choice
    Given a stage module runs inside a composite action
    When it needs the shared scripts directory
    Then it derives the action directory from its own location
    And the import of the shared modules succeeds

  Scenario: Shared helpers locate the actions directory without the runner's action var
    # GITHUB_ACTION_PATH is unset in composite inner steps on this runner
    # build, but common.py's own path always yields the checkout root
    Given a stage calls for a sibling action or the scripts directory
    When the runner's action var is unset
    Then it anchors the actions directory from the location of common.py
    And sibling actions and the guard script resolve to real paths

  Scenario: A composite run line locates the stage script without the runner's action var
    # the run line must not be built from GITHUB_ACTION_PATH (unset in
    # composite inner steps on this runner build): it falls back to the
    # checkout-relative action path, which a healthy runner resolves identically
    Given a composite action whose run line invokes the stage module
    When the runner's action var is unset
    Then the run line falls back to the checkout-relative action path
    And the stage module starts from its real location

  @safety
  Scenario: The README carries a prominent warning at its top
    Given the factory's README.md
    When the opening of the README is read
    Then a warning is presented there at the top, before the description of the factory
    And the warning sits above the workflow's usage and consumption sections

  @safety
  Scenario: The README warning advises using the workflow only in a private repo
    Given the warning at the top of the README
    When a maintainer of a target repo reads it
    Then it advises using the code-weaver workflow only in a private repo

  @safety
  Scenario: The README warning names who can start a factory run
    Given the warning at the top of the README
    When it is read
    Then it states that everyone who can create or tag issues can create a workflow run of the factory

  @safety
  Scenario: The README warning states what such a run consumes
    Given the warning at the top of the README
    When it is read
    Then it states that such a run consumes tokens and creates cost for the repo

  @safety
  Scenario: Every stage job of the pipeline trusts the workspace for git before any later step runs git in it
    Given a runner whose workspace the runner process does not own (a re-provisioned runner, a squashed share mount)
    And the checkout step's safe.directory shim lives in a temporary HOME that exists for that step alone
    When a later step of the job runs git against the workspace — the stage's branch cut, fetch, commit or push
    Then that step's git reads the workspace's safe.directory entry from the runner user's own global git configuration
    And no step of the job dies with "detected dubious ownership" on that runner
    And a write that cannot land (a runner user whose home is unwritable) warns and continues — the job must never die on the trust

  @safety
  Scenario: A stage script's git children carry the workspace's safe.directory entry in their own process environment
    Given the checkout step's safe.directory shim is written into a temporary HOME that exists for that step alone
    When the stage script's git child process runs in a later step of the job
    Then its managed git environment pins the workspace as a safe.directory entry for that child process, beside the runner user's home and the current working directory
    And the child process's git works whatever the runner user's global git configuration holds
