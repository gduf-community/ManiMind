"""Planner Agent 单元测试。"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from manimind.agents.planner import PlannerAgent, _validate_plan_output, _validate_summarize_output
from manimind.llm.templates.planner import PLAN_OUTPUT_SCHEMA, SUMMARIZE_OUTPUT_SCHEMA
from manimind.models import (
    AgentMode,
    AgentProfile,
    ContextRecord,
    ContextScope,
    PipelineStage,
    ProjectPlan,
    RuntimeLayout,
    SegmentModality,
    SegmentSpec,
    SourceBundle,
)


# ============================================================================
# Fixture: 构建测试用的 ProjectPlan
# ============================================================================


@pytest.fixture
def sample_plan(tmp_path: Path) -> ProjectPlan:
    """创建一个最小化的 ProjectPlan 用于测试。"""
    project_id = "test-project"
    runtime_layout = RuntimeLayout(
        project_context_dir=str(tmp_path / "projects" / project_id),
        session_context_root=str(tmp_path / "sessions"),
        output_dir=str(tmp_path / "outputs"),
        bootstrap_report="",
        doctor_report="",
    )

    segments = [
        SegmentSpec(
            id="seg-1",
            title="引言",
            goal="介绍核心概念",
            narration="开场白",
            modality=SegmentModality.HYBRID,
            formulas=["E = mc^2"],
        ),
        SegmentSpec(
            id="seg-2",
            title="推导过程",
            goal="展示数学推导",
            narration="详细解释",
            modality=SegmentModality.MANIM,
            formulas=["\\int_0^\\infty e^{-x} dx = 1"],
        ),
    ]

    contexts = [
        ContextRecord(
            key=f"{project_id}.research.summary",
            scope=ContextScope.LONG_TERM,
            summary="研究总结",
            writer_role="explorer",
            consumer_roles=["planner", "coordinator"],
        ),
        ContextRecord(
            key=f"{project_id}.glossary",
            scope=ContextScope.LONG_TERM,
            summary="术语表",
            writer_role="explorer",
            consumer_roles=["planner", "coordinator"],
        ),
        ContextRecord(
            key=f"{project_id}.formula.catalog",
            scope=ContextScope.LONG_TERM,
            summary="公式目录",
            writer_role="explorer",
            consumer_roles=["planner", "coordinator"],
        ),
        ContextRecord(
            key=f"{project_id}.style.guide",
            scope=ContextScope.LONG_TERM,
            summary="风格指南",
            writer_role="lead",
            consumer_roles=["planner", "coordinator"],
        ),
    ]

    agent_profiles = [
        AgentProfile(
            id="planner",
            mode=AgentMode.READ_ONLY,
            responsibility="只读分析约束并提出分镜与实现规划建议。",
            allowed_stages=[PipelineStage.SUMMARIZE, PipelineStage.PLAN],
            required_inputs=[
                f"{project_id}.research.summary",
                f"{project_id}.glossary",
                f"{project_id}.formula.catalog",
                f"{project_id}.style.guide",
            ],
            owned_outputs=[],
            output_contract="只能产出规划建议，正式分镜需由协调层写入结构化上下文。",
        ),
    ]

    return ProjectPlan(
        project_id=project_id,
        title="Test Project",
        source_bundle=SourceBundle(paper_path="test.pdf"),
        stages=[PipelineStage.SUMMARIZE, PipelineStage.PLAN],
        segments=segments,
        tasks=[],
        contexts=contexts,
        review_checkpoints=[],
        agent_profiles=agent_profiles,
        execution_tasks=[],
        runtime_layout=runtime_layout,
        current_stage=PipelineStage.SUMMARIZE,
    )


# ============================================================================
# LLM Client Mock
# ============================================================================


class MockLlmClient:
    """模拟 LLM 客户端，返回预设的 JSON 响应。"""

    def __init__(self, summarize_response: dict | None = None, plan_response: dict | None = None):
        self.summarize_response = summarize_response or self._default_summarize_response()
        self.plan_response = plan_response or self._default_plan_response()

    def chat(self, system_prompt: str, user_message: str, **kwargs) -> str:
        return json.dumps({"mock": "response"})

    def chat_structured(
        self, system_prompt: str, user_message: str, output_schema: dict
    ) -> dict:
        if "constraint_analysis" in output_schema.get("properties", {}):
            return self.summarize_response
        else:
            return self.plan_response

    @staticmethod
    def _default_summarize_response() -> dict:
        return {
            "constraint_analysis": {
                "audience_match": {
                    "difficulty_level": "intermediate",
                    "simplification_needed": [],
                    "recommendations": ["适合高中以上观众"],
                },
                "time_estimates": [
                    {"concept": "相对论", "min_seconds": 30, "recommended_seconds": 60}
                ],
                "modality_recommendations": [
                    {
                        "concept": "时空弯曲",
                        "recommended_modality": "manim",
                        "reason": "需要几何变换可视化",
                    }
                ],
                "risk_points": [
                    {
                        "risk": "概念抽象",
                        "severity": "medium",
                        "mitigation": "使用类比和图示",
                    }
                ],
            },
            "feasibility_assessment": {
                "overall_score": 4,
                "success_factors": ["概念清晰", "有现成资产"],
                "challenges": ["时间紧张"],
            },
        }

    @staticmethod
    def _default_plan_response() -> dict:
        return {
            "storyboard_suggestions": {
                "segment_order": ["seg-1", "seg-2"],
                "segments": [
                    {
                        "segment_id": "seg-1",
                        "key_concepts": ["相对论基础"],
                        "modality": "hybrid",
                        "estimated_seconds": 30,
                        "formulas": ["E = mc^2"],
                        "animation_notes": "使用转场动画引入",
                        "narration_points": "强调能量与质量的关系",
                        "asset_references": [],
                    },
                    {
                        "segment_id": "seg-2",
                        "key_concepts": ["积分计算"],
                        "modality": "manim",
                        "estimated_seconds": 45,
                        "formulas": ["\\int_0^\\infty e^{-x} dx = 1"],
                        "animation_notes": "逐步展示积分过程",
                        "narration_points": "解释每一步的物理意义",
                        "asset_references": [],
                    },
                ],
                "pacing_advice": {
                    "opening": "用引人入胜的问题开场",
                    "middle": "通过互动保持注意力",
                    "closing": "总结关键点并给出思考题",
                },
            }
        }


# ============================================================================
# SUMMARIZE 阶段测试
# ============================================================================


def test_planner_summarize_success(sample_plan: ProjectPlan):
    """测试 SUMMARIZE 阶段成功执行。"""
    mock_llm = MockLlmClient()
    agent = PlannerAgent(plan=sample_plan, llm_client=mock_llm, session_id="test-session")

    result = agent.run(PipelineStage.SUMMARIZE, "task-summarize-1")

    assert result["success"] is True
    assert result["task_id"] == "task-summarize-1"
    assert len(result["outputs"]) == 2
    assert "difficulty_level" in result
    assert result["difficulty_level"] == "intermediate"
    assert "overall_score" in result
    assert result["overall_score"] == 4


def test_planner_summarize_with_kwargs(sample_plan: ProjectPlan):
    """测试 SUMMARIZE 阶段通过 kwargs 传入数据。"""
    mock_llm = MockLlmClient()
    agent = PlannerAgent(plan=sample_plan, llm_client=mock_llm, session_id="test-session")

    research_summary = {
        "core_concepts": [{"name": "相对论", "difficulty": "intermediate"}],
        "key_findings": ["E=mc^2"],
    }
    glossary = {"terms": [{"term": "能量", "definition": "..."}]}
    formula_catalog = {"formulas": [{"latex": "E=mc^2", "meaning": "..."}]}
    style_guide = {"audience": "高中生"}

    result = agent.run(
        PipelineStage.SUMMARIZE,
        "task-summarize-2",
        research_summary=research_summary,
        glossary=glossary,
        formula_catalog=formula_catalog,
        style_guide=style_guide,
    )

    assert result["success"] is True


def test_planner_summarize_llm_unavailable(sample_plan: ProjectPlan):
    """测试 LLM 不可用时的优雅降级。"""
    agent = PlannerAgent(plan=sample_plan, llm_client=None, session_id="test-session")

    result = agent.run(PipelineStage.SUMMARIZE, "task-summarize-3")

    assert result["success"] is False
    assert result["error"] == "llm_unavailable"


# ============================================================================
# PLAN 阶段测试
# ============================================================================


def test_planner_plan_success(sample_plan: ProjectPlan):
    """测试 PLAN 阶段成功执行。"""
    mock_llm = MockLlmClient()
    agent = PlannerAgent(plan=sample_plan, llm_client=mock_llm, session_id="test-session")

    result = agent.run(PipelineStage.PLAN, "task-plan-1")

    assert result["success"] is True
    assert result["task_id"] == "task-plan-1"
    assert len(result["outputs"]) == 1
    assert "segments_planned" in result
    assert result["segments_planned"] == 2


def test_planner_plan_with_kwargs(sample_plan: ProjectPlan):
    """测试 PLAN 阶段通过 kwargs 传入数据。"""
    mock_llm = MockLlmClient()
    agent = PlannerAgent(plan=sample_plan, llm_client=mock_llm, session_id="test-session")

    constraint_analysis = {
        "audience_match": {"difficulty_level": "intermediate"},
        "time_estimates": [],
        "modality_recommendations": [],
        "risk_points": [],
    }

    result = agent.run(
        PipelineStage.PLAN,
        "task-plan-2",
        constraint_analysis=constraint_analysis,
    )

    assert result["success"] is True


def test_planner_plan_llm_unavailable(sample_plan: ProjectPlan):
    """测试 LLM 不可用时的优雅降级。"""
    agent = PlannerAgent(plan=sample_plan, llm_client=None, session_id="test-session")

    result = agent.run(PipelineStage.PLAN, "task-plan-3")

    assert result["success"] is False
    assert result["error"] == "llm_unavailable"


# ============================================================================
# 不支持的阶段测试
# ============================================================================


def test_planner_unsupported_stage(sample_plan: ProjectPlan):
    """测试 Planner 不支持的阶段。"""
    mock_llm = MockLlmClient()
    agent = PlannerAgent(plan=sample_plan, llm_client=mock_llm, session_id="test-session")

    result = agent.run(PipelineStage.INGEST, "task-ingest-1")

    assert result["success"] is False
    assert "does not support stage" in result["error"]


# ============================================================================
# 输出校验测试
# ============================================================================


def test_validate_summarize_output_valid():
    """测试 SUMMARIZE 输出校验 - 有效输入。"""
    valid_output = {
        "constraint_analysis": {
            "audience_match": {
                "difficulty_level": "intermediate",
                "simplification_needed": [],
                "recommendations": ["建议1"],
            },
            "time_estimates": [{"concept": "A", "min_seconds": 10, "recommended_seconds": 20}],
            "modality_recommendations": [
                {"concept": "A", "recommended_modality": "manim", "reason": "原因"}
            ],
            "risk_points": [{"risk": "风险", "severity": "medium", "mitigation": "缓解"}],
        },
        "feasibility_assessment": {
            "overall_score": 4,
            "success_factors": ["因素1"],
            "challenges": ["挑战1"],
        },
    }

    errors = _validate_summarize_output(valid_output)
    assert len(errors) == 0


def test_validate_summarize_output_invalid():
    """测试 SUMMARIZE 输出校验 - 无效输入。"""
    invalid_output = {
        "constraint_analysis": {
            "audience_match": {
                "difficulty_level": "invalid_level",  # 无效的难度级别
                "simplification_needed": [],
                "recommendations": "not a list",  # 应该是列表
            },
            "time_estimates": [],  # 空列表
            "modality_recommendations": [],  # 空列表
            "risk_points": "not a list",  # 应该是列表
        },
        "feasibility_assessment": {
            "overall_score": 10,  # 超出范围
            "success_factors": "not a list",
            "challenges": "not a list",
        },
    }

    errors = _validate_summarize_output(invalid_output)
    assert len(errors) > 0


def test_validate_plan_output_valid():
    """测试 PLAN 输出校验 - 有效输入。"""
    valid_output = {
        "storyboard_suggestions": {
            "segment_order": ["seg-1"],
            "segments": [
                {
                    "segment_id": "seg-1",
                    "key_concepts": ["概念1"],
                    "modality": "manim",
                    "estimated_seconds": 30,
                    "formulas": ["E=mc^2"],
                    "animation_notes": "备注",
                    "narration_points": "要点",
                    "asset_references": [],
                }
            ],
            "pacing_advice": {
                "opening": "开头",
                "middle": "中间",
                "closing": "结尾",
            },
        }
    }

    errors = _validate_plan_output(valid_output)
    assert len(errors) == 0


def test_validate_plan_output_invalid():
    """测试 PLAN 输出校验 - 无效输入。"""
    invalid_output = {
        "storyboard_suggestions": {
            "segment_order": [],  # 空列表
            "segments": [
                {
                    "segment_id": "",  # 缺少 segment_id
                    "key_concepts": [],
                    "modality": "invalid",  # 无效的 modality
                    "estimated_seconds": 2,  # 小于最小值
                    "formulas": [],
                    "animation_notes": "",
                    "narration_points": "",
                    "asset_references": [],
                }
            ],
            "pacing_advice": {
                "opening": "",  # 空字符串
                "middle": "",
                "closing": "",
            },
        }
    }

    errors = _validate_plan_output(invalid_output)
    assert len(errors) > 0


# ============================================================================
# JSON Schema 验证
# ============================================================================


def test_summarize_schema_structure():
    """测试 SUMMARIZE schema 结构完整性。"""
    assert "type" in SUMMARIZE_OUTPUT_SCHEMA
    assert SUMMARIZE_OUTPUT_SCHEMA["type"] == "object"
    assert "required" in SUMMARIZE_OUTPUT_SCHEMA
    assert "properties" in SUMMARIZE_OUTPUT_SCHEMA


def test_plan_schema_structure():
    """测试 PLAN schema 结构完整性。"""
    assert "type" in PLAN_OUTPUT_SCHEMA
    assert PLAN_OUTPUT_SCHEMA["type"] == "object"
    assert "required" in PLAN_OUTPUT_SCHEMA
    assert "properties" in PLAN_OUTPUT_SCHEMA
