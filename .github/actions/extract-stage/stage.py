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


def post_ok() -> bool:
    """The Gherkin-oracle half of stage 5: every generated .feature must
    parse; an invalid file is reverted and the loop continues."""
    baseline = stages.baseline_sha()
    req = common.env_dir("REQUIREMENTS_DIR").rstrip("/")
    validator = os.path.join(stages.repo_root(), ".github", "scripts", "gherkin-validate.py")
    files = [f for f in common.changed_files(baseline) if f.endswith(".feature") and stages.under(f, req)]
    if not files:
        return True  # nothing generated — valid vacuously (empty-body case)
    r = subprocess.run([sys.executable, validator, *files], capture_output=True, text=True)
    verdict = common.state_file("extract-validation.txt")
    if r.returncode == 0:
        with open(verdict, "w", encoding="utf-8") as f:
            f.write("PASS")
        common.log(f"stage 5: {len(files)} feature file(s) parse with the official Gherkin parser")
        return True
    # The parser's verdict is persisted: the next loop iteration's prompt
    # carries it, so the model repairs its own Gherkin against the exact
    # complaint instead of regenerating blind.
    with open(verdict, "w", encoding="utf-8") as f:
        f.write(r.stderr.strip() or "the official Gherkin parser rejected the file")
    bad: list[str] = []
    for line in r.stderr.splitlines():
        if line.startswith("FAIL "):
            bad.append(line[len("FAIL "):].split(":", 1)[0].strip())
    bad = list(dict.fromkeys(bad)) or files
    common.log(f"::error::stage 5: invalid Gherkin → reverted: {' '.join(bad)}")
    subprocess.run(["git", "checkout", baseline, "--"] + [b for b in bad if os.path.exists(b)],
                   cwd=common.repo(), check=False)
    subprocess.run(["git", "clean", "-fdq"] + [os.path.dirname(b) or "." for b in bad],
                   cwd=common.repo())
    common.commit_all("requirements: invalid Gherkin reverted (re-extracting)")
    return False


def main() -> None:
    req = common.env_dir("REQUIREMENTS_DIR")
    body = common.state_file("issue-body.md")

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
