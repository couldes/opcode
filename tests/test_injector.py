from opcode_cli.prompt.injector import PlanModeInjector


def test_injector_returns_none_for_no_mode():
    injector = PlanModeInjector()
    assert injector.get_instruction(1, None) is None
    assert injector.get_instruction(5, None) is None


def test_injector_full_on_first_iteration_plan():
    injector = PlanModeInjector()
    result = injector.get_instruction(1, "plan")
    assert result is not None
    assert "PLAN MODE" in result
    assert "read-only" in result.lower()


def test_injector_slim_on_second_iteration_plan():
    injector = PlanModeInjector()
    full = injector.get_instruction(1, "plan")
    slim = injector.get_instruction(2, "plan")
    assert slim is not None
    assert len(slim) < len(full)
    assert "PLAN MODE" in slim


def test_injector_full_every_fifth_iteration_plan():
    injector = PlanModeInjector()
    full = injector.get_instruction(1, "plan")

    for i in [2, 3, 4]:
        assert len(injector.get_instruction(i, "plan")) < len(full)

    assert len(injector.get_instruction(5, "plan")) == len(full)
    assert len(injector.get_instruction(10, "plan")) == len(full)


def test_injector_full_on_first_iteration_do():
    injector = PlanModeInjector()
    result = injector.get_instruction(1, "do")
    assert result is not None
    assert "DO MODE" in result


def test_injector_slim_on_third_iteration_do():
    injector = PlanModeInjector()
    full = injector.get_instruction(1, "do")
    slim = injector.get_instruction(3, "do")
    assert slim is not None
    assert len(slim) < len(full)
    assert "DO MODE" in slim


def test_injector_slim_plan_is_short():
    injector = PlanModeInjector()
    slim = injector.get_instruction(2, "plan")
    # Slim should be at most 3 sentences
    sentences = [s.strip() for s in slim.replace("\n", " ").split(".") if s.strip()]
    assert len(sentences) <= 3


def test_injector_unknown_mode_returns_none():
    injector = PlanModeInjector()
    assert injector.get_instruction(1, "unknown") is None
