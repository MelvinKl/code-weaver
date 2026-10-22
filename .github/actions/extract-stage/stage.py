#!/usr/bin/env python3
"""Stage 4+5 — requirement extraction + requirement check.

  pi (requirements.md prompt, issue body as the prompt, the project files as
  context) derives the delta requirements for the issue and writes them as
  Gherkin into the requirements dir; the guard (the one shared idiom) then
  verifies that ONLY the requirements dir changed — a leak reverts the
  offending files and the extraction re-runs. Generated features must parse
  with Cucumber's official Gherkin parser (a requirement must be executable:
  the test-and-review stage runs every scenario).
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
    return stages.project_context()


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
    """The Gherkin-oracle half of stage 5: every generated .feature must
    parse with the official parser, and the delta's shape is pinned — at most
    ONE new file, named after the issue; existing requirement files stay
    byte-identical (scenario: \"Extraction writes one new file named after
    the issue\"). A violation is reverted and its verdict persisted, so the
    next iteration's prompt carries it and the model repairs against the
    exact complaint instead of regenerating blind."""
    baseline = stages.baseline_sha()
    req = common.env_dir("REQUIREMENTS_DIR").rstrip("/")
    validator = os.path.join(stages.repo_root(), ".github", "scripts", "gherkin-validate.py")
    verdict = common.state_file("extract-validation.txt")

    complaints: list[str] = []
    revert: list[str] = []
    changed = common.changed_files(baseline)

    # Delta shape: the guard keeps changes inside the requirements dir; the
    # stage pins what is allowed inside it.
    num = common.cw_state("issue-number") or common.cw_input_opt("issue-number") or ""
    new: list[str] = []
    for f in changed:
        if not stages.under(f, req):
            continue  # the guard's territory
        existed = subprocess.run(["git", "cat-file", "-e", f"{baseline}:{f}"],
                                 cwd=common.repo(), capture_output=True).returncode == 0
        if existed:
            complaints.append(f"an existing requirement file must not change: {f}")
            revert.append(f)
        else:
            new.append(f)
    if len(new) > 1:
        complaints.append(f"at most one new file is allowed — found {len(new)}: "
                          + ", ".join(new))
        revert += new
    elif len(new) == 1 and num and str(num) not in os.path.basename(new[0]):
        complaints.append(f"the one new file must be named after the issue — expected "
                          f"a name containing #{num}, got '{os.path.basename(new[0])}'")
        revert.append(new[0])

    # Parse oracle: every generated .feature must parse with the official
    # Cucumber Gherkin parser (a requirement must be executable).
    files = [f for f in changed if f.endswith(".feature") and stages.under(f, req)]
    if files:
        r = subprocess.run([sys.executable, validator, *files],
                           capture_output=True, text=True)
        if r.returncode != 0:
            for line in r.stderr.splitlines():
                if line.startswith("FAIL "):
                    name = line[len("FAIL "):].split(":", 1)[0].strip()
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
        common.log(f"stage 5: {len(files)} feature file(s) parse with the official "
                   f"Gherkin parser; delta shape clean ({len(new)} new file(s))")
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
        # The model names its output file after the issue — the number and
        # title ride a small header above the body, so the file name it
        # chooses is deterministic for the issue (idempotent re-runs).
        # Rebuilt every iteration: after a failed validation the parser's
        # verdict is appended, so the model repairs its own Gherkin.
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
    )


if __name__ == "__main__":
    main()
