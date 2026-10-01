"""Small dependency-injection container used by the CLI composition root."""

from __future__ import annotations

import inspect
from typing import Any, Callable, TypeVar

T = TypeVar("T")


class ContainerError(Exception):
    """Base class for dependency-container errors."""


class ServiceNotFoundError(ContainerError):
    """Raised when a service or required dependency is not registered."""

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(f"Service not found: {name}")


class CircularDependencyError(ContainerError):
    """Raised when resolving a service re-enters the current dependency chain."""

    def __init__(self, services: list[str]) -> None:
        self.services = services
        super().__init__(f"Circular dependency detected: {' -> '.join(services)}")


class Container:
    """Resolve explicitly registered factories with singleton-by-default scope."""

    def __init__(self) -> None:
        self._services: dict[str, tuple[Callable[..., Any], bool]] = {}
        self._instances: dict[str, Any] = {}

    @property
    def service_names(self) -> list[str]:
        return list(self._services)

    @property
    def instance_count(self) -> int:
        return len(self._instances)

    def register(
        self,
        name: str,
        factory: Callable[..., T],
        singleton: bool = True,
    ) -> None:
        if name in self._services:
            raise ValueError(f"Service already registered: {name}")
        self._services[name] = (factory, singleton)

    def resolve(self, name: str, **overrides: Any) -> Any:
        """Resolve a service and recursively inject parameters by name."""
        return self._resolve(name, overrides, [])

    def _resolve(
        self,
        name: str,
        overrides: dict[str, Any],
        chain: list[str],
    ) -> Any:
        if name in overrides:
            return overrides[name]
        if name in self._instances:
            return self._instances[name]
        if name in chain:
            raise CircularDependencyError([*chain, name])
        if name not in self._services:
            raise ServiceNotFoundError(name)

        factory, singleton = self._services[name]
        signature = inspect.signature(factory)
        dependencies: dict[str, Any] = {}
        next_chain = [*chain, name]

        for parameter_name, parameter in signature.parameters.items():
            if parameter.kind in (
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            ):
                continue
            if parameter_name in overrides:
                dependencies[parameter_name] = overrides[parameter_name]
            elif parameter.default is not inspect.Parameter.empty:
                dependencies[parameter_name] = parameter.default
            else:
                dependencies[parameter_name] = self._resolve(
                    parameter_name,
                    overrides,
                    next_chain,
                )

        instance = factory(**dependencies)
        if singleton:
            self._instances[name] = instance
        return instance
