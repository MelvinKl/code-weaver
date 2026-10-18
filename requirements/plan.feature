# requirements/plan.feature
# Factory stages 6 + 7 — markdown plans under plans/; a plan may cover
# multiple requirement changes (no one-plan-per-requirement rule).

Feature: Planning
  As the factory
  I want the accepted requirements planned in markdown
  so that the implementation follows an explicit, reviewable design

  Background:
    Given the requirement-check stage passed

  @plan
  Scenario: The plans cover every requirement change
    Given the requirements span two Gherkin feature files
    When the plan stage runs pi with the plan prompt template
    Then the markdown plans under the configured PLAN_DIR cover every requirement change
    And a single plan file may fulfil multiple requirement changes

  @plan
  Scenario: The plan describes how the requirements are fulfilled
    Given a plan file covering one or more requirement changes
    When the plan is read
    Then it names the architecture slices the change touches
    And it lists the file-level changes required

  @plan
  Scenario: The plan is grounded in the current architecture
    Given the project's arc42 documentation is a set of markdown files
    When the plan stage runs
    Then pi read the arc42 markdown files and docs/ as context
    And the plan is consistent with the documented architecture

  @plan
  Scenario: The plan stage may only touch plans/
    Given the plan stage wrote files
    When the plan-check stage runs
    Then only files under plans/ have changed
    And any other change is reverted and the plan stage re-runs
