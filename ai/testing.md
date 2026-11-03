# 测试分层

| 层次 | 典型入口 | 运行条件 |
| --- | --- | --- |
| 纯编排 | `tests/test_workflow.py`、`tests/test_task_board.py` | Python、pytest |
| 仓库整理 | `tests/test_repository_organization.py`、`tests/test_legacy_cli_boundary.py` | 本轮公开迁移清单；无付费调用 |
| 媒体工具 | 字幕、拼接、单元发布相关测试 | FFmpeg/libass，使用测试目录 |
| 原生对象/字形 | component/native、typography | ManimGL、字体、TeX，按具体测试条件 |
| 本机素材 | 冻结 WAV、旧 candidate、真实计划 | 保留 native 来源的本机工作区 |
| 外部服务 | API、Windows 声音、GPU | 操作者单独授权并记录实际结果 |

离线验证设置 `MANIMIND_DISABLE_DOTENV=1`，不要收集或输出运行环境中的密钥。测试临时目录放在测试器自己的 session 或系统临时目录，不写在其他作者 session。

旧 `test_projectile_formula_motion_full.py` 的本机 candidate 依赖已通过保留原文归档与可移植后继测试处理：原测试和场景在 `archive/legacy/`，五项源回归由 `tests/test_projectile_source_snapshot.py` 继续执行，原始 candidate 字节快照在 `tests/fixtures/legacy-projectile/`。新测试读取公开 fixture，制作来源的 `outputs/` 原件与既有批准保持原样。

本轮新增仓库检查只证明公开导航、迁移 SHA、私密忽略边界及 CLI 隔离。当前八课的 native bindings、视频像素、字幕和听感由主控独立验收并记录。

默认仓库检查允许公开克隆缺少 `archive/local/`，本机存在时仍核 SHA；维护者使用 `python scripts/check_repository_organization.py --require-local` 验收完整本机归档。`local_only_20261103` 目录快照的公开 URL 为 null；后续真实发布可使用独立核验的发布收据，绑定 URL、全部资产 SHA 及收据 SHA，不受本轮快照的 null 规则永久限制。

安装脚本当前按版本范围解析依赖，wheel 发现范围为 `src`。锁定安装、包外 API 和全新机器媒体复现是单独工程项，验收时分别报告。
