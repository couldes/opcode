from __future__ import annotations

import sys
from pathlib import Path

import yaml

from opcode_cli.permission.rules import RuleSet, parse_rule_spec


def load_rule_file(path: Path) -> RuleSet | None:
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception as e:
        print(f"warning: failed to parse rules file '{path}': {e}", file=sys.stderr)
        return None

    if not data or not isinstance(data, dict):
        return None

    rules = data.get("rules")
    if not rules or not isinstance(rules, list):
        return None

    rs = RuleSet()
    for entry in rules:
        if not isinstance(entry, dict):
            continue
        for action in ("allow", "deny"):
            spec = entry.get(action)
            if spec:
                try:
                    rs.add(parse_rule_spec(spec, action))
                except ValueError as e:
                    print(
                        f"warning: skipping invalid rule '{spec}' in '{path}': {e}",
                        file=sys.stderr,
                    )
    return rs


def resolve_rule_paths(project_root: str) -> tuple[Path, Path]:
    project_rules = Path(project_root) / ".opcode" / "rules.yaml"
    user_rules = Path.home() / ".opcode" / "rules.yaml"
    return project_rules, user_rules


def merge_rulesets(*layers: RuleSet) -> RuleSet:
    merged = RuleSet()
    for layer in layers:
        for rule in layer._rules:
            merged.add(rule)
    return merged
