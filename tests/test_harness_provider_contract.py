"""Unit tests pinning the pi-harness provider surface (issue #23, task 1).

The setup stage stops treating pi as a pre-requisite of the runner
environment: it installs pi for the run and materialises the run's
provided harness, and the harness providers ride the reusable workflow's
`secrets:` block (configuration "The pi harness secrets ride the reusable
workflow's secrets block"; safety "Secrets are never plain inputs"):

- the factory declares the four providers — PI_MODELS (the model
  configuration), PI_SETTINGS (the additional packages), PI_MCP (the MCP
  configuration), PI_EXTENSION_ENV (the extension's .env-style
  environment variables) — as optional entries of its workflow_call
  `secrets:` block; GH_TOKEN stays the only `required: true` one;
- the setup-pi job delivers them to the setup-pi action through the
  factory's documented `with:` + `CW_<name>` env relay idiom (an empty
  secret value arrives empty and the stage treats it as an absent
  provider);
- no provider value appears in a `with:` input of the factory or in any
  committed file — a secret name may be referenced (as a `secrets.`
  expression, a secrets-block entry or a `CW_`/`INPUT_` env var), its
  content may not be committed.

Plain-stdlib by design (no third-party imports): no-argument `test_`
functions are auto-discovered by both runners (`tests/run.py` imports
every `tests/test_*.py`; house CI's "Validator unit tests" step runs
`pytest tests/`), so no `Makefile`, `tests/run.py` or
`.github/workflows/house-ci.yml` change is needed.
"""
from __future__ import annotations

import os
import re

ROOT = os.path.join(os.path.dirname(__file__), "..")

FACTORY = ".github/workflows/factory.yml"

# the four harness providers, in the order the stage materialises them
# (the workflow's secret name → the with: input the setup-pi action takes
# it on)
PROVIDERS = (
    ("PI_MODELS", "pi-models"),
    ("PI_SETTINGS", "pi-settings"),
    ("PI_MCP", "pi-mcp"),
    ("PI_EXTENSION_ENV", "pi-extension-env"),
)


def _read(relpath):
    with open(os.path.join(ROOT, relpath), encoding="utf-8") as f:
        return f.read()


def _workflow_call_secrets_block(factory: str) -> str:
    """The reusable workflow's `secrets:` block — the 4-indent `secrets:`
    key under `on.workflow_call`, entries at 6 indent, properties at 8 —
    sliced line-based (the whole-document yaml parse this repo's contract
    tests deliberately avoid is not needed to read one block)."""
    lines = factory.splitlines()
    starts = [i for i, ln in enumerate(lines) if ln == "    secrets:"]
    assert len(starts) == 1, \
        f"expected exactly one workflow_call secrets: block, found {len(starts)}"
    block = []
    for ln in lines[starts[0] + 1:]:
        if ln.strip():
            indent = len(ln) - len(ln.lstrip(" "))
            if indent < 6:
                break
        block.append(ln)
    return "\n".join(block)


def _secrets_entry(block: str, name: str) -> str:
    """One entry of the secrets block: from its 6-indent key line to the
    next 6-indent (or shallower) line."""
    lines = block.splitlines()
    for i, ln in enumerate(lines):
        if ln.strip() == f"{name}:":
            entry = [ln]
            for cont in lines[i + 1:]:
                if cont.strip():
                    indent = len(cont) - len(cont.lstrip(" "))
                    if indent <= 6:
                        break
                entry.append(cont)
            return "\n".join(entry)
    raise AssertionError(f"no {name} entry in the factory's secrets block")


def test_factory_declares_the_providers_as_optional_secrets():
    """(configuration "The pi harness secrets ride the reusable workflow's
    secrets block") the factory's workflow_call secrets: block carries the
    four provider entries — each declared `required: false` (an unset
    provider arrives empty and the setup stage treats it as an absent
    provider, the repo file is the fallback) — and GH_TOKEN is the only
    entry marked `required: true`."""
    block = _workflow_call_secrets_block(_read(FACTORY))
    for name, _input_name in PROVIDERS:
        entry = _secrets_entry(block, name)
        assert "required: true" not in entry, \
            f"{name} must be an optional secret — GH_TOKEN is the only required one"
        assert "required: false" in entry, \
            f"{name} must be declared optional in the factory's secrets block"
    assert "required: true" in _secrets_entry(block, "GH_TOKEN"), \
        "GH_TOKEN stays the factory's only required secret"
    assert block.count("required: true") == 1, \
        "GH_TOKEN is the only required: true entry of the factory's secrets block"


def _setup_pi_job(factory: str) -> str:
    """The setup-pi job's region: from its 2-indent job key to the next
    2-indent job key (stage 3's baseline job)."""
    start = factory.index("  setup-pi:")
    end = factory.index("  baseline:", start)
    return factory[start:end]


def test_setup_pi_job_passes_the_providers_to_the_action():
    """(configuration "The pi harness secrets ride the reusable workflow's
    secrets block") the setup-pi job delivers the four providers to the
    setup-pi action through both channels of the factory's documented relay
    idiom — the step's `with:` entries (bound to INPUT_* on a healthy
    runner) and the `CW_<name>` env (job-level for the stage code, and
    step-level, where it reaches the action's inner steps on this runner
    build) — and the action declares the matching inputs."""
    job = _setup_pi_job(_read(FACTORY))
    action = _read(".github/actions/setup-pi/action.yml")
    assert "uses: ./.github/actions/setup-pi/" in job, \
        "the setup-pi job lost its setup-pi action step"
    for name, input_name in PROVIDERS:
        assert f"          {input_name}: ${{{{ secrets.{name} }}}}" in job, \
            f"the setup-pi job's with: must pass {name} to the setup-pi action"
        assert f"      CW_{name}: ${{{{ secrets.{name} }}}}" in job, \
            f"the job's env must carry CW_{name} from the secret"
        assert f"          CW_{name}: ${{{{ inputs.{input_name} }}}}" in job, \
            f"the action step's env must relay CW_{name} to the inner steps"
        assert f"  {input_name}:" in action, \
            f"the setup-pi action must declare the {input_name} input the factory passes"


def test_no_provider_value_in_with_inputs_or_committed_files():
    """(configuration "The pi harness secrets ride the reusable workflow's
    secrets block" — "no harness secret value appears in with inputs or
    committed files"; safety "Secrets are never plain inputs") a provider
    secret name may be referenced — as a `secrets.` expression, a
    secrets-block entry or a `CW_`/`INPUT_` env var — but its content may
    not be committed: in the factory every occurrence of a provider name is
    exactly that (never a with: value), and no committed file outside the
    consumer workflow surfaces carries a provider's `secrets.` mapping
    (the tests/ dir is the checker, not a surface; .git is not the tree)."""
    factory = _read(FACTORY)
    for i, ln in enumerate(factory.splitlines(), 1):
        for name, _input_name in PROVIDERS:
            if not re.search(rf"\b{name}\b", ln):
                continue
            is_entry = ln.strip() == name + ":" or ln.strip().startswith(name + ": ")
            is_ref = f"secrets.{name}" in ln
            assert is_entry or is_ref, \
                (f"line {i} of {FACTORY} carries {name} neither as a "
                 f"secrets-block entry nor as a secrets. reference: "
                 f"{ln.strip()!r}")
    surfaces = {os.path.join(".github", "workflows", "factory.yml"),
                os.path.join(".github", "workflows", "code-weaver.yml"),
                "README.md"}
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in (".git", "tests")]
        for fname in filenames:
            rel = os.path.relpath(os.path.join(dirpath, fname), ROOT)
            if rel in surfaces:
                continue
            try:
                with open(os.path.join(dirpath, fname), encoding="utf-8") as f:
                    text = f.read()
            except (UnicodeDecodeError, OSError):
                continue  # a binary file cannot carry a text secret mapping
            for name, _input_name in PROVIDERS:
                assert f"secrets.{name}" not in text, \
                    f"{rel} commits a {name} secrets mapping — a provider value may not be committed"
