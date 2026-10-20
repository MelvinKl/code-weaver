# requirements/implement.feature
# Factory stages 8 + 9 — implement the plan: code, tests, arc42 docs, README.

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

  Scenario: The plan is handed to pi as its files
    Given the planning stage wrote plan files under the plan directory
    When the implementation stage builds pi's context
    Then the plan directory is expanded to the files it contains
    And no directory is ever passed as an @-argument
