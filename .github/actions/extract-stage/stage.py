#!/usr/bin/env python3
"""Stage 4+5 — requirement extraction + requirement check.

  pi (requirements.md prompt, issue body as the prompt, the project files as
  context) derives the delta requirements for the issue and writes them as
  Gherkin into the requirements dir, placed by topic — an existing topic file
  extended in place, a new file only for a topic no file yet covers; the guard
  (the one shared idiom) then verifies that ONLY the requirements dir changed
  — a leak reverts the offending files and the extraction re-runs. Changed
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


def existing_context() -> list[str]:
    """The project files the extraction's pi call reads — handed to pi as
    @-file arguments (pi reads the named files as context before answering):
    the Gherkin oracle, the arc42 markdown (the docs/ files — the top-level
    PLAN.md where a target has no doc dir), README.md, and the baseline diff
    (the issue's change set recorded by the baseline stage)."""
    ctx = stages.project_context()
    diff = common.state_file("baseline.diff")
    if os.path.exists(diff):
        ctx.append(diff)
    return ctx


def _revert(f: str, baseline: str) -> None:
    """Revert exactly one file, the guard's way: tracked at the baseline →
    restore its baseline content; a file the stage added → remove it from
    the tree (committed or not)."""
    p = os.path.join(common.repo(), f)
    if subprocess.run(["git", "cat-file", "-e", f"{baseline}:{f}"],
                      cwd=common.repo(), capture_output=True).returncode == 0:
        subprocess.run(["git", "checkout", baseline, "--", f], cwd=common.repo(), check=False)
    elif subprocess.run(["git", "ls-files", "--", f], cwd=common.repo(),
                        capture_output=True).stdout.strip():
        subprocess.run(["git", "rm", "-f", "--", f], cwd=common.repo(), check=False)
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
        existed = subprocess.run(["git", "cat-file", "-e", f"{baseline}:{f}"],
                                 cwd=common.repo(), capture_output=True).returncode == 0
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


def main() -> None:
    common.install_crash_diagnostics("stage 4 requirements-extraction")
    req = common.env_dir("REQUIREMENTS_DIR")
    body = common.state_file("issue-body.md")
    # A missing body and an empty body are the same case: no change is
    # described, so there are no delta requirements. The stage writes nothing
    # and stops cleanly — handing pi a blank issue would invite it to invent
    # requirements out of silence.
    if not os.path.exists(body) or not open(body, encoding="utf-8").read().strip():
        common.log("stage 4: issue body is empty — no delta requirements; the "
                   "stage writes nothing and stops cleanly")
        with open(common.state_file("stage-summary.txt"), "a", encoding="utf-8") as f:
            f.write("stage 4-5 requirement extraction: no delta requirements "
                    "(empty issue body)\n")
        return

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
        if not os.path.exists(body):
            return None
        text = open(body, encoding="utf-8").read()
        num = common.cw_state("issue-number") or common.cw_input_opt("issue-number") or ""
        title = common.cw_state("issue-title") or common.cw_input_opt("issue-title") or ""
        pf = common.state_file("issue-prompt.md")
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
    )


if __name__ == "__main__":
    main()
