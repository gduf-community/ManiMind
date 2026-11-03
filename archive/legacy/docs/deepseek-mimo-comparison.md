# DeepSeek 1017 与 MiMo 同题对照

## 目的与边界

分别评估生成和审片，不将合法JSON、成功渲染、候选自评或一次修复等同于视频质量。
生成沿用 `spec-suite-20261017` 的5次任务（3次同题、2次参数变体），冻结原始提示、SceneSpec契约、音轨规则和工程组件。DeepSeek采用官方 `deepseek-flash` 滚动别名，2026-10-18官方文档对应 V4.1-Flash-1017，非思考模式；历史MiMo采用用户指定网关及非思考模式。请求返回的model字段必须保留，不能由别名证明上游权重版本。

生成预算沿用最多8次请求、每run最多2次；不人工修改候选JSON。审片为4组原帧，每模型/组1次、最多4096输出token，不重试，共最多8次。缺少对应密钥时请求前阻断，不借用其他提供商密钥；认证、额度或限流错误阻止继续消耗同批请求。MiMo网关价格未知；DeepSeek只记录官方高峰无缓存上界估算，不作为实际账单。

## 审片协议

- 两边发送完全相同的system、purpose、brief、匿名图片路径与图片字节；各样本无对话历史，不看旧审核结论或另一模型回答。
- 输入包含原始1920x1080抽帧、时间戳、SceneSpec、精简时间轴；没有音频或完整连续视频。不是纯视觉测试，也不评估听感。
- 独立Reviewer在候选调用前核验原帧，保存ground truth；候选答案返回后再独立裁定，不使用关键词命中冒充语义评分。
- 统计必须发现的错误召回、无阻塞对照的误报、证据是否具体、是否虚称看过整段视频。建议项与数学阻塞分开。
- 4组相近样本包含旧稿与修复稿，不是4个独立知识点；不能外推真实课堂总体准确率。
- 候选审片结论永不直接写入SceneSpec正式 `review.json`；新视频仍须独立审核后合成。

## 状态归属

| 记录 | 写入者 / 消费者 | 生命周期与失效 |
|---|---|---|
| `runtime/projects/ds-mimo-review-20261018/comparison.json` | coordinator / evaluator, reviewer, lead | 本轮长期冻结；协议、输入、来源、提供商变化失效 |
| 同目录 `ground-truth.json`、裁定 | reviewer / evaluator, lead | 本轮证据标准；证据或门槛变化失效，不发送给候选 |
| `outputs/ds-mimo-review-20261018/` | coordinator / candidate, reviewer | 可追溯媒体副本/无答案输入；哈希变动阻断 |
| 每模型/组独立 `collaboration.json` 与 `dialogue.json` | coordinator/model_collaborator / reviewer, lead | 复用既有长短期协议；单请求预算，失败保留 |
| `runtime/projects/spec-deepseek-1017-20261018/` | coordinator, reviewer / worker, lead | 新生成套件，不覆盖MiMo旧记录 |

## 入口

在仓库根目录使用 `manimgl_env/bin/python`：

```bash
python -m manimind.experiments.model_comparison prepare
python -m manimind.experiments.model_comparison init-generation
python -m manimind.scene_spec.experiment generate --suite spec-deepseek-1017-20261018 --run poly-a
python -m manimind.scene_spec.experiment render --suite spec-deepseek-1017-20261018 --run poly-a
python -m manimind.scene_spec.experiment inspect --suite spec-deepseek-1017-20261018 --run poly-a
python -m manimind.experiments.model_comparison review --provider deepseek
python -m manimind.experiments.model_comparison review --provider mimo
python -m manimind.experiments.comparison_report
```

其他run同样独立执行；审核及反馈后才能修复或合成。重复运行review跳过已有尝试，不覆盖失败或暗中重试。上述命令是复现入口，不能当作全部已执行或成功的记录；实际完成情况以账本和报告为准。

## 2026-10-18 生成实测

DeepSeek实际调用5次，全部首轮产生合法SceneSpec，5次渲染、逐帧几何检查、独立Reviewer检查及最终合成都通过，无修复。独立Reviewer每条查看contact和8张原分辨率帧，共40张原帧；未实时播放全片、未听音频。最终合成检查音视频流时长并进行FFmpeg完整解码，不等同于听感审核。

| 指标 | 历史MiMo | DeepSeek 1017 |
|---|---:|---:|
| 首轮有效JSON | 5/5 | 5/5 |
| 首轮渲染与几何检查 | 5/5 | 5/5 |
| 首轮独立审核 | 3/5 | 5/5 |
| 修复请求 | 2 | 0 |
| 最终交付 | 5/5 | 5/5 |
| 首轮生成请求平均耗时 | 2.777秒 | 1.865秒 |

已逐条核验：两边首次生成提示完全相同，工程组件、配音、时间轴及渲染配置哈希相同。新片没有旧片的“0.5到0.1减半”错误，阶段标题与位移强调的搭配更一致。但仍只有一种镜头原型，只有5次生成，且API提供商/采样实现和调用时间不同；不能据此认定总体100%通过，也不能将组件共享的观感上限算作模型提升。

## 审片执行与成本

两家各完成4次盲审，16张原帧、4组输入提示哈希逐组相同，没有向候选发送ground truth。DeepSeek平均8.476秒/请求，MiMo平均19.665秒/请求。这里只是API延迟，不是成片端到端耗时。

DeepSeek生成+审片共9次，返回用量为26,884输入、7,859输出token，按已记录的高峰无缓存价上界估算0.11664元；生成部分0.02113元、审片部分0.09551元。未核实实际扣费，未计缓存/闲时优惠、强模型独立审核、渲染、配音、人工与组件研发成本。MiMo网关价格未知，不能比较真实人民币成本。

审片原回答中存在误报、算术错误及结论/发现矛盾，不能据“返回了JSON”放行。独立标准在 `runtime/projects/ds-mimo-review-20261018/ground-truth.json`，调用前哈希在 `ground-truth-lock.json`；最终裁定与汇总分别在同目录 `adjudication.json` 和 `outputs/ds-mimo-review-20261018/report.json`。所有统计仅适用于非思考模式，未测试DeepSeek思考模式的上限。

## 独立审片裁定

| 指标 | MiMo | DeepSeek 1017 |
|---|---:|---:|
| 必改问题被识别 | 2/3 | 3/3 |
| 必改问题正确列为blocker且理由成立 | 1/3 | 2/3 |
| 顶层结论符合标准 | 3/4 | 3/4 |
| 无阻塞对照中出现错误blocker指控 | 1/2 | 1/2 |
| 顶层接受但内部列blocker的矛盾回答 | 2/4 | 0/4 |
| 无依据阻塞根因组数 | 6 | 5 |

按顶层verdict看，MiMo在两个无错误对照上均写acceptable，而DeepSeek误挡一个。但MiMo的case02内部同时列了两个无依据blocker，所以不能声称MiMo误报为零。根因组数在同一模型/样本内去重，不能误读成错误视频条数或总体误报率。

严格匹配下，DeepSeek在case01确实注意到了减半措辞，但把关键阻塞理由落在动画中间值不是目标值上，又把稳定终态的标题问题降成建议，因此只计“检测到”，不计“可靠阻塞”；裁定单独记录宽松匹配的敏感性。MiMo在case01漏掉真实减半错误，却用其他错误指控给出blocked，不能因结论碰巧相同而给真错误识别分。

两家都把正常目标预告与过渡读数的差异上升为阻塞；DeepSeek还将凹函数h=1的位移写成5（实际3），以及在另一例中算错中间位移。MiMo还将未采样到的后续切线阶段判为未实现。各自有效建议仍有参考价值，不因这些错误全盘否定，但不能直接作为自动修复或交付许可。

结论：当前约束下优先试用DeepSeek作为镜头数据生成器；终审继续保留独立Reviewer和确定性数值检查。下一步应单独比较思考模式、明确过渡/终态标签、算术工具以及审核JSON一致性门禁，不将此次小样本外推为已稳定量产。
