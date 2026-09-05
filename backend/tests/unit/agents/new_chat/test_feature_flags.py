"""Tests for the agent feature-flag system."""

from __future__ import annotations

import pytest

from app.agents.chat.multi_agent_chat.shared.feature_flags import (
    AgentFeatureFlags,
    reload_for_tests,
)

pytestmark = pytest.mark.unit


def _clear_all(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in [
        "CORVOS_DISABLE_NEW_AGENT_STACK",
        "CORVOS_ENABLE_CONTEXT_EDITING",
        "CORVOS_ENABLE_COMPACTION_V2",
        "CORVOS_ENABLE_RETRY_AFTER",
        "CORVOS_ENABLE_MODEL_FALLBACK",
        "CORVOS_ENABLE_MODEL_CALL_LIMIT",
        "CORVOS_ENABLE_TOOL_CALL_LIMIT",
        "CORVOS_ENABLE_TOOL_CALL_REPAIR",
        "CORVOS_ENABLE_DOOM_LOOP",
        "CORVOS_ENABLE_PERMISSION",
        "CORVOS_ENABLE_BUSY_MUTEX",
        "CORVOS_ENABLE_LLM_TOOL_SELECTOR",
        "CORVOS_ENABLE_SKILLS",
        "CORVOS_ENABLE_SPECIALIZED_SUBAGENTS",
        "CORVOS_ENABLE_ACTION_LOG",
        "CORVOS_ENABLE_REVERT_ROUTE",
        "CORVOS_ENABLE_PLUGIN_LOADER",
        "CORVOS_ENABLE_OTEL",
        "CORVOS_ENABLE_AGENT_CACHE",
        "CORVOS_ENABLE_AGENT_CACHE_SHARE_GP_SUBAGENT",
    ]:
        monkeypatch.delenv(name, raising=False)


def test_defaults_match_shipped_agent_stack(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_all(monkeypatch)
    flags = reload_for_tests()
    assert isinstance(flags, AgentFeatureFlags)
    assert flags.disable_new_agent_stack is False
    assert flags.enable_context_editing is True
    assert flags.enable_compaction_v2 is True
    assert flags.enable_retry_after is True
    assert flags.enable_model_fallback is False
    assert flags.enable_model_call_limit is True
    assert flags.enable_tool_call_limit is True
    assert flags.enable_tool_call_repair is True
    assert flags.enable_doom_loop is True
    assert flags.enable_permission is True
    assert flags.enable_busy_mutex is True
    assert flags.enable_llm_tool_selector is False
    assert flags.enable_skills is True
    assert flags.enable_specialized_subagents is True
    assert flags.enable_action_log is True
    assert flags.enable_revert_route is True
    assert flags.enable_plugin_loader is False
    assert flags.enable_otel is False
    # Phase 2: agent cache is now default-on (the prerequisite tool
    # ``db_session`` refactor landed). The companion gp-subagent share
    # flag stays default-off pending data on cold-miss frequency.
    assert flags.enable_agent_cache is True
    assert flags.enable_agent_cache_share_gp_subagent is False
    assert flags.any_new_middleware_enabled() is True


def test_master_kill_switch_overrides_individual_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_all(monkeypatch)
    monkeypatch.setenv("CORVOS_DISABLE_NEW_AGENT_STACK", "true")
    monkeypatch.setenv("CORVOS_ENABLE_CONTEXT_EDITING", "true")
    monkeypatch.setenv("CORVOS_ENABLE_PERMISSION", "true")

    flags = reload_for_tests()
    assert flags.disable_new_agent_stack is True
    assert flags.enable_context_editing is False
    assert flags.enable_permission is False
    assert flags.any_new_middleware_enabled() is False


@pytest.mark.parametrize("truthy", ["1", "true", "TRUE", "yes", "on"])
def test_individual_flags_truthy_values(
    monkeypatch: pytest.MonkeyPatch, truthy: str
) -> None:
    _clear_all(monkeypatch)
    monkeypatch.setenv("CORVOS_ENABLE_RETRY_AFTER", truthy)
    flags = reload_for_tests()
    assert flags.enable_retry_after is True
    assert flags.any_new_middleware_enabled() is True


@pytest.mark.parametrize("falsy", ["0", "false", "no", "off", "", "garbage"])
def test_individual_flags_falsy_values(
    monkeypatch: pytest.MonkeyPatch, falsy: str
) -> None:
    _clear_all(monkeypatch)
    monkeypatch.setenv("CORVOS_ENABLE_RETRY_AFTER", falsy)
    flags = reload_for_tests()
    assert flags.enable_retry_after is False


def test_each_flag_can_be_set_independently(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_all(monkeypatch)
    flag_to_env = {
        "enable_context_editing": "CORVOS_ENABLE_CONTEXT_EDITING",
        "enable_compaction_v2": "CORVOS_ENABLE_COMPACTION_V2",
        "enable_retry_after": "CORVOS_ENABLE_RETRY_AFTER",
        "enable_model_fallback": "CORVOS_ENABLE_MODEL_FALLBACK",
        "enable_model_call_limit": "CORVOS_ENABLE_MODEL_CALL_LIMIT",
        "enable_tool_call_limit": "CORVOS_ENABLE_TOOL_CALL_LIMIT",
        "enable_tool_call_repair": "CORVOS_ENABLE_TOOL_CALL_REPAIR",
        "enable_doom_loop": "CORVOS_ENABLE_DOOM_LOOP",
        "enable_permission": "CORVOS_ENABLE_PERMISSION",
        "enable_busy_mutex": "CORVOS_ENABLE_BUSY_MUTEX",
        "enable_llm_tool_selector": "CORVOS_ENABLE_LLM_TOOL_SELECTOR",
        "enable_skills": "CORVOS_ENABLE_SKILLS",
        "enable_specialized_subagents": "CORVOS_ENABLE_SPECIALIZED_SUBAGENTS",
        "enable_action_log": "CORVOS_ENABLE_ACTION_LOG",
        "enable_revert_route": "CORVOS_ENABLE_REVERT_ROUTE",
        "enable_plugin_loader": "CORVOS_ENABLE_PLUGIN_LOADER",
        "enable_otel": "CORVOS_ENABLE_OTEL",
    }

    for attr, env_name in flag_to_env.items():
        _clear_all(monkeypatch)
        monkeypatch.setenv(env_name, "false")
        flags = reload_for_tests()
        assert getattr(flags, attr) is False, f"{attr} did not flip off for {env_name}"
