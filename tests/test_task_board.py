"""执行任务状态机测试。"""

from dataclasses import asdict, replace

import pytest

from manimind.models import ExecutionTask, SegmentModality, SegmentSpec, SourceBundle, TaskStatus
from manimind.task_board import (
    TaskGraphError,
    TaskMutationResult,
    list_available_tasks,
    update_execution_task_status,
)
from manimind.workflow import build_project_plan


def _demo_plan():
    return build_project_plan(
        project_id="demo",
        title="demo",
        source_bundle=SourceBundle(paper_path="paper.pdf"),
        segments=[
            SegmentSpec(
                id="seg-1",
                title="hybrid",
                goal="goal",
                narration="narration",
                modality=SegmentModality.HYBRID,
                formulas=["x^2"],
                requires_svg_motion=True,
            )
        ],
    )


def test_only_unblocked_tasks_are_available() -> None:
    plan = _demo_plan()
    available = {task.id for task in list_available_tasks(plan)}
    assert available == {"ingest.sources"}


def test_task_status_update_blocks_on_dependencies() -> None:
    plan = _demo_plan()
    result = update_execution_task_status(
        plan=plan,
        task_id="plan.storyboard",
        new_status=TaskStatus.IN_PROGRESS,
        actor_role="coordinator",
    )
    assert result.success is False
    assert result.reason == "task_blocked"


def test_verification_nudge_when_non_review_tasks_done() -> None:
    plan = _demo_plan()

    update_execution_task_status(
        plan=plan,
        task_id="ingest.sources",
        new_status=TaskStatus.COMPLETED,
        actor_role="lead",
    )
    update_execution_task_status(
        plan=plan,
        task_id="summarize.research",
        new_status=TaskStatus.COMPLETED,
        actor_role="lead",
    )
    update_execution_task_status(
        plan=plan,
        task_id="plan.storyboard",
        new_status=TaskStatus.COMPLETED,
        actor_role="coordinator",
    )
    update_execution_task_status(
        plan=plan,
        task_id="render.seg-1.html",
        new_status=TaskStatus.COMPLETED,
        actor_role="html_worker",
    )
    update_execution_task_status(
        plan=plan,
        task_id="render.seg-1.manim",
        new_status=TaskStatus.COMPLETED,
        actor_role="manim_worker",
    )
    last_non_review = update_execution_task_status(
        plan=plan,
        task_id="render.seg-1.svg",
        new_status=TaskStatus.COMPLETED,
        actor_role="svg_worker",
    )
    assert last_non_review.success is True
    assert last_non_review.verification_nudge_needed is True

    result = update_execution_task_status(
        plan=plan,
        task_id="post_produce.package",
        new_status=TaskStatus.IN_PROGRESS,
        actor_role="lead",
    )

    assert result.success is False
    assert result.reason == "task_blocked"

    review_done = update_execution_task_status(
        plan=plan,
        task_id="review.outputs",
        new_status=TaskStatus.COMPLETED,
        actor_role="reviewer",
    )
    assert review_done.success is True
    assert review_done.verification_nudge_needed is False

    package = update_execution_task_status(
        plan, "post_produce.package", TaskStatus.COMPLETED, "lead"
    )
    assert package.success is True


def _task(
    task_id: str,
    *blocked_by: str,
    owner_role: str = "worker",
    status: TaskStatus = TaskStatus.PENDING,
    verification_required: bool = False,
) -> ExecutionTask:
    return ExecutionTask(
        id=task_id,
        subject=task_id,
        owner_role=owner_role,
        active_form=task_id,
        blocked_by=list(blocked_by),
        status=status,
        verification_required=verification_required,
    )


def _graph_plan(*tasks: ExecutionTask):
    plan = _demo_plan()
    plan.execution_tasks = list(tasks)
    return plan


def test_parallel_worker_branches_and_owner_filter() -> None:
    plan = _demo_plan()
    for task_id in ("ingest.sources", "summarize.research", "plan.storyboard"):
        assert update_execution_task_status(plan, task_id, TaskStatus.COMPLETED, "lead").success

    assert {task.id for task in list_available_tasks(plan)} == {
        "render.seg-1.html", "render.seg-1.manim", "render.seg-1.svg"
    }
    assert [task.id for task in list_available_tasks(plan, "manim_worker")] == [
        "render.seg-1.manim"
    ]
    for worker in ("html", "manim"):
        result = update_execution_task_status(
            plan, f"render.seg-1.{worker}", TaskStatus.COMPLETED, f"{worker}_worker"
        )
        assert result.success
        assert not result.verification_nudge_needed
    assert [task.id for task in list_available_tasks(plan)] == ["render.seg-1.svg"]
    review = update_execution_task_status(plan, "review.outputs", TaskStatus.COMPLETED, "reviewer")
    assert not review.success
    assert review.reason == "task_blocked"


@pytest.mark.parametrize("defect", [
    "missing_dependency", "duplicate_task_id", "self_dependency", "dependency_cycle"
])
@pytest.mark.parametrize("new_status", list(TaskStatus))
@pytest.mark.parametrize("target", ["a", "unrelated"])
def test_invalid_graph_fails_closed_without_mutation(defect, new_status, target) -> None:
    a = _task("a", status=TaskStatus.COMPLETED)
    b = _task("b", status=TaskStatus.COMPLETED)
    c = _task("c", status=TaskStatus.COMPLETED)
    plan = _graph_plan(a, b, c, _task("unrelated"))
    if defect == "missing_dependency":
        a.blocked_by = ["missing"]
    elif defect == "duplicate_task_id":
        plan.execution_tasks.append(replace(a, status=TaskStatus.PENDING))
    elif defect == "self_dependency":
        a.blocked_by = ["a"]
    else:
        a.blocked_by = ["b"]
        b.blocked_by = ["c"]
        c.blocked_by = ["a"]
    before = plan.to_dict()

    with pytest.raises(TaskGraphError, match=defect) as error:
        list_available_tasks(plan, owner_role="worker")
    assert "a" in str(error.value)
    if defect == "missing_dependency":
        assert "missing" in str(error.value)
    if defect == "dependency_cycle":
        assert "b" in str(error.value) and "c" in str(error.value)

    result = update_execution_task_status(plan, target, new_status, "lead")
    assert not result.success
    assert result.reason == "invalid_task_graph"
    assert result.graph_errors == error.value.errors
    assert result.invalidated_task_ids == []
    assert not result.verification_nudge_needed
    assert plan.to_dict() == before


def test_graph_is_revalidated_after_dependency_changes() -> None:
    plan = _graph_plan(_task("a"), _task("b", "a"))
    assert [task.id for task in list_available_tasks(plan)] == ["a"]
    plan.execution_tasks[0].blocked_by.append("missing")
    with pytest.raises(TaskGraphError, match="missing_dependency: a -> missing"):
        list_available_tasks(plan)
    result = update_execution_task_status(plan, "a", TaskStatus.COMPLETED, "worker")
    assert not result.success
    assert plan.execution_tasks[0].status == TaskStatus.PENDING


@pytest.mark.parametrize("task_id,owner_role,verification_required", [
    ("review.outputs", "reviewer", True),
    ("custom.review", "reviewer", False),
    ("custom.review", "quality_reviewer", True),
    ("custom.review", "quality_reviewer", False),
])
@pytest.mark.parametrize("initial_status", [TaskStatus.PENDING, TaskStatus.COMPLETED])
def test_only_independent_owner_can_complete_review(
    task_id, owner_role, verification_required, initial_status
) -> None:
    review = _task(
        task_id, owner_role=owner_role, status=initial_status,
        verification_required=verification_required,
    )
    plan = _graph_plan(review)
    if owner_role == "quality_reviewer":
        profile = next(profile for profile in plan.agent_profiles if profile.id == "reviewer")
        plan.agent_profiles.append(replace(profile, id=owner_role))
    before = plan.to_dict()

    rejected = update_execution_task_status(plan, task_id, TaskStatus.COMPLETED, "lead")
    assert not rejected.success
    assert rejected.reason == "independent_reviewer_required"
    assert plan.to_dict() == before
    accepted = update_execution_task_status(plan, task_id, TaskStatus.COMPLETED, owner_role)
    assert accepted.success
    assert accepted.invalidated_task_ids == []


@pytest.mark.parametrize("owner_role", ["lead", "coordinator"])
@pytest.mark.parametrize("task_id,verification_required", [
    ("review.outputs", False), ("custom.review", True)
])
def test_review_misassigned_to_producer_cannot_be_completed(
    owner_role, task_id, verification_required
) -> None:
    task = _task(task_id, owner_role=owner_role, verification_required=verification_required)
    plan = _graph_plan(task)
    result = update_execution_task_status(plan, task_id, TaskStatus.COMPLETED, owner_role)
    assert not result.success
    assert result.reason == "independent_reviewer_required"
    assert task.status == TaskStatus.PENDING


@pytest.mark.parametrize("new_status", [TaskStatus.PENDING, TaskStatus.IN_PROGRESS])
def test_lead_can_reopen_review_but_not_complete_it(new_status) -> None:
    review = _task("review.outputs", owner_role="reviewer", status=TaskStatus.COMPLETED)
    package = _task("package", review.id, status=TaskStatus.COMPLETED)
    plan = _graph_plan(review, package)
    result = update_execution_task_status(plan, review.id, new_status, "lead")
    assert result.success
    assert result.invalidated_task_ids == [package.id]
    assert review.status == new_status
    assert package.status == TaskStatus.PENDING
    assert result.verification_nudge_needed


@pytest.mark.parametrize("actor", ["worker", "lead"])
def test_non_review_completion_keeps_owner_and_lead_compatibility(actor) -> None:
    task = _task("work")
    plan = _graph_plan(task)
    result = update_execution_task_status(plan, task.id, TaskStatus.COMPLETED, actor)
    assert result.success
    assert result.from_status == "pending"
    assert result.to_status == "completed"
    assert result.reason is None
    assert result.invalidated_task_ids == []
    assert result.graph_errors == []
    assert not result.verification_nudge_needed


@pytest.mark.parametrize("task_id,actor,reason", [
    ("unknown", "lead", "task_not_found"),
    ("work", "reviewer", "owner_mismatch"),
    ("review.outputs", "worker", "owner_mismatch"),
])
def test_rejected_update_preserves_all_task_states(task_id, actor, reason) -> None:
    plan = _graph_plan(_task("work"), _task("review.outputs", "work", owner_role="reviewer"))
    before = plan.to_dict()
    result = update_execution_task_status(plan, task_id, TaskStatus.COMPLETED, actor)
    assert not result.success
    assert result.reason == reason
    assert result.invalidated_task_ids == []
    assert plan.to_dict() == before


@pytest.mark.parametrize("new_status", [TaskStatus.PENDING, TaskStatus.IN_PROGRESS])
def test_reopening_worker_invalidates_review_package_and_preserves_other_branches(new_status) -> None:
    plan = _demo_plan()
    for task in plan.execution_tasks:
        task.status = TaskStatus.COMPLETED
        task.blocks = []
    task_by_id = {task.id: task for task in plan.execution_tasks}
    worker_id = "render.seg-1.manim"

    result = update_execution_task_status(plan, worker_id, new_status, "manim_worker")
    assert result.success
    assert result.from_status == "completed"
    assert result.to_status == new_status.value
    assert result.invalidated_task_ids == ["review.outputs", "post_produce.package"]
    assert not result.verification_nudge_needed
    for task in plan.execution_tasks:
        expected = (
            new_status if task.id == worker_id
            else TaskStatus.PENDING if task.id in result.invalidated_task_ids
            else TaskStatus.COMPLETED
        )
        assert task.status == expected
    assert update_execution_task_status(
        plan, "post_produce.package", TaskStatus.COMPLETED, "lead"
    ).reason == "task_blocked"

    repaired = update_execution_task_status(plan, worker_id, TaskStatus.COMPLETED, "manim_worker")
    assert repaired.success and repaired.verification_nudge_needed
    assert task_by_id["review.outputs"].status == TaskStatus.PENDING
    assert update_execution_task_status(
        plan, "review.outputs", TaskStatus.COMPLETED, "lead"
    ).reason == "independent_reviewer_required"
    assert update_execution_task_status(
        plan, "review.outputs", TaskStatus.COMPLETED, "reviewer"
    ).success
    assert update_execution_task_status(
        plan, "post_produce.package", TaskStatus.COMPLETED, "lead"
    ).success


def test_invalidation_traverses_pending_nodes_and_deduplicates_diamond() -> None:
    root = _task("root", status=TaskStatus.COMPLETED)
    plan = _graph_plan(
        _task("join", "left", "right", status=TaskStatus.COMPLETED),
        _task("left", "root", status=TaskStatus.COMPLETED),
        _task("right", "root", status=TaskStatus.IN_PROGRESS),
        _task("bridge.output", "bridge", status=TaskStatus.COMPLETED),
        _task("bridge", "root"),
        root,
        _task("unrelated", status=TaskStatus.COMPLETED),
        _task("unrelated.child", "unrelated", status=TaskStatus.IN_PROGRESS),
    )
    root.blocks = ["unrelated"]
    result = update_execution_task_status(plan, root.id, TaskStatus.PENDING, "worker")
    assert result.success
    assert result.invalidated_task_ids == ["join", "left", "right", "bridge.output"]
    assert [task.status for task in plan.execution_tasks] == [
        *([TaskStatus.PENDING] * 6), TaskStatus.COMPLETED, TaskStatus.IN_PROGRESS
    ]
    assert {task.id for task in list_available_tasks(plan)} == {"root"}


def test_deep_graph_validation_and_invalidation_do_not_recurse() -> None:
    tasks = [_task("0", status=TaskStatus.COMPLETED)]
    tasks.extend(
        _task(str(i), str(i - 1), status=TaskStatus.COMPLETED) for i in range(1, 1100)
    )
    plan = _graph_plan(*reversed(tasks))
    result = update_execution_task_status(plan, "0", TaskStatus.PENDING, "worker")
    assert result.success
    assert result.invalidated_task_ids == [str(i) for i in range(1099, 0, -1)]
    assert all(task.status == TaskStatus.PENDING for task in tasks)


def test_idempotent_completion_does_not_invalidate_downstream() -> None:
    plan = _graph_plan(
        _task("upstream", status=TaskStatus.COMPLETED),
        _task("downstream", "upstream", status=TaskStatus.COMPLETED),
    )
    before = plan.to_dict()
    result = update_execution_task_status(plan, "upstream", TaskStatus.COMPLETED, "worker")
    assert result.success
    assert result.invalidated_task_ids == []
    assert plan.to_dict() == before


def test_rejected_reopen_does_not_invalidate_descendants() -> None:
    plan = _graph_plan(
        _task("blocker"),
        _task("upstream", "blocker", status=TaskStatus.COMPLETED),
        _task("downstream", "upstream", status=TaskStatus.COMPLETED),
    )
    before = plan.to_dict()
    result = update_execution_task_status(plan, "upstream", TaskStatus.IN_PROGRESS, "worker")
    assert not result.success
    assert result.reason == "task_blocked"
    assert result.invalidated_task_ids == []
    assert plan.to_dict() == before


def test_verification_nudge_ignores_transitive_downstream_and_unrelated_tasks() -> None:
    plan = _graph_plan(
        _task("work"),
        _task("review.outputs", "work", owner_role="reviewer"),
        _task("package", "review.outputs"),
        _task("publish", "package"),
        _task("unrelated"),
    )
    result = update_execution_task_status(plan, "work", TaskStatus.COMPLETED, "worker")
    assert result.success
    assert result.verification_nudge_needed


def test_result_defaults_remain_compatible_and_are_not_shared() -> None:
    first = TaskMutationResult(True, "a", "pending", "completed")
    second = TaskMutationResult(True, "b", "pending", "completed")
    first.invalidated_task_ids.append("child")
    first.graph_errors.append("diagnostic")
    assert asdict(second) == {
        "success": True,
        "task_id": "b",
        "from_status": "pending",
        "to_status": "completed",
        "reason": None,
        "verification_nudge_needed": False,
        "invalidated_task_ids": [],
        "graph_errors": [],
    }


def test_empty_graph_is_valid_but_has_no_available_tasks() -> None:
    plan = _graph_plan()
    assert list_available_tasks(plan) == []
    result = update_execution_task_status(plan, "unknown", TaskStatus.COMPLETED, "lead")
    assert not result.success
    assert result.reason == "task_not_found"
