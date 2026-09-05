"""Context-window summarization with Corvos protected sections."""

from __future__ import annotations

from typing import Any

from deepagents.backends import StateBackend
from langchain_core.language_models import BaseChatModel

from app.agents.chat.shared.middleware import create_corvos_compaction_middleware


def build_compaction_mw(llm: BaseChatModel) -> Any:
    return create_corvos_compaction_middleware(llm, StateBackend)
