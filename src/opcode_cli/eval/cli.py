from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from opcode_cli.config import load_config
from opcode_cli.eval.artifacts import new_run_id
from opcode_cli.eval.report import aggregate, diff_tags, render_json, render_markdown
from opcode_cli.eval.runner import RunOptions, make_base_registry, run_task
from opcode_cli.eval.task import load_tasks
from opcode_cli.permission import PermissionMode
from opcode_cli.provider.manager import ProviderManager

_FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def add_eval_parser(subparsers) -> None:
    p = subparsers.add_parser("eval", help="run benchmark eval tasks")
    p.add_argument("--tasks", default=None, help=f"tasks dir (default: builtin fixtures)")
    p.add_argument("--task", action="append", dest="task_filter", default=[],
                   help="run only this task name (repeatable)")
    p.add_argument("--tag", default="default", help="tag for this run (default: default)")
    p.add_argument("--mode", default="permissive", choices=["strict", "default", "accept-edits", "permissive"],
                   help="permission mode (default: permissive)")
    p.add_argument("--max-iterations", type=int, default=25)
    p.add_argument("--memory", action="store_true", help="enable memory subsystem")
    p.add_argument("--checkpoint-interval", type=int, default=1)
    p.add_argument("--timeout", type=float, default=300.0, help="per-task timeout seconds")
    p.add_argument("--runs", default="runs", help="runs output dir (default: runs)")
    p.add_argument("--config", default=None, help="path to YAML config file")
    p.add_argument("-p", "--provider", default=None, help="provider name")
    p.add_argument("--verbose", action="store_true")
    p.set_defaults(func=cmd_eval)

    r = subparsers.add_parser("eval-report", help="aggregate eval run artifacts")
    r.add_argument("--runs", default="runs", help="runs dir to scan (default: runs)")
    r.add_argument("--tags", default=None, help="comma-separated tags to include")
    r.add_argument("--diff", nargs=2, metavar=("TAG_A", "TAG_B"), default=None,
                   help="diff two tags on shared tasks")
    r.add_argument("--format", default="md", choices=["json", "md"], help="output format")
    r.add_argument("-o", "--output", default=None, help="write to file instead of stdout")
    r.set_defaults(func=cmd_report)


def cmd_eval(args) -> int:
    tasks_dir = Path(args.tasks) if args.tasks else _FIXTURES_DIR
    tasks = load_tasks(tasks_dir)
    if args.task_filter:
        wanted = set(args.task_filter)
        tasks = [t for t in tasks if t.name in wanted]
    if not tasks:
        print(f"no eval tasks found in {tasks_dir}", file=sys.stderr)
        return 1

    try:
        config = load_config(args.config)
    except (FileNotFoundError, ValueError) as e:
        print(f"config error: {e}", file=sys.stderr)
        return 1
    try:
        manager = ProviderManager(config)
        provider = manager.get_provider(args.provider)
    except ValueError as e:
        print(f"provider error: {e}", file=sys.stderr)
        return 1

    registry = make_base_registry()
    failures = 0
    for task in tasks:
        opts = RunOptions(
            provider=provider,
            registry=registry,
            permission_mode=PermissionMode(args.mode),
            max_iterations=args.max_iterations,
            tag=args.tag,
            run_id=new_run_id(),
            runs_dir=Path(args.runs),
            enable_memory=args.memory,
            checkpoint_interval=args.checkpoint_interval,
            timeout_sec=args.timeout,
            verbose=args.verbose,
        )
        metrics = asyncio.run(run_task(task, opts))
        status = "OK" if metrics.success else "FAIL"
        if metrics.success is not True:
            failures += 1
        print(
            f"[eval] {task.name} ({task.scenario}): {status} "
            f"finish={metrics.finish_reason} iter={metrics.iterations} "
            f"dur={metrics.duration_sec:.1f}s → {opts.runs_dir / opts.run_id}"
        )
    return 1 if failures else 0


def cmd_report(args) -> int:
    tags = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else None
    report = aggregate(args.runs, tags)
    text = None
    extra = ""
    if args.diff:
        tag_a, tag_b = args.diff
        diffs = diff_tags(report, tag_a, tag_b)
        if args.format == "json":
            extra = "\n" + _render_diff_json(diffs)
        else:
            extra = "\n" + _render_diff_md(diffs)
    if args.format == "json":
        text = render_json(report) + extra
    else:
        text = render_markdown(report) + extra

    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    else:
        print(text)
    return 0


def _render_diff_json(diffs: list[dict]) -> str:
    import json
    return json.dumps({"diff": diffs}, ensure_ascii=False, indent=2)


def _render_diff_md(diffs: list[dict]) -> str:
    lines = ["", "## Diff", "", "| task | metric | a | b | diff |", "|------|--------|---|---|------|"]
    for d in diffs:
        lines.append(f"| {d['task']} | {d['metric']} | {d['a']} | {d['b']} | {d['diff']} |")
    return "\n".join(lines)
