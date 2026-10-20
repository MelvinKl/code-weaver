# requirements/test-and-review.feature
# Factory stages 10 + 11 — Gherkin scenarios as executable acceptance tests,
# plus the self-correcting fix loop (bounded).

Feature: Test and review loop
  As the factory
  I want the built code tested against the Gherkin requirements and reviewed
  so that nothing is proposed for merge that does not fulfil the requirements

  Background:
    Given the implement-check stage passed
    And the target repo's test suite is driven by make test
    And every Gherkin scenario under requirements/ is wired into the test suite

  @review
  Scenario: Gherkin scenarios run as executable acceptance tests
    When the test-and-review stage runs make test
    Then every Scenario under requirements/ is executed as an acceptance test

  @review
  Scenario: Each requirement is checked for fulfilment
    Given the test suite has run
    When pi reviews the results against every Scenario in requirements/
    Then each scenario is marked fulfilled or unfulfilled
    And a PR review of the full diff is produced

  @review
  Scenario: A failed scenario is fixed and re-reviewed
    Given the review reported an unfulfilled scenario
    When the fix loop commits a fix and re-runs test-and-review
    Then the loop repeats until zero problems remain

  @review @safety
  Scenario: The fix loop is bounded by MAX_LOOPS
    Given MAX_LOOPS is non-zero
    And the fix loop has run MAX_LOOPS iterations
    When the problems are still not zero
    Then the pipeline stops with a failure report listing the unfulfilled scenarios

  @review @safety
  Scenario: The loop respects the token budget
    Given MAX_TOTAL_TOKENS is non-zero
    And the cumulative LLM spend reached MAX_TOTAL_TOKENS
    When another loop iteration would start
    Then the loop stops and reports the budget exhaustion

  @review
  Scenario: Every iteration is logged without touching the repo tree
    Given the review loop ran N iterations
    Then each iteration's log is written to the workflow log or an artifact
    And no file under test-results/ is committed to the repo

  Scenario: The requirements reach the review's pi as feature files
    Given the review stage builds pi's context
    When the requirements directory is included
    Then it is expanded to its feature files
    And no directory is ever passed as an @-argument
