# requirements/requirement-extraction.feature
# Factory stages 3 + 4 — derive the delta requirements from the project itself
# (arc42.json + git diff + docs/README) and write them as Gherkin.

Feature: Requirement extraction
  As the factory
  I want to derive the delta requirements from the target project itself
  so that the requirements are grounded in the project's current state instead of being invented

  Background:
    Given pi is installed and configured
    And the factory works on an AI branch cut from the issue's base branch
    And the issue body is available to the factory

  @baseline
  Scenario: The baseline captures the issue's change set
    Given the issue describes a change already visible in the working tree
    When the baseline stage runs
    Then the baseline is the git diff of the issue's changed files
    And a baseline git ref is recorded for the later guard-rail checks

  @extraction
  Scenario: Requirements are derived from the project itself
    Given the project has arc42.json, docs/ and README.md
    When the extraction stage runs pi with the requirements prompt template
    Then pi reads arc42.json, the baseline diff and docs/README as context
    And the derived requirements are the delta implied by the issue text against that baseline

  @extraction
  Scenario: Requirements are written as Gherkin files
    Given the extraction stage produced delta requirements
    When pi writes the requirements
    Then the requirements land as .feature files under the configured REQUIREMENTS_DIR
    And every generated file is valid, parseable Gherkin

  @extraction
  Scenario: Gherkin structure follows the canonical keywords
    Given a generated .feature file
    Then it uses the Feature, Scenario, Background and Scenario Outline keywords
    And its steps use Given, When, Then, And and But
    And tabular examples and doc-strings use the Gherkin table and quoted-string syntax

  @extraction
  Scenario: An empty issue body does not produce invented requirements
    Given the issue body is empty or describes no change
    When the extraction stage runs
    Then no requirement file is written
    And the factory reports "no delta requirements" and stops cleanly

  @extraction
  Scenario: Re-running extraction on unchanged input is idempotent
    Given the extraction stage already wrote the requirements for issue 7
    When the extraction stage runs again for issue 7
    Then the requirement files are unchanged
