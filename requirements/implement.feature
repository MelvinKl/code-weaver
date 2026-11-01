# requirements/implement.feature
# Factory stages 8 + 9 — implement the plan one step at a time: code,
# tests, arc42 docs, README; the plan is a live Jira-ticket state tracker
# (the next open step is worked and marked done each invocation); only the
# current issue's plan is editable.

Feature: Implementation
  As the factory
  I want the plan implemented as code, tests, arc42 docs and README, one step at a time
  so that the program reflects the requirements in every artefact of the project
  and a re-run resumes exactly where the last run left off

  Background:
    Given the plan-check stage passed
    And a single plan exists under plans/ for the issue, named plans/<issue_number>.md, in Jira-ticket style with an ordered step checklist

  @implement
  Scenario: The plan is implemented as code
    Given an accepted plan under plans/
    When the implement stage runs pi with the implement prompt template
    Then the code changes named in the plan are made on the AI branch

  @implement
  Scenario: The implementation works the next open step and marks it done
    Given the plan file has one or more open (`- [ ]`) steps
    When the implement stage runs pi with the implement prompt template
    Then the implementation works exactly one open step — the first open step reading from the top of the Steps checklist
    And it marks that step done (`- [x]`) in the plan file when finished

  @implement
  Scenario: The implementation loops until every step is done or a cap is reached
    Given the plan file still has open steps after a step is marked done
    When the implement stage is called again
    Then it works the next open step and marks it done
    And it keeps doing this until every step is done or the time/token limit (a loop cap) is reached

  @implement
  Scenario: Tests are generated for the new behaviour
    When the implement stage runs
    Then tests covering the new behaviour are added under tests/
    And each test that implements a requirement carries a reference to the Gherkin scenario it arose from

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
    And any such edit is reverted by the guard's pi repair call — it does not re-run the stage or loop back to the plan stage

  @implement
  Scenario: Implementation may only edit the current issue's plan
    Given more than one plan exists under the plan dir (plans for different issues)
    And the implementation for issue N has finished a step named in plans/N.md
    When the implement stage commits its work
    Then plans/N.md marks that step as done
    And no other plan file (e.g. plans/M.md) is changed
    And the implement-check passes with the plan change intact

  @implement
  Scenario: An empty implementation on an already-implemented branch is a no-op, not an error
    Given a re-triggered run whose branch already carries the implemented work
    And every step in the plan is already marked done
    When the implement stage reads the plan and finds no open step
    Then the stage succeeds as a satisfied no-op
    And the empty response is not treated as a failure of the model or the environment

  @implement @safety
  Scenario: An empty implementation on an empty tree still fails cleanly
    Given the implement stage's model response is empty with no file changes
    And the branch carries no diff against the run's baseline
    When the stage's bounded retry tolerance is exhausted
    Then the stage fails with an explicit "model kept returning empty output" error
    And no later stage runs on the empty work

  Scenario: The plan is handed to pi as its files
    Given the planning stage wrote a plan file under the plan directory
    When the implementation stage builds pi's context
    Then the current issue's plan file is expanded to that file as an @-argument
    And no directory is ever passed as an @-argument

  Scenario: The implement guard runs inverted-allow
    Given a repo the implementation must add code and tests to
    And a `tests/` dir (or docs set, top-level files) that did not exist before the stage ran
    When the implementation guard computes its denied set and its allow set
    Then the denied set is the protected set — the requirements dir and the plan dir
    And the allow set re-allows exactly the current issue's plan file and pycache at any depth
    And everything else is admitted — the tests the implementation has the job to implement are never reverted
    And no other plan file is allowed
    And the requirements dir stays off-limits

  @implement @brownfield
  Scenario: A brown field run adjusts the tests without implementing code
    Given a run whose requirements were extracted from the project's existing code
    When the implement stage works the plan
    Then the implementation changes no source code — the changed files are the tests and the issue's plan file
    And the existing tests are adjusted to reference the requirements they describe
    And each adjusted test that implements a scenario cites it in its docstring as <feature file>::<scenario name>

  @implement
  Scenario: A clean call with steps still open logs the per-step line, not a stage completion
    Given the plan file has open (`- [ ]`) and done (`- [x]`) steps
    When a clean generation call inside the implement stage has just marked a step done
    Then the implement stage logs "stage 8 implementation: clean — step <done>/<total> of the plan done; <remaining> step(s) remain"
    And done, total and remaining are counted from the plan file's checkboxes
    And no "stage complete" is printed by the implement stage while any step of its plan remains open

  @implement
  Scenario: A fully tracked plan logs the full step count before the stage completes
    Given the plan file has no open (`- [ ]`) steps left
    When the implement stage exits its per-step loop
    Then it logs "stage 8 implementation: all <total> plan steps done — stage complete" with the plan's total step count
    And that is the only line the implement stage prints that calls the stage complete

  @implement
  Scenario: The single-call stages keep the plain completion line
    Given the extract, plan or review stage completes in a single generation call
    When the shared generation loop comes back clean for it
    Then it logs the plain "clean — stage complete" line for that stage
    And the per-step completion label is the implement stage's own — the shared loop does not force one wording on every caller

  @implement
  Scenario: The templates, the plan files and the stage log agree on one word for the plan's units
    Given the planner template and the implementer template
    And a plan file the plan stage generated and the implement stage's log
    When their wording for the plan's checklist units is read
    Then the plan's section heading is "Steps"
    And the templates' instructions and the implement stage's log call the units steps
    And the checkbox form `- [ ]` for an open unit and `- [x]` for a done one is unchanged — the code that reads the plan keys on the checkbox, not the word
