# requirements/cost-and-token-usage.feature
# Issue 43 — the final report carries the run's total cost and input/output
# token usage; the token budget (MAX_TOTAL_TOKENS), which cannot be enforced
# during a pi call, is removed from the configuration surface.
# Standing scenarios this delta supersedes — the rewording specified in
# plans/43.md was reported in run #43's stage reply instead of editing
# (requirements/ was read-only to the extraction stage then); it lands in
# the files themselves with the issue-69 run, which touches these same
# scenarios:
#   configuration.feature "The loop caps are configurable"
#   configuration.feature "A loop cap of 0 means no cap"
#   test-and-review.feature "The loop respects the token budget"
#   safety.feature "Every loop in the pipeline respects its cap" (wording)

@issue-43
Feature: Run cost and token usage in the report, token budget removed
  As a maintainer of a target project
  I want the final report to state what the run cost and how many tokens it used
  so that the LLM spend of the factory's work is visible before anything is merged
  and the configuration stops carrying a budget the pipeline cannot enforce

  @issue-43 @report
  Scenario: The final report lists the input and output tokens used during the run
    Given a run whose stages made pi calls
    When the report stage runs
    Then the final status report lists the total input tokens used across the run
    And the final status report lists the total output tokens used across the run

  @issue-43 @report
  Scenario: The final report lists the total cost of the run
    Given a run whose stages made pi calls
    When the report stage runs
    Then the final status report lists the total cost of the run's LLM usage
    And the listed cost is consistent with the run's recorded token usage

  @issue-43 @report
  Scenario: The usage totals cover every pi call the run made
    Given the run's stages made pi calls across several stages and loop iterations
    When the report stage assembles the run's usage totals
    Then the totals add up the usage of every pi call the run made
    And a pi call that left no usage record contributes nothing to the totals

  @issue-43 @report
  Scenario: Each pi call's token usage is recorded as the run proceeds
    Given a stage runs a pi call
    When the call finishes
    Then the call's input and output token counts are recorded in the run's state
    And the usage record travels with the run's state artifacts like every other stage value

  @issue-43 @report
  Scenario: The usage and cost of a failed run are reported too
    Given the run stopped early in a failed stage
    And the stages that ran before the failure made pi calls
    When the report stage assembles the usage totals of the run
    Then the totals cover the pi calls the run made before it stopped
    And the final status report still lists the tokens and the cost

  @issue-43 @config
  Scenario: The configuration surface no longer carries a token budget
    Given the factory's configurable settings
    When a target configures the factory
    Then the settings contain no max-tokens input and no token budget
    And the resolved configuration recorded in the workflow log has no token budget
    And the max-loops setting stays configurable at its default of 5

  @issue-43 @safety
  Scenario: The bounded loops stop on success or their iteration cap, not on token spend
    Given the pipeline contains the guard repair, the review-fix and the gate-fix loops
    And MAX_LOOPS is non-zero
    When one of those loops runs
    Then the loop stops when its problems are resolved or when it reaches the MAX_LOOPS iteration cap
    And no token budget is one of the loop's stopping conditions

  @issue-43 @safety
  Scenario: Removing the token budget keeps the factory guaranteed to terminate
    Given all remaining loop caps of the pipeline are non-zero
    Then the factory is guaranteed to terminate
    And every bounded loop is bounded by its iteration cap alone

  @issue-43 @config
  Scenario: The documented input surface no longer lists a token budget
    Given the README's table of the factory's workflow inputs
    When the table is read
    Then it lists no max-tokens input and no token budget
    And it still lists the max-loops input
