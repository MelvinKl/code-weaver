#!/usr/bin/env python3
"""Stage 4+5 — requirement extraction + requirement check.

  pi (requirements.md prompt, issue body as the prompt, the project files as
  context) derives the delta requirements for the issue and writes them as
  Gherkin into the requirements dir, placed by topic — an existing topic file
  extended in place, a new file only for a topic no file yet covers. A run for
  an issue that carries the bug label (the trigger records the bug-issue flag
  in the run's state, derived against the resolved bug label) skips the
  derivation entirely — the entry logic's first branch, checked before the
  directory branch: no pi call is made for the stage, no requirement file is
  written, the requirement check passes with no requirement file changed, the
  stage records its skip on the stage-summary channel, and the run proceeds
  to the update stage (when the AUTO_UPDATE setting runs it) and then to the
  planning stage (the plan is built from the issue itself);
  a bug-labelled issue with an empty body instead reaches the "no delta
  requirements" clean stop: the stop records its run-level half in the run's
  state dir (the no-delta-stop flag beside the trigger's recorded state — it
  rides the cumulative artefact chain to every later stage job, and the
  per-job env relay, like the other trigger-state keys), and the update
  stage (the plan job's inlined step — it checks the same flag in its step
  and no-ops) and the plan stage check it before their own pi call — set,
  the plan stage stops
  cleanly without a pi call (no plan file, its own outcome line on the
  stage-summary channel, the report rendering it as skipped, never as
  "stage complete"): the run is not forwarded to the update stage or the
  plan stage. A
  target without a requirements directory is a first factory run on that
  project: the entry logic takes its first-run branch there (the
  full-derivation prompt — pi derives the full requirement set from the
  project's current code, documentation and tests, a source the project does
  not have is skipped rather than failing, and the .feature files it writes
  create the directory); the empty-body "no delta requirements" stop applies
  only where a requirements directory exists — the standing stop records
  the same run-level no-delta-stop flag, so a run that stops there is not
  forwarded to the update stage or the plan stage either. The guard
  (the one shared idiom) then verifies that ONLY the requirements dir changed
  — a leak is repaired in place by the guard's pi call (the off-limits files
  named, told to be reverted, the stage's own work told to stay valid) and a
  clean re-check lets the stage complete without re-running the extraction.
  Changed
  feature files must parse with Cucumber's official Gherkin parser (a
  requirement must be executable: the test-and-review stage runs every
  scenario).
"""
from __future__ import annotations

import os
import subprocess
import sys

# The action directory comes from this file's own location: on this
# runner build GITHUB_ACTION_PATH is unset inside composite action
# inner steps, and on a healthy runner both sources agree anyway
action_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(action_dir)), "scripts"))

import common
import stages

# The full-derivation prompt a first run on a target without a requirements
# directory hands pi: the first-run marker plus the directive the template's
# first-run clause governs (derive the full requirement set from the
# project's current code, documentation and tests — a source the project does
# not have is skipped rather than failing — write the requirements as
# .feature files that create the directory). The issue's header and body ride
# below it where the trigger carries them (build_prompt appends them).
FIRST_RUN_PROMPT = (
    "# This run is a first run on a target without a requirements "
    "directory\n\n"
    "The target project has no requirements directory yet, so there is no "
    "existing oracle to derive a delta against. The first-run clause of "
    "your instructions governs this run: derive the project's **full** "
    "requirement set from the project's current code, documentation and "
    "tests — a source the project does not have is skipped rather than "
    "failing the extraction — and write the requirements as `.feature` "
    "files that create the requirements directory.\n"
)


def existing_context() -> list[str]:
    """The NON-oracle project files the extraction's pi call reads — handed
    to pi as @-file arguments (pi reads the named files as context before
    answering): the arc42 markdown (the docs/ files — the top-level PLAN.md
    where a target has no doc dir), README.md, and the baseline diff (the
    issue's change set recorded by the baseline stage). The Gherkin oracle
    is NOT expanded into these arguments: the call's instructions name its
    directory as the oracle's location and list no requirement file by name
    — pi reads the files it judges relevant from that directory on demand
    (a directory is never an @-argument)."""
    ctx = stages.project_context(include_oracle=False)
    diff = common.state_file("baseline.diff")
    if os.path.exists(diff):
        ctx.append(diff)
    return ctx


def _revert(f: str, baseline: str) -> None:
    """Revert exactly one file, the guard's way: tracked at the baseline →
    restore its baseline content; a file the stage added → remove it from
    the tree (committed or not)."""
    p = os.path.join(common.repo(), f)
    if common.git_exec(["cat-file", "-e", f"{baseline}:{f}"],
                       cwd=common.repo(),
                       capture_output=True).returncode == 0:
        common.git_exec(["checkout", baseline, "--", f],
                        cwd=common.repo(), check=False)
    elif common.git_exec(["ls-files", "--", f], cwd=common.repo(),
                         capture_output=True).stdout.strip():
        common.git_exec(["rm", "-f", "--", f], cwd=common.repo(), check=False)
    elif os.path.exists(p):
        os.remove(p)


def post_ok() -> bool:
    """The Gherkin-oracle half of stage 5: every changed .feature must parse
    with the official parser, and the delta's shape is the topic placement —
    a delta's scenarios extend the existing topic file that covers their topic
    (a merely changed existing file is NOT a violation), a new file is created
    only for a topic no file yet covers, named after the topic, never after the
    issue (the validator's naming check carries that complaint), and a changed
    existing file that no longer parses — or a deleted topic file — is reverted
    to its baseline content and the extraction re-runs. A violation is reverted
    and its verdict persisted, so the next iteration's prompt carries it and the
    model repairs against the exact complaint instead of regenerating blind."""
    baseline = stages.baseline_sha()
    req = common.env_dir("REQUIREMENTS_DIR").rstrip("/")
    validator = os.path.join(stages.repo_root(), ".github", "scripts", "gherkin-validate.py")
    verdict = common.state_file("extract-validation.txt")

    complaints: list[str] = []
    revert: list[str] = []
    changed = common.changed_files(baseline)

    # Delta shape: the guard keeps changes inside the requirements dir; the
    # stage pins the topic placement inside it.
    parse_batch: list[str] = []
    for f in changed:
        if not stages.under(f, req) or not f.endswith(".feature"):
            continue
        existed = common.git_exec(["cat-file", "-e", f"{baseline}:{f}"],
                                  cwd=common.repo(),
                                  capture_output=True).returncode == 0
        if existed and not os.path.exists(os.path.join(common.repo(), f)):
            # A deleted topic file is a violation: the delta places scenarios
            # (extending a topic file, creating one for an uncovered topic),
            # it does not delete a topic's home. Restore it.
            complaints.append(
                f"an existing feature file was deleted — the delta extends or "
                f"creates topic files, it does not delete them — restored: {f}")
            revert.append(f)
        else:
            # Both an extended existing topic file (the placement itself —
            # judged only by the parse check below: a changed file is NOT a
            # violation, a file that no longer parses IS) and a genuinely new
            # file (which must be named after the topic it covers, never after
            # the issue — the validator's naming check carries that complaint
            # below, which also triggers the revert) are judged by the
            # official parser.
            parse_batch.append(f)

    # Parse oracle: every changed .feature must parse with the official
    # Cucumber Gherkin parser (a requirement must be executable).
    if parse_batch:
        r = subprocess.run([sys.executable, validator, *parse_batch],
                           capture_output=True, text=True)
        if r.returncode != 0:
            for line in r.stderr.splitlines():
                if line.startswith("FAIL "):
                    name = line[len("FAIL "):].split(":", 1)[0].strip()
                    if "named after an issue" in line:
                        complaints.append(
                            f"a feature file must be named after the topic it "
                            f"covers, never after the issue — got "
                            f"'{os.path.basename(name)}'")
                    else:
                        complaints.append(f"the official Gherkin parser rejected {name}")
                    if name not in revert:
                        revert.append(name)
            parser_verdict = r.stderr.strip()
        else:
            parser_verdict = ""
    else:
        parser_verdict = ""

    if not complaints:
        with open(verdict, "w", encoding="utf-8") as f:
            f.write("PASS")
        common.log(f"stage 5: {len(parse_batch)} feature file(s) parse with the "
                   f"official Gherkin parser; delta placed by topic")
        return True

    with open(verdict, "w", encoding="utf-8") as f:
        f.write("\n".join(complaints))
        if parser_verdict:
            f.write("\n" + parser_verdict)
    revert = list(dict.fromkeys(revert))
    common.log(f"::error::stage 5: {'; '.join(complaints)} → reverted: "
               f"{' '.join(revert) or '(none)'}")
    for f in revert:
        _revert(f, baseline)
    common.commit_all("requirements: invalid extraction reverted (re-extracting)")
    return False


def _is_bug_run() -> bool:
    """Whether the run's issue is a bug issue — the trigger's recorded
    state value (the issue's labels compared against the resolved bug
    label): the state file in the trigger's state dir is the documented
    record (it rides the trigger's artifact to every later stage job), and
    the per-job env relay (CW_BUG_ISSUE) is the in-process channel the same
    value rides. A run the trigger did not record the flag for is not a bug
    run — the standing entry logic is unchanged for it."""
    v = (common.cw_state("bug-issue")
         or common.cw_input_opt("bug-issue") or "")
    return v.strip().lower() == "true"


def _record_no_delta_stop() -> None:
    """The no-delta stop's run-level half: the stop flag in the run's state
    dir — a state file beside the trigger's recorded state
    (`no-delta-stop`), riding the same channels every trigger-state value
    rides (the cumulative artefact chain to every later stage job — every
    upload carries the whole state dir — and the per-job env relay, like
    the other trigger-state keys). The plan stage checks that flag before
    its own work: the run that stopped at the extraction is not forwarded
    to the plan stage — the plan stage stops cleanly on the signal without
    a pi call (no plan file, and its own outcome line on the stage-summary
    channel, which the report renders as skipped, never as "stage
    complete"). A bug-labelled run that merely skipped the derivation (a
    non-empty-body bug issue) records no flag: its run proceeds to a plan
    built from the issue itself."""
    d = os.path.join(common.state_dir(), "state", "trigger")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "no-delta-stop.txt"), "w", encoding="utf-8") as f:
        f.write("true\n")


def main() -> None:
    common.install_crash_diagnostics("stage 4 requirements-extraction")
    # the run's resolved extension env applied to this stage's process
    # environment at entry (the artefact-channel half of the relay that
    # keeps the every-step contract whole on a runner build whose
    # GITHUB_ENV write ghosts): every CLI the stage then spawns — its pi
    # invocations, its git children — inherits the provider's values
    common.apply_extension_env()
    req = common.env_dir("REQUIREMENTS_DIR")
    body = common.state_file("issue-body.md")
    body_empty = (not os.path.exists(body)
                  or not open(body, encoding="utf-8").read().strip())
    # The bug-skip branch — the entry logic's first branch, checked before
    # the directory branch: a run for an issue that carries the resolved
    # bug label skips the derivation. No pi call is made for the stage and
    # no requirement file is written, so the requirement check passes with
    # no requirement file changed (the guard's whitelist over the
    # requirements dir is trivially satisfied — no file is touched, so no
    # repair call; the guard machinery is untouched). The stage records its
    # skip on the documented stage-summary channel and the run proceeds
    # to the update stage (when the AUTO_UPDATE setting runs it) and then
    # to the planning stage (the plan is built from the issue
    # itself; the 15-stage / 9-job pipeline count is unchanged — the skip
    # is a recorded outcome inside the existing job, not a new stage or
    # job). The branch's empty-body edge: a bug-labelled issue whose body
    # is empty or describes no change reaches the standing empty-body
    # stop's identical observable outcome (no requirement file written;
    # "no delta requirements" reported; the run stops cleanly) — by the
    # skip instead of by the extraction running and writing nothing — and
    # the run is NOT forwarded to the update stage (its step checks the
    # same flag and no-ops) or to the plan stage: the stop records its
    # run-level no-delta-stop flag in the run's state dir (the signal both
    # check before their own work), while the skip itself
    # records no flag — the bug-labelled run's way through to the plan.
    if _is_bug_run():
        if body_empty:
            common.log("stage 4: the issue is a bug issue and its body is "
                       "empty or describes no change — no delta "
                       "requirements; the stage writes nothing and stops "
                       "cleanly (the run is not forwarded to the update "
                       "stage or the plan stage); the stop records its "
                       "run-level flag in the run's state dir — the signal "
                       "both check before their own work")
            with open(common.state_file("stage-summary.txt"), "a",
                      encoding="utf-8") as f:
                f.write("stage 4-5 requirement extraction: no delta "
                        "requirements (bug-labelled issue, empty issue "
                        "body)\n")
            _record_no_delta_stop()
        else:
            common.log("stage 4: the issue is a bug issue — the run skips "
                       "the requirement extraction: no pi call is made for "
                       "the stage, no requirement file is written; the "
                       "requirement check passes with no requirement file "
                       "changed, and the run proceeds to the update stage "
                       "(when the AUTO_UPDATE setting runs it) and then to "
                       "the planning stage (the plan is built from the "
                       "issue itself)")
            with open(common.state_file("stage-summary.txt"), "a",
                      encoding="utf-8") as f:
                f.write("stage 4-5 requirement extraction: skipped "
                        "(bug-labelled issue — no pi call, no requirement "
                        "file written)\n")
        # the skip (like the early stop) completes the stage's work: its
        # completion marker rides with the line (the report cross-checks
        # both to tell "the stage ran" from "the stage never ran")
        common.record_stage_ran("cw-extract")
        return
    # The empty-body stop is conditioned on the target project HAVING a
    # requirements directory: a missing body and an empty body are the same
    # case there — no change is described, so there are no delta
    # requirements, and the stage writes nothing and stops cleanly (handing
    # pi a blank issue would invite it to invent requirements out of
    # silence). A target WITHOUT a requirements directory is a first factory
    # run on that project: the stage proceeds to its generation loop instead
    # of stopping, with the full-derivation prompt — the requirements it
    # derives are written as .feature files that create the directory.
    first_run = bool(req) and not os.path.isdir(req)
    if not first_run and body_empty:
        common.log("stage 4: issue body is empty — no delta requirements; the "
                   "stage writes nothing and stops cleanly; the stop records "
                   "its run-level flag in the run's state dir — the update "
                   "stage (its step) and the plan stage check it before "
                   "their own work, so the run is not forwarded to the "
                   "update stage or the plan stage")
        with open(common.state_file("stage-summary.txt"), "a", encoding="utf-8") as f:
            f.write("stage 4-5 requirement extraction: no delta requirements "
                    "(empty issue body)\n")
        _record_no_delta_stop()
        # the early stop completes the stage's work: its completion marker
        # rides with the line (the report cross-checks both to tell "the
        # stage ran" from "the stage never ran")
        common.record_stage_ran("cw-extract")
        return
    if first_run:
        common.log("stage 4: the target has no requirements directory — a "
                   "first factory run on that project; the extraction derives "
                   "the full requirement set, and the generated .feature "
                   "files create the directory")

    def build_prompt():
        # The model places the delta by topic — extending the existing topic
        # file, creating a new file only for a topic no file yet covers and
        # naming it after the topic, never the issue (the oracle is
        # structured by topic): same unchanged input → same placement → the
        # same files with the same content, so re-runs stay idempotent.
        # The issue's number and title ride a small header above the body as
        # context — not as file names. Rebuilt every iteration: after a
        # failed validation the validator's verdict is appended, so the model
        # repairs its own Gherkin against the exact complaint.
        # A first run (the target has no requirements directory) writes the
        # full-derivation prompt instead: there is no oracle to derive a
        # delta against, so the prompt carries the first-run marker and the
        # directive the template's first-run clause governs, the issue's
        # header and body riding below it where the trigger carries them.
        num = common.cw_state("issue-number") or common.cw_input_opt("issue-number") or ""
        title = common.cw_state("issue-title") or common.cw_input_opt("issue-title") or ""
        pf = common.state_file("issue-prompt.md")
        if first_run:
            text = (open(body, encoding="utf-8").read()
                    if os.path.exists(body) else "")
            with open(pf, "w", encoding="utf-8") as f:
                f.write(FIRST_RUN_PROMPT)
                if text.strip():
                    head = "GitHub issue"
                    if num:
                        head += f" #{num}"
                    if title:
                        head += f": {title}"
                    f.write("\n\n" + head + "\n\n" + text + "\n")
            return pf
        if not os.path.exists(body):
            return None
        text = open(body, encoding="utf-8").read()
        with open(pf, "w", encoding="utf-8") as f:
            head = "GitHub issue"
            if num:
                head += f" #{num}"
            if title:
                head += f": {title}"
            f.write(head + "\n\n" + text)
            verdict = common.state_file("extract-validation.txt")
            if os.path.exists(verdict):
                v = open(verdict, encoding="utf-8").read().strip()
                if v and v != "PASS":
                    f.write("\n\n## Your previous attempt failed validation\n"
                            "The official Gherkin parser rejected it with:\n"
                            f"```\n{v}\n```\n"
                            "Regenerate the file so every line parses — keep the same "
                            "scenarios, fix only the grammar the parser flagged.\n")
        return pf

    stages.run_generation_stage(
        stage="stage 4 requirements-extraction",
        template="requirements",
        allow=[req],
        context=existing_context(),
        prompt_file=build_prompt,
        post_ok=post_ok,
        # the extraction stage is the @-file slice of the context contract:
        # the project files ride the pi call as @-arguments and pi reads the
        # named files as context before answering (the other stages reference
        # their context by path — one invocation never mixes the slices)
        context_as_args=True,
        # the loop's completion point records the stage's outcome line and
        # completion marker (the report cross-checks them; a caller with
        # its own completion hook records its own lines instead)
        artifact="cw-extract",
    )


if __name__ == "__main__":
    main()
