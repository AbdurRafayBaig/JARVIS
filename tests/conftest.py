"""Pytest configuration for JARVIS tests."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest
import asyncio


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_dir(tmp_path):
    """Provide temporary directory."""
    return tmp_path


@pytest.fixture(autouse=True)
def reset_registries():
    """Reset global registries between tests."""
    from jarvis.agent.tools import get_registry
    registry = get_registry()
    # Clear tools but keep built-ins
    builtin_tools = {}
    for name, tool in registry._tools.items():
        if name in ["respond"]:
            builtin_tools[name] = tool

    registry._tools.clear()
    registry._categories.clear()
    for name, tool in builtin_tools.items():
        registry.register(tool)

    yield

    # Cleanup after test
    registry._tools.clear()
    registry._categories.clear()
    for name, tool in builtin_tools.items():
        registry.register(tool)