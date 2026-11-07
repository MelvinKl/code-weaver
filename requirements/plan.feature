# requirements/plan.feature
# Factory stages 6 + 7 — one Jira-ticket-style plan per issue, at
# plans/<issue_number>.md; the planner is told which requirement files
# changed and what those changes are (the whole oracle is not handed to
# it); the guard verifies only that one plan file changed.

Feature: Planning
  As the factory
  I want the accepted requirements planned in a Jira-ticket-style markdown
  plan per issue
  so that the implementation follows an explicit, reviewable design
  and each run resumes from where a previous run left off

  Background:
    Given the requirement-check stage passed

  @plan
  Scenario: The plan lives at plans/<issue_number>.md
    Given a run for issue N
    When the plan stage runs pi with the plan prompt template
    Then the plan is written to plans/N.md under the configured PLAN_DIR
    And the plan stage writes exactly one file for the issue

  @plan
  Scenario: Every issue gets its own plan and there is no overall plan
    Given a run for issue N
    When the plan stage runs
    Then the plan stage writes only plans/N.md for this issue
    And no other plan file is created
    And no overall/aggregate plan file is created

  @plan
  Scenario: The planner is told which requirements changed and what those changes are
    Given the full Gherkin requirements include scenarios that already exist (which bound what must NOT change)
    When the plan stage builds pi's context
    Then the instructions name the requirement file(s) that changed since the baseline
    And the instructions carry what those files changed — the delta the plan must cover
    And pi reads the changed files on demand rather than having them embedded in the prompt
    And the whole existing oracle is not injected into the planner

  @plan
  Scenario: The plan covers every requirement change
    Given the changed requirements for the issue
    When the plan stage runs pi with the plan prompt template
    Then the plan covers every changed requirement — each changed/new scenario is named in the plan

  @plan
  Scenario: The plan is written in Jira ticket style
    Given a plan file for the issue
    When the plan is read
    Then it has a Jira-issue structure (Summary, Description, Acceptance Criteria mapped to the scenarios)
    And it lists an ordered, atomic Steps checklist as checkboxes so the implementation works one step at a time

  @plan
  Scenario: The plan describes how the requirements are fulfilled
    Given a plan file covering the issue's requirement changes
    When the plan is read
    Then for each step it names the requirement(s) it fulfils
    And it lists the file-level changes and the architecture slices the step touches

  @plan
  Scenario: The plan is grounded in the current architecture
    Given the project's arc42 documentation is a set of markdown files
    When the plan stage runs
    Then pi read the arc42 markdown files and docs/ as context
    And the plan is consistent with the documented architecture

  @plan
  Scenario: The plan stage may only touch its own plan file
    Given the plan stage wrote files
    When the plan-check stage runs
    Then only plans/N.md has changed
    And any other change is reverted and the plan stage re-runs

  @plan @brownfield
  Scenario: A brown field plan scopes its steps to the test references
    Given a run whose requirements were extracted from the project's existing code
    When the plan stage runs pi with the plan prompt template
    Then the plan names the extracted scenarios it must cover
    And the plan's steps are scoped to adjusting the tests to reference those scenarios
    And no plan step implements code

  @plan
  Scenario: A bug issue is planned from the issue itself without an extracted delta
    Given the run skipped the extraction stage for a bug-labelled issue
    And no requirement file changed since the run's baseline
    When the plan stage builds pi's context
    Then the instructions name no requirement file as changed
    And the instructions carry the issue — its number, title and body — as what the plan must cover
    And the plan is written to plans/N.md like every other issue's plan
