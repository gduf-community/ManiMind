# 2026-11-03 仓库整理

本次把人类阅读入口、AI 执行资料、公开历史和本机证据分开。完整旧内容按批次物理迁移，原生来源继续留在原路径。

## 机器清单

- 移前计划：`runtime/sessions/repository-organization-20261103/migration-plan-v003.json`
- 原生依赖闭包：同目录 `native-dependency-closure-v003.json`
- 每批复核：`preflight-<batch>.json`
- 物理移动前后：`move-before-<batch>.json`、`move-after-<batch>.json`
- 回退原字节：同目录 `source-backup/<old-path>`
- 可公开的精简结果：[迁移清单](../../archive/migrations/20261103/manifest.json)

v001 为初始宽范围扫描，包含测试临时副本；v002 排除明确测试临时命名空间。v003 增加主控精确放行的 owned 文档：旧 scope-reading、政策背景和 course-context-plan 阅读来源保留为历史证据，区别于当前执行器/门禁直接哈希依赖。旧 source_snapshot、课程 plan 和报告本身保持原样。

第二批原执行 99 项；主控全套测试发现 `pilot.SCENE → full_lesson.init` 仍实际消费 `examples/instantaneous_velocity.py`，已按原 SHA rename 恢复该源、不改共享 helper，撤回这一条当前迁移。第二批当前归档 98 项，合计当前迁移 153 项。原 plan 和批次 before/after 保留，另见[撤回记录](../../archive/migrations/20261103/rollback-instantaneous-v001.json)；原测试继续保留完整覆盖。

其余为 13 个闲置实验模块、25 个非导数历史场景、32 个原测试、21 个历史配置、7 个 API 原型文件。每批重新算消费闭包和 SHA，并核新进程导入、01 caption bindings 与 pytest collect-only。当前源码、原声重建与额度观察工具继续保留。

## 暂留原路径

derivative 示例与当前测试、postproduce/components/review/render/curriculum、所有实际 native stage 输入及 `runtime/outputs` 原生证据维持原路径。experiments 中经实际消费核对的闲置项已按第二批明确放行迁移，当前 helper、共享库及操作工具保留。`docs/understanding-workflow.md`、`docs/remote-speech.md` 本轮为 `deferred_frozen`；此类文件不计物理归档数。

单独批准的 7 个本机历史项已同盘 rename 至 `archive/local/`，含 40 个文件。`opaque-before-v001.json`、`opaque-after-v001.json` 保存完整私密映射和树摘要；公开 map 仅给分组与数量。验证范围为相对树/inode/device/size/mode 元数据，不冒充文件内容校验。当前环境、凭据和项目本机工具配置继续保留原位置。

## 回退与失效

迁移协调者写计划、清单与字节备份，主控/维护者消费。每批状态 create-only，保留至迁移验收结束；新增原生引用、源 SHA 或路径变化即要求重新 preflight。公开文件的相对链接修正单列裁剪/修改记录，原始字节仍在 session 备份。回退前先核目标 SHA 与主控并行修改，再从备份恢复指定文件，保持其他作者内容。

## 公开边界

扫描只输出文件位置、行号和类型。带账号主机路径或网络信息的历史原文进入 `archive/local/`；环境、原始请求/日志、私有素材和迁移包沿用本机忽略边界。公共索引记录真实本机可获取位置，云端发布地址经主控核准后补入。
