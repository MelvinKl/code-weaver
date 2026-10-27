# 2. Objectives

- **One label starts a complete run.** A labelled issue produces reviewed,
  tested work as a pull request — no human scaffolding in between.
- **Requirements are derived, not invented.** The delta requirements come
  from the target project itself (its arc42 markdown, its baseline diff,
  its README); an empty or vague issue body produces nothing.
- **Bounded autonomy.** Every loop in the pipeline (guard re-run,
  review-fix, gate-fix) is capped; a cap of 0 means uncapped, and a
  non-zero cap guarantees the run terminates.
- **The human stays the gate.** The factory opens the PR and stops;
  merging is a manual decision, and the PR body is the final status
  report a human reads before merging. When the run succeeded, the
  factory closes the issue behind that PR; a failed run leaves the
  issue open for a re-trigger.
- **Reuse by ref, never copy-paste.** Factory upgrades are a one-line ref
  bump in the target; every published tag is a stable ref.
- **The oracle is executable.** Every Gherkin scenario under
  `requirements/` is an acceptance test the factory runs against its own
  work (and that a target's test-and-review stage runs against the
  target).
