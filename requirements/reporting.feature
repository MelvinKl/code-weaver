# requirements/reporting.feature
# Factory stage 15 — durable status report, issue comment, arc42 activity.

Feature: Reporting
  As a maintainer of the target project
  I want a durable report of what the factory did and how it went
  so that I can audit the AI work before I merge anything

  @report
  Scenario: A final status report is written
    Given the pipeline reached the report stage
    When the report stage runs
    Then the run status is written under test-results/
    And the report links the PR, the source issue and every stage outcome

  @report
  Scenario: The source issue is commented with the outcome
    Given GH_TOKEN has issues:write on the target repo
    When the report stage runs
    Then a summary comment is posted on the source issue

  @report
  Scenario: The arc42 documents the AI activity
    When the report stage runs
    Then an AI-activity section is added to the arc42 docs under docs/

  @report
  Scenario: A failed run is reported too
    Given the pipeline stopped early in a failed stage
    When the report stage runs
    Then the report states which stage failed and why
    And the source issue is commented with the failure summary
