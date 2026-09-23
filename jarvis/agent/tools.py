"""JARVIS Agent - Tool System"""

import inspect
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional, Union, get_type_hints
from pydantic import BaseModel, Field as PydanticField, create_model


_ARGS_SECTION = re.compile(
    r"^[ 	]*(?:Args|Arguments|Parameters)\s*:\s*$", re.MULTILINE
)
_ARG_LINE = re.compile(r"^\s*(\w+)\s*(?:\([^)]*\))?\s*:\s*(.+)$")


def parse_arg_docs(docstring):
    """Extract per-parameter descriptions from a Google-style docstring.

    Returns a mapping of parameter name to description for the ``Args:``
    section, or an empty mapping when there is none. Tool schemas are all the
    planner sees, so a documented argument is worth far more to it than a
    generic placeholder.
    """
    if not docstring:
        return {}

    match = _ARGS_SECTION.search(docstring)
    if not match:
        return {}

    body = docstring[match.end():]
    docs = {}
    current = None

    for raw in body.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        # A new unindented section (Returns:, Raises:, ...) ends the block.
        if re.match(r"^\S", line):
            break

        arg_match = _ARG_LINE.match(line)
        if arg_match:
            current = arg_match.group(1)
            docs[current] = arg_match.group(2).strip()
        elif current:
            # Continuation of the previous argument's description.
            docs[current] = docs[current] + " " + line.strip()

    return docs


class ToolRiskLevel(str, Enum):
    """Risk level for tool execution."""
    SAFE = "safe"
    SENSITIVE = "sensitive"
    DANGEROUS = "dangerous"


@dataclass
class ToolParameter:
    """Tool parameter definition."""
    name: str
    type: type
    description: str
    required: bool = True
    default: Any = None


@dataclass
class ToolSchema:
    """Tool schema for LLM consumption."""
    name: str
    description: str
    parameters: list[ToolParameter] = field(default_factory=list)
    risk_level: ToolRiskLevel = ToolRiskLevel.SAFE
    returns: str = "Any"

    def to_openai_schema(self) -> dict[str, Any]:
        """Convert to OpenAI function calling schema."""
        properties = {}
        required = []

        for param in self.parameters:
            param_schema = self._type_to_schema(param.type)
            param_schema["description"] = param.description
            properties[param.name] = param_schema

            if param.required:
                required.append(param.name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }

    def _type_to_schema(self, py_type: type) -> dict[str, Any]:
        """Convert Python type to JSON schema."""
        origin = getattr(py_type, "__origin__", None)

        if origin is list or py_type is list:
            return {"type": "array", "items": {"type": "string"}}
        if origin is dict or py_type is dict:
            return {"type": "object"}
        if py_type is str:
            return {"type": "string"}
        if py_type is int:
            return {"type": "integer"}
        if py_type is float:
            return {"type": "number"}
        if py_type is bool:
            return {"type": "boolean"}
        if py_type is Any:
            return {"type": "object"}

        # Handle Optional types
        if origin is Union:
            args = getattr(py_type, "__args__", ())
            non_none = [a for a in args if a is not type(None)]
            if len(non_none) == 1:
                return self._type_to_schema(non_none[0])

        return {"type": "string"}


def _coerce(value, target):
    """Best-effort coercion of a planner-supplied value to the declared type.

    An LLM routinely emits "60" where an int is wanted, or "true" for a bool.
    Coercing here keeps a step from failing on a formatting detail; a value
    that cannot be converted passes through unchanged so the tool itself can
    report a meaningful error.
    """
    if value is None or target is Any:
        return value

    origin = getattr(target, "__origin__", None)
    if origin is Union:
        args = [a for a in getattr(target, "__args__", ()) if a is not type(None)]
        if len(args) != 1:
            return value
        target = args[0]
        origin = getattr(target, "__origin__", None)

    try:
        if target is bool and not isinstance(value, bool):
            if isinstance(value, str):
                lowered = value.strip().lower()
                if lowered in ("true", "yes", "1", "on"):
                    return True
                if lowered in ("false", "no", "0", "off"):
                    return False
                return value
            return bool(value)

        if target is int and not isinstance(value, (bool, int)):
            return int(float(value))

        if target is float and not isinstance(value, float):
            return float(value)

        if target is str and not isinstance(value, str):
            return str(value)

        if (target is list or origin is list) and isinstance(value, (tuple, set)):
            return list(value)

    except (TypeError, ValueError):
        return value

    return value


class ToolResult(BaseModel):
    """Standard tool result."""
    success: bool
    data: Any = None
    error: Optional[str] = None
    metadata: dict[str, Any] = PydanticField(default_factory=dict)


class BaseTool(ABC):
    """Base class for all tools."""

    def __init__(self):
        self._schema = self._build_schema()

    @property
    @abstractmethod
    def name(self) -> str:
        """Tool name."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Tool description."""
        pass

    @property
    def risk_level(self) -> ToolRiskLevel:
        """Tool risk level."""
        return ToolRiskLevel.SAFE

    @property
    def requires_approval(self) -> bool:
        """Whether this tool requires user approval."""
        return self.risk_level in (ToolRiskLevel.SENSITIVE, ToolRiskLevel.DANGEROUS)

    @property
    def schema(self) -> ToolSchema:
        """Get tool schema."""
        return self._schema

    @property
    def parameter_descriptions(self) -> dict[str, str]:
        """Per-parameter descriptions, overriding any parsed from the docstring."""
        return {}

    def _build_schema(self) -> ToolSchema:
        """Build schema from execute method signature."""
        sig = inspect.signature(self.execute)
        try:
            type_hints = get_type_hints(self.execute)
        except Exception:
            # An unresolvable annotation should not stop the tool registering.
            type_hints = getattr(self.execute, "__annotations__", {})

        # A documented argument beats the generic placeholder, and an explicit
        # override on the tool beats both.
        arg_docs = parse_arg_docs(inspect.getdoc(self.execute))
        arg_docs.update(self.parameter_descriptions)

        parameters = []
        for param_name, param in sig.parameters.items():
            if param_name in ("self", "kwargs"):
                continue

            param_type = type_hints.get(param_name, Any)
            default = param.default if param.default != inspect.Parameter.empty else None
            required = param.default == inspect.Parameter.empty

            parameters.append(ToolParameter(
                name=param_name,
                type=param_type,
                description=arg_docs.get(param_name, f"Parameter {param_name}"),
                required=required,
                default=default,
            ))

        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters=parameters,
            risk_level=self.risk_level,
            returns=str(type_hints.get("return", "Any")),
        )

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """Execute the tool."""
        pass

    def validate_args(self, args: dict[str, Any]) -> dict[str, Any]:
        """Validate and coerce arguments."""
        args = args or {}
        validated = {}
        known = {p.name for p in self.schema.parameters}

        unknown = set(args) - known
        if unknown:
            # A planner occasionally invents an argument; drop it rather than
            # failing the whole step, but say so.
            from jarvis.core.logging import get_logger

            get_logger(__name__).warning(
                f"{self.name}: ignoring unknown argument(s): {', '.join(sorted(unknown))}"
            )

        for param in self.schema.parameters:
            if param.name in args:
                validated[param.name] = _coerce(args[param.name], param.type)
            elif param.required:
                raise ValueError(f"{self.name}: required parameter missing: {param.name}")
            elif param.default is not None:
                validated[param.name] = param.default
        return validated


class ToolRegistry:
    """Registry for managing available tools."""

    def __init__(self):
        self._tools: dict[str, BaseTool] = {}
        self._categories: dict[str, list[str]] = {}

    def register(self, tool: BaseTool, category: str = "general") -> None:
        """Register a tool."""
        if tool.name in self._tools:
            raise ValueError(f"Tool already registered: {tool.name}")

        self._tools[tool.name] = tool
        if category not in self._categories:
            self._categories[category] = []
        self._categories[category].append(tool.name)

    def unregister(self, name: str) -> None:
        """Unregister a tool."""
        if name in self._tools:
            tool = self._tools.pop(name)
            for cat, tools in self._categories.items():
                if name in tools:
                    tools.remove(name)

    def get(self, name: str) -> Optional[BaseTool]:
        """Get a tool by name."""
        return self._tools.get(name)

    def get_all(self) -> list[BaseTool]:
        """Get all registered tools."""
        return list(self._tools.values())

    def get_by_category(self, category: str) -> list[BaseTool]:
        """Get tools by category."""
        names = self._categories.get(category, [])
        return [self._tools[n] for n in names if n in self._tools]

    def get_schemas(self) -> list[ToolSchema]:
        """Get all tool schemas for LLM."""
        return [tool.schema for tool in self._tools.values()]

    def get_openai_schemas(self) -> list[dict[str, Any]]:
        """Get OpenAI-compatible schemas."""
        return [tool.schema.to_openai_schema() for tool in self._tools.values()]

    def list_tools(self) -> dict[str, dict[str, Any]]:
        """List all tools with metadata."""
        return {
            name: {
                "name": tool.name,
                "description": tool.description,
                "risk_level": tool.risk_level.value,
                "requires_approval": tool.requires_approval,
                "parameters": [
                    {
                        "name": p.name,
                        "type": str(p.type),
                        "description": p.description,
                        "required": p.required,
                    }
                    for p in tool.schema.parameters
                ],
            }
            for name, tool in self._tools.items()
        }


# Global registry instance
_registry: Optional[ToolRegistry] = None


def get_registry() -> ToolRegistry:
    """Get global tool registry."""
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry


def register_tool(tool: BaseTool, category: str = "general") -> None:
    """Register a tool globally."""
    get_registry().register(tool, category)