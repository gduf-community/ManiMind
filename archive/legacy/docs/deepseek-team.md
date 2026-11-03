# DeepSeek 三角色隔离协作实验

## 目的与边界

项目 `deepseek-team-20261023` 从空白上下文重新制作平抛动画，不继承旧候选。
导演/主控、创作者、独立审片全部使用 `deepseek-flash`，开启思考，强度 `max`。
导演可以自己提出内容建议并组织返工；GPT 只实现执行器，不创作或修改任何候选内容。
没有费用、调用数、渲染数或返工轮数上限。故障保护不是制作预算。

输入仅为冻结的公共任务、物理事实、通用运行接口，以及各角色本轮产生的内容。
不读取主对话、记忆、旧片、旧讲稿、其他实验审核、GPT 修改建议。
主控和创作者有各自工作记录，委托/回报原样传递；审片者不接收这些记录。
本轮不包含 6.1 Sol。后续同题模型比较应新建实验 ID，不把本轮成片或反馈当作参考输入。

## 执行与门禁

入口为 `src/manimind/experiments/freeform_team.py`，复用已有媒体工具、静态代码检查和 macOS 沙箱，不修改旧实验实现。

1. 主控自主写计划、测量配音，或原样委托创作者。
2. 创作者自主实现、查 ManimGL API、渲染、分段看图、返工，再回报主控。
3. 主控亲自检查本版每段真实抽帧。创作者的自检不能代替主控观察。
4. 独立审片使用新上下文，分组和全片审核当前讲稿、源码、实测时间轴及原始分辨率帧。每组可以请求额外取帧，并有一次纯结构错误自修复。
5. 原始审核结果交还主控。任一组要求返工即不允许发布；内容或渲染变化使双方检查覆盖和当前批准失效。
6. 全部分组与全片通过后，主控可调用 `finish`。机械适配器核对真实 reviewer 原答、输入及媒体哈希，再进入已有合成门禁，不代改审核结论。

审片是同模型异上下文审核，不是异模型共识、连续播放或实际听审，也不代表学生理解测试通过。
最终只称审核后的配音预览，不称学校可销售成品。旧 `delivery.json` 的监督试片标签由共享媒体组件继承；`team-delivery.json` 明确监督者是 DeepSeek，而非 GPT。
原稿没有任意文件、shell、网络工具。静态筛选和沙箱仍不是对抗性安全证明。

## 状态归属

| 路径 | 写入者 / 消费者 | 生命周期与失效 |
|---|---|---|
| `runtime/projects/<id>/isolation.json`、`agent-protocol.json`、`collaboration-protocol.json` | 初始化器 / 各角色、审计者 | 首次调用前冻结；配置或实现指纹变化即停机，不刷新覆盖 |
| 同目录 `authorship.json` | 原答提取器 / 渲染器、来源验证 | 当前模型讲稿来源；改稿保留旧版，重新绑定新原答 |
| 同目录 `review.json` | 独立结论的机械适配器 / 发布门禁 | 只对绑定的当前候选有效；内容、媒体、字体、时间轴变化失效 |
| `runtime/sessions/<id>-generation/team-state.json` | 编排器 / 下轮角色、审计者 | 本轮完整工作记录、委托、活动角色、检查覆盖、未决操作、计时；每步原子检查点，媒体变化清空覆盖 |
| 同目录 `agent-state.json` | 媒体工具 / 下次工具、审核器 | 渲染收据及媒体状态；新稿或重渲染使旧收据失效 |
| 同目录 `team-step-NNNN/` | 工具执行器 / 下一角色、审计者 | 原命令、来源哈希、结果和被替换版本；保留，不移入长期提示 |
| `<id>-director/`、`<id>-generation/`、`<id>-independent-review/` 的 `request-NNNN/` | 各角色请求器 / 各自上下文、账本、审计者 | 原输入、原答、用量、进度；失败与截断也保留，不默认为零成本 |
| `<id>-independent-review/cycle-NN/` | 审片器 / 主控、发布门禁 | 当前轮原始证据和审核；改稿后只可作历史反馈，不可作新批准 |
| `outputs/<id>/` | 原答提取器、渲染与合成器 / 角色、观众 | 源码、讲稿、时间轴、版本化无声片及真实帧；发布后成片不覆盖 |
| 同目录 `cost-report.json`、`timing-report.json` | 账本汇总器 / 审计者 | 可从请求重建；三角色全部尝试计入，未知费用单列；工程时间不混入模型制作时间 |
| 同目录 `team-delivery.json` | 发布适配器 / 观众、审计者 | 不可变交付来源；视频或审核变动失效 |
| `team.lock` | 当前执行器 / 其他执行器 | 运行期间排他，退出删除；崩溃残留需核实 PID 后处理，不盲目启动重复收费进程 |

`team-state` 状态为 `ready -> running -> complete/model_stopped/repeated_identical_failure`。
服务或执行异常进入 `execution_stopped`，用户/进程打断进入 `interrupted`，保留 `inflight`。
只有确认原请求完整接收且尚未开始工具时，才能原样恢复已收响应；未知是否执行过的工具不自动重放。

## 运行与验证

```bash
manimgl_env/bin/python -m pytest -q tests/test_freeform_team.py
manimgl_env/bin/python -m manimind.experiments.freeform_team --config configs/deepseek-team-20261023.json --initialize-only
caffeinate -i manimgl_env/bin/python -m manimind.experiments.freeform_team --config configs/deepseek-team-20261023.json
```

启动前确认无现存进程。没有未决操作的正常检查点可用同命令续跑。
`--resume-received-request` 只重放同上下文中已经完整收到、来源未变、尚未执行工具的原答，不再次调用 API。
传输失败、截断、未返回用量不自动重试，需核对证据后再决定；不可删除请求记录或擅自清空 `inflight`。
三次内容未变的相同失败动作触发故障停机。锁与这些停机条件不会限制正常返工次数。

模型制作计时从第一条主控请求开始，API 时间包含网络等待；审片工具耗时含 reviewer API 时间，不可重复相加。
价格按调用前核验的官方单价估算，分缓存/时段上下界，非账单；不含编排器开发、TTS、渲染电费及事后对比。
Codex 历史样片的约 47 分钟包含部分工程工作，工具权限与审片采样也不同，因此只能比较生产方案，不能宣称严格同条件模型排名。
