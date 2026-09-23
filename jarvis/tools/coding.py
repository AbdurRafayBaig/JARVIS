"""JARVIS Tools - Coding Tools"""

import asyncio
import subprocess
import os
from pathlib import Path
from typing import Any, Optional

from jarvis.agent.tools import BaseTool, ToolResult, ToolRiskLevel, register_tool
from jarvis.core.logging import get_logger
from jarvis.core.config import get_settings

logger = get_logger(__name__)


class RunPythonTool(BaseTool):
    """Run a Python script."""

    @property
    def name(self) -> str:
        return "run_python"

    @property
    def description(self) -> str:
        return "Run a Python script or command"

    @property
    def risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.SENSITIVE

    async def execute(
        self,
        script: str,
        cwd: Optional[str] = None,
        args: list[str] = None,
        timeout: int = 120,
    ) -> ToolResult:
        """Run Python.

        Args:
            script: Python source to execute.
            cwd: Working directory to run it in.
            args: Command-line arguments passed to the script as sys.argv.
            timeout: Seconds to wait before killing the process.
        """
        try:
            cmd = ["python", "-c", script]
            if args:
                cmd.extend(args)

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )

            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.communicate()
                return ToolResult(success=False, error=f"Python script timed out after {timeout}s")

            return ToolResult(
                success=proc.returncode == 0,
                data={
                    "stdout": stdout.decode() if stdout else "",
                    "stderr": stderr.decode() if stderr else "",
                    "returncode": proc.returncode,
                },
                error=stderr.decode() if stderr and proc.returncode != 0 else None,
            )
        except Exception as e:
            logger.error(f"Run Python failed: {e}")
            return ToolResult(success=False, error=str(e))


class RunPythonFileTool(BaseTool):
    """Run a Python file."""

    @property
    def name(self) -> str:
        return "run_python_file"

    @property
    def description(self) -> str:
        return "Run a Python file"

    @property
    def risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.SENSITIVE

    async def execute(
        self,
        file_path: str,
        cwd: Optional[str] = None,
        args: list[str] = None,
        timeout: int = 120,
    ) -> ToolResult:
        """Run Python file.

        Args:
            file_path: Path of the .py file to run.
            cwd: Working directory to run it in.
            args: Command-line arguments passed to the script.
            timeout: Seconds to wait before killing the process.
        """
        try:
            cmd = ["python", file_path]
            if args:
                cmd.extend(args)

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )

            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.communicate()
                return ToolResult(success=False, error=f"Python file timed out after {timeout}s")

            return ToolResult(
                success=proc.returncode == 0,
                data={
                    "stdout": stdout.decode() if stdout else "",
                    "stderr": stderr.decode() if stderr else "",
                    "returncode": proc.returncode,
                },
                error=stderr.decode() if stderr and proc.returncode != 0 else None,
            )
        except Exception as e:
            logger.error(f"Run Python file failed: {e}")
            return ToolResult(success=False, error=str(e))


class RunTestsTool(BaseTool):
    """Run tests (pytest)."""

    @property
    def name(self) -> str:
        return "run_tests"

    @property
    def description(self) -> str:
        return "Run pytest tests"

    @property
    def risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.SAFE

    async def execute(
        self,
        path: str = ".",
        pattern: str = "test_*.py",
        cwd: Optional[str] = None,
        timeout: int = 300,
        extra_args: list[str] = None,
    ) -> ToolResult:
        """Run tests.

        Args:
            path: Directory or test file to run.
            pattern: Test file pattern to collect, such as 'test_*.py'.
            cwd: Working directory, normally the project root.
            timeout: Seconds to wait before killing the run.
            extra_args: Extra pytest arguments, such as ['-v', '-k', 'auth'].
        """
        try:
            cmd = ["python", "-m", "pytest", path, "-k", pattern, "-v", "--tb=short"]
            if extra_args:
                cmd.extend(extra_args)

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )

            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.communicate()
                return ToolResult(success=False, error=f"Tests timed out after {timeout}s")

            output = stdout.decode() if stdout else ""
            error_output = stderr.decode() if stderr else ""

            # Parse test results
            passed = output.count("PASSED")
            failed = output.count("FAILED")
            errors = output.count("ERROR")

            return ToolResult(
                success=proc.returncode == 0,
                data={
                    "stdout": output,
                    "stderr": error_output,
                    "returncode": proc.returncode,
                    "passed": passed,
                    "failed": failed,
                    "errors": errors,
                },
                error=error_output if proc.returncode != 0 else None,
            )
        except Exception as e:
            logger.error(f"Run tests failed: {e}")
            return ToolResult(success=False, error=str(e))


class InstallPackageTool(BaseTool):
    """Install Python package via pip."""

    @property
    def name(self) -> str:
        return "install_package"

    @property
    def description(self) -> str:
        return "Install a Python package using pip"

    @property
    def risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.SENSITIVE

    async def execute(
        self,
        package: str,
        version: Optional[str] = None,
        index_url: Optional[str] = None,
        timeout: int = 120,
    ) -> ToolResult:
        """Install package.

        Args:
            package: Package name to install with pip.
            version: Exact version to pin. Omit for the latest.
            index_url: Alternative package index URL.
            timeout: Seconds to wait before giving up.
        """
        try:
            cmd = ["python", "-m", "pip", "install"]
            if index_url:
                cmd.extend(["--index-url", index_url])
            if version:
                cmd.append(f"{package}=={version}")
            else:
                cmd.append(package)

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.communicate()
                return ToolResult(success=False, error=f"Install timed out after {timeout}s")

            return ToolResult(
                success=proc.returncode == 0,
                data={
                    "stdout": stdout.decode() if stdout else "",
                    "stderr": stderr.decode() if stderr else "",
                    "returncode": proc.returncode,
                },
                error=stderr.decode() if stderr and proc.returncode != 0 else None,
            )
        except Exception as e:
            logger.error(f"Install package failed: {e}")
            return ToolResult(success=False, error=str(e))


class GitTool(BaseTool):
    """Git operations."""

    @property
    def name(self) -> str:
        return "git"

    @property
    def description(self) -> str:
        return "Run Git commands"

    @property
    def risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.SENSITIVE

    async def execute(
        self,
        command: str,
        cwd: Optional[str] = None,
        timeout: int = 60,
    ) -> ToolResult:
        """Run git command.

        Args:
            command: Git arguments without the leading 'git', e.g. 'log --oneline -5'.
            cwd: Repository directory.
            timeout: Seconds to wait before killing the command.
        """
        try:
            cmd = ["git"] + command.split()

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )

            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.communicate()
                return ToolResult(success=False, error=f"Git command timed out after {timeout}s")

            return ToolResult(
                success=proc.returncode == 0,
                data={
                    "stdout": stdout.decode() if stdout else "",
                    "stderr": stderr.decode() if stderr else "",
                    "returncode": proc.returncode,
                },
                error=stderr.decode() if stderr and proc.returncode != 0 else None,
            )
        except Exception as e:
            logger.error(f"Git command failed: {e}")
            return ToolResult(success=False, error=str(e))


class GitStatusTool(BaseTool):
    """Get git status."""

    @property
    def name(self) -> str:
        return "git_status"

    @property
    def description(self) -> str:
        return "Get git repository status"

    @property
    def risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.SAFE

    async def execute(self, cwd: Optional[str] = None) -> ToolResult:
        """Get git status.

        Args:
            cwd: Repository directory.
        """
        return await GitTool().execute("status --porcelain", cwd=cwd)


class GitInitTool(BaseTool):
    """Initialize git repository."""

    @property
    def name(self) -> str:
        return "git_init"

    @property
    def description(self) -> str:
        return "Initialize a new git repository"

    @property
    def risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.SENSITIVE

    async def execute(self, cwd: Optional[str] = None) -> ToolResult:
        """Init git repo.

        Args:
            cwd: Directory to turn into a git repository.
        """
        return await GitTool().execute("init", cwd=cwd)


class GitAddTool(BaseTool):
    """Add files to git."""

    @property
    def name(self) -> str:
        return "git_add"

    @property
    def description(self) -> str:
        return "Add files to git staging area"

    @property
    def risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.SAFE

    async def execute(self, files: str = ".", cwd: Optional[str] = None) -> ToolResult:
        """Git add.

        Args:
            files: Paths to stage, space separated. Use '.' for everything.
            cwd: Repository directory.
        """
        return await GitTool().execute(f"add {files}", cwd=cwd)


class GitCommitTool(BaseTool):
    """Commit changes."""

    @property
    def name(self) -> str:
        return "git_commit"

    @property
    def description(self) -> str:
        return "Commit staged changes"

    @property
    def risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.SENSITIVE

    async def execute(
        self,
        message: str,
        cwd: Optional[str] = None,
        author: Optional[str] = None,
    ) -> ToolResult:
        """Git commit.

        Args:
            message: Commit message.
            cwd: Repository directory.
            author: Override the commit author, as 'Name <email>'.
        """
        cmd = f'commit -m "{message}"'
        if author:
            cmd += f' --author="{author}"'
        return await GitTool().execute(cmd, cwd=cwd)


class GitPushTool(BaseTool):
    """Push to remote."""

    @property
    def name(self) -> str:
        return "git_push"

    @property
    def description(self) -> str:
        return "Push commits to remote repository"

    @property
    def risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.SENSITIVE

    async def execute(
        self,
        remote: str = "origin",
        branch: Optional[str] = None,
        force: bool = False,
        cwd: Optional[str] = None,
    ) -> ToolResult:
        """Git push.

        Args:
            remote: Remote name, usually 'origin'.
            branch: Branch to push. Omit to push the current branch.
            force: Force-push, overwriting remote history. Use with care.
            cwd: Repository directory.
        """
        cmd = f"push {remote}"
        if branch:
            cmd += f" {branch}"
        if force:
            cmd += " --force"
        return await GitTool().execute(cmd, cwd=cwd)


class GitPullTool(BaseTool):
    """Pull from remote."""

    @property
    def name(self) -> str:
        return "git_pull"

    @property
    def description(self) -> str:
        return "Pull changes from remote repository"

    @property
    def risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.SENSITIVE

    async def execute(
        self,
        remote: str = "origin",
        branch: Optional[str] = None,
        cwd: Optional[str] = None,
    ) -> ToolResult:
        """Git pull.

        Args:
            remote: Remote name, usually 'origin'.
            branch: Branch to pull. Omit for the current branch's upstream.
            cwd: Repository directory.
        """
        cmd = f"pull {remote}"
        if branch:
            cmd += f" {branch}"
        return await GitTool().execute(cmd, cwd=cwd)


class CreateGitIgnoreTool(BaseTool):
    """Create .gitignore file."""

    @property
    def name(self) -> str:
        return "create_gitignore"

    @property
    def description(self) -> str:
        return "Create a .gitignore file for a project type"

    @property
    def risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.SAFE

    async def execute(self, project_type: str = "python", cwd: Optional[str] = None) -> ToolResult:
        """Create gitignore.

        Args:
            project_type: Project type the ignore rules should target, such as python
                or node.
            cwd: Directory to write the .gitignore into.
        """
        try:
            gitignore_templates = {
                "python": """# Byte-compiled / optimized / DLL files
__pycache__/
*.py[cod]
*$py.class

# Virtual environments
venv/
env/
ENV/

# Distribution / Packaging
dist/
build/
*.egg-info/

# IDE
.vscode/
.idea/
*.swp
*.swo

# Testing
.coverage
htmlcov/
.pytest_cache/

# Environment
.env
.env.local

# OS
.DS_Store
Thumbs.db
""",
                "node": """# Dependencies
node_modules/

# Build
dist/
build/
*.log

# IDE
.vscode/
.idea/

# Environment
.env
.env.local

# OS
.DS_Store
Thumbs.db
""",
                "general": """# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Environment
.env
.env.local

# Logs
*.log
""",
            }

            template = gitignore_templates.get(project_type.lower(), gitignore_templates["general"])

            path = Path(cwd or ".") / ".gitignore"
            path.write_text(template)

            return ToolResult(success=True, data={"path": str(path), "type": project_type})
        except Exception as e:
            logger.error(f"Create gitignore failed: {e}")
            return ToolResult(success=False, error=str(e))


# Phase 4: File Editing, Directory Tree, Grep Search & Code Error Analysis Tools

class FileEditTool(BaseTool):
    """Replace target text in a file."""

    @property
    def name(self) -> str:
        return "edit_file"

    @property
    def description(self) -> str:
        return "Replace target text in a file with new content (exact string replacement)."

    @property
    def risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.SENSITIVE

    async def execute(self, path: str, target: str, replacement: str) -> ToolResult:
        """Edit file by replacing target string.

        Args:
            path: File to edit.
            target: Exact existing text to replace. It must appear in the file.
            replacement: Text to put in its place.
        """
        try:
            p = Path(path).resolve()
            if not p.exists():
                return ToolResult(success=False, error=f"File not found: {path}")

            content = p.read_text(encoding="utf-8")
            if target not in content:
                return ToolResult(success=False, error=f"Target text not found in {path}")

            new_content = content.replace(target, replacement, 1)
            p.write_text(new_content, encoding="utf-8")
            return ToolResult(success=True, data={"path": str(p), "status": "replaced"})
        except Exception as e:
            logger.error(f"Edit file failed: {e}")
            return ToolResult(success=False, error=str(e))


class FileTreeTool(BaseTool):
    """Generate directory tree string."""

    @property
    def name(self) -> str:
        return "file_tree"

    @property
    def description(self) -> str:
        return "Generate a visual text tree representation of a directory up to max_depth."

    @property
    def risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.SAFE

    async def execute(self, path: str = ".", max_depth: int = 3) -> ToolResult:
        """Generate file tree.

        Args:
            path: Directory to render as a tree.
            max_depth: How many levels deep to descend.
        """
        try:
            root = Path(path).resolve()
            if not root.exists():
                return ToolResult(success=False, error=f"Path not found: {path}")

            tree_lines = [f"{root.name}/"]

            def _build_tree(directory: Path, prefix: str = "", current_depth: int = 1):
                if current_depth > max_depth:
                    return
                items = sorted(list(directory.iterdir()), key=lambda x: (not x.is_dir(), x.name.lower()))
                # Filter common ignores
                items = [
                    item for item in items
                    if not item.name.startswith(".")
                    and item.name not in ("node_modules", "__pycache__", "venv", ".venv")
                ]
                for i, item in enumerate(items):
                    is_last = (i == len(items) - 1)
                    connector = "└── " if is_last else "├── "
                    tree_lines.append(f"{prefix}{connector}{item.name}{'/' if item.is_dir() else ''}")
                    if item.is_dir():
                        extension = "    " if is_last else "│   "
                        _build_tree(item, prefix + extension, current_depth + 1)

            _build_tree(root)
            tree_text = "\n".join(tree_lines)
            return ToolResult(success=True, data={"tree": tree_text, "lines_count": len(tree_lines)})
        except Exception as e:
            logger.error(f"File tree failed: {e}")
            return ToolResult(success=False, error=str(e))


class GrepSearchTool(BaseTool):
    """Search text or regex pattern across files."""

    @property
    def name(self) -> str:
        return "grep_search"

    @property
    def description(self) -> str:
        return "Search for matching text or pattern inside files in a workspace directory."

    @property
    def risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.SAFE

    async def execute(
        self,
        query: str,
        path: str = ".",
        file_extension: Optional[str] = None,
        max_results: int = 50,
    ) -> ToolResult:
        """Grep search.

        Args:
            query: Text or regular expression to search for.
            path: Directory to search in, recursively.
            file_extension: Limit the search to one extension, such as '.py'.
            max_results: Maximum number of matching lines to return.
        """
        try:
            import re
            root = Path(path).resolve()
            if not root.exists():
                return ToolResult(success=False, error=f"Path not found: {path}")

            regex = re.compile(query, re.IGNORECASE)
            matches = []

            pattern = f"*{file_extension}" if file_extension else "*"
            for file_path in root.rglob(pattern):
                if len(matches) >= max_results:
                    break
                if not file_path.is_file():
                    continue
                # Skip hidden/ignored
                if any(p.startswith(".") or p in ("node_modules", "__pycache__", "venv", ".venv") for p in file_path.parts):
                    continue

                try:
                    lines = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
                    for line_num, line in enumerate(lines, 1):
                        if regex.search(line):
                            matches.append({
                                "file": str(file_path.relative_to(root)),
                                "line_number": line_num,
                                "line_content": line.strip(),
                            })
                            if len(matches) >= max_results:
                                break
                except Exception:
                    continue

            return ToolResult(success=True, data={"query": query, "matches": matches, "count": len(matches)})
        except Exception as e:
            logger.error(f"Grep search failed: {e}")
            return ToolResult(success=False, error=str(e))


class AnalyzeCodeErrorTool(BaseTool):
    """Analyze error output and suggest code fix."""

    @property
    def name(self) -> str:
        return "analyze_code_error"

    @property
    def description(self) -> str:
        return "Analyze python error traceback or test failure output and identify root cause."

    @property
    def risk_level(self) -> ToolRiskLevel:
        return ToolRiskLevel.SAFE

    async def execute(self, error_text: str) -> ToolResult:
        """Analyze code error.

        Args:
            error_text: The full error message or traceback to diagnose.
        """
        try:
            lines = error_text.strip().splitlines()
            traceback_lines = [l for l in lines if "Error" in l or "Exception" in l or "Traceback" in l or "File " in l]
            summary = "\n".join(traceback_lines[-10:]) if traceback_lines else error_text[:500]

            return ToolResult(
                success=True,
                data={
                    "error_summary": summary,
                    "total_lines": len(lines),
                    "suggestion": "Review exception type and line number referenced in traceback.",
                },
            )
        except Exception as e:
            logger.error(f"Analyze error failed: {e}")
            return ToolResult(success=False, error=str(e))


# Register coding tools
def register_coding_tools():
    """Register all coding tools."""
    tools = [
        RunPythonTool(),
        RunPythonFileTool(),
        RunTestsTool(),
        InstallPackageTool(),
        GitTool(),
        GitStatusTool(),
        GitInitTool(),
        GitAddTool(),
        GitCommitTool(),
        GitPushTool(),
        GitPullTool(),
        CreateGitIgnoreTool(),
        FileEditTool(),
        FileTreeTool(),
        GrepSearchTool(),
        AnalyzeCodeErrorTool(),
    ]
    for tool in tools:
        register_tool(tool, category="coding")