"""Corvos filesystem middleware (multi-agent flavour)."""

from __future__ import annotations

from .index import build_filesystem_mw
from .middleware import CorvosFilesystemMiddleware

__all__ = [
    "CorvosFilesystemMiddleware",
    "build_filesystem_mw",
]
