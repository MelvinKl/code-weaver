# 3. Constraints

- **No pre-installed or pre-configured pi is a pre-requisite of the runner
  environment.** The factory's setup stage (stage 2) installs pi for the
  run and configures it for the workflow run from the run's provided
  harness — all set by env vars: each element's provider is the run's
  environment variables, the GitHub secret the consumer workflow's secrets
  block carries (a named repo file is no longer a provider of any harness
  element), written into the agent directory the run's pi invocations
  resolve — and fails with an explicit message where it cannot install or
  configure (a run whose environment provides no model configuration
  fails the stage clearly: the run's pi configuration is incomplete). The
  `gh` CLI is a runner pre-requisite (trigger / pr-open / gates shell out
  to it), as is a runner user that owns `~/.config`. The only adjustable
  LLM setting is which configured model the run uses; the backend is
  provided for the run via the models-configuration GitHub secret (the
  run's environment variables — a named repo file is no longer a provider
  of any harness element), not a property of the runner.
- **Secrets are never plain inputs.** `GH_TOKEN` (repo-scoped, with
  `issues:write` + `pull-requests:write` + `contents:write`) rides the
  reusable workflow's `secrets:` block only; no secret value ever appears
  in `with:` inputs or committed files — the four optional harness
  providers (`PI_MODELS`, `PI_SETTINGS`, `PI_MCP`, `EXTENSION_ENV`)
  ride the same block. The optional `dependency-install` input rides the
  `with:` block rather than this one — an install command is project
  configuration, not a secret value, so the input channel is the
  consistent one, and the value is deliberately not a fifth harness
  element (the setup stage's four provider elements stay the pi harness,
  not the project's working environment). The run executes the declared
  command in the jobs whose stages consume it — after each job's checkout
  and before its stage — and a target that leaves it undeclared runs
  unchanged: the step is a no-op, and the run is unchanged by the
  mechanism's presence.
- **The requirements are read-only.** No stage may edit a file under the
  requirements dir: the guard repairs such edits in place with a pi call —
  the changed file named and reverted, the stage's own work told to stay
  valid — instead of reverting them by git; a requirement edit during
  implementation does not loop the run back to the plan stage (the same
  repair call confirms the implementation's work based on the plan is still
  valid).
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
