# Phase 0 前置准备工作报告

**日期**: 2026-05-10  
**执行角色**: Lead  
**阶段**: Phase 0 — 前置准备  
**状态**: 已完成

---

## 交付清单

| 编号 | 任务 | 产出物 | 状态 |
|------|------|--------|------|
| L1 | 定义 BaseAgent 抽象基类 | `src/manimind/agents/base.py` | 已完成 |
| L2 | 定义 Agent 间数据协议 | `docs/agent-data-protocol.md` | 已完成 |
| L3 | 创建目录结构 + __init__.py | 5 个新包目录 | 已完成 |
| L2.1 | 补充输入摄取层输出格式 | `docs/agent-data-protocol.md` v1.1 | 已完成（补充） |

---

## L1: BaseAgent 抽象基类

**文件**: `src/manimind/agents/base.py` (~140 行)

### 设计决策

- **`LlmClientProtocol`**: 使用 `Protocol` + `@runtime_checkable` 定义 LLM 客户端接口，不依赖具体实现。包含 `chat()` 和 `chat_structured()` 两个方法，与实施计划中 C2 的 `LlmClient` 设计一致。
- **`BaseAgent`**: 使用 `ABC` 抽象基类，定义统一的 Agent 生命周期：
  - `get_context_packet(stage)` — 获取上下文包
  - `build_system_prompt(stage)` — 生成系统提示词分段
  - `build_user_message(stage, task_id)` — 构建用户消息（子类可按阶段覆盖）
  - `run(stage, task_id)` — 抽象方法，子类必须实现
- **上下文读写**: `_read_context(key)` 和 `_write_context(key, content, scope)` 直接操作 runtime 文件系统，读写统一信封格式的 JSON。后续可提取到 `context_io.py`。
- **权限控制**: `_write_context()` 强制校验 read_only 角色不能写入长期上下文。
- **子类约定**: 子类只需设置 `role_id` 类属性并实现 `run()` 即可自动匹配 `AgentProfile`。

### 关键接口

```python
class BaseAgent(ABC):
    role_id: str                      # 子类设置，匹配 AgentProfile.id

    def __init__(self, plan, llm_client=None, session_id="default")
    def build_system_prompt(stage) -> list[str]
    def get_context_packet(stage) -> dict
    def run(stage, task_id, **kwargs) -> dict    # 抽象方法
    def build_user_message(stage, task_id) -> str # 可覆盖
    def _read_context(key) -> Any | None
    def _write_context(key, content, scope) -> Path
```

---

## L2: Agent 间数据协议

**文件**: `docs/agent-data-protocol.md` (~360 行)  
**版本**: v1.0 → v1.1

### 文档结构

1. **输入摄取层输出格式** — SourceBundle统一入口、PaperContent、NoteContent、AssetList、EnvReport（新增）
2. **核心原则** — 文件系统交换、短期/长期上下文分离、审计日志
3. **数据流总览** — ASCII图展示 输入摄取层 → Explorer → Planner → Coordinator 完整链路
4. **文件路径约定** — 短期/长期上下文的目录结构和命名规则
5. **Explorer 产出格式** — 研究总结、术语表、公式目录的 JSON Schema
6. **Planner 产出格式** — 约束分析、分镜建议的 JSON Schema
7. **Coordinator 产出格式** — 讲解脚本、分镜主表、会话交接的 JSON Schema
8. **通用信封格式** — 所有上下文文件的统一封装结构
9. **优雅降级规则** — PDF 缺失、LLM 不可用等场景的处理方式
10. **版本兼容性** — 向前兼容策略

### 关键设计

- **输入摄取层**（新增）：纯工具层，不写 runtime，返回 Python dataclass 给 Explorer
- Explorer 和 Planner 产出写入 `runtime/sessions/<session_id>/`（短期上下文），符合 read_only 角色约束
- Coordinator 产出写入 `runtime/projects/<project_id>/`（长期上下文），下游 Worker 直接消费
- 所有 JSON 使用统一信封 `{key, scope, writer_role, session_id, content}`
- JSON Schema 严格类型化但向前兼容（忽略未知字段）

---

## L3: 目录结构与包初始化

### 新建目录

```
src/manimind/
├── agents/          # Agent 执行器层
│   └── base.py      # BaseAgent + LlmClientProtocol
├── ingest/          # 输入摄取层（待 Team A 实现）
├── llm/             # LLM 调用层（待 Team C2 实现）
│   └── templates/   # Prompt 模板（待各 Agent 组实现）
└── memory/          # 上下文读写层（待 Team B2 实现）
```

### 已更新文件

- `src/manimind/__init__.py` — 新增 `BaseAgent` 和 `LlmClientProtocol` 导出
- `src/manimind/agents/__init__.py` — 导出 BaseAgent 和 LlmClientProtocol
- 各新包的 `__init__.py` — 含 docstring 说明职责

---

## 验证结果

- **现有测试**: 21 passed, 0 failed
- **导入验证**: `BaseAgent` 和 `LlmClientProtocol` 可通过 `from manimind import ...` 正常导入
- **类型检查**: `LlmClientProtocol` 正确标记为 `@runtime_checkable`

---

## 下一步（Phase 1 基础设施并行）

Phase 0 为以下并行工作提供了接口契约：

| 组 | 依赖 Phase 0 的哪些产出 |
|----|------------------------|
| 输入摄取组 (A1, A2) | L3 目录结构 + L2.1 SourceBundle/PaperContent/NoteContent/AssetList/EnvReport格式约定 |
| LLM 封装 (C2) | L1 的 `LlmClientProtocol` |
| 上下文 IO (B2) | L1 的 `_read_context` / `_write_context` 签名 |
| Explorer 组 (B1) | L1 的 `BaseAgent` + L2 的产出格式 + L2.1 的 SourceBundle |
| Planner 组 (C1) | L1 的 `BaseAgent` + L2 的产出格式 |
| Coordinator 组 (D1, D2) | L1 的 `BaseAgent` + L2 的产出格式 |

各组可**完全并行**启动 Phase 1。
