"""JARVIS - Intent router and no-LLM command path tests."""

from pathlib import Path

import pytest

from jarvis.agent.agent import Agent
from jarvis.agent.intent_router import IntentRouter
from jarvis.agent.planner import HybridPlanner, Plan
from jarvis.agent.task import TaskStatus, TaskStep
from jarvis.agent.tools import ToolRegistry, BaseTool, ToolResult
from jarvis.tools.paths import known_folder, resolve_path


@pytest.fixture
def router():
    return IntentRouter()


def tools_of(steps):
    return [s.tool_name for s in steps] if steps else None


# (command, expected tool, expected subset of args)
SINGLE_COMMANDS = [
    ("open chrome", "open_application", {"app_name": "chrome"}),
    ("Hey Jarvis, please open notepad", "open_application", {"app_name": "notepad"}),
    ("open display settings", "open_settings", {"page": "display"}),
    ("wifi settings", "open_settings", {"page": "wifi"}),
    ("settings kholo", "open_settings", {"page": ""}),
    ("chrome band karo", "close_application", {"app_name": "chrome"}),
    ("volume up", "volume", {"action": "up", "amount": 10}),
    ("turn the volume down by 20", "volume", {"action": "down", "amount": 20}),
    ("set volume to 40", "volume", {"action": "set", "amount": 40}),
    ("mute", "volume", {"action": "mute"}),
    ("awaz kam karo", "volume", {"action": "down"}),
    ("set brightness to 70%", "brightness", {"action": "set", "amount": 70}),
    ("dark mode", "set_theme", {"mode": "dark"}),
    ("turn off dark mode", "set_theme", {"mode": "light"}),
    ("take a screenshot", "take_screenshot", {}),
    ("lock the computer", "lock_screen", {}),
    ("shut down", "power_action", {"action": "shutdown"}),
    ("cancel shutdown", "power_action", {"action": "cancel"}),
    ("show desktop", "show_desktop", {}),
    ("minimize notepad", "window_action", {"title": "notepad", "action": "minimize"}),
    ("restore chrome", "window_action", {"action": "restore"}),
    ("switch to chrome", "focus_window", {"title": "chrome"}),
    ("search for best laptops 2026", "web_search", {"query": "best laptops 2026", "site": "google"}),
    ("google python and pandas tutorial", "web_search", {"query": "python and pandas tutorial"}),
    ("play lofi beats on youtube", "web_search", {"query": "lofi beats", "site": "youtube"}),
    ("open youtube", "open_url", {"url": "https://www.youtube.com"}),
    ("open github.com", "open_url", {"url": "github.com"}),
    ("type salt and pepper", "type_text", {"text": "salt and pepper"}),
    ("press enter", "press_key", {"key": "enter"}),
    ("press ctrl+shift+esc", "hotkey", {"keys": ["ctrl", "shift", "esc"]}),
    ("copy", "hotkey", {"keys": ["ctrl", "c"]}),
    ("close this window", "hotkey", {"keys": ["alt", "f4"]}),
    ("what time is it", "get_current_time", {}),
    ("what is the current time?", "get_current_time", {}),
    ("battery", "battery_status", {}),
    ("show me system info", "get_system_info", {}),
    ("pause", "media_control", {"action": "play_pause"}),
    ("next song", "media_control", {"action": "next"}),
    ("what can you do", "respond", {}),
]


@pytest.mark.parametrize("command,tool,args", SINGLE_COMMANDS)
def test_single_commands(router, command, tool, args):
    steps = router.route(command)
    assert steps is not None, f"not understood: {command!r}"
    assert len(steps) == 1
    assert steps[0].tool_name == tool
    for key, value in args.items():
        assert steps[0].tool_args.get(key) == value


def test_file_commands_resolve_user_folders(router):
    desktop = known_folder("desktop")
    documents = known_folder("documents")

    steps = router.route("create a folder called Work on the desktop")
    assert tools_of(steps) == ["create_directory"]
    assert steps[0].tool_args["path"] == str(desktop / "Work")

    # No location given: the Desktop, where the user will see it.
    steps = router.route("create a file called todo with text buy milk and eggs")
    assert tools_of(steps) == ["create_file"]
    assert steps[0].tool_args == {"path": str(desktop / "todo.txt"), "content": "buy milk and eggs"}

    steps = router.route("rename todo.txt on desktop to tasks")
    assert tools_of(steps) == ["move_path"]
    assert steps[0].tool_args["destination"] == str(desktop / "tasks.txt")

    steps = router.route("move tasks.txt from desktop to documents")
    assert steps[0].tool_args == {"source": str(desktop / "tasks.txt"), "destination": str(documents)}

    # Deleting goes to the Recycle Bin, never a hard delete.
    steps = router.route("delete tasks.txt from documents")
    assert tools_of(steps) == ["recycle_path"]

    steps = router.route("open downloads")
    assert tools_of(steps) == ["open_path"]
    assert steps[0].tool_args["path"] == str(known_folder("downloads"))


def test_multi_step_commands_wait_for_the_window(router):
    steps = router.route("open notepad and type hello world")
    assert tools_of(steps) == ["open_application", "wait", "type_text"]
    assert steps[2].tool_args["text"] == "hello world"

    steps = router.route("open notepad then type hi and press enter")
    assert tools_of(steps) == ["open_application", "wait", "type_text", "press_key"]


@pytest.mark.parametrize("goal", [
    "open vscode and implement authentication",
    "build me a raft implementation",
    "write a report about our quarterly sales",
    "",
])
def test_partly_understood_goals_are_left_for_the_llm(router, goal):
    """Half-understanding a goal must not lead to half-executing it."""
    assert router.route(goal) is None


def test_resolve_path_prefers_real_relative_paths(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "music").mkdir()

    assert resolve_path("music") == Path("music")
    assert resolve_path("downloads/x.txt") == known_folder("downloads") / "x.txt"


# -- hybrid planner ---------------------------------------------------------


class RecordingTool(BaseTool):
    def __init__(self, tool_name: str, result="ok"):
        self._tool_name = tool_name
        self._result = result
        self.calls = []
        super().__init__()

    @property
    def name(self) -> str:
        return self._tool_name

    @property
    def description(self) -> str:
        return "records calls"

    async def execute(self, **kwargs) -> ToolResult:
        self.calls.append(kwargs)
        return ToolResult(success=True, data=self._result)

    def validate_args(self, args):
        return dict(args or {})


class ExplodingLLMPlanner:
    """Stands in for an LLM that is out of credits."""

    fallback_to_simple = False

    def __init__(self):
        self.calls = 0

    async def plan(self, goal, context):
        self.calls += 1
        raise RuntimeError("insufficient_quota")

    async def replan(self, task, failed_step, error):
        raise RuntimeError("insufficient_quota")


@pytest.mark.asyncio
async def test_direct_command_runs_without_touching_the_llm():
    registry = ToolRegistry()
    volume = RecordingTool("volume", "Volume up 10%")
    registry.register(volume)
    llm = ExplodingLLMPlanner()

    agent = Agent(planner=HybridPlanner(llm, registry), tool_registry=registry)
    task = await agent.execute_task("volume up")

    assert task.status == TaskStatus.COMPLETED
    assert volume.calls == [{"action": "up", "amount": 10}]
    assert llm.calls == 0
    assert task.result == "Volume up 10%."
    assert task.metadata["plan_source"] == "router"


@pytest.mark.asyncio
async def test_llm_failure_is_explained_and_not_retried_every_time():
    registry = ToolRegistry()
    llm = ExplodingLLMPlanner()
    planner = HybridPlanner(llm, registry)

    plan = await planner.plan("write a poem about autumn", {})
    assert plan.source == "fallback"
    assert plan.steps[0].tool_name == "respond"
    assert "language model" in plan.steps[0].tool_args["message"]

    # The LLM just failed; the next request must not wait on it again.
    await planner.plan("summarise my week", {})
    assert llm.calls == 1


@pytest.mark.asyncio
async def test_multi_step_direct_command_summary_skips_internal_steps():
    registry = ToolRegistry()
    for name, result in [("open_application", "Opened notepad"), ("wait", "Waited 2s"),
                         ("type_text", "Typed 5 characters")]:
        registry.register(RecordingTool(name, result))

    agent = Agent(planner=HybridPlanner(None, registry), tool_registry=registry)
    task = await agent.execute_task("open notepad and type hello")

    assert task.status == TaskStatus.COMPLETED
    assert task.result == "Opened notepad. Typed 5 characters."
