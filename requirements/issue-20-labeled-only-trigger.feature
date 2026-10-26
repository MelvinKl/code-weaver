# requirements/issue-20-labeled-only-trigger.feature
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
  Scenario: The README example shows a labeled-only trigger
    When the example's workflow declares the issues trigger
    Then it lists only the "labeled" event type
    And it lists no "opened" or "edited" event type

  @issue-20 @trigger
  Scenario: The repo's own deployed workflow uses a labeled-only trigger
    When the consumer workflow's issues trigger is read
    Then it lists only the "labeled" event type
    And it lists no "opened" or "edited" event type

  @issue-20 @trigger
  Scenario: The documented example and the deployed workflow agree on the trigger
    When the issues trigger declared by the example and by the consumer workflow are compared
    Then both list exactly the same single event type "labeled"

  @issue-20 @trigger
  Scenario: Adding the trigger label still starts the factory and records the issue
    Given the consumer workflow's issues trigger lists only the "labeled" event type
    And the factory is configured with the default label "ai-requirements"
    When the label "ai-requirements" is added to an issue
    Then the factory workflow runs for that issue
    And the factory records the issue number and the issue body

  @issue-20 @trigger
  Scenario: Adding a label that is not the trigger label leaves the factory idle
    Given the consumer workflow's issues trigger lists only the "labeled" event type
    And the factory is configured with the default label "ai-requirements"
    When a label other than "ai-requirements" is added to an issue
    Then the code-weaver workflow fires for that event
    And the trigger stage finds no "ai-requirements" label and stays idle

  @issue-20 @trigger
  Scenario: Opening an issue does not start a factory run
    Given the consumer workflow's issues trigger lists only the "labeled" event type
    When an issue is opened in the repo without any label being added
    Then the code-weaver workflow does not run

  @issue-20 @trigger
  Scenario: Editing an issue without a label change does not start a factory run
    Given the consumer workflow's issues trigger lists only the "labeled" event type
    When an existing issue is edited without any label being added
    Then the code-weaver workflow does not run
