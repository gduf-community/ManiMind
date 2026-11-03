# Agent 与执行工具导航

组员从[项目首页](../README.md)和[制作流程](../docs/开始制作.md)进入。本目录集中维护 Agent 执行规则、精确契约、测试边界和迁移记录。

## 加载顺序

1. 根 [AGENTS.md](../AGENTS.md) 与当前任务中的保护范围
2. [完整 Agent 规则](AGENT_RULES.md)
3. [强前置条件](contracts/强前置条件约束.md)
4. [执行架构详解](architecture/执行架构详解.md)、[模块与状态详解](architecture/模块与状态详解.md)

## 当前课程链

创作和交接时同时参考[跨题材自检](创作与交接自检.md)：分清变量状态与条件、核对调参过程，并把观看覆盖、实际缺陷和报告格式分开记录。

| 事项 | 当前契约 |
| --- | --- |
| 课程 context 与连续意群 | [course-unit-workflow](../docs/course-unit-workflow.md) |
| 公式动作创作建议 | [公式动画创作引导](../docs/公式动画创作引导.md) |
| 公式取证、正式稿安装、静音发布 | [formula-continuity-v3](../docs/formula-continuity-v3.md)，`traceable_film_v3` |
| 既有作品的独立内容回归 | [content-regression](../docs/content-regression.md) |
| 讲稿运算对象 | [数学讲稿口述引导](../docs/数学讲稿口述引导.md) |
| 原音、意群、单套字幕 | [理解优先契约](../docs/understanding-workflow.md)及 [焦点字幕](reference/focus-captions.md) |
| 整章交付 | [逐课及整章交付](../docs/导数整章交付.md)、[整章帧时钟](../docs/整章合并时钟.md) |

以上 native 契约维持原路径与字节；导航不升级旧批准。监督器、plan、媒体、原生索引和报告按当前版本核对，收据失败从已完成的媒体断点继续。

## 技术参考与历史

- [上下文与状态](reference/上下文与状态设计.md)、[角色数据协议](reference/agent-data-protocol.md)
- [通用组件](reference/component-foundation.md)、[第三方整合](reference/第三方整合.md)
- [历史 CLI 隔离](legacy-cli.md)、[测试分层](testing.md)
- [归档与冻结迁移](migrations/README.md)、[历史实验资料](../archive/README.md)
- [当前模块与历史源码定位](architecture/当前模块与历史源码.md)

`docs/understanding-workflow.md` 与 `docs/remote-speech.md` 仍在原生来源闭包内。涉及本机主机/账号的资料保存在本机忽略区；公开导航仅给出通用契约与维护者入口。

## 协作状态

新增持久状态须同时给出 writer、consumers、lifecycle、invalidation。长期项目事实进入 `runtime/projects`；本轮交接、审核和迁移操作进入 `runtime/sessions`。作者撤回交接时保留旧包并明确 supersedes；协调者停止派发该旧版本，新版本重新取证。
