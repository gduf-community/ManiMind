# GPT-6.1 Sol 订阅协作实验

项目为 `sol61-team-20261023`，模型固定为 `gpt-6.1-sol`，三个角色均使用 `max` 推理。
公共任务与 `deepseek-team-20261023` 相同。任务只规定知识目标、物理事实和审核标准，不输入旧片、旧稿、旧审核、主对话或记忆。

复用 `freeform_team.py` 的角色交接、原始分辨率分段和全片审核、原始意见返工、版本失效与发布门禁。仅在新增 `codex_cli_team.py` 适配订阅 CLI，不修改已冻结的 DeepSeek 执行器。此处用 Codex 的原生系统包装，DeepSeek 用直接 API；这是比较解释时必须保留的运行条件差异。

每轮 `codex exec` 都是全新 `--ephemeral` 会话，不恢复主聊天；关闭用户配置、项目文档注入、记忆、插件、原生 shell、浏览器及多 Agent 工具。模型仅返回公共 JSON 动作，实际媒体工具仍由同一执行器运行。角色合同只作模型身份替换，不改模型原答。单次原生推理出现额外工具调用即停机，不能作为成功响应执行。

长期协议、讲稿来源与批准在 `runtime/projects/<id>/`。短期角色历史、请求、原答、调用参数、CLI `events.jsonl`、错误及进程进度在 `runtime/sessions/<id>-{generation,director,independent-review}/`。媒体、实测时间轴、成本、耗时和交付证明在 `outputs/<id>/`。状态写入者、消费者与失效规则沿用 [三角色实验](deepseek-team.md)。

新增请求事件由 CLI 写入、账本解析器消费，生命周期为本轮原始调用证据；只要事件缺失、使用原生额外工具、退出异常或没有完整用量，就不执行原答。调用参数、输入和原答绑定哈希；旧证据不覆盖。CLI 不自动重放未决制作步骤。

`launcher.json` 由后台启动器写入、操作者和重复启动防护消费，仅对记录的进程存活期间有效；进程退出后仍需核对未决状态。短期 `launch.lock` 排除并发启动，创建完进程即释放；`runner.log` 保留本轮执行输出。运行时 `team.lock` 仍由原执行器管理。

`runtime/projects/<id>/quota-snapshots.json` 由主协调者读取账户用量工具后追加，供费用审计与用户核对。先记接入前，再记正式制作起点和终点；重置时间或账号变化必须分段。它是账号级用量，可能包含同时进行的其他 Codex 工作，不能冒充单任务精确扣费。

`experiments/subscription_quota.py` 是独立的只读记账配套程序，不进入模型上下文，也不修改冻结的制作实现。它仅调用官方 `account/rateLimits/read`，不创建模型轮次。每 30 秒追加短期 `quota-samples.jsonl`，输出派生 `quota-report.json`，由费用审计消费；团队结束或连续读数失败即退出。`quota-capture.lock` 由该记录器写入，在进程退出时删除。重置或窗口变更使简单起终差值失效，未知读数不能计零。

`cost-report.json` 由请求记录重建每个角色的输入、缓存、输出 token，以及按官方 Standard 购买额度费率计算的等价值。该等价值不是订阅已扣额度，也不能直接换成订阅周百分比。工程准备/传输验证与正式制作时间分别记录；所有失败用量保留，未知值不按零处理。额度刷新时不可简单相减起终百分比。

发布关卡复用父类的实际 reviewer 原答、输入图片和媒体哈希验证，再机械校正继承的历史模型标签。讲稿、场景、审核语义不变。`review.json`、`delivery.json`、`team-delivery.json` 中明确记录 Sol 身份和最终审核哈希。审核证据是抽帧与源码、时间轴，未进行连续播放听审或学生理解测试。

```bash
manimgl_env/bin/python -m manimind.experiments.codex_cli_team --config configs/sol61-team-20261023.json --initialize-only
manimgl_env/bin/python -m manimind.experiments.codex_cli_team --config configs/sol61-team-20261023.json --background
```
