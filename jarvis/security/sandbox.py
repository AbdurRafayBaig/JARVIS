"""Sandbox Runner

Provides isolated execution environment for dangerous operations.
"""

import asyncio
import subprocess
from typing import Optional
from loguru import logger

from jarvis.core.config import get_settings


class SandboxRunner:
    """Runs commands in an isolated sandbox environment."""

    def __init__(self):
        self._settings = get_settings()
        self._enabled = self._settings.security.sandbox_enabled
        self._timeout = self._settings.security.max_execution_time

    async def run_command(
        self,
        command: str,
        cwd: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> tuple[bool, str, str]:
        """Run a command in sandbox."""
        if not self._enabled:
            return await self._run_direct(command, cwd, timeout)

        return await self._run_sandboxed(command, cwd, timeout)

    async def _run_direct(
        self,
        command: str,
        cwd: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> tuple[bool, str, str]:
        """Run command directly."""
        effective_timeout = timeout or self._timeout

        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=effective_timeout,
            )

            success = process.returncode == 0
            return success, stdout.decode(), stderr.decode()

        except asyncio.TimeoutError:
            logger.error(f"Command timed out: {command}")
            return False, "", "Command timed out"
        except Exception as e:
            logger.error(f"Command failed: {e}")
            return False, "", str(e)

    async def _run_sandboxed(
        self,
        command: str,
        cwd: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> tuple[bool, str, str]:
        """Run command in sandbox."""
        sandbox_cmd = self._wrap_for_sandbox(command)

        return await self._run_direct(sandbox_cmd, cwd, timeout)

    def _wrap_for_sandbox(self, command: str) -> str:
        """Wrap command for sandbox execution."""
        if self._settings.security.run_in_docker:
            return self._wrap_docker(command)
        elif self._settings.security.run_in_vm:
            return self._wrap_vm(command)
        else:
            return command

    def _wrap_docker(self, command: str) -> str:
        """Wrap command for Docker execution."""
        docker_image = "python:3.11-slim"
        return (
            f"docker run --rm "
            f"--network none "
            f"--read-only "
            f"--tmpfs /tmp:size=100m "
            f"{docker_image} "
            f"bash -c '{command}'"
        )

    def _wrap_vm(self, command: str) -> str:
        """Wrap command for VM execution."""
        logger.warning("VM sandboxing not implemented, running directly")
        return command

    async def run_python_code(
        self,
        code: str,
        timeout: Optional[int] = None,
    ) -> tuple[bool, str, str]:
        """Run Python code in sandbox."""
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".py",
            delete=False,
        ) as f:
            f.write(code)
            temp_path = f.name

        try:
            command = f"python {temp_path}"
            return await self.run_command(command, timeout=timeout)
        finally:
            os.unlink(temp_path)


_sandbox_runner: Optional[SandboxRunner] = None


def get_sandbox_runner() -> SandboxRunner:
    """Get the global sandbox runner instance."""
    global _sandbox_runner
    if _sandbox_runner is None:
        _sandbox_runner = SandboxRunner()
    return _sandbox_runner
