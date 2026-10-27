"""The automatic release's version number — issue-#21 release machinery.

A change landing on `main` publishes the next version: the tag is the
**next single increasing number** — the number after the highest
published version of the new scheme (a bare integer tag — no `v`
prefix, no dots), and where no numbered release is published yet the
first release is `1`. The older `vX.Y.Z` tags are not part of the new
number series — they are not numbers — so the numbers of published
releases never repeat and never decrease, and the older tags are left
where they are (workflows pinned to them keep working).

Two shapes, one rule:

  - `next_release_number(published)` — the pure computation;
    `tests/test_release_contract.py` unit-tests it (auto-discovered by
    both runners — the stage-10 driver `python3 tests/run.py` and house
    CI's `pytest tests/`);
  - the CLI form below — one published ref per line on stdin, the next
    tag on stdout — which the release workflow
    (`.github/workflows/release.yml`) pipes the remote's tag list into
    at run time.

Plain-stdlib on purpose: the `gh` CLI is a pre-requisite of the runner
environment (`docs/08`) — and the workflow consumes it, not this
module.
"""
from __future__ import annotations

import re
import sys

_NUMBER_RE = re.compile(r"\d+")


def next_release_number(published: list[str]) -> str:
    """The next automatic release's tag.

    `published` is the repo's published refs (tag names, any series —
    the workflow hands in the remote's whole tag list). Only the
    single-number tags enter the new series — a bare integer, no `v`
    prefix, no dots — and the result is the number after the highest
    one published: `1` where none is, else `N + 1` for the highest
    number `N`. Older `vX.Y.Z` tags are not numbers: they are ignored,
    which is what keeps the number series strictly increasing — never
    a repeat, never a decrease — next to the older tags."""
    nums = [int(t) for t in published if _NUMBER_RE.fullmatch(t)]
    return str((max(nums) if nums else 0) + 1)


def main() -> None:
    """The CLI form: one published ref per line on stdin; the next
    single-number tag on stdout (no refs at all → `1`)."""
    tags = [line.strip() for line in sys.stdin if line.strip()]
    print(next_release_number(tags))


if __name__ == "__main__":
    main()
