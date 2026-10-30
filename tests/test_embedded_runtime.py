"""Unit tests for the release pipeline's rewrite of the published file.

The reusable workflow is the file a target pins, and GitHub fetches only
that file at the called ref — the called ref is not visible to the run's
jobs. The old design answered that by relaying the ref as the
`factory-ref` input (a second pin beside the consumer's uses: line) and
cloning the factory repo at it at run time; the retired design answered
it by rewriting the workflow file on a throwaway release branch at
release time — a push that updates a workflow file, which the
publishing principal is refused (`workflows` is not a permission the
github-actions App can be granted). The restored-and-improved rewrite is
the embedded runtime tree: the tree the stage steps execute (the
.github scripts, the stage scripts, the pi prompt templates) is carried
IN the file — a base64 tarball behind the heredoc in stage 1's first
step. The rewrite is committed to main (the `embed` make target runs
`.github/scripts/embed-runtime.py`), and the tag the release flow cuts
points at main's HEAD — so the file at a published ref carries exactly
the runtime tree of that ref, and a consumer pins the version exactly
once: its uses: line. No stage reads the `factory-ref` input anymore
(it stays declared as a legacy no-op so an older consumer's `with:`
block stays schema-valid), and no run fetches the factory repo.

The pins:
- the payload region of the file (the heredoc body between the
  `<<'CW_EMBEDDED_RUNTIME_TAR'` opener and its terminator) is exactly a
  fresh deterministic build of the repo's runtime tree — a maintainer
  who edited .github/scripts, .github/actions or pi-prompts without
  re-running `make embed` turns the suite red before the release tags;
- the region decodes to a tarball whose extracted tree holds the
  canonical marker files (a curation drift would be silent otherwise);
- no run fetches the factory repo: the file carries no git clone and no
  owner-qualified factory URL, and no stage reads the `factory-ref`
  input (the file's runtime is selected by the called ref alone).

Plain-stdlib by design (no third-party imports): the stage-10 driver
(`make test` → `python3 tests/run.py`) is a stdlib-only plain-python
contract per the Makefile. The embedder is loaded by file path (its
filename is import-safe, but the loader idiom follows
`tests/test_release_contract.py`'s `release-number.py` precedent, and a
target interpreter may not see the .github package layout).
No-argument `test_` functions — discovered automatically by both
runners (`tests/run.py` imports every `tests/test_*.py`; house CI's
"Validator unit tests" step runs `pytest tests/`), so no `Makefile`
`test` target or `tests/run.py` change is needed.
"""
from __future__ import annotations

import base64
import io
import importlib.util
import os
import re
import tarfile

ROOT = os.path.join(os.path.dirname(__file__), "..")
FACTORY = os.path.join(".github", "workflows", "factory.yml")

# The shared-plumbing embedder the workflow file's payload region is
# built (and checked) by. Load it by file path, the way the
# release-contract module loads `release-number.py`.
_spec = importlib.util.spec_from_file_location(
    "embed_runtime", os.path.join(ROOT, ".github", "scripts", "embed-runtime.py"))
embed = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(embed)


def _read(relpath):
    with open(os.path.join(ROOT, relpath)) as f:
        return f.read()


def _payload_bytes(text):
    """The file's payload region decoded to the tarball bytes (base64
    across the region's lines, the heredoc body the stage-1 step feeds
    `base64 -d`)."""
    lines = text.splitlines()
    open_idx, term_idx = embed.payload_region(lines)
    indent = len(lines[open_idx]) - len(lines[open_idx].lstrip(" "))
    region = [ln[indent:] if ln.lstrip() else ln for ln in lines[open_idx + 1:term_idx]]
    blob = "".join(region).encode("ascii")
    return base64.b64decode(blob, validate=True)


def test_factory_file_carries_its_runtime_tree_embedded():
    """(reuse-by-ref "a published version is self-contained" — the
    restored-and-improved rewrite) the workflow file's payload region
    exists exactly once and holds a fresh build of the repo's runtime
    tree — the embed the release pipeline's rewrite commits: the file
    at the tag the release flow cuts carries the tree of that tag, byte
    for byte."""
    text = _read(FACTORY)
    openers = [ln for ln in text.splitlines() if embed.OPEN_MARKER in ln]
    assert len(openers) == 1, (
        f"the workflow file opens the embedded-payload heredoc {len(openers)} "
        "times — stage 1's materialisation step is the file's single "
        "payload region")
    fresh, _raw = embed.build_payload(ROOT)
    _o, term = embed.payload_region(text.splitlines())
    indent = len(text.splitlines()[_o]) - len(text.splitlines()[_o].lstrip(" "))
    region = [ln[indent:] if ln.lstrip() else ln
              for ln in text.splitlines()[_o + 1:term]]
    assert region == fresh, (
        "the embedded runtime tree is STALE — the file's payload differs "
        "from a fresh build of the repo's runtime tree (run `make embed` "
        "in the commit that changed .github/scripts, .github/actions or "
        "pi-prompts; a release cut before the re-embed would publish a "
        "file whose tree is not the tagged tree)")


def test_embedded_tree_holds_the_canonical_runtime_files():
    """(the same scenario, made silent-safe) the payload decodes to a
    tarball whose extracted tree holds the marker files the stage code
    resolves against — a curation drift in the embedder (a prefix lost,
    an exclusion over-broad) would leave a tree the stage steps cannot
    run from, and no other check would name the missing file."""
    blob = _payload_bytes(_read(FACTORY))
    with tarfile.open(fileobj=io.BytesIO(blob)) as t:
        names = set(m.name for m in t.getmembers())
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
            f"the embedded runtime tree is missing {marker} — the "
            "embedder's curation changed under the stage code's "
            "__file__-relative resolution")


def test_no_run_fetches_the_factory_repo():
    """(reuse-by-ref "a published version is self-contained" — the
    single-pin property) no run-time path in the file reaches the
    factory repo: the old mechanism's git clone and its owner-qualified
    URL are gone, so the ref on the consumer's uses: line is the only
    version selection a run makes — there is no second pin to keep in
    step."""
    text = _read(FACTORY)
    assert "git clone" not in text, (
        "factory.yml still git-clones at run time — a run fetching the "
        "factory repo needs a ref, and the called ref is not visible to "
        "the jobs: the double pin is back")
    assert "https://github.com/MelvinKl" not in text and \
        "MelvinKl/code-weaver" not in text, (
        "factory.yml still names an owner-qualified factory repo URL — "
        "the file must stay owner-agnostic: the ref the caller pins is "
        "the only ref in the run")


def test_no_stage_reads_the_factory_ref_input():
    """(the input the double pin relayed) no step expression in the
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
