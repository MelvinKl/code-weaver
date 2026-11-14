# requirements/configuration.feature
# The full configurable surface (plan §11): every setting has a default
# and can be overridden per target repo via workflow inputs.

Feature: Configuration surface
  As a maintainer of a target project
  I want every factory setting configurable per target repo
  so that one factory fits different projects without forking the code

  @config
  Scenario: The trigger label is configurable
    Given the default AI_REQUIREMENTS_LABEL is "ai-requirements"
    When a target sets AI_REQUIREMENTS_LABEL to another value
    Then the factory triggers on the target's value instead

  @config
  Scenario: The target branch is configurable
    Given the default TARGET_BRANCH is "main"
    When a target sets TARGET_BRANCH to "develop"
    Then the PR is opened against develop

  @config
  Scenario: The artefact directories are configurable
    Given the defaults are REQUIREMENTS_DIR requirements/, PLAN_DIR plans/ and DOC_DIR docs/
    When a target overrides any of them
    Then the factory reads and writes under the overridden paths
    And the guard-rail allowed sets follow the overridden paths

  @config
  Scenario: Which configured model is used is adjustable
    Given the run's provided model configuration lists several models
    And the default LLM_MODEL is "Ornith-1.5-35B-A3B"
    When a target sets LLM_MODEL to another already-configured model
    Then every pi invocation in the pipeline uses that model
    And the backend configuration itself is unchanged

  @config
  Scenario: The action ref is configurable
    Given the factory is consumed through the target repo's own workflow
    When the target edits the ref in its uses: line
    Then the factory runs from that ref
    And the target's own workflow file is the only file that changes

  @config
  Scenario: The loop caps are configurable
    Given the default is MAX_LOOPS 5
    When a target lowers or raises it
    Then every bounded loop in the pipeline uses the target's values

  @config
  Scenario: A loop cap of 0 means no cap
    Given the default is MAX_LOOPS 5
    When a target sets MAX_LOOPS to 0
    Then the guard repair, review-fix and gate-fix loops run without a loop-count limit
    And the resolved configuration records the removed caps

  @config
  Scenario: The pi call time cap is a configurable workflow input
    Given the factory's reusable workflow declares the PI_TIMEOUT input as a string
    And its default is "21600"
    When a target sets PI_TIMEOUT to another number of seconds
    Then every pi invocation in the pipeline runs under the target's value
    And a consumer that leaves the input undeclared keeps the current 360 minute cap

  @config
  Scenario: The job's timeout backstop is a target-side input
    Given the factory's reusable workflow declares the job-timeout input as a string
    And its default is "480" minutes
    When a target sets the job-timeout input to another number of minutes
    Then the five stage jobs that make pi calls run under the target's value as their job-level timeout-minutes
    And the trigger and setup-pi jobs are unaffected by the input
    And a consumer that leaves the input undeclared keeps the 480-minute backstop

  @config
  Scenario: The fastmode threshold is a configurable workflow input
    Given the default fastmode threshold is 5 steps
    When a target sets the fastmode threshold to another number of steps
    Then the implement stage compares the plan's step count against the target's value
    And a consumer that leaves the input undeclared keeps the default of 5

  @config @safety
  Scenario Outline: A declared timeout that fails the trigger's validation ends the run before any stage runs
    Given the target declares <violation>
    When the trigger stage validates the run's configuration
    Then the run fails at trigger time with a precise error
    And no stage runs after the trigger

    Examples:
      | violation |
      | a job timeout that is not a number of minutes |
      | a PI_TIMEOUT and job-timeout pair with no headroom between them — the job timeout does not exceed the resolved pi call cap (the declared pi-timeout value, or the 21600 default where undeclared) by at least the headroom the stage's non-call work needs (the declared job-timeout value, or the "480" default where undeclared) |

  @config
  Scenario: The resolved settings ride the resolved-configuration record
    Given the trigger stage records the run's resolved configuration in the workflow log
    When a run starts with a declared or default pi call cap and job timeout
    Then the resolved values are listed with the rest of the resolved configuration
    And the record stays in the workflow log, never committed to the repo

  @config
  Scenario: The dependency-upgrade setting is configurable
    Given the default for the dependency-upgrade setting is on
    When a target turns it off via its workflow inputs
    Then the run's pipeline runs without the dependency-upgrade stage
    And the run's stages, pull request and final status report are unchanged by the upgrade's absence

  @config
  Scenario: The AUTO_UPDATE setting is configurable
    Given the default for the AUTO_UPDATE setting is true
    When a target turns it off via its workflow inputs
    Then the run's pipeline runs without the update stage
    And the run's stages, pull request and final status report are unchanged by the stage's absence

  @config
  Scenario: Settings flow from workflow inputs to stage environment
    Given the target repo passes its settings via with on the reusable workflow
    When the factory runs
    Then every stage receives the settings via environment variables
    And the resolved configuration is recorded in the workflow log for audit, never committed to the repo

  @config @safety
  Scenario: Secrets are never plain inputs
    Given the factory requires GH_TOKEN and accepts the run's pi harness (the models, settings, mcp and extension-env providers) as GitHub secrets
    When the target repo wires them
    Then the token and the harness providers pass via the reusable workflow's secrets block
    And no secret value appears in with inputs or committed files

  @config
  Scenario: The bug label is configurable
    Given the default bug label is "bug"
    When a target sets the bug label to another value
    Then a run for an issue that carries the trigger label and that value skips the requirements extraction

  @config
  Scenario: Project files are referenced by path, not injected into the pi call
    Given a stage builds a headless pi invocation with project files available (the arc42 docs, the Gherkin oracle, the README, the test output)
    When the stage passes those files to pi
    Then they are only referenced by path in the invocation
    And their contents are NOT embedded in the prompt in full
    And pi reads the ones the task needs on demand with its read tool
    And the invocation's token overhead stays small
    And a file list appears in an instruction only where the set is the instruction's scope — the changed requirements the plan must cover, the off-limits files the guard reverts, the plan file the implement stage works
    And where a stage must hand a project file to pi in full, the plan files and the system prompt are the only files it does so with

  Scenario: A pi call that dies with no output is a dropped stream, not a broken environment
    Given the model backend process is recreated while a stage's pi call is in flight
    And the call's stream closes with nothing delivered
    When the stage classifies the call's non-zero exit
    Then it retries the iteration, consuming the budget
    And only a failure that produced output fails the stage
