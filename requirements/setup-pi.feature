# requirements/setup-pi.feature
# Factory stage 2 — pi installed in CI and pointed at the LLM backend.

Feature: pi installation and LLM backend configuration
  As a CI runner
  I want pi installed and configured against the LLM backend
  so that every later stage can invoke pi headless without a TTY

  @setup
  Scenario: pi is installed on the runner
    Given a fresh CI runner (ubuntu-latest)
    And the target repo is checked out on the AI branch
    When the setup stage installs pi
    Then pi is available on the PATH
    And pi runs on a Node v22 runtime

  @setup
  Scenario: The LLM backend is configured as an MCP server
    Given the factory is configured with LLM_MCP_URL "http://192.168.5.28:8080/v1"
    And the factory is configured with LLM_MODEL "Qwen3.8"
    When the setup stage configures the backend
    Then pi is pointed at the backend keyless with apiKey "llama-swap"
    And the configuration is committed to ./.pi/mcp.json

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
  Scenario: An unreachable backend fails the stage clearly
    Given the LLM backend at LLM_MCP_URL is unreachable from the CI network
    When the setup stage verifies the backend
    Then the stage fails with an explicit "backend unreachable" error
    And no later stage runs
