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
  Scenario: The LLM backend is a pre-requisite of the environment
    Given the pi configuration in the runner environment defines the LLM backend
    Then the backend is fixed by that pre-requisite configuration
    And no target repo can change which backend the factory uses

  @config
  Scenario: Which configured model is used is adjustable
    Given the runner environment has pi pre-configured with several models
    And the default LLM_MODEL is "Ornith-1.5-35B-A3B"
    When a target sets LLM_MODEL to another already-configured model
    Then every pi invocation in the pipeline uses that model
    And the backend configuration itself is unchanged

  @config
  Scenario: The action ref is configurable
    Given the default AI_REPO_REF is MelvinKl/code-weaver at the current release tag
    When a target pins a different ref
    Then the factory runs from that ref

  @config
  Scenario: The loop caps are configurable
    Given the defaults are MAX_LOOPS 5 and MAX_TOTAL_TOKENS 500000
    When a target lowers or raises them
    Then every bounded loop in the pipeline uses the target's values

  @config
  Scenario: A loop cap of 0 means no cap
    Given the defaults are MAX_LOOPS 5 and MAX_TOTAL_TOKENS 500000
    When a target sets MAX_LOOPS to 0
    Then the guard re-run, review-fix and gate-fix loops run without a loop-count limit
    And setting MAX_TOTAL_TOKENS to 0 removes the token budget
    And the resolved configuration records the removed caps

  @config
  Scenario: Settings flow from workflow inputs to stage environment
    Given the target repo passes its settings via with on the reusable workflow
    When the factory runs
    Then every stage receives the settings via environment variables
    And the resolved configuration is recorded in the workflow log for audit, never committed to the repo

  @config @safety
  Scenario: Secrets are never plain inputs
    Given the factory requires GH_TOKEN
    When the target repo wires the token
    Then it passes it via the reusable workflow's secrets block
    And no secret value appears in with inputs or committed files

  Scenario: A stage's pi calls bound the model's thinking
    Given a reasoning model whose chat template runs thinking unbounded by default
    When a stage builds a headless pi invocation
    Then the command passes an explicit bounded --thinking level
    And the runner's pre-installed pi configuration is never modified
    And a single call cannot reason past the loop's time cap

  Scenario: A pi call that dies with no output is a dropped stream, not a broken environment
    Given the model backend process is recreated while a stage's pi call is in flight
    And the call's stream closes with nothing delivered
    When the stage classifies the call's non-zero exit
    Then it retries the iteration, consuming the budget
    And only a failure that produced output fails the stage
