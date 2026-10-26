"""GAS diagnostics: real PIE calls; no skips on a correctly configured host."""
import pytest
import time

from _framework.mcp_client import cap_first
from _framework.assertions import assert_tool_error

pytestmark = pytest.mark.l4_runtime
GET = "GetRuntimeActorAbilitySystem"
INTERACT = "InteractRuntimeActorAbilitySystem"
ABILITY = "/Script/Nexus.NexusDiagnosticAbility"


@pytest.fixture
def diagnostic_actor(mcp, pie):
    result = cap_first(mcp.call_capability("SpawnRuntimeActor", ClassName="NexusDiagnosticCharacter"))
    name = result.get("ActorName") or result["name"]
    yield name
    mcp.call_capability("DestroyRuntimeActor", ActorName=name)


def test_diagnostic_sections_and_readonly(mcp, diagnostic_actor):
    args = {"ActorName": diagnostic_actor}
    before = cap_first(mcp.call_capability(GET, **args, Sections=["Abilities"]))
    result = cap_first(mcp.call_capability(GET, **args, AbilityPath=ABILITY,
        Sections=["Context", "Tags", "ActivationDiagnostics", "Attributes", "Effects"]))
    assert result["Context"]["ProcessId"] > 0
    assert result["Context"]["WorldId"] > 0
    assert result["ActivationDiagnostics"]["bGranted"] is True
    assert "Nexus.Diagnostics.Required" in result["OwnedTags"]
    after = cap_first(mcp.call_capability(GET, **args, Sections=["Abilities"]))
    assert before["Abilities"] == after["Abilities"]
    all_sections = cap_first(mcp.call_capability(GET, **args, Sections=["All"]))
    assert "SectionErrors" not in all_sections
    assert "Context" in all_sections


def test_capture_try_activate_and_stop(mcp, diagnostic_actor):
    args = {"ActorName": diagnostic_actor}
    capture = cap_first(mcp.call_capability(INTERACT, **args, Action="StartActivationCapture"))["CaptureId"]
    try:
        result = cap_first(mcp.call_capability(INTERACT, **args, Action="TryActivateGrantedAbility", AbilityPath=ABILITY))
        assert result["bRequestAccepted"] is True
        events = cap_first(mcp.call_capability(GET, **args, Sections=["ActivationEvents"], CaptureId=capture))
        assert events.get("Dropped", 0) == 0
        assert "Committed" in events["EventTypes"]
        assert "Activated" in events["EventTypes"]
    finally:
        mcp.call_capability(INTERACT, **args, Action="StopActivationCapture", CaptureId=capture)
    assert_tool_error(mcp.try_call(GET, **args, Sections=["ActivationEvents"], CaptureId=capture))


def test_not_granted_and_missing_target(mcp, diagnostic_actor):
    args = {"ActorName": diagnostic_actor}
    result = cap_first(mcp.call_capability(GET, **args, Sections=["ActivationDiagnostics"],
                                         AbilityPath="/Script/GameplayAbilities.GameplayAbility"))
    assert result["ActivationDiagnostics"]["bGranted"] is False
    assert_tool_error(mcp.try_call(INTERACT, **args, Action="TryActivateGrantedAbility",
                                  AbilityPath="/Script/GameplayAbilities.GameplayAbility"))
    assert_tool_error(mcp.try_call(INTERACT, Action="StartActivationCapture"))


def test_capture_bounded_and_expired(mcp, diagnostic_actor):
    args = {"ActorName": diagnostic_actor}
    capture = cap_first(mcp.call_capability(INTERACT, **args, Action="StartActivationCapture"))["CaptureId"]
    try:
        # 初次成功后冷却阻止后续激活，每次拒绝都应留下事件并最终触发丢弃计数。
        for _ in range(260):
            mcp.call_capability(INTERACT, **args, Action="TryActivateGrantedAbility", AbilityPath=ABILITY)
        events = cap_first(mcp.call_capability(GET, **args, Sections=["ActivationEvents"], CaptureId=capture))
        assert events["Dropped"] > 0
        assert len(events["Events"]) == 256
        time.sleep(121)
        assert_tool_error(mcp.try_call(GET, **args, Sections=["ActivationEvents"], CaptureId=capture))
    finally:
        # 过期捕获已经由 ticker 清理，不把预期的不存在作为清理异常。
        mcp.try_call(INTERACT, **args, Action="StopActivationCapture", CaptureId=capture)


def test_destroyed_actor_capture_does_not_consume_limit(mcp, pie):
    spawned = cap_first(mcp.call_capability("SpawnRuntimeActor", ClassName="NexusDiagnosticCharacter"))
    name = spawned.get("ActorName") or spawned["name"]
    for _ in range(16):
        mcp.call_capability(INTERACT, ActorName=name, Action="StartActivationCapture")
    assert_tool_error(mcp.try_call(INTERACT, ActorName=name, Action="StartActivationCapture"))
    mcp.call_capability("DestroyRuntimeActor", ActorName=name)
    time.sleep(1.2)
    replacement = cap_first(mcp.call_capability("SpawnRuntimeActor", ClassName="NexusDiagnosticCharacter"))
    replacement_name = replacement.get("ActorName") or replacement["name"]
    try:
        capture = cap_first(mcp.call_capability(INTERACT, ActorName=replacement_name, Action="StartActivationCapture"))["CaptureId"]
        mcp.call_capability(INTERACT, ActorName=replacement_name, Action="StopActivationCapture", CaptureId=capture)
    finally:
        mcp.call_capability("DestroyRuntimeActor", ActorName=replacement_name)
