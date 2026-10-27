#!/usr/bin/env python3
"""Stage 2 — install pi for this workflow run, and configure it from the
run's provided harness.

The setup stage is not a verify-only gate on a pre-requisite of the runner
environment: it provides the harness for the run.

  (a) install — install pi for this workflow run into the agent directory
      (npm's global prefix = the agent directory, so the installed binary
      lands in the agent directory's bin/ — the directory that sits first on
      the runner user's PATH, so every later pi invocation in the run
      resolves that installed copy). Its location rides the run's state/env
      relay like every other stage value.

  (b) materialise the harness — for each element resolve its provider (a
      non-empty GitHub secret wins over the named repo file) and write it
      into the agent directory (`~/.pi/agent/`, honouring
      PI_CODING_AGENT_DIR) the run's pi invocations resolve:
        models.json   ← the PI_MODELS secret or the repo file
                        .pi/agent/models.json — the backend the run uses is
                        the one in it
        settings.json ← the PI_SETTINGS secret or the repo file
                        .pi/settings.json — the additional packages; an empty
                        or absent provider writes nothing, so the run's pi runs
                        without additional packages
        mcp.json      ← the PI_MCP secret or the repo file .pi/mcp.json —
                        an absent provider means the run's pi runs without MCP
                        servers
        extensions/   ← the extension's environment (the .env-style
                        PI_EXTENSION_ENV secret) materialised as a user-level
                        extension that sets the provided variables, so the
                        run's pi invocations run the extension with them
      The runner's pre-existing user-level configuration is replaced for the
      run, never read as the run's: an element without a provider is cleared
      from the agent directory, not inherited.

  (c) keep the checks, re-pointed at what the stage installed and wrote —
      the provided model configuration must carry an OpenAI-compatible
      backend URL (a provided file without one fails "no backend in the
      provided configuration" — the runner's pre-existing user-level
      configuration is never used as the run's), the backend must answer its
      /models probe (otherwise "backend unreachable"), the selected
      llm-model must be listed in the model set of the configuration the
      stage wrote, and the headless `pi --print` smoke check runs the
      installed pi against the backend the stage configured.

  (d) the failure modes — an installation or configuration that cannot
      complete fails the stage with an explicit "pi installation or
      configuration failed" error (no later stage runs); an unreachable
      backend fails with "backend unreachable". The reason is persisted like
      every other stage failure (stage-fail-reason.txt in the state dir + the
      runner's diagnostic log).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request

# The action directory comes from this file's own location: on this
# runner build GITHUB_ACTION_PATH is unset inside composite action
# inner steps, and on a healthy runner both sources agree anyway
action_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(action_dir)), "scripts"))

import common

STAGE = "stage 2 setup-pi"


def fail(msg: str) -> None:
    """An explicit, persisted stage failure — the job log dies with the
    run, so the reason goes to the stage's artefacts (the setup job's
    summary/upload steps carry stage-fail-reason.txt on) and the runner's
    diagnostic log. install_crash_diagnostics' hook only fires on uncaught
    exceptions, so a controlled failure writes the same artefacts itself.
    No later stage runs."""
    d = common.state_dir()
    with open(os.path.join(d, "stage-fail-reason.txt"), "w") as f:
        f.write(f"{STAGE} FAILED — {msg}\n")
    diag = os.environ.get("CW_DIAG_LOG", "/opt/actions-runner/_diag/cw-diag.log")
    try:
        with open(diag, "a") as f:
            f.write(f"=== {STAGE} FAILED ===\n{msg}\n")
    except OSError:
        pass  # a runner without the diag dir: the artefact line survives
    print(f"::error::{msg}")
    sys.exit(1)


def agent_dir() -> str:
    """The agent subdirectory the run's pi invocations resolve:
    PI_CODING_AGENT_DIR where the runner sets it, otherwise
    `~/.pi/agent/`."""
    d = (os.environ.get("PI_CODING_AGENT_DIR") or "").strip()
    return os.path.expanduser(d) if d else os.path.expanduser("~/.pi/agent")


def provider_value(input_name: str) -> str | None:
    """The provider's GitHub secret value, delivered through the factory's
    documented `with:` + `CW_<name>` env relay idiom (INPUT_<name> on a
    healthy runner, CW_<name> on this one). A value that arrives empty —
    an unset or empty secret — is an absent provider."""
    v = common.cw_input_opt(input_name)
    if v is None or not v.strip():
        return None
    return v


def resolve_provider(input_name: str, repo_rel: str) -> tuple[str, str] | None:
    """Resolve one harness element's provider: a non-empty GitHub secret
    wins over the named repo file in the checked-out workspace; neither
    present → the element has no provider. Returns (content, source) — or
    None for an element without a provider."""
    v = provider_value(input_name)
    if v is not None:
        return v, f"the GitHub secret (the run's {input_name} provider)"
    p = os.path.join(common.repo(), repo_rel)
    if os.path.isfile(p):
        with open(p, encoding="utf-8") as f:
            return f.read(), f"the repo file {repo_rel}"
    return None


def resolve_extension_env() -> str | None:
    """The extension's environment provider — a `.env`-style GitHub secret
    (KEY=VALUE lines; blank lines and # comments carry no variables).
    Empty or comment-only is an absent provider."""
    v = provider_value("pi-extension-env")
    if v is None:
        return None
    kept = [ln.strip() for ln in v.splitlines()
            if ln.strip() and not ln.strip().startswith("#")]
    if not kept:
        return None
    return "\n".join(kept)


def _extension_source(env_text: str) -> str:
    """The generated user-level extension's source — the extension's
    environment file written into the agent directory for the run
    (extensions/cw-harness-env.ts).

    User (agent-directory) extensions load before project extensions, and
    project extensions load before package extensions — pi's extension load
    order — so the provided variables are already in process.env when the
    pi-jev package extension reads them at load time. The generated file
    mirrors the shape of the project's .pi/extensions/pi-jev-config.ts: an
    object of the provided variables, applied with the same leave-untouched
    rule (a value already present in the environment wins over the run's
    provided one)."""
    entries = []
    for line in env_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        name, value = name.strip(), value.strip().strip('"').strip("'")
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name):
            continue  # a malformed line is skipped, never fatal
        entries.append((name, value))
    body = "".join(f"  {json.dumps(n)}: {json.dumps(v)},\n"
                   for n, v in entries)
    return (
        "// Generated by the code-weaver setup stage for this workflow run —\n"
        "// the extension's environment (the .env-style provider), materialised\n"
        "// into the agent directory the run's pi invocations resolve.\n"
        "const CW_RUN_ENV: Record<string, string> = {\n"
        f"{body}"
        "};\n"
        "export default function () {\n"
        "  for (const [name, value] of Object.entries(CW_RUN_ENV)) {\n"
        "    if (!process.env[name]) {\n"
        "      process.env[name] = value;\n"
        "    }\n"
        "  }\n"
        "}\n"
    )


def materialize_harness(models, settings, mcp, extension_env,
                        agent_dir: str) -> dict:
    """(b) Write the run's harness into the agent directory.

    The agent directory carries what the stage wrote — replaced for the run:
    an element with a provider is written from the resolved provider (a
    non-empty GitHub secret having won over the named repo file), and an
    element without one is CLEARED — the runner's pre-existing user-level
    configuration is never used as the run's configuration (an empty or
    absent settings provider leaves pi without additional packages; an
    absent MCP provider means the run's pi runs without MCP servers).

    Returns {element: path} for what the run's pi invocations resolve."""
    os.makedirs(agent_dir, exist_ok=True)
    written: dict = {}

    def place(agent_file: str, content: str, element: str) -> None:
        p = os.path.join(agent_dir, agent_file)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content if content.endswith("\n") else content + "\n")
        written[element] = p

    def clear(agent_file: str, element: str) -> None:
        try:
            os.remove(os.path.join(agent_dir, agent_file))
        except FileNotFoundError:
            pass
        written[element] = "(no provider — cleared, not inherited)"

    if models is not None:
        place("models.json", models[0], "models")
    else:
        clear("models.json", "models")
    if settings is not None:
        place("settings.json", settings[0], "settings")
    else:
        clear("settings.json", "settings")
    if mcp is not None:
        place("mcp.json", mcp[0], "mcp")
    else:
        clear("mcp.json", "mcp")
    ext_dir = os.path.join(agent_dir, "extensions")
    if extension_env:
        os.makedirs(ext_dir, exist_ok=True)
        p = os.path.join(ext_dir, "cw-harness-env.ts")
        with open(p, "w", encoding="utf-8") as f:
            f.write(_extension_source(extension_env))
        written["extension-env"] = p
    else:
        clear(os.path.join("extensions", "cw-harness-env.ts"), "extension-env")
    return written


def backend_from_config(raw: str) -> str | None:
    """The OpenAI-compatible backend URL in the provided model
    configuration — the only configuration the run's checks read.

    The walk looks for a url/baseUrl/base_url field carrying an http URL
    anywhere in the parsed document (a provider's baseUrl in pi's
    models.json shape); a document that parses to no URL falls back to a
    raw-text scan for an endpoint ending in /v1. A configuration that
    yields no URL is not a usable configuration — the stage fails
    "no backend in the provided configuration" and never falls back to the
    runner's pre-existing user-level configuration."""
    try:
        data = json.loads(raw)
    except Exception:
        data = None
    backend = None
    if data is not None:
        def walk(o):
            if isinstance(o, dict):
                for k, v in o.items():
                    if (k.lower() in ("url", "baseurl", "base_url")
                            and isinstance(v, str) and v.startswith("http")):
                        yield v.rstrip("/")
                    else:
                        yield from walk(v)
            elif isinstance(o, list):
                for v in o:
                    yield from walk(v)
        backend = next(iter(walk(data)), None)
    if backend is None:
        m = re.search(r"https?://[^\s\"'<>]+/v1", raw)
        if m:
            backend = m.group(0).rstrip("/")
    if backend is None:
        return None
    return backend if backend.endswith("/v1") else backend + "/v1"


def model_ids_from_config(raw: str) -> list:
    """The model set of the provided model configuration — the set the
    selected llm-model must be listed in (judged against the configuration
    the stage wrote, not against the backend's live /models listing)."""
    try:
        data = json.loads(raw)
    except Exception:
        return []
    ids = []
    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k == "models" and isinstance(v, list):
                    for m in v:
                        if isinstance(m, dict) and isinstance(m.get("id"), str):
                            ids.append(m["id"])
                else:
                    walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(data)
    return ids


class InstallError(RuntimeError):
    pass


def install_pi(agent_dir: str) -> str:
    """(a) Install pi for this workflow run into the agent directory.

    The package is installed with the agent directory as npm's global
    prefix — the same layout a system-level pi install uses (the package
    under <prefix>/lib/node_modules, its `pi` bin linked into
    <prefix>/bin/) — so the installed binary lands in the agent directory's
    bin/. That bin directory sits first on the runner user's PATH (pi's own
    helper binaries — fd, rg — already live there), so every later pi
    invocation in the run — any stage, any job on the runner — resolves that
    installed copy.

    The stage fails explicitly rather than continuing where the runner's
    PATH would resolve `pi` to a different copy: the run's contract is that
    every later pi invocation uses the copy this run installed."""
    spec = os.environ.get("PI_PACKAGE") or "@earendil-works/pi-coding-agent"
    os.makedirs(agent_dir, exist_ok=True)
    r = subprocess.run(
        ["npm", "install", "-g", "--prefix", agent_dir, spec],
        capture_output=True, text=True, timeout=1800)
    if r.returncode != 0:
        raise InstallError(
            f"the pi install failed (npm exit {r.returncode}, package {spec}): "
            f"{(r.stderr or r.stdout).strip()[-300:]}")
    installed = os.path.join(agent_dir, "bin", "pi")
    if not os.path.exists(installed) or not os.access(installed, os.X_OK):
        raise InstallError(f"the install left no executable pi at {installed}")
    on_path = shutil.which("pi")
    same = (on_path is not None
            and os.path.realpath(on_path) == os.path.realpath(installed))
    if not same:
        raise InstallError(
            "the runner's PATH does not resolve `pi` to the installed copy — "
            f"installed {installed}, the PATH resolves {on_path or 'no pi'}; "
            "put the agent directory's bin/ on the runner user's PATH so every "
            "later pi invocation in the run uses the installed copy")
    return installed


def check_run_configuration(models, model: str, agent_dir: str,
                            installed: str) -> str:
    """(c) The checks, re-pointed at what the stage installed and wrote.

    The backend-reachability probe reads the configuration the stage wrote
    (a provided file carrying no OpenAI-compatible backend URL → fails
    "no backend in the provided configuration"); the selected llm-model
    must be listed in the model set of the configuration the stage wrote;
    and the headless `pi --print` smoke check runs the installed pi against
    the backend the stage configured. Returns the backend URL the run uses."""
    if models is None:
        fail("pi installation or configuration failed — no provider for the "
             "model configuration (set the PI_MODELS secret or commit the repo "
             "file .pi/agent/models.json)")
    raw = models[0]
    backend = backend_from_config(raw)
    if backend is None:
        fail("no backend in the provided configuration — "
             f"the model configuration ({models[1]}) carries no OpenAI-compatible "
             "backend URL; the runner's pre-existing user-level configuration "
             "is never used as the run's configuration")
    # backend reachability — the probe reads the configuration the stage
    # wrote: a backend that does not answer its /models probe fails the stage
    try:
        req = urllib.request.Request(backend + "/models",
                                     headers={"User-Agent": "code-weaver-setup"})
        with urllib.request.urlopen(req, timeout=10) as r:
            r.read()
    except Exception as e:
        fail(f"backend unreachable: {backend} did not answer its /models "
             f"probe ({e.__class__.__name__})")
    # the selected model must be listed in the model set of the
    # configuration the stage wrote
    ids = model_ids_from_config(raw)
    if model not in ids:
        fail(f"pi installation or configuration failed — model '{model}' is "
             f"not in the model set of the configuration the stage wrote: {ids}")
    # headless smoke check — the installed pi (not a PATH `pi` that could be
    # a different copy) against the backend the stage configured, the run's
    # harness in place. The window must absorb a COLD backend load: the
    # host's llama-swap unloads the model entry after an idle ttl, so a run
    # started long after the last use finds it unloaded and the swap loads it
    # on the first request (2-3 min cold) before the first answer. 420 s
    # leaves 2-4x margin while staying inside the job cap.
    r = subprocess.run(
        [installed, "--print", "--model", model, "Reply with exactly: OK"],
        capture_output=True, text=True, timeout=420, cwd=common.repo(),
        env={**os.environ, "PI_CODING_AGENT_DIR": agent_dir})
    if r.returncode != 0 or not r.stdout.strip():
        fail(f"pi installation or configuration failed — the installed pi did "
             f"not answer the smoke check for model '{model}' "
             f"(exit {r.returncode}): {r.stderr.strip()[:200]}")
    return backend


def main() -> None:
    common.install_crash_diagnostics(STAGE)
    agent = agent_dir()
    model = (os.environ.get("LLM_MODEL")
             or common.cw_input_opt("llm-model") or "")

    # (a) install pi for this workflow run — every later pi invocation in
    # the run resolves that installed copy; its location rides the run's
    # state/env relay like every other stage value
    try:
        installed = install_pi(agent)
    except (InstallError, OSError, subprocess.SubprocessError) as e:
        fail(f"pi installation or configuration failed — {e}")
    with open(common.state_file("setup-pi-install.txt"), "w") as f:
        f.write(f"PI_INSTALL_DIR={agent}\nPI_PATH={installed}\n")
    common.log(f"setup-pi: pi installed for the run — {installed} (the agent "
               f"directory's bin/ is on the runner user's PATH, so every later "
               f"pi invocation in the run resolves it)")

    # (b) materialise the run's provided harness into the agent directory
    # the run's pi invocations resolve
    models = resolve_provider("pi-models",
                              os.path.join(".pi", "agent", "models.json"))
    settings = resolve_provider("pi-settings", os.path.join(".pi", "settings.json"))
    mcp = resolve_provider("pi-mcp", os.path.join(".pi", "mcp.json"))
    extension_env = resolve_extension_env()
    try:
        written = materialize_harness(models, settings, mcp,
                                      extension_env, agent)
    except OSError as e:
        fail(f"pi installation or configuration failed — the agent directory "
             f"{agent} could not be written: {e}")
    for el in ("models", "settings", "mcp", "extension-env"):
        common.log(f"setup-pi: harness {el}: {written.get(el)}")

    # (c) the checks, re-pointed at what the stage installed and wrote
    backend = check_run_configuration(models, model, agent, installed)

    # the relay — the state dir (the artefact channel the later jobs and the
    # report stage read) + GITHUB_OUTPUT (the job-outputs relay on a healthy
    # runner); both carry the values the verify-only stage relayed
    # (backend-url, model) plus the install location
    with open(os.path.join(common.state_dir(), "setup-env"), "w") as f:
        f.write(f"BACKEND_URL={backend}\nMODEL={model}\n")
        f.write(f"PI_INSTALL_DIR={agent}\nPI_PATH={installed}\n")
        for el in ("models", "settings", "mcp", "extension-env"):
            f.write(f"HARNESS_{el.upper()}={written.get(el)}\n")
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a") as f:
            f.write(f"backend-url={backend}\nmodel={model}\n"
                    f"pi-install-dir={agent}\n")
    common.log(f"setup-pi: OK — installed pi for the run ({installed}), "
               f"harness written into {agent}; backend {backend} reachable, "
               f"model '{model}' in the written set, smoke check passed")


if __name__ == "__main__":
    main()
