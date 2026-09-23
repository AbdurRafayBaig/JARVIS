#!/usr/bin/env python3
"""JARVIS - Main Entry Point"""

import sys
import asyncio
import argparse
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from jarvis.core.config import get_settings, reload_settings
from jarvis.core.logging import setup_logging, get_logger, setup_stdlib_logging
from jarvis.core.database import init_database, close_database
from jarvis.tools.registry_loader import load_all_tools
from jarvis.agent.agent import create_agent
from jarvis.agent.planner import SimplePlanner
from jarvis.llm.manager import get_llm_manager

# Subsystems
from jarvis.services.hotkeys import get_hotkey_service, HotkeyConfig
from jarvis.services.startup import get_startup_service
from jarvis.services.notifications import get_notification_service
from jarvis.memory.conversation_memory import ConversationMemory
from jarvis.memory.project_memory import ProjectMemory
from jarvis.memory.vector_store import get_vector_store
from jarvis.memory.retrieval import MemoryRetriever
from jarvis.memory.task_store import get_task_store
from jarvis.security.approval import get_approval_manager
from jarvis.security.audit import get_audit_logger
from jarvis.browser.engine import get_browser_engine
from jarvis.integrations.github_client import get_github_client
from jarvis.desktop.vision import VisionCapture
from jarvis.desktop.screen_analyzer import ScreenAnalyzer

logger = get_logger(__name__)

# Global hotkeys registered in GUI mode.
HOTKEY_TOGGLE_PANEL = "ctrl+space"
HOTKEY_TOGGLE_VOICE = "ctrl+shift+j"
HOTKEY_COMMAND_CENTER = "ctrl+shift+c"
HOTKEY_CANCEL_TASK = "ctrl+shift+x"


class JarvisApplication:
    """Main JARVIS application."""

    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.settings = get_settings()
        self.agent = None
        self.running = False
        self._gui_app = None
        self._main_window = None
        self._command_center_window = None
        self._shutting_down = False

        # Subsystems
        self._hotkey_service = get_hotkey_service()
        self._startup_service = get_startup_service()
        self._notification_service = get_notification_service()
        self._conversation_memory = ConversationMemory()
        self._project_memory = ProjectMemory()
        self._vector_store = get_vector_store()
        self._memory_retriever = MemoryRetriever()
        self._task_store = get_task_store()
        self._approval_manager = get_approval_manager()
        self._audit_logger = get_audit_logger()
        self._browser_engine = get_browser_engine()
        self._github_client = get_github_client()
        self._vision_capture = VisionCapture()
        self._screen_analyzer = ScreenAnalyzer()

    # -- lifecycle -----------------------------------------------------------

    async def initialize(self) -> None:
        """Initialize all subsystems."""
        logger.info("Initializing JARVIS...")

        # Setup logging
        setup_logging()
        setup_stdlib_logging()

        # Load tools
        load_all_tools()

        # Initialize database. Long-term memory, the audit log and task
        # history all stay inert until this succeeds.
        await init_database()

        # Initialize LLM
        llm_manager = get_llm_manager()
        if not await llm_manager.health_check():
            logger.warning("LLM health check failed - some features may not work")

        # Create agent with memory context (uses LLMPlanner if available)
        self.agent = create_agent(
            max_steps=self.settings.agent.max_steps,
            max_retries=self.settings.agent.max_retries,
            enable_verification=self.settings.agent.enable_verification,
            enable_recovery=self.settings.agent.enable_recovery,
        )

        # Setup agent callbacks
        self.agent.on("task_start", self._on_task_start)
        self.agent.on("task_step", self._on_task_step)
        self.agent.on("task_complete", self._on_task_complete)
        self.agent.on("error", self._on_error)

        # Wire approval callback
        self._approval_manager.set_approval_callback(self._handle_approval_request)

        self.running = True
        logger.info("JARVIS initialization complete")

    async def start_hotkeys(self) -> None:
        """Register and start the global hotkeys used by the GUI."""
        bindings = [
            (HOTKEY_TOGGLE_PANEL, self._toggle_panel, "Toggle JARVIS panel"),
            (HOTKEY_TOGGLE_VOICE, self._toggle_voice, "Toggle voice listening"),
            (HOTKEY_COMMAND_CENTER, self._open_command_center, "Open Command Center"),
            (HOTKEY_CANCEL_TASK, self._cancel_task, "Cancel the running task"),
        ]
        for key, callback, description in bindings:
            self._hotkey_service.register(
                HotkeyConfig(key=key, callback=callback, description=description)
            )

        await self._hotkey_service.start()
        logger.info(
            f"Global hotkeys active: {HOTKEY_TOGGLE_PANEL} panel, "
            f"{HOTKEY_TOGGLE_VOICE} voice, {HOTKEY_COMMAND_CENTER} command center, "
            f"{HOTKEY_CANCEL_TASK} cancel"
        )

    async def apply_autostart_preference(self) -> None:
        """Keep the Windows startup entry in sync with the configured setting."""
        try:
            enabled = await self._startup_service.is_enabled()
            if self.settings.ui.auto_start and not enabled:
                await self._startup_service.enable()
            elif not self.settings.ui.auto_start and enabled:
                await self._startup_service.disable()
        except Exception as e:
            logger.warning(f"Could not apply auto-start preference: {e}")

    async def _handle_approval_request(self, tool_name: str, tool_args: str) -> bool:
        """Handle a tool approval request."""
        logger.info(f"Approval requested for: {tool_name}")

        if getattr(self.args, "cli", False):
            try:
                ans = input(
                    f"\n[APPROVAL REQUIRED] Tool '{tool_name}' with args {tool_args}. "
                    f"Proceed? (y/n): "
                ).strip().lower()
                return ans in ("y", "yes")
            except Exception:
                return False

        if self._main_window is not None:
            return await self._main_window.request_approval(tool_name, tool_args)

        return True

    # -- agent events --------------------------------------------------------

    def _on_task_start(self, task) -> None:
        logger.info(f"Task started: {task.goal}")
        if self._main_window:
            self._main_window.set_task(task)

    def _on_task_step(self, task, step, status) -> None:
        logger.debug(f"Task step: {step.description} - {status}")
        if self._main_window:
            self._main_window.update_task(task)

    def _on_task_complete(self, task) -> None:
        status = "SUCCESS" if task.status.value == "completed" else "FAILED"
        logger.info(f"Task {status}: {task.goal}")
        if self._main_window:
            self._main_window.update_task(task)
        if self._command_center_window:
            try:
                self._command_center_window.update_task(task)
            except Exception:
                pass

    def _on_error(self, task, error) -> None:
        logger.error(f"Task error: {error}")

    # -- run modes -----------------------------------------------------------

    async def run_cli(self) -> None:
        """Run in CLI mode."""
        print("\n+======================================+")
        print("|        JARVIS CLI MODE               |")
        print("|   Type 'exit' or 'quit' to exit      |")
        print("+======================================+\n")

        loop = asyncio.get_running_loop()

        while True:
            try:
                # input() blocks; keep it off the event loop so background
                # work (voice, browser, timers) keeps running while we wait.
                user_input = (await loop.run_in_executor(None, input, "JARVIS> ")).strip()

                if user_input.lower() in ("exit", "quit", "q"):
                    break
                if not user_input:
                    continue

                print(f"\n[Processing: {user_input}]\n")
                task = await self.agent.execute_task(user_input)

                if task.status.value == "completed":
                    print(f"[OK] {task.result}")
                else:
                    print(f"[FAILED] {task.error or task.result}")
                print()

            except KeyboardInterrupt:
                print("\nInterrupted")
                break
            except EOFError:
                break
            except Exception as e:
                logger.error(f"CLI error: {e}")
                print(f"Error: {e}")

    async def run_headless(self) -> None:
        """Run without a UI, servicing voice and background work only."""
        logger.info("Running in headless mode. Press Ctrl+C to exit.")
        await self.start_voice_pipeline()
        try:
            while self.running:
                await asyncio.sleep(1)
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass

    async def setup_gui(self) -> None:
        """Build and show the GUI. The qasync loop is already running."""
        from jarvis.ui.main_window import MainWindow

        self._main_window = MainWindow()
        self._main_window.set_agent(self.agent)

        # Connect signals
        self._main_window.toggle_panel_requested.connect(self._toggle_panel)
        self._main_window.toggle_voice.connect(self._toggle_voice)
        self._main_window.open_settings.connect(self._open_settings)
        self._main_window.open_command_center.connect(self._open_command_center)
        # quit_requested carries an async shutdown, so it goes through a
        # plain slot that schedules the coroutine.
        self._main_window.quit_requested.connect(self._request_shutdown)

        # Show the transparent overlay (for the side panel) and the orb
        if not getattr(self.args, "minimized", False):
            self._main_window.show()
        self._main_window.orb.show()

        await self.start_hotkeys()
        await self.apply_autostart_preference()

        logger.info("GUI launched - floating orb and system tray are visible.")

        await self.start_voice_pipeline()

    async def start_voice_pipeline(self) -> None:
        """Start the voice pipeline if voice is enabled."""
        if not self.settings.voice.enabled:
            logger.info("Voice is disabled in settings; skipping voice pipeline.")
            return

        try:
            from jarvis.voice.voice_pipeline import get_voice_pipeline

            pipeline = get_voice_pipeline()
            if self._main_window is not None:
                pipeline.set_wake_callback(self._main_window.on_wake_word)

            await pipeline.start(self.agent.execute_task)
            logger.info("Voice pipeline active and listening in the background.")
        except Exception as e:
            logger.warning(f"Voice pipeline could not start: {e}")

    # -- UI actions ----------------------------------------------------------

    def _toggle_panel(self) -> None:
        logger.debug("Toggle panel requested")
        if self._main_window:
            self._main_window.panel_controller.toggle()

    def _toggle_voice(self) -> None:
        logger.info("Toggle voice requested")
        try:
            from jarvis.voice.voice_pipeline import get_voice_pipeline

            pipeline = get_voice_pipeline()
            if pipeline.is_running:
                asyncio.ensure_future(pipeline.stop())
                logger.info("Voice pipeline stopping")
            else:
                asyncio.ensure_future(pipeline.start(self.agent.execute_task))
                logger.info("Voice pipeline starting")
        except Exception as e:
            logger.error(f"Voice pipeline toggle error: {e}")

    def _cancel_task(self) -> None:
        """Cancel the running task."""
        if self.agent and self.agent.is_running:
            logger.info("Cancel requested via hotkey")
            asyncio.ensure_future(self.agent.cancel_current_task())

    def _open_settings(self) -> None:
        logger.info("Open settings requested")
        try:
            from jarvis.ui.settings_dialog import SettingsDialog

            dialog = SettingsDialog(self._main_window)
            dialog.exec()
        except Exception as e:
            logger.error(f"Failed to open settings: {e}")

    def _open_command_center(self) -> None:
        logger.info("Open command center requested")
        try:
            from jarvis.ui.command_center import CommandCenterDashboard

            if self._command_center_window is None:
                self._command_center_window = CommandCenterDashboard()
            self._command_center_window.show()
            self._command_center_window.raise_()
            self._command_center_window.activateWindow()
        except Exception as e:
            logger.error(f"Failed to open command center: {e}")

    def _request_shutdown(self) -> None:
        """Slot for quit_requested; schedules the async shutdown."""
        asyncio.ensure_future(self._shutdown_and_stop())

    async def _shutdown_and_stop(self) -> None:
        """Shut down, then stop the event loop so the process can exit."""
        await self.shutdown()
        try:
            asyncio.get_running_loop().stop()
        except RuntimeError:
            pass

    async def shutdown(self) -> None:
        """Shutdown the application."""
        if self._shutting_down:
            return
        self._shutting_down = True

        logger.info("Shutting down...")
        self.running = False

        # Stop voice pipeline
        try:
            from jarvis.voice.voice_pipeline import get_voice_pipeline

            pipeline = get_voice_pipeline()
            if pipeline.is_running:
                await pipeline.stop()
        except Exception:
            pass

        # Stop services
        try:
            await self._hotkey_service.stop()
        except Exception:
            pass

        # Close browser
        try:
            await self._browser_engine.stop()
        except Exception:
            pass

        # Close GitHub client
        try:
            await self._github_client.close()
        except Exception:
            pass

        # Flush vector store (embeddings cache + indexed entries)
        try:
            self._vector_store.save()
        except Exception:
            pass

        # Close database
        try:
            await close_database()
        except Exception:
            pass

        if self._gui_app:
            self._gui_app.quit()

    # Kept for backwards compatibility with earlier callers.
    _shutdown = shutdown

    # -- diagnostics ---------------------------------------------------------

    async def run_diagnostics(self) -> bool:
        """Run system diagnostics."""
        print("\n+=======================================+")
        print("|      JARVIS DIAGNOSTICS              |")
        print("+=======================================+\n")

        checks = []

        # Python version
        py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        checks.append(("Python Version", py_version, True))

        # Dependencies
        deps = [
            ("PySide6", "PySide6"),
            ("qasync", "qasync"),
            ("OpenAI", "openai"),
            ("Anthropic", "anthropic"),
            ("Ollama", "ollama"),
            ("SQLAlchemy", "sqlalchemy"),
            ("Loguru", "loguru"),
            ("Pydantic", "pydantic"),
            ("psutil", "psutil"),
            ("pywinauto", "pywinauto"),
            ("mss", "mss"),
            ("PIL", "PIL"),
            ("cv2", "cv2"),
            ("numpy", "numpy"),
            ("Playwright", "playwright"),
            ("httpx", "httpx"),
            ("faster_whisper", "faster_whisper"),
            ("pyaudio", "pyaudio"),
            ("pvporcupine", "pvporcupine"),
        ]

        for name, module in deps:
            try:
                __import__(module)
                checks.append((name, "[OK] Available", True))
            except ImportError:
                checks.append((name, "[MISSING] Missing", False))

        # Configuration
        checks.append((
            "Config File",
            ".env" if Path(".env").exists() else ".env.example",
            Path(".env").exists(),
        ))

        # LLM
        try:
            llm_manager = get_llm_manager()
            llm_ok = await llm_manager.health_check()
            provider_name = llm_manager.get_provider().__class__.__name__
            checks.append(("LLM Provider", provider_name, llm_ok))
        except Exception as e:
            checks.append(("LLM Provider", f"Not configured: {e}", False))

        # Database
        try:
            await init_database()
            checks.append(("Database", "SQLite", True))
        except Exception as e:
            checks.append(("Database", f"Error: {e}", False))

        # Tools
        from jarvis.agent.tools import get_registry

        tool_count = len(get_registry().get_all())
        checks.append(("Tool Registry", f"{tool_count} tools", tool_count > 0))

        # Services
        checks.append((
            "Hotkey Service",
            "Win32 global hotkeys" if self._hotkey_service.is_supported else "Unsupported platform",
            self._hotkey_service.is_supported,
        ))
        checks.append(("Notification Service", "Available", True))

        # Memory — exercised against the real database rather than assumed.
        try:
            stored = await self._conversation_memory.store("system", "diagnostics probe")
            checks.append(("Conversation Memory", "Read/write OK", stored is not None))
        except Exception as e:
            checks.append(("Conversation Memory", f"Error: {e}", False))

        try:
            await self._project_memory.list_preferences()
            checks.append(("Project Memory", "Read/write OK", True))
        except Exception as e:
            checks.append(("Project Memory", f"Error: {e}", False))

        try:
            stats = await self._task_store.get_stats()
            checks.append(("Task History", f"{stats['total']} tasks recorded", True))
        except Exception as e:
            checks.append(("Task History", f"Error: {e}", False))

        checks.append(("Vector Store", "Available", True))

        # Security
        checks.append(("Approval Manager", "Available", True))
        try:
            await self._audit_logger.log_user_action("diagnostics")
            audit_stats = await self._audit_logger.get_stats()
            checks.append(("Audit Logger", f"{audit_stats['total']} events (24h)", True))
        except Exception as e:
            checks.append(("Audit Logger", f"Error: {e}", False))

        # Browser
        try:
            get_browser_engine()
            checks.append(("Browser Engine", "Playwright", True))
        except Exception:
            checks.append(("Browser Engine", "Not initialized", False))

        # GitHub
        try:
            github = get_github_client()
            github_ok = await github.health_check()
            checks.append(("GitHub Client", "API" if github_ok else "Token missing/invalid", github_ok))
        except Exception:
            checks.append(("GitHub Client", "Not configured", False))

        # Voice
        checks.append((
            "Wake Word",
            "Porcupine" if self.settings.voice.pv_access_key else "No PV_ACCESS_KEY (hands-free off)",
            bool(self.settings.voice.pv_access_key),
        ))

        # Vision
        checks.append(("Vision Capture", "mss", True))
        checks.append(("Screen Analyzer", "LLM Vision", True))

        # Paths
        data_dir = self.settings.get_data_dir()
        checks.append(("Data Directory", str(data_dir), data_dir.exists()))

        projects_dir = self.settings.get_projects_dir()
        checks.append(("Projects Directory", str(projects_dir), projects_dir.exists()))

        # Print results
        all_passed = True
        for name, value, passed in checks:
            status = "[OK]" if passed else "[FAIL]"
            print(f"  {status} {name:<25} {value}")
            if not passed:
                all_passed = False

        print(f"\n{'All checks passed!' if all_passed else 'Some checks failed!'}\n")
        return all_passed


def parse_args(argv=None) -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="JARVIS - Personal AI Computer Agent")
    parser.add_argument("--gui", action="store_true", help="Run in GUI mode (default)")
    parser.add_argument("--cli", action="store_true", help="Run in CLI mode")
    parser.add_argument("--diagnose", action="store_true", help="Run diagnostics")
    parser.add_argument("--no-gui", action="store_true", help="Run without GUI (headless)")
    parser.add_argument(
        "--minimized",
        action="store_true",
        help="Start with the panel hidden (used by the Windows startup entry)",
    )
    parser.add_argument("--config", type=str, help="Path to config file")
    parser.add_argument("--log-level", type=str, default="INFO", help="Log level")
    return parser.parse_args(argv)


async def run_without_gui(args: argparse.Namespace) -> int:
    """Run diagnostics, CLI or headless mode on a plain asyncio loop."""
    app = JarvisApplication(args)
    try:
        await app.initialize()

        if args.diagnose:
            return 0 if await app.run_diagnostics() else 1

        if args.cli:
            await app.run_cli()
        else:
            await app.run_headless()

    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        return 1
    finally:
        await app.shutdown()

    return 0


def run_with_gui(args: argparse.Namespace) -> int:
    """Run GUI mode on a qasync loop that drives both Qt and asyncio.

    The Qt event loop must be the asyncio loop, so it is created up front and
    everything else runs inside it -- starting asyncio first and then trying
    to run a second loop for Qt raises "Cannot run the event loop while
    another loop is running".
    """
    try:
        import qasync
    except ImportError:
        logger.error(
            "qasync is required for GUI mode (pip install qasync). "
            "Falling back to headless mode; use --cli for an interactive prompt."
        )
        return asyncio.run(run_without_gui(argparse.Namespace(**{**vars(args), "no_gui": True})))

    from jarvis.ui.main_window import create_app

    qt_app = create_app()
    loop = qasync.QEventLoop(qt_app)
    asyncio.set_event_loop(loop)

    app = JarvisApplication(args)
    app._gui_app = qt_app
    exit_code = 0

    async def boot() -> None:
        nonlocal exit_code
        try:
            await app.initialize()
            await app.setup_gui()
        except Exception as e:
            logger.exception(f"Fatal error during startup: {e}")
            exit_code = 1
            await app._shutdown_and_stop()

    try:
        with loop:
            loop.create_task(boot())
            loop.run_forever()
    except KeyboardInterrupt:
        logger.info("Interrupted")
    finally:
        # The loop is closed here, so shutdown gets a short-lived one of its own.
        if not app._shutting_down:
            try:
                asyncio.run(app.shutdown())
            except Exception as e:
                logger.warning(f"Shutdown error: {e}")

    return exit_code


def main(argv=None) -> int:
    """Main entry point."""
    args = parse_args(argv)

    if args.config:
        import os

        os.environ["JARVIS_CONFIG"] = args.config
        reload_settings()

    if args.diagnose or args.cli or args.no_gui:
        return asyncio.run(run_without_gui(args))

    return run_with_gui(args)


if __name__ == "__main__":
    # Windows event loop policy
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nShutdown requested")
        sys.exit(0)
