# requirements/requirements-update.feature
# Factory stage — the update stage: it sits in the pipeline after the
# requirement-extraction stage and updates all requirements to the
# newest version unless prohibited by a Gherkin requirement. The stage
# is optional — the AUTO_UPDATE setting turns it off, and it is true by
# default (the setting's configurability lives in configuration.feature).
# Issue 145 delta — new topic file: no existing file covers the update
# stage. requirement-extraction.feature's "A bug-labelled run skips the
# extraction stage" is updated in place — its last Then line now reads
# "And the run proceeds to the update stage and then to the planning
# stage", the update stage sitting between the two.

@update
Feature: The update stage
  As the factory
  I want an optional stage after the requirement-extraction stage that updates all requirements to the newest version
  so that the requirements track the newest version unless a Gherkin requirement prohibits it

  @update
  Scenario: The update stage runs between the requirement-extraction and the planning stages
    Given the AUTO_UPDATE setting is on
    When the run's pipeline has passed the requirement-extraction stage
    Then the update stage runs before the planning stage

  @update
  Scenario: A target that leaves AUTO_UPDATE undeclared runs with the update stage
    Given the target's workflow leaves the AUTO_UPDATE setting undeclared
    When the trigger resolves the run's configuration
    Then AUTO_UPDATE resolves to its true default
    And the run's pipeline runs the update stage

  @update
  Scenario: The update stage updates all requirements to the newest version
    Given the AUTO_UPDATE setting is on
    When the update stage runs
    Then every requirement is updated to the newest version

  @update
  Scenario: A Gherkin requirement can prohibit the update of a requirement
    Given a Gherkin requirement that prohibits a requirement from being updated
    And the AUTO_UPDATE setting is on
    When the update stage runs
    Then the prohibited requirement is left at its current version
    And the requirements no Gherkin requirement prohibits are updated to the newest version
