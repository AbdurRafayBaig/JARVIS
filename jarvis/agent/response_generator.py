"""JARVIS Agent - Response Generator

Generates natural language responses and summaries after task execution.
"""

from typing import Any, Optional
from jarvis.agent.task import Task, TaskStatus, StepStatus
from jarvis.llm.manager import get_llm
from jarvis.llm.providers import Message
from jarvis.core.logging import get_logger

logger = get_logger(__name__)


class ResponseGenerator:
    """Generates natural language responses for completed agent tasks."""

    def __init__(self, llm_provider: Optional[Any] = None):
        self.llm = llm_provider

    async def generate_response(
        self,
        task: Task,
        personality_mode: str = "jarvis",
    ) -> str:
        """Generate a natural language summary of the task result."""
        # If task used the 'respond' tool, return its direct result
        for step in task.steps:
            if step.tool_name == "respond" and step.status == StepStatus.COMPLETED:
                if isinstance(step.result, str):
                    return step.result

        if not self.llm:
            try:
                self.llm = get_llm()
            except Exception:
                pass

        # Fallback if no LLM available
        if not self.llm:
            if task.status == TaskStatus.COMPLETED:
                return f"Task completed successfully: {task.goal}"
            else:
                return f"Task failed: {task.error or 'Unknown error'}"

        # Construct prompt for LLM summary
        steps_summary = []
        for step in task.steps:
            status_str = step.status.value.upper()
            res_str = str(step.result)[:200] if step.result else ""
            err_str = f" Error: {step.error}" if step.error else ""
            steps_summary.append(
                f"- {step.description} [{status_str}]: {res_str}{err_str}"
            )

        steps_text = "\n".join(steps_summary)

        system_prompt = f"""You are JARVIS, a Tony Stark-style personal AI computer agent for Windows.
Synthesize a concise, helpful, and natural response to the user summarizing what was accomplished.

Personality Mode: {personality_mode}
- "jarvis": Professional, crisp, intelligent ("Done. Visual Studio Code has been opened.")
- "professional": Formal, technical ("The operation completed successfully.")
- "minimal": Brief, direct ("Done.")

Rules:
1. Don't show raw JSON or debug output.
2. State clearly whether the request succeeded or failed.
3. If an error occurred, explain it simply.
4. Keep responses under 3-4 sentences unless detailed explanation was asked."""

        user_prompt = f"""Goal: {task.goal}
Task Status: {task.status.value}
Error (if any): {task.error or 'None'}

Execution Steps:
{steps_text}

Provide the final natural response for the user."""

        try:
            messages = [
                Message(role="system", content=system_prompt),
                Message(role="user", content=user_prompt),
            ]
            resp = await self.llm.chat_completion(messages)
            return resp.content.strip() if resp.content else "Task completed."
        except Exception as e:
            logger.error(f"Response generation failed: {e}")
            if task.status == TaskStatus.COMPLETED:
                return f"Done. {task.goal}"
            return f"Task failed: {task.error or str(e)}"
