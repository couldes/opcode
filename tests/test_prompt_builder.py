from opcode_cli.prompt.builder import PromptModule, SystemPromptBuilder


def test_prompt_module_creation():
    m = PromptModule(name="test", priority=1, content="hello")
    assert m.name == "test"
    assert m.priority == 1
    assert m.content == "hello"


def test_register_single_module():
    builder = SystemPromptBuilder()
    builder.register(PromptModule(name="a", priority=2, content="module a"))
    assert len(builder.modules) == 1


def test_register_many():
    builder = SystemPromptBuilder()
    builder.register_many([
        PromptModule(name="a", priority=2, content="module a"),
        PromptModule(name="b", priority=1, content="module b"),
    ])
    assert len(builder.modules) == 2


def test_get_system_text_priority_order():
    builder = SystemPromptBuilder()
    builder.register(PromptModule(name="a", priority=3, content="third"))
    builder.register(PromptModule(name="b", priority=1, content="first"))
    builder.register(PromptModule(name="c", priority=2, content="second"))

    text = builder.get_system_text()
    parts = text.split("\n\n")
    assert parts[0] == "first"
    assert parts[1] == "second"
    assert parts[2] == "third"


def test_get_system_text_cache_marker():
    builder = SystemPromptBuilder()
    builder.register(PromptModule(name="a", priority=1, content="hello"))

    text = builder.get_system_text()
    assert "<!-- cache_control: ephemeral -->" in text


def test_get_system_text_env_context():
    builder = SystemPromptBuilder()
    builder.register(PromptModule(name="a", priority=1, content="hello"))

    text = builder.get_system_text(env_context="<env>\nworkspace: /tmp\n</env>")
    assert "<env>" in text
    assert "workspace: /tmp" in text
    assert "<!-- cache_control: ephemeral -->" in text


def test_get_system_text_filters_empty_content():
    builder = SystemPromptBuilder()
    builder.register(PromptModule(name="a", priority=1, content="hello"))
    builder.register(PromptModule(name="empty", priority=2, content=""))

    text = builder.get_system_text()
    assert "hello" in text
    parts = text.split("\n\n")
    assert len([p for p in parts if "hello" in p]) == 1


def test_get_system_text_modules_separated_by_double_newline():
    builder = SystemPromptBuilder()
    builder.register(PromptModule(name="a", priority=1, content="first"))
    builder.register(PromptModule(name="b", priority=2, content="second"))

    text = builder.get_system_text()
    assert "\n\n" in text
