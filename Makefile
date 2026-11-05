.PHONY: test

# The factory's test stage drives its suite through this target (its driver
# chain checks `make test` first). The runner is stdlib-only plain python:
# a runner whose system python is externally-managed may have no pytest and
# no venv/ensurepip to install one, so the suite must not need it.
test:
	python3 tests/run.py

# The release pipeline's rewrite of the published file is retired:
# .github/workflows/factory.yml is static plain text (it stores no
# binary content), and a maintainer who changes the runtime tree
# (.github/scripts, .github/actions, pi-prompts) commits the tree — the
# tag the release flow cuts points at a commit whose tree is consistent
# with the file, and no per-release rewrite of the file is owed. The
# version's consistency is checked, not rewritten: the contract test
# (tests/test_embedded_runtime.py) fails — in house CI and in the
# factory's own test stage — while the committed file and tree are not
# the one consistent version, and the release flow's publication gate
# (embed-runtime.py --check: the file plain text within the max allowed
# size, the tagged commit's tree carrying the runtime tree the file's
# stage steps execute) runs the same check before the tag — an
# inconsistent version is never published.

