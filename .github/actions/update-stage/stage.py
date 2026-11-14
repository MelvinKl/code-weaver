#!/usr/bin/env python3
"""The update stage — every requirement to its newest version (the
optional stage between the requirement-extraction and the planning
stages).

The stage sits in the pipeline after the requirement-extraction stage
and before the planning stage, as an inlined step in the `plan` job —
the documented dependency-upgrade idiom (inlined workflow text, not a
new component: no new job, the 15-stage / 9-job pipeline count and the
five pi-calling stage jobs unchanged; the step's pi call runs under
the plan job's documented job-timeout). It is optional — the
AUTO_UPDATE setting (the workflow's optional `auto-update` input: the
target's declared value, the `true` default where a consumer leaves
the input undeclared — the trigger records the resolved value as a
state file in its recorded run state, and every stage job's Read
trigger state step relays it into the job's env like the other
trigger-state keys) turns it off: off, the stage is a no-op — it logs
and exits without touching the workspace (the run's pipeline runs
without the stage, and the run's stages, pull request and final
status report are unchanged by the stage's absence — the documented
dependency-upgrade off-form); a run whose extraction stopped with the
`no-delta-stop` flag (already relayed to the plan job and checked by
the plan stage) gets the stage no-op'ing as well, so that run's
documented clean-stop outcome is undisturbed.

When it runs, the stage updates **every requirement in the oracle to
its newest version** — a scenario that no longer holds against the
project's current state is updated in place (the oracle is the single
source of truth — the documented in-place-update idiom), a
requirement already at its newest version — including the ones this
run's extraction just derived — is left untouched, so the update's
footprint never disturbs the run's delta the plan stage covers, and a
Gherkin requirement that prohibits a requirement from being updated
leaves that requirement at its current version (the prohibition is a
Gherkin requirement of the oracle; the requirements no Gherkin
requirement prohibits are updated to the newest version).

The stage runs its pi call through the documented shared plumbing —
the `pi-run` primitive, the per-call time cap resolved through the
documented chain (the `pi-timeout` input's value at the
`INPUT_PI_TIMEOUT` → `CW_PI_TIMEOUT` links, then the 21600 code
default), the usage ledger (each finished call appends its input and
output token counts), the stage-baseline recording (the plan job's
update step records it before the stage; the plan stage's baseline
recording re-records the branch tip after the stage, so the update's
footprint is never counted as the plan stage's work by the guard) and
the shared bounded generation loop whose completion points commit the
stage's work and push the AI branch — the push firing only after the
guard has passed — against the update prompt template under
`pi-prompts/`. The template's instructions carry the documented
two-slice context contract on its path-referenced side (the arc42 set
and the README referenced by path, the requirements directory named
as the oracle's location — pi reads the files it judges relevant on
demand, a directory never an `@`-argument).

The stage's guard runs the shared idiom with the requirements
directory as its lane — a change outside it is reverted in place by
the guard's pi call, the stage's own work stays valid, and a repair
that does not clear re-runs the stage bounded by the loop caps; a
changed feature file that no longer parses is a guard violation — the
documented extraction validation (the stage's post-check reverts the
offending file and re-runs the stage, carrying the parser's complaint
back into the next attempt). The stage records its outcome on the
stage-summary channel (a done stage reported "stage complete", the
report's stage-outcome list rendering from it).
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


def _auto_update_on() -> bool:
    """Whether the run's pipeline runs the update stage — the
    AUTO_UPDATE setting resolved through the documented chain
    (chapter 3's settings flow): the workflow's own binding
    `INPUT_AUTO_UPDATE` on a healthy runner, then
    `CW_AUTO_UPDATE` — the job-env entry the stage jobs relay from
    the trigger's recorded run state (the trigger records the
    resolved value as a state file beside its recorded state, and
    every stage job's Read trigger state step relays it into the
    job's env like the other trigger-state keys; the state file is
    the authoritative channel, the env the in-process half) — then
    the `true` code default at the chain's end: a consumer that
    leaves the input undeclared runs with the update stage, its run
    unchanged on the default. A value that is not an on value
    (off/false/no/0, case-insensitive) turns the stage off — the
    documented dependency-upgrade off-form."""
    v = (common.cw_input_opt("auto-update") or "true")
    return v.strip().lower() not in ("", "off", "false", "no", "0")


def _extraction_stopped_no_delta() -> bool:
    """Whether the run's requirement extraction stopped with no
    delta — the run-level stop signal the extract stage records in
    the run's state dir when it takes the no-delta stop (a
    bug-labelled issue with an empty body, or the standing
    empty-body stop): a state file beside the trigger's recorded
    state (`no-delta-stop`) — the state file rides the cumulative
    artefact chain to every later stage job, the per-job env relay
    (CW_NO_DELTA_STOP) is the in-process channel, like the other
    trigger-state keys. The plan stage checks the same flag before
    its own work and stops cleanly; where the flag is set the update
    stage no-ops too — the run that stopped at the extraction is not
    forwarded to the update stage, so that run's documented
    clean-stop outcome is undisturbed."""
    v = (common.cw_state("no-delta-stop")
         or common.cw_input_opt("no-delta-stop") or "")
    return v.strip().lower() == "true"


def update_context() -> list[str]:
    """The path-referenced slice of the documented two-slice context
    contract — the arc42 markdown under the doc dir (the top-level
    PLAN.md where a target has no doc dir) and the README,
    referenced by path: their contents are never embedded in the
    prompt, pi reads the ones the task needs on demand with its read
    tool, and the invocation's token overhead stays small. The
    Gherkin oracle is NOT one of these entries: the call's
    instructions name its directory as the oracle's location (the
    prompt file below), and pi reads the files it judges relevant
    from it on demand — a directory is never an @-argument (its
    handling reads files, so one there would crash pi with EISDIR)."""
    doc = common.env_dir("DOC_DIR")
    ctx = stages.dir_files(doc, at_prefix=False)
    if os.path.isfile("README.md"):
        ctx.append("README.md")
    # A target without a doc dir documents itself in its top-level
    # planning markdown — reference PLAN.md so the context still
    # carries the arc42 set (the same fallback the other context
    # builders share).
    if not ctx and os.path.isfile("PLAN.md"):
        ctx.append("PLAN.md")
    return ctx


def build_prompt() -> str:
    """The prompt file the update call rides — rebuilt every
    iteration: it names the oracle's location (the configured
    requirements directory — the instructions' directory reach, the
    half of the two-slice context contract the oracle takes), and
    after a failed validation the parser's verdict is appended, so
    the model repairs the file it broke against the exact
    complaint."""
    req = common.env_dir("REQUIREMENTS_DIR") or "requirements"
    pf = common.state_file("update-prompt.md")
    with open(pf, "w", encoding="utf-8") as f:
        f.write("# The oracle's location\n\n")
        f.write(f"The Gherkin oracle is the directory `{req}`. It is "
                "named, not handed: read from it the files you judge "
                "relevant with your read tool — a directory is never "
                "an @-argument.\n")
        verdict = common.state_file("update-validation.txt")
        if os.path.exists(verdict):
            v = open(verdict, encoding="utf-8").read().strip()
            if v and v != "PASS":
                f.write("\n## Your previous attempt failed validation\n")
                f.write("The official Gherkin parser rejected it with:\n")
                f.write(f"```\n{v}\n```\n")
                f.write("Regenerate the file so every line parses — keep "
                        "the same scenarios, fix only the grammar the "
                        "parser flagged.\n")
    return pf


def _revert(f: str, baseline: str) -> None:
    """Revert exactly one file, the guard's way: tracked at the
    baseline → restore its baseline content; a file the stage added →
    remove it from the tree (committed or not)."""
    p = os.path.join(common.repo(), f)
    if common.git_exec(["cat-file", "-e", f"{baseline}:{f}"],
                       cwd=common.repo(),
                       capture_output=True).returncode == 0:
        common.git_exec(["checkout", baseline, "--", f],
                        cwd=common.repo(), check=False)
    elif common.git_exec(["ls-files", "--", f], cwd=common.repo(),
                         capture_output=True).stdout.strip():
        common.git_exec(["rm", "-f", "--", f], cwd=common.repo(),
                        check=False)
    elif os.path.exists(p):
        os.remove(p)


def post_ok() -> bool:
    """The documented extraction validation, run as the update
    stage's loop post-check: every changed `.feature` file must parse
    with Cucumber's official Gherkin parser (a requirement must be
    executable) — a changed feature file that no longer parses is a
    guard violation: it is reverted to its baseline content and the
    stage re-runs, the parser's complaint persisted to the state dir
    so the next attempt's prompt carries it and the model repairs
    against the exact error. A changed file that still parses is the
    update's work — admitted, never reverted (the guard keeps the
    change set inside the requirements dir; inside it, an in-place
    update is the update stage's lane)."""
    baseline = stages.baseline_sha()
    req = common.env_dir("REQUIREMENTS_DIR").rstrip("/")
    validator = os.path.join(stages.repo_root(), ".github", "scripts",
                             "gherkin-validate.py")
    verdict = common.state_file("update-validation.txt")

    complaints: list[str] = []
    revert: list[str] = []
    parse_batch: list[str] = []
    for f in common.changed_files(baseline):
        if not (stages.under(f, req) and f.endswith(".feature")):
            continue
        if os.path.exists(os.path.join(common.repo(), f)):
            parse_batch.append(f)
        else:
            # The update updates requirements in place — it does not
            # delete a topic's home: restore a changed file that is
            # missing from the worktree.
            complaints.append(
                f"a feature file changed against the baseline is missing "
                f"from the worktree — the update updates in place, it "
                f"does not delete: restored: {f}")
            revert.append(f)

    if parse_batch:
        r = subprocess.run([sys.executable, validator, *parse_batch],
                           capture_output=True, text=True)
        if r.returncode != 0:
            for line in r.stderr.splitlines():
                if line.startswith("FAIL "):
                    name = line[len("FAIL "):].split(":", 1)[0].strip()
                    complaints.append(
                        f"the official Gherkin parser rejected {name}")
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
        common.log(f"update stage: {len(parse_batch)} changed feature "
                   f"file(s) parse with the official Gherkin parser; "
                   f"the update's work is validated")
        return True

    with open(verdict, "w", encoding="utf-8") as f:
        f.write("\n".join(complaints))
        if parser_verdict:
            f.write("\n" + parser_verdict)
    revert = list(dict.fromkeys(revert))
    common.log(f"::error::update stage: {'; '.join(complaints)} → "
               f"reverted: {' '.join(revert) or '(none)'}")
    for f in revert:
        _revert(f, baseline)
    common.commit_all("requirements: invalid update reverted "
                      "(re-running the update stage)")
    return False


def run_update_stage() -> None:
    """The stage's work: one generation call through the documented
    shared bounded loop — generate → commit → guard (the requirements
    directory as the lane) → post-check (the extraction validation) —
    bounded by the loop caps, whose completion points commit the
    stage's work and push the AI branch (the push fires only after
    the guard has passed; a run terminated after the push keeps the
    stage's completed work on the remote branch). `artifact` stays
    empty on purpose: the update stage is an inlined step in the plan
    job, not a job of its own — the plan job's completion marker is
    the plan stage's, and a run whose update completed but plan
    failed must not carry it; the stage's evidence is the outcome
    line the loop records on the stage-summary channel (the report's
    stage-outcome list renders from it)."""
    req = common.env_dir("REQUIREMENTS_DIR")
    stages.run_generation_stage(
        stage="update stage",
        template="update",
        allow=[req],
        context=update_context(),
        prompt_file=build_prompt,
        post_ok=post_ok,
    )


def main() -> None:
    common.install_crash_diagnostics("update stage")
    # the run's resolved extension env applied to this stage's process
    # environment at entry (the artefact-channel half of the relay that
    # keeps the every-step contract whole on a runner build whose
    # GITHUB_ENV write ghosts): every CLI the stage then spawns — its pi
    # invocations, its git children — inherits the provider's values
    common.apply_extension_env()
    # The setting's gate: the AUTO_UPDATE setting resolved through the
    # documented chain (chapter 3). Off — the documented
    # dependency-upgrade off-form: the stage is a no-op (it logs and
    # exits without touching the workspace): the run's pipeline runs
    # without the update stage, and the run's stages, pull request and
    # final status report are unchanged by the stage's absence.
    if not _auto_update_on():
        common.log("update stage: the AUTO_UPDATE setting is off — "
                   "the run's pipeline runs without the update stage "
                   "(the run's stages, pull request and final status "
                   "report are unchanged by the stage's absence)")
        return
    # The run's no-delta-stop flag: a run whose extraction stopped with
    # no delta (the extract stage records it in the run's state dir) is
    # not forwarded to the update stage — the stage no-ops, so that
    # run's documented clean-stop outcome is undisturbed (the plan
    # stage checks the same flag and stops).
    if _extraction_stopped_no_delta():
        common.log("update stage: the run's requirement extraction "
                   "stopped with no delta (the no-delta-stop flag) — "
                   "the run is not forwarded to the update stage; the "
                   "stage no-ops")
        common.record_stage_outcome(
            "update stage: skipped (the run's requirement extraction "
            "stopped with no delta — the run is not forwarded to the "
            "update stage)")
        return
    run_update_stage()


if __name__ == "__main__":
    main()
