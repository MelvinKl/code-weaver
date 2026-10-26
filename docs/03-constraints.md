# 3. Constraints

- **The runner environment is a pre-requisite.** `pi` is pre-installed and
  pre-configured (LLM backend included) on the runner; the factory's
  stage 2 only *verifies* and fails with an explicit message — it never
  installs or re-configures pi. The only adjustable LLM setting is which
  configured model the run uses. The `gh` CLI is the second pre-requisite
  (trigger / pr-open / gates shell out to it).
- **Secrets are never plain inputs.** `GH_TOKEN` (repo-scoped, with
  `issues:write` + `pull-requests:write` + `contents:write`) rides the
  reusable workflow's `secrets:` block only; no secret value ever appears
  in `with:` inputs or committed files.
- **The requirements are read-only.** No stage may edit a file under the
  requirements dir: the guard reverts such edits (and, during
  implementation, loops the run back to the plan stage).
- **Work happens only on the AI branch** `ai/code-weaver/<issue_number>`;
  the target branch is never modified by the factory.
- **The test suite is stdlib-only.** The suite runner is a plain-python
  script driven through the repo's `make test` target — a runner's system
  interpreter may be externally-managed with no pytest and no
  venv/ensurepip to install one. The Gherkin-parser port is the same:
  where it is absent the oracle check is **skipped, not failed**.
- **YAML 1.1 gotcha.** `yaml.safe_load` reads a workflow's `on:` key as
  the boolean `True`, so whole-document YAML parsing is the wrong tool
  for a workflow's event map; the trigger-contract tests parse the
  `types:` line line-based with stdlib only.
- **Composite-action input binding is unreliable on this runner build.**
  A composite action's `with:` values are not materialised as `INPUT_*`
  for its inner steps (and job-level `GITHUB_ENV` entries are not always
  seen by later steps' expressions on that build) — so stage jobs also
  pass each stage value as `CW_<name>` in the job/step `env:`, and the
  stage code resolves `INPUT_<name>` → `CW_<name>` → the trigger
  artifact's state files. The `with:` blocks stay declared for
  portability to a healthy runner.
