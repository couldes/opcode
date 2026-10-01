import pytest

from opcode_cli.shared.di.container import (
    CircularDependencyError,
    Container,
    ServiceNotFoundError,
)


def test_container_resolves_registered_singleton():
    container = Container()
    container.register("value", lambda: object())

    first = container.resolve("value")
    second = container.resolve("value")

    assert first is second
    assert container.instance_count == 1


def test_container_injects_registered_dependencies():
    container = Container()
    container.register("value", lambda: 3)
    container.register("doubled", lambda value: value * 2)

    assert container.resolve("doubled") == 6


def test_container_reports_missing_dependency():
    container = Container()
    container.register("service", lambda missing: missing)

    with pytest.raises(ServiceNotFoundError, match="missing"):
        container.resolve("service")


def test_container_detects_circular_dependency():
    container = Container()
    container.register("first", lambda second: second)
    container.register("second", lambda first: first)

    with pytest.raises(CircularDependencyError, match="first.*second.*first"):
        container.resolve("first")
