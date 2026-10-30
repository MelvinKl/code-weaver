.PHONY: test embed

# The factory's test stage drives its suite through this target (its driver
# chain checks `make test` first). The runner is stdlib-only plain python:
# a runner whose system python is externally-managed may have no pytest and
# no venv/ensurepip to install one, so the suite must not need it.
test:
	python3 tests/run.py

# The release pipeline's rewrite of the published file: embed the runtime
# tree (.github/scripts, .github/actions, pi-prompts) into
# .github/workflows/factory.yml as the base64 tarball stage 1 materialises,
# so the file at a tag carries the tree of that tag — one ref is one
# version, and a consumer pins nothing besides its uses: line. Run it in
# the commit that changes any of those trees: the embedder is
# deterministic, and the contract test (tests/test_embedded_runtime.py)
# fails — in house CI and in the factory's own test stage — while the
# file's embedding is stale, and the release flow gates publication on
# the same check (a stale version is never published).
embed:
	python3 .github/scripts/embed-runtime.py

