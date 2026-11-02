# requirements/project-dependencies.feature
# The target project's dependencies — the pipeline step that installs
# them. The factory's pipeline installs pi itself (stage 2) and
# configures the run's pi harness (models, settings, mcp, the
# extension's environment), but it carries no step that installs the
# TARGET PROJECT's own dependencies, and the README carries no
# instructions for adding such a step. This file covers the way to add
# the step, where the declared step runs in the run, that a target
# without one is unchanged, and the README's instructions for it.
# Issue 18 delta — the file's topic gains a second mechanism: the
# factory's pipeline runs a dependency-upgrade stage that upgrades the
# project's dependencies to newer versions — default on, configurable
# off through the consumer workflow (like max-loops), without breaking
# the project's current functionality. The file now also covers that the
# upgrade stage is part of the pipeline and runs before the
# implementation stage, that it keeps the project's functionality
# intact, and the README/arc42 documentation for it (the setting's
# configurability lives in configuration.feature).

Feature: A target can add the pipeline step that installs the project's dependencies
  As a maintainer of a target project
  I want a way to add the pipeline step that installs the project's dependencies to the factory's run
  so that the factory's stages that work the project — the implementation, the target's test suite — run against an environment the project's dependencies are installed in

  @dependencies
  Scenario: The factory provides a way for a target to add a project-dependency-install step
    Given a target project whose work needs the project's dependencies installed
    When the target declares a pipeline step that installs the project's dependencies
    Then the factory provides a way to accept that declaration
    And the run's pipeline executes the declared step as part of the run

  @dependencies
  Scenario: The declared dependency-install step runs before the stages that consume the dependencies
    Given a target declares a project-dependency-install step for its runs
    When the factory's stages that consume the project's dependencies run
    Then the declared step has executed before them
    And the implementation stage and the test-and-review stage's suite run see the installed dependencies

  @dependencies
  Scenario: A target that declares no dependency-install step runs unchanged
    Given a target project that declares no project-dependency-install step
    When the factory's run proceeds
    Then no dependency-install step runs in the pipeline
    And the run's stages, pull request and final status report are unchanged by the mechanism's presence

  @dependencies @docs
  Scenario: The README documents how to add the project-dependency-install step
    Given a target maintainer reading the README for how to run the factory
    When the maintainer looks for how to add the pipeline step that installs the project's dependencies
    Then the README's instructions show how to declare the step the run's pipeline executes
    And the arc42 documentation covering the same mechanism states the same

  @dependencies
  Scenario: The factory's run upgrades the target project's dependencies
    Given a target project with pinned project dependencies
    And the dependency-upgrade setting is at its default
    When the factory's run proceeds
    Then the run's pipeline upgrades the project's dependencies to newer versions
    And the dependency-upgrade stage runs before the implementation stage

  @dependencies
  Scenario: The dependency upgrade does not break the project's current functionality
    Given a target project whose test suite passes on the run's baseline
    When the dependency-upgrade stage upgrades the project's dependencies
    Then the project's test suite still passes against the upgraded dependencies
    And the run's stages that consume the dependencies work against a project whose functionality is intact

  @dependencies @docs
  Scenario: The README and the arc42 documentation describe the dependency-upgrade stage
    Given a target maintainer reading the README for how to run the factory
    When the maintainer looks for how the run's pipeline treats the project's dependencies
    Then the README describes the dependency-upgrade stage and how a target turns it off
    And the arc42 documentation covering the same mechanism states the same
