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
no longer carries the semver scheme"; "A push that changes only the
consumer workflow publishes no release" — the issue-#79 delta: the
helper's changed-files skip shape unit-tested, the workflow's
dedicated pre-publish step pinned line-based, and the Publish step's
payload-independent backstop pinned (the same predicate asked over the
committed tree — a run's event metadata is not a contract); "The
release notes name
the changes since the previous release" — the notes' range base is the
predecessor release's tag restricted to the numbered series, the notes
reference it (the first-commit fallback only where no predecessor
exists), and the changelog's one row per commit over the range base →
HEAD range pinned line-based; "The release notes are never empty for
a release that publishes changes" — the full-history checkout and the
changelog enumerating one row per commit over the whole range (not a
pathspec subset of it) pinned line-based; "The release changelog is a
table of the commits since the last release" — the issue-#18 delta:
the changelog is a markdown table, its header's per-commit columns and
each row's title, author, hash and datetime pinned line-based) and in
the adjusted
`reuse-by-ref` scenario "Every published version is a stable ref" (whose
And line — workflows pinned to an older ref keep working — is unchanged:
both tag series stay immutable, pinnable refs) and in the reworked
`reuse-by-ref` scenario "A published version is self-contained" (the
workflow's stage steps are inlined in the file, which stores no binary
payload — the tag needs no pre-tag rewrite: the whole version — the
stage steps and the runtime tree, the trigger's artifact carrying the
tree across jobs — is selected by that one ref).


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


def _first_line_index(lines, marker):
    """The index of the first line holding `marker`, or -1 if none —
    the line-ordering form of the module's line-based pins: a step that
    must run before another must appear earlier in the file."""
    for i, line in enumerate(lines):
        if marker in line:
            return i
    return -1


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
    """(scenario "A change on main automatically releases a new version"
    — its full shape as adjusted by the issue-#79 delta, which added the
    And precondition "the change's files are not confined to the consumer
    workflow .github/workflows/code-weaver.yml", and the trigger half of
    its When: the trigger still fires on any main advance — a change
    confined to the consumer workflow fires it too — and the confinement
    the precondition names is handled by the flow's pre-publish check
    (the changed-files check, which exits a consumer-workflow-only push
    before any publication), not by the trigger; scenario "The release
    flow no longer carries the semver scheme" — "it fires on the main
    branch's advance"; reference
    `requirements/auto-release-on-main.feature::A change on main
    automatically releases a new version`,
    `requirements/auto-release-on-main.feature::The release flow no longer
    carries the semver scheme`)
    the release workflow's push event declares `main` among its branches: a
    change landing on the main branch is what schedules the release run."""
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
    "rather than on a maintainer's manual tag"; reference
    `requirements/auto-release-on-main.feature::The release flow no
    longer carries the semver scheme`) the push event declares
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
    "it creates no semver vX.Y.Z tags"; reference
    `requirements/auto-release-on-main.feature::The release flow no
    longer carries the semver scheme`) no semver tag anywhere in the
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
    """(scenario "The automatic release takes the next increasing number";
    reference
    `requirements/auto-release-on-main.feature::The automatic release
    takes the next increasing number`)
    no numbered release published yet — the published ref set is empty, or
    carries only the older `vX.Y.Z` tags — → the first release is `1`."""
    assert release_number.next_release_number([]) == "1"
    assert release_number.next_release_number(
        ["v0.1.3", "v0.1.2", "v0.0.5"]) == "1"


def test_next_number_is_the_number_after_the_highest():
    """(scenario "The automatic release takes the next increasing number"
    — "the new version is tagged with the number after N", "the version
    numbers of published releases never repeat and never decrease";
    reference
    `requirements/auto-release-on-main.feature::The automatic release
    takes the next increasing number`)
    numbered releases [1, 2, 3] published → the next is 4; the input order
    is irrelevant, and successive releases grow the series strictly — one
    more than everything already published."""
    assert release_number.next_release_number(["1", "2", "3"]) == "4"
    assert release_number.next_release_number(["3", "1", "2"]) == "4"
    published = []
    for expected in "1234":
        assert release_number.next_release_number(published) == expected
        published.append(expected)
    assert release_number.next_release_number(published) == "5"


def test_older_semver_tags_stay_out_of_the_number_series():
    """(scenario "The automatic release takes the next increasing number";
    reference
    `requirements/auto-release-on-main.feature::The automatic release
    takes the next increasing number`)
    the published set mixed with older `vX.Y.Z` tags — the older tags are
    not numbers and are ignored: they neither lower nor advance the new
    series, which stays strictly increasing next to them."""
    assert release_number.next_release_number(["v0.1.3", "2"]) == "3"
    assert release_number.next_release_number(
        ["v0.1.3", "v0.0.5", "2", "10"]) == "11"


def test_workflow_tags_the_computed_single_number():
    """(scenario "A change on main automatically releases a new version"
    — the publication half; "The automatic release takes the next
    increasing number" — the tag it creates; reference
    `requirements/auto-release-on-main.feature::A change on main
    automatically releases a new version`,
    `requirements/auto-release-on-main.feature::The automatic release
    takes the next increasing number`) the workflow computes the
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
    published version"; reference
    `requirements/auto-release-on-main.feature::A change on main
    automatically releases a new version`)
    the workflow creates the GitHub release from the computed tag with the
    `gh release create` mechanism (the `gh` CLI is a documented runner
    pre-requisite, `docs/08`) — publication happens without any maintainer
    action."""
    text = _read(RELEASE_WORKFLOW)
    assert re.search(r'gh release create "\$NEXT"', text), (
        "release.yml does not create a GitHub release from the computed "
        "tag — a target could not pin the new version")


def test_release_publishes_with_the_default_token():
    """(scenario "A change on main automatically releases a new version"
    — the publication half; reference
    `requirements/auto-release-on-main.feature::A change on main
    automatically releases a new version`)
    the flow publishes the tag and the release with the default
    GITHUB_TOKEN — no special token, no secret: the tag points at main's
    HEAD (a commit the push already delivered to the remote), so the tag
    push uploads only the tag object — no new commit content, no
    workflow-file update in the push. The github-actions App behind the
    GITHUB_TOKEN can never be granted the `workflows` permission (that is
    not a scope available to it, and a workflow claiming it in its
    permissions block is rejected as invalid — a run dies at 0s) — so the
    flow must never push a commit that updates a workflow file, and it
    never does. The permissions block grants only what publication needs:
    `contents: write` (the tag
    ref and the release object)."""
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
    tokenless flow possible; reference
    `requirements/auto-release-on-main.feature::A change on main
    automatically releases a new version`)
    the tag points at main's HEAD — the commit this push delivered, already
    on the remote. The flow cuts no throwaway branch: the retired design
    rewrote the reusable workflow's own action refs on a throwaway release
    branch and tagged that rewritten commit — its push uploaded a new
    commit updating a workflow file, the one push the publishing principal
    is refused. The rewrite is gone with the consolidation (factory.yml is
    self-contained — its stage steps are inlined) — so the tag is cut from
    main's HEAD itself, and the push uploads only the tag object."""
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
    README surface; reference
    `requirements/auto-release-on-main.feature::A change on main
    automatically releases a new version`,
    `requirements/auto-release-on-main.feature::The automatic release
    takes the next increasing number`) the README's "Upgrading is a ref
    bump" paragraph
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
    """(the same two scenarios — the arc42 surface; reference
    `requirements/auto-release-on-main.feature::A change on main
    automatically releases a new version`,
    `requirements/auto-release-on-main.feature::The automatic release
    takes the next increasing number`) chapter 8's "Upgrades
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
    the documentation surfaces; reference
    `requirements/auto-release-on-main.feature::The release flow no
    longer carries the semver scheme`) no surface — the README or any arc42
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


def test_re_run_at_an_already_tagged_head_publishes_nothing():
    """(reuse-by-ref "Every published version is a stable ref" — the
    added And line: a re-run of the release at an unchanged HEAD
    publishes nothing — one tag per commit, so a number is never spent
    on a duplicate; reference
    `requirements/reuse-by-ref.feature::Every published version is a
    stable ref`) the guard is the helper's second pure function:
    fed the remote's whole `git ls-remote --tags` line list and a commit
    sha, it names the numbered tag pointing at that sha — a non-empty
    answer is the workflow's skip signal (a re-run of the flow at an
    unchanged HEAD exits before the tag, publishing nothing). Annotated
    tags' peeled `sha\trefs/tags/<name>^{}` lines never match, and the
    older `vX.Y.Z` series is not a number."""
    lines = [
        "abc123\trefs/tags/12",
        "abc123\trefs/tags/13",
        "def456\trefs/tags/13^{}",
        "def456\trefs/tags/v0.1.0^{}",
        "abc123\trefs/tags/v0.1.0",
        "def456\trefs/tags/14",
    ]
    assert release_number.published_at(lines, "abc123") == ["12", "13"]
    assert release_number.published_at(lines, "def456") == ["14"]
    assert release_number.published_at(lines, "nope") == []
    assert release_number.published_at([], "abc123") == []


def test_changed_files_confined_to_the_consumer_workflow_skip():
    """(scenario "A push that changes only the consumer workflow
    publishes no release" — "the push's only changed file is the
    consumer workflow .github/workflows/code-weaver.yml"; reference
    `requirements/auto-release-on-main.feature::A push that changes
    only the consumer workflow publishes no release`)
    a push whose change set is confined to the consumer workflow — at
    least one changed file, and every changed file the consumer
    workflow file — is the release flow's skip signal: a version is the
    factory workflow and its runtime tree as one published version, never
    the consumer's own workflow file, so the push changes nothing a
    published version carries and must spend no release number."""
    changed = [".github/workflows/code-weaver.yml"]
    assert release_number.consumer_workflow_only(changed) is True
    # the confinement is per-file: any multiplicity of entries of that
    # one file is still confined to it
    assert release_number.consumer_workflow_only(changed * 3) is True


def test_a_change_reaching_a_version_file_does_not_skip():
    """(the same scenario — "a later push whose change set reaches the
    published version publishes the next release"; reference
    `requirements/auto-release-on-main.feature::A push that changes
    only the consumer workflow publishes no release`)
    a change set that reaches a version file — the factory workflow or
    any file of the runtime tree the version carries — is not confined to
    the consumer workflow, so the skip predicate is false and the flow
    publishes the next release for it."""
    for version_file in (".github/workflows/factory.yml",
                         ".github/scripts/common.py",
                         ".github/actions/plan-stage/stage.py",
                         "pi-prompts/plan.md"):
        assert release_number.consumer_workflow_only([version_file]) is False, (
            f"{version_file} is part of the published version (the factory "
            "workflow and its runtime tree as one published version) — a "
            "change reaching it must not skip")


def test_the_consumer_workflow_plus_any_other_file_does_not_skip():
    """(the adjusted scenario "A change on main automatically releases
    a new version" — the "not confined" half of its added precondition
    "the change's files are not confined to the consumer workflow
    .github/workflows/code-weaver.yml": a change whose files are not
    confined to the consumer workflow still releases the next version;
    reference
    `requirements/auto-release-on-main.feature::A change on main
    automatically releases a new version`,
    `requirements/auto-release-on-main.feature::A push that changes
    only the consumer workflow publishes no release`)
    the consumer workflow plus at least one other changed file — the
    change set is not confined to the consumer workflow (the skip
    predicate is the scenario's confinement wording exactly,
    deliberately not generalised to "no changed file reaches a version
    file") — so the skip predicate is false and the flow publishes."""
    assert release_number.consumer_workflow_only(
        [".github/workflows/code-weaver.yml", "README.md"]) is False
    assert release_number.consumer_workflow_only(
        ["README.md", ".github/workflows/code-weaver.yml"]) is False


def test_an_empty_change_set_does_not_skip():
    """(the same scenario — its "no version number is spent" protection
    must not swallow the flow's other no-op: a re-run at an unchanged
    HEAD, whose change set is empty and whose no-op protection is the
    one-tag-per-commit guard (`reuse-by-ref` "Every published version
    is a stable ref"); reference
    `requirements/auto-release-on-main.feature::A push that changes
    only the consumer workflow publishes no release`,
    `requirements/reuse-by-ref.feature::Every published version is a
    stable ref`)
    an empty change set is not confined to the consumer workflow — it
    names no changed file at all — so the skip predicate is false and
    the guard's case stays the guard's."""
    assert release_number.consumer_workflow_only([]) is False


def test_workflow_runs_the_changed_files_check_as_a_pre_publish_step():
    """(scenario "A push that changes only the consumer workflow
    publishes no release" — "the skip is achieved by the release flow
    checking the push's changed files before publishing" (this plan
    takes the check's branch of the scenario's either/or — the trigger
    stays pinned to fire on the main branch's advance) — and "no new
    version tag is created and no new GitHub release is published", "no
    version number is spent on a version whose content did not change";
    reference
    `requirements/auto-release-on-main.feature::A push that changes
    only the consumer workflow publishes no release`)
    release.yml runs the helper's changed-files shape as a dedicated
    pre-publish step — after the version-consistency gate, before the
    Publish step — and exits (a green no-op, like the
    one-tag-per-commit guard) where the skip signal is non-empty: a
    change set confined to the consumer workflow exits the step before
    a number is materialised, a tag is created, or a release is
    published."""
    lines = _read(RELEASE_WORKFLOW).splitlines()
    gate = _first_line_index(lines, "embed-runtime.py --check")
    check = _first_line_index(lines, "release-number.py --changed-files")
    tag = _first_line_index(lines, r'git tag "$NEXT" HEAD')
    assert check != -1, (
        "release.yml does not run the changed-files check — the helper's "
        "--changed-files shape (one changed file name per line on stdin, "
        "non-empty output the skip signal) must be a step of the flow: a "
        "push whose changed files are confined to the consumer workflow "
        "would otherwise spend a release number on a version whose "
        "content did not change")
    assert gate != -1 and tag != -1 and gate < check < tag, (
        "the changed-files check is not a dedicated pre-publish step — it "
        "must sit after the version-consistency gate and before the "
        "Publish step, so a skipped push exits cleanly before a number is "
        "materialised, a tag is created, or a release is published")
    skip_test = _first_line_index(lines, r'[ -n "$SKIP" ]')
    skip_exit = _first_line_index(lines, "exit 0")
    assert skip_test != -1 and skip_exit != -1 and skip_test < skip_exit, (
        "the pre-publish step does not test the skip signal's "
        "non-emptiness and exit (a green no-op) on it")
    assert skip_exit < tag, (
        "the step's skip exit comes after the tag — a skipped push must "
        "exit before any tag is created")


def test_publish_step_carries_the_payload_independent_backstop():
    """(scenario "A push that changes only the consumer workflow
    publishes no release" — the backstop half; reference
    `requirements/auto-release-on-main.feature::A push that changes
    only the consumer workflow publishes no release`)
    the pre-publish step's input is the push event's metadata, and a
    run is not bound to hand it over as the helper expects — the event
    metadata is not a contract. The Publish step therefore re-asks the
    same changed-files predicate over the committed tree (the
    advance's range base → HEAD diff, the input the notes' range
    already computes): a range confined to the consumer's own workflow
    file exits the step before the tag — the skip fires from the
    payload where it can and from the tree where it cannot, and a
    number is spent only where a published version's content actually
    changed."""
    lines = _read(RELEASE_WORKFLOW).splitlines()
    tag = _first_line_index(lines, r'git tag "$NEXT" HEAD')
    assert tag != -1, "the workflow is not the pinned release shape"
    backstop = _first_line_index(lines, "CONSUMER_ONLY=$(git diff")
    assert backstop != -1, (
        "the Publish step does not re-ask the changed-files predicate "
        "over the committed tree — a payload the pre-publish helper did "
        "not read as consumer-only would spend a number on a version "
        "whose content did not change")
    assert backstop < tag, (
        "the backstop is not before the tag — a consumer-only advance "
        "must exit before any tag is created")


def test_structure_gate_sits_between_the_consistency_gate_and_the_changed_files_check():
    """(scenario "A workflow file the runner's parser mis-reads publishes
    no version"; reference
    `requirements/auto-release-on-main.feature::A workflow file the
    runner's parser mis-reads publishes no version`)
    release.yml runs the helper's structure gate — the one that fails a
    file a standard engine cannot parse, a step that declares keys after
    its run block (the shape the runner's workflow parser diverges on:
    the dedent that ends the block inside the step mapping, or a key on
    the block line — issue #106's collapsed run graph), or a run block
    past the giant-body budget — as a dedicated pre-tag step: after the
    version-consistency gate and before the changed-files check, failing
    the run with the exact cause before any tag is created, so a version
    whose jobs the runner mis-parses is never published and a target pin
    never lands on it."""
    lines = _read(RELEASE_WORKFLOW).splitlines()
    check = _first_line_index(lines, "embed-runtime.py --check")
    structure = _first_line_index(lines, "embed-runtime.py --verify-structure")
    skip = _first_line_index(lines, "release-number.py --changed-files")
    tag = _first_line_index(lines, r'git tag "$NEXT" HEAD')
    assert check != -1 and structure != -1 and skip != -1 and tag != -1, (
        "release.yml lost one of its pre-tag gates — the version-"
        "consistency gate, the workflow-structure gate (the parser-safe "
        "shape the runner's workflow parser is exercised on), and the "
        "changed-files check")
    assert check < structure < skip < tag, (
        "the structure gate is not a dedicated pre-tag step — it must "
        "sit after the version-consistency gate and before the "
        "changed-files check, so a file the runner's parser mis-reads "
        "fails the run with the exact cause before a tag is created")
    window = lines[structure:structure + 12]
    assert any(l.strip() == "exit 1" for l in window), (
        "the structure gate does not fail the run — a file the runner's "
        "parser mis-reads must exit the flow non-zero, before the tag")
    assert not any(l.strip() == "exit 0" for l in window), (
        "the structure gate exits zero on an unsafe file — a version "
        "whose jobs the runner mis-parses must not be published")


def test_release_notes_name_the_changes_since_the_previous_release():
    """(scenario "The release notes name the changes since the
    previous release"; reference
    `requirements/auto-release-on-main.feature::The release notes name
    the changes since the previous release`)
    for a release with a predecessor release the notes' changed-since
    reference is the predecessor release and not the first commit:
    release.yml derives the range base from the predecessor release's
    tag, restricted to the numbered series (the scheme is a bare
    integer — no `v` prefix, no dots — the older `v`-prefixed semver
    tags stay out of it, so none can name the reference), keeps the
    first-commit fallback for a release with no predecessor only, and
    the notes' changelog is a table with one row per commit in the
    branch since the predecessor release — the `git log` over the
    range base → HEAD range (the whole range), with the notes'
    range-base reference line below it."""
    lines = _read(RELEASE_WORKFLOW).splitlines()
    prev = _first_line_index(lines, "PREV=$(git describe")
    assert prev != -1, (
        "release.yml no longer computes the notes' range base — the "
        "changed-since reference must be the predecessor release's tag")
    assert "--match '[0-9]*'" in lines[prev], (
        f"the range base is not derived from the numbered series — "
        f"{lines[prev]!r}: an unrestricted describe would also name "
        "the older `v`-prefixed semver tags, and the notes' "
        "changed-since reference would be a tag of the retired scheme")
    base = _first_line_index(
        lines, "RANGEFROM=${PREV:-$(git rev-list --max-parents=0 HEAD)}")
    assert base != -1, (
        "the range base is no longer the dichotomy the scenario "
        "encodes — the predecessor release's tag where one exists, the "
        "first commit only where it does not")
    changelog = _first_line_index(lines, 'git log "$RANGEFROM"..HEAD')
    assert changelog != -1, (
        "the notes' changelog no longer enumerates one row per commit "
        "in the branch since the range base")
    notes = _first_line_index(lines, "${PREV:-the first commit}")
    assert notes != -1, (
        "the notes do not reference the range base — with the "
        "predecessor release where one exists, the first commit only "
        "where there is no predecessor")
    assert prev < base < changelog < notes, (
        "the notes' reference is not the range base computed above it "
        "— the computation, the changelog and the notes must sit in "
        "that order in the Publish step")


def test_release_notes_are_never_empty_for_a_release_that_publishes_changes():
    """(scenario "The release notes are never empty for a release
    that publishes changes"; reference
    `requirements/auto-release-on-main.feature::The release notes are
    never empty for a release that publishes changes`)
    a release published for a push that changed at least one file
    carries a changelog table that is not empty: the checkout fetches
    full history (a shallow checkout's object database carries no
    tags, so a release with a predecessor would compute its range base
    as the shallow clone's "first commit," which is HEAD itself, and
    the enumeration behind it prints nothing — full history puts the
    predecessor's tag in the database and the real first commit at a
    first release's range base), and the changelog enumerates one row
    per commit over the range base → HEAD range — the whole range, not
    a pathspec subset of it (a push that changes files elsewhere still
    publishes, and a restricted enumeration would print no row for
    it)."""
    lines = _read(RELEASE_WORKFLOW).splitlines()
    checkout = _first_line_index(lines, "actions/checkout")
    depth = _first_line_index(lines, "fetch-depth: 0")
    assert checkout != -1 and depth != -1 and checkout < depth, (
        "release.yml's checkout does not fetch full history (the "
        "factory workflow's own stage jobs' fetch-depth: 0 idiom) — a "
        "shallow object database carries no tags, so a release with a "
        "predecessor would fall back to the shallow clone's "
        "'first commit,' which is HEAD itself, and the notes' table "
        "would print empty for a release that publishes changes")
    changelog = _first_line_index(lines, 'git log "$RANGEFROM"..HEAD')
    assert changelog != -1, (
        "release.yml does not enumerate the notes' changelog as one "
        "row per commit over the range base → HEAD range")
    assert " -- " not in lines[changelog], (
        f"the notes' changelog enumeration is restricted to a path "
        f"subset of the range — {lines[changelog]!r}: a push that "
        "changes commits outside that subset would publish a release "
        "whose table is empty")


def test_release_changelog_is_a_table_of_the_commits_since_the_last_release():
    """(scenario "The release changelog is a table of the commits
    since the last release"; reference
    `requirements/auto-release-on-main.feature::The release changelog
    is a table of the commits since the last release`)
    a release published whose branch carries commits since the previous
    release renders its changelog as a table: the changelog is a
    markdown table (its header line and the column-separator line that
    follow it — printed even where the range is empty, so the
    changelog is never the empty string), the table carries one row
    per commit in the branch since the previous release (the
    `git log` enumerates the range base → HEAD range above the table
    it renders), and each row carries the commit's title, the
    commit's author, the commit's hash and the commit's datetime — all
    four fields in the pretty format, in the header's column order.
    """
    lines = _read(RELEASE_WORKFLOW).splitlines()
    header = _first_line_index(lines, "| Title | Author | Hash | Datetime |")
    assert header != -1, (
        "the changelog is not a table — the changelog computation "
        "prints no markdown table header line for its per-commit "
        "columns")
    separator = _first_line_index(lines, "|---|---|---|---|")
    assert separator == header + 1, (
        "the table's header line is not followed by its "
        "column-separator line — the changelog would not render as a "
        "table")
    enum = _first_line_index(lines, 'git log "$RANGEFROM"..HEAD')
    assert enum != -1 and enum < header, (
        "the changelog's rows are not enumerated one per commit over "
        "the range base → HEAD range (since the previous release) "
        "above the table they render")
    fmt = _first_line_index(lines, "--pretty=format:")
    assert fmt != -1, (
        "the changelog's rows carry no per-commit fields — the "
        "enumeration has no pretty format")
    for field in ("%s", "%an", "%h", "%ad"):
        assert field in lines[fmt], (
            f"the changelog's row format lacks its {field} field — "
            "each row must carry the commit's title, its author, its "
            "hash and its datetime")
    assert "--date=" in lines[fmt], (
        "the changelog's datetime field has no date format — the "
        "row's datetime column would print git's internal format")
