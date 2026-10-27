"""Unit tests pinning the reworked setup-pi stage (issue #23, task 2).

The setup stage stops verifying a pre-requisite of the runner environment:
it installs pi for the run and materialises the run's provided harness into
the agent directory the run's pi invocations resolve (`~/.pi/agent/`, or
`PI_CODING_AGENT_DIR`). These tests read the provider-resolution logic from
the action's stage code (loaded the way the implement-guard test loads the
implement stage's) and run it against a sandbox:

- a non-empty secret provider wins over the named repo file (setup-pi
  "The model configuration is provided by a GitHub secret or a repo file" —
  the secret half of the provider pair, for every harness element);
- an empty or absent settings provider yields no additional packages — no
  `settings.json` written, and the runner's pre-existing user-level one
  cleared, never inherited (setup-pi "An empty or absent settings provider
  leaves pi without additional packages");
- a provided model configuration without an OpenAI-compatible backend URL
  triggers the explicit "no backend in the provided configuration" failure,
  and the code path never reads the runner's user-level configuration as the
  run's configuration (setup-pi "A provided file without a backend is not a
  usable configuration");
- the harness write targets the agent directory with `PI_CODING_AGENT_DIR`
  honoured (setup-pi "The run's harness is written into the agent
  subdirectory the invocation resolves").

Plain-stdlib by design (no third-party imports): no-argument `test_`
functions are auto-discovered by both runners (`tests/run.py` imports every
`tests/test_*.py`; house CI's "Validator unit tests" step runs
`pytest tests/`), so no `Makefile`, `tests/run.py` or
`.github/workflows/house-ci.yml` change is needed.
"""
from __future__ import annotations

import importlib.util
import os
import shutil
import sys
import tempfile

ROOT = os.path.join(os.path.dirname(__file__), "..")

STAGE = os.path.join(ROOT, ".github", "actions", "setup-pi", "stage.py")


def _load_stage():
    """Load the stage's stage.py as a module — the same importlib idiom the
    implement-guard test uses for implement-stage/stage.py. The module's
    top-level sys.path bootstrap + `import common` run once; `main()` is not
    called (the module is not `__main__`), so the functions under test run
    exactly as the test drives them, against the sandbox environment."""
    spec = importlib.util.spec_from_file_location("cw_setup_pi_stage", STAGE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _sandbox:
    """The sandbox the stage's resolution logic runs against: a temp HOME
    (the runner user's home — where the user-level agent directory the run
    must never inherit lives), a temp workspace (the target repo checkout
    the repo-file providers resolve from), a temp RUNNER_TEMP state dir, and
    a diag-log path inside the sandbox (the stage's failure persistence never
    touches the real runner's diag log).

    Entering the sandbox clears every provider/input env var the stage
    reads (a host environment that carries its own CW_*/INPUT_* values must
    not leak into a case); each case sets exactly the providers it pins."""
    KEYS = ("HOME", "RUNNER_TEMP", "GITHUB_WORKSPACE", "GITHUB_OUTPUT",
            "PI_CODING_AGENT_DIR", "PI_PACKAGE", "LLM_MODEL", "CW_DIAG_LOG",
            "INPUT_PI_MODELS", "CW_PI_MODELS",
            "INPUT_PI_SETTINGS", "CW_PI_SETTINGS",
            "INPUT_PI_MCP", "CW_PI_MCP",
            "INPUT_PI_EXTENSION_ENV", "CW_PI_EXTENSION_ENV",
            "INPUT_LLM_MODEL", "CW_LLM_MODEL")

    def __init__(self):
        self.home = tempfile.mkdtemp(prefix="cw-setup-home-")
        self.ws = tempfile.mkdtemp(prefix="cw-setup-ws-")
        self.rt = tempfile.mkdtemp(prefix="cw-setup-rt-")
        self.diag = tempfile.mkdtemp(prefix="cw-setup-diag-")
        self.saved = None

    def __enter__(self):
        self.saved = {k: os.environ.get(k) for k in self.KEYS}
        for k in self.KEYS:
            os.environ.pop(k, None)
        os.environ.update({
            "HOME": self.home,
            "RUNNER_TEMP": self.rt,
            "GITHUB_WORKSPACE": self.ws,
            "GITHUB_OUTPUT": os.path.join(self.rt, "github-output.txt"),
            "CW_DIAG_LOG": os.path.join(self.diag, "cw-diag.log"),
        })
        return self

    def __exit__(self, *exc):
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        for d in (self.home, self.ws, self.rt, self.diag):
            shutil.rmtree(d, ignore_errors=True)
        return False

    def write_repo(self, rel: str, content: str) -> None:
        """A file in the target repo checkout (the repo-file providers)."""
        p = os.path.join(self.ws, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)

    def write_user(self, rel: str, content: str) -> None:
        """A file in the runner user's pre-existing agent directory — the
        user-level configuration the run must never inherit."""
        p = os.path.join(self.home, ".pi", "agent", rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)


def test_secret_provider_wins_over_repo_file():
    """(setup-pi "The model configuration is provided by a GitHub secret or
    a repo file", "The additional packages are provided by a GitHub secret
    or a repo file", "The MCP configuration is provided via a GitHub secret"
    — the GitHub-secret half of each provider pair) a non-empty GitHub
    secret provider wins over the named repo file: the resolved content is
    the secret's, for every harness element that carries both a secret and
    a repo-file provider. A secret value that arrives empty is an absent
    provider — the repo file is the fallback."""
    mod = _load_stage()
    with _sandbox() as sb:
        sb.write_repo(".pi/agent/models.json",
                      '{"providers": {"repo": '
                      '{"baseUrl": "http://repo-file.example/v1"}}}')
        sb.write_repo(".pi/settings.json", '{"packages": ["npm:from-repo-file"]}')
        sb.write_repo(".pi/mcp.json", '{"mcpServers": {"repo-server": {}}}')
        os.environ["CW_PI_MODELS"] = ('{"providers": {"secret": '
                                      '{"baseUrl": "http://secret.example/v1"}}}')
        os.environ["CW_PI_SETTINGS"] = '{"packages": ["npm:from-secret"]}'
        os.environ["CW_PI_MCP"] = '{"mcpServers": {"secret-server": {}}}'
        for input_name, repo_rel, secret_mark, repo_mark in (
                ("pi-models", ".pi/agent/models.json",
                 "secret.example", "repo-file.example"),
                ("pi-settings", ".pi/settings.json",
                 "from-secret", "from-repo-file"),
                ("pi-mcp", ".pi/mcp.json",
                 "secret-server", "repo-server")):
            content, source = mod.resolve_provider(input_name, repo_rel)
            assert content is not None, f"{input_name} has a non-empty secret"
            assert secret_mark in content, \
                f"the non-empty {input_name} secret must win over the repo file"
            assert repo_mark not in content, \
                f"the {input_name} repo file must not be read when the secret is set"
        # a secret value that arrives empty (an unset secret) is an absent
        # provider — the repo file is the fallback
        os.environ["CW_PI_MODELS"] = "   "
        content, source = mod.resolve_provider(
            "pi-models", ".pi/agent/models.json")
        assert content is not None and "repo-file.example" in content, \
            "an empty secret value must fall back to the repo file"


def test_empty_or_absent_settings_provider_leaves_no_additional_packages():
    """(setup-pi "An empty or absent settings provider leaves pi without
    additional packages") the harness materialisation writes a
    `settings.json` only for a present provider: with the provider empty or
    absent (both halves), it CLEARS the agent directory's `settings.json`
    instead — the runner's pre-existing user-level settings (which declare
    packages) is replaced for the run, never inherited, so the run's pi runs
    without any additional packages."""
    mod = _load_stage()
    for provider_env in ({"CW_PI_SETTINGS": ""}, {}):
        with _sandbox() as sb:
            # the runner's pre-existing user-level configuration declares
            # packages — the state the old verify-only stage would have
            # let the run inherit
            sb.write_user("settings.json", '{"packages": ["npm:runner-leftover"]}')
            for k, v in provider_env.items():
                os.environ[k] = v
            agent = os.path.join(sb.home, ".pi", "agent")
            settings = mod.resolve_provider("pi-settings", ".pi/settings.json")
            assert settings is None, \
                f"an empty or absent provider is an absent provider, got {settings!r}"
            written = mod.materialize_harness(
                ('{"providers": {"p": {"baseUrl": "http://b.example/v1"}}}',
                 "the GitHub secret (the run's pi-models provider)"),
                settings, None, None, agent)
            assert "settings" not in written or str(written["settings"]).startswith(
                "(no provider"), \
                f"no settings provider — nothing may be written: {written!r}"
            assert not os.path.exists(os.path.join(agent, "settings.json")), \
                "the runner's pre-existing user-level settings must be " \
                "cleared, not inherited — pi runs without additional packages"


def test_provided_config_without_backend_fails_and_never_falls_back():
    """(setup-pi "A provided file without a backend is not a usable
    configuration") a provided model configuration (a GitHub secret or the
    repo file) carrying no OpenAI-compatible backend URL triggers the
    explicit "no backend in the provided configuration" failure — and the
    code path never reads the runner's user-level configuration as the run's
    configuration: the failure holds even though a valid user-level
    configuration (a backend URL and a model set) sits in the user agent
    directory, and the stage never resolves the run's backend from it."""
    mod = _load_stage()
    with _sandbox() as sb:
        # a valid pre-existing user-level configuration in the runner's
        # home — the fallback the old verify-only stage scanned for
        sb.write_user("models.json",
                      '{"providers": {"user": '
                      '{"baseUrl": "http://user-config.example/v1", '
                      '"models": [{"id": "user-model"}]}}}')
        provided = ('{"providers": {"provided": '
                    '{"models": [{"id": "provided-model"}]}}}')
        os.environ["CW_PI_MODELS"] = provided
        agent = os.path.join(sb.home, ".pi", "agent")
        # a stand-in installed pi — the check's smoke half would run this
        fake_pi = os.path.join(sb.rt, "fake-pi")
        with open(fake_pi, "w", encoding="utf-8") as f:
            f.write("#!/usr/bin/env python3\nprint('OK')\n")
        os.chmod(fake_pi, 0o755)
        exited = False
        try:
            mod.check_run_configuration(
                (provided, "the GitHub secret (the run's pi-models provider)"),
                "provided-model", agent, fake_pi)
        except SystemExit:
            exited = True
        assert exited, \
            "a provided configuration without a backend must fail the stage"
        reason = open(os.path.join(sb.rt, "cw", "stage-fail-reason.txt"),
                      encoding="utf-8").read()
        assert "no backend in the provided configuration" in reason, \
            f"the failure must name the missing backend explicitly: {reason!r}"
        assert "user-config.example" not in reason, \
            ("the failure must be about the provided configuration — the "
             f"runner's user-level one was never read as the run's: {reason!r}")
        assert "backend unreachable" not in reason, \
            "a configuration without a backend fails before any reachability probe"


def test_harness_write_targets_the_agent_directory_honoring_pi_coding_agent_dir():
    """(setup-pi "The run's harness is written into the agent subdirectory
    the invocation resolves", "pi resolves its model configuration from the
    agent directory the setup stage wrote", "The additional environment
    variables are provided via a .env-style GitHub secret") the harness
    materialisation targets the agent subdirectory the run's pi invocations
    resolve — `PI_CODING_AGENT_DIR` where the runner sets it, otherwise
    `~/.pi/agent` — and writes every provided element there: `models.json`,
    `settings.json`, `mcp.json`, and the extension's environment file
    (the .env-style provider materialised as a user-level extension that
    sets the provided variables, so the run's pi invocations run the
    extension with them). The runner user's own agent directory stays
    untouched."""
    mod = _load_stage()
    with _sandbox() as sb:
        custom = os.path.join(sb.rt, "custom-agent-dir")
        # the default: the runner user's ~/.pi/agent
        assert mod.agent_dir() == os.path.join(sb.home, ".pi", "agent")
        # PI_CODING_AGENT_DIR honoured
        os.environ["PI_CODING_AGENT_DIR"] = custom
        assert mod.agent_dir() == custom
        os.environ["CW_PI_MODELS"] = \
            '{"providers": {"p": {"baseUrl": "http://b.example/v1"}}}'
        os.environ["CW_PI_SETTINGS"] = '{"packages": ["npm:pi-jev"]}'
        os.environ["CW_PI_MCP"] = '{"mcpServers": {"laya": {}}}'
        os.environ["CW_PI_EXTENSION_ENV"] = (
            "PI_JEV_THINKING=1\n"
            "PI_JEV_BASE_URL=http://laya.example/\n"
            "# a comment line carries no variable\n")
        models = mod.resolve_provider("pi-models",
                                      os.path.join(".pi", "agent", "models.json"))
        settings = mod.resolve_provider("pi-settings",
                                        os.path.join(".pi", "settings.json"))
        mcp = mod.resolve_provider("pi-mcp", os.path.join(".pi", "mcp.json"))
        ext = mod.resolve_extension_env()
        assert ext is not None and "PI_JEV_THINKING=1" in ext
        written = mod.materialize_harness(models, settings, mcp, ext, custom)
        for element, rel in (("models", "models.json"),
                             ("settings", "settings.json"),
                             ("mcp", "mcp.json"),
                             ("extension-env",
                              os.path.join("extensions", "cw-harness-env.ts"))):
            p = written.get(element)
            assert p is not None and p.startswith(custom + os.sep), \
                (f"the {element} must be written into the PI_CODING_AGENT_DIR "
                 f"agent directory, got {p!r}")
            assert os.path.isfile(p), f"the {element} file must exist: {p!r}"
        # the extension's environment file sets the provided variables
        ext_src = open(os.path.join(custom, "extensions",
                                    "cw-harness-env.ts"),
                       encoding="utf-8").read()
        assert '"PI_JEV_THINKING": "1"' in ext_src, ext_src
        assert '"PI_JEV_BASE_URL": "http://laya.example/"' in ext_src, ext_src
        assert "process.env" in ext_src, \
            "the generated extension must set the variables in the environment"
        # the runner user's own agent directory is not the run's configuration
        assert not os.path.exists(
            os.path.join(sb.home, ".pi", "agent", "models.json")), \
            "the harness lands in the agent directory the invocations resolve — " \
            "the runner user's own one is not written when PI_CODING_AGENT_DIR is set"
