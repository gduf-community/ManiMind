# Coordinator 组 Phase 1 工作交付报告

**日期**: 2026-05-10
**团队**: Coordinator 组 (D1, D2)
**阶段**: Phase 1 — Agent 核心逻辑
**状态**: 已完成

---

## 一、交付清单

| 编号 | 任务 | 文件 | 行数 |
|------|------|------|------|
| D1-1 | PLAN 阶段 prompt 模板 | `src/manimind/llm/templates/coordinator.py` | 314 |
| D1-2 | CoordinatorAgent 主类 | `src/manimind/agents/coordinator.py` | 225 |
| D1-3 | PLAN 阶段输出解析/校验 | `src/manimind/agents/coordinator.py` (同文件) | — |
| D2-1 | DISPATCH 阶段 prompt 模板 | `src/manimind/llm/templates/coordinator.py` (同文件) | — |
| D2-2 | DISPATCH 阶段输出校验 | `src/manimind/agents/coordinator.py` (同文件) | — |
| D2-3 | 单元测试 | `tests/test_coordinator.py` | 435 |

---

## 二、模块设计

### 2.1 CoordinatorAgent (`agents/coordinator.py`)

继承 `BaseAgent`，`role_id = "coordinator"`。是项目中**第一个有写入权**的 Agent（`structured_write` 模式）。

#### 主入口：`run(stage, task_id) -> dict`

```
stage=PLAN        → _run_plan()
stage=DISPATCH    → _run_dispatch()
其他阶段           → {"success": False, "error": "..."}
```

#### PLAN 阶段流程

```
1. _read_context("<pid>.research.summary")      ← Explorer 产出（短期上下文）
2. _read_context("planner.constraint.analysis")  ← Planner 产出（短期上下文）
3. _read_context("planner.storyboard.suggestions")
4. segments = [s.to_dict() for s in self.plan.segments]
5. build_plan_user_message(segments, research_summary, planner_suggestions)
6. build_system_prompt(PLAN) → "\n".join(...)
7. llm_client.chat_structured(system_prompt, user_message, PLAN_OUTPUT_SCHEMA)
8. _validate_plan_output(result)  → 字段校验 + narration/storyboard 一致性
9. _write_context(narration.script, ..., LONG_TERM)
10. _write_context(storyboard.master, ..., LONG_TERM)
```

**上游数据缺失时的降级**：如果 Explorer/Planner 未产出，`research_summary` 和 `planner_suggestions` 为 `None`，prompt 模板自动跳过对应段落，LLM 仅基于 manifest segments 生成。

#### DISPATCH 阶段流程

```
1. _read_context("<pid>.storyboard.master")  ← PLAN 阶段产出（长期上下文）
2. build_dispatch_user_message(storyboard, segments)
3. llm_client.chat_structured(..., DISPATCH_OUTPUT_SCHEMA)
4. _validate_dispatch_output(result)  → 非空校验
5. _write_context(session.handoff, ..., SHORT_TERM)
```

### 2.2 Prompt 模板 (`llm/templates/coordinator.py`)

两个用户消息构建函数 + 5 套 JSON Schema：

| 符号 | 用途 |
|------|------|
| `build_plan_user_message()` | 注入 segments + 上游数据，5 步骤指令 |
| `build_dispatch_user_message()` | 注入 storyboard + segments，5 步骤指令 |
| `NARRATION_SCRIPT_SCHEMA` | 讲解脚本 JSON Schema（OpenAI strict 模式兼容） |
| `STORYBOARD_MASTER_SCHEMA` | 分镜主表 JSON Schema |
| `SESSION_HANDOFF_SCHEMA` | 会话交接 JSON Schema |
| `PLAN_OUTPUT_SCHEMA` | 聚合 narration + storyboard |
| `DISPATCH_OUTPUT_SCHEMA` | 聚合 task_assignments + session_handoff |

所有 Schema 均设置 `additionalProperties: False`，用于 `chat_structured` 的 `response_format.json_schema` 严格模式。

### 2.3 输出校验器 (`agents/coordinator.py` 底部)

两个独立函数（可被其他模块直接导入）：

- **`_validate_plan_output(result) -> list[str]`**:
  - `narration_script` 必须为 dict 且 segments 非空
  - `storyboard_master` 必须为 dict 且 segments 非空
  - 交叉校验：narration 和 storyboard 的 `segment_id` 集合必须一致，不一致时报告具体缺失

- **`_validate_dispatch_output(result) -> list[str]`**:
  - `task_assignments` 必须为非空数组
  - `session_handoff` 必须为 dict

---

## 三、测试方法

### 3.1 测试策略

采用**单元测试 + 接口隔离**策略。CoordinatorAgent 依赖两个外部接口：

| 依赖 | 接口 | 提供方 | 测试策略 |
|------|------|--------|----------|
| LLM 调用 | `LlmClientProtocol` | Planner 组 C2 | **Mock** — `MockLlmClient` 实现协议，预设返回值 |
| 上下文读写 | `BaseAgent._read_context / _write_context` | Lead (Phase 0) | **真实调用** — BaseAgent 已实现完整的文件系统读写 |

### 3.2 MockLlmClient 设计

```python
class MockLlmClient:
    def __init__(self, chat_response="", structured_response=None):
        self.calls: list[dict] = []        # 记录每次调用参数

    def chat(self, system_prompt, user_message, ...) -> str:
        self.calls.append({...})           # 记录调用
        return self.chat_response          # 返回预设文本

    def chat_structured(self, system_prompt, user_message, output_schema) -> dict:
        self.calls.append({...})           # 记录调用（含 output_schema）
        return self.structured_response    # 返回预设 JSON
```

**验证维度**：
1. **返回值正确性** — `result["success"]`、`result["outputs"]`、`result["segment_count"]`
2. **LLM 调用参数** — 检查 `mock_llm.calls[0]["user_message"]` 是否包含 segments
3. **落盘正确性** — 调用真实的 `agent._read_context()` 验证写入的长期/短期上下文

### 3.3 测试用例清单（17 个）

#### PLAN 阶段 (4)

| 测试 | 场景 | 预期 |
|------|------|------|
| `test_plan_stage_success` | 正常输入（2 个 segments） | `success=True`, outputs 含 narration + storyboard, segment_count=2, 上下文已落盘 |
| `test_plan_stage_with_upstream_context` | 模拟上游 Explorer 已写入研究总结 | 成功读取并注入 prompt |
| `test_plan_stage_no_llm_client` | `llm_client=None` | `success=False`, `error="llm_unavailable"` |
| `test_plan_stage_validation_error` | LLM 返回空 segments | `success=False`, `error="validation_failed"`, 2+ 条错误 |

#### DISPATCH 阶段 (3)

| 测试 | 场景 | 预期 |
|------|------|------|
| `test_dispatch_stage_success` | 预先写入 storyboard.master（模拟 PLAN 产出） | `success=True`, outputs 含 session.handoff, assigned_count=2 |
| `test_dispatch_stage_no_llm_client` | `llm_client=None` | `success=False`, `error="llm_unavailable"` |
| `test_dispatch_stage_validation_error` | LLM 返回空数组 + 空对象 | `success=False`, `error="validation_failed"` |

#### 边界情况 (2)

| 测试 | 场景 | 预期 |
|------|------|------|
| `test_unsupported_stage` | `stage=REVIEW` | `success=False`, error 含 "does not support" |
| `test_mode_is_structured_write` | 检查 AgentMode | `agent.mode == STRUCTURED_WRITE` |
| `test_profile_auto_resolved` | Profile 自动匹配 | `profile.id == "coordinator"`, PLAN/DISPATCH 在 allowed_stages 中 |

#### 输出校验器 (7)

| 测试 | 函数 | 输入 | 预期 |
|------|------|------|------|
| `test_validate_plan_output_valid` | `_validate_plan_output` | 合法输出 | `[]` |
| `test_validate_plan_output_empty_narration` | `_validate_plan_output` | narration.segments=[] | 1 条错误 |
| `test_validate_plan_output_empty_storyboard` | `_validate_plan_output` | storyboard.segments=[] | 1 条错误 |
| `test_validate_plan_output_mismatched_segments` | `_validate_plan_output` | narration 多一个 seg-extra | 1 条错误，含 "missing from storyboard_master" |
| `test_validate_dispatch_output_valid` | `_validate_dispatch_output` | 合法输出 | `[]` |
| `test_validate_dispatch_output_empty_assignments` | `_validate_dispatch_output` | task_assignments=[] | 1 条错误 |
| `test_validate_dispatch_output_missing_handoff` | `_validate_dispatch_output` | session_handoff=None | 1 条错误 |

### 3.4 运行结果

```
tests/test_coordinator.py::test_plan_stage_success PASSED
tests/test_coordinator.py::test_plan_stage_with_upstream_context PASSED
tests/test_coordinator.py::test_plan_stage_no_llm_client PASSED
tests/test_coordinator.py::test_plan_stage_validation_error PASSED
tests/test_coordinator.py::test_dispatch_stage_success PASSED
tests/test_coordinator.py::test_dispatch_stage_no_llm_client PASSED
tests/test_coordinator.py::test_dispatch_stage_validation_error PASSED
tests/test_coordinator.py::test_unsupported_stage PASSED
tests/test_coordinator.py::test_mode_is_structured_write PASSED
tests/test_coordinator.py::test_profile_auto_resolved PASSED
tests/test_coordinator.py::test_validate_plan_output_valid PASSED
tests/test_coordinator.py::test_validate_plan_output_empty_narration PASSED
tests/test_coordinator.py::test_validate_plan_output_empty_storyboard PASSED
tests/test_coordinator.py::test_validate_plan_output_mismatched_segments PASSED
tests/test_coordinator.py::test_validate_dispatch_output_valid PASSED
tests/test_coordinator.py::test_validate_dispatch_output_empty_assignments PASSED
tests/test_coordinator.py::test_validate_dispatch_output_missing_handoff PASSED

17 passed in 0.09s
```

全量回归：**38 passed** (21 original + 17 new)，0 failed。

---

## 四、与上游依赖关系

| 依赖 | 提供方 | 当前状态 | Coordinator 如何对接 |
|------|--------|----------|---------------------|
| `LlmClientProtocol` | Lead (Phase 0) | 已定义 | 通过 `self._require_llm()` 获取，`isinstance` 校验 |
| `BaseAgent` | Lead (Phase 0) | 已实现 | 继承，复用 `build_system_prompt`、`_read_context`、`_write_context` |
| `llm/client.py` (LlmClient) | Planner 组 C2 | 待实现 | 无直接依赖 — Coordinator 只依赖 Protocol，不 import 具体类 |
| `memory/context_io.py` | Explorer 组 B2 | 待实现 | 无直接依赖 — Coordinator 使用 BaseAgent 内置的 `_read_context`/`_write_context` |
| Explorer 产出 (research.summary 等) | Explorer 组 | 待实现 | `_read_context` 读取短期上下文，缺失时 prompt 自动降级 |
| Planner 产出 (constraint.analysis 等) | Planner 组 | 待实现 | 同上 |

**关键设计**：CoordinatorAgent 与 C2/B2 组**零耦合** — 不 import 任何未完成的模块，所有外部能力通过 Protocol 和 BaseAgent 内置方法间接使用。

---

## 五、接口契约

CoordinatorAgent 对外暴露的契约（下游 Worker 和 Reviewer 直接消费）：

### 写入的长期上下文

| Context Key | 文件 | 写入阶段 |
|-------------|------|----------|
| `<pid>.narration.script` | `runtime/projects/<pid>/<pid>-narration-script.json` | PLAN |
| `<pid>.storyboard.master` | `runtime/projects/<pid>/<pid>-storyboard-master.json` | PLAN |

### 写入的短期上下文

| Context Key | 文件 | 写入阶段 |
|-------------|------|----------|
| `<pid>.session.handoff` | `runtime/sessions/<sid>/<pid>-session-handoff.json` | DISPATCH |

### run() 返回格式

```python
# 成功 — PLAN
{"success": True, "task_id": "...", "outputs": ["...narration.script", "...storyboard.master"],
 "segment_count": 2, "total_duration_seconds": 75}

# 成功 — DISPATCH
{"success": True, "task_id": "...", "outputs": ["...session.handoff"],
 "task_assignments": [...], "assigned_count": 2}

# 失败
{"success": False, "task_id": "...", "error": "llm_unavailable | validation_failed | ...",
 "validation_errors": [...]}  # 仅 validation_failed 时
```
