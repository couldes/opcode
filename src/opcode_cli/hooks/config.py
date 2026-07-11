from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from opcode_cli.hooks.types import (
    ConditionGroup,
    ConditionRule,
    HookAction,
    HookCondition,
    HookDefinition,
)

logger = logging.getLogger(__name__)

KNOWN_EVENTS = frozenset({
    # Lifecycle
    "startup", "shutdown",
    "session_start", "session_end", "session_idle",
    "turn_start", "turn_end",
    "pre_send", "post_receive",
    # Iteration
    "iteration_start", "iteration_end",
    # User/assistant
    "user_input", "assistant_response",
    # Tool
    "tool_pre_execute", "tool_post_execute",
    "tool_permission_denied", "tool_error",
    # System
    "compression", "config_changed", "error",
})

VALID_ACTION_TYPES = frozenset({"command", "prompt", "http", "agent"})


def validate_hook(raw: dict) -> list[str]:
    errors: list[str] = []
    name = raw.get("name", "<unnamed>")

    # Required top-level fields
    if not raw.get("name"):
        errors.append(f"hook missing 'name'")
    if not raw.get("event"):
        errors.append(f"hook '{name}': missing 'event'")
    elif raw["event"] not in KNOWN_EVENTS:
        errors.append(
            f"hook '{name}': unknown event '{raw['event']}'"
        )

    if not raw.get("action"):
        errors.append(f"hook '{name}': missing 'action'")
    else:
        action = raw["action"]
        if not isinstance(action, dict):
            errors.append(f"hook '{name}': 'action' must be a dict")
        else:
            action_type = action.get("type", "")
            if action_type not in VALID_ACTION_TYPES:
                errors.append(
                    f"hook '{name}': unknown action type '{action_type}'"
                )
            elif action_type == "command" and not action.get("command"):
                errors.append(
                    f"hook '{name}': command action missing 'command' field"
                )
            elif action_type == "prompt" and not action.get("content"):
                errors.append(
                    f"hook '{name}': prompt action missing 'content' field"
                )
            elif action_type == "http" and not action.get("url"):
                errors.append(
                    f"hook '{name}': http action missing 'url' field"
                )

    # tool_pre_execute + background conflict
    if raw.get("event") == "tool_pre_execute" and raw.get("background"):
        errors.append(
            f"hook '{name}': tool_pre_execute event cannot use background: true"
        )

    # Condition validation (legacy + new format)
    if "if" in raw:
        cond = raw["if"]
        if not isinstance(cond, dict):
            errors.append(f"hook '{name}': 'if' must be a dict")
        else:
            _validate_condition_block(name, cond, errors)

    return errors


def _validate_condition_block(name: str, cond: dict, errors: list[str]) -> None:
    """Validate condition block. Supports legacy and new format."""
    has_legacy = "mode" in cond or "match" in cond
    has_new = any(k in cond for k in ("all", "any"))

    if has_legacy and "mode" in cond and cond["mode"] not in ("all", "any"):
        errors.append(
            f"hook '{name}': if.mode must be 'all' or 'any', got '{cond['mode']}'"
        )

    if has_new:
        for mode_key in ("all", "any"):
            if mode_key not in cond:
                continue
            rules = cond[mode_key]
            if not isinstance(rules, list):
                errors.append(
                    f"hook '{name}': if.{mode_key} must be a list, got {type(rules).__name__}"
                )
                continue
            for i, rule in enumerate(rules):
                if not isinstance(rule, dict):
                    errors.append(
                        f"hook '{name}': if.{mode_key}[{i}] must be a dict"
                    )
                    continue
                if "field" not in rule:
                    errors.append(
                        f"hook '{name}': if.{mode_key}[{i}] missing 'field'"
                    )
                if "operator" in rule and rule["operator"] not in ("==", "!=", "=~", "~="):
                    errors.append(
                        f"hook '{name}': if.{mode_key}[{i}] invalid operator "
                        f"'{rule['operator']}', expected one of: ==, !=, =~, ~="
                    )


def _parse_condition_block(cond_raw: dict) -> HookCondition:
    """Parse condition block, supporting both legacy and new group format."""
    # New format: all/any as a list of rules
    for mode_key in ("all", "any"):
        if mode_key in cond_raw and isinstance(cond_raw[mode_key], list):
            rules_raw = cond_raw[mode_key]
            rules = [
                ConditionRule(
                    field=r.get("field", ""),
                    operator=r.get("operator", "=="),
                    value=r.get("value", ""),
                )
                for r in rules_raw
                if isinstance(r, dict)
            ]
            # Check for sibling groups
            groups: list[ConditionGroup] = []
            for other_key in ("all", "any"):
                if other_key == mode_key:
                    continue
                if other_key in cond_raw and isinstance(cond_raw[other_key], list):
                    sub_rules = [
                        ConditionRule(
                            field=r.get("field", ""),
                            operator=r.get("operator", "=="),
                            value=r.get("value", ""),
                        )
                        for r in cond_raw[other_key]
                        if isinstance(r, dict)
                    ]
                    groups.append(ConditionGroup(mode=other_key, rules=sub_rules))

            return HookCondition(
                mode=mode_key,
                match={},
                group=ConditionGroup(mode=mode_key, rules=rules, groups=groups),
            )

    # Legacy format
    return HookCondition(
        mode=cond_raw.get("mode", "all"),
        match=cond_raw.get("match", {}),
    )


def _raw_to_hook(raw: dict) -> HookDefinition:
    action_raw = raw.get("action", {})
    condition = None
    if "if" in raw and raw["if"]:
        condition = _parse_condition_block(raw["if"])

    action = HookAction(
        type=action_raw.get("type", ""),
        command=action_raw.get("command"),
        cwd=action_raw.get("cwd"),
        env=action_raw.get("env"),
        content=action_raw.get("content"),
        position=action_raw.get("position", "next_iteration"),
        scope=action_raw.get("scope", "once"),
        url=action_raw.get("url"),
        method=action_raw.get("method", "POST"),
        headers=action_raw.get("headers"),
        body=action_raw.get("body"),
        prompt=action_raw.get("prompt"),
        model=action_raw.get("model"),
        tools=action_raw.get("tools"),
        max_iterations=action_raw.get("max_iterations", 5),
    )

    return HookDefinition(
        name=raw["name"],
        event=raw["event"],
        action=action,
        condition=condition,
        run_once=raw.get("run_once", False),
        background=raw.get("background", False),
        timeout=raw.get("timeout", 30.0),
    )


def _load_yaml_file(path: Path) -> tuple[list[dict], list[str]]:
    """Returns (raw_hooks, warnings)."""
    warnings: list[str] = []
    try:
        text = path.read_text(encoding="utf-8")
        data = yaml.safe_load(text) or {}
        if not isinstance(data, dict):
            return [], [f"{path}: YAML root must be a dict, got {type(data).__name__}"]
        hooks = data.get("hooks", [])
        if not isinstance(hooks, list):
            return [], [f"{path}: 'hooks' must be a list, got {type(hooks).__name__}"]
        return hooks, warnings
    except yaml.YAMLError as e:
        return [], [f"{path}: YAML parse error: {e}"]
    except OSError as e:
        return [], [f"{path}: read error: {e}"]


def load_hooks(project_root: str) -> list[HookDefinition]:
    project_path = Path(project_root)
    user_path = Path.home()

    project_file = project_path / ".opcode" / "hooks.yaml"
    user_file = user_path / ".opcode" / "hooks.yaml"

    # Collect warnings
    all_warnings: list[str] = []

    # Load with user first, then project overrides
    merged: dict[str, dict] = {}

    for fpath in (user_file, project_file):
        if not fpath.exists():
            continue
        raw_hooks, warnings = _load_yaml_file(fpath)
        all_warnings.extend(warnings)
        for raw in raw_hooks:
            if not isinstance(raw, dict):
                all_warnings.append(
                    f"{fpath}: skipping non-dict hook entry: {type(raw).__name__}"
                )
                continue
            name = raw.get("name", "")
            if name:
                merged[name] = raw
            else:
                all_warnings.append(f"{fpath}: skipping hook without name")

    # Validate and convert
    hooks: list[HookDefinition] = []
    for name, raw in merged.items():
        errors = validate_hook(raw)
        if errors:
            for err in errors:
                logger.warning(f"hook validation: {err}")
                all_warnings.append(err)
            continue
        try:
            hooks.append(_raw_to_hook(raw))
        except Exception as e:
            logger.warning(f"hook '{name}': conversion error: {e}")
            all_warnings.append(f"hook '{name}': conversion error: {e}")

    for warning in all_warnings:
        logger.info(f"hooks: {warning}")

    return hooks
