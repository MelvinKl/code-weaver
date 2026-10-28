# 8. Deployment View

**Consume it by ref.** The target repo carries the short consumer
workflow (chapter 4). It pins the factory by **owner, repo, path and a
version tag** — `uses:
MelvinKl/code-weaver/.github/workflows/factory.yml@5`. The oracle
pins that owner and a version tag: a moving branch ref (`@main`) is not a
stable ref, so both the deployed consumer workflow and the README's
consumption example declare the same owner and the same tag (the
trigger-contract tests keep the two surfaces in lock-step on the
`labeled`-only trigger). Its `secrets:` block carries `GH_TOKEN` (the only
required one) plus the four optional harness-provider secrets
(`PI_MODELS`, `PI_SETTINGS`, `PI_MCP`, `PI_EXTENSION_ENV`) — a provider
value never appears in a `with:` input or a committed file.

**Upgrades are a ref bump.** `release.yml` fires on the main branch's
advance: from the advance's head it cuts a throwaway release branch,
rewrites the reusable workflow's own action references to the next single
increasing number it is about to tag, commits the rewrite, tags that
commit and publishes only the tag as a GitHub release without any
maintainer action (a push to main would re-trigger the release workflow —
the tag is the only ref it publishes). The versions the flow publishes
from this change on are self-consistent — the workflow at a ref
references its composite actions at that same ref, so a target's ref bump
selects the workflow and its actions as one version — and the tags cut
before the change keep their relative refs, still stable pinnable refs for
targets whose tree carries a copy of the actions; tags are immutable, so
targets pinned to an older ref keep working, and bumping the ref is the
only change a target ever makes.

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
