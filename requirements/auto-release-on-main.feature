# requirements/auto-release-on-main.feature
# Issue 21 — the release trigger and the tag scheme change together: a
# change that lands on the main branch automatically publishes the next
# version as a GitHub release, and that next version is the next single
# increasing number (the old vX.Y.Z semver tags are gone from the release
# flow), so a target never waits on a manual tag to pick up a factory change.

@issue-21 @auto-release
Feature: Automatic release on main branch changes
  As a maintainer of the code-weaver repo
  I want a change that lands on the main branch to publish a new version automatically
  so that targets never wait on a manual tag to pick up a factory change

  @issue-21 @auto-release
  Scenario: A change on main automatically releases a new version
    Given a change is merged into the code-weaver repo's main branch
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
