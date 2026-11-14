"""Unit tests pinning the reworked setup-pi stage (issue #23, task 2).

The setup stage stops verifying a pre-requisite of the runner environment:
it installs pi for the run and materialises the run's provided harness into
the agent directory the run's pi invocations resolve (`~/.pi/agent/`, or
`PI_CODING_AGENT_DIR`). These tests read the provider-resolution logic from
the action's stage code (loaded the way the implement-guard test loads the
implement stage's) and run it against a sandbox:

- the run's environment variables are the only providers — a named repo
  file is no longer a provider of any harness element, so a repo file
  placed in the workspace beside an empty or absent secret is never read
  (setup-pi "The run's pi configuration is set by environment variables",
  "The additional packages are provided by a GitHub secret" — each
  element's provider is the run's environment variables, the GitHub secret
  the consumer workflow's secrets block carries);
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
  subdirectory the invocation resolves") — the expected outcome for the
  extension-env element carries the effective half: the resolved values
  are set as environment variables in the environment of the run's pi
  invocations (recorded as state files in the run's state dir that ride
  the cumulative artefact chain to the later stage jobs, whose Read
  trigger state relay carries them into each job's env; applied to the
  stage's process environment) — a run without the provider sets no
  variables and is unchanged.
- the factory repo's tree carries no `.pi` directory — no committed file of
  the run's pi harness (a models file, a settings file, an mcp file, an
  extension) is a repo file (setup-pi "The .pi directory is removed from the
  factory repo");

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
            "INPUT_EXTENSION_ENV", "CW_EXTENSION_ENV",
            "INPUT_LLM_MODEL", "CW_LLM_MODEL",
            # the extension-env values the stage applies to its process
            # environment — a host environment carrying its own must not
            # leak into a case
            "PI_JEV_THINKING", "PI_JEV_BASE_URL")

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
    """(setup-pi "The additional packages are provided by a GitHub secret",
    "The LLM backend configuration is provided for the run, not a
    pre-requisite of the environment", "The MCP configuration is optional"
    — reference
    `requirements/setup-pi.feature::The additional packages are provided
    by a GitHub secret`,
    `requirements/setup-pi.feature::The LLM backend configuration is provided
    for the run, not a pre-requisite of the environment`,
    `requirements/setup-pi.feature::The MCP configuration is optional`)
    a non-empty GitHub secret is the element's provider: the resolved
    content is the secret's, for every harness element. A named repo file is
    no longer a provider of any harness element: a repo file placed in the
    workspace beside an empty or absent secret is never read — the element
    has no provider, whatever the workspace tree holds."""
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
        for input_name, secret_mark, repo_mark in (
                ("pi-models", "secret.example", "repo-file.example"),
                ("pi-settings", "from-secret", "from-repo-file"),
                ("pi-mcp", "secret-server", "repo-server")):
            content, source = mod.resolve_provider(input_name)
            assert content is not None, f"{input_name} has a non-empty secret"
            assert secret_mark in content, \
                f"{input_name} resolves the secret's content — the secret " \
                f"is the element's provider"
            assert repo_mark not in content, \
                f"the {input_name} repo file is never read — it is no " \
                f"longer a provider of any harness element"
        # a secret value that arrives empty (an unset secret) is an absent
        # provider — the repo file beside it is never read
        os.environ["CW_PI_MODELS"] = "   "
        assert mod.resolve_provider("pi-models") is None, \
            "an empty secret is an absent provider — the repo file in the " \
            "workspace is never read, whatever the tree holds"
        # an absent secret is the same: the element has no provider
        os.environ.pop("CW_PI_MODELS", None)
        assert mod.resolve_provider("pi-models") is None, \
            "an absent secret is an absent provider — the repo file in the " \
            "workspace is never read, whatever the tree holds"


def test_empty_or_absent_settings_provider_leaves_no_additional_packages():
    """(setup-pi "An empty or absent settings provider leaves pi without
    additional packages"; reference
    `requirements/setup-pi.feature::The additional packages are provided
    by a GitHub secret`) the harness materialisation writes a
    `settings.json` only for a present provider: with the provider empty or
    absent, it CLEARS the agent directory's `settings.json`
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
            settings = mod.resolve_provider("pi-settings")
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
    configuration"; reference
    `requirements/setup-pi.feature::A provided file without a backend is
    not a usable configuration`)
    a provided model configuration (the GitHub secret that provides it)
    carrying no OpenAI-compatible backend URL triggers the explicit "no
    backend in the provided configuration" failure — and the code path
    never reads the runner's user-level configuration as the run's
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


def test_environment_providing_no_model_configuration_fails_the_stage_clearly():
    """(setup-pi "A run whose environment provides no model configuration
    fails the setup stage clearly"; reference
    `requirements/setup-pi.feature::A run whose environment provides no model
    configuration fails the setup stage clearly`) a run whose environment
    carries no provider for the model configuration fails the setup stage —
    a non-zero exit, the stage's failure record stating the run's pi
    configuration is incomplete (naming the missing provider, the
    PI_MODELS secret the consumer workflow's secrets block must carry,
    beside the standing "pi installation or configuration failed" wording),
    and the reachability / smoke checks never running — the no-later-stage
    half rides the stage job's failure propagating through the job gates the
    stage contract already pins. A repo file placed in the workspace beside
    the absent provider is never read — a named repo file is no longer a
    provider of any harness element (the tree no longer holds one to
    consult)."""
    mod = _load_stage()
    with _sandbox() as sb:
        # a repo file in the workspace tree — the stage must never read it
        sb.write_repo(".pi/agent/models.json",
                      '{"providers": {"repo": '
                      '{"baseUrl": "http://repo-file.example/v1"}}}')
        # a stand-in installed pi — the check's smoke half would run this
        fake_pi = os.path.join(sb.rt, "fake-pi")
        with open(fake_pi, "w", encoding="utf-8") as f:
            f.write("#!/usr/bin/env python3\nprint('OK')\n")
        os.chmod(fake_pi, 0o755)
        agent = os.path.join(sb.home, ".pi", "agent")
        # the sandbox's environment carries no model-configuration provider
        assert mod.resolve_provider("pi-models") is None, \
            "no provider in the environment — a repo file in the workspace " \
            "is never read, whatever the tree holds"
        code = None
        try:
            mod.check_run_configuration(None, "any-model", agent, fake_pi)
        except SystemExit as e:
            code = e.code
        assert code == 1, \
            f"the stage must exit non-zero where the environment provides " \
            f"no model configuration, exit code {code!r}"
        reason = open(os.path.join(sb.rt, "cw", "stage-fail-reason.txt"),
                      encoding="utf-8").read()
        assert "pi installation or configuration failed" in reason, \
            f"the failure keeps the standing explicit wording: {reason!r}"
        assert "the run's pi configuration is incomplete" in reason, \
            f"the failure must state the run's pi configuration is " \
            f"incomplete: {reason!r}"
        assert "PI_MODELS" in reason, \
            f"the failure must name the missing provider (the PI_MODELS " \
            f"secret): {reason!r}"
        assert "repo-file.example" not in reason, \
            "a repo file in the workspace was never read as the run's " \
            "configuration"
        assert "backend unreachable" not in reason, \
            "an absent provider fails before any reachability probe"
        assert "smoke" not in reason, \
            "an absent provider fails before the smoke check runs"


def test_harness_write_targets_the_agent_directory_honoring_pi_coding_agent_dir():
    """(setup-pi "The run's harness is written into the agent subdirectory
    the invocation resolves", "pi resolves its model configuration from the
    agent directory the setup stage wrote", "The additional environment
    variables are provided via a .env-style GitHub secret"; reference
    `requirements/setup-pi.feature::The run's harness is written into the
    agent subdirectory the invocation resolves`,
    `requirements/setup-pi.feature::The run's harness is written into the agent subdirectory the
    invocation resolves`,
    `requirements/setup-pi.feature::The additional environment variables
    are provided via a .env-style GitHub secret`) the harness
    materialisation targets the agent subdirectory the run's pi invocations
    resolve — `PI_CODING_AGENT_DIR` where the runner sets it, otherwise
    `~/.pi/agent` — and writes every provided element there: `models.json`,
    `settings.json`, `mcp.json`, and the extension's environment file
    (the .env-style provider materialised as a user-level extension that
    sets the provided variables, so the run's pi invocations run the
    extension with them). The expected outcome for the extension-env
    element carries the effective half beside that: the resolved values
    are set as environment variables in the environment of the run's pi
    invocations — recorded as state files in the run's state dir (one
    value a file, beside the trigger's recorded state; the files ride the
    cumulative artefact chain to every later stage job, whose Read
    trigger state relay carries them into the job's env like the other
    trigger-state keys) and applied to the stage's process environment —
    and an absent provider records no file and sets no variable, the run
    unchanged. Every standing step of the scenario keeps holding beside
    the grown one, and the runner user's own agent directory stays
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
        os.environ["CW_EXTENSION_ENV"] = (
            "PI_JEV_THINKING=1\n"
            "PI_JEV_BASE_URL=http://laya.example/\n"
            "# a comment line carries no variable\n")
        models = mod.resolve_provider("pi-models")
        settings = mod.resolve_provider("pi-settings")
        mcp = mod.resolve_provider("pi-mcp")
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
        # the effective half of the extension-env element (the grown
        # outcome): the resolved values are set as environment variables
        # in the environment of the run's pi invocations — recorded as
        # state files in the run's state dir (one value a file, beside the
        # trigger's recorded state; the files ride the cumulative artefact
        # chain to every later stage job, whose Read trigger state relay
        # carries them into the job's env like the other trigger-state
        # keys), and applied to the stage's process environment for its
        # own pi invocations
        recorded = mod.record_extension_env(ext)
        assert recorded == [("PI_JEV_THINKING", "1"),
                            ("PI_JEV_BASE_URL", "http://laya.example/")], \
            f"the comment line carries no variable; {recorded!r}"
        for name, value in recorded:
            sf = os.path.join(sb.rt, "cw", "state", "trigger",
                              f"extension-env-{name}.txt")
            assert os.path.isfile(sf), \
                ("each resolved value is recorded as a state file in the "
                 "run's state dir (the later stage jobs' Read trigger "
                 f"state relay reads it): {sf!r}")
            assert open(sf).read() == value + "\n", \
                f"the state file carries the value: {sf!r}"
            assert os.environ.get(name) == value, \
                ("the value is set in the stage's process environment "
                 "(the run's pi invocations resolve it there)")
        # the clear-if-absent half: an absent extension-env provider
        # records no file and sets no variable — the run is unchanged
        assert mod.record_extension_env(None) == [], \
            "an absent provider records no file and sets no variable"
        # the runner user's own agent directory is not the run's configuration
        assert not os.path.exists(
            os.path.join(sb.home, ".pi", "agent", "models.json")), \
            "the harness lands in the agent directory the invocations resolve — " \
            "the runner user's own one is not written when PI_CODING_AGENT_DIR is set"


def test_install_on_a_pristine_runner_extends_the_path_instead_of_failing():
    """(setup-pi "The setup stage installs pi for the run" — the
    pristine-runner half: "a runner whose PATH does not carry the agent
    directory gets it extended for the run, so the installed copy
    resolves on any runner"; reference
    `requirements/setup-pi.feature::The setup stage installs pi for the
    run`) a runner whose user PATH does not resolve `pi` (a hosted label:
    the agent directory's bin/ is not on the PATH) — the stage extends
    the PATH (this stage's process and the run's later steps, through
    GITHUB_ENV) and returns the installed copy: a pi that is merely not
    on the PATH is not a failed installation, and the run's contract
    (every later pi invocation uses the installed copy) is what the
    extension plus the state relay establish."""
    from unittest import mock as um
    import subprocess as sp
    mod = _load_stage()
    with _sandbox() as sb:
        agent = os.path.join(sb.home, ".pi", "agent")
        installed = os.path.join(agent, "bin", "pi")
        os.makedirs(os.path.dirname(installed), exist_ok=True)
        with open(installed, "w", encoding="utf-8") as f:
            f.write("#!/bin/sh\n")
        os.chmod(installed, 0o755)
        base_path = os.environ.get("PATH", "")
        github_env = os.path.join(sb.rt, "github-env.txt")
        saved_env = os.environ.get("GITHUB_ENV")
        os.environ["GITHUB_ENV"] = github_env
        try:
            fake_npm = sp.CompletedProcess(
                args=["npm", "install", "-g", "--prefix", agent, "spec"],
                returncode=0, stdout="", stderr="")
            with um.patch.object(mod.shutil, "which", return_value=None), \
                 um.patch.object(mod.subprocess, "run", return_value=fake_npm):
                got = mod.install_pi(agent)
            extended = os.environ["PATH"]
        finally:
            os.environ["PATH"] = base_path
            if saved_env is None:
                os.environ.pop("GITHUB_ENV", None)
            else:
                os.environ["GITHUB_ENV"] = saved_env
        assert got == installed, f"{got!r}"
        assert extended.startswith(
            os.path.join(agent, "bin") + os.pathsep), \
            "the stage's process PATH is not extended with the agent directory's bin/"
        env_text = open(github_env, encoding="utf-8").read()
        # the relay value is the fully extended absolute PATH — the same
        # value the stage's process keeps, verbatim: the runner applies a
        # GITHUB_ENV entry to the later steps' environment verbatim, never
        # expanding a shell reference, so a `.../bin:$PATH` value would
        # arrive on every later step as the literal string `.../bin:$PATH`
        # — a PATH that resolves nothing, and each later step would die on
        # its first external command (run 42469989855's stage 2: the
        # terminal summary step exited 127 on `tee: command not found`).
        assert env_text.strip() == f"PATH={extended}", \
            (f"the GITHUB_ENV PATH relay must carry the fully extended "
             f"absolute PATH verbatim (an unexpanded `:$PATH` tail would "
             f"break every later step's PATH) — got {env_text!r}")


def test_pi_calls_extend_their_path_from_the_state_relay_on_a_pristine_runner():
    """(the same scenario — the later-jobs half: the install location
    rides the run's state relay, and every pi call re-applies the
    extension before it invokes, so the installed copy resolves in every
    job on a pristine runner; reference
    `requirements/setup-pi.feature::The setup stage installs pi for the
    run`)"""
    from unittest import mock as um
    mod = _load_stage()
    with _sandbox() as sb:
        agent = os.path.join(sb.home, ".pi", "agent")
        os.makedirs(os.path.join(agent, "bin"), exist_ok=True)
        os.makedirs(os.path.join(sb.rt, "cw"), exist_ok=True)
        saved_relay = {k: os.environ.get(k)
                       for k in ("PI_PATH", "PI_INSTALL_DIR")}
        os.environ.pop("PI_PATH", None)
        os.environ.pop("PI_INSTALL_DIR", None)
        with open(os.path.join(sb.rt, "cw", "setup-pi-install.txt"),
                  "w", encoding="utf-8") as f:
            f.write(f"PI_INSTALL_DIR={agent}\n"
                    f"PI_PATH={os.path.join(agent, 'bin', 'pi')}\n")
        base_path = os.environ.get("PATH", "")
        try:
            with um.patch.object(mod.shutil, "which", return_value=None):
                mod.common.ensure_pi_on_path()
            extended = os.environ["PATH"]
        finally:
            os.environ["PATH"] = base_path
            for k, v in saved_relay.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
        assert extended.startswith(
            os.path.join(agent, "bin") + os.pathsep), \
            "the pi call's PATH is not extended from the state relay"


def test_pi_calls_need_no_path_help_where_pi_is_already_resolved():
    """(the same scenario — the no-op half: a runner whose PATH already
    resolves `pi` is left untouched; reference
    `requirements/setup-pi.feature::The setup stage installs pi for the
    run`)"""
    from unittest import mock as um
    mod = _load_stage()
    with _sandbox() as sb:
        base_path = os.environ.get("PATH", "")
        try:
            with um.patch.object(mod.shutil, "which",
                                 return_value="/usr/bin/pi"):
                mod.common.ensure_pi_on_path()
        finally:
            os.environ["PATH"] = base_path
        assert os.environ["PATH"] == base_path, \
            "a runner whose PATH already resolves pi is modified"


def test_repo_tree_contains_no_dot_pi_directory():
    """(setup-pi "The .pi directory is removed from the factory repo"; reference
    `requirements/setup-pi.feature::The .pi directory is removed from the factory repo`)
    the factory repo's tree contains no `.pi` directory: no `.pi`-prefixed
    path is committed — no file of the run's pi harness (a models file, a
    settings file, an mcp file, an extension) is a repo file, so nothing in
    the tree still names a repo-file provider. The scenario's committed
    tree is read as the repo tree: the suite's tests never invoke the real
    git binary, so the check walks the checkout (its `.git` directory is
    git's own bookkeeping, not the tree) and finds no `.pi` entry at any
    depth."""
    dot_pi = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        if ".git" in dirnames:
            dirnames.remove(".git")
        rel = os.path.relpath(dirpath, ROOT)
        for name in dirnames + filenames:
            entry = name if rel == "." else os.path.join(rel, name)
            if entry == ".pi" or entry.startswith(".pi" + os.sep):
                dot_pi.append(entry)
    assert dot_pi == [], (
        "the factory repo's tree contains no `.pi` directory — no "
        f"`.pi`-prefixed path may be committed, found {sorted(dot_pi)!r}")

