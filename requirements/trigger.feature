# requirements/trigger.feature
# Factory stage 1 — what starts the pipeline, and for which issue.

Feature: Factory trigger
  As a maintainer of a target project
  I want the factory to start when I tag an issue with the requirements label
  so that I can kick off the whole pipeline with a single label change

  Background:
    Given the target repo has installed the code-weaver workflow
    And the workflow references the factory as a reusable workflow
    And the factory is configured with the default label "ai-requirements"

  @trigger
  Scenario: Issue opened with the label starts the factory
    Given an issue is opened in the target repo
    When the issue carries the label "ai-requirements"
    Then the factory workflow runs
    And the factory records the issue number and the issue body

  @trigger
  Scenario: Editing an issue to add the label starts the factory
    Given an existing issue without the label "ai-requirements"
    When the label "ai-requirements" is added to the issue
    Then the factory workflow runs for that issue

  @trigger
  Scenario: An issue without the label does not start the factory
    Given an issue is opened in the target repo
    When the issue carries only the label "bug"
    Then the factory workflow does not run

  @trigger
  Scenario: The trigger label is configurable
    Given the factory is configured with AI_REQUIREMENTS_LABEL "ai-changes"
    When an issue is labelled "ai-changes"
    Then the factory workflow runs for that issue

  @trigger
  Scenario: A manual dispatch processes a named issue
    Given no issue label is present
    When the workflow is dispatched with issue_number "42"
    Then the factory runs for issue 42

  @trigger @safety
  Scenario: Re-entrant runs on the same issue do not duplicate work
    Given a factory run for issue 7 is already in progress
    When a second trigger fires for issue 7
    Then the second run does not duplicate the work of the first
    And both runs operate on the same branch "ai/code-weaver/7"
