"""Unit tests for how the published workflow file carries its runtime tree.

The reusable workflow is the file a target pins, and GitHub fetches
only that file at the called ref — the called ref is not visible to the
run's jobs. The old design answered that by relaying the ref as the
`factory-ref` input (a second pin beside the consumer's uses: line) and
cloning the factory repo at it at run time; a later rewrite answered it
by embedding the runtime tree in the file itself — a base64 tarball
behind the heredoc in stage 1's first step. The embed is retired: it
put a binary payload in a file that must be plain text, and the bloat
took the published file past its max allowed size. The current answer
lets the first job fetch the called version's tree: the called ref is
recovered from the consumer workflow (read over the GitHub API at the
run's base ref — a declared version tag resolves to the factory repo
fetched at that tag, a relative uses: to the triggering repo at its own
base ref), the fetch is an actions/checkout of the public factory repo
that does not ride the target-scoped GH_TOKEN (the documented contract
scopes that token to the target repo, and it cannot read the factory
repo), and the tree lands in the runner's temp dir before the first
checkout replaces the workspace (the trigger's artifact then carries it
to every later stage job). No stage reads the `factory-ref` input
anymore (it stays declared as a legacy no-op so an older consumer's
`with:` block stays schema-valid), and the consumer relays nothing —
the uses: line is the only pin a run makes.

The pins:
- the file's payload region is gone (the embed is retired): the file
  holds no `CW_EMBEDDED_RUNTIME_TAR` heredoc, and stage 1's steps
  resolve the called ref and fetch the called version's tree into the
  stash;
- the committed tree the gate verifies carries the canonical runtime
  files the file's steps execute (a curation drift in the check's file
  set would leave a tree the stage steps cannot run from — the drift
  stays a failure, not silent);
- a run fetches the factory repo: the fetch is an owner-qualified
  `actions/checkout` that rides a run-time-resolved ref (no ref literal
  anywhere in the file — the called ref is recovered, not declared),
  and no stage reads the `factory-ref` input (the declared legacy
  no-op).

Plain-stdlib by design (no third-party imports): the stage-10 driver
(`make test` → `python3 tests/run.py`) is a stdlib-only plain-python
contract per the Makefile. The gate script is loaded by file path (its
filename is import-safe, but the loader idiom follows
`tests/test_release_contract.py`'s `release-number.py` precedent, and a
target interpreter may not see the .github package layout).
No-argument `test_` functions — discovered automatically by both
runners (`tests/run.py` imports every `tests/test_*.py`; house CI's
"Validator unit tests" step runs `pytest tests/`), so no `Makefile`
`test` target or `tests/run.py` change is needed.
"""
from __future__ import annotations

import importlib.util
import os
import re

ROOT = os.path.join(os.path.dirname(__file__), "..")
FACTORY = os.path.join(".github", "workflows", "factory.yml")

# The shared-plumbing script the release flow's publication gate runs
# on the committed file and tree (--check). Load it by file path, the
# way the release-contract module loads `release-number.py`.
_spec = importlib.util.spec_from_file_location(
    "embed_runtime", os.path.join(ROOT, ".github", "scripts", "embed-runtime.py"))
embed = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(embed)


def _read(relpath):
    with open(os.path.join(ROOT, relpath)) as f:
        return f.read()


def test_factory_file_carries_its_runtime_tree_embedded():
    """(reuse-by-ref "a published version is self-contained" — the
    scenario adjusted in place by the issue-100 delta; reference
    `requirements/reuse-by-ref.feature::A published version is
    self-contained`) the embed is retired: the file stores no binary
    content, so the payload region (the heredoc body of stage 1's first
    step) is gone from the file, and the stage-1 steps that replace it
    resolve the called ref — recovered from the consumer workflow read
    over the GitHub API at the run's base ref (GitHub fetched the file
    at the ref the consumer's uses: line declared, and the jobs are not
    told which ref that was) — and fetch the called version's tree into
    the stash before the first checkout replaces the workspace: the
    ref's published version carries the file and the tree together, the
    file storing no binary payload — the shape the adjusted scenario's
    Given and Then state."""
    text = _read(FACTORY)
    assert "CW_EMBEDDED_RUNTIME_TAR" not in text, (
        "the workflow file still holds the CW_EMBEDDED_RUNTIME_TAR "
        "heredoc — the payload region is gone: the embed is retired, and "
        "the file stores no binary content")
    # stage 1 resolves the called ref — from the consumer workflow,
    # read over the GitHub API at the run's base ref (no checkout has
    # happened yet, so nothing has replaced the workspace)
    assert "id: called-version" in text, (
        "stage 1 does not resolve the called version — the called ref is "
        "recovered from the consumer workflow, and the fetch rides the "
        "recovered value")
    assert re.search(r"gh api[^\n]*contents/\.github/workflows/", text), (
        "stage 1 does not read the consumer workflow over the GitHub API "
        "— the called ref is recovered from that file as committed at the "
        "run's base ref")
    # ...and fetches the called version's tree into the stash, riding
    # the run-time-resolved ref (no ref literal anywhere in the file —
    # the called ref is recovered, not declared)
    assert re.search(
        r"ref:\s*\$\{\{\s*steps\.called-version\.outputs\.called-ref\s*\}\}",
        text), (
        "the fetch does not ride the run-time-resolved ref — the called "
        "ref is recovered from the consumer workflow, and no ref literal "
        "may stand in the fetch's ref input")
    assert re.search(
        r"path:\s*\$\{\{\s*runner\.temp\s*\}\}/cw/stash", text), (
        "stage 1 does not fetch the called version's tree into the stash "
        "($RUNNER_TEMP/cw/stash) before the first checkout replaces the "
        "workspace")

def test_embedded_tree_holds_the_canonical_runtime_files():
    """(the same scenario, made silent-safe; reference
    `requirements/reuse-by-ref.feature::A published version is
    self-contained`) the committed tree the gate verifies — the
    curated file set the check covers (the prefixes the first job's
    fetch materialises) — carries the canonical runtime files the
    file's steps execute: a curation drift in the check's file set
    (a prefix lost, an exclusion over-broad) would leave a tree the
    stage steps cannot run from — the drift stays a failure, not
    silent, and the missing file is named."""
    names = set(arcname for arcname, _ in embed.runtime_files(ROOT))
    for marker in (".github/scripts/common.py",
                   ".github/scripts/stages.py",
                   ".github/scripts/gherkin-validate.py",
                   ".github/scripts/release-number.py",
                   ".github/actions/setup-pi/stage.py",
                   ".github/actions/extract-stage/stage.py",
                   ".github/actions/plan-stage/stage.py",
                   ".github/actions/implement-stage/stage.py",
                   ".github/actions/review-stage/stage.py",
                   ".github/actions/gates-stage/stage.py",
                   ".github/actions/guard-check/guard-check.py",
                   "pi-prompts/requirements.md",
                   "pi-prompts/plan.md",
                   "pi-prompts/implement.md",
                   "pi-prompts/review.md",
                   "pi-prompts/pr-body.md"):
        assert marker in names, (
            f"the committed tree the gate verifies is missing {marker} "
            "— the curation changed under the stage code's "
            "__file__-relative resolution")


def test_no_run_fetches_the_factory_repo():
    """(reuse-by-ref "a published version is self-contained" — the
    single-pin property, its expectation inverted by the issue-100
    delta; reference
    `requirements/reuse-by-ref.feature::A published version is
    self-contained`) the fetch returns: a run now DOES fetch the
    factory repo, owner-qualified, as its fetch source — the called
    ref selects a published version, the tag's commit carries the file
    and the runtime tree together, and stage 1 fetches that tree. The
    new pins: the fetch rides a run-time-resolved ref (no ref literal
    anywhere in the file — the called ref is recovered from the
    consumer workflow, not declared), no stage reads the `factory-ref`
    input (the input stays a declared legacy no-op), and the fetch is
    an `actions/checkout` fetch rather than a raw `git clone` (that ban
    stands — a raw run-time clone would be the retired mechanism's
    form)."""
    text = _read(FACTORY)
    # the ban that stands: no raw git clone of the factory repo at run
    # time
    assert "git clone" not in text, (
        "factory.yml still git-clones at run time — the fetch is an "
        "actions/checkout fetch; a raw clone would be the retired "
        "mechanism's form")
    # the inversion: the run now fetches the factory repo,
    # owner-qualified, as the fetch source
    assert "MelvinKl/code-weaver" in text, (
        "factory.yml no longer names the owner-qualified factory repo — "
        "a run fetches it: stage 1's fetch is the owner-qualified "
        "checkout of the factory repo at the called ref")
    # the fetch is an actions/checkout step whose repository and ref
    # ride the run-time-resolved values (no ref literal anywhere in the
    # file — the called ref is recovered, not declared)
    lines = text.splitlines()
    fetch = None
    for i, ln in enumerate(lines):
        if "uses: actions/checkout" in ln and any(
                "repository:" in cont for cont in lines[i + 1:i + 12]):
            fetch = lines[i:i + 12]
            break
    assert fetch is not None, (
        "factory.yml has no actions/checkout step that fetches a "
        "repository — the called version's tree must arrive as an "
        "actions/checkout fetch, not a raw clone")
    assert re.search(
        r"repository:\s*\$\{\{\s*steps\.called-version\.outputs\.called-repo\s*\}\}",
        "\n".join(fetch)), (
        "the fetch does not ride the run-time-resolved repo — the called "
        "version's source is recovered from the consumer workflow, and no "
        "literal repo may stand in the fetch's repository input")
    assert not any(
            re.search(r"ref:\s*(?!\$\{\{)\S", cont) for cont in fetch), (
        "the fetch declares a literal ref — the called ref is recovered "
        "from the consumer workflow at run time, and no ref literal may "
        "stand in the fetch's ref input")
    # no stage reads the factory-ref input (the input stays a declared
    # legacy no-op)
    assert "inputs.factory-ref" not in text, (
        "a stage still reads the factory-ref input — the consumer's "
        "uses: line is the only pin a run makes; the input is a declared "
        "legacy no-op")

def test_no_stage_reads_the_factory_ref_input():
    """(the input the double pin relayed; reference
    `requirements/reuse-by-ref.feature::The whole version is one ref`)
    no step expression in the
    file reads `inputs.factory-ref` anymore — the input stays declared
    (a legacy no-op, so an older consumer's with: block stays
    schema-valid), but the runtime tree is the file's own: reading the
    input would put a second version selection back into the run."""
    text = _read(FACTORY)
    assert "factory-ref:" in text, (
        "the factory-ref input declaration is gone — an older consumer "
        "with: block that passes it must stay schema-valid")
    assert "inputs.factory-ref" not in text, (
        "a stage still reads the factory-ref input — the consumer's "
        "uses: line is the only pin a run makes; the input is a legacy "
        "no-op")
    # and the declared entry is the deprecated no-op (not the old
    # "the stage jobs clone their runtime tree from" contract)
    assert re.search(
        r'(?m)^\s*description:\s*[\"\']?\(legacy\).*no stage reads it', text), (
        "the factory-ref input's declaration no longer marks it as the "
        "legacy no-op")

def test_factory_file_stays_within_the_max_allowed_size():
    """(reuse-by-ref "the factory workflow file stays within the max
    allowed size" — the issue-100 delta's added scenario; reference
    `requirements/reuse-by-ref.feature::The factory workflow file stays
    within the max allowed size`) the measured size of
    `.github/workflows/factory.yml` is at most 500kb — the max allowed
    size for the file: the base64-tarball embed that the issue retires is
    what took the published file past it (528kb when the issue was
    filed). The check reads the figure conservatively, as 500,000 bytes
    (decimal): a file at most that is also under 500×1024, so the pin
    holds under either reading of `kb`. The cap is a checked property of
    the published file — this pins the committed file against it."""
    size = os.path.getsize(os.path.join(ROOT, FACTORY))
    assert size <= 500000, (
        f"the factory workflow file is {size} bytes — past its max "
        f"allowed size (at most 500kb, read conservatively as 500,000 "
        f"bytes)")

def test_factory_file_stores_no_binary_content():
    """(reuse-by-ref "the factory workflow file stores no binary
    content" — the issue-100 delta's added scenario; reference
    `requirements/reuse-by-ref.feature::The factory workflow file stores
    no binary content`) the file is plain text — it decodes, and no NUL
    byte stands anywhere in it — and the runtime tree its steps execute
    is not embedded in the file as a base64 tarball: the retired payload
    was the tarball's base64 across a `CW_EMBEDDED_RUNTIME_TAR` heredoc
    in stage 1's first step (a 76-column wrap — 68 base64 characters a
    line, the heredoc's body the step fed `base64 -d`), and neither the
    heredoc region nor a line of that base64-blob form remains in the
    file (its surviving `base64 -d` is the consumer workflow's
    API-content decode — a short line, a different purpose)."""
    with open(os.path.join(ROOT, FACTORY), "rb") as f:
        data = f.read()
    assert b"\x00" not in data, (
        "the workflow file holds a NUL byte — it stores binary content, "
        "and a workflow file must be plain text")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as e:
        raise AssertionError(
            "the workflow file does not decode as text — it stores "
            f"binary content ({e})") from None
    assert "CW_EMBEDDED_RUNTIME_TAR" not in text, (
        "the workflow file still opens the CW_EMBEDDED_RUNTIME_TAR "
        "heredoc — the retired payload region is back in the file")
    for ln in text.splitlines():
        body = ln.strip()
        if body and re.fullmatch(r"[A-Za-z0-9+/]{64,}={0,2}", body):
            raise AssertionError(
                "the workflow file holds a base64 blob line — the "
                "retired embed's form (the runtime tree's base64 across "
                f"the heredoc's wrapped lines): {body[:40]!r}…")
