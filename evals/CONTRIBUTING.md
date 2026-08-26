# Contributing to Corvos Evals

Thanks for your interest in contributing! This document covers setup and
conventions specific to `evals/`. For the repo-wide process (branching, PR
checklist, issue triage), see the root [CONTRIBUTING.md](../CONTRIBUTING.md).

## Development Setup

**Prerequisites:** Python 3.11+, [uv](https://github.com/astral-sh/uv), a
running Corvos backend

```bash
git checkout dev && git pull origin dev
git checkout -b feature/your-feature-name

uv pip install -e ./evals
cp evals/.env.example evals/.env
```

See [README.md](./README.md) for the full walkthrough of running benchmarks.

## Adding a New Benchmark Suite

1. Create `evals/src/evals/suites/<domain>/<benchmark>/` with `__init__.py`,
   `ingest.py`, `runner.py`, optional `prompt.py`.
2. Implement a `Benchmark` subclass (see `core/registry.py`); compose with
   `core.clients.*`, `core.arms.*`, `core.parse.*`, `core.metrics.*`.
3. Call `register(MyBenchmark())` at the bottom of `<benchmark>/__init__.py`.

The harness talks to Corvos over HTTP only - do not import backend Python
modules.

## Code Style

- Python, PEP 8, formatted with Black
- Never commit real API keys or datasets containing PII

## Pull Requests

Follow the root [Pull Request Checklist](../CONTRIBUTING.md#pull-request-checklist).
All PRs target `dev`. Include the benchmark(s) affected and, where relevant,
before/after report numbers.

## License

By contributing, you agree your contributions are licensed under the
[MIT License](./LICENSE).
