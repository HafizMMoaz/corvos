"""Arm protocol + concrete arms shared across suites.

Concrete arms (``NativePdfArm``, ``CorvosArm``, ``BareLlmArm``) are
imported lazily via ``__getattr__`` so consumers that only need the
protocol - e.g. the registry's ``Arm`` re-export - don't transitively
pull in ``httpx`` providers or the Corvos client unless they
actually use those arms.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .base import Arm, ArmRequest, ArmResult

if TYPE_CHECKING:  # pragma: no cover
    from .bare_llm import BareLlmArm
    from .native_pdf import NativePdfArm
    from .corvos import CorvosArm

__all__ = [
    "Arm",
    "ArmRequest",
    "ArmResult",
    "BareLlmArm",
    "NativePdfArm",
    "CorvosArm",
]


def __getattr__(name: str):  # PEP 562
    if name == "NativePdfArm":
        from .native_pdf import NativePdfArm

        return NativePdfArm
    if name == "CorvosArm":
        from .corvos import CorvosArm

        return CorvosArm
    if name == "BareLlmArm":
        from .bare_llm import BareLlmArm

        return BareLlmArm
    raise AttributeError(f"module 'evals.core.arms' has no attribute {name!r}")
