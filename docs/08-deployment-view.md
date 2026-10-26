# 8. Deployment View

**Consume it by ref.** The target repo carries the short consumer
workflow (chapter 4). It pins the factory by **owner, repo, path and a
version tag** — `uses:
MelvinKl/code-weaver/.github/workflows/factory.yml@v0.1.0`. The oracle
pins that owner and a version tag: a moving branch ref (`@main`) is not a
stable ref, so both the deployed consumer workflow and the README's
consumption example declare the same owner and the same tag (the
trigger-contract tests keep the two surfaces in lock-step on the
`labeled`-only trigger).

**Upgrades are a ref bump.** `release.yml` turns a `vX.Y.Z` tag into a
GitHub release; tags are immutable, so targets pinned to an older ref keep
working, and bumping the ref is the only change a target ever makes.

**The runner environment.** A runner labelled for the factory must have,
ahead of time: `pi` installed and configured (its LLM backend — e.g. the
keyless internal swap — plus the model set the `llm-model` input selects
from), the `gh` CLI, and a runner user that owns `~/.config` (a
root-owned one makes every token-bearing `gh` call die with
permission-denied). The repo ships `.pi/` as documentation of the
factory's model configuration: `mcp.json` is an MCP server registry
(without a backend URL) and `agent/models.json` the model reference —
stage 2 scans every `.pi` candidate (repo-local first, then the runner's
user config, both layouts) and uses the first file that actually yields an
OpenAI-compatible backend URL; a registry file without one is skipped,
never treated as the configuration. At runtime the runner's user-level pi
configuration is what the invocation resolves; the repo-local file is a
reference, never an override.

**House CI.** This repo's own gate (`house-ci.yml`, ubuntu-latest,
uv-managed python) mirrors the shape a target's pull requests run against
the factory's PR: every python script compiles, every workflow/action YAML
parses, the Gherkin oracle validates with Cucumber's official parser, and
the validator's unit tests pass (`pytest tests/` where pytest exists —
the same files also run under the stdlib-only runner).
