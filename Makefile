# iil-enrichment — Developer Makefile

.PHONY: setup install test test-v lint clean help

# venv-first (platform#2591 K3): make setup fuellt ./.venv, make test nutzt es
PYTHON := $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
PIP    := pip

help:
	@echo "Available targets:"
	@echo "  setup     — frisches .venv + pip install -e '.[dev]' (Cold-Start-Einstieg)"
	@echo "  install   — pip install -e '.[dev]' in die aktive Umgebung"
	@echo "  test      — pytest (quiet)"
	@echo "  test-v    — pytest (verbose)"
	@echo "  lint      — ruff check + format --check (deckungsgleich mit _ci-pypi.yml)"
	@echo "  clean     — remove __pycache__ + .pytest_cache"

setup:
	python3 -m venv .venv
	.venv/bin/pip install -U pip
	.venv/bin/pip install -e ".[dev]" || .venv/bin/pip install -e .
	.venv/bin/pip install pytest

install:
	$(PIP) install -e ".[dev]"

test:
	$(PYTHON) -m pytest tests/ --tb=short -q

test-v:
	$(PYTHON) -m pytest tests/ --tb=short -v

lint:
	ruff check .
	ruff format --check .

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -name '*.pyc' -delete 2>/dev/null || true
	@echo "Cleaned."
