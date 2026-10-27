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
  Scenario: The LLM backend is provided for the run, not a pre-requisite of the environment
    Given the run's model configuration is provided via a GitHub secret or the repo file ".pi/agent/models.json"
    Then the backend the run uses is the one in that provided configuration
    And the runner's pre-existing pi configuration is not the run's configuration

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

  @config @safety
  Scenario: The pi harness secrets ride the reusable workflow's secrets block
    Given the factory accepts the run's pi harness (the models, settings, mcp and extension-env providers) as GitHub secrets
    When the target repo wires them
    Then they pass via the reusable workflow's secrets block
    And no harness secret value appears in with inputs or committed files

  Scenario: A stage's pi call lets pi-jev choose the thinking level
    Given pi-jev is configured for the run (its environment variables provided via the .env-style secret, or the repo file ".pi/extensions/pi-jev-config.ts") to classify each prompt (PI_JEV_THINKING / --jev-thinking)
    When a stage builds a headless pi invocation of a reasoning model
    Then the command does NOT pass an explicit --thinking level
    And pi-jev chooses the reasoning level for that prompt
    And the stage's invocation never modifies the pi configuration — only the setup stage writes it for the run
    And a single call stays within the pi call's own time cap

  @config
  Scenario: Project files are referenced by path, not injected into the pi call
    Given a stage builds a headless pi invocation with project files available (the arc42 docs, the Gherkin oracle, the README, the test output)
    When the stage passes those files to pi
    Then they are only referenced by path in the invocation
    And their contents are NOT embedded in the prompt in full
    And pi reads the ones the task needs on demand with its read tool
    And the invocation's token overhead stays small

  @config
  Scenario: The plan files are the only implementation files handed to pi in full
    Given the implement stage builds a headless pi invocation
    Then the system prompt is handed to pi in full
    And the plan files the stage reads and updates are handed to pi in full
    And every other project file is only referenced by path

  Scenario: A pi call that dies with no output is a dropped stream, not a broken environment
    Given the model backend process is recreated while a stage's pi call is in flight
    And the call's stream closes with nothing delivered
    When the stage classifies the call's non-zero exit
    Then it retries the iteration, consuming the budget
    And only a failure that produced output fails the stage
