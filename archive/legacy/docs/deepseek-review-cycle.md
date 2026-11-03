# DeepSeek 独立审片与返工

本轮 `deepseek-review-cycle-20261021` 机械沿用上一轮 DeepSeek 自己的讲稿、源码及缓存配音，从新项目重新渲染；不读取上一轮独立审核、作者自评、Codex 参考片或主对话。不属于从零创作实验，也不是与 Codex 同预算能力排名。

`experiments/freeform_review_cycle.py` 继承自主作者工具，新增独立 DeepSeek 审片上下文。审片者只收到公共任务、当前源码、旁白时间轴、实际图片；每两段一组机械抽取各6帧，可以自行追加最多6个时间点，再进行全片因果一致性检查。分段否决不能被总评覆盖。原始意见与其来源哈希直接交回作者，不由协调者筛选、改写或补充内容建议。作者可自由改稿、改场景，再渲染与自检。

模型和非思考模式、公共任务不变。最多3轮独立审片，即初审及最多2次返工后的复审；新增作者最多48次请求，审片最多32次请求，最多8次渲染（含未改种子）。作者与审片合计10元高峰未缓存估算上限，未知用量即停。历史种子成本另列，不伪装成本轮成本；未计编排、最终独立验收、TTS和本地计算，不是供应商账单。

作者和独立审片使用同一家模型，但不共享对话状态。模型自评、API 审片通过均不自动产生发布许可；最终由另一独立审核 Agent 读取实际媒体，满足既有哈希绑定发布关卡后才合成。不通过则只能另外审批带提示的诊断展示。

## 状态归属

| 状态 | 写入者 / 消费者 | 生命周期与失效 |
| --- | --- | --- |
| `runtime/projects/<id>/review-cycle-protocol.json`、`seed-provenance.json` | coordinator / author、reviewer、evaluator | 冻结本轮协议和原始种子；输入或工具变更必须新实验 |
| `runtime/sessions/<id>-generation/review-cycle-state.json`、锁 | coordinator / executor | 本轮阶段、游标和原始反馈引用；不授予发布权；中断不自动重发未决请求 |
| `runtime/sessions/<id>-independent-review/request-*/` | reviewer API runner / reviewer、evaluator | 原始请求、实际图片哈希、原答、失败和用量；不可覆盖 |
| 同目录 `cycle-*/` | deterministic sampler、reviewer / author、evaluator | 当前版本证据和原始评语；媒体改变后不再是当前审核，仍可供作者返工参考 |
| `outputs/<id>/cost-report.json`、`review-cycle-report.json` | evaluator / user | 从所有角色请求和阶段重建；新请求后重算，不替代成片验收 |
| 讲稿、源码、音视频、最终 `review.json` | 继承作者/渲染器/独立 reviewer | 沿用现有来源校验、修稿失效、独立发布门禁 |

```sh
manimgl_env/bin/python -m manimind.experiments.freeform_review_cycle \
  --config configs/deepseek-review-cycle-20261021.json
```

局限：抽帧不等于连续观看或听审，同模型异上下文仍可能共享盲点；结构校验不能验证评语事实正确；沙箱不是对抗性安全保证。本轮只测试增加独立审片反馈后的改进，不预先保证通过。

## 格式失败与新实验

首轮独立审片6次调用后，总评把同一条issue的字段拆为多个对象，结构校验拒绝，作者尚未返工。该轮原答、媒体及约0.23856元估算成本原样保留，不手工合并评语。

新编号 `deepseek-review-cycle-20261021-v2` 仍沿用原始同作者种子，不继承失败轮的评语。`experiments/freeform_review_retry.py` 仅扩展审核输出的结构恢复：每组最多一次 API 自修复，输入同组原始请求/图片、原答和原始校验报错；不输入人工内容建议，二次无效就停止。所有调用计费，失败首轮费用计入本轮10元合计估算上限。冻结旧实现不修改，新增协议写入 `runtime/projects/<id>/review-schema-repair-protocol.json`；短期 `schema-error.json` 由校验器写、reviewer消费，保留历史，不授予发布权。

```sh
manimgl_env/bin/python -m manimind.experiments.freeform_review_retry \
  --config configs/deepseek-review-cycle-20261021-v2.json
```

## 本轮实测

v2 独立审片完成4组分段检查和1次全片检查，结论为返工，原始评语直接进入全部作者请求。作者随后执行38次调用：1次无效动作、1次讲稿、3次完整代码、14次逐字改码、7次渲染、7次分段看图、2次提交、2次API查询和1次主动停止。另有1次机械种子渲染，合计8次渲染中7次完整成功。

作者在第8次渲染后继续改码，旧版审片覆盖正确失效；两次提交均未得到发布许可，最后报告预算耗尽、当前源码未渲染并停止。因此只完成“初审 -> 作者返工”，没有完成返工后的独立复审，更不是稳定的两轮通过。保留最后完整的 `story-v008-h.mp4` 与其源码快照；当前 `candidate.py` 是后来未渲染版本，不能混称为该影片源码。

7次分段看图中，`range_formula` 和 `height_prediction` 各被选6次，开头两段各1次，另外3段没有进入本轮作者自检。原始旁白逐段未变。可观察到自检集中在局部、未完成全片收尾；不能据此把问题简单归为模型永远无法胜任，也不能把多次看图当成全段覆盖。

成本：v2作者估算3.57554元、独立审片0.186198元，加格式失败轮0.23856元，本轮新增合计4.000298元；此前种子成本2.463072元另列，累计6.46337元。不含Codex工程/最终验收、TTS、本地计算，也不是供应商账单。v2五次审片请求没有触发格式自修复分支，该分支只有回归测试覆盖，不能宣称已获线上成功率验证。

来源审计核对43次v2请求、28个图片附件、17份含种子的成功源码版本，源码可从模型原答和逐字改码重放；冻结输入通过，没有协调者内容修改。最后完整渲染的source/video/audio/timeline/spec均与历史证据匹配，见 `outputs/<id>/provenance-audit.json`。相关测试196项通过、1项跳过。最终画面判定另见独立历史渲染审核，不由作者或来源审计代替。

最终外部审核查看全部7个cue的4张联系表、7张既有原尺寸帧和22张补抽帧，拒绝教学发布：高度段字幕与T/根号2T的图示冲突，射程公式与数值重叠，答案字幕先于实验揭晓。仅批准绑定v008、原mix.wav与持续警示的诊断展示。该审核者的记忆索引检索意外暴露历史摘要，因此外部验收不是严格零历史盲审；这一偏差在报告中披露，没有传给DeepSeek作者或API审片者。没有听审、连续观看或学生测试。报告为 `runtime/projects/<id>/archived-render-v008-review.json`，不是最终代码的发布批准。
