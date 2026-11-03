# 历史 CLI 与审计隔离

基础计划命令 `plan/context-pack/task-update` 保持可用。旧 `pipeline-run` 和 `assemble-video` 归为历史实验，默认在 CLI 边界阻断；显式的 `--legacy-experiment` 仅用于复现旧实验。

课程生产使用 [当前监督入口](../docs/formula-continuity-v3.md)、独立回归以及原音字幕发布链。

## 已隔离范围

- CLI 在读取 manifest、启动渲染、读取 API 配置之前拒绝默认旧制作调用。
- 旧 pipeline 的 CLI 汇总区分执行完成和 reviewer 批准；block/缺少 review 时返回失败退出码。
- 旧拼接器和 Orchestrator 的直接 Python API 保留原字节，其冻结实现仍有审计中记录的风险。显式实验开关不提供发布批准。

## 后续修复

`postproduce/assembler.py` 在固定保护前缀内；`agents/reviewer.py`、`agents/orchestrator.py` 在原声 input-bindings 中。主控解除对应实现冻结后，另立版本修复：拼接器要求当前审核绑定、Reviewer 证据覆盖预期镜头、流水线按 verdict 失败阻断。验证旧来源可继续读取，再独立测试新发布路径。

本页是代码边界与剩余风险说明，实际 CLI 行为由 `tests/test_legacy_cli_boundary.py` 检查。初始现场证据保留在[仓库审计](../docs/仓库现状审计-20261103.md)。
