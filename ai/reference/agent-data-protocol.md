# Agent 间数据协议

**版本**: 1.1  
**状态**: 已发布（Phase 0 前置交付）  
**维护者**: Lead

---

## 零、输入摄取层输出格式（Explorer前置依赖）

输入摄取层是纯工具层，**不写入 runtime 文件系统**，而是直接返回结构化数据给 Explorer 调用。所有格式约定如下：

### 0.1 SourceBundle统一入口

**位置**: `ingest/__init__.py` 的 `load_source_bundle()`

```python
@dataclass
class SourceBundle:
    """输入摄取层的统一输出，给Explorer使用。"""
    paper: PaperContent | None      # 论文内容，若无则None
    notes: list[NoteContent]        # 笔记列表
    assets: AssetList               # 参考资产清单
    env_report: EnvReport           # 环境检测报告
```

---

### 0.2 PaperContent（PDF解析输出）

```python
@dataclass
class PaperContent:
    path: str                       # 原始PDF路径
    exists: bool                    # 文件是否存在
    text: str | None                # 全文本（包括公式LaTeX）
    extracted_at: datetime          # 提取时间
    parse_warnings: list[str]       # 解析警告（如编码问题、公式可能混排）
```

---

### 0.3 NoteContent（Markdown笔记输出）

```python
@dataclass
class NoteContent:
    path: str                       # 原始笔记路径
    title: str | None               # 标题（来自YAML front matter或文件名）
    front_matter: dict[str, Any]    # YAML front matter内容
    body_text: str                  # 正文文本
    images: list[str]               # 笔记中引用的图片路径
```

---

### 0.4 AssetList（参考资产扫描输出）

```python
@dataclass
class AssetList:
    scanned_at: datetime
    components: list[ComponentInfo] # 可用组件（HyperFrames、HTML模板等）
    manim_assets: list[str]         # Manim参考脚本
    references: list[str]           # 其他参考文档
```

```python
@dataclass
class ComponentInfo:
    path: str
    name: str
    category: str                   # "html_template" / "manim_script" / "svg_asset" / "other"
    description: str | None
```

---

### 0.5 EnvReport（环境检测输出）

```python
@dataclass
class EnvReport:
    generated_at: datetime
    python: ToolCheckResult
    node: ToolCheckResult
    manim: ToolCheckResult
    ffmpeg: ToolCheckResult
    overall_status: "ok" | "warning" | "error"
    warnings: list[str]
```

```python
@dataclass
class ToolCheckResult:
    name: str
    available: bool
    version: str | None
    path: str | None
    details: str | None
```

---

## 一、核心原则

1. **Agent 间不直接通信** — 所有数据通过 `runtime/` 文件系统交换，与 `runtime_store.py` 原子写入 + JSONL 审计机制一致。
2. **read_only Agent 写入短期上下文** — Explorer 和 Planner 产出"建议稿"，写入 `runtime/sessions/<session_id>/`，不污染长期上下文。
3. **structured_write Agent 写入长期上下文** — Coordinator 产出权威版本，写入 `runtime/projects/<project_id>/`，下游 Worker 直接消费。
4. **所有交换均有审计日志** — 每次写入追加 `events.jsonl`，可追溯。

---

## 二、数据流总览

```
manifest
  (paper_path, note_paths)
        │
        ▼
┌──────────────────────────────────────────────────────────────┐
│  输入摄取层 (纯工具，不写runtime)                            │
│  ingest/pdf_reader.py, ingest/markdown_reader.py             │
│  ingest/asset_scanner.py, ingest/env_reporter.py             │
│                                                              │
│  输出: SourceBundle (Python dataclass，内存传递给Explorer)    │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│  Explorer (read_only)                                       │
│                                                              │
│  阶段: PRESTART → INGEST → SUMMARIZE → PLAN                 │
│                                                              │
│  产出 → runtime/sessions/<session_id>/explorer-findings/    │
│          ├── research-summary-draft.json                    │
│          ├── glossary-draft.json                            │
│          └── formula-catalog-draft.json                     │
└──────────────────────────┬──────────────────────────────────┘
                           │ (Planner 读取 explorer-findings/)
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Planner (read_only)                                        │
│                                                             │
│  阶段: SUMMARIZE → PLAN                                     │
│                                                             │
│  产出 → runtime/sessions/<session_id>/planner-suggestions/  │
│          ├── constraint-analysis.json                       │
│          └── storyboard-suggestions.json                    │
└──────────────────────────┬──────────────────────────────────┘
                           │ (Coordinator 读取全部建议稿)
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Coordinator (structured_write)                             │
│                                                             │
│  阶段: PLAN → DISPATCH                                      │
│                                                             │
│  产出 → runtime/projects/<project_id>/                      │
│          ├── <project_id>.narration.script.json             │
│          ├── <project_id>.storyboard.master.json            │
│          └── <project_id>.session.handoff.json              │
└──────────────────────────┬──────────────────────────────────┘
                           │ (下游 Worker 读取长期上下文)
                           ▼
              ┌─────────────────────────┐
              │ HTML / Manim / SVG      │
              │ Workers (DISPATCH 阶段) │
              └─────────────────────────┘
```

---

## 三、文件路径约定

### 短期上下文（Session-scoped）

| 来源 | 路径 |
|------|------|
| Explorer 发现 | `runtime/sessions/<session_id>/explorer-findings/` |
| Planner 建议 | `runtime/sessions/<session_id>/planner-suggestions/` |
| 上下文包存档 | `runtime/sessions/<session_id>/context-packets/` |
| 任务更新日志 | `runtime/sessions/<session_id>/task-updates/` |
| 审计日志 | `runtime/sessions/<session_id>/events.jsonl` |

### 长期上下文（Project-lifecycle）

| Context Key | 文件路径 |
|-------------|----------|
| `<pid>.research.summary` | `runtime/projects/<pid>/<pid>-research-summary.json` |
| `<pid>.glossary` | `runtime/projects/<pid>/<pid>-glossary.json` |
| `<pid>.formula.catalog` | `runtime/projects/<pid>/<pid>-formula-catalog.json` |
| `<pid>.narration.script` | `runtime/projects/<pid>/<pid>-narration-script.json` |
| `<pid>.storyboard.master` | `runtime/projects/<pid>/<pid>-storyboard-master.json` |
| `<pid>.session.handoff` | `runtime/projects/<pid>/<pid>-session-handoff.json` |
| `<pid>.review.report` | `runtime/projects/<pid>/<pid>-review-report.json` |

### 文件命名规则

- Context key 中的 `.` 替换为 `-`
- 后缀统一为 `.json`
- 临时写入使用 `.{filename}.{uuid}.tmp`，完成后 `os.replace` 原子替换

---

## 四、Explorer 产出格式

### 4.1 研究总结建议稿

**文件**: `explorer-findings/research-summary-draft.json`

```json
{
  "key": "<pid>.research.summary",
  "scope": "short_term",
  "writer_role": "explorer",
  "session_id": "<session_id>",
  "content": {
    "paper_available": true,
    "paper_title": "论文标题（如有）",
    "core_concepts": [
      {
        "name": "概念名",
        "description": "一句话解释",
        "difficulty": "beginner | intermediate | advanced",
        "visualizable": true
      }
    ],
    "key_findings": [
      "研究发现 1",
      "研究发现 2"
    ],
    "audience_assessment": {
      "level": "beginner | intermediate | advanced",
      "prerequisites": ["前置知识"],
      "simplification_needed": ["需要简化的部分"]
    },
    "visual_suggestions": [
      {
        "concept": "关联概念",
        "visual_type": "graph | transform | comparison | 3d",
        "notes": "视觉建议说明"
      }
    ]
  }
}
```

### 4.2 术语表建议稿

**文件**: `explorer-findings/glossary-draft.json`

```json
{
  "key": "<pid>.glossary",
  "scope": "short_term",
  "writer_role": "explorer",
  "session_id": "<session_id>",
  "content": {
    "terms": [
      {
        "term": "术语",
        "definition": "定义",
        "latex": "可选 LaTeX 表达式",
        "category": "数学 | 物理 | 计算机 | 其他",
        "related_terms": ["关联术语"]
      }
    ]
  }
}
```

### 4.3 公式目录建议稿

**文件**: `explorer-findings/formula-catalog-draft.json`

```json
{
  "key": "<pid>.formula.catalog",
  "scope": "short_term",
  "writer_role": "explorer",
  "session_id": "<session_id>",
  "content": {
    "formulas": [
      {
        "id": "公式唯一标识",
        "latex": "完整 LaTeX 表达式",
        "description": "公式含义",
        "variables": {
          "符号": "含义"
        },
        "importance": "core | supporting | optional",
        "visual_approach": "如何可视化该公式"
      }
    ]
  }
}
```

---

## 五、Planner 产出格式

### 5.1 约束分析

**文件**: `planner-suggestions/constraint-analysis.json`

```json
{
  "key": "planner.constraint.analysis",
  "scope": "short_term",
  "writer_role": "planner",
  "session_id": "<session_id>",
  "content": {
    "difficulty_assessment": {
      "overall_level": "beginner | intermediate | advanced",
      "gap_analysis": "受众水平与内容难度的差距分析",
      "recommendations": ["降低难度的建议"]
    },
    "time_estimates": [
      {
        "segment_id": "镜头 id",
        "estimated_seconds": 30,
        "rationale": "估算依据"
      }
    ],
    "modality_recommendations": [
      {
        "segment_id": "镜头 id",
        "recommended_modality": "html | manim | hybrid | svg",
        "reason": "推荐理由"
      }
    ],
    "risk_items": [
      {
        "segment_id": "镜头 id",
        "risk": "风险描述",
        "severity": "low | medium | high",
        "mitigation": "缓解措施"
      }
    ]
  }
}
```

### 5.2 分镜建议

**文件**: `planner-suggestions/storyboard-suggestions.json`

```json
{
  "key": "planner.storyboard.suggestions",
  "scope": "short_term",
  "writer_role": "planner",
  "session_id": "<session_id>",
  "content": {
    "segments": [
      {
        "segment_id": "镜头 id",
        "title": "镜头标题",
        "suggested_order": 1,
        "transition_from": null,
        "key_visuals": ["关键视觉元素"],
        "pacing_notes": "节奏建议",
        "formula_placement": "inline | standalone | deferred"
      }
    ],
    "narrative_arc": {
      "opening": "开场策略",
      "development": "展开方式",
      "climax": "高潮设计",
      "closing": "结尾策略"
    }
  }
}
```

---

## 六、Coordinator 产出格式

### 6.1 讲解脚本

**文件**: `<project_id>-narration-script.json`（长期上下文）

```json
{
  "key": "<pid>.narration.script",
  "scope": "long_term",
  "writer_role": "coordinator",
  "content": {
    "segments": [
      {
        "segment_id": "镜头 id",
        "title": "镜头标题",
        "narration_text": "口语化讲解词，适合配音朗读",
        "timing_hints": {
          "estimated_seconds": 30,
          "pause_after": 2
        },
        "emphasis": ["需要重读的关键词"],
        "formulas_in_context": [
          {
            "latex": "公式 LaTeX",
            "spoken_form": "公式的口语化读法",
            "display_timing": "before_narration | during_narration | after_narration"
          }
        ]
      }
    ],
    "voiceover_notes": {
      "style": "配音风格建议",
      "tone": "语调建议",
      "total_estimated_duration_seconds": 300
    }
  }
}
```

### 6.2 分镜主表

**文件**: `<project_id>-storyboard-master.json`（长期上下文）

```json
{
  "key": "<pid>.storyboard.master",
  "scope": "long_term",
  "writer_role": "coordinator",
  "content": {
    "segments": [
      {
        "segment_id": "镜头 id",
        "title": "镜头标题",
        "order": 1,
        "modality": "html | manim | hybrid | svg",
        "estimated_seconds": 30,
        "goal": "该镜头要传达的核心信息",
        "formulas": ["LaTeX 公式列表"],
        "animation_notes": ["动画备注"],
        "visual_references": ["视觉参考"],
        "html_motion_notes": ["HTML 动效备注"],
        "requires_svg_motion": false,
        "worker_tasks": [
          {
            "worker": "html | manim | svg",
            "task_id": "render.<segment_id>.<worker>",
            "objective": "具体任务目标"
          }
        ]
      }
    ],
    "style_sheet": {
      "color_palette": ["主色", "辅色"],
      "font_scale": "标题/正文比例",
      "animation_pacing": "动画节奏偏好"
    }
  }
}
```

### 6.3 会话交接

**文件**: `<project_id>-session-handoff.json`（短期上下文）

```json
{
  "key": "<pid>.session.handoff",
  "scope": "short_term",
  "writer_role": "coordinator",
  "content": {
    "session_summary": "本次会话完成了什么",
    "completed_tasks": ["已完成的任务 id"],
    "pending_tasks": ["待完成的任务 id"],
    "blockers": ["阻塞项"],
    "notes_for_workers": {
      "html_worker": "HTML Worker 需要的上下文",
      "manim_worker": "Manim Worker 需要的上下文",
      "svg_worker": "SVG Worker 需要的上下文"
    },
    "review_checkpoints": ["需要审核的检查点"]
  }
}
```

---

## 七、通用文件封装格式

每个上下文文件使用统一的信封格式：

```json
{
  "key": "上下文唯一标识（与 ContextRecord.key 一致）",
  "scope": "long_term | short_term",
  "writer_role": "写入者 role_id",
  "session_id": "会话标识",
  "content": { }
}
```

- `content` 字段的具体结构由各 Agent 的产出格式定义（见第四至六节）
- 读取方通过 `key` 和 `scope` 定位文件，通过 `writer_role` 了解来源
- `BaseAgent._read_context(key)` 和 `BaseAgent._write_context(key, content, scope)` 自动处理信封封装

---

## 八、优雅降级规则

| 场景 | 处理方式 |
|------|----------|
| PDF 文件不存在 | Explorer 标记 `paper_available: false`，仅基于笔记和资产扫描生成报告 |
| LLM 不可用 | Agent 返回 `{"success": false, "error": "llm_unavailable"}`，不阻塞 pipeline |
| 资源目录为空 | 资产扫描器返回空清单 `{"assets": []}`，不报错 |
| 上游产出缺失 | 下游 Agent 在 `build_user_message()` 中标记 `（数据缺失）`，继续执行 |
| JSON Schema 校验失败 | Coordinator DISPATCH 阶段拒绝写入，返回 `{"success": false, "validation_errors": [...]}` |

---

## 九、版本兼容性

- 所有 JSON 格式均为**向前兼容**：读取方忽略未知字段，不因新增字段而崩溃
- `content` 内部结构如需大版本变更，通过 `content.content_version` 字段标识
- 当前版本为 `1.0`，省略 `content_version` 即视为 `1.0`
