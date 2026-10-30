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
# So the actions were consolidated into the workflow: one file is one
# version.
# Single-pin delta — GitHub fetches only the called workflow's file, and
# the called ref is not visible to the run's jobs; the old answer relayed
# the ref as the factory-ref input (a second pin beside the consumer's
# uses: line) and had each stage job clone the factory repo at it. The
# restored-and-improved rewrite carries the answer in the file: the
# runtime tree (the .github scripts, the stage scripts, the pi prompt
# templates) is embedded in the workflow file, stage 1 materialises it,
# and the trigger's artifact carries it to every later stage job — the
# consumer's uses: ref is the only pin a run makes, and no run fetches
# the factory repo. The rewrite is committed to main by the maintainer
# (the `embed` make target), guarded by the embed's contract test, and
# the release flow gates publication on its freshness — the publishing
# principal still only pushes tag objects, never a workflow-file commit.
# Dogfood delta — this repo is the factory project itself: a run
# triggered in it checks and works the code of the repo it was
# triggered in (the checkout is the triggered repo, never a clone of
# the factory repo). Its consumer workflow pins the public release
# line — a version tag of the MelvinKl line, the same shape its
# external targets use: the dogfood exercises exactly the published
# version the external targets get, so a broken release breaks the
# dogfood visibly. The pin selects the machinery — the workflow file
# and the runtime tree embedded in it (the tagged version; the embed's
# contract test keeps that version fresh) — never the code a run
# works. One tag per commit: the release flow's guard makes a re-run
# at an unchanged HEAD publish nothing, so a number is never spent on
# a duplicate.

Feature: Reuse by ref, never copy-paste
  As a maintainer of a target project
  I want the factory code to live in the code-weaver repo and be referenced by ref
  so that factory upgrades are a one-line ref bump with zero drift

  @reuse
  Scenario: The factory is invoked as a reusable workflow
    Given the target repo's workflow .github/workflows/code-weaver.yml
    When it invokes the factory
    Then an external target uses MelvinKl/code-weaver/.github/workflows/factory.yml at a version tag — one pin: the file at the tag carries its runtime tree embedded, so no relayed ref accompanies it
    And a repo that is the factory project itself pins the public release line too — a version tag of the MelvinKl line — with the (legacy) factory-ref input left undeclared
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
    And its runtime tree is embedded in the file (a base64 tarball in stage 1's first step), so the file carries what its steps execute

  @reuse
  Scenario: The stage jobs materialise the runtime tree before their first checkout
    Given a factory run on a target repo whose tree holds no copy of the factory's runtime tree
    When a stage job starts
    Then the first job of the run decodes the runtime tree embedded in the workflow file into the runner's temp dir
    And every later stage job restores it from the trigger's artifact before its first checkout replaces the workspace
    And its stage steps run their scripts from that materialised copy

  @reuse
  Scenario: The whole version is one ref
    Given the factory's reusable workflow at a published version ref
    When a target invokes it at that ref
    Then the workflow file and the runtime tree its steps execute are the one version that ref selects — the tree is embedded in the file, so no stage job clones the factory repo at a second ref
    And the stage jobs fetch nothing from the factory repo at run time — the consumer's uses: ref is the only pin a run makes

  @reuse
  Scenario: A run triggered in the factory's own repo works on that repo's code
    Given the triggered repo is the factory project itself
    When a stage job starts
    Then the run's workflow file is the public release the dogfood pins — the factory workflow at a version tag of the MelvinKl line, never a clone of the factory repo at a second ref
    And each stage job materialises the runtime tree the workflow file embeds — the tagged version's tree, the embed's contract test keeping that version fresh — and runs its stage steps from that copy
    And the code the run works is the triggered repo's own — the pin selects the machinery (the file and its embedded tree), never the code

  @reuse
  Scenario: An upgrade is a ref bump
    Given the code-weaver repo tagged a new release
    When the target repo bumps the ref in its workflow
    Then the next factory run uses the new version
    And the target's workflow file keeps its single pin — the uses: line
    And no other file in the target repo changed

  @reuse
  Scenario: Every published version is a stable ref
    Given the code-weaver repo has published versions
    When a new release is published
    Then its tag is a single increasing version number
    And workflows pinned to an older ref keep working
    And a re-run of the release at an unchanged HEAD publishes nothing — one tag per commit, so a number is never spent on a duplicate

  @reuse @issue-60
  Scenario: The README's consumption pattern works on a target repo
    Given a target repo whose consumer workflow is written exactly as the README documents it
    And the target repo's tree holds no copy of the factory's runtime tree
    When a factory run starts on that target repo
    Then every stage step runs the factory's own script from the materialised runtime tree
    And the materialised runtime tree is the factory's at the called ref — the file's embedded payload, decoded by stage 1 (no clone at run time; the consumer relays nothing)
    And no step fails looking for the factory's scripts under the target's own checkout
    And the run does not crash at the first stage step

  @reuse @issue-60
  Scenario: A published version is self-contained
    Given the factory's reusable workflow at a published version ref
    And the workflow's stage steps inlined and its runtime tree embedded in the file
    When a target invokes the workflow at that version ref
    Then the whole version — the workflow's stage steps, its embedded runtime tree, and the trigger's artifact that carries it across jobs — is selected by that one ref
    And a target's ref bump upgrades the factory atomically, with no separate ref to keep in step

  Scenario: Stage steps declare their shell explicitly
    Given a reusable-workflow factory consumed by this repo's ref
    And the factory's stage steps are inlined workflow steps whose run blocks run scripts
    When a stage step defines a run: but no shell:
    Then the step relies on the runner's default shell instead of the one the script was written against
    And the stage fails before any of its processes start
    And every stage step in the factory declares its shell explicitly
