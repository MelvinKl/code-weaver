.PHONY: test

# The factory's test stage drives its suite through this target (its driver
# chain checks `make test` first). The runner is stdlib-only plain python:
# a runner whose system python is externally-managed may have no pytest and
# no venv/ensurepip to install one, so the suite must not need it.
test:
	python3 tests/run.py
