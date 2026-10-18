# requirements/setup-pi.feature
# Factory stage 2 — pi is already installed and configured in the
# GitHub Actions environment; the factory verifies it, never installs it.

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
  Scenario: The LLM backend configuration is already in place
    Given the runner environment has pi pre-configured
    When the setup stage checks the backend configuration
    Then pi is pointed at LLM_MCP_URL "http://192.168.5.28:8080/v1" with LLM_MODEL "Qwen3.8" keyless
    And the factory performs no configuration step

  @setup
  Scenario: The setup stage verifies pi actually works
    Given pi is pre-installed and pre-configured
    When the setup stage runs a headless smoke check with pi --print
    Then the stage exits 0 only if pi reaches the backend and answers

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
    Given the LLM backend at LLM_MCP_URL is unreachable from the runner
    When the setup stage verifies the backend
    Then the stage fails with an explicit "backend unreachable" error
    And no later stage runs
