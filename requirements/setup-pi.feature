# requirements/setup-pi.feature
# Factory stage 2 — the setup-pi stage installs pi and configures it for
# this workflow run. The run's pi harness is provided per run — all pi
# configurations are set by env vars: the model configuration, the
# additional packages (an empty or absent provider leaves pi without
# additional packages), the MCP configuration and the extension's
# environment variables, each via the GitHub secret the consumer
# workflow's secrets block carries as the element's provider (issue 147
# removed the repo's .pi directory — a named repo file is no longer a
# provider of any harness element).

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
    And a runner whose PATH does not carry the agent directory gets it extended for the run, so the installed copy resolves on any runner

  @setup
  Scenario: The LLM backend configuration is provided for the run, not a pre-requisite of the environment
    Given the run's model configuration (the models file) is provided by the run's environment variables (the GitHub secret the consumer workflow's secrets block carries)
    When the setup stage configures pi for the run
    Then the pi LLM backend the run uses is the one in that provided model configuration
    And the stage writes that configuration into the pi agent directory the run's pi invocations resolve
    And a target repo steers the run's backend by providing that configuration, not by the runner's environment
    And the runner's pre-existing user-level configuration is never used as the run's configuration

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
    And the run's pi invocations inside the checked-out workspace resolve their model configuration from the agent directory the stage wrote
    And the runner's pre-existing user-level configuration is replaced for the run, not what the invocation resolves
    And the selected model must be listed in the run's configuration for the setup stage's smoke check to pass

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
    Given the provided model configuration (the GitHub secret that provides it) carries no OpenAI-compatible backend URL
    When the setup stage configures pi for the run
    Then the stage fails with an explicit "no backend in the provided configuration" error
    And the runner's pre-existing user-level configuration is never used as the run's configuration

  @setup
  Scenario: The additional packages are provided by a GitHub secret
    Given the additional-packages configuration (the settings content) for the run is provided
    When the setup stage configures pi for the run
    Then the provider is the run's environment variables (the GitHub secret the consumer workflow's secrets block carries)
    And the run's pi runs with the additional packages the provided settings name
    And an empty or absent settings provider leaves pi without additional packages

  @setup
  Scenario: The MCP configuration is optional
    Given no MCP configuration is provided for the run
    When the setup stage configures pi for the run
    Then the run proceeds
    And the run's pi runs without MCP servers
    And where the MCP configuration is provided via a GitHub secret, the stage writes it into the pi agent directory for the run

  @setup
  Scenario: The additional environment variables are provided via a .env-style GitHub secret
    Given the pi extension's environment variables are provided as a GitHub secret in ".env" style
    When the setup stage configures pi for the run
    Then the provided variables are materialised as the extension's environment for the run
    And the run's pi invocations run the extension with those variables
    And the provided variables are set as environment variables in the environment of every pi invocation of the run
    And each value is recorded as a state file in the run's state dir beside the trigger's recorded state, rides the run's artefact chain to every later stage job, and is relayed into that job's environment like the other trigger-state keys
    And every stage job applies the recorded values to its process environment at the stage's entry, so every CLI the stage spawns (its pi invocations, its git children) runs with them in its process environment
    And a run without the provider sets no variable and is unchanged

  @setup
  Scenario: The run's commits carry the author identity the extension's environment provides
    Given the run's provider for the extension's environment carries GIT_AUTHOR_NAME and GIT_AUTHOR_EMAIL
    When the run commits its stage work on the AI branch
    Then the commits carry the provided name and email as their author identity
    And where the provider is empty or absent, the factory writes no identity of its own — the run's commit identity is whatever the runner's own git configuration provides

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
    Then they list the providers — the GitHub secrets for the model configuration, the additional packages, the MCP configuration and the extension's environment variables, all set by env vars
    And they state a named repo file is no longer a provider of any harness element
    And they state an empty or absent settings provider leaves pi without additional packages

  @setup
  Scenario: The .pi directory is removed from the factory repo
    Given the code-weaver repo's committed tree
    Then the tree contains no .pi directory
    And no file of the run's pi harness (a models file, a settings file, an mcp file, an extension) is committed in the repo

  @setup
  Scenario: The run's pi configuration is set by environment variables
    Given the run's pi harness elements (the model configuration, the additional packages, the MCP configuration, the extension's environment variables)
    When the setup stage resolves the harness for the run
    Then each element's provider is the run's environment variables — the GitHub secrets the consumer workflow's secrets block carries
    And a named repo file is no longer a provider of any harness element

  @setup @safety
  Scenario: A run whose environment provides no model configuration fails the setup stage clearly
    Given the run's environment carries no provider for the model configuration
    When the setup stage runs
    Then the stage fails with an explicit error that the run's pi configuration is incomplete
    And no later stage runs
