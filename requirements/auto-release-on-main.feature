# requirements/auto-release-on-main.feature
# Issue 21 — the release trigger and the tag scheme change together: a
# change that lands on the main branch automatically publishes the next
# version as a GitHub release, and that next version is the next single
# increasing number (the old vX.Y.Z semver tags are gone from the release
# flow), so a target never waits on a manual tag to pick up a factory change.
# Issue 79 delta — a published release exposed two holes in that flow.
# (1) A push to main whose only changed file is the consumer workflow
# .github/workflows/code-weaver.yml changed nothing a published version
# carries — a version is the factory workflow and its embedded runtime
# tree, never the consumer's own workflow file — yet the flow spent a
# release number on it. Such a push must publish no release: either the
# flow checks the push's changed files before publishing, or the trigger
# is adjusted so the change does not fire it. (2) The release notes'
# "changed since" list was always empty — the range base fell back to
# "the first commit" even for a release with a predecessor, and the
# diff behind it printed nothing — so the notes must take the
# predecessor release as their range base, list the real changes since
# it, and never print an empty list for a release that publishes
# changes.
# Issue 18 delta — the release changelog's form: the notes'
# changed-since list becomes a table with one row per commit in the
# branch since the previous release, each row carrying the commit's
# title, its author, its hash and its datetime. The two issue-79 notes
# scenarios are updated in place to the table form; their range-base
# rules (predecessor release, first commit without one, never empty)
# stay.

@issue-21 @auto-release
Feature: Automatic release on main branch changes
  As a maintainer of the code-weaver repo
  I want a change that lands on the main branch to publish a new version automatically
  so that targets never wait on a manual tag to pick up a factory change

  @issue-21 @auto-release
  Scenario: A change on main automatically releases a new version
    Given a change is merged into the code-weaver repo's main branch
    And the change's files are not confined to the consumer workflow .github/workflows/code-weaver.yml
    When the release workflow observes the main branch advance
    Then a new version is created and published without any maintainer action
    And the release is a GitHub release that a target can pin like any published version

  @issue-21 @auto-release
  Scenario: The automatic release takes the next increasing number
    Given the code-weaver repo's highest published version is N
    When a change on main triggers the next automatic release
    Then the new version is tagged with the number after N
    And the version numbers of published releases never repeat and never decrease

  @issue-21 @auto-release
  Scenario: The release flow no longer carries the semver scheme
    Given the release workflow that publishes the code-weaver repo's versions
    When its trigger and tag configuration are read
    Then it fires on the main branch's advance rather than on a maintainer's manual tag
    And it creates no semver vX.Y.Z tags

  @issue-79 @auto-release
  Scenario: A push that changes only the consumer workflow publishes no release
    Given a push to the code-weaver repo's main branch
    And the push's only changed file is the consumer workflow .github/workflows/code-weaver.yml
    When the release machinery handles that push
    Then no new version tag is created and no new GitHub release is published
    And no version number is spent on a version whose content did not change
    And the skip is achieved by the release flow checking the push's changed files before publishing or by a trigger the consumer-workflow-only change does not fire
    And a later push whose change set reaches the published version publishes the next release

  @issue-79 @issue-18 @auto-release
  Scenario: The release notes carry a changelog table of the commits since the previous release
    Given a release is published whose branch carries commits since the previous release
    And the release's changed-since range base is the predecessor release — or the first commit where the release has no predecessor
    When the release's notes are read
    Then the notes' changelog is a table with one row per commit in the branch since the range base
    And each row carries the commit's title, its author, its hash and its datetime
    And the table is never empty for a release that publishes changes

  @issue-106 @issue-112 @issue-114 @issue-130 @auto-release
  Scenario Outline: A structurally broken factory workflow file publishes no version
    Given a push to the code-weaver repo's main branch
    And the push's factory workflow file carries the structural defect <defect>
    When the release machinery gates publication on the committed version
    Then the run fails at the structure gate with the exact cause, before the tag
    And no new version tag is created and no new GitHub release is published
    And a target pin never lands on a file whose steps the runner mis-reads

    Examples:
      | defect |
      | a step the runner's YAML parser mis-reads — a step key declared after its run block, or a run block past the giant-body budget |
      | a step whose run block's heredoc terminator sits indented past the block's base indent, or a heredoc the block never terminates — bash reads to end of file |
      | a step whose `python3` code-heredoc has its body's first line indented past the block's base indent — the python program dies with an IndentationError |
      | a step whose field value holds an opening `${` with whitespace after the brace — the runner passes the literal text through as the field's value |
