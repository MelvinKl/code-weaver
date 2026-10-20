# requirements/reuse-by-ref.feature
# The crux: factory code lives in the code-weaver repo and is referenced by ref —
# reusable workflow, JS action as npm package, composite action.
# Update = a one-line ref bump in the target repo, never copy-paste.

Feature: Reuse by ref, never copy-paste
  As a maintainer of a target project
  I want the factory code to live in the code-weaver repo and be referenced by ref
  so that factory upgrades are a one-line ref bump with zero drift

  @reuse
  Scenario: The factory is invoked as a reusable workflow
    Given the target repo's workflow .github/workflows/code-weaver.yml
    When it invokes the factory
    Then it uses MelvinKl/code-weaver/.github/workflows/factory.yml at a version tag
    And it passes issue-number and the factory settings via with
    And it passes GH_TOKEN via secrets

  @reuse
  Scenario: The target workflow stays short and stable
    Given the target repo's workflow file
    Then it only names refs and passes inputs
    And it contains none of the pipeline logic itself

  @reuse
  Scenario: Composite actions are referenced by owner, repo and path
    Given a composite action in the code-weaver repo
    When a step references it
    Then it uses MelvinKl/code-weaver/.github/actions/NAME at a version tag

  @reuse
  Scenario: An upgrade is a ref bump
    Given the code-weaver repo tagged a new release
    When the target repo bumps the ref in its workflow
    Then the next factory run uses the new version
    And no other file in the target repo changed

  @reuse
  Scenario: Every published version is a stable ref
    Given the code-weaver repo has published versions
    When a maintainer tags a new release
    Then the tag follows vX.Y.Z semver
    And workflows pinned to an older ref keep working

  Scenario: Composite action steps declare their shell explicitly
    Given a reusable-workflow factory consumed by this repo's ref
    And the factory's stage actions are composite actions whose steps run scripts
    When a stage action defines a step with a run: but no shell:
    Then the runner's action loader rejects the action (required property missing)
    And the stage step fails before any of its processes start
    So every composite step in the factory declares its shell explicitly
