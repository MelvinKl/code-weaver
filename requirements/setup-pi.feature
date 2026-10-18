# requirements/setup-pi.feature
# Factory stage 2 — pi is pre-installed and pre-configured in the
# GitHub Actions environment; the factory verifies it, never installs or
# configures it. The LLM backend is a pre-requisite of the environment;
# what is adjustable is which of the configured models is used.

Feature: pi pre-installed and configured in the runner environment
  As the operator of the GitHub Actions runners
  I want pi installed and configured in the runner environment ahead of time
  so that the factory never installs or configures pi itself in CI

  @setup
  Scenario: pi is already on the runner
    Given a GitHub Actions runner environment
    When the setup stage checks for pi
    Then pi is present on the PATH
    And the factory performs no installation step

  @setup
  Scenario: The LLM backend configuration is a pre-requisite of the environment
    Given the pi configuration defining the LLM backend is a pre-requisite of the runner environment
    When the setup stage checks the backend configuration
    Then pi's LLM backend (e.g. keyless llama-swap at "http://192.168.5.28:8080/v1") is already configured
    And the factory performs no configuration step
    And no target repo can change which backend the factory uses

  @setup
  Scenario: Which configured model is used is adjustable
    Given the runner environment has pi pre-configured with one or more models
    When the factory runs with LLM_MODEL "Qwen3.8"
    Then every pi invocation in the pipeline uses that configured model
    And the backend configuration itself is untouched

  @setup
  Scenario: The setup stage verifies pi actually works
    Given pi is pre-installed and pre-configured
    When the setup stage runs a headless smoke check with pi --print against the selected LLM_MODEL
    Then the stage exits 0 only if pi reaches the pre-configured backend with that model and answers

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

  @setup @safety
  Scenario: A missing or misconfigured pi fails the stage clearly
    Given pi is absent or misconfigured on the runner
    When the setup stage verifies pi
    Then the stage fails with an explicit "pi not installed or configured on this runner" error
    And the factory does not attempt to install or configure pi
    And no later stage runs

  @setup @safety
  Scenario: An unreachable backend fails the stage clearly
    Given the pre-configured LLM backend is unreachable from the runner
    When the setup stage verifies the backend
    Then the stage fails with an explicit "backend unreachable" error
    And no later stage runs
