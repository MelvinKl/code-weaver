# requirements/implement.feature
# Factory stages 8 + 9 — implement the plan: code, tests, arc42 docs,
# README; the plan doubles as a state tracker (finished tasks marked done).

Feature: Implementation
  As the factory
  I want the accepted plan implemented as code, tests, arc42 docs and README
  so that the program reflects the requirements in every artefact of the project

  Background:
    Given the plan-check stage passed
    And plans exist under plans/ covering every requirement change

  @implement
  Scenario: The plan is implemented as code
    Given an accepted plan under plans/
    When the implement stage runs pi with the implement prompt template
    Then the code changes named in the plan are made on the AI branch

  @implement
  Scenario: Tests are generated for the new behaviour
    When the implement stage runs
    Then tests covering the new behaviour are added under tests/

  @implement
  Scenario: The arc42 documentation is updated and complete
    Given the implementation changed the architecture
    When the implement stage runs
    Then the arc42 markdown files are updated to reflect the change
    And the arc42 set under docs/ stays complete

  @implement
  Scenario: The README is kept current
    Given the implementation changed user-visible behaviour
    When the implement stage runs
    Then README.md is updated accordingly

  @implement
  Scenario: Implementation must not edit requirements
    Given the implement stage finished
    When the implement-check stage runs
    Then no file under requirements/ has changed
    And any such edit is reverted and the pipeline loops back to the plan stage

  @implement
  Scenario: The implement stage marks finished plan tasks as done
    Given the plan files under the plan dir track which tasks are done
    And the implementation has finished a task named in a plan
    When the implement stage commits its work
    Then the plan file marks that task as done
    And the implement-check passes with the plan change intact

  @implement
  Scenario: An empty implementation on an already-implemented branch is a no-op, not an error
    Given a re-triggered run whose branch already carries the implemented work
    And the implement stage's model response is empty with no file changes
    When the stage measures the branch against the run's baseline (the target's head)
    Then the diff is non-empty — the implementation is already in place
    And the stage succeeds as a satisfied no-op
    And the empty response is not treated as a failure of the model or the environment

  @implement @safety
  Scenario: An empty implementation on an empty tree still fails cleanly
    Given the implement stage's model response is empty with no file changes
    And the branch carries no diff against the run's baseline
    When the stage's bounded retry tolerance is exhausted
    Then the stage fails with an explicit "model kept returning empty output" error
    And no later stage runs on the empty work

  Scenario: The plan is handed to pi as its files
    Given the planning stage wrote plan files under the plan directory
    When the implementation stage builds pi's context
    Then the plan directory is expanded to the files it contains
    And no directory is ever passed as an @-argument

  Scenario: The allow set covers the repo's real layout
    Given a repo whose code lives outside the conventional source dirs (such as .github/)
    And the repo also has a tests/ directory
    When the implementation guard computes its allow set
    Then the set includes the conventional dirs and the other top-level code dirs
    And the set also includes the plans dir — the plan is a live tracker of task state
    And the top-level documentation (README.md, PLAN.md) is allowed
    And the requirements dir stays off-limits
