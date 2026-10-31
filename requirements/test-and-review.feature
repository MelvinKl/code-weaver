# requirements/test-and-review.feature
# Factory stages 10 + 11 — Gherkin scenarios as executable acceptance tests,
# plus the self-correcting fix loop (bounded).

Feature: Test and review loop
  As the factory
  I want the built code tested against the Gherkin requirements and reviewed
  so that nothing is proposed for merge that does not fulfil the requirements

  Background:
    Given the implement-check stage passed
    And the target repo's test suite is driven by make test
    And every Gherkin scenario under requirements/ is wired into the test suite

  @review
  Scenario: Gherkin scenarios run as executable acceptance tests
    When the test-and-review stage runs the target's suite and pi reviews the results
    Then every Scenario under requirements/ is executed by the suite and reported as pass or fail
    And pi marks each scenario of the feature files changed in this run fulfilled or unfulfilled as its acceptance verdict
    And pi does not re-judge scenarios of feature files the run left unchanged

  @review
  Scenario: Each requirement is checked for fulfilment
    Given the test suite has run
    When pi reviews the results against the Scenarios of the feature files changed in this run
    Then each of those scenarios is marked fulfilled or unfulfilled
    And a short note of anything the tests don't cover that affects those scenarios is produced

  @review
  Scenario: A failed scenario is fixed and re-reviewed
    Given the review reported an unfulfilled scenario
    When the fix loop commits a fix and re-runs test-and-review
    Then the loop repeats until zero problems remain

  @review
  Scenario: The reviewer's report is fed into the fixer
    Given the review judged the run's scenarios against the test output
    When the fix loop builds the fix directive
    Then the reviewer's report for the iteration is mirrored into the state dir
    And the directive names the report by path — the fixer reads it on demand
    And the per-scenario evidence, what the fix must do and the findings the tests don't cover reach the fixer with the report

  @review
  Scenario: The review judges every iteration, red or green
    Given a test-and-review iteration
    When the iteration's suite run is reviewed
    Then the review runs on the iteration's test output whether the suite is green or red
    And a red iteration whose review breaks keeps the fix loop running on the raw test output

  @review @safety
  Scenario: The fix loop is bounded by MAX_LOOPS
    Given MAX_LOOPS is non-zero
    And the fix loop has run MAX_LOOPS iterations
    When the problems are still not zero
    Then the pipeline stops with a failure report listing the unfulfilled scenarios

  @review
  Scenario: Every iteration is logged without touching the repo tree
    Given the review loop ran N iterations
    Then each iteration's log is written to the workflow log or an artifact
    And no file under test-results/ is committed to the repo

  Scenario: The requirements reach the review's pi as changed feature files
    Given the review stage builds pi's context
    When the requirements that changed in this run are included
    Then they are expanded to their feature files and only those are referenced
    And no directory is ever passed as an @-argument

  Scenario: A review or fix call cut off at its cap is retried, not fatal
    Given a review or fix pi call outlives its time cap and is cut off
    When the self-correcting loop continues
    Then the iteration is consumed and the call is not treated as a broken environment
    And partial edits from the cut-off call are never committed
    And the next prompt tells the model to audit the partial work before continuing

  Scenario: The suite runs on an interpreter without pytest
    Given the runner's default python interpreter has no pytest module
    And it has no venv or ensurepip to install one
    When the test stage derives its driver
    Then it takes the repo's make test target
    And the suite's runner is a stdlib-only script in the tree
    And the oracle is skipped-not-failed where the parser port is absent

  Scenario: Tests reference the Gherkin requirement they arose from
    Given the test suite under tests/
    When a test that implements a Gherkin scenario is read
    Then it carries a reference to the scenario it arose from
    And a test that is only for correctness carries no such reference

  @review
  Scenario: A test change is judged by the requirement it references
    Given a run whose work changes a test
    When the test-and-review stage reviews the change
    Then a test that is only for correctness may be changed freely
    And a test that references a requirement leaves that requirement fulfilled after the change

  Scenario: A changed requirement pulls in the tests that reference it
    Given the run changed a Gherkin scenario in place
    And the test suite has tests that reference that scenario
    When the implementation works the changed requirement
    Then every test that references the changed scenario is adjusted with it
    And the adjusted tests fulfil the requirement as it now reads
