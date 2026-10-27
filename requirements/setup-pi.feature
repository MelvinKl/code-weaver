# requirements/setup-pi.feature
# Factory stage 2 — the setup-pi stage installs pi and configures it for
# this workflow run. The run's pi harness is provided per run: the model
# configuration via a GitHub secret or the repo file ".pi/agent/models.json",
# the additional packages via a GitHub secret or ".pi/settings.json" (an
# empty or absent provider leaves pi without additional packages), the MCP
# configuration via an optional GitHub secret, and the extension's
# environment variables (such as the ones ".pi/extensions/pi-jev-config.ts"
# carries) via a .env-style GitHub secret.

Feature: The setup-pi stage installs and configures pi for the run
  As a maintainer of a target project
  I want the setup-pi stage to install pi and configure it for each workflow run
  so that the run's pi harness — models, packages, MCP, the extension's environment — is provided per run via a GitHub secret or a repo file

  @setup
  Scenario: The setup stage installs pi for the run
    Given a GitHub Actions runner environment
    When the setup stage runs for a run
    Then the stage installs pi for this workflow run
    And every later pi invocation in the run uses that installed copy

  @setup
  Scenario: The LLM backend configuration is provided for the run, not a pre-requisite of the environment
    Given the run's model configuration (the models file) is provided via a GitHub secret or the repo file ".pi/agent/models.json"
    When the setup stage configures pi for the run
    Then the pi LLM backend the run uses is the one in that provided model configuration
    And the stage writes that configuration into the pi agent directory the run's pi invocations resolve
    And a target repo steers the run's backend by providing that configuration, not by the runner's environment

  @setup
  Scenario: Which configured model is used is adjustable
    Given the run's provided model configuration lists one or more models
    When the factory runs with LLM_MODEL "Ornith-1.5-35B-A3B"
    Then every pi invocation in the pipeline uses that configured model
    And the backend configuration itself is untouched

  @setup
  Scenario: The setup stage verifies the pi it installed actually works
    Given the setup stage installed pi and wrote the run's provided harness
    When the setup stage runs a headless smoke check with pi --print against the selected LLM_MODEL
    Then the stage exits 0 only if the installed pi reaches the backend the stage configured with that model and answers

  @setup
  Scenario: pi runs headless
    Given pi is installed and configured
    When a stage invokes pi with --print
    Then pi processes the prompt and exits
    And no interactive TUI is opened

  @setup
  Scenario: pi reads the project files as context
    Given pi is configured
    When a stage invokes pi with @file arguments for requirements/, README.md and docs/
    Then pi reads the named files as context before answering

  @setup
  Scenario: The run's harness is written into the agent subdirectory the invocation resolves
    Given pi keeps its user configuration in the "~/.pi/agent/" subdirectory (or PI_CODING_AGENT_DIR)
    When the setup stage configures pi for the run
    Then the provided harness (models, settings, mcp, the extension's environment file) is written into that agent directory for the run
    And the backend definition in the configuration the stage wrote is what the smoke check verifies

  @setup @safety
  Scenario: A setup that cannot install or configure pi fails the stage clearly
    Given the setup stage's installation of pi fails or its provided model configuration is unusable
    When the setup stage runs
    Then the stage fails with an explicit "pi installation or configuration failed" error
    And no later stage runs

  @setup @safety
  Scenario: An unreachable backend fails the stage clearly
    Given the backend named in the run's provided model configuration is unreachable from the runner
    When the setup stage verifies the backend
    Then the stage fails with an explicit "backend unreachable" error
    And no later stage runs

  @setup
  Scenario: A verify step only runs under a runner-accepted shell form
    Given a composite action step that carries an interpreter program
    When the runner validates the step's shell declaration before executing it
    Then the declaration is a built-in shell or a format string naming the interpreter and the script placeholder
    And the step's program actually executes and the stage sees its result

  @setup
  Scenario: A provided file without a backend is not a usable configuration
    Given the provided model configuration (a GitHub secret or the repo file) carries no OpenAI-compatible backend URL
    When the setup stage configures pi for the run
    Then the stage fails with an explicit "no backend in the provided configuration" error
    And the runner's pre-existing user-level configuration is never used as the run's configuration

  Scenario: pi resolves its model configuration from the agent directory the setup stage wrote
    Given pi resolves models.json from the user agent directory ("~/.pi/agent/", or PI_CODING_AGENT_DIR)
    And the setup stage wrote the run's provided models configuration into that directory
    When a factory stage invokes pi inside the checked-out workspace
    Then the invocation resolves the run's provided model configuration from the agent directory
    And the runner's pre-existing user-level configuration is replaced for the run, not what the invocation resolves
    And the selected model must be listed in the run's configuration for the setup stage's smoke check to pass

  @setup
  Scenario: The model configuration is provided by a GitHub secret or a repo file
    Given the model configuration for the run is provided
    When the setup stage configures pi for the run
    Then the provider is a GitHub secret or the repo file ".pi/agent/models.json"
    And the run's pi invocations resolve their model set from the configuration the stage wrote

  @setup
  Scenario: The additional packages are provided by a GitHub secret or a repo file
    Given the additional-packages configuration (the settings content) for the run is provided
    When the setup stage configures pi for the run
    Then the provider is a GitHub secret or the repo file ".pi/settings.json"
    And the run's pi runs with the additional packages the provided settings name

  @setup
  Scenario: An empty or absent settings provider leaves pi without additional packages
    Given the settings secret is empty or absent
    And no ".pi/settings.json" file exists in the repo
    When the setup stage configures pi for the run
    Then the run's pi runs without any additional packages

  @setup
  Scenario: The MCP configuration is optional
    Given no MCP configuration is provided for the run
    When the setup stage configures pi for the run
    Then the run proceeds
    And the run's pi runs without MCP servers

  @setup
  Scenario: The MCP configuration is provided via a GitHub secret
    Given the MCP configuration (the ".pi/mcp.json" content) is provided via a GitHub secret
    When the setup stage configures pi for the run
    Then the stage writes the provided MCP configuration into the pi agent directory for the run

  @setup
  Scenario: The additional environment variables are provided via a .env-style GitHub secret
    Given the pi extension's environment variables (such as the ones ".pi/extensions/pi-jev-config.ts" carries) are provided as a GitHub secret in ".env" style
    When the setup stage configures pi for the run
    Then the provided variables are materialised as the extension's environment for the run
    And the run's pi invocations run the extension with those variables

  @setup @docs
  Scenario: The documented setup stage installs and configures pi for the run
    Given the README's stage list and the arc42 chapters describe the setup stage
    When those descriptions are read
    Then they state the setup stage installs pi and configures it for the workflow run
    And they state no pre-installed or pre-configured pi is a pre-requisite of the runner environment

  @setup @docs
  Scenario: The documentation lists the harness providers
    Given the README and the arc42 deployment chapter describe how the run's pi harness is provided
    When those descriptions are read
    Then they list the providers — the GitHub secrets and the repo files ".pi/agent/models.json", ".pi/settings.json" and ".pi/mcp.json", plus the ".env"-style secret for the extension's environment variables
    And they state an empty or absent settings provider leaves pi without additional packages
