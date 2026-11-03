"""执行任务状态机与验证关卡检查。"""

from __future__ import annotations

from dataclasses import dataclass, field
from graphlib import CycleError, TopologicalSorter

from .models import AgentMode, ExecutionTask, ProjectPlan, TaskStatus


@dataclass(slots=True)
class TaskMutationResult:
    success: bool
    task_id: str
    from_status: str | None
    to_status: str | None
    reason: str | None = None
    verification_nudge_needed: bool = False
    invalidated_task_ids: list[str] = field(default_factory=list)
    graph_errors: list[str] = field(default_factory=list)


class TaskGraphError(ValueError):
    """任务图无效；errors 包含可定位到任务 ID 的诊断。"""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("invalid_task_graph: " + "; ".join(errors))


def _task_index(plan: ProjectPlan) -> dict[str, ExecutionTask]:
    # blocked_by is authoritative; blocks may be absent or stale.
    index: dict[str, ExecutionTask] = {}
    errors: list[str] = []
    for task in plan.execution_tasks:
        if task.id in index:
            errors.append(f"duplicate_task_id: {task.id}")
        else:
            index[task.id] = task
    for task in plan.execution_tasks:
        for blocker in task.blocked_by:
            if blocker == task.id:
                errors.append(f"self_dependency: {task.id}")
            elif blocker not in index:
                errors.append(f"missing_dependency: {task.id} -> {blocker}")
    if errors:
        raise TaskGraphError(errors)

    try:
        TopologicalSorter({task.id: task.blocked_by for task in index.values()}).prepare()
    except CycleError as exc:
        cycle = " -> ".join(exc.args[1])
        raise TaskGraphError([f"dependency_cycle: {cycle}"]) from exc
    return index


def _is_unblocked(task: ExecutionTask, index: dict[str, ExecutionTask]) -> bool:
    for blocker in task.blocked_by:
        blocker_task = index.get(blocker)
        if blocker_task is None or blocker_task.status != TaskStatus.COMPLETED:
            return False
    return True


def list_available_tasks(plan: ProjectPlan, owner_role: str | None = None) -> list[ExecutionTask]:
    """列出可执行任务；无效 DAG 抛出 TaskGraphError，不放行任何分支。"""
    index = _task_index(plan)
    candidates = [
        task
        for task in plan.execution_tasks
        if task.status == TaskStatus.PENDING and _is_unblocked(task, index)
    ]
    if owner_role is not None:
        candidates = [task for task in candidates if task.owner_role == owner_role]
    return candidates


def _invalidate_downstream(task_id: str, index: dict[str, ExecutionTask]) -> list[str]:
    """重开时重置所有后代，按计划顺序报告实际发生状态回退的任务。"""
    dependents: dict[str, list[str]] = {item_id: [] for item_id in index}
    for task in index.values():
        for blocker in task.blocked_by:
            dependents[blocker].append(task.id)

    downstream: set[str] = set()
    pending = list(dependents[task_id])
    while pending:
        item_id = pending.pop()
        if item_id not in downstream:
            downstream.add(item_id)
            pending.extend(dependents[item_id])

    invalidated = []
    for task in index.values():
        if task.id in downstream and task.status != TaskStatus.PENDING:
            task.status = TaskStatus.PENDING
            invalidated.append(task.id)
    return invalidated


def update_execution_task_status(
    plan: ProjectPlan,
    task_id: str,
    new_status: TaskStatus,
    actor_role: str,
) -> TaskMutationResult:
    """按依赖规则更新状态；重开已完成任务会使下游执行状态失效。

    失效清单仅属于本次更新结果，由调用方消费或持久化，不另存长期状态。
    actor_role 沿用可信调用方提供的角色，不在此接口内进行身份认证。
    """
    try:
        index = _task_index(plan)
    except TaskGraphError as exc:
        return TaskMutationResult(
            success=False,
            task_id=task_id,
            from_status=None,
            to_status=new_status.value,
            reason="invalid_task_graph",
            graph_errors=exc.errors,
        )
    task = index.get(task_id)
    if task is None:
        return TaskMutationResult(
            success=False,
            task_id=task_id,
            from_status=None,
            to_status=new_status.value,
            reason="task_not_found",
        )

    if actor_role not in {task.owner_role, "lead"}:
        return TaskMutationResult(
            success=False,
            task_id=task_id,
            from_status=task.status.value,
            to_status=new_status.value,
            reason="owner_mismatch",
        )

    reviewer_roles = {"reviewer"} | {
        profile.id for profile in plan.agent_profiles if profile.mode == AgentMode.VERIFY_ONLY
    }
    is_review = (
        task.verification_required
        or task.id == "review.outputs"
        or task.owner_role in reviewer_roles
    )
    if new_status == TaskStatus.COMPLETED and is_review and (
        actor_role != task.owner_role or actor_role not in reviewer_roles or actor_role == "lead"
    ):
        return TaskMutationResult(
            success=False,
            task_id=task_id,
            from_status=task.status.value,
            to_status=new_status.value,
            reason="independent_reviewer_required",
        )

    if new_status in {TaskStatus.IN_PROGRESS, TaskStatus.COMPLETED} and not _is_unblocked(task, index):
        return TaskMutationResult(
            success=False,
            task_id=task_id,
            from_status=task.status.value,
            to_status=new_status.value,
            reason="task_blocked",
        )

    previous = task.status
    task.status = new_status
    invalidated_task_ids = []
    if previous == TaskStatus.COMPLETED and new_status in {TaskStatus.PENDING, TaskStatus.IN_PROGRESS}:
        invalidated_task_ids = _invalidate_downstream(task_id, index)

    review_task = index.get("review.outputs")
    verification_nudge_needed = (
        review_task is not None
        and review_task.status != TaskStatus.COMPLETED
        and _is_unblocked(review_task, index)
    )

    return TaskMutationResult(
        success=True,
        task_id=task_id,
        from_status=previous.value,
        to_status=new_status.value,
        verification_nudge_needed=verification_nudge_needed,
        invalidated_task_ids=invalidated_task_ids,
    )
