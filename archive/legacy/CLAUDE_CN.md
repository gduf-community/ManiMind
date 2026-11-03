# CLAUDE_CN.md

本文件为 Claude Code (claude.ai/code) 在处理此仓库代码时提供指导。

## 项目概述

ManiMind 是一个面向数学科普动画生产的多 Agent 编排层。输入：论文 + 笔记。输出：讲解脚本、分镜、Manim 数学动画、HTML 科普片段，以及用于配音/字幕/编辑阶段的结构化资产。

本仓库仅为**编排层**——它不重新实现渲染引擎（Manim、HyperFrames、HTML 动画）。外部渲染能力位于 `resources/skills/` 和 `resources/references/` 下。

## 构建与测试命令

```bash
# 安装核心 + API + 开发依赖
pip install -e ".[api,dev]"

# 运行所有测试（testpaths = tests, pythonpath = src）
pytest

# 运行单个测试文件
pytest tests/test_workflow.py

# 运行 FastAPI 服务器
uvicorn backend.main:app --reload

# CLI 入口点
python -m manimind <command>
```

PowerShell 脚本（仅 Windows 初始化）：
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\init-workspace.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\sync-thirdparty-assets.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\check-prerequisites.ps1
```

## 架构：9 阶段流水线

`prestart → ingest → summarize → plan → dispatch → review → post_produce → package → done`

**阶段由任务状态驱动**，而非显式的阶段转换。`runtime.py:derive_current_stage()` 根据哪个 `ExecutionTask` 处于 `IN_PROGRESS` / `COMPLETED` 来推断当前阶段。

## Agent 角色与模式

在 `workflow.py:build_agent_profiles()` 中定义。每个角色都有一个 `AgentMode`：

| 角色 | 模式 | 职责 |
|------|------|------|
| `lead` | structured_write | 全局状态、阶段转换、资产清单 |
| `explorer` | read_only | 搜索论文/代码/资产以寻找模式 |
| `planner` | read_only | 约束分析、分镜建议 |
| `coordinator` | structured_write | 讲解脚本、分镜、任务分发 |
| `html_worker` | structured_write | HTML 科普片段 |
| `manim_worker` | structured_write | Manim 数学动画片段 |
| `svg_worker` | structured_write | SVG 动效片段 |
| `reviewer` | verify_only | 基于证据的审核、后处理前的关卡 |

**审核者是硬关卡**：在 `review.outputs` 完成之前，`review` 之后的任务都无法开始。

## 上下文系统：长期 vs 短期

- **长期**（`runtime/projects/<project_id>/`）：项目生命周期记录——研究总结、术语表、公式目录、风格指南、讲解脚本、分镜、审核报告。`sticky=True` 的记录会自动包含给所有角色。
- **短期**（`runtime/sessions/<session_id>/`）：每次会话的交接与协调。会话范围，会话结束时失效。

每个 `ContextRecord` 声明：写入者、消费者、生命周期、失效规则。`context_assembly.py:build_context_packet()` 通过交叉角色的模式默认值、必需输入和角色的消费者权限，来装配角色+阶段特定的上下文包。

## 核心模块（`src/manimind/`）

- **`models.py`**：所有数据类和枚举。纯数据——除了 `to_dict()` 之外没有行为。
- **`workflow.py`**：从清单构建完整的 `ProjectPlan`。包含上下文蓝图、工作任务生成（由 `SegmentModality` 驱动）、Agent 配置文件、执行任务 DAG 和审核检查点。
- **`task_board.py`**：执行任务状态机。强制仅所有者可写入，推进前需解决阻塞。当所有审核前任务都完成但审核尚未开始时，返回 `verification_nudge_needed=True`。
- **`runtime.py`**：加载持久化快照，将其应用于内存中的 `ProjectPlan`，推导当前阶段。
- **`runtime_store.py`**：持久化层。原子写入（先写入临时文件再 `os.replace`），每次变更的 JSONL 审计日志。同时写入项目级和会话级目录。
- **`context_assembly.py`**：上下文包构建器 + 提示词分段缓存（避免重建相同的提示词段）。
- **`bootstrap.py`**：工作区目录创建、工具链检测（`python`、`node`、`bun`、`ffmpeg`、`manim`）、运行时布局路径生成。

## 后端 API（`backend/`）

`src/manimind/` 之上的轻量 FastAPI 封装。路由：
- `POST /api/projects/plan` — 从清单创建项目计划
- `GET /api/projects/{project_id}/runtime` — 读取运行时快照
- `POST /api/projects/tasks` — 列出执行任务
- `POST /api/projects/tasks/update` — 推进任务状态
- `POST /api/projects/context-pack` — 生成角色+阶段上下文包

## 清单格式

参见 `configs/pipeline.example.json`。清单定义 `project_id`、`title`、`source_bundle`（paper_path、note_paths、audience、style_refs）和 `segments`（每个都有 id、title、goal、narration、modality、formulas 等）。

## 关键不变量

- 永远不要将长期和短期上下文合并到同一个文件或路径中。
- 永远不要跳过审核关卡——审核通过前不进行后处理。
- 多 Agent 协调没有隐式全局状态。
- 所有持久化状态必须通过 `runtime_store.py` 中的原子写入。
- 本仓库仅为编排层——不要重新实现 `resources/` 中的渲染逻辑。
- 模块边界、角色、状态路径或上下文装配的结构性变更必须更新 `docs/architecture.canvas` 和 `docs/通用项目架构模板.md`。
