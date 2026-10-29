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
  Scenario: The PR description carries the same usage numbers as the issue comment
    Given the run made pi calls and the report stage assembles the usage totals
    When the report stage completes the PR body and comments the source issue
    Then the PR description and the issue comment list the same total input tokens
    And the PR description and the issue comment list the same total output tokens and the same total cost
    And the stage verifies the PR-body completion actually landed before claiming the final status is in the PR body
    And where the completion could not be applied to the PR — as when the PR was already merged — the issue comment carries the full final status itself instead of that claim

  @report
  Scenario: A successful run closes the source issue
    Given the run reached the report stage with result success and the PR is open
    When the report stage runs
    Then the source issue is closed with the completed state reason
    And the issue comment states the run result and that the issue is closed
    And the factory still does not merge the PR itself

  @report
  Scenario: A failed run leaves the source issue open
    Given the run reached the report stage with result failure
    When the report stage runs
    Then the source issue is left open for a re-trigger
    And only the failure summary is commented on it

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

  @report
  Scenario: The report step's plumbing is bound on a runner where the shared module imports
    Given the report stage's step is inlined in the factory workflow
    And the step calls its plumbing (the state dir, the state file, the log, the gh api, the branch push) by bare name
    When the shared module the step imports resolves from the runtime tree
    Then the step's plumbing names are bound for the step's body
    And the step does not fail with an undefined-name error before any of its report work has run

  @report
  Scenario: The report step's fallback plumbing stays effective where the shared module cannot import
    Given the report stage's step is inlined in the factory workflow
    And the shared module the step imports does not resolve from the runtime tree
    When the step runs in that environment
    Then the step's body runs on its local fallback definitions
    And the step completes its report as on the import path
