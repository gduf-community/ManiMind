# Explorer / Planner / Coordinator 三 Agent 实施方案

---

## ⚠️ 重要说明

以下所有人员工作时间分配均**仅供参考**。考虑到团队成员可能有不同的时间投入、课程安排或其他事务，实际实施过程中请**根据实时情况灵活调整**：

- 如果某个成员时间有限，可以将其任务拆分给其他有空的成员
- 如果某个小组进度受阻，可以从其他小组临时调配人员支援
- 可以根据每个人的兴趣和专长调整任务分配
- 优先保证核心路径的功能实现，非关键功能可以延后

让我们保持灵活沟通，共同完成项目！💪

---

## 📋 完整项目框架总览

ManiMind 是一个面向数学科普动画生产的多 Agent 编排系统，完整的 Agent 体系如下：

```
                    ┌─────────────────────────┐
                    │         Lead            │
                    │    项目总控/状态        │
                    └──────────┬────────────┘
                               │
           ┌───────────────────┼───────────────────┐
           │                   │                   │
    ┌──────▼──────┐    ┌──────▼──────┐    ┌──────▼──────┐
    │   Explorer  │    │   Planner   │    │ Coordinator │
    │   资料探索    │    │   方案规划    │    │脚本/分镜/分发│
    └─────────────┘    └─────────────┘    └──────┬──────┘
                                                    │
                              ┌─────────────────────┼─────────────────────┐
                              │                     │                     │
                       ┌──────▼──────┐     ┌──────▼──────┐     ┌──────▼──────┐
                       │  HTML Worker │     │  Manim Worker│     │  SVG Worker  │
                       │   HTML片段    │     │   数学动画    │     │   SVG动效    │
                       └──────┬──────┘     └──────┬──────┘     └──────┬──────┘
                              │                     │                     │
                              └─────────────────────┼─────────────────────┘
                                                    │
                                           ┌────────▼───────┐
                                           │    Reviewer    │
                                           │  审核/阻塞/放行 │
                                           └────────────────┘
```

### 🎯 我们的当前任务

**本次实施范围：Explorer / Planner / Coordinator 三 Agent**

我们采用**分阶段、迭代式**的开发策略：

1. **第一阶段**（当前）：完成上游核心逻辑
   - ✅ Lead（已有部分）
   - 🔄 **Explorer（资料探索）**
   - 🔄 **Planner（方案规划）**
   - 🔄 **Coordinator（脚本/分镜/分发）**

2. **第二阶段**（后续）：完成下游工作
   - HTML Worker
   - Manim Worker
   - SVG Worker
   - Reviewer

3. **第三阶段**（最后）：完成端到端闭环
   - post_produce（后期）
   - package（打包）

---

## 概况预览：（省流版！）
● 计划已保存到 docs/Explorer-Planner-Coordinator实施计划.md。以下是核心思路的概述：

  ---
  当前代码 vs 需要做的事

  骨架已完整（models.py, workflow.py, context_assembly.py, task_board.py, runtime_store.py），但三个 Agent 只是数据描述
  —— 没有任何代码真正"运行"它们。

  需要新建的核心能力：
  1. Agent 执行器 — 每个 Agent 的 run() 逻辑
  2. LLM 调用层 — 把 context packet 变成真正发给 LLM 的 prompt，并解析返回结果
  3. 输入摄取层 — PDF 解析、笔记读取、资产扫描
  4. 上下文读写层 — context_io.py 读写 runtime/projects/ 和 runtime/sessions/

  团队分工

  | 组              | 人数 | 负责                                                                 |
  |-----------------|------|----------------------------------------------------------------------|
  | Lead            | 1    | BaseAgent 接口、数据协议、CLI/API 接入、集成测试、代码审查          |
  | 输入摄取组      | 2    | PDF 读取、Markdown 读取、资产扫描、环境检测                          |
  | Explorer 组     | 2    | Explorer prompt 模板 + 主逻辑 + context_io（上下文读写工具）        |
  | Planner 组      | 2    | LLM 客户端封装 + Planner prompt 模板 + 主逻辑                       |
  | Coordinator 组  | 2    | Coordinator prompt 模板 + 主逻辑 + DISPATCH 阶段 + 输出格式校验     |

---

## 🎯 团队分工选择指南
---

### 📋 任务清单（按难度标记）

#### 输入摄取组
| 任务 | 难度 | 说明 |
|------|------|------|
| Markdown 读取 | 🌟 | 相对简单，适合入门 |
| 资产扫描 | 🌟 | 遍历目录，生成清单 |
| 环境检测报告 | 🌟🌟 | 复用现有 bootstrap.check_tools() |
| PDF 读取 | 🌟🌟 | 处理编码、公式混排 |
| 单元测试 | 🌟-🌟🌟 | 根据模块难度而定 |

#### Explorer 组
| 任务 | 难度 | 说明 |
|------|------|------|
| context_io（读取） | 🌟🌟 | 从 runtime 读文件 |
| context_io（写入） | 🌟🌟 | 原子写入 + 权限校验 |
| Explorer 输出解析器 | 🌟🌟 | 从 LLM 响应提取结构化数据 |
| Explorer prompt 模板 | 🌟🌟🌟 | 需要理解 context_packet |
| ExplorerAgent 主类 | 🌟🌟🌟 | 继承 BaseAgent，实现 run() |

#### Planner 组
| 任务 | 难度 | 说明 |
|------|------|------|
| LLM 客户端封装 | 🌟🌟 | OpenAI API 调用 + 重试 |
| Planner 输出解析器 | 🌟🌟 | 提取约束、建议等 |
| Planner prompt 模板 | 🌟🌟🌟 | 需要理解业务逻辑 |
| PlannerAgent 主类 | 🌟🌟🌟 | 继承 BaseAgent，实现 run() |

#### Coordinator 组
| 任务 | 难度 | 说明 |
|------|------|------|
| 输出格式校验 | 🌟🌟 | JSON Schema 校验 |
| Coordinator prompt 模板（PLAN） | 🌟🌟🌟 | 讲解脚本 + 分镜 |
| Coordinator prompt 模板（DISPATCH） | 🌟🌟🌟 | 任务分发 + 会话交接 |
| Coordinator 输出解析器 | 🌟🌟🌟 | 两个阶段都要处理 |
| CoordinatorAgent 主类 | 🌟🌟🌟🌟 | 最复杂，需要结构化写入 |

#### Lead
| 任务 | 难度 | 说明 |
|------|------|------|
| BaseAgent 抽象类 | 🌟🌟🌟 | 定义接口和通用逻辑 |
| Agent 间数据协议 | 🌟🌟🌟 | 文档 + 格式约定 |
| CLI/API 接入 | 🌟🌟🌟 | 集成所有模块 |
| 集成测试 | 🌟🌟🌟 | 端到端测试 |
| 代码审查 | 🌟🌟🌟 | 全局把控代码质量 |

---

  四阶段推进（约 10 天）

  1. 阶段 0（1 天） — lead 先写出 BaseAgent 抽象类和 Agent 间数据协议
  2. 阶段 1（2-4 天） — 三组并行：输入摄取组 / LLM 封装+上下文IO / 基础设施
  3. 阶段 2（5-8 天） — 三组并行：各自的 Agent 主逻辑和 prompt 模板
  4. 阶段 3-4（9-10 天） — CLI/API 接入、三 Agent 串联、端到端验证

  关键设计决策

  - Agent 间不直接通信，通过 runtime/sessions/ 文件系统交换数据（与现有原子写入+JSONL 审计机制一致）
  - Explorer 和 Planner 是 read_only，产出写入短期上下文作为"建议稿"，Coordinator 是第一个有写入权的
  Agent，产出写入长期上下文
  - LLM 客户端支持 OpenAI 兼容接口（.env 配置 OPENAI_API_KEY / OPENAI_BASE_URL），Coordinator 用 chat_structured 强制
  JSON Schema 输出


## 一、现状盘点：已有 vs 缺失

### 已有（可直接复用）

| 模块 | 能力 | 位置 |
|:---|:---|:---|
| 数据模型 | `AgentProfile`, `ExecutionTask`, `ContextRecord`, `ProjectPlan` 等全部语义骨架 | `src/manimind/models.py` |
| 工作流引擎 | `build_project_plan()` 已定义三 Agent 的角色画像、允许阶段、必需输入、产出归属 | `src/manimind/workflow.py` |
| 上下文装配 | `build_context_packet()` 可按 role_id + stage 生成上下文包与约束 | `src/manimind/context_assembly.py` |
| 任务状态机 | `update_execution_task_status()` 含 owner/blocker 校验、verification nudge | `src/manimind/task_board.py` |
| 状态落盘 | `persist_plan_snapshot()` / `persist_context_packet()` / `persist_task_update()` 原子写入 + JSONL 审计日志 | `src/manimind/runtime_store.py` |
| 阶段派生 | `derive_current_stage()` 从任务状态自动推断当前阶段 | `src/manimind/runtime.py` |
| CLI 入口 | `plan` / `context-pack` / `task-update` 三个命令已接入落盘 | `src/manimind/main.py` |
| 配置文件 | `pipeline.example.json` 标准 manifest 示例 | `configs/pipeline.example.json` |
| 测试 | 14 个测试全部通过 | `tests/` |

### 缺失（需要新建）

1. **没有 Agent 执行器** — `AgentProfile` 只是描述，没有任何代码真正"运行" Explorer / Planner / Coordinator
2. **没有 LLM 调用层** — 当前只生成 prompt scaffold（context_packet），缺少实际调用 LLM 并解析返回结果的代码
3. **没有输入摄取能力** — 无法解析 PDF、读取 Markdown 笔记、扫描参考资源
4. **没有上下文内容读写** — context packet 描述了"应该有什么"，但没有实际读写上下文正文的方法
5. **没有子 Agent 回传协议** — Explorer 的发现如何写给 Planner？Planner 的建议如何传给 Coordinator？格式未定义

### 一句话

> 编排骨架已完整，当前需要的是**让三个 Agent 真正"动起来"**，即：接收 context packet → 调用 LLM → 解析结果 → 写入 runtime → 推进任务状态。

---

## 二、目标架构

```
┌──────────────────────────────────────────────────────────────────┐
│                      CLI / API 层（已有）                          │
│  plan | context-pack | task-update                                │
└──────────────────────────┬───────────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────────┐
│                   Agent Runner 层（本次新建）                       │
│                                                                    │
│  agents/base.py         → BaseAgent 统一接口                       │
│  agents/explorer.py     → ExplorerAgent.run()                     │
│  agents/planner.py      → PlannerAgent.run()                      │
│  agents/coordinator.py  → CoordinatorAgent.run()                  │
│  agents/orchestrator.py → 串联 Explorer→Planner→Coordinator       │
└──────────────────────────┬───────────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────────┐
│                   支撑层（本次新建）                                 │
│                                                                    │
│  llm/client.py          → LLM 调用封装（OpenAI 兼容接口）            │
│  llm/templates.py       → 各 Agent 的 prompt 模板                  │
│  ingest/pdf_reader.py   → PDF 文本提取                             │
│  ingest/markdown_reader.py → Markdown 笔记读取                     │
│  ingest/asset_scanner.py   → resources/ 参考资产发现               │
│  memory/context_io.py   → 上下文读取 / 结构化回写                   │
└──────────────────────────┬───────────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────────┐
│                   编排内核层（已有）                                 │
│  models.py / workflow.py / context_assembly.py /                  │
│  task_board.py / runtime.py / runtime_store.py                    │
└──────────────────────────────────────────────────────────────────┘
```

---

## 三、三个 Agent 的详细设计

### 3.1 共同接口：`BaseAgent`

```python
# src/manimind/agents/base.py
class BaseAgent:
    """所有 Agent 的抽象基类。"""

    role_id: str          # "explorer" / "planner" / "coordinator"
    profile: AgentProfile # 来自 build_agent_profiles()
    plan: ProjectPlan     # 当前项目计划
    llm_client: LlmClient # LLM 调用封装

    def build_system_prompt(self, stage: PipelineStage) -> str:
        """调用 context_assembly 生成该角色在该阶段的系统提示词。"""
        ...

    def run(self, stage: PipelineStage, task_id: str) -> dict:
        """
        1. 从 runtime 加载当前状态
        2. 组装 system prompt
        3. 构造 user message（包含具体任务指令）
        4. 调用 LLM
        5. 解析返回结果
        6. 写入 runtime（如果是 structured_write 模式）
        7. 更新任务状态
        """
        ...

    def _read_context(self, key: str) -> str | None:
        """从 runtime 读取指定 key 的上下文正文。"""
        ...

    def _write_context(self, key: str, content: str) -> None:
        """向 runtime 写入上下文正文（仅 structured_write 可用）。"""
        ...
```

### 3.2 Explorer Agent

**角色定位（已有定义）：**
- mode: `read_only`
- allowed_stages: `PRESTART, INGEST, SUMMARIZE, PLAN`
- responsibility: 只读检索论文、现有代码与第三方资产中的相关模式
- owned_outputs: 无（只读角色）
- output_contract: 只返回搜索发现与候选引用，不直接落盘项目产物

**需要实现的能力：**

| 功能 | 输入 | 输出 | 对应阶段 |
|:---|:---|:---|:---|
| 工具链检测 | workspace | `doctor-report.json` | PRESTART |
| PDF 提取 | paper_path | 论文全文文本 | INGEST |
| 笔记读取 | note_paths | 结构化笔记内容 | INGEST |
| 参考资产扫描 | resources/ | 可用模板/块/组件清单 | INGEST |
| 研究总结生成 | 论文全文 + 笔记 | `research.summary` 建议稿 | SUMMARIZE |
| 术语表生成 | 论文全文 | `glossary` 建议稿 | SUMMARIZE |
| 公式目录生成 | 论文全文 | `formula.catalog` 建议稿 | SUMMARIZE |
| 模式检索 | 用户问题 | 候选参考链接与说明 | PLAN |

**关键约束：**
- Explorer 是 read_only 模式 → 不能写 `owned_outputs`
- 其产出是"建议"而非"权威版本"，需写入短期上下文供 Lead 审核
- 实际写入 `runtime/sessions/<session_id>/explorer-findings/`

**实现策略：**
Explorer 的核心逻辑是"读取 + 总结"。LLM 扮演 Explorer 角色，接收论文内容和笔记，输出结构化的研究发现。paper_path 对应的 PDF 可能不存在（测试用 .pdf 占位符），需要优雅降级。

### 3.3 Planner Agent

**角色定位（已有定义）：**
- mode: `read_only`
- allowed_stages: `SUMMARIZE, PLAN`
- responsibility: 只读分析约束并提出分镜与实现规划建议
- owned_outputs: 无（只读角色）
- output_contract: 只能产出规划建议，正式分镜需由协调层写入结构化上下文

**需要实现的能力：**

| 功能 | 输入 | 输出 | 对应阶段 |
|:---|:---|:---|:---|
| 约束分析 | research.summary + glossary + formula.catalog + style.guide | 约束清单（数学难度、受众适配、时间预估） | SUMMARIZE |
| 分镜建议 | 约束清单 + segments 定义 | `storyboard` 建议稿（镜头顺序、转场、重点） | PLAN |
| 可行性评估 | 分镜建议 + 资产清单 | 风险点与替代方案 | PLAN |

**关键约束：**
- Planner 是 read_only 模式 → 不能写 `owned_outputs`
- 建议稿写入 `runtime/sessions/<session_id>/planner-suggestions/`
- 正式分镜和脚本由 Coordinator 写入

**实现策略：**
Planner 的核心逻辑是"分析 + 建议"。它接收 Explorer 产出的研究总结、术语表和公式目录，结合受众画像和风格规范，输出结构化的规划建议。LLM 扮演 Planner 角色。

### 3.4 Coordinator Agent

**角色定位（已有定义）：**
- mode: `structured_write`
- allowed_stages: `PLAN, DISPATCH`
- responsibility: 生成讲解脚本、分镜和任务分发表，负责把建议落实为结构化计划
- owned_outputs: `narration.script`, `storyboard.master`, `session.handoff`
- output_contract: 必须写出可追溯任务分发结果，不能只停留在自然语言说明

**需要实现的能力：**

| 功能 | 输入 | 输出 | 对应阶段 |
|:---|:---|:---|:---|
| 讲解脚本生成 | segments + research.summary + planner 建议 | `narration.script`（逐镜头讲解词） | PLAN |
| 分镜主表生成 | segments + narration.script + style.guide | `storyboard.master`（含 modality、时长、公式、动画备注） | PLAN |
| 任务分发 | storyboard.master + worker profiles | `execution_tasks` 更新（解锁 render.* 任务） | DISPATCH |
| 会话交接 | 本次会话所有产出 | `session.handoff`（下游 Worker 需要知道的信息） | DISPATCH |

**关键约束：**
- Coordinator 是 `structured_write` → 可以写入 `owned_outputs`
- 产出写入 `runtime/projects/<project_id>/`（长期上下文）
- 必须产出可追溯、结构化、能被下游 HTML/Manim/SVG Worker 直接消费的内容

**实现策略：**
Coordinator 是第一个有"写入权"的 Agent。它汇总 Explorer 的发现和 Planner 的建议，生成最终的讲解脚本和分镜表。Coordinator 的输出是下游 Worker 的输入，因此格式必须严格结构化。

---

## 四、团队分工（9 人）

### 角色与对应关系

```
Lead（1人）
  ├── 总体架构 + BaseAgent 接口 + 集成联调 + 代码审查
  │
  ├── 输入摄取组（2 人）
  │   ├── A1：PDF 读取 + Markdown 读取
  │   └── A2：参考资产扫描 + 环境检测报告生成
  │
  ├── Explorer Agent 组（2 人）
  │   ├── B1：Explorer 主逻辑 + LLM prompt 模板
  │   └── B2：上下文读写工具（memory/context_io.py）
  │
  ├── Planner Agent 组（2 人）
  │   ├── C1：Planner 主逻辑 + 约束分析 prompt 模板
  │   └── C2：LLM 客户端封装（llm/client.py）
  │
  └── Coordinator Agent 组（2 人）
      ├── D1：Coordinator 主逻辑 + 讲解脚本 prompt 模板
      └── D2：分镜/分发 prompt 模板 + 输出格式校验
```


### 详细任务分配（仅供参考）
#### Lead— 架构 + 基座 + 集成

| 序号 | 任务 | 产出物 |
|:---|:---|:---|
| L1 | 定义 `BaseAgent` 抽象接口（含 `run()` 生命周期） | `src/manimind/agents/base.py` |
| L2 | 定义 Agent 间数据协议（Explorer→Planner→Coordinator 传递格式） | `docs/agent-data-protocol.md` |
| L3 | 新增 CLI 命令 `agent-run <manifest> <role_id> --stage <stage>` | 修改 `src/manimind/main.py` |
| L4 | 新增 API 端点 `POST /api/projects/agents/run` | 修改 `backend/api/` |
| L5 | 编写集成测试（三 Agent 串联跑通 pipeline.example.json） | `tests/test_agent_integration.py` |
| L6 | 代码审查：每个子团队的 PR 至少审一轮 | — |

#### 输入摄取组（2 人：A1, A2）

| 序号 | 负责人 | 任务 | 产出物 |
|:---|:---|:---|:---|
| A1-1 | A1 | PDF 文本提取器（基于 `pypdf`，处理编码、公式混排） | `src/manimind/ingest/pdf_reader.py` |
| A1-2 | A1 | Markdown 笔记读取器（解析 YAML front matter + 正文） | `src/manimind/ingest/markdown_reader.py` |
| A1-3 | A1 | `ingest/__init__.py` + 统一入口 `load_source_bundle()` | `src/manimind/ingest/__init__.py` |
| A2-1 | A2 | 参考资产扫描器（遍历 `resources/` 生成可用组件清单） | `src/manimind/ingest/asset_scanner.py` |
| A2-2 | A2 | 环境检测报告生成器（复用 `bootstrap.check_tools()` 生成可读报告） | `src/manimind/ingest/env_reporter.py` |
| A2-3 | A2 | 为输入摄取组写单元测试 | `tests/test_ingest.py` |

> **依赖**：需要先安装 `pypdf`（已在 `pyproject.toml` 的 `[project.optional-dependencies].pdf` 中定义）

#### Explorer Agent 组（2 人：B1, B2）

| 序号 | 负责人 | 任务 | 产出物 |
|:---|:---|:---|:---|
| B1-1 | B1 | Explorer prompt 模板（PRESTART / INGEST / SUMMARIZE 三阶段） | `src/manimind/llm/templates/explorer.py` |
| B1-2 | B1 | Explorer Agent 主类 `ExplorerAgent(BaseAgent)` | `src/manimind/agents/explorer.py` |
| B1-3 | B1 | Explorer 输出解析器（从 LLM 响应中提取结构化发现） | `src/manimind/agents/explorer.py` |
| B2-1 | B2 | 上下文读取器（从 `runtime/projects/` 和 `runtime/sessions/` 读上下文正文） | `src/manimind/memory/context_io.py` |
| B2-2 | B2 | 上下文写入器（原子写入上下文正文到正确路径，校验 scope 权限） | `src/manimind/memory/context_io.py` |
| B2-3 | B2 | Explorer 组单元测试 | `tests/test_explorer.py` |

> **依赖**：A1, A2 先完成（Explorer 需要读取 PDF/笔记/资产扫描结果）

#### Planner Agent 组（2 人：C1, C2）

| 序号 | 负责人 | 任务 | 产出物 |
|:---|:---|:---|:---|
| C2-1 | C2 | LLM 客户端封装（OpenAI 兼容接口，支持 .env 配置、重试、超时） | `src/manimind/llm/client.py` |
| C2-2 | C2 | `llm/__init__.py` + 统一配置加载 | `src/manimind/llm/__init__.py` |
| C1-1 | C1 | Planner prompt 模板（SUMMARIZE / PLAN 两阶段，含约束分析框架） | `src/manimind/llm/templates/planner.py` |
| C1-2 | C1 | Planner Agent 主类 `PlannerAgent(BaseAgent)` | `src/manimind/agents/planner.py` |
| C1-3 | C1 | Planner 输出解析器（提取约束清单、分镜建议、可行性评估） | `src/manimind/agents/planner.py` |
| C1-4 | C1 | Planner 组单元测试 | `tests/test_planner.py` |

> **依赖**：C2 先完成（LLM 客户端是 C1 和 Coordinator 组的前置依赖）。B 组的 context_io 先完成（Planner 需要读取 Explorer 的发现）

#### Coordinator Agent 组（2 人：D1, D2）

| 序号 | 负责人 | 任务 | 产出物 |
|:---|:---|:---|:---|
| D1-1 | D1 | Coordinator prompt 模板（PLAN 阶段：讲解脚本 + 分镜） | `src/manimind/llm/templates/coordinator.py` |
| D1-2 | D1 | Coordinator Agent 主类 `CoordinatorAgent(BaseAgent)` | `src/manimind/agents/coordinator.py` |
| D1-3 | D1 | Coordinator PLAN 阶段输出解析器 | `src/manimind/agents/coordinator.py` |
| D2-1 | D2 | Coordinator DISPATCH 阶段 prompt 模板（任务分发 + 会话交接） | `src/manimind/llm/templates/coordinator.py` |
| D2-2 | D2 | Coordinator DISPATCH 阶段输出解析器 + 输出格式校验 | `src/manimind/agents/coordinator.py` |
| D2-3 | D2 | Coordinator 组单元测试 | `tests/test_coordinator.py` |

> **依赖**：C2（LLM 客户端）、B2（context_io）、C1（Planner 建议格式）先完成

---

## 五、新建目录与文件清单

```
src/manimind/
├── agents/                          # 新建
│   ├── __init__.py                  # 导出所有 Agent 类
│   ├── base.py                      # BaseAgent 抽象基类
│   ├── explorer.py                  # ExplorerAgent
│   ├── planner.py                   # PlannerAgent
│   ├── coordinator.py               # CoordinatorAgent
│   └── orchestrator.py             # 三 Agent 串联编排器（可选，第二阶段）
├── ingest/                          # 新建
│   ├── __init__.py                  # load_source_bundle() 统一入口
│   ├── pdf_reader.py               # PDF 文本提取
│   ├── markdown_reader.py          # Markdown 笔记读取
│   ├── asset_scanner.py            # resources/ 资产发现
│   └── env_reporter.py             # 环境检测报告
├── llm/                             # 新建
│   ├── __init__.py                  # 导出 LlmClient + 配置
│   ├── client.py                    # OpenAI 兼容 LLM 客户端
│   └── templates/                   # 新建
│       ├── __init__.py
│       ├── explorer.py             # Explorer 各阶段 prompt 模板
│       ├── planner.py              # Planner 各阶段 prompt 模板
│       └── coordinator.py          # Coordinator 各阶段 prompt 模板
├── memory/                          # 新建
│   ├── __init__.py                  # 导出 context_reader / context_writer
│   └── context_io.py               # 上下文读 / 写 / 校验
├── main.py                          # 修改：新增 agent-run 命令
└── __init__.py                      # 修改：导出新模块

backend/
└── api/
    └── agents.py                    # 新建：Agent 运行 API 端点

tests/
├── test_ingest.py                   # 新建
├── test_explorer.py                 # 新建
├── test_planner.py                  # 新建
├── test_coordinator.py             # 新建
└── test_agent_integration.py       # 新建
```

---

## 六、实施顺序与阶段划分

### 阶段 0：前置准备（Lead + 全队，1 天）

```
任务：
  L1: BaseAgent 接口定义
  L2: Agent 间数据协议文档
  L3: 新建目录结构 + __init__.py 骨架

产出检查：
  - BaseAgent 抽象类通过 mypy 类型检查
  - 数据协议文档全队确认无歧义
  - 空目录 + __init__.py 可正常 import
```

### 阶段 1：基础设施并行（第 2-4 天）

```
输入摄取组（A1, A2）：
  ├─ pdf_reader.py + markdown_reader.py
  ├─ asset_scanner.py + env_reporter.py
  └─ 单元测试

LLM 封装（C2）：
  ├─ client.py（OpenAI 兼容接口）
  └─ 单元测试

上下文 IO（B2）：
  ├─ context_io.py（读 / 写 / 校验）
  └─ 单元测试
```

**此阶段不依赖其他组，三组完全并行。**

### 阶段 2：Agent 核心逻辑（第 5-8 天）

```
Explorer 组（B1, B2）：
  ├─ explorer prompt 模板
  ├─ ExplorerAgent 主类
  ├─ 输出解析器
  └─ 单元测试

Planner 组（C1, C2）：
  ├─ planner prompt 模板
  ├─ PlannerAgent 主类
  ├─ 输出解析器
  └─ 单元测试

Coordinator 组（D1, D2）：
  ├─ coordinator prompt 模板（PLAN + DISPATCH）
  ├─ CoordinatorAgent 主类
  ├─ 输出解析器 + 格式校验
  └─ 单元测试
```

**Explorer 和 Planner 可并行。Coordinator 依赖 Planner 的建议格式已确定（由 L2 数据协议文档保证），因此也可并行。**

### 阶段 3：CLI/API 接入 + 集成（第 9 天）

```
Lead（L3, L4, L5）：
  ├─ CLI 命令 agent-run
  ├─ API 端点 POST /api/projects/agents/run
  ├─ orchestrator.py（三 Agent 串联）
  └─ 集成测试

全队：
  └─ 各自修复集成测试中发现的问题
```

### 阶段 4：端到端验证（第 10 天）

```
全队：
  1. 用 pipeline.example.json 跑完整流程
  2. 验证 runtime 落盘正确
  3. 验证审核关卡逻辑
  4. 补充文档
```

---

## 七、关键技术决策

### 7.1 Agent 间数据协议

三个 Agent 不直接通信，而是通过 **runtime 文件系统** 交换数据：

```
Explorer 产出 → runtime/sessions/<session_id>/explorer-findings/
    ├── research-summary-draft.md
    ├── glossary-draft.json
    └── formula-catalog-draft.json

Planner 产出 → runtime/sessions/<session_id>/planner-suggestions/
    ├── constraint-analysis.json
    └── storyboard-suggestions.json

Coordinator 产出 → runtime/projects/<project_id>/
    ├── narration-script.json      （长期上下文，key=project_id.narration.script）
    ├── storyboard-master.json     （长期上下文，key=project_id.storyboard.master）
    └── session-handoff.json       （短期上下文，key=project_id.session.handoff）
```

**为什么用文件而非内存传递？**
- 与当前 `runtime_store.py` 的设计一致
- 任意 Agent 可在任意时间恢复上下文
- 所有交换均有 JSONL 审计日志可追溯
- 符合"编排层不持有隐式全局状态"的约束

### 7.2 LLM 调用策略

```python
# src/manimind/llm/client.py
class LlmClient:
    """基于 .env 配置的 LLM 客户端。
    - OPENAI_API_KEY / OPENAI_BASE_URL：兼容任何 OpenAI 接口服务
    - MANIMIND_MODEL：指定模型名（默认 gpt-4o）
    """

    def chat(
        self,
        system_prompt: str,
        user_message: str,
        *,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> str:
        ...

    def chat_structured(
        self,
        system_prompt: str,
        user_message: str,
        output_schema: dict,  # JSON Schema 约束输出格式
    ) -> dict:
        ...
```

**关键约束：**
- 支持 `.env` 配置，不硬编码 API key
- `chat_structured` 用于 Coordinator（需要严格的 JSON 输出格式）
- 所有 LLM 调用记录 prompt + response 到 session audit log

### 7.3 read_only Agent 的输出通道

Explorer 和 Planner 是 read_only 模式，不能写 `owned_outputs`。它们的输出通过以下方式传递：

1. **写入短期上下文**：`runtime/sessions/<session_id>/explorer-findings/` 和 `planner-suggestions/`
2. **作为 Lead/Coordinator 的输入**：Coordinator 在构建 prompt 时，会从短期上下文中读取 Explorer 和 Planner 的产出
3. **在 CLI 中回显**：`agent-run` 命令将 read_only 产出直接打印到 stdout

### 7.4 优雅降级

- **PDF 不存在时**：Explorer 不崩溃，而是标记 `paper_unavailable: true`，仅基于笔记和资产扫描生成报告
- **LLM 不可用时**：Agent 输出空结果 + 错误标记，不阻塞 pipeline
- **资源目录为空时**：资产扫描器返回空清单，不报错

---

## 八、各 Agent 的 Prompt 模板结构（仅参考）

### Explorer — INGEST 阶段

```
System: {context_packet 中的角色、约束、可用上下文}

User:
你是一个数学科普项目的资料探索 Agent。请阅读以下内容并完成探索任务。

## 输入材料

### 论文
{paper_text 或 "（论文文件未找到，请基于笔记分析）"}

### 笔记
{notes_text}

### 可用资产
{asset_list}

## 任务
1. 提取论文的核心数学概念（5-10 个）
2. 识别论文中的关键公式（逐个列出 LaTeX 表达式与含义）
3. 评估受众适配难度
4. 列出可用于动画表现的视觉元素建议
5. 标记论文中需要简化的部分

请用以下 JSON 格式输出：
{...}
```

### Planner — SUMMARIZE 阶段

```
System: {context_packet}

User:
你是一个数学科普项目的方案规划 Agent。请基于已有的研究总结，分析约束并提出建议。

## 研究总结
{research_summary_draft}

## 术语表
{glossary_draft}

## 公式目录
{formula_catalog_draft}

## 任务
1. 分析数学难度与受众的匹配度
2. 估算每个镜头所需的最短时长
3. 标注哪些概念适合 HTML 动画、哪些需要 Manim 数学动画
4. 标记潜在风险点

请用以下 JSON 格式输出：
{...}
```

### Coordinator — PLAN 阶段

```
System: {context_packet}

User:
你是一个数学科普项目的协调 Agent。请基于研究总结和规划建议，生成讲解脚本和分镜表。

## 研究总结
{research_summary}

## 规划建议
{planner_suggestions}

## 镜头清单
{segments}

## 任务
1. 为每个镜头写讲解词（口语化，适合配音）
2. 确定每个镜头的 modality（html/manim/hybrid/svg）
3. 列出每个镜头的公式、动画备注、预计时长
4. 生成完整分镜表

请用以下 JSON 格式输出：
{...}
```

---

## 九、风险与应对

| 风险 | 概率 | 影响 | 应对 |
|:---|:---|:---|:---|
| LLM API 不可用或限流 | 中 | 高 | `chat_structured` 加重试；支持本地模型（Ollama 兼容） |
| PDF 公式无法正确提取 | 高 | 中 | 降级为"提示用户手动输入公式"；保留 PDF 原始文本供人工对照 |
| 三 Agent 串联时上下文断裂 | 中 | 高 | 数据协议文档先行（L2），所有传递字段严格 schema 约束 |
| 9 人并行开发导致合并冲突 | 中 | 中 | 各组独立目录 + 接口先行（阶段 0 定义完所有抽象类和协议） |
| Coordinator 输出格式下游 Worker 无法消费 | 中 | 高 | `output_schema` JSON Schema 校验 + D2 的格式校验器 |
| 现有 14 个测试被破坏 | 低 | 中 | 每个阶段跑 `pytest`，CI 化（后续） |

---

## 十、检查清单

### 阶段 0 完成标志
- [ ] `BaseAgent` 抽象类可 import，定义清晰
- [ ] 数据协议文档全队确认
- [ ] 新目录结构创建完毕

### 阶段 1 完成标志
- [ ] `load_source_bundle()` 可返回 PDF 文本 + 笔记内容
- [ ] `AssetScanner.scan()` 可返回 `resources/` 组件清单
- [ ] `LlmClient.chat()` 可成功调用 LLM 并返回响应
- [ ] `context_io.read()` / `context_io.write()` 可读写 runtime 目录

### 阶段 2 完成标志
- [ ] `ExplorerAgent.run(PipelineStage.INGEST)` 可输出研究发现
- [ ] `PlannerAgent.run(PipelineStage.SUMMARIZE)` 可输出约束分析
- [ ] `CoordinatorAgent.run(PipelineStage.PLAN)` 可输出讲解脚本和分镜表

### 阶段 3 完成标志
- [ ] `python -m manimind agent-run pipeline.example.json explorer --stage ingest` 可正常运行
- [ ] `POST /api/projects/agents/run` 返回正确结果
- [ ] 三 Agent 按 Explorer→Planner→Coordinator 顺序串联成功

### 阶段 4 完成标志
- [ ] 完整流程产物落盘到 `runtime/projects/` 和 `runtime/sessions/`
- [ ] `events.jsonl` 完整记录所有 Agent 调用
- [ ] 14 + 新增测试全部通过

---

## 十一、GitHub 成员协作更新使用说明（仅参考！！！）

### 11.1 仓库分支策略

```
main（主分支，受保护）
  └── develop（开发主分支）
        ├── feature/runtime-closure       (Lead + Team A)
        ├── feature/ingest                 (Team A1/A2 - 输入摄取组)
        ├── feature/explorer-agent        (Team B1/B2 - Explorer组)
        ├── feature/planner-agent         (Team C1/C2 - Planner组)
        ├── feature/coordinator-agent     (Team D1/D2 - Coordinator组)
        └── feature/agents-base           (Lead - BaseAgent接口)
```

### 11.2 Git 协作流程（每个人的日常）

#### 第一步：初始化本地仓库（仅第一次）

```bash
# 克隆仓库
git clone <GitHub仓库地址>
cd ManiMind

# 配置用户名和邮箱
git config user.name "你的名字"
git config user.email "你的邮箱@example.com"

# 查看所有分支
git branch -a
```

#### 第二步：从 develop 创建你的功能分支

```bash
# 确保本地 develop 是最新的
git checkout develop
git pull origin develop

# 创建你的功能分支（替换为你的分支名）
git checkout -b feature/你的分支名
```

#### 第三步：日常开发与提交

```bash
# 查看当前状态
git status

# 添加修改的文件
git add .

# 提交（使用有意义的提交信息）
git commit -m "feat: 完成 PDF 读取器基础功能"
# 或者
git commit -m "fix: 修复 Markdown 解析中的编码问题"
# 或者
git commit -m "docs: 更新团队协作说明"

# 推送到远程仓库
git push origin feature/你的分支名
```

**提交信息规范：**
- `feat:` 新功能
- `fix:` 修复 Bug
- `docs:` 文档更新
- `test:` 测试相关
- `refactor:` 重构
- `chore:` 构建/工具相关

#### 第四步：创建 Pull Request (PR)

1. 在 GitHub 网页上，进入你的仓库
2. 点击 "Pull requests" → "New pull request"
3. 选择 `base: develop` ← `compare: feature/你的分支名`
4. 填写 PR 标题和描述：
   ```
   标题：[Team A] 完成 PDF 读取器实现
   
   描述：
   - 实现 pdf_reader.py，支持基本 PDF 文本提取
   - 添加单元测试 test_ingest.py
   - 处理了编码问题和公式混排场景
   
   关联任务：A1-1, A1-2
   审查人：@Lead的GitHub用户名
   ```
5. 点击 "Create pull request"

#### 第五步：代码审查与修改

1. 等待 Lead 或其他成员审查
2. 如果有修改建议，在本地修改后提交：
   ```bash
   git add .
   git commit -m "fix: 根据审查意见修改 PDF 解析逻辑"
   git push origin feature/你的分支名
   ```
3. PR 会自动更新

#### 第六步：合并到 develop

1. 审查通过后，由 Lead 或指定人员点击 "Merge pull request"
2. 选择 "Squash and merge"（把多个提交合并为一个）
3. 删除远程功能分支

### 11.3 各团队分支命名规范

| 团队 | 分支命名示例 | 负责人 |
|:---|:---|:---|
| Lead | `feature/agents-base`, `feature/cli-api` | @lead |
| 输入摄取组 | `feature/ingest-pdf`, `feature/ingest-markdown` | @A1, @A2 |
| Explorer组 | `feature/explorer-agent`, `feature/context-io` | @B1, @B2 |
| Planner组 | `feature/planner-agent`, `feature/llm-client` | @C1, @C2 |
| Coordinator组 | `feature/coordinator-agent`, `feature/output-validation` | @D1, @D2 |

### 11.4 同步最新代码（重要！）

**在开始每天的工作前，务必同步最新代码：**

```bash
# 切换到 develop
git checkout develop

# 拉取最新代码
git pull origin develop

# 切换回你的功能分支
git checkout feature/你的分支名

# 合并最新的 develop 到你的分支
git merge develop

# 如果有冲突，解决冲突后：
git add .
git commit -m "merge: 同步最新 develop 分支"
git push origin feature/你的分支名
```

### 11.5 解决冲突

如果 `git merge develop` 出现冲突：

1. Git 会标记冲突的文件，打开这些文件
2. 找到 `<<<<<<< HEAD` 和 `>>>>>>> develop` 之间的内容
3. 手动编辑，保留需要的代码，删除标记
4. 保存文件
5. 执行 `git add .` 和 `git commit`

### 11.6 日常协作建议

#### 每日
- 推送到远程你今天完成的代码
- 同步最新的 develop 分支
- 告诉大家：昨天做了什么？今天要做什么？遇到什么问题？

#### 代码提交频率
- **至少每天一次**：不要等所有功能都做完才提交
- 小步提交：每个小功能点完成就提交一次
- 提交前确保：代码可以编译/运行，测试通过

#### PR 审查流程
- **PR 创建后**：在群里 @ 审查人
- **审查时限**：尽量在 24 小时内完成审查
- **审查意见**：使用 GitHub 的 "Review changes" 功能，逐行评论
- **合并时机**：至少 1 人批准后才能合并

#### 临时同步代码
如果需要同步队友未合并的代码用于测试：
```bash
# 添加队友的远程仓库（如果需要）
git remote add teammate <队友的仓库地址>

# 拉取队友的分支
git fetch teammate
git checkout -b teammate-feature teammate/feature/队友分支名
```

### 11.7 GitHub Issues 管理

- **Bug 报告**：发现 Bug 时创建 Issue，标签：`bug`
- **功能建议**：标签：`enhancement`
- **任务追踪**：每个任务可以创建一个 Issue，分配给对应的人
- **问题讨论**：遇到技术问题可以在 Issue 中讨论

### 11.8 保护 main 分支

- main 分支设为保护分支，不允许直接推送
- 必须通过 PR 合并，且至少 1 人审查通过
- 合并前要求 CI 测试通过（后续配置）

### 11.9 快速参考命令

```bash
# 查看当前分支
git branch

# 查看修改
git diff

# 查看提交历史
git log --oneline --graph

# 撤销本地未提交的修改
git checkout -- 文件名

# 撤销最后一次提交（保留修改）
git reset --soft HEAD~1

# 暂存当前修改（用于切换分支前）
git stash
# 恢复暂存
git stash pop
```

---

## 十二、快速开始（新成员）

### 1. 环境准备
```bash
# 克隆仓库
git clone <仓库地址>
cd ManiMind

# 安装依赖
pip install -e ".[api,dev,pdf]"

# 运行初始化脚本
powershell -ExecutionPolicy Bypass -File .\scripts\init-workspace.ps1

# 跑测试，确保环境正常
pytest
```

### 2. 配置 Git
```bash
git config user.name "你的名字"
git config user.email "你的邮箱"
```

### 3. 创建你的第一个分支
```bash
git checkout develop
git pull origin develop
git checkout -b feature/你的分支名
```

### 4. 开始开发！

祝你协作愉快！🎉
