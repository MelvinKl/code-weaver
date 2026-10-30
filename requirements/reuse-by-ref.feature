# requirements/reuse-by-ref.feature
# The crux: factory code lives in the code-weaver repo and is referenced by ref —
# the reusable workflow (self-contained: its stage steps are inlined in the
# workflow file) and the runtime tree its steps execute, in the same repo.
# Update = a one-line ref bump in the target repo, never copy-paste.
# Issue 60 delta — the reusable workflow's own composite-action references
# were relative paths, which the runner resolves against the CALLING repo's
# checkout: a target whose tree holds no copy of the factory's actions
# crashes at the first such step ("Can't find 'action.yml' ..."). Fully
# qualifying the refs would pin the workflow to action refs that only a
# release-time rewrite of the workflow file could make consistent — a push
# that updates a workflow file, which the publishing principal is refused.
# So the actions are consolidated into the workflow: one file is one
# version, and each stage job's first step provides the runtime tree it
# executes in the runner's temp dir before the first checkout replaces
# the workspace with the target repo. GitHub never checks the factory
# repo into the target's workspace (it only fetches the workflow file),
# so the consumer relays the called ref as the factory-ref input and the
# step clones the factory repo at that ref (an empty factory-ref falls
# back to copying whatever tree the workspace holds).
# Dogfood delta — this repo is the factory project itself: a run
# triggered in it must check and work the code of the repo it was
# triggered in, not a clone of the factory repo at a pinned ref. Its
# consumer workflow therefore calls the repo's own copy of the factory
# workflow (a relative uses: — the runner reads the file from the
# triggering commit) and leaves the factory-ref input empty: each stage
# job stashes the workspace's own .github / pi-prompts tree before the
# first checkout replaces it, and the run's workflow file and the
# runtime tree its stage steps execute are one version — the triggered
# repo's own. The pinned-tag + relayed-ref pattern above stays the spec
# for external targets (a target whose tree holds no copy of the factory's
# runtime tree).

Feature: Reuse by ref, never copy-paste
  As a maintainer of a target project
  I want the factory code to live in the code-weaver repo and be referenced by ref
  so that factory upgrades are a one-line ref bump with zero drift

  @reuse
  Scenario: The factory is invoked as a reusable workflow
    Given the target repo's workflow .github/workflows/code-weaver.yml
    When it invokes the factory
    Then an external target uses MelvinKl/code-weaver/.github/workflows/factory.yml at a version tag and relays that tag as the factory-ref input
    And a repo that is the factory project itself uses its own copy of the factory workflow — a relative uses: of the workflow file in its own repo — with the factory-ref input left empty
    And it passes issue-number and the factory settings via with
    And it passes GH_TOKEN via secrets

  @reuse
  Scenario: The target workflow stays short and stable
    Given the target repo's workflow file
    Then it only names refs and passes inputs
    And it contains none of the pipeline logic itself

  @reuse
  Scenario: The factory workflow is self-contained
    Given the factory's reusable workflow
    When its stage jobs are read
    Then every stage's steps live in the workflow file itself
    And no step references the factory's actions as separate files

  @reuse
  Scenario: The stage jobs stash the runtime tree before their first checkout
    Given a factory run on a target repo whose tree holds no copy of the factory's runtime tree
    When a stage job starts
    Then its first step provides the factory's .github tree and prompt templates in the runner's temp dir before any checkout replaces the workspace
    And its stage steps run their scripts from that stashed copy

  @reuse
  Scenario: The stage jobs clone the runtime tree from the factory repo at the relayed ref
    Given the consumer workflow passes the factory's called ref as the factory-ref input
    When a stage job starts on a runner whose workspace holds no copy of the factory's runtime tree
    Then its first step clones the factory repo at that ref into the runner's temp dir
    And its stage steps run their scripts from that clone
    And the tree they run is the factory's at the called ref — the workflow file and the runtime tree are one version

  @reuse
  Scenario: A run triggered in the factory's own repo works on that repo's code
    Given the triggered repo is the factory project itself — its tree holds the factory's own runtime tree
    When a stage job starts
    Then the run's workflow file is the repo's own copy of the factory workflow, read from the triggering commit — a relative uses:, never a clone of the factory repo at a pinned ref
    And each stage job stashes the workspace's own .github / pi-prompts tree before its first checkout replaces the workspace and runs its stage steps from that stashed copy
    And the run's workflow file and the runtime tree its stage steps execute are one version — the code of the repo the run was triggered in

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
  Scenario: The README's consumption pattern works on a target repo
    Given a target repo whose consumer workflow is written exactly as the README documents it
    And the target repo's tree holds no copy of the factory's runtime tree
    When a factory run starts on that target repo
    Then every stage step runs the factory's own script from the stashed runtime tree
    And the stashed runtime tree is the factory's, cloned from the factory repo at the ref the consumer relays
    And no step fails looking for the factory's scripts under the target's own checkout
    And the run does not crash at the first stage step

  @reuse @issue-60
  Scenario: A published version is self-contained
    Given the factory's reusable workflow at a published version ref
    And the workflow's stage steps inlined and its runtime tree in the same repo
    When a target invokes the workflow at that version ref
    Then the whole version — the workflow's stage steps and the runtime tree they execute — is selected by that one ref
    And a target's ref bump upgrades the factory atomically, with no separate ref to keep in step

  Scenario: Stage steps declare their shell explicitly
    Given a reusable-workflow factory consumed by this repo's ref
    And the factory's stage steps are inlined workflow steps whose run blocks run scripts
    When a stage step defines a run: but no shell:
    Then the step relies on the runner's default shell instead of the one the script was written against
    And the stage fails before any of its processes start
    And every stage step in the factory declares its shell explicitly
