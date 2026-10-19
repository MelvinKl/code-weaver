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

action_dir = os.environ.get("GITHUB_ACTION_PATH", ".")
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
    if r.returncode == 0:
        common.log(f"stage 5: {len(files)} feature file(s) parse with the official Gherkin parser")
        return True
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
    stages.run_generation_stage(
        stage="stage 4 requirements-extraction",
        template="requirements",
        allow=[req],
        context=existing_context(),
        prompt_file=common.state_file("issue-body.md")
        if os.path.exists(common.state_file("issue-body.md")) else None,
        post_ok=post_ok,
    )


if __name__ == "__main__":
    main()
