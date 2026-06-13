"""
Action Registry — 动作注册表
Decorator-based tool registration with auto schema generation.
Inspired by Browser-use @controller.action() and Composio ToolSet.

@module: core.action_registry
"""
from __future__ import annotations

import asyncio
import inspect
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, get_type_hints

logger = logging.getLogger("Nonull.actions")

_PYTHON_TYPE_TO_JSON_SCHEMA = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
}


@dataclass
class ActionInfo:
    name: str
    description: str
    parameters: Dict[str, Any]
    handler: Callable
    tags: List[str] = field(default_factory=list)
    enabled: bool = True


@dataclass
class ActionResult:
    success: bool
    data: Any = None
    error: Optional[str] = None
    duration_ms: float = 0.0


def _is_optional(annotation: Any) -> tuple[bool, Any]:
    origin = getattr(annotation, "__origin__", None)
    args = getattr(annotation, "__args__", None)
    if origin is not None and args is not None:
        # Optional[X] is Union[X, None]
        if type(None) in args and len(args) == 2:
            inner = args[0] if args[1] is type(None) else args[1]
            return True, inner
    return False, annotation


def _type_to_json_schema(annotation: Any) -> Dict[str, Any]:
    optional, inner = _is_optional(annotation)

    origin = getattr(inner, "__origin__", None)
    args = getattr(inner, "__args__", None)

    if inner in _PYTHON_TYPE_TO_JSON_SCHEMA:
        return {"type": _PYTHON_TYPE_TO_JSON_SCHEMA[inner]}

    if origin is list or origin is List:
        schema: Dict[str, Any] = {"type": "array"}
        if args:
            schema["items"] = _type_to_json_schema(args[0])
        return schema

    if origin is dict or origin is Dict:
        return {"type": "object"}

    return {"type": "string"}


def _build_parameters_schema(func: Callable) -> Dict[str, Any]:
    try:
        hints = get_type_hints(func)
    except Exception:
        hints = {}

    sig = inspect.signature(func)
    properties: Dict[str, Any] = {}
    required: List[str] = []

    for param_name, param in sig.parameters.items():
        if param_name in ("self", "cls"):
            continue

        annotation = hints.get(param_name, param.annotation)
        if annotation is inspect.Parameter.empty:
            prop_schema: Dict[str, Any] = {"type": "string"}
        else:
            optional, _ = _is_optional(annotation)
            prop_schema = _type_to_json_schema(annotation)
            if not optional and param.default is inspect.Parameter.empty:
                required.append(param_name)

        if param.default not in (inspect.Parameter.empty, None):
            prop_schema["default"] = param.default

        properties[param_name] = prop_schema

    schema: Dict[str, Any] = {
        "type": "object",
        "properties": properties,
    }
    if required:
        schema["required"] = required
    return schema


class ActionRegistry:
    def __init__(self) -> None:
        self._actions: Dict[str, ActionInfo] = {}
        self._lock = threading.Lock()

    def action(
        self,
        name: str,
        description: str,
        tags: Optional[List[str]] = None,
    ) -> Callable:
        def decorator(func: Callable) -> Callable:
            func._action_meta = {
                "name": name,
                "description": description,
                "tags": tags or [],
            }
            schema = _build_parameters_schema(func)
            info = ActionInfo(
                name=name,
                description=description,
                parameters=schema,
                handler=func,
                tags=tags or [],
            )
            with self._lock:
                self._actions[name] = info
            logger.debug("Registered action: %s", name)
            return func

        return decorator

    def register(
        self,
        name: str,
        handler: Callable,
        description: str,
        parameters: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
    ) -> None:
        schema = parameters if parameters is not None else _build_parameters_schema(handler)
        info = ActionInfo(
            name=name,
            description=description,
            parameters=schema,
            handler=handler,
            tags=tags or [],
        )
        with self._lock:
            self._actions[name] = info
        logger.debug("Registered action: %s", name)

    def unregister(self, name: str) -> bool:
        with self._lock:
            removed = self._actions.pop(name, None)
        if removed:
            logger.debug("Unregistered action: %s", name)
            return True
        return False

    def execute(self, name: str, **kwargs: Any) -> ActionResult:
        info = self.get(name)
        if info is None:
            return ActionResult(success=False, error=f"Action not found: {name}")
        if not info.enabled:
            return ActionResult(success=False, error=f"Action is disabled: {name}")

        start = time.perf_counter()
        try:
            if asyncio.iscoroutinefunction(info.handler):
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None

                if loop and loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                        result = pool.submit(
                            lambda: asyncio.run(info.handler(**kwargs))
                        ).result()
                else:
                    result = asyncio.run(info.handler(**kwargs))
            else:
                result = info.handler(**kwargs)

            elapsed = (time.perf_counter() - start) * 1000
            return ActionResult(success=True, data=result, duration_ms=elapsed)
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            logger.error("Action %s failed: %s", name, exc, exc_info=True)
            return ActionResult(success=False, error=str(exc), duration_ms=elapsed)

    def get(self, name: str) -> Optional[ActionInfo]:
        with self._lock:
            return self._actions.get(name)

    def list_actions(self, tag: Optional[str] = None) -> List[ActionInfo]:
        with self._lock:
            actions = list(self._actions.values())
        if tag is not None:
            actions = [a for a in actions if tag in a.tags]
        return actions

    def to_openai_tools(self) -> List[Dict[str, Any]]:
        tools: List[Dict[str, Any]] = []
        with self._lock:
            actions = list(self._actions.values())
        for info in actions:
            if not info.enabled:
                continue
            tools.append({
                "type": "function",
                "function": {
                    "name": info.name,
                    "description": info.description,
                    "parameters": info.parameters,
                },
            })
        return tools

    def from_class(self, obj: Any) -> None:
        for attr_name in dir(obj):
            try:
                method = getattr(obj, attr_name)
            except Exception:
                continue
            meta = getattr(method, "_action_meta", None)
            if meta is None:
                continue
            schema = _build_parameters_schema(method)
            info = ActionInfo(
                name=meta["name"],
                description=meta["description"],
                parameters=schema,
                handler=method,
                tags=meta.get("tags", []),
            )
            with self._lock:
                self._actions[meta["name"]] = info
            logger.debug("Registered action from class: %s", meta["name"])

    def __len__(self) -> int:
        with self._lock:
            return len(self._actions)

    def __contains__(self, name: str) -> bool:
        with self._lock:
            return name in self._actions

    def __repr__(self) -> str:
        with self._lock:
            names = list(self._actions.keys())
        return f"ActionRegistry(actions={names})"
