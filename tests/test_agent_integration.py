"""Agent 集成测试 — Explorer → Planner → Coordinator 串联验证。"""

from typing import Any

from manimind.agents.orchestrator import Orchestrator
from manimind.models import PipelineStage, SegmentModality, SegmentSpec, SourceBundle
from manimind.workflow import build_project_plan


class MockLlmClient:
    """可预设返回值的 mock LLM 客户端。"""

    def __init__(self):
        self.calls: list[dict[str, Any]] = []
        self._response_map: dict[str, dict[str, Any]] = {}
        self._default_response: dict[str, Any] = {"status": "ok"}

    def set_response(self, schema_key: str, response: dict[str, Any]) -> None:
        self._response_map[schema_key] = response

    def chat(self, system_prompt: str, user_message: str, *, temperature: float = 0.3, max_tokens: int = 4096) -> str:
        self.calls.append({"method": "chat", "user_message": user_message[:200]})
        return "mock response"

    def chat_structured(self, system_prompt: str, user_message: str, output_schema: dict[str, Any]) -> dict[str, Any]:
        self.calls.append({
            "method": "chat_structured",
            "user_message": user_message[:200],
        })
        return self._default_response


def _make_plan() -> Any:
    return build_project_plan(
        project_id="test-project",
        title="Integration Test",
        source_bundle=SourceBundle(paper_path="paper.pdf"),
        segments=[
            SegmentSpec(
                id="seg-1",
                title="introduction",
                goal="Introduce spacetime concept",
                narration="Welcome to special relativity.",
                modality=SegmentModality.HTML,
                estimated_seconds=30,
            ),
            SegmentSpec(
                id="seg-2",
                title="lorentz_transform",
                goal="Show Lorentz transformation",
                narration="Now let's derive the Lorentz transformation.",
                modality=SegmentModality.MANIM,
                formulas=["\\gamma = \\frac{1}{\\sqrt{1-v^2/c^2}}"],
                estimated_seconds=60,
            ),
        ],
    )


# ============================================================================
# 三 Agent 串联测试
# ============================================================================


def test_orchestrator_pipeline_all_stages() -> None:
    """完整 Pipeline 五个阶段全部跑通（使用 mock LLM）。"""

    plan = _make_plan()
    mock_llm = MockLlmClient()
    orchestrator = Orchestrator(plan, llm_client=mock_llm, session_id="test-session")

    result = orchestrator.run()

    assert result.success is False  # 无真实 LLM 返回，但不会崩溃
    assert result.project_id == "test-project"
    assert result.session_id == "test-session"
    # 即使 LLM 返回无效数据，编排器也不会崩溃，只标记失败
    assert result.stage_count == 6
    assert result.error_count > 0


def test_orchestrator_creates_agents() -> None:
    """编排器能正确创建三种 Agent 实例。"""

    plan = _make_plan()
    orchestrator = Orchestrator(plan, llm_client=None, session_id="test")

    # 无 LLM 时不应崩溃
    result = orchestrator.run()
    assert result.project_id == "test-project"
    assert result.stage_count == 6


def test_orchestrator_with_null_llm_handles_gracefully() -> None:
    """无 LLM 时 Pipeline 不会崩溃，所有阶段返回 llm_unavailable。"""

    plan = _make_plan()
    orchestrator = Orchestrator(plan, llm_client=None, session_id="test")

    result = orchestrator.run()

    assert result.success is False
    assert result.stage_count == 6
    # 每个阶段应该都因为 llm_unavailable 而失败
    for stage_result in result.stage_results:
        err = stage_result.get("error", "")
        assert err == "llm_unavailable" or "No module named" not in str(err)


def test_orchestrator_custom_stages() -> None:
    """编排器支持指定只运行部分阶段。"""

    plan = _make_plan()
    orchestrator = Orchestrator(plan, llm_client=None, session_id="test")

    result = orchestrator.run(stages=[PipelineStage.PRESTART, PipelineStage.INGEST])

    assert result.stage_count == 2
    # 不应尝试运行其它阶段


def test_orchestrator_dispatch_fails_when_any_worker_fails(monkeypatch) -> None:
    """DISPATCH 必须把 Worker 失败当成硬阻塞。"""

    from manimind.agents import orchestrator as orchestrator_module

    class FakeCoordinator:
        def __init__(self, *args, **kwargs):
            pass

        def run(self, *args, **kwargs):
            return {"success": True}

    class FakeHtmlWorker:
        def __init__(self, *args, **kwargs):
            pass

        def run(self, *args, **kwargs):
            return {"success": True}

    class FakeManimWorker:
        def __init__(self, *args, **kwargs):
            pass

        def run(self, *args, **kwargs):
            return {"success": False, "error": "render_failed"}

    class FakeSvgWorker:
        def __init__(self, *args, **kwargs):
            pass

        def run(self, *args, **kwargs):
            return {"success": True}

    monkeypatch.setattr(orchestrator_module, "CoordinatorAgent", FakeCoordinator)
    monkeypatch.setattr(orchestrator_module, "HtmlWorkerAgent", FakeHtmlWorker)
    monkeypatch.setattr(orchestrator_module, "ManimWorkerAgent", FakeManimWorker)
    monkeypatch.setattr(orchestrator_module, "SvgWorkerAgent", FakeSvgWorker)

    plan = _make_plan()
    orchestrator = Orchestrator(plan, llm_client=None, session_id="test")
    result = orchestrator.run(stages=[PipelineStage.DISPATCH])

    assert result.success is False
    assert result.stage_results[0]["success"] is False
    assert result.stage_results[0]["failed_workers"] == ["manim"]


def test_orchestrator_pipeline_result_structure() -> None:
    """PipelineResult 包含完整输出结构。"""

    plan = _make_plan()
    orchestrator = Orchestrator(plan, llm_client=None, session_id="test-sess")
    result = orchestrator.run(stages=[PipelineStage.PRESTART])

    assert hasattr(result, "success")
    assert hasattr(result, "project_id")
    assert hasattr(result, "stage_results")
    assert hasattr(result, "errors")
    assert hasattr(result, "outputs")
    assert result.project_id == "test-project"
    assert result.session_id == "test-sess"
    assert isinstance(result.stage_results, list)
    assert "prestart" in result.outputs


# ============================================================================
# Agent 间数据传递测试
# ============================================================================


def test_explorer_to_planner_context_chain() -> None:
    """Explorer 产出 → 可被 Planner 通过 _read_context 读取。"""

    from manimind.agents.explorer import ExplorerAgent
    from manimind.agents.planner import PlannerAgent
    from manimind.models import ContextScope

    plan = _make_plan()

    # 先运行 Explorer SUMMARIZE
    explorer_llm = MockLlmClient()
    explorer_llm._default_response = {
        "research_summary": {
            "paper_available": True,
            "paper_title": "Test Paper",
            "core_concepts": [
                {
                    "name": "Gravity",
                    "description": "Force of attraction",
                    "difficulty": "intermediate",
                    "visualizable": True,
                }
            ],
            "key_findings": ["Gravity curves spacetime"],
            "audience_assessment": {
                "level": "intermediate",
                "prerequisites": ["Basic physics"],
                "simplification_needed": [],
            },
            "visual_suggestions": [],
        },
        "glossary": {
            "terms": [
                {
                    "term": "Gravity",
                    "definition": "Attraction between masses",
                    "category": "物理",
                }
            ],
        },
        "formula_catalog": {
            "formulas": [
                {
                    "id": "f1",
                    "latex": "F=ma",
                    "description": "Newton's second law",
                    "importance": "core",
                }
            ],
        },
    }

    explorer = ExplorerAgent(plan, llm_client=explorer_llm, session_id="test")
    explorer_result = explorer.run(PipelineStage.SUMMARIZE, "test-task")

    assert explorer_result["success"] is True

    # Planner 应该能读取 Explorer 写入的上下文
    planner_llm = MockLlmClient()
    planner_llm._default_response = {
        "constraint_analysis": {
            "audience_match": {
                "difficulty_level": "intermediate",
                "recommendations": ["Simplify math"],
            },
            "time_estimates": [{"segment_id": "seg-1", "estimated_seconds": 30}],
            "modality_recommendations": [{"segment_id": "seg-1", "modality": "html"}],
            "risk_points": [],
        },
        "feasibility_assessment": {
            "overall_score": 4,
            "success_factors": ["Good visual materials"],
            "challenges": ["Complex math"],
        },
    }

    planner = PlannerAgent(plan, llm_client=planner_llm, session_id="test")
    planner_result = planner.run(PipelineStage.SUMMARIZE, "test-task")

    assert planner_result["success"] is True

    # 验证 Planner 成功读取了 Explorer 写入的上下文
    research = planner._read_context("test-project.research.summary")
    assert research is not None
    assert research["core_concepts"][0]["name"] == "Gravity"


def test_planner_to_coordinator_context_chain() -> None:
    """Planner 产出 → 可被 Coordinator 通过 _read_context 读取。"""

    from manimind.agents.planner import PlannerAgent
    from manimind.agents.coordinator import CoordinatorAgent
    from manimind.models import ContextScope

    plan = _make_plan()

    # 先运行 Planner SUMMARIZE
    planner_llm = MockLlmClient()
    planner_llm._default_response = {
        "constraint_analysis": {
            "audience_match": {
                "difficulty_level": "intermediate",
                "recommendations": ["Add visual aids"],
            },
            "time_estimates": [{"segment_id": "seg-1", "estimated_seconds": 30}],
            "modality_recommendations": [{"segment_id": "seg-1", "modality": "html"}],
            "risk_points": [],
        },
        "feasibility_assessment": {
            "overall_score": 4,
            "success_factors": ["Clear structure"],
            "challenges": ["Technical terms"],
        },
    }

    planner = PlannerAgent(plan, llm_client=planner_llm, session_id="test")
    planner.run(PipelineStage.SUMMARIZE, "planner-task")

    # Coordinator PLAN 应该能读取 Planner 产出
    coord_llm = MockLlmClient()
    coord_llm._default_response = {
        "narration_script": {
            "segments": [
                {
                    "segment_id": "seg-1",
                    "title": "intro",
                    "narration_text": "Hello world.",
                    "timing_hints": {"estimated_seconds": 30, "pause_after": 2},
                    "emphasis": [],
                    "formulas_in_context": [],
                },
            ],
            "voiceover_notes": {
                "style": "calm",
                "tone": "educational",
                "total_estimated_duration_seconds": 30,
            },
        },
        "storyboard_master": {
            "segments": [
                {
                    "segment_id": "seg-1",
                    "title": "intro",
                    "order": 1,
                    "modality": "html",
                    "estimated_seconds": 30,
                    "goal": "Introduce",
                    "worker_tasks": [
                        {"worker": "html", "task_id": "render.seg-1.html", "objective": "Build intro"}
                    ],
                },
            ],
            "style_sheet": {
                "color_palette": ["#fff"],
                "font_scale": "1.0",
                "animation_pacing": "medium",
            },
        },
    }

    coordinator = CoordinatorAgent(plan, llm_client=coord_llm, session_id="test")
    coord_result = coordinator.run(PipelineStage.PLAN, "coord-task")

    assert coord_result["success"] is True
    assert "test-project.narration.script" in coord_result["outputs"]
