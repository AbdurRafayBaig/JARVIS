"""Step Context

Lets a planned step consume the results of earlier steps.

The planner writes the whole plan up front, so it cannot know a value that
only exists once an earlier tool has run -- a file it just listed, a repo URL
GitHub just returned, the text it just read. A step may therefore reference an
earlier result with a placeholder, which is substituted just before the tool
executes:

    {{step_1.result}}     result of the first step (1-based)
    {{step_2}}            shorthand for {{step_2.result}}
    {{previous.result}}   result of the most recently completed step
    {{step_1.result.url}} key "url" of a dict result

A placeholder that fills a whole string yields the raw value, so dicts and
lists keep their type; a placeholder embedded in surrounding text is
stringified.
"""

import re
from typing import Any, Optional

from loguru import logger

from jarvis.agent.task import TaskStep, StepStatus

# {{ step_3.result.url }} -> ("step_3", ".result.url")
_PLACEHOLDER = re.compile(r"\{\{\s*([A-Za-z_][\w]*)\s*((?:\.[\w]+)*)\s*\}\}")


class StepContext:
    """Holds completed step results for placeholder substitution."""

    def __init__(self):
        self._results: list[Any] = []

    def record(self, step: TaskStep) -> None:
        """Record a completed step's result."""
        self._results.append(step.result)

    @property
    def count(self) -> int:
        return len(self._results)

    def _lookup(self, ref: str) -> tuple[bool, Any]:
        """Resolve a bare reference to a recorded result."""
        if ref == "previous":
            if not self._results:
                return False, None
            return True, self._results[-1]

        if ref.startswith("step_"):
            try:
                index = int(ref[5:])
            except ValueError:
                return False, None
            # step_1 is the first step; negative indices count from the end.
            if index > 0 and index <= len(self._results):
                return True, self._results[index - 1]
            if index < 0 and -index <= len(self._results):
                return True, self._results[index]
            return False, None

        return False, None

    @staticmethod
    def _walk(value: Any, path: str) -> tuple[bool, Any]:
        """Follow a dotted path such as '.result.url' into a value."""
        for part in [p for p in path.split(".") if p]:
            if part == "result":
                # The reference already yields the step's result.
                continue
            if isinstance(value, dict) and part in value:
                value = value[part]
            elif isinstance(value, (list, tuple)) and part.isdigit():
                index = int(part)
                if index >= len(value):
                    return False, None
                value = value[index]
            elif hasattr(value, part):
                value = getattr(value, part)
            else:
                return False, None
        return True, value

    def resolve(self, value: Any) -> Any:
        """Substitute placeholders anywhere inside a value."""
        if isinstance(value, str):
            return self._resolve_string(value)
        if isinstance(value, dict):
            return {k: self.resolve(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self.resolve(v) for v in value]
        return value

    def _resolve_string(self, text: str) -> Any:
        whole = _PLACEHOLDER.fullmatch(text.strip())
        if whole:
            ok, resolved = self._resolve_match(whole)
            return resolved if ok else text

        def replace(match: re.Match) -> str:
            ok, resolved = self._resolve_match(match)
            return str(resolved) if ok else match.group(0)

        return _PLACEHOLDER.sub(replace, text)

    def _resolve_match(self, match: re.Match) -> tuple[bool, Any]:
        ref, path = match.group(1), match.group(2)
        found, value = self._lookup(ref)
        if not found:
            logger.warning(f"Unresolved step placeholder: {match.group(0)}")
            return False, None
        return self._walk(value, path)

    def resolve_args(self, args: Optional[dict]) -> dict:
        """Resolve every placeholder in a step's tool arguments."""
        if not args:
            return {}
        return {k: self.resolve(v) for k, v in args.items()}


def rebuild_context(steps: list[TaskStep]) -> StepContext:
    """Rebuild a context from steps that have already completed."""
    context = StepContext()
    for step in steps:
        if step.status == StepStatus.COMPLETED:
            context.record(step)
    return context
