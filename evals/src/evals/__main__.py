"""Module entry point: ``python -m evals ...``.

Delegates to ``core.cli.main``. ``core.cli`` lazily imports
``evals.suites`` so every benchmark gets a chance to register
before argparse builds its subcommand groups.
"""

from __future__ import annotations

from evals.core.cli import main

if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
