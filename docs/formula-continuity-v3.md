# 公式连续性监督入口

2026-11-03。创作引导沿用[公式连续性](formula-continuity.md)：选择推理承重的关系，呈现可跟踪的数学身份、来路、去向和运算，不规定所有字符动画。绘图仍采用 `configs/visual-first-workflow-v4.3.1-unit.json`，旧动画输入与旧发布器保持冻结。

## 当前实际入口

使用 `manimind.postproduce.traceable_film_v3` 的 `evidence/gate/install/silent`，参数与[v2](formula-continuity-v2.md)一致。v3复用冻结v2的当前视频PNG取证、尺寸/像素核对、原生bindings及独立上下文检查，再核对**全部**声明的PNG和联系表哈希。准备前拒绝所有既有输出路径，包括悬空符号链接。

```bash
PYTHONPATH=src manimgl_env/bin/python -m manimind.postproduce.traceable_film_v3 evidence --attempt CURRENT_ATTEMPT --output NEW_LOSSLESS_DIRECTORY
PYTHONPATH=src manimgl_env/bin/python -m manimind.postproduce.traceable_film_v3 gate --attempt CURRENT_ATTEMPT --visual-review CURRENT_REVIEW
PYTHONPATH=src manimgl_env/bin/python -m manimind.postproduce.traceable_film_v3 install --attempt CURRENT_ATTEMPT --visual-review CURRENT_REVIEW --draft DRAFT --output NEW_NARRATION
PYTHONPATH=src manimgl_env/bin/python -m manimind.postproduce.traceable_film_v3 silent --attempt CURRENT_ATTEMPT --visual-review CURRENT_REVIEW --narration NEW_NARRATION --narration-review CURRENT_TEXT_REVIEW --output NEW_SILENT
```

独立首看使用新目录的PNG和联系表。报告 `formula_continuity.evidence_index` 指向 `supervised-evidence.json`，`evidence_index_sha256`为其实际哈希，其余逐项前/中/后、身份与运算观察字段不变。原 `formula-evidence.json`保留；新派生清单引用其哈希并单独绑定v3监督器源码。

## 失效范围

动画实现与时间轴影响渲染输入；v3是纯审核监督器，不改变几何或时钟，源码版本单独绑定在本轮独立取证包。修监督器要重新准备取证并独立审核，不应只因核验逻辑升级重渲完全相同的画面，也不能冒称旧批准适用于新协议。当前修片仍须经v3的新批准，旧v1/v2审查失败保留。

作者写长期plan的动作选择；取证器写当前媒体绑定的新证据包；独立Reviewer写短期审核；发布器写版本媒体及来源收据。任何声明资产、原索引、监督器、当前媒体或报告变化使本轮额外批准失效。PNG相同不证明讲解有效，真正看图和独立新旧回归仍是必要判断；听审与学生理解另记。

这是新监督入口，不是旧 `chapter_workflow.prepare`（仍选v4.2）或旧自主执行器已自动升级。新公式返修直接消费已准备的v4.3.1 plan，经v3安装正式稿与静音发布后，原音对齐/声音/字幕继续复用冻结 `unit_film`，不绕过独立审核。
