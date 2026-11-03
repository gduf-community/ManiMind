# API 模型评测与历史实验

路线更新：2026-10-15。目标是测量“合格视频的总生产成本”，不是只比较每百万 token 报价。当前试验入口是 `python -m manimind.experiments.model_benchmark`，与原 `pipeline-run`、精修 `pilot` 分开，不修改原片。

## 当前决策：只做 API 验证

用户已决定放弃当前阶段的本地模型部署，不连接学校服务器，不下载模型权重。保留历史配置和研究记录，但不将它们作为当前实施计划。模型推理改走云 API，动画渲染仍在现有机器上进行。

先以 `mimo-pro`（MiMo-V2.6-Pro）做同题验证，再用 `glm-flash`（GLM-5.3-Flash，Z.ai 普通 API）比较质量与成本。这是试验顺序，不是已经测出的能力排名，也不意味着最终必须采用双模型。新模型接口、参数和价格于 2026-10-15 按官方文档核验；历史 profile 未在本次重新核验。

官方直连配置目前仅完成离线测试，没有这两家的成片结果。未替换主 `pipeline-run` 的现有 `.env` 默认模型。先通过试验入口取得独立审核通过的视频，再决定主工作流的模型。

用户随后指定 `https://mimo.ezlook.top/v1`，对应独立 profile `mimo-ezlook-pro`。它不是小米官方域名，使用单独的 `MIMO_EZLOOK_API_KEY`，不复用 `MIMO_API_KEY` 或 `OPENAI_API_KEY`。2026-10-15 已通过带鉴权的模型列表查询，该网关列出了 `mimo-v2.6-pro`；这不能证明上游模型身份、服务质量或官方价格适用。网关价格尚未核实，`pricing=null`，费用显示未知而非免费。请求中的教案和提示词会交给该网关处理，学校内部资料需另行确认授权。

同日通过 OpenAI 兼容 SDK 做了一次短请求：关闭思考、输出预算 64 token、无重试、禁止 HTTP 重定向。服务端返回模型名 `mimo-v2.6-pro`，回答正确，finish_reason=stop，输入 92 / 输出 1 token，约 3.708 秒。专用密钥已存入被 Git 忽略且权限为 `0600` 的 `.env`，其他配置保持不变；报告不含密钥或回答正文。证据：`runtime/sessions/mimo-ezlook-connect-20261015-042402/connection.json`。这是连通性验证，不是思考模式、长代码生成或成片质量测试，也不是一条合格视频的费用。

## 2026-10-15 MiMo 整片生成实测

用户授权后，以 `mimo-ezlook-pro` 在 `mimo-ezlook-velocity-20261015` 运行固定 88.7 秒教案的整片视觉代码生成。没有提供原精修源码，思考模式开启，最多两次生成；未由 Codex 编写替代场景。

| 请求 | 输出预算（含思考） | API 耗时 | 服务端用量与结果 |
| --- | --- | --- | --- |
| 01 | 16384 | 89.618 秒 | 输入 4423、输出 16384；其中 reasoning_tokens=16384，finish_reason=length，客户端拒绝截断结果，没有可用源码 |
| 02 | 显式提高至 65536 | 600.961 秒 | APITimeoutError，无响应模型或 usage，没有可用源码 |

第二次预算调整在调用前告知用户并记录于短期 `budget-policy.json`，默认配置仍为 16384。这不是等预算横评，也不是第二次运行已经消耗 65536 token；超时调用的实际用量未知。两次 API 等待合计约 **690.579 秒（11 分 31 秒）**，不含检查与调试时间。

本轮模型源码数、渲染视频数、审核通过成片数均为 **0**。输出目录中的配音和时间轴是固定输入副本，不是新生成的视频。未渲染、未拼接、未覆盖原片。网关价格未知，且第二次未返回 usage，因此金额保持 `null`，不能称为免费或套用小米官方价格。

证据：`runtime/sessions/mimo-ezlook-velocity-20261015-generation/attempts.json`、`prompt-01.json`、`prompt-02.json`、`feedback.txt`、`budget-policy.json`，以及 `outputs/mimo-ezlook-velocity-20261015/cost.json`。独立审核落在 `runtime/projects/mimo-ezlook-velocity-20261015/review.json`。

本轮仅证明该网关、模式、整片任务和时限组合未跑通，不能评价模型的视觉生成质量，不能断言超时来自上游模型而非网关。下一轮应单独记录条件：先用非思考模式生成一个短镜头，或采用支持进度与中断记录的流式请求，再测完整片段；不继续盲目放大整片预算。上述下一轮尚未执行，也不以新 run-id 隐藏本轮失败。

## 2026-10-15 非思考短镜头验证

新增独立 profile `mimo-ezlook-fast`，同一网关和服务端模型名，`thinking.type=disabled`，temperature=0.6，单次超时 180 秒；不修改旧思考模式的实验记录。首次短片选择 `half tenth approach` 三句，保持一套连续几何，源时间段 28.7 至 47.5667 秒，目标时长 18.8667 秒。片段延续原配音上下文，不伪装成从零讲解概念的完整课程。

```bash
manimgl_env/bin/python -m manimind.experiments.model_benchmark generate --run-id mimo-ezlook-short-20261015 --profile mimo-ezlook-fast --max-output-tokens 8192 --cues half tenth approach
```

`--cues` 只接受原时间轴中连续、同序、无重复的 cue ID。协调器冻结所选教案，将时钟归零，按相同视频帧边界无损截取原 PCM 音轨，不调用新的配音服务。`experiment.json` 的 `excerpt` 保存选段、原时轴/音轨哈希和帧区间；长期写入者为 coordinator，消费者为 worker/reviewer/lead，生命周期与本实验一致，换选段必须开新实验。短期请求账本和产物路径不变。修复请求默认沿用原选段，不得偷偷更换题目或手修模型源码。

短片仍需独立审核数学、布局、叙事和逐句同步。只有冻结教案含 `zoom` 镜头时，额外强制真实局部放大检查；不含该镜头时应明确标注不适用，不将其填成已通过的放大实验。原完整试片默认保留全部五项检查。新 profile 的网关价格仍未知，不能按官方报价计算模型费。本段记录实验条件；实际结果另按输出账本记录，不代表已经成功。

实际执行的两次请求均返回 `reasoning_tokens=0`：

| 请求 | 输出预算 | API 耗时 | 输入/输出 token | 结果 |
| --- | --- | --- | --- | --- |
| 01 | 8192 | 47.292 秒 | 2233 / 8193 | `finish_reason=length`，拒绝截断结果；当前客户端未保留截断正文，不能分析其中的视觉实现 |
| 02 | 16384 | 7.614 秒 | 2527 / 1379 | 得到完整源码；实际 ManimGL 渲染 2.711 秒后失败 |

第二次显式要求紧凑完整源码，调整预算记录在 `budget-policy.json`，不是等预算对照。两次 API 等待合计 54.905 秒，已知输入 4760、输出 9572 token，金额未知。与旧整片失败不同，本轮拿到了可解析的完整源码，但还没有成功视频。

实际报错为 `attempt-02/scene.py:31` 调用 `beat` 时没有 `last_fraction`：模型把 `self.cue(...)` 当普通函数调用，没有进入规定的 `with` 上下文。源码另调用了不存在的 `self.add_updater_to`，且在要求保持 0.1 的讲解中继续变化到 0.08；后两项是静态发现，不能声称已经播放到相关画面。原模型源码保持不改；新增前置检查拦截未进入上下文的 cue、未知 updater 方法和 beat 的错误参数。

追加修复之前，两次生成额度已用尽，成功渲染数和审核通过成片数都是 0。未进行最终音画合成，没有覆盖旧精修视频。额外修复需要另行明确授权并记录，不隐藏此次失败。证据在 `runtime/sessions/mimo-ezlook-short-20261015-generation/`、`outputs/mimo-ezlook-short-20261015/attempt-02/` 及本轮长期审核目录。

## 明确授权的额外修复

2026-10-15 用户在上述两次短片失败后明确回复“再修复一次”。仅为该 run 的第三次请求追加一次额度，不修改全局默认上限，也不重建新 run 来隐藏前两次失败。仍使用 `mimo-ezlook-fast`、16384 token 上限、180 秒超时和 SDK 零重试；此处记录的是授权与条件，不预先宣称成功。

CLI 的 `--repair-authorization` 接受当前 session 内的授权记录，绑定 run-id、下一次 attempt 序号、旧 attempts 账本哈希、冻结教案哈希、修复反馈哈希和输出预算。默认预算取冻结实验配置；旧记录缺少 max_requests 时沿用历史默认 3。授权只允许一个 HTTP 请求，失败或超时同样消耗，账本一旦追加就不能再次使用同一授权。记录属于本轮短期协作状态，由 coordinator 按人类明确回复写入，worker 消费、reviewer/lead 审计；随实验保留，输入或序号变化即失效。它是本地审计机制，不是用户身份认证服务。

原 `review.json` 先归档为 `runtime/projects/<run-id>/review-attempt-02.json`，新 attempt 必须另做独立审核，不能沿用旧批准（本次旧结论本来就是 blocked）。第三次回答、源码、渲染继续写入同一 run 的 `attempt-03` 路径，仍禁止手改模型场景。

第三次实际结果：API 6.366 秒，输入 4273、输出 1425 token，reasoning_tokens=0、finish_reason=stop。模型修正了 cue 上下文和 updater 接口，原样源码通过 ManimGL 高清渲染，耗时 13.002 秒。无声样片位于 `outputs/mimo-ezlook-short-20261015/attempt-03/manim/media/manimgl/lesson-h.mp4`，1920×1080、30fps、566 帧、18.866667 秒，完整解码验证通过。这是渲染成功，不等于审核通过或带声音成片。

三次请求合计 API 等待 61.271 秒，输入 9033、输出 10997 token；金额仍未知。第三次只使用用户新增的一次请求，授权重复使用已测试会被拒绝，未调用第四次 API。原精修成片及前两次失败证据均保留。

独立审核最终为 `blocked`：Reviewer 查看 contact sheet 及 18.067 秒原分辨率帧，确认纵轴单位 `s/m` 与模型公式 `s(t)=4t²` 明显重叠。数学静态与末帧读数核对通过，布局失败，精确音画时序未听审、不记为通过。主线程重新核对报告绑定哈希和已看帧哈希，并验证合成关卡正确拒绝该报告，因此未进行配音合成，未产生合格最终交付。无声原渲染仅作为不合格样片展示。

此次入口与授权变更的完整离线测试：395 passed、1 skipped。实测说明明确报错反馈可以把本次接口错误修到可渲染，但不能据此宣称画面质量达标、获得稳定成功率或已经测出低价量产成本。

## 2026-10-14 历史实测

当时只使用项目现有 Moonshot 账户做 API 实测；并未完成多家国内模型横评，不能据此宣布 Kimi 最优或国内模型都不可用。

| 请求 | 模型/模式 | API 耗时 | 输入/输出 token | 实际结果 |
| --- | --- | --- | --- | --- |
| Code 01 | `kimi-k2.7-code` 思考 | 600.571 秒 | 未返回 | 超时，没有源码，无法评价视频质量 |
| Fast 01 | `kimi-k2.6` 非思考 | 0.368 秒 | 未返回 | HTTP 429；当时账户并发上限为 1，属于调度失败 |
| Fast 02 | `kimi-k2.6` 非思考 | 97.927 秒 | 4238 / 6815 | 源码返回；渲染 4.305 秒后因错误调用 `beat(run_time=...)` 失败 |
| Fast 03 | `kimi-k2.6` 非思考，唯一自修 | 103.236 秒 | 11626 / 7515 | 源码返回；高清渲染 19.124 秒后因虚线端点更新失败 |

Fast 02 和 Fast 03 按未缓存公开报价分别约 0.211552 元、0.278474 元，已知用量合计 **0.490026 元**。这是两次有 usage 响应的模型费估计，不是本轮完整账单，也不是一条合格视频的成本。超时和 429 未返回 usage，保留为未知；审核、配音、渲染和人工投入未包含。合格成片数为 0，不能计算或宣传“每条合格视频不到一元”。

两份源码均未被人工修改，没有把原精修样片冒充 API 生成结果，也没有追加无限重试。原来的 `outputs/velocity-pilot/instantaneous-velocity.mp4` 保持不变。本轮没有可交付的新成片，不进入拼接，不覆盖 iCloud 的原片。

### 错误归因

- Fast 02 的实际日志定位 `attempt-02/scene.py:104`：自定义时钟只接受比例参数，模型额外传入 `run_time`。这属于模型未遵守本实验支撑 API，不宜全部归因于 ManimGL 自身。
- Fast 03 的实际日志定位 `attempt-03/scene.py:269`：对 `DashedLine` 调用 `put_start_and_end_on` 后，ManimGL 报 `Mobject with no points`。这是本版本对象结构/API 使用错误。
- 源码另有明确缺陷，但不是完整观影结论：第 271 行对 Tex 公式调用数字更新接口；第 267 至 275 行逐项移动点、割线和读数，不能保持同一时刻几何量同步；点使用端点直线插值，不持续满足曲线方程。
- 讲解结束前就删除内容，以及缩放时轴、曲线、切线各自先后变换，说明“写出完整场景代码”和“形成连续、严谨的教学动画”仍有距离。缩放场景未实际运行到，不宣称已观察到最终画面。
- Code 模型超时和 Fast 的首次 429 只能说明本账户/配置下的延迟与调度问题，不能作为该模型教学能力的评分。

可追溯证据：`runtime/sessions/kimi-code-velocity-20261014-generation/attempts.json`、`runtime/sessions/kimi-fast-velocity-20261014-generation/attempts.json`、对应 `reply-02.txt` / `reply-03.txt`、`outputs/kimi-fast-velocity-20261014/attempt-02/render.json` / `attempt-03/render.json`。独立审核结论存放在 `runtime/projects/kimi-fast-velocity-20261014/review.json`；没有完整视频时只能做失败审核，不填写已通过的画面验收。

### 下一轮验证

先让新的 API 候选在相同教案、时间轴、代码约束和修复预算下完成同题测试，不因旧 Kimi 的两次失败预先判定所有模型都必须改用模板。

若自由生成代码仍反复失败，再验证“低价模型生成受约束的分镜参数，成熟组件负责动态几何”，与自由写整段 Python 分开计分。先只覆盖一个课程簇，例如函数图像、割线、切线和极限，再逐步扩展。组件开发成本也要记录，不把它隐去后宣称模型独立完成一切。

独立 API 对照需要各自密钥，不能借用 Moonshot 密钥。后续可增加流式响应和分镜级任务，测量首 token/完成耗时与断流成本；当前工具仍是非流式请求，不宣称已实现这些能力。

## 实验边界

- 固定 `velocity-pilot` 的数学事实、十二句讲解、已有配音和 88.7 秒时间轴。
- 外部模型独立生成完整 ManimGL 视觉代码；不给它此前精修场景源码，不由 Codex 代写或手修输出。
- 共享支撑只提供中文 FreeType 贴图、公式字体、字幕、标题和逐句时钟，不提供汽车、函数曲线、差商、缩放等教学场景实现。
- 每模型每 run 默认最多两次模型生成、三次 HTTP 请求；额外单请求修复必须有上述明确用户授权与绑定记录。保留原始回答、失败、使用量、耗时。明确的 429 拒绝不消耗代码自修名额，但仍计入请求数；超时因可能已生成/计费，保守计入生成数。历史最初两请求上限在遇到 429 后显式调整，变化记录在会话 `budget-policy.json`，不伪造成第一次成功。
- 生成代码先人工检查再执行，AST 预检不是安全沙箱。批量校内运行前必须另加隔离容器、无密钥渲染环境、网络隔离和资源限额。
- 画面由独立 Reviewer 检查数学、布局、叙事、逐句同步、真实放大，未通过不得合成最终带声音版本。36 帧抽检不等于完整观影/听审。
- 这是固定教案的动画实现实验，不证明自动教研、全学科泛化或无人审核售卖已经成立。

## 模型配置

`configs/model-benchmark.json` 提供八个 profile，只引用环境变量名，不保存密钥。每个 profile 独立指定 key 和 endpoint，云服务校验 host 和 HTTPS，禁止把一个平台的 key 发到另一家。

| Profile | 用途 | 当前配置依据 |
| --- | --- | --- |
| `mimo-ezlook-fast` | 同网关非思考短片实验 | 关闭思考，180 秒超时，独立选段与审核，价格未知 |
| `mimo-ezlook-pro` | 用户指定网关的首测入口 | `mimo-v2.6-pro`，独立 `MIMO_EZLOOK_API_KEY`，价格未知 |
| `mimo-pro` | 本轮首测候选 | `mimo-v2.6-pro`，思考模式，`MIMO_API_KEY`，按量付费 endpoint |
| `glm-flash` | 本轮低成本对照 | `glm-5.3-flash`，思考模式，reasoning_effort=max，`ZAI_API_KEY` |
| `kimi-code` | 已有账户的编程质量样本 | `kimi-k2.7-code`，必须思考，temperature=1 |
| `kimi-fast` | 同账户关闭思考的对照 | `kimi-k2.6`，thinking disabled，temperature=0.6 |
| `deepseek-flash` | 待独立密钥的低价 API 对照 | `deepseek-flash`，非思考模式，按峰时未缓存价保守估算 |
| `school-qwen` | 历史配置，当前不推进 | Qwen3-Coder-Next 或通过 `SCHOOL_LLM_MODEL` 指定精确服务模型名 |

新增来源：[MiMo 接口](https://mimo.mi.com/docs/en-US/quick-start/summary/first-api-call)、[MiMo 思考参数](https://mimo.mi.com/docs/en-US/quick-start/usage-guide/text-generation/deep-thinking)、[MiMo 实时与批量定价](https://mimo.mi.com/docs/en-US/quick-start/usage-guide/text-generation/batch-api)、[GLM 模型参数](https://docs.z.ai/guides/vlm/glm-5.3-flash)、[Z.ai 接口](https://docs.z.ai/api-reference/introduction)、[Z.ai 定价](https://docs.z.ai/guides/overview/pricing)。MiMo 使用中国大陆按量价格，Z.ai 使用其美元价格，不混用智谱 BigModel 账户或 Coding Plan endpoint。

MiMo Pro 实时未缓存价：输入 3 元/百万、输出 6 元/百万；GLM Flash 的 Z.ai 报价：输入 $0.15/百万、输出 $0.50/百万。仅作模型费估计，不代表每条合格视频总成本；未启用 Batch API，也未把批量折扣用于实时调用。

MiMo profile 将客户端 `max_tokens` 预算映射到请求体的 `max_completion_tokens`，其他 profile 保留 `max_tokens`。两字段不会同时发送；默认每次限制为 16384 token。MiMo 的这个上限包括思考和正文，可能因此截断代码；截断按失败记录，不当作完成，也不自动放宽预算。CLI 可显式传入 `--max-output-tokens`（1 至 65536），逐次写入既有 attempts 账本供 reviewer/lead 审计，随该实验保留；不修改默认配置、不增加生成次数。变更预算的实验不得宣传为等预算横评。

来源：[Kimi Code 参数](https://platform.kimi.com/docs/guide/kimi-k2-7-code-quickstart)、[Kimi K2.6 参数](https://platform.kimi.com/docs/guide/kimi-k2-6-quickstart)、[Kimi 定价原文](https://platform.kimi.com/docs/pricing/chat.md)、[DeepSeek 定价](https://api-docs.deepseek.com/quick_start/pricing/)、[Qwen 官方模型卡](https://huggingface.co/Qwen/Qwen3-Coder-Next)。型号与价格会变；应以实际请求返回的 `response_model` 和账单为准。

Kimi 两个普通版本均按输入 6.5 元/百万、输出 27 元/百万作未缓存估计；不选单价更高的高速版。DeepSeek Flash 暂按峰时输入 $0.30/百万、输出 $1.20/百万估计。缓存优惠、非高峰优惠未计入；这不是账单。没有服务端 usage 或没有核实价格时，费用为 `null`，不能写成免费。推理 token 以服务端 completion usage 为准，不与 reasoning tokens 重复相加。

## 复现

先安装 `[llm]` 可选依赖，准备原试片时间轴和配音。当前 Mac 用 `manimgl_env/bin/python`。同一 API 账户应串行调用，不能假设有多路并发额度。

当前用户指定网关：在项目 `.env` 或进程环境中单独设置 `MIMO_EZLOOK_API_KEY`，使用该网关签发的密钥。模型评测命令如下，尚不代表已经生成视频：

```bash
manimgl_env/bin/python -m manimind.experiments.model_benchmark generate --run-id mimo-ezlook-velocity-20261015 --profile mimo-ezlook-pro
```

若改用官方直连，再单独设置 `MIMO_API_KEY`。密钥从 [MiMo 控制台](https://platform.xiaomimimo.com/) 的 API Keys 获取，使用按量付费密钥，不使用 Token Plan 密钥；不要贴到聊天或写入 profile。无需修改现有 `OPENAI_*`。对照实验另设置 `ZAI_API_KEY`；只做 MiMo 时无需配置它。`.env.example` 仅为字段说明，不能覆盖已有 `.env`。

以下 `generate` 命令会产生实际 API 费用；使用新的 run-id，先逐条验证，不批量启动。

```bash
manimgl_env/bin/python -m manimind.experiments.model_benchmark generate --run-id mimo-pro-velocity-20261015 --profile mimo-pro
# 阅读 outputs/<run-id>/attempt-01/scene.py；确认没有危险操作后执行：
manimgl_env/bin/python -m manimind.experiments.model_benchmark render --run-id mimo-pro-velocity-20261015 --execute-reviewed-source
manimgl_env/bin/python -m manimind.experiments.model_benchmark inspect --run-id mimo-pro-velocity-20261015
# 独立 Reviewer 将版本绑定结论写入 runtime/projects/<run-id>/review.json 后：
manimgl_env/bin/python -m manimind.experiments.model_benchmark assemble --run-id mimo-pro-velocity-20261015
```

GLM 对照使用 `--profile glm-flash --run-id glm-flash-velocity-20261015`，保持其余任务与验收条件一致。

一次修复用 `generate --feedback runtime/sessions/<run-id>-generation/feedback.txt`；反馈只描述证据中的问题，不附替模型写好的新代码。第二次仍失败就标记未通过，不删掉失败重开同名测试。

## 状态归属

| 状态 | 写入者 | 消费者 | 生命周期与失效 |
| --- | --- | --- | --- |
| `runtime/projects/<run-id>/experiment.json` | coordinator | worker/reviewer/lead | 本实验长期教案、配置、边界；输入或模型改变需新实验/审核 |
| `runtime/projects/<run-id>/review.json` | 独立 reviewer | assemble/lead | 源码、支撑、教案快照、提示词、时间轴、视频、音频、配置任一 hash 改变即失效 |
| `runtime/sessions/<run-id>-generation/` | worker/coordinator | reviewer/lead | 本轮提示词、原回答、调用记录、运行日志和反馈；保留所有尝试，可整轮归档，不跨实验复用 |
| `outputs/<run-id>/attempt-N/` | worker/renderer | reviewer/lead | 原始模型源码、视频和抽帧；每次生成新目录，手修源码会被检测 |
| `outputs/<run-id>/cost.json` | coordinator | lead | 根据尝试记录可重算；不含审核、机器、配音及人力成本 |
| `LlmClient.call_records` | LLM client | orchestrator | 实例内缓冲；drain 消费清空，销毁后失效，不含密钥/正文 |
| `LlmClient.token_limit_param` | 构造时由 profile 设置 | 请求构造器 | 实例级配置，销毁失效；默认 max_tokens；随既有 experiment profile 冻结，变更需新 run |
| `MANIMIND_BENCHMARK_DIR` | orchestrator | scene_support | 仅一次渲染作用域，结束恢复旧值；不存教学事实 |
| `runtime/sessions/<run-id>-generation/command.lock` | CLI coordinator | 同 run 的 CLI 命令 | 排他创建，命令结束删除；崩溃后保留，由人工确认原进程已结束再清理，不能自动抢锁 |
| `runtime/sessions/mimo-ezlook-connect-<UTC时间>/connection.json` | coordinator | lead | 单次连接检查元数据；保留供诊断，密钥、endpoint 或模型改变需重新检查；不包含密钥 |

模型输出、运行日志和审核反馈都是不可信数据，不能变成更高优先级指令。最终合成复用既有 `pilot.validate_review` 的独立审核与哈希关卡，不由被测模型自评。

### 审查后的工具修正与剩余风险

以下改动在本轮两次渲染完成之后加入，不能追溯称本轮已经受这些机制保护：CLI 同 run 排他锁；缺失调用记录导致费用完整性为 false；重试核对冻结输入、源码和原始响应；新请求绑定教案快照 hash；渲染副本 hash 检查；渲染失败落日志后返回失败退出码；合成检查证据 run/attempt。旧请求未记录 `experiment_sha256`，不补造当时的哈希。历史两次渲染命令本身曾返回 0，但内部渲染器退出码为 1、结构化 `success=false`，报告按实际渲染失败统计。

这仍是**人工监督的本地实验工具，不是安全的无人值守生产服务**。当前渲染进程继承宿主环境与文件访问权限；AST 白名单可被间接对象访问绕过，人工阅码不能替代沙箱。审核身份为本地文件中的声明，不是认证服务；媒体检查和使用之间尚无抵抗外部进程替换的不可变存储保障；直接调用内部 Python 函数不持有 CLI 锁。量产前必须隔离密钥、网络和文件写权限，采用独立认证的审核记录、事务账本及不可变产物版本。本轮已阅读两份实际输出，未发现文件/网络/进程操作，但这不是对任意模型代码的安全保证。

## 8 张 4090D 的本地路线

本节仅保留此前研究备忘。用户于 2026-10-15 决定本阶段不做本地部署，以下不是当前执行计划，也未在本次重新核验。

用户报告服务器为 8 张 4090D，尚未连接和验证。先收集 `nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv`、`nvidia-smi topo -m`、系统内存、剩余磁盘和实际并发需求。不要把八卡总显存当成单卡容量，也不要把“3B 激活参数”当成“只加载 3B 权重”。

首选测试候选 Qwen3-Coder-Next：官方模型卡为 80B 总参数、3B 激活、Apache-2.0，并提供官方 FP8 权重与 vLLM 接口。先以短上下文、低并发实测；推荐不是质量保证，也不是已经部署。

若每卡确为 24GB，八卡约 192GB 总显存。80B BF16 仅权重约 160GB（十进制粗算），KV cache、工作区与通信还要空间，直接满上下文不合理。官方 FP8 权重约减半，是更适合先验证的方向。最终显存和速度须按模型文件、量化内核与驱动实测，不能按参数量拍板。

以下为待服务器验证的起始命令，不是已通过的部署脚本。官方模型卡要求 vLLM >=0.15；实际安装需要选与服务器驱动/CUDA 匹配的稳定版本并锁定。首次建议八卡 FP8、32K 上下文、并发 1，验证后比较四卡部署及多副本吞吐，不直接追求最大上下文。

```bash
# 在隔离推理环境安装匹配服务器的 vLLM 后运行；密钥事先由管理员设定。
vllm serve Qwen/Qwen3-Coder-Next-FP8 \
  --served-model-name school-qwen-coder \
  --host 127.0.0.1 --port 8000 \
  --tensor-parallel-size 8 \
  --max-model-len 32768 --max-num-seqs 1 \
  --gpu-memory-utilization 0.90 \
  --api-key "$SCHOOL_LLM_API_KEY"
```

仅监听回环地址，使用 SSH 转发或学校认证网关连接，别开放无认证端口。项目环境设置 `SCHOOL_LLM_BASE_URL=http://127.0.0.1:8000/v1`（按转发端口调整）、`SCHOOL_LLM_MODEL=school-qwen-coder` 和独立 `SCHOOL_LLM_API_KEY` 后，以 `--profile school-qwen --run-id <新实验名>` 运行同题。没有学校服务地址前，本地结果必须标记未测。

[官方 FP8 权重与限制](https://huggingface.co/Qwen/Qwen3-Coder-Next-FP8)特别说明模型卡性能表来自未量化 BF16，不应直接当成 FP8 成绩。单卡/多卡速度还受 PCIe、CPU、内存和并发影响，硬件投入须等同题实测后决定。

## 候选模型共同诊断实验

2026-10-16 起增加显式的 `model_dialogue init/ask`。先给候选模型实际抽帧和失败事实，要求其区分观察/推断、质疑工程师，再回答它的问题、确认规范。协作自身不能放行成片。`ask --images` 发送本地 JPEG/PNG，使用既有 profile，失败占预算且不自动换接口；不在文件中保存密钥或重复 base64。

固定流程为：联合诊断 -> 冻结设计规范 -> 全新生成 -> 实际渲染与标签端点检查 -> 图像复盘/限次修复 -> 独立审核 -> 合成。两份新样片共享同一规范，不用人工改模型源码制造成功。首轮试验仍需人工协调，不自动循环到预算耗尽。

| 新状态 | 写入者 | 消费者 | 生命周期与失效 |
| --- | --- | --- | --- |
| `runtime/projects/<case>/collaboration.json` | coordinator | model_collaborator/reviewer/lead | 本轮目的、profile、请求上限；改变需新case或显式记录用户授权 |
| `runtime/projects/<case>/scene-design-v1.json` / `experiment.json.design_brief` | coordinator | worker/reviewer/lead | 双方确认的版本化规范；改变需新实验，不能偷偷覆盖重试输入 |
| `runtime/sessions/<case>-generation/dialogue*.json` / `dialogue-*-reply.txt` | model_collaborator/coordinator | reviewer/lead | 单轮原始请求、回复、用量；失败/中断也占预算，历史哈希变化阻止继续 |
| `outputs/<case>/dialogue-NN.json` / `dialogue-cost.json` | coordinator | lead | 原回答的解析副本和费用汇总；可由短期原始记录重建，不是审核结论 |
| `outputs/<run>/design-brief.json` | coordinator | guarded_scene/reviewer | 长期规范的渲染输入副本，hash变化使本轮失效 |
| `outputs/<run>/attempt-N/layout-checks.json` | guarded_scene | benchmark/reviewer | 该次模型代码注册标签的实际端点包围盒；源码、规范、仪器改变失效，合成前重算问题 |
| `MANIMIND_LAYOUT_REPORT` | renderer coordinator | guarded_scene | 单次渲染内明确传递，结束恢复旧值 |
| `GuardedBenchmarkScene.layout_labels/layout_checkpoints` | scene | beat采集器 | 单次渲染内状态，销毁后失效；持久证据写上表输出目录 |

布局仪器不检查任意未注册对象、组内部文字间距或所有中间帧；它不证明数学正确或影片好看。独立审核必须继续查源码、原始画面、过渡与逐句时序。旧样片的支撑模块未修改，避免以新仪器追溯宣称旧片已经受保护。

### 2026-10-16 联合诊断实测结果

使用用户指定网关的 `mimo-ezlook-fast`（返回模型名 `mimo-v2.6-pro`，非思考）。返回名称不能证明网关上游身份；未知实际单价保持 `null`。完成4轮模型协作，以及A/B各一次新生成和一次修复，共8次API调用，已知输入74,168 token、输出17,302 token，调用累计约98.79秒。不含本轮工程实现、渲染、独立审核或人力成本。

协作不是单向下指令：第一轮交三张旧片原帧让模型独立诊断；第二轮纠正其颜色/同步误判并共同冻结规范；第三轮交A原帧、两份源码、布局报告和运行错误复盘；第四轮讨论落实失败与下一版职责划分。原始对话可追溯至 `runtime/sessions/mimo-collab-20261016-generation/dialogue.json`，解析副本在 `outputs/mimo-collab-20261016/dialogue-01.json` 至 `dialogue-04.json`。

| 实验 | 首轮 | 一次修复后 | 独立审核 |
| --- | --- | --- | --- |
| `mimo-collab-a-20261016` | 完成渲染，轴单位越界、割线太短 | 完成18.8667秒1080p渲染；轴单位仍越界，有限割线未覆盖Q，8个刻度漏注册 | blocked |
| `mimo-collab-b-20261016` | FadeIn参数错误而失败，另有beat比例倒退 | 完成18.8667秒1080p渲染；纵轴单位越界/碰撞，早期割线过长越界 | blocked |

两份首轮system完全相同，user提示除运行ID外相同；相同教案、音轨、设计规范。所有场景均来自原始API回答，没有手工改场景救片。独立Reviewer每份查看5张原分辨率帧与contact，并核对源码、数学、包围盒、时序。主Agent复核审核绑定哈希及所看帧哈希，验证布局和审核两道关卡都拒绝交付；因此没有合成带声成片。末帧读数0.02、0.3216、16.08正确不等于影片合格。未听音频，未逐帧完整审查，不冒称声画同步已验证。

本轮实际落地：有界联合诊断、原帧输入、冻结共同规范、原回答与用量审计、标签端点包围盒关卡、FadeIn参数/字面量beat顺序预检、独立审核。代码测试为427 passed、1 skipped；测试数不是视频质量分数。

结论：当前接口在这两次自由代码生成中的约束落实不可靠，且模型复盘自身也会误读目标标题、时钟与几何证据。不能采用模型自评作为事实；同时，这两份同题样本不足以认定该模型或所有低价模型永远无解，也不能推算通用成功率。

下一版拟改为受约束 `SceneSpec` 数据，经校验、布局编译和可信图形组件渲染；LLM保留教学目标、解释和对象组合，确定性组件负责轴/单位/刻度、增量绑定、直线裁剪和时钟。**本轮尚未实现该编译器**，不将草案当成稳定工作流。模型提出的草案仍包含 `func`/`bind` 表达式字符串，不能直接 `eval`；实现时应使用多项式系数等结构化数学模型、枚举绑定与类型化运算。下一轮至少要同题重复和一个参数变体，随后再验证不同表示法与长叙事。

## SceneSpec 1.0 组件实验

该路径不执行模型Python或表达式字符串。模型输出数据，工程组件执行，数学任务与讲解音轨被冻结。当前语法限定：定义域从0开始、位置非负的一至三次多项式；图元固定为曲线、动点、增量三角形、割线、切线、比值，允许模型规划中文标题/目标、读数顺序和阶段焦点/节奏。不是支持任意知识点的通用视频语言。

```bash
manimgl_env/bin/python -m manimind.scene_spec.experiment init --suite spec-suite-20261017
manimgl_env/bin/python -m manimind.scene_spec.experiment generate --suite spec-suite-20261017 --run poly-a
manimgl_env/bin/python -m manimind.scene_spec.experiment render --suite spec-suite-20261017 --run poly-a
manimgl_env/bin/python -m manimind.scene_spec.experiment inspect --suite spec-suite-20261017 --run poly-a
# 独立Reviewer写入该run的版本绑定review.json之后：
manimgl_env/bin/python -m manimind.scene_spec.experiment assemble --suite spec-suite-20261017 --run poly-a
# 汇总所有原请求与当前审核、成片；未完成/被阻塞的trial不会算交付成功：
manimgl_env/bin/python -m manimind.scene_spec.report --suite spec-suite-20261017 --collaboration spec-collab-20261017
```

`configs/scene-spec-suite.json` 定义3个同题独立请求与2个参数/曲率变体，生成最多8请求且每run最多2次，另留2请求给模型图像协作，总上限10。失败/超时计入，不自动重试，修复必须显式 `--feedback`。不手改模型数据。`calibrate` 仅渲染工程fixture，不调用模型；其全部版本和失败单独保留，不计入模型通过率。

| 状态 | 写入者 | 消费者 | 生命周期与失效 |
| --- | --- | --- | --- |
| `runtime/projects/<suite>/suite.json` | coordinator | worker/reviewer/lead | 本轮任务、schema、prompt、profile和预算，改变须新suite |
| `runtime/projects/<suite>/<run>/review.json` | 独立reviewer | assemble/lead | 绑定所有输入/组件/实际视频/审计哈希，任一改变失效 |
| `runtime/sessions/<suite>-generation/requests.json` 与prompt/reply | worker | reviewer/lead | 本轮调用生命周期；先登记再调用，失败不可删除，原回答不可覆盖 |
| `outputs/<suite>/<run>/attempt-N/scene-spec.json` | validator | renderer/reviewer | 原模型回答解析产物，与原回答相符才能继续，改动需新请求 |
| `outputs/<suite>/<run>/assets/` | audio coordinator | renderer/reviewer | 冻结任务的音轨/时钟及provenance；任务或哈希变化拒绝复用 |
| `outputs/<suite>/<run>/render-N/` | renderer/inspector | reviewer/assemble | 单次不可覆盖渲染及逐帧原始测量；源码/数据/音轨/时钟/配置变化需新版本 |
| `render-index.json` / `review-input.json` / `generation-cost.json` | coordinator | reviewer/lead | 指向当前版本或从账本派生，可重新计算，不等于审核许可 |
| `outputs/<suite>/report.json` | experiment_reporter | reviewer/lead | 从保留账本/当前审核/成片重建的快照，来源哈希变化须重建；首轮与修复后通过分别统计 |
| `runtime/sessions/<suite>-generation/*feedback*.txt` / `first-attempt-triage.json` | coordinator/model_collaborator | worker/reviewer | 本轮临时诊断和有界重试输入，保留失败，不作为最终审核；新尝试另建原始请求 |
| `SpecLesson.frame_records/labels/geom` | render process | frame auditor | 本次渲染内状态，结束落盘报告并销毁 |

逐帧关卡复算真实端点和读数，检查割线包含P/Q、真实增量、两线裁剪、切线斜率、数值同步、标签边界/碰撞、完整帧覆盖和句末目标。显示数值明确使用近似符号，防止连续运动时舍入数字被误解为精确等式。未来出现的切线标签提前保留空间；颜色和线型由组件固定。

原题复用已冻结的三句配音；参数变体使用本机Tingting，台词由真值生成并实测时长，不伪称LLM自主完成课程或配音。所有成片仍需独立审核。该实现不是认证审核服务或完整安全沙箱，教师教学验收、字幕/听感与跨题/长片仍需进一步验证。

### 2026-10-17 五次重复与变式实测

实际套件为 `spec-suite-20261017`，协作为 `spec-collab-20261017`。沿用用户提供的网关及 `mimo-ezlook-fast` 非思考配置，接口回报 `mimo-v2.6-pro`；该字符串不构成上游身份验证。以下均为实际API、实际ManimGL渲染与独立审核结果，不是mock测试。语法支持一至三次多项式，但本次五条只测试了二次函数的一个镜头类型。

| run | 函数 / 固定点 | 首轮内容审核 | 处理后结果 | 视频时长 |
| --- | --- | --- | --- | --- |
| poly-a | s=4t², t=2 | coordinator发现0.5→0.1被称为减半，阻塞 | 原模型仅改标题，attempt-02独立审核通过 | 18.8667s |
| poly-b | 同题独立请求 | 独立审核通过 | 无修复，已合成 | 18.8667s |
| poly-c | 同题独立请求 | 独立审核通过 | 无修复，已合成 | 18.8667s |
| poly-shifted | s=3t²+2t, t=1 | 独立审核通过，有焦点建议 | 无修复，已合成 | 19.6667s |
| poly-concave | s=-t²+8t+12, t=2 | coordinator发现减半错误及阶段内固定h=1措辞，阻塞 | 原模型仅改两个标题，attempt-02独立审核通过 | 19.7333s |

可复核统计：

- 五条首轮均通过JSON校验、实际渲染和机械检查；**首轮不经修复通过独立审核为3/5**。两条有事实错误的样片没有被当成首轮成功，也没有合成。
- 低价模型参与图像与数据复盘后，A/concave各追加一次API修复，原回答与修复版本保留，工程师没有手工改模型数据。最终5/5在有限镜头标准下通过独立审核并合成1080p/30fps带声视频。
- 三个原题首轮请求的完整提示哈希相同，历史互不传递；初轮五条及修复两条共7次渲染使用完全相同的组件/编排指纹，没有逐片偷偷改组件。
- 最终五条共2880视频帧，逐帧仪器保留2885条记录（每条另含frame 0）。检查全帧标签、读数、真实P/Q与直线端点，所有当前帧关卡通过。独立Reviewer另查看5张contact及32张原分辨率帧，逐条绑定输入/代码/音轨/时钟/实际视频哈希。
- 最终文件逐条检查音视频流时长并全片解码；**未试听音频**，审核中的时序结论只覆盖画面与timeline，不是听感、逐字发音或教师验收。
- 自动测试为463 passed、1 skipped，包含契约、500组随机直线裁剪、API上限、输入篡改与缺少/过期/不通过审核不得合成等回归；测试数量不代表教学质量。

协作实际消耗2请求：第一条4096输出token上限触发截断，作为失败计入账本；客户端未返回可保存的完整答案。第二条压缩问题范围并提高单次上限，返回可用JSON，对实际两张原帧和全部五份数据提出问题与修复建议。模型确认减半错误，指出concave固定初值措辞，以及标题与强调行不完全一致的风险。它也误读了一个字幕字形，不能把模型视觉描述当作事实或审核许可。最终独立审核将A/shifted的焦点问题降为建议，未继续消耗API修复非阻塞项。

共使用9/10预算请求：7次数据生成/修复，2次协作（1成功、1截断）。网关回报数据生成输入8278、输出2151 token；含协作共输入24210、输出7933 token。实际单价未核验，费用保持null，不能把token数直接宣称为人民币成本；这些数字也不含本次强模型协调/独立Reviewer、渲染、TTS、人工和工程开发成本。生成与修复的7次API延迟约2.38–3.13秒/次，不是端到端交付时长。

工程校准单独放在 `outputs/spec-calibration-20261017/`：先后修复浮点序列化、轴单位与末刻度间距，并校准切线可见性；只有第三个fixture版本通过机械检查，之后才启动真实模型套件。这些人工组件调试不计入模型首轮成功率。曾有一次并发渲染命令被套件锁拒绝，未进入渲染，也不算模型生成失败。

**结论：这一轮支持“把数值、几何、布局交给可信组件能改善稳定性”，不支持“低价模型已能自主稳定生产高质量课程”。** 标题语义仍会出错，首轮完整通过只有3/5；有限重试后5/5也不足以估计总体成功率。Q未标字母、趋近时两线辨识度、A/shifted强调行与标题衔接、concave末标题省略主语，都是保留的教学改进项。当前产物是受约束的短镜头，不是3b1b级完整叙事，也没有学生理解度测试。

复现入口与记录：`src/manimind/scene_spec/`、`configs/scene-spec-suite.json`、`outputs/spec-suite-20261017/report.json`、各run的 `review-input.json` 和 `runtime/projects/spec-suite-20261017/<run>/review.json`。汇总器可重建首轮/当前审核、交付、调用和token统计，不会因为最后成功而抹掉失败。下一轮应将可确定的数值/比例标题改成结构化语义槽位；对照评估仍需另建suite，不能改本轮冻结契约再追溯计分。

## 批量生产的下一关

试验至少扩展到导数、抛体运动、圆锥曲线、线性变换、概率分布、电磁感应等不同表示方式；每题多次独立运行。分开统计数学错误率、首轮渲染成功率、限次修复通过率、视觉通过率、审片分钟数、每合格分钟总成本。带教师审核和版权/配音授权检查的课程资产，才是学校实际购买的东西；一条成功样片不能替代验收体系。
