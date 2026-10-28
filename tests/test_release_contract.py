"""Unit tests for the issue-#21 automatic-release-on-main contract.

The release workflow (`.github/workflows/release.yml`) fires on the main
branch's advance — the same trigger shape `house-ci.yml` uses — and the
semver scheme is gone from the flow: the retired trigger
(`push: tags: ["v*.*.*"]` — a maintainer pushing a `vX.Y.Z` tag
manually) is replaced by a push to `main`, and no path in the workflow
creates a semver tag. These tests pin the workflow line-based, the way
`tests/test_trigger_contract.py` pins the consumer workflow: a
whole-document `yaml.safe_load` reads `on:` as the boolean `True` under
YAML 1.1, so a whole-document parse is wrong for a workflow's event map.

The scenarios pinned live in
`requirements/auto-release-on-main.feature` ("A change on main
automatically releases a new version" — the trigger half, and the
publication half: the advance is tagged with the next single
increasing number, computed at run time by the shared-plumbing helper,
and published as a GitHub release a target can pin; "The automatic
release takes the next increasing number" — the next-number
computation itself, unit-tested against the helper; "The release flow
no longer carries the semver scheme") and in the adjusted
`reuse-by-ref` scenario "Every published version is a stable ref" (whose
And line — workflows pinned to an older ref keep working — is unchanged:
both tag series stay immutable, pinnable refs) and in the reworked
`reuse-by-ref` scenario "A published version is self-contained" (the
workflow's stage steps are inlined and its runtime tree stashes at the
called ref — the tag needs no pre-tag rewrite: the version a target pins
is one file).


Plain-stdlib by design (no third-party imports): the stage-10 driver
(`make test` → `python3 tests/run.py`) is a stdlib-only plain-python
contract per the Makefile. No-argument `test_` functions — discovered
automatically by both runners (`tests/run.py` imports every
`tests/test_*.py`; house CI's "Validator unit tests" step runs
`pytest tests/`), so no `Makefile`, `tests/run.py` or
`.github/workflows/house-ci.yml` changes are needed.
"""
from __future__ import annotations

import importlib.util
import os
import re

ROOT = os.path.join(os.path.dirname(__file__), "..")
RELEASE_WORKFLOW = os.path.join(".github", "workflows", "release.yml")
SCRIPTS = os.path.join(ROOT, ".github", "scripts")

# The shared-plumbing helper the release workflow pipes the remote's tag
# list into at run time. Its filename carries a hyphen, so a plain import
# cannot reach it — load it by file path (the same `importlib` idiom
# `tests/test_pi_stream.py` uses for `common.py`).
_spec = importlib.util.spec_from_file_location(
    "release_number", os.path.join(SCRIPTS, "release-number.py"))
release_number = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(release_number)


def _read(relpath):
    with open(os.path.join(ROOT, relpath)) as f:
        return f.read()


def _event_map(text):
    """The lines of the workflow's `on:` event map: the `on:` line plus
    the lines below it, up to the next top-level key (a non-blank line at
    zero indentation, e.g. `permissions:`)."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.strip() == "on:":
            block = [line]
            for nxt in lines[i + 1:]:
                if nxt.strip() and not nxt.startswith((" ", "\t")):
                    break
                block.append(nxt)
            return block
    raise AssertionError("release.yml has no `on:` line")


def _push_block(event_map):
    """The lines of the `push:` event: the `push:` line plus the lines
    indented deeper than it, up to the next event key at the same or a
    shallower indentation. [] if no push event is declared."""
    block = []
    in_push = False
    push_indent = 0
    for line in event_map:
        indent = len(line) - len(line.lstrip(" \t"))
        s = line.strip()
        if s.startswith("push:"):
            if in_push and indent <= push_indent:
                break
            in_push = True
            push_indent = indent
            block.append(line)
        elif in_push:
            if s and indent <= push_indent:
                break
            block.append(line)
    return block


def _push_list_value(block, key):
    """The value declared under `key:` in the push block as a list of
    unquoted strings — a flow sequence `[a, b]` on the key line, a block
    sequence of `- item` lines below it, or a single scalar; None if the
    key is undeclared, [] if declared but empty."""
    for i, line in enumerate(block):
        s = line.strip()
        if not s.startswith(key + ":"):
            continue
        rest = s[len(key) + 1:].strip()
        if rest.startswith("[") and rest.endswith("]"):
            els = [e.strip().strip("'\"") for e in rest[1:-1].split(",")]
            return [e for e in els if e] or []
        if not rest:
            vals = []
            for nxt in block[i + 1:]:
                ns = nxt.strip()
                if ns.startswith("- "):
                    vals.append(ns[2:].strip().strip("'\""))
                elif ns:
                    break
            return vals
        return [rest.strip("'\"")]
    return None


def test_release_workflow_fires_on_main_advance():
    """(scenario "A change on main automatically releases a new version" —
    the trigger half of its When; scenario "The release flow no longer
    carries the semver scheme" — "it fires on the main branch's advance")
    the release workflow's push event declares `main` among its branches:
    a change landing on the main branch is what schedules the release
    run."""
    text = _read(RELEASE_WORKFLOW)
    branches = _push_list_value(_push_block(_event_map(text)), "branches")
    assert branches is not None, (
        "release.yml's push event declares no branches — a change landing "
        "on main no longer schedules the release run")
    assert "main" in branches, (
        f"release.yml's push event branches are {branches!r} — main's "
        "advance must schedule the release run")


def test_release_workflow_declares_no_tag_trigger():
    """(scenario "The release flow no longer carries the semver scheme" —
    "rather than on a maintainer's manual tag") the push event declares
    no tag filter of any kind — the retired trigger was
    `push: tags: ["v*.*.*"]`, a maintainer pushing a `vX.Y.Z` tag
    manually; under the new flow a maintainer tag must schedule nothing."""
    text = _read(RELEASE_WORKFLOW)
    tags = _push_list_value(_push_block(_event_map(text)), "tags")
    assert tags is None, (
        f"release.yml's push event still declares a tags trigger "
        f"({tags!r}) — a maintainer's manual tag must not schedule the "
        "release run")


def test_release_workflow_carries_no_semver_tag():
    """(scenario "The release flow no longer carries the semver scheme" —
    "it creates no semver vX.Y.Z tags") no semver tag anywhere in the
    workflow file — header, trigger, or any body step: neither the retired
    `v*.*.*` glob, nor the `vX.Y.Z` placeholder, nor a concrete
    `v<digits>.<digits>.<digits>` tag (which would be the only shape a
    tag-creating step could carry of that scheme)."""
    text = _read(RELEASE_WORKFLOW)
    specs = []
    if "v*.*.*" in text:
        specs.append("the v*.*.* glob")
    if "vX.Y.Z" in text:
        specs.append("the vX.Y.Z placeholder")
    specs += re.findall(r"v\d+\.\d+\.\d+", text)
    assert not specs, (
        f"release.yml still carries semver tag spec(s) {specs!r} — the "
        "semver scheme is gone from the release flow")


def test_next_number_with_no_published_number_is_one():
    """(scenario "The automatic release takes the next increasing number")
    no numbered release published yet — the published ref set is empty, or
    carries only the older `vX.Y.Z` tags — → the first release is `1`."""
    assert release_number.next_release_number([]) == "1"
    assert release_number.next_release_number(
        ["v0.1.3", "v0.1.2", "v0.0.5"]) == "1"


def test_next_number_is_the_number_after_the_highest():
    """(scenario "The automatic release takes the next increasing number"
    — "the new version is tagged with the number after N", "the version
    numbers of published releases never repeat and never decrease")
    numbered releases [1, 2, 3] published → the next is 4; the input
    order is irrelevant, and successive releases grow the series
    strictly — one more than everything already published."""
    assert release_number.next_release_number(["1", "2", "3"]) == "4"
    assert release_number.next_release_number(["3", "1", "2"]) == "4"
    published = []
    for expected in "1234":
        assert release_number.next_release_number(published) == expected
        published.append(expected)
    assert release_number.next_release_number(published) == "5"


def test_older_semver_tags_stay_out_of_the_number_series():
    """(scenario "The automatic release takes the next increasing number")
    the published set mixed with older `vX.Y.Z` tags — the older tags are
    not numbers and are ignored: they neither lower nor advance the new
    series, which stays strictly increasing next to them."""
    assert release_number.next_release_number(["v0.1.3", "2"]) == "3"
    assert release_number.next_release_number(
        ["v0.1.3", "v0.0.5", "2", "10"]) == "11"


def test_workflow_tags_the_computed_single_number():
    """(scenario "A change on main automatically releases a new version"
    — the publication half; "The automatic release takes the next
    increasing number" — the tag it creates) the workflow computes the
    number at run time with the shared-plumbing helper and creates the
    tag from exactly that value — no maintainer tags anything by hand,
    and the tag is a single increasing number, not a semver ref."""
    text = _read(RELEASE_WORKFLOW)
    assert "release-number.py" in text, (
        "release.yml does not compute the next number with the "
        "shared-plumbing helper (.github/scripts/release-number.py) at "
        "run time")
    assert re.search(r'git tag "\$NEXT"', text), (
        "release.yml does not create the tag from the computed value — "
        "the main-branch advance must be tagged with the next single "
        "increasing number")


def test_workflow_creates_a_github_release_from_the_tag():
    """(scenario "A change on main automatically releases a new version"
    — "the release is a GitHub release that a target can pin like any
    published version") the workflow creates the GitHub release from the
    computed tag with the `gh release create` mechanism (the `gh` CLI is
    a documented runner pre-requisite, `docs/08`) — publication happens
    without any maintainer action."""
    text = _read(RELEASE_WORKFLOW)
    assert re.search(r'gh release create "\$NEXT"', text), (
        "release.yml does not create a GitHub release from the computed "
        "tag — a target could not pin the new version")


def test_release_publishes_with_the_default_token():
    """(scenario "A change on main automatically releases a new version"
    — the publication half) the flow publishes the tag and the release
    with the default GITHUB_TOKEN — no special token, no secret: the tag
    points at main's HEAD (a commit the push already delivered to the
    remote), so the tag push uploads only the tag object — no new commit
    content, no workflow-file update in the push. The github-actions App
    behind the GITHUB_TOKEN can never be granted the `workflows`
    permission (that is not a scope available to it, and a workflow
    claiming it in its permissions block is rejected as invalid — a run
    dies at 0s) — so the flow must never push a commit that updates a
    workflow file, and it never does. The permissions block grants only
    what publication needs: `contents: write` (the tag ref and the
    release object)."""
    text = _read(RELEASE_WORKFLOW)
    assert re.search(r"(?m)^  contents: write", text), (
        "release.yml's permissions block no longer grants contents: write "
        "— publishing the tag ref and the release object needs it")
    assert not re.search(r"(?m)^  workflows:", text), (
        "release.yml's permissions block claims the workflows scope — it "
        "is not available to the GITHUB_TOKEN's App, and a workflow "
        "claiming it is rejected as invalid (a run dies at 0s)")
    assert "secrets.GH_TOKEN" not in text, (
        "release.yml reads a special GH_TOKEN secret — the tokenless flow "
        "publishes the tag with the default GITHUB_TOKEN")
    assert "GH_TOKEN: ${{ github.token }}" in text, (
        "the Publish step's env does not map GH_TOKEN to the github.token "
        "context — the gh CLI refuses to run in an Actions job unless "
        "GH_TOKEN is set (no GITHUB_TOKEN fallback); the context is the "
        "same default token that pushes the tag")
    assert 'git push origin "refs/tags/$NEXT"' in text, (
        "the tag push no longer goes out the checkout's origin remote "
        "with the embedded GITHUB_TOKEN — the push URL must not embed a "
        "special token")


def test_release_tags_main_head_not_a_throwaway_branch():
    """(the same scenario — the publication-side invariant that makes the
    tokenless flow possible) the tag points at main's HEAD — the commit
    this push delivered, already on the remote. The flow cuts no
    throwaway branch: the retired design rewrote the reusable
    workflow's own action refs on a throwaway release branch and tagged
    that rewritten commit — its push uploaded a new commit updating a
    workflow file, the one push the publishing principal is refused. The
    rewrite is gone with the consolidation (factory.yml is
    self-contained — its stage steps are inlined) — so the tag is cut
    from main's HEAD itself, and the push uploads only the tag object."""
    text = _read(RELEASE_WORKFLOW)
    assert "git checkout -B" not in text, (
        "release.yml still cuts a throwaway release branch — the tag "
        "points at main's HEAD; there is no pre-tag commit to cut")
    assert re.search(r'git tag "\$NEXT" HEAD', text), (
        "release.yml no longer tags HEAD with the computed number")


def _doc_surfaces():
    """[(relpath, text)] — the README plus every arc42 chapter file under
    `docs/` (one chapter per file)."""
    surfaces = [("README.md", _read("README.md"))]
    docs = os.path.join(ROOT, "docs")
    surfaces += [(os.path.join("docs", fname),
                  _read(os.path.join("docs", fname)))
                 for fname in sorted(os.listdir(docs))
                 if fname.endswith(".md")]
    return surfaces


def _paragraph(text, heading):
    """The paragraph that opens with `heading` — from the heading to the
    next blank line (the end of the text where there is none), with its
    whitespace runs collapsed to single spaces: prose wraps at any width,
    and a marker must survive re-wrapping."""
    i = text.index(heading)
    j = text.find("\n\n", i)
    para = text[i:] if j == -1 else text[i:j]
    return " ".join(para.split())


def test_readme_upgrading_section_describes_the_new_flow():
    """(scenarios "A change on main automatically releases a new version"
    and "The automatic release takes the next increasing number" — the
    README surface) the README's "Upgrading is a ref bump" paragraph
    describes the new mechanism: a push to the factory's main branch
    publishes the next single increasing number as a GitHub release."""
    para = _paragraph(_read("README.md"), "**Upgrading is a ref bump**")
    assert "main" in para, (
        "the README's Upgrading paragraph no longer names the main branch "
        f"advance — {para!r}")
    assert "single increasing number" in para, (
        "the README's Upgrading paragraph no longer states the single "
        f"increasing number scheme — {para!r}")


def test_chapter8_upgrades_paragraph_describes_the_new_flow():
    """(the same two scenarios — the arc42 surface) chapter 8's "Upgrades
    are a ref bump" paragraph describes the new mechanism (fires on the
    main branch's advance; publishes the next single increasing number as
    a GitHub release) and keeps the retained stability sentence (tags are
    immutable → targets pinned to an older ref keep working)."""
    para = _paragraph(_read("docs/08-deployment-view.md"),
                      "**Upgrades are a ref bump.**")
    assert "main" in para, (
        "chapter 8's Upgrades paragraph no longer names the main branch "
        f"advance — {para!r}")
    assert "single increasing number" in para, (
        "chapter 8's Upgrades paragraph no longer states the single "
        f"increasing number scheme — {para!r}")
    assert "tags are immutable" in para, (
        "chapter 8's Upgrades paragraph lost the retained tag-immutability "
        "sentence — targets pinned to an older ref keep working")


def test_no_documented_surface_states_the_retired_mechanism():
    """(scenario "The release flow no longer carries the semver scheme" —
    the documentation surfaces) no surface — the README or any arc42
    chapter — still states the retired mechanism: `release.yml`
    "turns a `vX.Y.Z` tag into a GitHub release" (chapter 8's form) or
    "tag `vX.Y.Z` → GitHub release" (the README's form). A doc that still
    describes a maintainer-tagged semver release after this change is a
    false doc."""
    retired = (
        "turns a `vX.Y.Z` tag into a GitHub release",
        "tag `vX.Y.Z` → GitHub release",
    )
    for relpath, text in _doc_surfaces():
        text = " ".join(text.split())  # whitespace-collapsed: a marker
        # split across a wrap must still be caught
        for marker in retired:
            assert marker not in text, (
                f"{relpath} still states the retired release mechanism "
                f"({marker!r})")
