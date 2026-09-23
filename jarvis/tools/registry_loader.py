"""JARVIS Tools - Registry Loader"""

from jarvis.tools.computer import register_computer_tools
from jarvis.tools.coding import register_coding_tools
from jarvis.tools.browser import register_browser_tools
from jarvis.tools.github import register_github_tools
from jarvis.tools.vision import register_vision_tools
from jarvis.tools.system import register_system_tools
from jarvis.tools.memory import register_memory_tools
from jarvis.agent.tools import get_registry


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

    print(f"Loaded {len(registry._tools)} tools:")
    for cat, tools in tools_by_category.items():
        print(f"  {cat}: {', '.join(tools)}")


if __name__ == "__main__":
    load_all_tools()