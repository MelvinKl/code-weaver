# requirements/reporting.feature
# Factory stage 15 — the PR itself is the final status report (no report
# files in the repo), plus the issue comment and arc42 AI-activity section.

Feature: Reporting
  As a maintainer of the target project
  I want a durable report of what the factory did and how it went
  so that I can audit the AI work before I merge anything

  @report
  Scenario: The final status report is the PR
    Given the pipeline reached the report stage
    When the report stage runs
    Then the PR description carries the run status, the source issue and every stage outcome
    And no separate report file is written into the repo

  @report
  Scenario: The source issue is commented with the outcome
    Given GH_TOKEN has issues:write on the target repo
    When the report stage runs
    Then a summary comment is posted on the source issue

  @report
  Scenario: The arc42 documents the AI activity
    When the report stage runs
    Then an AI-activity section is added to the arc42 markdown files under docs/

  @report
  Scenario: A failed run is reported too
    Given the pipeline stopped early in a failed stage
    When the report stage runs
    Then the failure summary states which stage failed and why
    And the source issue is commented with the failure summary
    And no report file is written into the repo

  Scenario: A report is not blocked by a stage that never ran
    Given an earlier stage failed and its job was skipped downstream
    When the report job downloads the stage artifacts
    Then the missing artifacts are downloaded with continue-on-error
    And the stage summary lists only the stages that actually ran
    And the run still concludes failure from the failed stage
