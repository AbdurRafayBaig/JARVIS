"""Local Summary

Plain-language replies for direct commands, written without a language
model. A request like "volume up" is already answered by what the tool did;
sending that to an LLM to be rephrased would add a network round trip (and a
failure mode) to the fastest path JARVIS has.
"""

from pathlib import Path
from typing import Any, Callable

from jarvis.agent.task import Task, TaskStatus, StepStatus, TaskStep

# Steps that exist only to make a plan work and are not worth mentioning.
_SILENT_TOOLS = {"wait"}


def _time(data: Any) -> str:
    return f"It's {data['time'][:5]} on {data['day_of_week']}, {data['date']}."


def _system(data: Any) -> str:
    return (
        f"CPU is at {data['cpu_percent']}%, memory {data['memory_used_percent']}% used of "
        f"{data['memory_total_gb']} GB, disk {data['disk_usage_percent']}% full. "
        f"{data['os']} {data['os_version']} on {data['hostname']}."
    )


def _directory(data: Any) -> str:
    items = data.get("items", [])
    name = Path(data.get("path", "")).name or data.get("path", "")
    if not items:
        return f"{name} is empty."
    names = [("[" + i["name"] + "]") if i.get("type") in ("dir", "directory") else i["name"] for i in items[:15]]
    more = f" and {len(items) - 15} more" if len(items) > 15 else ""
    return f"{name} has {len(items)} items: {', '.join(names)}{more}."


def _search(data: Any) -> str:
    results = data.get("results", [])
    if not results:
        return f"I found nothing matching {data.get('pattern', 'that')}."
    paths = [r["path"] for r in results[:8]]
    more = f"\n...and {len(results) - 8} more" if len(results) > 8 else ""
    return f"I found {len(results)} match(es):\n" + "\n".join(paths) + more


def _windows(data: Any) -> str:
    titles = [w["title"] for w in data.get("windows", []) if w.get("title")]
    if not titles:
        return "No windows are open."
    return f"{len(titles)} windows are open: " + "; ".join(titles[:12]) + "."


def _processes(data: Any) -> str:
    rows = data.get("processes", [])
    parts = [f"{p['name']} ({p['memory_percent']:.1f}% memory)" for p in rows[:10]]
    return "Top processes: " + ", ".join(parts) + "."


def _clipboard(data: Any) -> str:
    text = (data.get("text") or "").strip()
    return f"The clipboard contains: {text[:500]}" if text else "The clipboard is empty."


def _screenshot(data: Any) -> str:
    return f"Screenshot saved to {data.get('path')}."


def _created(kind: str) -> Callable[[Any], str]:
    def render(data: Any) -> str:
        path = data.get("path") if isinstance(data, dict) else data
        return f"Created {kind} {Path(str(path)).name} in {Path(str(path)).parent}."
    return render


_FORMATTERS: dict[str, Callable[[Any], str]] = {
    "get_current_time": _time,
    "get_system_info": _system,
    "list_directory": _directory,
    "search_files": _search,
    "list_windows": _windows,
    "list_processes": _processes,
    "get_clipboard": _clipboard,
    "take_screenshot": _screenshot,
    "create_directory": _created("folder"),
    "create_file": _created("file"),
}


def _describe(step: TaskStep) -> str:
    """One sentence for a completed step."""
    formatter = _FORMATTERS.get(step.tool_name)
    if formatter is not None:
        try:
            return formatter(step.result)
        except Exception:
            pass

    if isinstance(step.result, str) and step.result.strip():
        text = step.result.strip()
        return text if text.endswith((".", "!", "?")) else f"{text}."

    return f"{step.description}: done."


def summarize_locally(task: Task) -> str:
    """Summarise a task from its step results, with no model involved."""
    lines: list[str] = []

    for step in task.steps:
        if step.tool_name in _SILENT_TOOLS:
            continue
        if step.status == StepStatus.COMPLETED:
            lines.append(_describe(step))
        elif step.status == StepStatus.FAILED:
            reason = step.error or "it failed"
            lines.append(f"I couldn't {_lower_first(step.description)}: {reason}")

    if not lines:
        if task.status == TaskStatus.COMPLETED:
            return "Done."
        return f"That didn't work: {task.error or 'unknown error'}"

    return " ".join(lines) if all("\n" not in line for line in lines) else "\n".join(lines)


def _lower_first(text: str) -> str:
    return text[:1].lower() + text[1:] if text else text
