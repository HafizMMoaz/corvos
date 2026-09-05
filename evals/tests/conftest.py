"""Shared pytest fixtures for corvos-evals."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from evals.core.config import Config


@pytest.fixture
def tmp_env(monkeypatch, tmp_path: Path) -> Path:
    """Isolate env vars + filesystem state per test.

    Wipes every ``CORVOS_*`` / ``OPENROUTER_*`` / ``EVAL_*`` var so a
    test that wants a specific credential mode can ``monkeypatch.setenv``
    just what it needs without leakage from the caller's shell.
    """

    for key in list(os.environ):
        if key.startswith(("CORVOS_", "OPENROUTER_", "EVAL_")):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("EVAL_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("EVAL_REPORTS_DIR", str(tmp_path / "reports"))
    return tmp_path


@pytest.fixture
def isolated_config(tmp_env: Path) -> Config:  # noqa: ARG001
    from evals.core.config import load_config

    return load_config()
