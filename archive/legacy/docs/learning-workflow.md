# 教学工作流迭代

2026-10-24新增独立的[视觉优先工作流](visual-first-workflow.md)，先审核静音动画，再写事件绑定旁白，最终语音后置。下文保留v1/v2/v3配音先行实验的历史设计和记录；不修改已有冻结实现。

## 目标

执行“优化工作流 → 新上下文制作 → 看实际成片 → 提炼通用问题”，不把某题的分镜做成所有课程的模板。入口 `experiments/learning_workflow.py` 继承原三角色制作、权限、原答来源、互斥、最高思考与发布门禁。当前按用户要求，先使用 GPT-6.1 Sol 优化，不继续 DeepSeek。Sol 的主控、创作与独立审片均使用 max；外部协调者开发通用工具并做外部评估，不改候选讲稿或源码。旧冻结实验保持原样。

`experiments/sol_learning_workflow.py` 组合通用教学工作流和既有 Sol 订阅传输，使用独立的 `configs/workflow-sol61-20261023.json`。每次角色推理是全新临时会话，只接收当前实验授权上下文，不导入已中止 DeepSeek 的讲稿、时间轴、代码或制作记录。该中止尝试仍保留在原 study 中，不能删除费用或计作成功样本。

`configs/learning-workflow-v1.json` 保存题目无关引导和固定评分政策，`configs/workflow-study-20261023.json` 保存题目划分。制作角色每次只接收当前题目的公共任务，不接收其他题目、旧作品、逐片评论、主对话或记忆。

## 迭代安排

1. 平抛：开发集，检查已知教学和时序问题，不给作者旧稿或逐片改法。
2. 条件概率：开发集，检验集合筛选、分母改变，不照搬物理片的节奏。
3. 并联电路：留出集，在最终profile和开发评估冻结前不可运行。

开发片暴露问题后，先提炼跨题目成立的原因，再创建新profile版本；实质变更至少做一次同题回归。最终profile需在两个开发题下都取得版本绑定的外部验收，才可开放留出题。只适合一题的改法应留给该题作者，不升格为全局要求。不为凑轮数强行改动，不把不同题的分数差解释成工作流的因果提升。

看过留出结果再调参，就必须将它转为开发数据并使用新study/新留出题。少量题目成功不能证明统计稳定或学校销售就绪。

## 新审核

- 每段每0.5秒生成时序联系表，保留实际原帧与哈希，补充原分辨率审核帧；这仍不是连续观看，不保证覆盖任意短暂故障。
- 首看只给公开学习目标、受众、段落边界和像素，不给作者源码、设计说明和讲稿。记录画面支持的解释、缺失连接及迁移问题。
- 另开请求核对源码、讲稿和实测时钟，不能用后一次通过覆盖首看未通过。
- 固定0–4锚点及权重：科学20、因果25、视觉解释20、完成度15、节奏10、兴趣10。整片至少80分，科学/因果/视觉解释/节奏各至少3。blocker不能被总分补偿；这是内部编辑量表，不是学生效果或客观质量真值。
- 字幕检查精确复现当前字体宽度折行，三行以上、孤立标点阻断；40字以上仅提示阅读负荷，不限制讲稿长度，也不代写句子。
- 通过后仍走原合成门禁，再导出无外挂字幕的独立播放包。原SRT保留为制作档案。

生产端不规定固定镜头数、角色、时长、配色、公式数量或持续运动。沙箱、来源、权限等工程安全边界继续保留。

## 状态归属

| 路径 | 写入者 / 消费者 | 生命周期及失效 |
| --- | --- | --- |
| `runtime/projects/<study>/protocol.json` | study协调器 / runner、审计者 | 首次使用冻结；题目或政策变化须新study |
| 同目录 `run-configs/<study>-<version>-<case>.json` | 配置生成器 / 对应runner | 单次配置不可覆盖；profile/实现指纹变化停止续跑 |
| 同目录 `assessments/<version>-<case>.json` | 外部评估者 / 留出门禁、用户 | 当前视频与profile有效；旧版保留 |
| 同目录 `holdout-freeze.json` | study协调器 / 留出runner | 单向不可覆盖；绑定profile/study/开发评估变化失效 |
| `runtime/projects/<run>/` | 原初始化与审核适配器 / 角色、发布门禁 | 沿用冻结协议和独立审核，不混入临时尝试 |
| `runtime/sessions/<run>-generation/`等角色目录 | 原执行器 / 对应角色、审计者 | 分离请求、原答、笔记、未决操作与费用；沿用原故障恢复 |
| `outputs/<run>/temporal-vNNN/`、`review-input.json` | 媒体取证器 / 作者、导演、审核者 | 渲染分版本；原帧或联系表哈希变化阻止发布 |
| 同目录 `subtitle-audit.json` | 字幕诊断器 / 审核、发布 | 当前时间轴/字体有效，输入变化重新生成 |
| 同目录 `playback/` | 审核后打包器 / 用户、播放器 | 已批准视频逐字节副本，不附外挂字幕 |

外部开发评估需包含 `case_id`、`profile_sha256`、`video_sha256`、`verdict`、`blockers` 和符合固定量表的 `review`。留出门禁核对实际发布视频，不接受只有一个总分的记录。外部评估不回传本轮候选；下一版只吸收通用工作流原则。

## 运行

当前 Sol 入口先隔离宿主参数再加载 ManimGL。通用工作流、Sol 传输、运行入口及额度观察器均在首个制作调用前冻结；既有 DeepSeek 入口不被修改。

```bash
PYTHONPATH=src manimgl_env/bin/python -m manimind.experiments.sol_learning_workflow \
  --study configs/workflow-sol61-20261023.json --profile configs/learning-workflow-v1.json \
  --case projectile
```

Sol 首次调用前记录 `runtime/projects/<run>/quota-snapshots.json` 账户基线，写入者为只读额度观察器，消费者为用户和费用审计，生命周期为该次制作；账户或窗口变化不能直接相减，其他聊天使用使单项目归因失效。短期 `quota-samples.jsonl` 定时采样，输出 `quota-report.json` 汇总；团队结束后观察器退出。每角色原始 CLI 事件中的 token 和缓存单列，不把账户变化全算到本片，也不把 credit 等价量说成订阅实付费用。

历史 DeepSeek 入口为 `experiments/learning_runtime.py`。执行适配器单独哈希绑定，若在已有请求后接入，会记录接入前调用数，不能包装成从未故障的首轮。以下命令仅用于该历史入口，不是当前优化计划：

```bash
PYTHONPATH=src manimgl_env/bin/python -m manimind.experiments.learning_runtime \
  --study configs/workflow-study-20261023.json --profile configs/learning-workflow-v1.json \
  --case projectile

# 两个开发题在最终profile下均通过外部验收后
PYTHONPATH=src manimgl_env/bin/python -m manimind.experiments.learning_runtime \
  --study configs/workflow-study-20261023.json --profile configs/learning-workflow-v1.json \
  --freeze-holdout
```

同入口可运行 `conditional`；留出 `parallel` 冻结前拒绝运行且不调用API。续跑前核实进程与未决请求，`--resume-received-request`只恢复完整已收且尚未执行工具的原答。

`--recover-read-api` 仅在确认没有活跃锁、原命令为只读API查询、原答和输入哈希完整、候选稿和时间轴未变时补完该只读动作，不调用provider；绝不据此恢复未知是否执行过的写稿、渲染或发布。恢复收据永久保留，故障时间包含在本轮墙钟时间中，不冒充纯模型推理耗时。

## 验证与限制

首批49项相关测试通过。离线字幕回归检出了旧DeepSeek片的孤立句号和4条长字幕提示，旧Sol片该项无blocker；这不是新片的成功率。模型仍可能高估自己，需要外部实际帧复核、独立听审和目标学生的解释/迁移测试。每轮分别记录首轮、返工后、外部验收与全部费用/耗时，失败不能从分母删除。

Sol 接入后的首批整仓工程验证为1224项通过、2项跳过。第一条 Sol 样片制作暴露了公开接口说明缺项和列表/向量参数类型问题；`learning-workflow-v2.json` 补全通用技术引导，创作引导和固定教学量表逐项不变，不包含本片分镜或改稿。该候选版本不会中途注入v1制作角色，在新的同题完整回归前，不声称减少耗时、提高质量或已经完成第二轮验证。

检查真正发出的审核输入后发现：v1虽然从`reviewer_context`排除了讲稿，但后续附加的字幕诊断包含全片`rows`，间接带入字幕全文和时间。v1因此不能被称为无讲稿首看，其原答、费用、样片和偏差证据均保留，不中途修改冻结实现。

`experiments/sol_learning_v2.py` 在最终审核装配边界只传当前分组的机械诊断摘要，剔除字幕正文、完整span、其他分组诊断和未知字段；实际字幕仍可从画面辨认。源码/讲稿复核仍是单独的新请求，不能覆盖首看未通过。新增回归测试在真实装配链末端截取将发给原生传输的文本和图片列表，而不只测试某个context辅助函数。v2入口命令将模块名改为`manimind.experiments.sol_learning_v2`，profile改为`configs/learning-workflow-v2.json`，其余study/case参数相同。

`experiments/learning_background.py` 是独立的执行启动适配器，只启动显式匹配的已冻结Sol v2/v3入口，不新增创作上下文。它先验证冻结配置与留出门禁，再以启动锁、既有进程、团队锁和未决检查点阻止重复调用；不恢复未知是否收费的请求。短期`launcher.json`记录启动器源码哈希、配置哈希、PID和完整参数，由启动器写、操作者和重复启动防护消费，仅对当前进程有效，进程退出或未决状态变化后须先检查。该收据不修改冻结媒体实现。后台命令将模块名改为`manimind.experiments.learning_background`，参数仍为study/profile/case。

## 批量取证候选版

v1实际调用记录显示重复上下文与分组请求的开销较大。`experiments/sol_learning_v3.py`保留v2的首看隔离，将多项公开接口查询在本机按四项处理后一次返回；`inspect_segments`可一次选多个当前cue；成功渲染自动附上全部当前cue的实际联系表，不必再发一轮仅索取同样像素的模型请求。实际观察仍须由模型在下一响应记录，执行器不伪造观察或批准。

独立审核改为两个全新上下文的全片请求，各自必须逐cue举证：无源码/讲稿的像素首看，以及源码/实测时序复核。两者都消费与v2相同种类的原分辨率帧和0.5秒时序证据，可补取细帧，沿用结构修复和原发布门禁。任一未过不能发布，教学量表和关键维度阈值完全不变。减少了独立分组判断次数，可能影响漏检率，必须用真实回归检验，不能只根据调用数称其更优。

使用`configs/learning-workflow-v3.json`及模块`manimind.experiments.sol_learning_v3`。后台入口显式加`--engine sol-v3`，启动器强制engine与profile版本相符，不能误走旧执行器。v2仅是未付费制作的中间修订，不计为第二次成片实验；下一份完整回归使用v3，保留所有历史失败和费用。仍须同题回归与跨题开发验收后才开放留出题。

macOS后台启动用系统`caffeinate -i`临时防止运行期间闲置睡眠，子进程结束即退出，不更改系统电源偏好或创建计划任务。手动睡眠、关机或配额耗尽仍可能使本轮中断，未决调用必须先检查，不能自动重发。

## 本地版本管理与发布

自2026-10-24起，优化阶段先在本地Git保存阶段性检查点，暂不推送GitHub；整体优化完成后再统一整理远端更新。后续本地提交不视为推送授权。

版本管理包含源码、非敏感配置、测试、文档和可复现示例；密钥、本机环境、运行记录、视频及迁移备份保留在本机，不进入提交。本地提交是工程快照，不表示工作流已经完成跨题验证，也不表示预览已通过教学验收。

## DeepSeek high 同工作流实验

2026-10-24按用户要求，以全新study `workflow-deepseek-high-20261024` 运行平抛，不恢复旧DeepSeek候选。入口 `experiments/deepseek_learning_v3.py` 直接继承通用 `LearningWorkflow`，不继承Sol订阅传输；主控、创作、两路独立审片和审核结构自修复均通过官方DeepSeek API，显式传 `thinking=enabled`、`reasoning_effort=high`。不得把high记为max或最高推理。

复用未修改的 `configs/learning-workflow-v3.json`，平抛公共任务与Sol study逐字段相同。为保留冻结历史，直接复用Sol v2的无正文审核装配方法和Sol v3的双全片审核方法；两者不包含Sol传输和依赖继承上下文的 `super` 调用。批量工具语义与成功渲染后的自动取证保持一致；同模型审片仍不等于不同模型家族共识或学生理解测试。模型及推理等级都不同，不能将单次差异归因为模型能力一个变量。

```bash
PYTHONPATH=src manimgl_env/bin/python -m manimind.experiments.deepseek_learning_v3 \
  --study configs/workflow-deepseek-high-20261024.json \
  --profile configs/learning-workflow-v3.json --case projectile --background
```

长期协议与执行适配器绑定在 `runtime/projects/<run>/`；每角色原始请求、回答、使用量和启动收据在 `runtime/sessions/<run>-*/`；视频、实际帧及费用/计时报告在 `outputs/<run>/`。写入者分别为初始化器、角色请求传输、后台启动器和报告器，消费者为对应角色、发布门禁与审计者。配置、profile、使用的冻结源码或媒体变更使旧证据失效；进程退出或未决状态变化使启动收据失效，不能因此自动重发收费请求。作者与审片只收到当前公共任务、通用工具和本轮授权内容；凭证不写入请求档案，也不进入渲染候选。原始失败、未知用量与非成片候选全部保留，源码适配和成片质量分别验收。


## Harness 接手单条高中物理片（2026-10-24）

本次不启动 `deepseek_learning_v3`、`sol_learning_v3` 等全自动成片执行器，而由主 Agent 直接规划、写讲稿、写 ManimGL 场景，并按实际渲染帧逐轮返工。配音、渲染、抽帧、混音与合成复用 `postproduce/freeform_pilot`；独立审核为两个全新上下文的子 Agent：一个只看像素和公开学习目标，另一个核对讲稿、源码与实测时序。两者都通过才写 `review.json` 并进入合成。这不是人工审片、不同模型家族共识或学生理解测试，也不修改 v3 profile、评分量表或任何冻结历史。

交付、复现、审核原答和限制见 [平抛：水平速度与落地时间无关](projectile-independence.md)。
