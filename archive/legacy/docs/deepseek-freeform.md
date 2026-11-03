# DeepSeek 自由创作隔离试验

目标是在现有自由创作工具下测试 DeepSeek 独立完成同一学习目标的水平，不向它提供 Codex 参考片、场景源码、讲稿、具体批评或修改方案。本试验不是与人工监督参考片等预算的盲测排名。

作者通过官方 API 无工具请求工作。公共输入只包含平抛事实、受众目标、通用创作引导、审核标准、运行接口；例子数值、讲稿、分镜、图形、角色由作者决定。`freeform_support.py` 仅提供字体、实测时间及逐句字幕，不含教学画面。固定请求额度为讲稿一次、代码一次、最多两次自修复和一次图像自检。没有隐式网络重试。原始响应不人工改写，仅机械解包代码围栏和添加工程路径。

渲染复用现有 ManimGL 命令构建器、TTS 和 `freeform_pilot` 抽帧/审核合成关卡。代码必须先人工检查；AST 筛选、精简环境变量和 macOS sandbox 限制网络及其他项目/隐私路径读取，不能当成对抗性安全证明。作者自检不得作为发布审批。

## 状态与失效

| 状态 | 写入者 / 消费者 | 生命周期、失效 |
| --- | --- | --- |
| `runtime/projects/<id>/isolation.json` | coordinator / author、reviewer、evaluator | 长期预注册协议；配置、提示与帮助代码改变需新试验 ID |
| `runtime/projects/<id>/authorship.json` | coordinator / reviewer | 原讲稿与工程包装指纹；原答或讲稿变化即失败 |
| `runtime/sessions/<id>-generation/request-*/` | API runner / reviewer、evaluator | 请求前记账，保存原提示、响应、usage；不覆盖失败 |
| `outputs/<id>/spec.json`、`candidate.py` | API runner 机械解包 / renderer | 当前候选；来源原件留在请求目录；禁止手工修复 |
| `outputs/<id>/candidate-origin.json` | API runner / renderer、reviewer | 当前代码原答指纹；字节变化阻断渲染 |
| `outputs/<id>/author-self-review.json` | 候选模型 / reviewer | 当前抽帧自检，不具备放行权；新渲染后失效 |
| `runtime/sessions/<id>-production/` | renderer / reviewer | 原始渲染日志和逐版本收据；保留失败 |
| 媒体、抽帧、正式审核、成片 | 既有 Production 和独立 reviewer | 继承自由场景媒体哈希关卡，不跳过审核 |
| `outputs/<id>/cost-report.json` | evaluator / 用户 | 可重建；调用变化失效；高峰未缓存估算，不是账单 |

API 成本单独报告，不包含 Codex 编排/独立审核、TTS、渲染机器时间和人工成本。滚动模型名保留实际响应 model，不当作不可变版本证明。

```sh
manimgl_env/bin/python -m manimind.experiments.freeform_isolated init
manimgl_env/bin/python -m manimind.experiments.freeform_isolated plan
manimgl_env/bin/python -m manimind.experiments.freeform_isolated code
# 人工只做安全检查，不改模型代码
manimgl_env/bin/python -m manimind.experiments.freeform_isolated render
manimgl_env/bin/python -m manimind.experiments.freeform_isolated self-review
# 如有报错，repair --feedback 原始日志或审核文件；最多两次
```

独立 reviewer 按实际证据决定是否通过。通过才可调用既有 `freeform_pilot assemble --spec outputs/<id>/spec.json`。该工具保留历史默认文件名；名称不代表使用了参考片内容。原媒体发布收据中的通用“监督试片”描述不代替本试验的作者来源和隔离协议。

## 2026-10-20 实测

官方 `deepseek-flash` 滚动别名，公开文档当日对应 V4.1-Flash-1017。单次输出上限 32768，包含思考 token；这不是模型最高输出长度，也不是完整能力上限测试。

| 阶段 | 结果 | 调用数 | 高峰未缓存估算 CNY |
| --- | --- | --- | --- |
| 默认思考 | 生成原讲稿；代码两次达到长度上限，usage 均报告 32768 reasoning tokens | 3 | 0.619254 |
| low 思考 | 沿用原讲稿/同配音；代码仍达到上限 | 1 | 0.277000 |
| 非思考 | 原代码一次、原始错误自修复一次、自己的6张失败帧自检一次、最后自修复一次 | 4 | 0.404724 |
| 合计 | 没有完成可发布整片 | 8 | 1.300978 |

实际用量为输入 97037、输出 138363 tokens，包含失败调用。估算按输入 2 元/百万、输出 8 元/百万计算；没有套用空闲时段或缓存折扣，不是供应商账单。不含 Codex 编排/独立审核、TTS、渲染电力和人工耗时。原始 usage 与请求指纹在各阶段 session 目录，汇总见 `outputs/deepseek-freeform-final-20261020/experiment-summary.json`。

讲稿计划 152.7667 秒。最后候选只渲染出 109.8 秒，在引用未定义的 `DashedRectangle` 时终止。不能将已有部分当作完整课程，后两个 cue 完全没有可见证据。`author-self-review.json` 只检查了上一稿前 26 秒的6张原帧，不是全片复审。

### 干预账本

- 没有向作者传入 Codex 参考片、其源码/讲稿、聊天记忆或上一版具体批评；没有手改任何候选源码。
- 默认思考、low 和非思考分别注册配置和长期协议；后两者机械继承同一 DeepSeek 原讲稿、分镜与相同的实测配音，不另行编内容。
- 修正了两个本方执行器缺陷：字幕 `Group.arrange` 的方向参数改为 numpy 数组；允许 TeX 编译器读取必要父目录的元信息。都发生在候选源码之外，原候选字节不变，不消耗模型修复次数。
- 工具修订分别进入 `fast-fixed` 与 `final` 新目录，保留旧协议/原日志/原稿。非思考分支合计仍只有初稿、两次自修复和一次自检，没有因新目录重置调用额度。
- 旧 runner 快照分别保存于最初实验和 `fast-fixed` 的 generation session；旧字幕支撑保存在 `fast` 的 generation session。变更前后哈希可核对，不覆盖失败。
- 网络和环境变量限制经过检查，但不声称是对抗性安全沙箱。审核曾发现反馈来源验证、原答验证闭环、写入权限等机制缺口；本轮须按实际请求和源文件字节审计，不能仅凭配置声称隔离。

当前证据只支持“这个接口、这些设置与有限修复预算下没有完成目标”。不支持“DeepSeek 永远做不到”，也不能把有不同上下文和人工精修预算的 Codex 参考片拿来做严格同条件能力排名。后续复测必须使用新项目 ID，不能覆盖这些已冻结历史。

诊断展示复用 `experiments/isolated_montage.py` 的独立审批路径：保留拒绝结论、完整已有片段、对应旁白前缀和持续失败警示，不补拍、不修画面、不变速，不进入合格课程发布入口。

### 独立审核结论

`runtime/projects/deepseek-freeform-final-20261020/review.json` 拒绝教学发布。审核实际检查了覆盖全部已渲染 cue 的34个采样画面，其中7帧另以原分辨率查看，并核对输入、候选来源、音频前缀、媒体哈希和全部8次调用费用。没有连续观看或实际听审，不把采样结论扩大为全片审核。

- 多段旧标题持续残留并与新标题叠印；“同一高度”与假设文字也有重叠。
- 三球重合后无法分别观察各自的竖直运动。
- 51.447秒和54.197秒字幕已经宣布同时触地，画面仍在释放位置或空中。
- 75.507秒出现 `a_y=g`，与冻结事实中向上为正的坐标约定不一致，画面未声明切换正方向。
- 开场部分遮挡和初始高度不一致已由模型自修复，但不能抵消后续失败与缺失段落。

审核没有发现本轮保存的请求中包含参考片或外部教学改法，也没有发现候选的人工内容改写。此结论基于实际留档证据，不是服务商签名或对抗性隔离保证。诊断编辑的审批只授权展示失败证据，不改变这份拒绝结论。
