# requirements/guard-rail.feature
# Factory stages 5, 7, 9 — the shared "only X changed" check:
# collect working-tree changes since the baseline, compare them against the
# per-stage file set, and repair a violation with a pi call — the off-limits
# files named, told to be reverted, the stage's own work told to stay valid —
# instead of reverting by git and restarting the stage.

Feature: Only-X-changed guard-rail
  As the factory
  I want every generation stage checked against its allowed file set
  so that a stage that leaks changes elsewhere is repaired by a pi call

  Background:
    Given a baseline git ref was recorded before the stage ran
    And the stage has finished writing files

  @guard
  Scenario: A clean stage passes the guard
    Given the requirement-extraction stage only touched files under requirements/
    When the requirement-check stage compares the working tree against the baseline
    Then the check reports OK
    And the pipeline proceeds to the plan stage

  @guard
  Scenario: A leaking stage is repaired by a pi call, not restarted
    Given the requirement-extraction stage also edited src/app.py
    When the requirement-check stage finds the off-limits change in the working tree
    Then the guard calls pi to repair the violation — the stage is not reverted and re-run
    And the call names src/app.py as the file that changed off-limits
    And the call instructs pi to revert the changes to the named files
    And the call instructs pi to keep the stage's own work valid against the task its initial instructions gave it
    And the allowed changes under requirements/ stay intact
    And a clean re-check lets the pipeline proceed to the plan stage without re-running the extraction stage

  @guard
  Scenario: The allowed file set is per-stage
    Given the pipeline defines an allowed file set per check stage
    Then the requirement-check allows only requirements/
    And the plan-check allows only plans/
    And the implement-check allows everything except requirements/ and the other issues' plans
    And the implement-check does not allow requirements/

  @guard
  Scenario: A requirement edited during implementation is reverted in place
    Given the implement stage edited a file under requirements/
    When the implement-check stage runs
    Then the guard calls pi with the changed file named to revert the edit — no loop back to the plan stage
    And the same call confirms the implementation's work based on the plan is still valid

  @guard @safety
  Scenario: Guard repairs are capped
    Given the loop caps are non-zero
    And the same generation stage keeps leaking the same off-limits file
    When the guard's repair call runs MAX_LOOPS times without clearing the violation
    Then the pipeline stops with a failure report listing the violations

  @guard
  Scenario: All three checks share one implementation
    Given the checks are implemented as one shared guard (one script, three call sites)
    Then each check collects the files changed against its own baseline
    And compares them against its per-stage allowed set
    And repairs a violation with a pi call — the off-limits files named, told to be reverted, the stage's own work told to stay valid

  Scenario: A stage's guard judges only that stage's work
    Given a stage started after earlier stages had committed their outputs
    When the stage's guard collects working-tree changes
    Then it measures them against the branch tip recorded as that stage started
    And outputs committed by earlier stages are not treated as off-limits
