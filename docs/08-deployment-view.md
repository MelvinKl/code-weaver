# 8. Deployment View

**Consume it by ref.** The target repo carries the short consumer
workflow (chapter 4). An external target pins the factory by **owner,
repo, path and a version tag** — `uses:
MelvinKl/code-weaver/.github/workflows/factory.yml@<version tag>` — and
that is the only pin: the ref selects the published version, so no
relayed ref accompanies it. The oracle pins the owner
and a version tag: a moving branch ref (`@main`) is not a stable ref, so
both the deployed consumer workflow and the README's consumption example
declare the same owner and the same tag (the
trigger-contract tests keep the two surfaces in lock-step on the
`labeled`-only trigger). **This repo is the factory project itself — and
its workflow uses the same shape as its external targets**: it pins the
public release line (a version tag of the MelvinKl line) with the
(legacy) `factory-ref` input left undeclared, so the dogfood exercises
exactly the published version the external targets get — a broken
release breaks the dogfood visibly — while a run triggered in it still
checks out and works the code of the repo it was triggered in: the pin
selects the machinery (the file and its runtime tree as one published
version), never the code — each stage job materialises the runtime tree
of the pinned version (the tagged version's tree, kept consistent with
the file by the release flow's publication gate) and runs its stage
steps from that copy, and no stage clones the factory repo at a second
ref (the first job fetches the called version's tree from the factory
repo at the ref that selected the file — the consumer's `uses:` line
stays the only pin). Its `secrets:` block carries
`GH_TOKEN` (the only required one) plus the four optional
harness-provider secrets (`PI_MODELS`, `PI_SETTINGS`, `PI_MCP`,
`PI_EXTENSION_ENV`) — a provider value never appears in a `with:` input
or a committed file. The `with:` block may also declare the optional
`dependency-install` input — the command the run's pipeline runs to
install the target project's dependencies: project configuration, not a
secret value (the chapter-3 constraint holds on the input channel), and
not a fifth harness element — the harness table below stays the setup
stage's four provider elements, the pi harness, while the
dependency-install step targets the project's working environment. The
run executes the declared command in the jobs whose stages consume it,
after each job's checkout and before its stage; a target that leaves the
input undeclared runs unchanged — the step is a no-op, and the run is
unchanged by the mechanism's presence. The `with:` block may also
declare the optional `dependency-upgrade` setting — whether the run's
pipeline runs the dependency-upgrade stage: the stage upgrades the
project's dependencies to newer versions, before the implementation
stage. Project configuration, not a secret value (the chapter-3
constraint holds on the input channel), and not a fifth harness
element. The setting's default is `on`; a target turns the stage off
through its consumer workflow (a `dependency-upgrade: off` line in the
`with:` block, like `max-loops`). Where the setting is off, the
pipeline runs without the stage, and the run is unchanged: the run's
stages, pull request and final status report are unchanged by the
upgrade's absence.

**Upgrades are a ref bump.** `release.yml` fires on the main branch's
advance: it tags the advance's head with the next single increasing
number and publishes that tag as a GitHub release without any maintainer
action (a push to main would re-trigger the release workflow — the tag is
the only ref it publishes). The tag points at a commit that is already on
the remote, so the push uploads only the tag object — no new commit
content — and the default GITHUB_TOKEN publishes it: no special token, no
secret. A re-run of the flow at an unchanged HEAD publishes nothing —
one tag per commit, the number series advancing only when main does (the
helper's guard), so a number is never spent on a duplicate version. A
push whose changed files are confined to the consumer workflow publishes
no release (no tag, no release, no number spent — the version it would
have carried is unchanged: a version is the factory workflow and its
runtime tree as one published version, never the consumer's own
workflow file). The published file is plain text within the max
allowed size for it — at most 500kb; a version whose file exceeds the
cap is not consistent. The workflow at a ref is self-contained — its
stage steps are inlined in the file, which stores no binary content —
and the tagged commit carries the tree the file's stage steps execute
(stage 1 fetches the called version's runtime tree at the called ref
into $RUNNER_TEMP before the first checkout; the trigger's artifact
carries it to every later stage job's first step — that upload opts
into hidden files, the tree sitting under the hidden .github/ directory
the artifact API would otherwise drop); the release flow's publication
gate keeps the two consistent, failing a publish that is not —
including a file past 500kb — so a target's ref bump selects the whole
version at once (the workflow file and the tree its steps execute are
one version: the ref's published version carries the two together);
tags are
immutable, so targets pinned to an older ref keep working, and bumping
the ref is the only change a target ever makes. A release's notes name
the changes since the predecessor release (first commit only where
there is no predecessor; never empty for a release that publishes
changes). The factory project's
own repo keeps the same pattern: its dogfood pins the public release
line, and the ref bump is the upgrade of the machinery a run works with
— while a run triggered in it still checks and works the triggered
repo's own code. Stage 15 keeps those
pinned targets working with its own dual-path plumbing (chapter 6):
where the pinned ref's runtime tree resolves no shared module (a ref
that predates the module, or the legacy workspace-copy tree), the report
step's `import common` fails and its `ImportError` branch runs the body
on the local fallback definitions; on a healthy runner where the
stashed tree resolves the module, the same names bind to the shared
module's definitions instead. The two paths are behaviourally
equivalent for the report's output — one ledger, one set of numbers on
both the PR body and the issue comment — so a pinned target's report is
complete, not degraded.

**The runner environment.** No pre-installed or pre-configured pi is a
pre-requisite of a runner labelled for the factory — the setup stage
installs pi for the run and configures it for the workflow run from the
run's provided harness. The surviving runner pre-requisites are the `gh`
CLI and a runner user that owns `~/.config` (a root-owned one makes every
token-bearing `gh` call die with permission-denied).

**The harness providers.** The run's pi harness is provided per run; each
element resolves to a GitHub secret in the consumer workflow's `secrets:`
block winning over the named repo file, and an element without a provider
is cleared from the agent directory — the runner's pre-existing
user-level configuration is replaced for the run, never what the
invocation resolves:

| element | GitHub secret | repo file |
|---|---|---|
| the model configuration — the run's LLM backend (e.g. the keyless internal swap) is defined in it, and the `llm-model` input selects from its model set | `PI_MODELS` | `.pi/agent/models.json` |
| the additional-packages settings — an empty or absent settings provider leaves pi without additional packages | `PI_SETTINGS` | `.pi/settings.json` |
| the MCP configuration — an absent provider means the run's pi runs without MCP servers | `PI_MCP` | `.pi/mcp.json` |
| the extension's environment variables — a `.env`-style secret, such as the ones `.pi/extensions/pi-jev-config.ts` carries | `PI_EXTENSION_ENV` | — (the secret is the provider) |

The stage writes each resolved element into the agent directory the run's
pi invocations resolve (`~/.pi/agent/`, honouring `PI_CODING_AGENT_DIR`):
`models.json`, `settings.json`, `mcp.json`, and the extension's
environment materialised as a user-level extension in the agent
directory's `extensions/`. The repo's `.pi/` files are the repo-file half
of the providers — a target that commits them steers the run's harness
without any secret. The checks the stage then runs read only what it
wrote: a provided model configuration that carries no OpenAI-compatible
backend URL is not a usable configuration (the stage fails "no backend in
the provided configuration" — it never falls back to the runner's
user-level configuration), the backend must answer its reachability
probe, the selected model must be listed in the written model set, and
the headless smoke check runs the installed pi.

**House CI.** This repo's own gate (`house-ci.yml`, ubuntu-latest,
uv-managed python) mirrors the shape a target's pull requests run against
the factory's PR: every python script compiles, every workflow/action YAML
parses, the Gherkin oracle validates with Cucumber's official parser, and
the validator's unit tests pass (`pytest tests/` where pytest exists —
the same files also run under the stdlib-only runner).
