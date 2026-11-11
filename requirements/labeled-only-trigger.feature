# requirements/labeled-only-trigger.feature
# Issue 20 — the code-weaver trigger (on.issues.types) should be set to
# "labeled" only, both in the README's consumption example and in the
# version this repo deploys on itself (.github/workflows/code-weaver.yml).
# Consequence: opening or editing issues no longer fires the workflow —
# only a label addition (and manual dispatch) does.

Feature: Labeled-only factory trigger
  As a maintainer of a target project
  I want the code-weaver workflow to fire only when the trigger label is added
  so that opening or editing issues no longer spawns idle factory runs

  Background:
    Given the code-weaver repo's own consumer workflow .github/workflows/code-weaver.yml
    And the README's "Consume it (by ref)" example of a target code-weaver workflow

  @issue-20 @trigger
  Scenario: The README example and the repo's own deployed workflow declare the same labeled-only trigger
    When the issues trigger declared by the example and by the consumer workflow are compared
    Then both list exactly the same single event type "labeled"
    And neither lists an "opened" or "edited" event type

  @issue-20 @trigger
  Scenario: An issue opened or edited without a label addition does not start a factory run
    Given the consumer workflow's issues trigger lists only the "labeled" event type
    When an issue is opened without any label being added, or an existing issue is edited without any label being added
    Then the code-weaver workflow does not run

  @issue-20 @trigger
  Scenario: Adding a label that is not the trigger label leaves the factory idle
    Given the consumer workflow's issues trigger lists only the "labeled" event type
    And the factory is configured with the default label "ai-requirements"
    When a label other than "ai-requirements" is added to an issue
    Then the code-weaver workflow fires for that event
    And the trigger stage finds no "ai-requirements" label and stays idle
