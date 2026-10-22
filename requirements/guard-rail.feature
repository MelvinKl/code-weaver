# requirements/guard-rail.feature
# Factory stages 5, 7, 9 — the shared "only X changed" check:
# collect working-tree changes since the baseline, allow a per-stage file set,
# revert exactly the off-limits changes, re-run the generation step.

Feature: Only-X-changed guard-rail
  As the factory
  I want every generation stage checked against its allowed file set
  so that a stage that leaks changes elsewhere is reverted and re-run

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
  Scenario: A leaking stage is reverted and re-run
    Given the requirement-extraction stage also edited src/app.py
    When the requirement-check stage compares the working tree against the baseline
    Then only the off-limits file src/app.py is reverted with git checkout and git clean
    And the allowed changes under requirements/ stay intact
    And the requirement-extraction stage is re-run

  @guard
  Scenario: The allowed file set is per-stage
    Given the pipeline defines an allowed file set per check stage
    Then the requirement-check allows only requirements/
    And the plan-check allows only plans/
    And the implement-check allows src/, tests/, docs/, plans/ and README.md
    And the implement-check does not allow requirements/

  @guard
  Scenario: A requirement edited during implementation loops back to planning
    Given the implement stage edited a file under requirements/
    When the implement-check stage runs
    Then the requirement edit is reverted
    And the pipeline loops back to the plan stage

  @guard @safety
  Scenario: Guard re-runs are capped
    Given the loop caps are non-zero
    And the same generation stage keeps leaking the same off-limits file
    When the guard re-runs the generation stage MAX_LOOPS times without success
    Then the pipeline stops with a failure report listing the violations

  @guard
  Scenario: All three checks share one implementation
    Given the checks are implemented as one shared guard (one script, three call sites)
    Then each check collects the files changed against its own baseline
    And compares them against its per-stage allowed set
    And reverts exactly the off-limits files (tracked restored, added removed)

  Scenario: A stage's guard judges only that stage's work
    Given a stage started after earlier stages had committed their outputs
    When the stage's guard collects working-tree changes
    Then it measures them against the branch tip recorded as that stage started
    And outputs committed by earlier stages are not treated as off-limits
