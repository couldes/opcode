# Opcode 项目重构设计文档

**状态**: 待审核  
**日期**: 2025-12-19  
**作者**: Qoder (AI Coding Assistant)  
**相关技能**: brainstorming → writing-plans → implementation

---

## 1. 概述

### 1.1 目标

对 opcode CLI AI 编程助手进行系统性重构，提升代码可维护性、架构清晰度和工程实践质量。

### 1.2 范围

- ✅ **包含**: 核心逻辑层、应用层、基础设施层、表现层的完整重组
- ✅ **包含**: 工具系统整合、依赖注入框架引入、测试体系建立
- ❌ **排除**: 用户界面交互细节（保持 Textual TUI 结构）
- ❌ **排除**: MCP 协议适配器的内部实现细节

### 1.3 成功标准

| 标准 | 指标 |
|------|------|
| 架构清晰度 | 任意两层之间的调用关系一目了然，无循环依赖 |
| 代码减量 | 减少 20-30% 冗余代码（从 17,512 行降至约 12,000-14,000 行） |
| 测试覆盖 | 核心模块单元测试覆盖率 > 80% |
| 文档完整 | 新手 1 天可以开始贡献代码 |
| 性能不降 | 执行速度不低于原版本 |
| 向后兼容 | API 接口保持不变，用户无感知 |

---

## 2. 当前问题分析

### 2.1 架构混乱

**问题描述**: `main.py` 文件承担了过多责任，存在隐式依赖循环。

**证据**:
```python
# main.py (539 行) - 导入列表
from opcode_cli.agent.agent import Agent           # Agent 循环
from opcode_cli.subagent.repo import RoleRepository  # 子 Agent
from opcode_cli.commands.context import CommandContext  # 命令上下文
from opcode_cli.context import ContextManager      # 上下文管理
from opcode_cli.permission import PermissionChecker  # 权限检查
from opcode_cli.mcp import MCPServerManager        # MCP 适配
from opcode_cli.skills import SkillRegistry        # 技能系统
from opcode_cli.team.manager import TeamManager    # 团队协作
from opcode_cli.tui.app import OpcodeApp          # UI 层
```

**影响**: 
- 难以定位具体功能的责任归属
- 修改一处可能引发不可预知的副作用
- 单元测试几乎无法编写

### 2.2 代码冗余

**问题描述**: 多个工具和 Handler 之间存在重复逻辑。

**发现的模式**:
1. **文件操作类工具**: `ReadFileTool`, `WriteFileTool`, `EditFileTool` 都实现了相似的 `is_read_only` 判断和参数验证逻辑
2. **搜索类工具**: `GlobFindTool`, `GrepSearchTool` 共享了路径查找和结果过滤逻辑
3. **Handler 模式**: 每个命令在 `commands/handlers/` 下都有独立处理器，但部分逻辑与工具重复

**影响**: 
- 维护成本高，同一 bug 需要多处修复
- 代码膨胀，增加理解负担

### 2.3 文档缺失

**问题描述**: 缺乏经验知识库和架构决策记录。

**现状**:
- ❌ `experience/` 目录不存在（项目说明中要求记录开发教训）
- ❌ ADR (Architecture Decision Records) 未建立
- ⚠️ README.md 内容陈旧，未反映最新架构
- ⚠️ 类型注解覆盖率低（估计 < 30%）

**影响**: 
- 新人上手困难
- 历史决策原因不明确
- 技术债务累积

### 2.4 测试不足

**问题描述**: tests/ 目录存在但未明确测试策略。

**现状**:
- ❌ 缺少完整的单元测试套件
- ❌ 集成测试可能缺失
- ❌ E2E 测试策略不明

**影响**: 
- 重构风险高
- 回归 bug 难捕获

### 2.5 Pi 最佳实践未采用

**缺失的关键机制**:
- ❌ 分层架构设计 (DDD 原则)
- ❌ 依赖注入模式
- ❌ 单向数据流
- ❌ 结构化日志

---

## 3. 目标架构设计

### 3.1 分层架构蓝图

```
┌─────────────────────────────────────────────────────┐
│                PRESENTATION LAYER                   │
│  ┌───────────────────────┐   ┌───────────────────┐  │
│  │       TUI             │   │       CLI         │  │
│  │  ┌─────────────────┐  │   │    entry.py       │  │
│  │  │ OpcodeApp       │  │   │  (新入口点)       │  │
│  │  └─────────────────┘  │   └───────────────────┘  │
│  └───────────────────────┘                          │
├─────────────────────────────────────────────────────┤
│               APPLICATION LAYER                     │
│  ┌───────────────────────┐   ┌───────────────────┐  │
│  │     COMMANDS          │   │    TEAM SYSTEM    │  │
│  │  ┌─────────────────┐  │   │   coordinator     │  │
│  │  │ handlers/       │  │   │   task_board      │  │
│  │  │ registry.py     │  │   │   mailbox         │  │
│  │  └─────────────────┘  │   └───────────────────┘  │
│  └───────────────────────┘                          │
│  ┌───────────────────────┐   ┌───────────────────┐  │
│  │      HOOKS            │   │    SESSIONS       │  │
│  │   hook_runner.py      │   │   archiver.py     │  │
│  └───────────────────────┘   └───────────────────┘  │
├─────────────────────────────────────────────────────┤
│                 CORE LAYER                          │
│  ┌───────────────────────┐   ┌───────────────────┐  │
│  │    AGENT              │   │    CONTEXT        │  │
│  │  agent.py             │   │  context_manager  │  │
│  │  batcher.py           │   │  offload_manager  │  │
│  │  events.py            │   │  summary_generator│  │
│  └───────────────────────┘   └───────────────────┘  │
│  ┌───────────────────────┐   ┌───────────────────┐  │
│  │   PERMISSION          │   │    PROMPT         │  │
│  │ permission_checker    │   │ system_prompt_bld │  │
│  │ mode_matrix.py        │   │ fixed_modules.py  │  │
│  └───────────────────────┘   └───────────────────┘  │
│  ┌───────────────────────┐   ┌───────────────────┐  │
│  │      MEMORY           │   │    SKILLS         │  │
│  │  memory_store.py      │   │ skill_registry    │  │
│  │ memory_index.py       │   │ skills_loader     │  │
│  └───────────────────────┘   └───────────────────┘  │
├─────────────────────────────────────────────────────┤
│             INFRASTRUCTURE LAYER                    │
│  ┌───────────────────────┐   ┌───────────────────┐  │
│  │      MCP              │   │   PROVIDERS       │  │
│  │  server_manager.py    │   │  base_provider.py │  │
│  │  tool_adapter.py      │   │  anthropic.py     │  │
│  └───────────────────────┘   │  openai.py        │  │
│                              └───────────────────┘  │
│  ┌───────────────────────┐   ┌───────────────────┐  │
│  │      TOOLS            │   │   SUBAGENT        │  │
│  │  base_tool.py         │   │  runner.py        │  │
│  │  registry.py          │   │  filter.py        │  │
│  │  file_ops.py          │   │  task_manager.py  │  │
│  │  search_tools.py      │   └───────────────────┘  │
│  └───────────────────────┘                          │
├─────────────────────────────────────────────────────┤
│                  SHARED LAYER                       │
│  ┌───────────────────────┐   ┌───────────────────┐  │
│  │    CONFIG             │   │    TYPES          │  │
│  │  config_loader.py     │   │ domain_models.py  │  │
│  │  di_container.py      │   │ value_objects.py  │  │
│  └───────────────────────┘   └───────────────────┘  │
│  ┌───────────────────────┐   ┌───────────────────┐  │
│  │    UTILS              │   │    ERRORS         │  │
│  │  path_utils.py        │   │ exception_hier.py │  │
│  │  async_utils.py       │   │ error_codes.py    │  │
│  └───────────────────────┘   └───────────────────┘  │
├─────────────────────────────────────────────────────┤
│                  DOMAIN LAYER                       │
│  ┌───────────────────────┐   ┌───────────────────┐  │
│  │    EVENTS             │   │   AGGREGATES      │  │
│  │  agent_events.py      │   │ session_agg.py    │  │
│  │  tool_events.py       │   │ user_agg.py       │  │
│  └───────────────────────┘   └───────────────────┘  │
└─────────────────────────────────────────────────────┘
```

### 3.2 依赖关系规则

1. **单向依赖**: Presentation → Application → Core → Infrastructure
2. **禁止跨层**: Shared 层可被任何层依赖，Domain 层完全独立
3. **接口隔离**: 每层通过 Protocol 定义清晰的边界

### 3.3 依赖注入框架设计

#### 设计理由
- 解耦对象创建和使用
- 便于测试（Mock 替换）
- 支持运行时配置

#### 简单 DI 容器实现

```python
# shared/di/container.py
from typing import Any, Callable, Type, TypeVar
from dataclasses import field

T = TypeVar('T')

class Container:
    """轻量级依赖注入容器"""
    
    def __init__(self):
        self._services: dict[str, tuple[Type, bool]] = {}  # name -> (type, singleton)
        self._instances: dict[str, Any] = {}
    
    def register(self, name: str, factory: Callable[..., T], singleton: bool = True) -> None:
        """注册服务"""
        self._services[name] = (factory, singleton)
    
    def resolve(self, name: str, **dependencies) -> Any:
        """解析服务"""
        if name in self._instances:
            return self._instances[name]
        
        factory, _singleton = self._services[name]
        instance = factory(**dependencies)
        
        if _singleton:
            self._instances[name] = instance
        
        return instance
    
    def build_from_config(self, config: AppConfig) -> 'Container':
        """根据配置构建完整容器"""
        container = Container()
        
        # Provider 层
        provider_mgr = ProviderManager(config)
        container.register('provider', lambda: provider_mgr.get_provider('default'))
        
        # Agent 层
        container.register(
            'agent',
            lambda provider, registry, ctx_mgr: Agent(
                provider=provider,
                registry=registry,
                context_manager=ctx_mgr
            ),
            singleton=True
        )
        
        # 命令系统层
        container.register(
            'command_registry',
            lambda deps: CommandRegistry(deps)
        )
        
        return container
```

### 3.4 工具系统优化

#### 合并重复实现

**文件操作组**:
```python
# infrastructure/tools/file_ops.py
from pydantic import BaseModel, Field
from pathlib import Path
from abc import abstractmethod
from typing import Optional

class FileOperationParams(BaseModel):
    path: str = Field(..., description="文件路径")
    
    @property
    def is_read_only(self) -> bool:
        return False

class ReadFileParams(FileOperationParams):
    @property
    def is_read_only(self) -> bool:
        return True

class WriteFileParams(FileOperationParams):
    content: str = Field(..., description="写入内容")

class EditFileParams(FileOperationParams):
    old_content: str = Field(..., description="原始内容")
    new_content: str = Field(..., description="新内容")

class FileSystemBaseTool(Tool):
    """文件操作基类"""
    
    def __init__(self, params_model: type[BaseModel]):
        super().__init__()
        self.params_model = params_model
        self.permission_checker: Optional[PermissionChecker] = None
    
    def set_permission_checker(self, checker: PermissionChecker) -> None:
        self.permission_checker = checker
    
    def validate_path(self, path: Path) -> bool:
        if not self.permission_checker:
            return True
        return self.permission_checker.check(path)
```

**搜索工具组**:
```python
# infrastructure/tools/search_tools.py
class SearchOptions(BaseModel):
    base_path: str = Field(..., description="搜索根路径")
    pattern: str = Field(..., description="匹配模式")
    max_results: int = Field(default=50, description="最大结果数")

class SearchResults(BaseModel):
    total_found: int
    results: list[dict[str, Any]]
    search_time_ms: float

class BaseSearchTool(Tool):
    """搜索工具基类"""
    
    params_model = SearchOptions
    
    @abstractmethod
    def execute_search(self, options: SearchOptions) -> SearchResults:
        pass
```

#### 简化的注册表

```python
# infrastructure/tools/registry.py
class ToolRegistry:
    """简化版工具注册表，移除复杂的 defer/discover 逻辑"""
    
    def __init__(self, timeout: float = 30.0):
        self._tools: dict[str, Tool] = {}
        self._timeout = timeout
    
    def register(self, tool: Tool) -> None:
        """注册工具"""
        if tool.name in self._tools:
            raise ValueError(f"tool already registered: {tool.name}")
        self._tools[tool.name] = tool
    
    def list_tools(self) -> list[Tool]:
        """列出所有工具"""
        return list(self._tools.values())
    
    def to_anthropic_format(self) -> list[dict]:
        """转换为 Anthropic schema"""
        return [t.get_schema(fmt="anthropic") for t in self._tools.values()]
    
    def to_openai_format(self) -> list[dict]:
        """转换为 OpenAI schema"""
        return [t.get_schema(fmt="openai") for t in self._tools.values()]
    
    async def execute(self, name: str, **kwargs) -> ToolResult:
        """统一执行器"""
        tool = self._tools[name]
        params = tool.params_model(**kwargs) if tool.params_model else kwargs
        
        try:
            result = await asyncio.wait_for(
                tool.execute(params),
                timeout=self._timeout
            )
            return result
        except Exception as e:
            return ToolResult(success=False, content="", error=str(e))
```

---

## 4. 详细实施计划

### 4.1 阶段一：清理和准备 (预计 1-2 天)

#### 任务清单

**T1.1: 建立经验知识库**
```bash
mkdir -p experience
touch experience/.gitkeep
```

**T1.2: 分析并删除死代码**
```bash
# 使用 tools 找出未使用的导入和变量
pylint src/opcode_cli --reports=n
grep -r "TODO\|FIXME\|XXX" src/opcode_cli --include="*.py"

# 手动审查后删除
# - docs/01-09 中的重复历史文档（保留最近的演进记录）
# - 未使用的工具实现
# - dead imports
```

**T1.3: 补充基础文档**
```markdown
docs/
├── README.md              # 更新为反映目标架构
├── ARCHITECTURE.md        # 现有架构缺点和目标
├── CONTRIBUTING.md        # 开发者指南
└── CHANGELOG.md           # 版本变更记录
```

**T1.4: 生成依赖图**
```bash
# 安装工具
pip install pyan3

# 生成调用图
pyan3 src/opcode_cli/*.py --no-paths --dot > call_graph.dot

# 可视化（可选）
dot -Tpng call_graph.dot -o call_graph.png
```

**产出物**:
- ✅ `experience/01-initial-analysis.md` (本次分析记录)
- ✅ 清理后的代码库（减少 ~500 行死代码）
- ✅ 新的 README.md 和 ARCHITECTURE.md
- ✅ call_graph.dot 文件

### 4.2 阶段二：核心架构重组 (预计 3-5 天)

#### 任务清单

**T2.1: 创建新目录结构**
```bash
mkdir -p src/opcode_cli/{core,application,infrastructure,presentation,shared,domain}

# 移动文件
mv src/opcode_cli/{agent,context,memory,permission,prompt} src/opcode_cli/core/
mv src/opcode_cli/commands src/opcode_cli/application/
mv src/opcode_cli/mcp src/opcode_cli/infrastructure/
mv src/opcode_cli/provider src/opcode_cli/infrastructure/providers/
mv src/opcode_cli/tools src/opcode_cli/infrastructure/tools/
mv src/opcode_cli/tui src/opcode_cli/presentation/tui/

# 创建空目录
mkdir -p src/opcode_cli/shared/{config,types,utils}
mkdir -p src/opcode_cli/domain/{events,aggregates,value_objects}
```

**T2.2: 重构 main.py 为新入口点**
```python
# presentation/cli/entry.py (替代 main.py)
import sys
import asyncio
from opcode_cli.shared.config import load_app_config
from opcode_cli.shared.di import Container
from opcode_cli.presentation.tui.app import OpcodeApp

def create_application_container():
    """创建应用容器"""
    container = Container()
    
    # 配置
    config = load_app_config()
    container.register('config', lambda: config)
    
    # Provider
    from opcode_cli.infrastructure.providers.manager import ProviderManager
    provider_mgr = ProviderManager(config)
    container.register('provider', lambda: provider_mgr.get_provider('default'))
    
    # Registry
    from opcode_cli.infrastructure.tools.registry import ToolRegistry
    registry = ToolRegistry()
    # ... 注册工具
    container.register('registry', lambda: registry, singleton=True)
    
    # Agent
    from opcode_cli.core.agent.agent import Agent
    container.register(
        'agent',
        lambda p, r: Agent(provider=p, registry=r),
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

async def run_member_mode():
    """队员模式运行逻辑"""
    pass

def main():
    """主入口"""
    # 解析命令行参数
    args = parse_args()
    
    # 启动队员模式或 TUI
    if args.team and args.member:
        asyncio.run(run_member_mode(args))
    else:
        container = create_application_container()
        app = OpcodeApp(container.resolve('agent'), 
                       container.resolve('command_registry'))
        app.run()

if __name__ == "__main__":
    main()
```

**T2.3: 重构工具系统**
```bash
# 整理工具文件
mv src/opcode_cli/infrastructure/tools/{read_file,write_file,edit_file}.py \
   src/opcode_cli/infrastructure/tools/file_ops.py

mv src/opcode_cli/infrastructure/tools/{glob_find,grep_search}.py \
   src/opcode_cli/infrastructure/tools/search_tools.py

# 删除不必要的单独文件
rm src/opcode_cli/infrastructure/tools/{agent_tool,install_skill,load_skill,run_command,run_isolated}.py
# 将这些工具迁移到更合适的 location
```

**T2.4: 整合记忆系统**
```python
# core/memory/store.py (整合原有分散的 store/index/updater)
from dataclasses import dataclass
from pathlib import Path
import json
from typing import Optional

@dataclass
class MemoryEntry:
    id: str
    created_at: str
    content: str
    tags: list[str]

class MemoryStore:
    """统一记忆存储"""
    
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self._cache: dict[str, MemoryEntry] = {}
    
    def save(self, entry: MemoryEntry) -> None:
        """保存记忆"""
        path = self.base_dir / f"{entry.id}.json"
        with open(path, 'w') as f:
            json.dump(entry.__dict__, f, indent=2)
    
    def get(self, id: str) -> Optional[MemoryEntry]:
        """获取记忆"""
        if id in self._cache:
            return self._cache[id]
        
        path = self.base_dir / f"{id}.json"
        if path.exists():
            with open(path) as f:
                data = json.load(f)
            entry = MemoryEntry(**data)
            self._cache[id] = entry
            return entry
        return None
    
    def index(self) -> list[MemoryEntry]:
        """获取索引"""
        return list(self._cache.values())
```

**T2.5: 重构 UI 层**
```python
# presentation/tui/app.py (精简 main.py 中的 App 初始化逻辑)
from textual.app import App
from opcode_cli.core.events import AgentEvent

class OpcodeApp(App):
    """Opcode TUI 应用"""
    
    def __init__(self, agent, command_registry):
        super().__init__()
        self.agent = agent
        self.command_registry = command_registry
        self.events_queue: asyncio.Queue = asyncio.Queue()
    
    async def on_mount(self):
        """应用启动时开始监听 Agent"""
        asyncio.create_task(self._listen_agent())
    
    async def _listen_agent(self):
        """监听 Agent 事件"""
        async for event in self.agent.run("start"):
            await self.events_queue.put(event)
    
    async def process_event(self, event: AgentEvent):
        """处理事件"""
        # 根据事件类型更新 UI
        pass
```

**产出物**:
- ✅ 新的目录结构完成迁移
- ✅ `presentation/cli/entry.py` (单责入口点)
- ✅ `infrastructure/tools/file_ops.py` (整合文件操作工具)
- ✅ `infrastructure/tools/search_tools.py` (整合搜索工具)
- ✅ `core/memory/store.py` (统一记忆存储)
- ✅ 精简的 `presentation/tui/app.py`

### 4.3 阶段三：代码优化和质量提升 (预计 2-3 天)

#### 任务清单

**T3.1: 类型注解全覆盖**
```bash
# 安装类型检查工具
pip install mypy==1.8.0 pydantic==2.5.0

# 为目标文件添加类型注解
# 参考示例：
def process_user_input(user_input: str, context: CommandContext) -> Result[CommandResponse, Error]:
    """处理用户输入"""
    ...

# 运行严格类型检查
mypy --strict src/opcode_cli/core/
mypy --strict src/opcode_cli/application/
```

**T3.2: 统一错误处理**
```python
# shared/errors.py
from enum import Enum
from dataclasses import dataclass

class ErrorCode(Enum):
    PERMISSION_DENIED = "PERM_001"
    TOOL_EXECUTION_FAILED = "TOOL_001"
    CONFIG_ERROR = "CFG_001"
    INVALID_PARAMETER = "INV_001"

@dataclass
class OpcodeError(Exception):
    code: ErrorCode
    message: str
    details: dict[str, Any] = None

class PermissionError(OpcodeError):
    def __init__(self, message: str, resource: str):
        super().__init__(
            code=ErrorCode.PERMISSION_DENIED,
            message=message,
            details={"resource": resource}
        )

class ToolExecutionError(OpcodeError):
    def __init__(self, tool_name: str, original_error: Exception):
        super().__init__(
            code=ErrorCode.TOOL_EXECUTION_FAILED,
            message=f"Tool '{tool_name}' execution failed",
            details={"original_error": str(original_error)}
        )
```

**T3.3: 日志标准化**
```python
# shared/utils/logger.py
import structlog
import logging
from pathlib import Path

def setup_logger(name: str, log_file: Path) -> None:
    """设置结构化日志"""
    
    # 配置文件输出
    logging.basicConfig(
        filename=log_file,
        level=logging.INFO,
        format='%(message)s'
    )
    
    # 配置控制台输出
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # 使用 structlog 包装
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.set_exc_info,
            structlog.processors.format_stdlib(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

# 使用示例
log = structlog.get_logger(__name__)
log.info("tool_executed", tool_name="read_file", duration=0.5, success=True)
```

**T3.4: 性能分析和优化**
```bash
# 安装 profilers
pip install py-spy line_profiler memory_profiler

# CPU Profiling
py-spy record -o profile.svg -- python -m opcode_cli

# Line-by-line profiling
@profile
def critical_path_function():
    # hot path code
    pass

# Run with: kernprof -l -v script.py
```

**产出物**:
- ✅ 所有公共 API 带有完整类型注解
- ✅ 统一的异常层次结构和错误码
- ✅ 结构化日志系统（支持 JSON 格式输出）
- ✅ 性能分析报告和优化建议

### 4.4 阶段四：测试体系建设 (预计 2-3 天)

#### 任务清单

**T4.1: 创建测试目录结构**
```bash
tests/
├── conftest.py              # pytest fixtures
├── unit/
│   ├── core/
│   │   ├── test_agent.py
│   │   ├── test_context_manager.py
│   │   ├── test_permission_checker.py
│   │   └── test_memory_store.py
│   ├── application/
│   │   └── test_commands.py
│   └── infrastructure/
│       ├── test_tools.py
│       └── test_providers.py
├── integration/
│   ├── test_agent_toolchain.py
│   └── test_team_collaboration.py
└── e2e/
    └── test_full_workflow.py
```

**T4.2: 编写核心单元测试**
```python
# tests/unit/core/test_agent.py
import pytest
from opcode_cli.core.agent.agent import Agent
from opcode_cli.infrastructure.tools.registry import ToolRegistry
from opcode_cli.provider.base import Message

@pytest.mark.asyncio
async def test_agent_initialization():
    """测试 Agent 初始化"""
    registry = ToolRegistry()
    agent = Agent(registry=registry)
    
    assert agent.max_iterations == 25
    assert len(agent.messages) == 0

@pytest.mark.asyncio
async def test_agent_tool_execution(mocker):
    """测试 Agent 工具执行"""
    # Mock provider
    mock_provider = mocker.Mock()
    mock_provider.chat_completion.return_value = Message(
        role="assistant",
        content='{"tool_calls": [{"name": "read_file", "arguments": {"path": "/test"}}]}'
    )
    
    # Mock tool
    mock_tool = mocker.Mock()
    mock_tool.name = "read_file"
    mock_tool.is_read_only = True
    mock_tool.execute.return_value = ToolResult(
        success=True,
        content="file content"
    )
    
    registry = ToolRegistry()
    registry.register(mock_tool)
    
    agent = Agent(provider=mock_provider, registry=registry)
    
    async for event in agent.run("read /test"):
        if isinstance(event, ToolExecuteEvent):
            assert event.tool_name == "read_file"
            break
```

**T4.3: 编写集成测试**
```python
# tests/integration/test_agent_toolchain.py
import pytest
from opcode_cli.core.agent.agent import Agent
from opcode_cli.infrastructure.tools.registry import ToolRegistry
from opcode_cli.tools.read_file import ReadFileTool
from opcode_cli.tools.write_file import WriteFileTool
import tempfile
import os

@pytest.mark.asyncio
async def test_read_write_cycle():
    """测试读写文件循环"""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = os.path.join(tmpdir, "test.txt")
        
        registry = ToolRegistry()
        registry.register(ReadFileTool())
        registry.register(WriteFileTool())
        
        agent = Agent(registry=registry)
        
        # 写入文件
        await agent.run(f"echo 'hello world' > {test_file}")
        
        # 读取文件
        content = await agent.run(f"cat {test_file}")
        
        assert "hello world" in content
```

**T4.4: 编写 E2E 测试**
```python
# tests/e2e/test_full_workflow.py
import pytest
from textual.testing import run_app

@pytest.mark.asyncio
async def test_full_cli_workflow():
    """测试完整 CLI 工作流"""
    # 模拟用户输入和响应
    # ... 详细的端到端测试逻辑
    pass
```

**T4.5: 配置覆盖率**
```toml
# pyproject.toml
[tool.coverage.run]
source = ["src/opcode_cli"]
branch = true

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise AssertionError",
    "raise NotImplementedError",
]
fail_under = 80  # 至少 80% 覆盖率
```

**产出物**:
- ✅ 单元测试套件（核心模块 > 80% 覆盖率）
- ✅ 集成测试套件（关键流程）
- ✅ E2E 测试（核心用户体验）
- ✅ 自动化 CI/CD 配置（GitHub Actions）

### 4.5 阶段五：文档完善和发布 (预计 1 天)

#### 任务清单

**T5.1: 编写 ADR 文档**
```markdown
docs/adr/
├── 001-modular-layered-architecture.md
├── 002-dependency-injection-pattern.md
├── 003-unified-tool-interface.md
├── 004-error-handling-strategy.md
├── 005-structured-logging.md
└── 006-testing-pyramid.md
```

**T5.2: 更新开发者文档**
```markdown
CONTRIBUTING.md:
- Prerequisites (Python >= 3.10, virtualenv)
- Setup instructions
- Code style guidelines
- Testing requirements
- How to submit PRs
```

**T5.3: 生成 API 文档**
```bash
# 安装文档生成工具
pip install pdoc

# 生成文档
pdoc src/opcode_cli --output-dir docs/api

# 部署到 GitHub Pages (可选)
```

**产出物**:
- ✅ 完整的 ADR 文档集
- ✅ 更新的 CONTRIBUTING.md
- ✅ 自动生成的 API 文档

---

## 5. 风险控制策略

### 5.1 渐进式迁移

**原则**: 不要一次性重写所有代码，而是按阶段逐步迁移：

1. **先写测试**（确保有安全网）
2. **小步提交**（每次 commit 都是可发布的）
3. **并行运行**（新旧代码可同时运行一段时间）
4. **回滚计划**（每个阶段都有明确的回滚步骤）

### 5.2 兼容性保障

**策略**:
- 保持外部 API 不变（CLI 参数、配置文件格式）
- 隐藏内部重构细节（用户无感知）
- 充分测试回归问题

### 5.3 回滚方案

如果某个阶段出现问题：

```bash
# Git 标签回滚
git checkout <previous-stable-tag>

# 恢复旧代码
git restore src/opcode_cli

# 重新部署
python -m pip install -e .
```

---

## 6. 时间估算

| 阶段 | 主要任务 | 预计工时 |
|------|----------|----------|
| 1. 清理和准备 | 经验库、删除死代码、基础文档、依赖图 | 10-16 小时 |
| 2. 架构重组 | 分层改造、依赖注入、工具整合 | 24-40 小时 |
| 3. 质量提升 | 类型注解、错误处理、日志标准化、性能优化 | 16-24 小时 |
| 4. 测试建设 | 单元测试、集成测试、E2E 测试 | 16-24 小时 |
| 5. 文档完善 | ADR、API 文档、开发者指南 | 8 小时 |
| **总计** | | **74-112 小时** |

按每天工作 8 小时计算：**约 9-14 个工作日**

---

## 7. 验收标准

重构完成后，需满足以下标准才能视为完成：

### 7.1 功能性验收

- ✅ 所有现有功能正常工作
- ✅ CLI 参数和行为保持一致
- ✅ 配置文件格式无需变更
- ✅ TUI 界面和操作体验不变

### 7.2 质量性验收

- ✅ `mypy --strict` 零错误
- ✅ `flake8` 零警告
- ✅ 单元测试覆盖率 > 80%
- ✅ 集成测试全部通过
- ✅ E2E 测试覆盖核心流程

### 7.3 文档验收

- ✅ ADR 文档完整（至少 5 个关键决策）
- ✅ README.md 更新（包含新架构说明）
- ✅ CONTRIBUTING.md 可用（新人能上手）
- ✅ API 文档自动生成

### 7.4 性能验收

- ✅ 启动时间不超过原版本的 110%
- ✅ 单次工具调用延迟增加不超过 50ms
- ✅ 内存占用无明显增长

---

## 8. 后续改进建议

重构完成后，可考虑的进一步改进方向：

1. **插件化架构**: 允许外部自定义工具
2. **远程协作增强**: 支持更多成员角色和审批流
3. **LLM 路由优化**: 基于成本和质量的智能路由
4. **增量学习**: 长期记忆和改进机制

---

## 9. 附录

### 9.1 参考资料

- [Pi Tools Adaptation](C:\Users\95desire\.pi\agent\git\github.com\obra\superpowers\skills\using-superpowers\references\pi-tools.md)
- [Textual 8.x Guidelines](https://textual.textualize.io/)
- [Pydantic v2 Migration](https://docs.pydantic.dev/latest/migration/)
- [Dependency Injection Patterns](https://dev.to/robinrendle/the-di-container-from-zero-to-hero-560d)

### 9.2 工具链

```bash
# 开发工具
pip install mypy==1.8.0 flake8==7.0.0 black==24.1.0 isort==5.13.2

# 测试工具
pip install pytest==7.4.0 pytest-cov==4.1.0 pytest-asyncio==0.23.0

# 性能工具
pip install py-spy==0.3.14 line_profiler==4.0.3

# 文档工具
pip install pdoc==14.2.0 structlog==24.1.0

# 绘图工具
pip install pyan3==1.8.0 graphviz==0.20.1
```

---

**文档结束**

请仔细阅读此规格文档并提出反馈意见。一旦您批准此设计，我将开始创建详细的实施清单并逐步执行。

