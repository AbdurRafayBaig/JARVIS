"""JARVIS Tools - Registry Loader"""

from jarvis.tools.computer import register_computer_tools
from jarvis.tools.coding import register_coding_tools
from jarvis.tools.browser import register_browser_tools
from jarvis.tools.github import register_github_tools
from jarvis.tools.vision import register_vision_tools
from jarvis.tools.system import register_system_tools
from jarvis.tools.memory import register_memory_tools
from jarvis.agent.tools import get_registry
from jarvis.core.logging import get_logger

logger = get_logger(__name__)


def load_all_tools() -> None:
    """Load all built-in tools into the registry."""
    registry = get_registry()

    # Clear existing tools (for reload)
    for tool_name in list(registry._tools.keys()):
        registry.unregister(tool_name)

    # Register all tool categories
    register_system_tools()
    register_computer_tools()
    register_coding_tools()
    register_browser_tools()
    register_github_tools()
    register_vision_tools()
    register_memory_tools()

    # Log loaded tools
    tools_by_category = {}
    for name, tool in registry._tools.items():
        cat = "unknown"
        for category, tools in registry._categories.items():
            if name in tools:
                cat = category
                break
        tools_by_category.setdefault(cat, []).append(name)

    logger.info(f"Loaded {len(registry._tools)} tools")
    for cat, tools in sorted(tools_by_category.items()):
        logger.debug(f"  {cat}: {', '.join(sorted(tools))}")


if __name__ == "__main__":
    load_all_tools()
    registry = get_registry()
    for tool in sorted(registry.get_all(), key=lambda t: t.name):
        print(f"{tool.name:<24} [{tool.risk_level.value}] {tool.description}")