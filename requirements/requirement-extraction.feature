# requirements/requirement-extraction.feature
# Factory stages 3 + 4 — derive the delta requirements from the project itself
# (arc42 markdown files + git diff + docs/README) and write them as Gherkin.

Feature: Requirement extraction
  As the factory
  I want to derive the delta requirements from the target project itself
  so that the requirements are grounded in the project's current state instead of being invented

  Background:
    Given pi is pre-installed and pre-configured in the runner environment
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
    Given the project has the arc42 markdown files, docs/ and README.md
    When the extraction stage runs pi with the requirements prompt template
    Then pi reads the arc42 markdown files, the baseline diff and docs/README as context
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
    Given the extraction stage already wrote the requirements for an issue
    When the extraction stage runs again for the same issue
    Then it updates the same requirement file in place (named after the issue)
    And no duplicate requirement files fork

  Scenario: The context handed to pi is concrete files, never directories
    # pi's @-argument handling reads each argument as a file (it even
    # sniffs image mime types) — a directory there crashes pi with EISDIR
    Given the requirements dir and the doc dir exist in the checkout
    When the stage assembles the pi context arguments
    Then every context argument is a file that exists
    And directories are expanded to the files they contain

  Scenario: Extraction writes one new file named after the issue
    Given an issue with a number and a title
    When the extraction stage writes its delta requirements
    Then it creates exactly one new feature file named after the issue number
    And no existing feature file differs from the baseline

  Scenario: An empty model response does not consume the loop budget
    # a wedged or silent model must not burn a bounded-loop iteration the
    # guard could only trivially pass; the retry tolerance is itself bounded
    Given a generation loop bounded by the loop cap
    When the model returns no output and changes no file
    Then the same iteration is retried without counting against the cap
    And the empty-response tolerance is itself bounded

  Scenario: Generated feature files contain only Gherkin the official parser accepts
    Given a model response that produced a feature file
    When the file is checked against the official Gherkin parser
    Then every line is a Gherkin keyword line or blank
    And no markdown, prose or scratchpad text is present

  Scenario: A failed validation feeds the parser's verdict back into the next attempt
    Given a generated feature file the official parser rejected
    When the loop re-runs the model
    Then the next prompt carries the parser's complaint
    And the model repairs the file against that exact error

  Scenario: A pi call cut off at its time cap is retried, not treated as a broken environment
    Given a reasoning model whose generation outlives the pi call cap
    When a stage runs the bounded generation loop
    Then the call is cut off at the cap and reports exit code 124
    And the stage does not fail on the grounds of a broken environment
    And the partial output is committed and judged like any other iteration
    And the loop retries the model within its bounded budget
