from argparse import Namespace

from opcode_cli.presentation.cli.entry import create_application_container


def test_create_application_container_builds_agent_dependencies():
    args = Namespace(
        config="opcode.yaml",
        provider=None,
        max_iterations=25,
        mode=None,
        team=None,
        member=None,
        backend="auto",
        command=None,
    )

    container = create_application_container(args)
    agent = container.resolve("agent")

    assert agent._provider is not None
    assert agent._registry is not None
    assert agent._permission_checker is not None
    assert agent._context_manager is not None
    assert agent._builder is not None
    assert agent._injector is not None
    assert "command_registry" in container.service_names
