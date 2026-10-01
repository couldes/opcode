# Opcode 重构实施计划

**状态**: 待执行  
**日期**: 2025-12-19  
**总工时**: 74-112 小时（约 9-14 工作日）

---

## 📋 执行概览

| Phase | 任务 | 预计工时 | 优先级 |
|-------|------|----------|--------|
| 1 | 清理和准备 | 10-16h | ⭐⭐⭐ |
| 2 | 架构重组 | 24-40h | ⭐⭐⭐ |
| 3 | 质量提升 | 16-24h | ⭐⭐ |
| 4 | 测试建设 | 16-24h | ⭐⭐⭐ |
| 5 | 文档完善 | 8h | ⭐ |

---

## Phase 1: 清理和准备 (10-16 小时)

### Task 1.1: 建立经验知识库 ✅ [已完成]

**目标**: 为团队创建代码库中记录开发教训和经验的地方

**步骤**:
```bash
mkdir -p experience
touch experience/.gitkeep
```

**产出**:
- `experience/01-initial-refactor-analysis.md` - 本次分析记录
- `experience/` 目录结构准备好供未来使用

**验收标准**:
- ✅ 目录存在
- ✅ 首份分析报告完成并说明问题、策略、教训

---

### Task 1.2: 识别并删除死代码

**目标**: 清理未使用的代码，减少代码膨胀

**步骤**:
1. **安装分析工具**
   ```bash
   pip install pylint==3.1.0 flake8==7.0.0
   ```

2. **静态分析**
   ```bash
   # 查找未使用的导入
   pylint src/opcode_cli --reports=n --unused-imports > unused_imports.txt
   
   # 查找 TODO/FIXME/XXX 标记
   grep -r "TODO\|FIXME\|XXX\|HACK" src/opcode_cli --include="*.py" > todos.txt
   
   # 查找长文件（>500 行）
   find src/opcode_cli -name "*.py" -exec wc -l {} + | sort -n -r | head -10
   ```

3. **审查 dead code**
   - 检查 `main.py` 中的导入是否都在使用
   - 检查 `docs/01-09` 中的重复历史文档（保留最近的演进记录）
   - 检查工具实现中是否有重复逻辑

4. **删除并验证**
   ```bash
   # 示例：删除未使用的导入
   git checkout HEAD~1 -- src/opcode_cli/main.py
   
   # 运行测试确保无破坏
   pytest tests/ -v --tb=short
   ```

**产出**:
- 清理后的代码库（预计减少 ~500 行死代码）
- `unused_imports.txt` 分析报告
- 精简的 `docs/` 目录（只保留必要文档）

**验收标准**:
- ✅ Pylint 报告无未使用导入警告
- ✅ 所有 `TODO` 标记有明确的状态（解决/拒绝/延后）
- ✅ 最长文件从 main.py (539 行) 降至 <500 行

---

### Task 1.3: 补充基础文档

**目标**: 确保开发者能够快速上手和理解项目

**步骤**:

1. **更新 README.md**
   ```markdown
   ## Opcode CLI AI Assistant
   
   A command-line AI coding agent with multi-provider LLM support, 
   permission control, MCP protocol extension, and context management.
   
   ### Core Features
   
   - **Multi-Provider LLM**: Anthropic, OpenAI, DeepSeek, Gemini
   - **Permission Control**: 9-layer decision chain with mode matrix
   - **Context Management**: Double-threshold compression (offload+summary)
   - **Team Collaboration**: Lead-member workflow with approval guards
   - **Tool Extension**: MCP protocol support for external tools
   
   ### Quick Start
   
   ```bash
   python -m pip install -e .
   opcode
   ```
   
   ### Architecture Overview
   
   ```
   src/opcode_cli/
     ├── core/              # Domain layer: Agent, Context, Permission...
     ├── application/       # Application layer: Commands, Hooks, Sessions...
     ├── infrastructure/    # Infrastructure layer: MCP, Providers, Tools...
     └── presentation/      # Presentation layer: TUI, CLI Entry Point
   ```
   
   ### Development
   
   ```bash
   # Run tests
   pytest tests/ -v
   
   # Type check
   mypy --strict src/opcode_cli/
   
   # Format code
   black src/opcode_cli tests/
   ```
   ```

2. **创建 ARCHITECTURE.md**
   ```markdown
   # Architecture Decision Records (ADRs)
   
   ## ADR-001: Modular Layered Architecture
   
   **Status**: Accepted  
   **Date**: 2025-12-19  
   **Context**: Need to improve code maintainability through clear layer separation.
   
   **Decision**: Adopt 6-layer architecture with strict dependency rules.
   
   ```
   Layers (top to bottom):
   - Presentation: User interface (TUI, CLI)
   - Application: Orchestration (Commands, Team, Hooks)
   - Core: Domain logic (Agent, Context, Permission)
   - Infrastructure: External dependencies (MCP, Providers, Tools)
   - Shared: Cross-cutting concerns (Config, Types, Utils)
   - Domain: Pure domain models (Events, Aggregates)
   ```
   
   **Dependency Rules**:
   - Dependencies only point downward
   - No cyclic dependencies allowed
   - Shared layer can be imported by any layer
   - Domain layer is completely independent
   
   **Consequences**:
   - ✅ Improved testability due to clear boundaries
   - ✅ Easier onboarding for new developers
   - ⚠️ More upfront design effort needed
   - ⚠️ Slight performance overhead from DI container
   
   ---
   
   ## ADR-002: Dependency Injection Strategy
   
   **Status**: Accepted  
   **Date**: 2025-12-19  
   **Context**: Current main.py has tight coupling between components.
   
   **Decision**: Implement lightweight DI container instead of full framework.
   
   **Benefits**:
   - Simplifies unit testing (mocking)
   - Reduces initialization complexity
   - Makes dependencies explicit
   
   **Implementation**:
   ```python
   class Container:
       def register(self, name: str, factory: Callable, singleton: bool = True)
       def resolve(self, name: str, **dependencies)
   ```
   ```

3. **更新 CONTRBUTING.md**
   - Python 版本要求（>=3.10）
   - 虚拟环境设置指南
   - 代码风格规范（black, isort）
   - 提交规范（conventional commits）

**产出**:
- ✅ 更新的 README.md
- ✅ ARCHITECTURE.md
- ✅ CONTRIBUTING.md

**验收标准**:
- ✅ README.md 清晰介绍核心功能
- ✅ ARCHITECTURE.md 解释分层原理
- ✅ 新开发者 1 天内可以跑通 Hello World

---

### Task 1.4: 生成依赖关系图

**目标**: 可视化当前模块间的依赖关系，识别循环依赖

**步骤**:

1. **安装工具**
   ```bash
   pip install pyan3 graphviz
   ```

2. **生成调用图**
   ```bash
   # 生成 DOT 格式
   pyan3 src/opcode_cli/*.py \
         src/opcode_cli/**/**/*.py \
         --no-paths \
         --dot \
         > call_graph.dot
   
   # 可选：渲染成 PNG
   dot -Tpng call_graph.dot -o call_graph.png
   ```

3. **分析循环依赖**
   ```python
   # 简单脚本检测循环
   import re
   
   with open('call_graph.dot') as f:
       content = f.read()
   
   # 提取节点和边
   nodes = re.findall(r'(\w+)', content)
   edges = re.findall(r'(\w+) -> (\w+)', content)
   
   # 构建图
   graph = {node: [] for node in set(nodes)}
   for src, dst in edges:
       if src in graph:
           graph[src].append(dst)
   
   # DFS 检测循环
   def find_cycle(node, visited, path):
       visited.add(node)
       path.append(node)
       
       for neighbor in graph.get(node, []):
           if neighbor not in visited:
               cycle = find_cycle(neighbor, visited, path)
               if cycle:
                   return cycle
           elif neighbor in path:
               return path[path.index(neighbor):]
       
       path.pop()
       return None
   
   # 遍历检测
   for start_node in graph:
       cycle = find_cycle(start_node, set(), [])
       if cycle:
           print(f"Cycle detected: {' -> '.join(cycle)}")
   ```

4. **修复发现的关系**
   - 如果是跨层调用，调整模块位置
   - 如果有隐式导入，添加显式接口

**产出**:
- ✅ `call_graph.dot` 依赖关系图
- ✅ 循环依赖分析报告
- ✅ 必要的模块位置调整

**验收标准**:
- ✅ 无循环依赖
- ✅ 每层之间的调用关系一目了然
- ✅ 关键路径（Agent → Provider → Tools）清晰可见

---

## Phase 2: 架构重组 (24-40 小时)

### Task 2.1: 创建新的目录结构

**目标**: 实现清晰的 6 层架构划分

**步骤**:

1. **创建目录**
   ```bash
   mkdir -p src/opcode_cli/{core,application,infrastructure,presentation,shared,domain}
   mkdir -p src/opcode_cli/core/{agent,context,memory,permission,prompt}
   mkdir -p src/opcode_cli/application/{commands,hooks,sessions,team}
   mkdir -p src/opcode_cli/infrastructure/{mcp,providers,tools,subagent}
   mkdir -p src/opcode_cli/presentation/{tui,cli}
   mkdir -p src/opcode_cli/shared/{config,types,utils,errors}
   mkdir -p src/opcode_cli/domain/{events,aggregates,value_objects}
   ```

2. **移动现有模块**
   ```bash
   # Core layer
   mv src/opcode_cli/agent/* src/opcode_cli/core/agent/
   mv src/opcode_cli/context/* src/opcode_cli/core/context/
   mv src/opcode_cli/memory/* src/opcode_cli/core/memory/
   mv src/opcode_cli/permission/* src/opcode_cli/core/permission/
   mv src/opcode_cli/prompt/* src/opcode_cli/core/prompt/
   
   # Application layer
   mv src/opcode_cli/commands/* src/opcode_cli/application/commands/
   mv src/opcode_cli/hooks/* src/opcode_cli/application/hooks/
   mv src/opcode_cli/session/* src/opcode_cli/application/sessions/
   mv src/opcode_cli/team/* src/opcode_cli/application/team/
   
   # Infrastructure layer
   mv src/opcode_cli/mcp/* src/opcode_cli/infrastructure/mcp/
   mv src/opcode_cli/provider/* src/opcode_cli/infrastructure/providers/
   mv src/opcode_cli/tools/* src/opcode_cli/infrastructure/tools/
   mv src/opcode_cli/subagent/* src/opcode_cli/infrastructure/subagent/
   
   # Presentation layer
   mv src/opcode_cli/tui/* src/opcode_cli/presentation/tui/
   ```

3. **创建空占位符**
   ```bash
   touch src/opcode_cli/{core,application,infrastructure,presentation}/{__init__.py}
   touch src/opcode_cli/shared/__init__.py
   touch src/opcode_cli/domain/__init__.py
   ```

4. **更新 __init__.py 文件**
   ```python
   # src/opcode_cli/core/__init__.py
   """Core domain logic layer"""
   
   from opcode_cli.core.agent.agent import Agent
   from opcode_cli.core.context.manager import ContextManager
   from opcode_cli.core.permission.checker import PermissionChecker
   
   __all__ = ['Agent', 'ContextManager', 'PermissionChecker']
   ```

**产出**:
- ✅ 完整的 6 层目录结构
- ✅ 每个层的 __init__.py 文件
- ✅ 正确的模块导入路径

**验收标准**:
- ✅ 所有源文件移动到正确位置
- ✅ 没有循环导入错误
- ✅ `import opcode_cli` 仍然可用

---

### Task 2.2: 重构 main.py 为新入口点

**目标**: 将庞大的 main.py 拆分为职责清晰的入口模块

**步骤**:

1. **创建 DI 容器**
   ```python
   # src/opcode_cli/shared/di/container.py
   from typing import Any, Callable, TypeVar, Dict
   from functools import wraps
   
   T = TypeVar('T')
   
   class Container:
       """轻量级依赖注入容器"""
       
       def __init__(self):
           self._services: Dict[str, tuple[Callable, bool]] = {}
           self._instances: Dict[str, Any] = {}
       
       def register(self, name: str, factory: Callable[..., T], singleton: bool = True) -> None:
           """注册服务"""
           self._services[name] = (factory, singleton)
       
       def resolve(self, name: str, **overrides) -> Any:
           """解析服务"""
           if name in overrides:
               return overrides[name]
           
           if name in self._instances:
               return self._instances[name]
           
           factory, _singleton = self._services[name]
           instance = factory()
           
           if _singleton:
               self._instances[name] = instance
           
           return instance
   
       def build_from_config(self, config) -> 'Container':
           """根据配置构建完整容器"""
           container = Container()
           
           # 配置层
           container.register('config', lambda: config)
           
           # Provider 层
           from opcode_cli.infrastructure.providers.manager import ProviderManager
           provider_mgr = ProviderManager(config)
           container.register(
               'provider',
               lambda pm: pm.get_provider('default'),
               singleton=True
           )
           
           # Registry 层
           from opcode_cli.infrastructure.tools.registry import ToolRegistry
           registry = ToolRegistry()
           # ... 注册工具
           container.register('registry', lambda: registry, singleton=True)
           
           # Permission Checker
           from opcode_cli.core.permission.checker import PermissionChecker
           perm_checker = PermissionChecker(
               project_root=config.project_root,
               mode=config.mode,
               registry=registry,
           )
           container.register('permission_checker', lambda: perm_checker, singleton=True)
           
           # Context Manager
           from opcode_cli.core.context.manager import ContextManager
           ctx_mgr = ContextManager(
               project_root=config.project_root,
               session_id=config.session_id,
               context_window=config.context_window or 128000,
           )
           container.register('context_manager', lambda: ctx_mgr, singleton=True)
           
           # Agent
           from opcode_cli.core.agent.agent import Agent
           container.register(
               'agent',
               lambda p, r, pm, cm: Agent(
                   provider=p,
                   registry=r,
                   permission_checker=pm,
                   context_manager=cm
               ),
               singleton=True
           )
           
           # Commands
           from opcode_cli.application.commands.registry import CommandRegistry
           container.register(
               'command_registry',
               lambda deps: CommandRegistry(deps),
               singleton=True
           )
           
           return container
   ```

2. **创建 CLI entry point**
   ```python
   # src/opcode_cli/presentation/cli/entry.py
   import sys
   import argparse
   import asyncio
   from pathlib import Path
   
   from opcode_cli.shared.config import load_app_config
   from opcode_cli.shared.di.container import Container
   from opcode_cli.presentation.tui.app import OpcodeApp
   from opcode_cli.infrastructure.tools.registry import ToolRegistry
   from opcode_cli.infrastructure.tools.file_ops import ReadFileTool, WriteFileTool, EditFileTool
   from opcode_cli.infrastructure.tools.search_tools import GlobFindTool, GrepSearchTool
   from opcode_cli.infrastructure.tools.command import RunCommandTool
   
   def create_application_container() -> Container:
       """创建应用容器并初始化所有组件"""
       config = load_app_config()
       
       container = Container()
       container.register('config', lambda: config)
       
       # 初始化工具注册表
       registry = ToolRegistry()
       registry.register(ReadFileTool())
       registry.register(WriteFileTool())
       registry.register(EditFileTool())
       registry.register(RunCommandTool())
       registry.register(GlobFindTool())
       registry.register(GrepSearchTool())
       container.register('registry', lambda: registry, singleton=True)
       
       # 后续继续注册其他组件
       # ... 参考上面 Container.build_from_config 方法
       
       return container
   
   def parse_args() -> argparse.Namespace:
       parser = argparse.ArgumentParser(description="Opcode - CLI AI Coding Agent")
       parser.add_argument("-c", "--config", help="Config file path")
       parser.add_argument("-p", "--provider", help="Provider name")
       parser.add_argument("--max-iterations", type=int, default=25)
       # ... 更多参数
       
       return parser.parse_args()
   
   async def run_member_mode(args):
       """队员模式：直接运行而非通过 TUI"""
       # 简化版成员模式逻辑
       pass
   
   def main():
       """主入口点"""
       args = parse_args()
       
       # 启动队员模式或 TUI
       if hasattr(args, 'team') and args.team and hasattr(args, 'member') and args.member:
           asyncio.run(run_member_mode(args))
       else:
           container = create_application_container()
           app = OpcodeApp(
               agent=container.resolve('agent'),
               command_registry=container.resolve('command_registry')
           )
           app.run()
   
   if __name__ == "__main__":
       main()
   ```

3. **更新 pyproject.toml**
   ```toml
   [project.scripts]
   opcode = "opcode_cli.presentation.cli.entry:main"
   ```

4. **测试入口点**
   ```bash
   opcode --help
   opcode -c ./opcode.yaml
   ```

**产出**:
- ✅ `src/opcode_cli/shared/di/container.py`
- ✅ `src/opcode_cli/presentation/cli/entry.py`
- ✅ 简化的初始化逻辑
- ✅ 清晰的依赖注册顺序

**验收标准**:
- ✅ `opcode --help` 正常工作
- ✅ 所有原有命令行参数支持
- ✅ 依赖注入正确工作

---

### Task 2.3: 整合工具系统

**目标**: 抽取重复的工具实现逻辑

**步骤**:

1. **创建抽象基类**
   ```python
   # src/opcode_cli/infrastructure/tools/base.py
   from abc import abstractmethod
   from pydantic import BaseModel
   from typing import Optional
   
   class ToolResult(BaseModel):
       success: bool
       content: str
       error: Optional[str] = None
   
   class BaseTool:
       """工具基类"""
       
       name: str = "base_tool"
       description: str = "Base tool description"
       
       @property
       @abstractmethod
       def is_read_only(self) -> bool:
           """是否为只读工具"""
           pass
       
       @property
       def params_model(self) -> Optional[type[BaseModel]]:
           """参数模型"""
           return None
       
       async def execute(self, params: BaseModel, working_dir: str = None) -> ToolResult:
           """执行工具"""
           pass
       
       def get_schema(self, fmt: str = "anthropic") -> dict:
           """获取工具 schema"""
           pass
   ```

2. **文件操作工具分组**
   ```python
   # src/opcode_cli/infrastructure/tools/file_ops.py
   from pathlib import Path
   from pydantic import Field
   from .base import BaseTool, ToolResult
   
   class FileOperationParams(BaseModel):
       path: str = Field(..., description="文件路径")
   
   class ReadFileParams(FileOperationParams):
       @property
       def is_read_only(self) -> bool:
           return True
   
   class WriteFileParams(FileOperationParams):
       content: str = Field(..., description="写入内容")
   
   class EditFileParams(FileOperationParams):
       old_content: str = Field(..., description="原始内容")
       new_content: str = Field(..., description="新内容")
   
   class BaseFileSystemTool(BaseTool):
       """文件系统操作基类"""
       
       permission_checker = None
       
       def set_permission_checker(self, checker) -> None:
           self.permission_checker = checker
       
       def validate_path(self, path: Path) -> bool:
           """验证路径权限"""
           if not self.permission_checker:
               return True
           return self.permission_checker.check(path)
   
   class ReadFileTool(BaseFileSystemTool):
       name = "read_file"
       description = "Read a file from the local filesystem"
       params_model = ReadFileParams
       
       @property
       def is_read_only(self) -> bool:
           return True
       
       async def execute(self, params: ReadFileParams, working_dir: str = None) -> ToolResult:
           path = Path(params.path)
           if not self.validate_path(path):
               return ToolResult(success=False, content="", error="Path not allowed")
           
           try:
               content = path.read_text()
               return ToolResult(success=True, content=content)
           except Exception as e:
               return ToolResult(success=False, content="", error=str(e))
   
   class WriteFileTool(BaseFileSystemTool):
       name = "write_file"
       description = "Write content to a file"
       params_model = WriteFileParams
       
       @property
       def is_read_only(self) -> bool:
           return False
       
       async def execute(self, params: WriteFileParams, working_dir: str = None) -> ToolResult:
           path = Path(params.path)
           if not self.validate_path(path):
               return ToolResult(success=False, content="", error="Path not allowed")
           
           try:
               path.write_text(params.content)
               return ToolResult(success=True, content=f"Successfully wrote to {params.path}")
           except Exception as e:
               return ToolResult(success=False, content="", error=str(e))
   
   class EditFileTool(BaseFileSystemTool):
       name = "edit_file"
       description = "Edit a file using search and replace"
       params_model = EditFileParams
       
       @property
       def is_read_only(self) -> bool:
           return False
       
       async def execute(self, params: EditFileParams, working_dir: str = None) -> ToolResult:
           # 统一的编辑逻辑
           pass
   ```

3. **搜索工具分组**
   ```python
   # src/opcode_cli/infrastructure/tools/search_tools.py
   from pathlib import Path
   from pydantic import Field
   from .base import BaseTool, ToolResult
   
   class SearchOptions(BaseModel):
       base_path: str = Field(..., description="搜索根路径")
       pattern: str = Field(..., description="匹配模式")
       max_results: int = Field(default=50, description="最大结果数")
   
   class SearchResults(BaseModel):
       total_found: int
       results: list[dict]
       search_time_ms: float
   
   class BaseSearchTool(BaseTool):
       """搜索工具基类"""
       params_model = SearchOptions
       
       @abstractmethod
       def execute_search(self, options: SearchOptions) -> SearchResults:
           pass
       
       async def execute(self, params: SearchOptions, working_dir: str = None) -> ToolResult:
           results = self.execute_search(params)
           return ToolResult(success=True, content=str(results))
   
   class GlobFindTool(BaseSearchTool):
       name = "glob_find"
       description = "Find files matching glob pattern"
       
       @property
       def is_read_only(self) -> bool:
           return True
       
       def execute_search(self, options: SearchOptions) -> SearchResults:
           # 实现 glob 搜索
           pass
   
   class GrepSearchTool(BaseSearchTool):
       name = "grep_search"
       description = "Search for text patterns in files"
       
       @property
       def is_read_only(self) -> bool:
           return True
       
       def execute_search(self, options: SearchOptions) -> SearchResults:
           # 实现 grep 搜索
           pass
   ```

4. **移除旧工具文件**
   ```bash
   rm src/opcode_cli/infrastructure/tools/read_file.py
   rm src/opcode_cli/infrastructure/tools/write_file.py
   rm src/opcode_cli/infrastructure/tools/edit_file.py
   rm src/opcode_cli/infrastructure/tools/glob_find.py
   rm src/opcode_cli/infrastructure/tools/grep_search.py
   rm src/opcode_cli/infrastructure/tools/run_command.py
   ```

**产出**:
- ✅ 统一的 `BaseTool` 基类
- ✅ `file_ops.py` 包含读写编辑工具
- ✅ `search_tools.py` 包含搜索工具
- ✅ 重复代码减少约 30%

**验收标准**:
- ✅ 所有原有工具功能正常
- ✅ 新增的参数验证通过 Pydantic 实现
- ✅ 类型注解更清晰

---

### Task 2.4: 整合记忆系统

**目标**: 统一分散的记忆存储逻辑

**步骤**:

```python
# src/opcode_cli/core/memory/store.py
from dataclasses import dataclass, asdict
from pathlib import Path
import json
from typing import Optional, List
from datetime import datetime

@dataclass
class MemoryEntry:
    id: str
    created_at: str
    content: str
    tags: List[str]
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'MemoryEntry':
        return cls(**data)


class MemoryStore:
    """统一记忆存储"""
    
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, MemoryEntry] = {}
    
    def save(self, entry: MemoryEntry) -> None:
        """保存记忆"""
        path = self.base_dir / f"{entry.id}.json"
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(entry.to_dict(), f, indent=2, ensure_ascii=False)
        
        self._cache[entry.id] = entry
    
    def get(self, id: str) -> Optional[MemoryEntry]:
        """获取记忆"""
        if id in self._cache:
            return self._cache[id]
        
        path = self.base_dir / f"{id}.json"
        if path.exists():
            with open(path, encoding='utf-8') as f:
                data = json.load(f)
            entry = MemoryEntry.from_dict(data)
            self._cache[id] = entry
            return entry
        return None
    
    def index(self) -> List[MemoryEntry]:
        """获取索引（所有记忆）"""
        return list(self._cache.values())
    
    def delete(self, id: str) -> bool:
        """删除记忆"""
        if id in self._cache:
            del self._cache[id]
        
        path = self.base_dir / f"{id}.json"
        if path.exists():
            path.unlink()
            return True
        return False
    
    def search(self, query: str, tags: List[str] = None) -> List[MemoryEntry]:
        """搜索记忆"""
        results = []
        query_lower = query.lower()
        
        for entry in self.index():
            # 文本匹配
            if query_lower in entry.content.lower():
                results.append(entry)
                continue
            
            # Tag 匹配
            if tags:
                if set(tags).issubset(set(entry.tags)):
                    results.append(entry)
        
        return results


class MemoryIndex:
    """记忆索引器"""
    
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self._index: dict[str, list[str]] = {}  # tag -> [memory_ids]
    
    def add_tag(self, memory_id: str, tag: str) -> None:
        """添加标签索引"""
        if tag not in self._index:
            self._index[tag] = []
        if memory_id not in self._index[tag]:
            self._index[tag].append(memory_id)
    
    def remove_tag(self, memory_id: str, tag: str) -> None:
        """移除标签索引"""
        if tag in self._index:
            if memory_id in self._index[tag]:
                self._index[tag].remove(memory_id)
    
    def get_by_tag(self, tag: str) -> List[str]:
        """根据标签获取记忆 ID 列表"""
        return self._index.get(tag, [])
    
    def list_all_tags(self) -> List[str]:
        """列出所有标签"""
        return list(self._index.keys())


class MemoryUpdater:
    """记忆更新管理器"""
    
    def __init__(
        self,
        project_memory_dir: Path,
        user_memory_dir: Path,
        store: MemoryStore,
        index: MemoryIndex,
    ):
        self.project_store = MemoryStore(project_memory_dir)
        self.user_store = MemoryStore(user_memory_dir)
        self.store = store
        self.index = index
    
    def merge_project_and_user(self) -> List[MemoryEntry]:
        """合并项目和用户记忆"""
        all_memories = set()
        
        # 项目记忆
        for entry in self.project_store.index():
            all_memories.add(entry.id)
        
        # 用户记忆
        for entry in self.user_store.index():
            all_memories.add(entry.id)
        
        return [self.store.get(mid) for mid in all_memories if self.store.get(mid)]
```

**产出**:
- ✅ 统一的 `MemoryStore` 类
- ✅ `MemoryIndex` 标签管理
- ✅ `MemoryUpdater` 合并逻辑

**验收标准**:
- ✅ 记忆保存和加载功能正常
- ✅ 标签索引机制工作
- ✅ 项目/用户记忆可以合并

---

### Task 2.5: 精简 UI 层

**目标**: 保持 Widget 层次但优化内部实现

**步骤**:

1. **保持整体结构不变**
   - VerticalScroll(chat)
   - StatusBar
   - ChatInput

2. **拆分复杂组件**
   ```python
   # src/opcode_cli/presentation/tui/widgets/user_message.py
   from textual.widgets import Static
   from textual.css.query import NoWidgetMatches
   
   class UserMsgNode(Static):
       """用户消息显示组件"""
       
       CSS = """
       UserMsgNode {
           width: 100%;
           height: auto;
           padding: 1;
       }
       """
       
       def __init__(self, message: str):
           super().__init__(message)
           self.mount(Static(message, classes="user-message"))
   ```

   ```python
   # src/opcode_cli/presentation/tui/widgets/notification.py
   from textual.widgets import Static
   
   class NotificationNode(Static):
       """通知消息组件"""
       
       CSS = """
       NotificationNode {
           width: 100%;
           height: auto;
           border-left: thick $accent;
           padding: 1 2;
       }
       """
   ```

3. **简化 App 初始化逻辑**
   ```python
   # src/opcode_cli/presentation/tui/app.py
   from textual.app import App, ComposeResult
   from textual.containers import VerticalScroll
   from opcode_cli.core.events import AgentEvent
   
   class OpcodeApp(App):
       AUTO_FOCUS = "#user-input"
       CSS_PATH = "styles.tcss"
   
       def compose(self) -> ComposeResult:
           yield VerticalScroll(id="chat")
           yield StatusBar()
           yield OpcodeChatInput(id="user-input")
   
       async def on_mount(self) -> None:
           """仅处理焦点和事件监听"""
           self.call_after_refresh(self._focus_input)
           asyncio.create_task(self._listen_agent_events())
   
       async def _listen_agent_events(self):
           """统一的事件监听器"""
           async for event in self.agent.run("start"):
               await self.event_queue.put(event)
   
       async def process_event(self, event: AgentEvent):
           """统一的事件处理器"""
           if isinstance(event, ToolExecuteEvent):
               # 处理工具执行
               pass
           elif isinstance(event, AssistantResponseEvent):
               # 处理助手回复
               pass
           # ... 其他事件类型
   ```

**产出**:
- ✅ 清晰的 Widget 层次
- ✅ 简化的 App 初始化
- ✅ 统一的事件处理机制

**验收标准**:
- ✅ TUI 界面与之前一致
- ✅ Plan mode UX 良好
- ✅ 响应速度无明显下降

---

## Phase 3: 质量提升 (16-24 小时)

### Task 3.1: 类型注解全覆盖

**目标**: 所有公共 API 添加完整类型提示

**步骤**:

1. **安装工具**
   ```bash
   pip install mypy==1.8.0 pydantic==2.5.0
   ```

2. **配置 mypy**
   ```toml
   # pyproject.toml
   [tool.mypy]
   python_version = "3.10"
   warn_return_any = true
   warn_unused_ignores = true
   follow_imports = "normal"
   strict_optional = true
   disallow_untyped_defs = true
   ignore_missing_imports = true
   
   [[tool.mypy.overrides]]
   module = "tests.*"
   disallow_untyped_defs = false
   ```

3. **逐个模块添加注解**
   ```python
   # 示例：Type annotation improvement
   from typing import Any, Dict, List, Optional, Protocol, TypeVar
   
   T = TypeVar('T')
   
   class Result(Protocol[T]):
       @property
       def value(self) -> T: ...
       
       @property
       def is_success(self) -> bool: ...
   
   class CommandHandler:
       """命令处理器基类"""
       
       def handle(self, command: str, context: CommandContext) -> Result[str]:
           """处理命令"""
           pass
   
   def parse_command(text: str) -> Optional[ParsedCommand]:
       """解析命令"""
       pass
   
   def execute_command(
       command: ParsedCommand,
       context: CommandContext
   ) -> ToolCall | None:
       """执行命令"""
       pass
   ```

4. **运行类型检查**
   ```bash
   # 严格检查核心模块
   mypy --strict src/opcode_cli/core/
   
   # 检查应用层
   mypy --strict src/opcode_cli/application/
   
   # 修复发现的问题
   ```

**产出**:
- ✅ 所有公共 API 有类型注解
- ✅ `mypy --strict` 零错误
- ✅ IDE 智能提示完全启用

**验收标准**:
- ✅ `mypy src/opcode_cli/` 返回 0
- ✅ No `# type: ignore` comments needed (except third-party libs)

---

### Task 3.2: 统一错误处理

**目标**: 定义标准化的异常体系和错误码

**步骤**:

```python
# src/opcode_cli/shared/errors.py
from enum import Enum
from dataclasses import dataclass
from typing import Any, Optional


class ErrorCode(Enum):
    """全局错误码"""
    
    # Permission errors
    PERMISSION_DENIED = "PERM_001"
    PATH_OUTSIDE_SANDBOX = "PERM_002"
    
    # Tool execution errors
    TOOL_EXECUTION_FAILED = "TOOL_001"
    TOOL_TIMEOUT = "TOOL_002"
    TOOL_VALIDATION_ERROR = "TOOL_003"
    
    # Configuration errors
    CONFIG_ERROR = "CFG_001"
    PROVIDER_NOT_FOUND = "CFG_002"
    
    # Context errors
    CONTEXT_OVERFLOW = "CTX_001"
    COMPRESSION_FAILED = "CTX_002"
    
    # General errors
    INVALID_PARAMETER = "INV_001"
    INTERNAL_ERROR = "INT_001"


@dataclass(frozen=True)
class OpcodeError(Exception):
    """基础错误类"""
    code: ErrorCode
    message: str
    details: Optional[Dict[str, Any]] = None
    
    def __str__(self) -> str:
        if self.details:
            return f"[{self.code.value}] {self.message}: {self.details}"
        return f"[{self.code.value}] {self.message}"


class PermissionError(OpcodeError):
    """权限错误"""
    def __init__(self, message: str, resource: str, rule: Optional[str] = None):
        super().__init__(
            code=ErrorCode.PERMISSION_DENIED,
            message=message,
            details={"resource": resource, "rule": rule}
        )


class ToolExecutionError(OpcodeError):
    """工具执行错误"""
    def __init__(self, tool_name: str, original_error: Exception):
        super().__init__(
            code=ErrorCode.TOOL_EXECUTION_FAILED,
            message=f"Tool '{tool_name}' execution failed",
            details={"original_error": str(original_error)}
        )


class ContextCompressionError(OpcodeError):
    """上下文压缩错误"""
    def __init__(self, reason: str):
        super().__init__(
            code=ErrorCode.COMPRESSION_FAILED,
            message="Context compression failed",
            details={"reason": reason}
        )


def handle_opcodes_error(error: OpcodeError, log) -> None:
    """结构化错误日志"""
    log.error(
        "opcode_error",
        code=error.code.value,
        message=error.message,
        details=error.details,
        exc_info=True,
    )


def format_error_for_api(error: OpcodeError) -> dict:
    """格式化 API 响应"""
    return {
        "error_code": error.code.value,
        "message": error.message,
        "details": error.details,
    }
```

**产出**:
- ✅ 统一的异常层次结构
- ✅ 错误码枚举
- ✅ 错误日志格式化函数

**验收标准**:
- ✅ 所有错误都继承自 `OpcodeError`
- ✅ 错误信息包含错误码和详情
- ✅ 结构化日志输出

---

### Task 3.3: 日志标准化

**目标**: 引入结构化日志系统

**步骤**:

1. **安装工具**
   ```bash
   pip install structlog==24.1.0
   ```

2. **配置日志**
   ```python
   # src/opcode_cli/shared/utils/logger.py
   import logging
   import structlog
   from pathlib import Path
   
   def setup_logger(name: str, log_file: Path) -> None:
       """设置结构化日志"""
       
       # JSON file handler
       file_handler = logging.FileHandler(log_file)
       file_handler.setLevel(logging.INFO)
       
       # Console handler
       console_handler = logging.StreamHandler()
       console_handler.setLevel(logging.INFO)
       
       # Configure structlog
       structlog.configure(
           processors=[
               structlog.stdlib.filter_by_level,
               structlog.stdlib.add_logger_name,
               structlog.stdlib.add_log_level,
               structlog.processors.TimeStamper(fmt="iso"),
               structlog.dev.set_exc_info,
               structlog.processors.JSONRenderer(),
           ],
           wrapper_class=structlog.stdlib.BoundLogger,
           context_class=dict,
           logger_factory=structlog.stdlib.LoggerFactory(),
           cache_logger_on_first_use=True,
       )
   
   def get_logger(name: str) -> structlog.stdlib.BoundLogger:
       """获取日志实例"""
       return structlog.get_logger(name)
   
   # Usage example
   log = get_logger(__name__)
   log.info(
       "tool_executed",
       tool_name="read_file",
       duration_ms=150,
       success=True,
       file_size=2048,
   )
   ```

**产出**:
- ✅ Structured logging 配置
- ✅ JSON 格式日志文件
- ✅ 时间戳和异常追踪

**验收标准**:
- ✅ 日志包含结构化字段
- ✅ JSON 格式可读性好
- ✅ 异常堆栈完整记录

---

### Task 3.4: 性能分析和优化

**目标**: 找出性能瓶颈并优化

**步骤**:

1. **安装 profilers**
   ```bash
   pip install py-spy==0.3.14 line_profiler==4.0.3
   ```

2. **CPU Profiling**
   ```bash
   # Record profile
   py-spy record -o profile.svg -- python -m opcode_cli --help
   
   # Analyze hot paths
   pip install flamegraph
   sudo flamegraph-profile-to-svg profile.svg > flamegraph.html
   ```

3. **Line-by-line profiling**
   ```python
   # Add decorator to functions
   from line_profiler import LineProfiler
   
   @profile
   def critical_path_function(messages: list[Message]) -> str:
       """Hot path function"""
       # Your code here
       pass
   ```

4. **优化建议**
   - 缓存频繁的配置查询
   - 异步 I/O 操作
   - 批量处理工具调用

**产出**:
- ✅ Profile 报告
- ✅ 性能优化建议
- ✅ Hot path 改进

**验收标准**:
- ✅ 主要操作延迟减少 20%
- ✅ 内存占用无明显增长

---

## Phase 4: 测试体系建设 (16-24 小时)

### Task 4.1: 创建测试目录结构

```bash
mkdir -p tests/unit/core
mkdir -p tests/unit/application  
mkdir -p tests/unit/infrastructure
mkdir -p tests/integration
mkdir -p tests/e2e
```

### Task 4.2: 编写核心单元测试

```python
# tests/unit/core/test_context_manager.py
import pytest
from opcode_cli.core.context.manager import ContextManager
from opcode_cli.provider.base import Message


@pytest.mark.asyncio
async def test_context_manager_initialization():
    """测试 ContextManager 初始化"""
    mgr = ContextManager(
        project_root="/tmp",
        session_id="test_session",
        context_window=128000,
    )
    
    assert mgr.estimator is not None
    assert mgr.circuit_breaker is not None


@pytest.mark.asyncio
async def test_soft_threshold_compression(mocker):
    """测试软阈值触发压缩"""
    mocker.patch.object(ContextManager, '_do_compress', return_value=None)
    
    mgr = ContextManager("/tmp", "test", 1000)
    
    messages = [Message(role="user", content="x" * 10000)]
    
    await mgr.before_request(messages)
    
    # 验证压缩被调用
    ...


@pytest.mark.asyncio
async def test_hard_threshold_force_compression(mocker):
    """测试硬阈值强制压缩"""
    mocker.patch.object(ContextManager, '_do_compress', return_value=None)
    
    mgr = ContextManager("/tmp", "test", 1000)
    
    messages = [Message(role="user", content="y" * 100000)]
    
    await mgr.before_request(messages)
    
    # 硬阈值应该绕过熔断器
    ...
```

### Task 4.3: 编写集成测试

```python
# tests/integration/test_agent_workflow.py
import pytest
from opcode_cli.core.agent.agent import Agent
from opcode_cli.infrastructure.tools.registry import ToolRegistry
from opcode_cli.infrastructure.tools.file_ops import ReadFileTool


@pytest.mark.asyncio
async def test_agent_read_write_cycle(tmp_path):
    """测试读写文件流程"""
    test_file = tmp_path / "test.txt"
    test_file.write_text("hello world")
    
    registry = ToolRegistry()
    registry.register(ReadFileTool())
    
    agent = Agent(registry=registry)
    
    result = await agent.run(f"read {test_file}")
    
    assert "hello world" in result.content


@pytest.mark.asyncio
async def test_permission_check_chain():
    """测试权限检查链"""
    from opcode_cli.core.permission.checker import PermissionChecker
    
    checker = PermissionChecker(
        project_root="/tmp",
        mode="strict",
    )
    
    # Test layer 0: plan mode
    # ...
    
    # Test layer 1b: dangerous command
    # ...
    
    # Test layer 2: path sandbox
    # ...
```

### Task 4.4: 配置覆盖率

```toml
# pyproject.toml
[tool.coverage.run]
source = ["src/opcode_cli"]
branch = true
omit = [
    "*/tests/*",
    "*/__pycache__/*",
]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise AssertionError",
    "raise NotImplementedError",
    "if TYPE_CHECKING:",
]
fail_under = 80
show_missing = true
```

**验收标准**:
- ✅ 核心模块覆盖率 > 80%
- ✅ 所有断言都有测试覆盖
- ✅ CI/CD 自动运行测试

---

## Phase 5: 文档完善 (8 小时)

### Task 5.1: 编写 ADR 文档

```markdown
docs/adr/
├── 001-modular-layered-architecture.md
├── 002-dependency-injection-pattern.md
├── 003-unified-tool-interface.md
├── 004-error-handling-strategy.md
├── 005-structured-logging.md
└── 006-testing-pyramid.md
```

### Task 5.2: 生成 API 文档

```bash
pip install pdoc
pdoc src/opcode_cli --output-dir docs/api
```

**验收标准**:
- ✅ ADR 文档完整（至少 5 个决策）
- ✅ API 文档自动生成
- ✅ 开发者快速上手

---

## 总结

这个实施计划基于以下原则：

1. **保留优秀的既有设计**：ContextManager、PermissionChecker、TUI 保持架构不变
2. **渐进式迁移**：分 5 个阶段逐步推进
3. **向后兼容**：用户感知最小化
4. **质量优先**：类型注解、测试覆盖、文档完善

完成后将达到：
- ✅ 清晰的 6 层架构
- ✅ 完整的类型注解
- ✅ >80% 测试覆盖率
- ✅ 良好的可维护性

**总计工时**：74-112 小时（约 9-14 工作日）

---

**状态**: 待执行  
**下一步**: 按 Phase 顺序依次完成任务
