# requirements/reuse-by-ref.feature
# The crux: factory code lives in the code-weaver repo and is referenced by ref —
# reusable workflow, JS action as npm package, composite action.
# Update = a one-line ref bump in the target repo, never copy-paste.
# Issue 60 delta — the reusable workflow's own composite-action references
# are relative paths, which the runner resolves against the CALLING repo's
# checkout: a target whose tree holds no copy of the factory's actions
# crashes at the first such step ("Can't find 'action.yml' ..."), so the
# documented consumption must name the factory's actions by owner, repo and
# path, and every published version must be self-consistent in its refs.

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
    Given the target consumes the factory as a reusable workflow
    When the consumer writes its uses: line
    Then it names the factory by owner, repo, path and ref
    And the factory's own workflow steps reference its composite actions by owner, repo and path — pinned to that same ref

  @reuse
  Scenario: An upgrade is a ref bump
    Given the code-weaver repo tagged a new release
    When the target repo bumps the ref in its workflow
    Then the next factory run uses the new version
    And no other file in the target repo changed

  @reuse
  Scenario: Every published version is a stable ref
    Given the code-weaver repo has published versions
    When a new release is published
    Then its tag is a single increasing version number
    And workflows pinned to an older ref keep working

  @reuse @issue-60
  Scenario: The factory's workflow names its own actions by owner, repo and path
    Given the factory's reusable workflow invokes its composite actions in its stage jobs
    When every step's uses reference in the workflow is read
    Then each composite action is named by the factory's owner, repo and path
    And no reference is a relative path — a relative path in a reusable workflow resolves against the calling repo's checkout

  @reuse @issue-60
  Scenario: The README's consumption pattern works on a target repo
    Given a target repo whose consumer workflow is written exactly as the README documents it
    And the target repo's tree holds no copy of the factory's composite actions
    When a factory run starts on that target repo
    Then every stage job's composite action step loads the factory's action definition
    And no step fails with a missing action file under the target's own checkout
    And the run does not crash at the first stage that invokes a composite action

  @reuse @issue-60
  Scenario: A published version is self-consistent in its action references
    Given the factory's reusable workflow at a published version ref
    And the workflow's steps reference the factory's composite actions
    When a target invokes the workflow at that version ref
    Then every composite action in the run loads from the same version ref as the workflow
    And a target's ref bump selects the workflow and its actions as one version

  Scenario: Composite action steps declare their shell explicitly
    Given a reusable-workflow factory consumed by this repo's ref
    And the factory's stage actions are composite actions whose steps run scripts
    When a stage action defines a step with a run: but no shell:
    Then the runner's action loader rejects the action (required property missing)
    And the stage step fails before any of its processes start
    And every composite step in the factory declares its shell explicitly
