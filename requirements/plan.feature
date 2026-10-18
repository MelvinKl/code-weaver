# requirements/plan.feature
# Factory stages 6 + 7 — one markdown plan per requirement group, under plans/.

Feature: Planning
  As the factory
  I want each accepted requirement group planned in markdown
  so that the implementation follows an explicit, reviewable design

  Background:
    Given the requirement-check stage passed

  @plan
  Scenario: One plan file per requirement group
    Given the requirements span two Gherkin feature files
    When the plan stage runs pi with the plan prompt template
    Then one markdown plan is written per requirement group under the configured PLAN_DIR

  @plan
  Scenario: The plan describes how the requirements are fulfilled
    Given a plan file for a requirement group
    When the plan is read
    Then it names the architecture slices the change touches
    And it lists the file-level changes required

  @plan
  Scenario: The plan is grounded in the current architecture
    Given the project has an arc42.json
    When the plan stage runs
    Then pi read arc42.json and docs/ as context
    And the plan is consistent with the documented architecture

  @plan
  Scenario: The plan stage may only touch plans/
    Given the plan stage wrote files
    When the plan-check stage runs
    Then only files under plans/ have changed
    And any other change is reverted and the plan stage re-runs
