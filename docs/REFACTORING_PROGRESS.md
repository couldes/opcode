# 重构进度报告

**阶段**: 第一轮可维护性重构收敛

## 已完成

- 将 `main.py` 精简为兼容性入口；实际装配移至 `presentation/cli/entry.py`。
- 增加轻量级 DI 容器，支持单例、构造函数注入、缺失依赖和循环依赖检测。
- 抽取 `tools/file_ops.py` 和 `tools/search_tools.py`，消除文件/搜索工具的重复路径逻辑。
- 保留旧工具模块名作为兼容导出，避免影响 Agent、eval 和外部调用方。
- 增加 CLI 装配、工具整合和 DI 容器回归测试。
- 保留并记录 Pi 风格的上下文压缩、权限决策和 Textual TUI 机制。
- 删除未接入运行时的重复迁移副本，避免维护两套实现。

## 当前验证结果

```text
557 passed, 1 skipped
```

验证命令：

```bash
python -m pytest tests/ -q --tb=short
python -m opcode_cli.main --help
```

## 明确未做的工作

本轮没有强行移动所有业务包，也没有重写 ContextManager、PermissionChecker 或 TUI。它们已经是稳定且有测试覆盖的核心机制；继续迁移需要单独按模块进行兼容导出和回归验证。

长期计划仍在 `refactoring_plan.md`，其中的目录重组、类型检查、覆盖率提升和 ADR 建设属于后续工作，不代表已经完成。
