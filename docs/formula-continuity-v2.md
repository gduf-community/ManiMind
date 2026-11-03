# 公式连续性门禁修正

2026-11-03。沿用[制作与审核引导](formula-continuity.md)，创作侧不新增动作数、路径、片长或字符运动要求。v4.3实现复核发现两项来源/独立性不足，原字节与诊断render保留，未作正式片批准。

新选 `configs/visual-first-workflow-v4.3.1-unit.json` 与 `postproduce/traceable_film_v2.py`。渲染sources显式包括两个traceable_film模块及这份说明，冻结实际使用的门禁；后续原音/字幕仍复用冻结的 `unit_film`。

原渲染器仍生成JPEG概览，不改变它及历史输入。渲染后、独立看图前先运行新取证入口：

```bash
PYTHONPATH=src manimgl_env/bin/python -m manimind.postproduce.traceable_film_v2 evidence --attempt CURRENT_ATTEMPT --output NEW_LOSSLESS_DIRECTORY
```

该动作按当前原生索引时刻从**实际视频重新抽取PNG**，不把JPEG转PNG；新目录create-only，失败保留，未知结果不自动重放。它保存 `formula-evidence.json`、逐帧哈希和供查看的联系表，绑定当前attempt、原生bindings、视频和取证器源码。作者和Reviewer不能把索引生成等同看过图。

独立首看使用这份新索引的实际PNG和联系表。报告在原有 `formula_continuity.checks` 外增加 `formula_continuity.evidence_index`（该JSON绝对路径）及 `evidence_index_sha256`，每项前/中/后帧来自这份无损索引。v2取代v1“只能引用原JPEG索引帧”的实现限制；旧索引和旧报告不改写。

之后运行v2的 `gate/install/silent`，原参数保持不变；例如：

```bash
PYTHONPATH=src manimgl_env/bin/python -m manimind.postproduce.traceable_film_v2 gate --attempt CURRENT_ATTEMPT --visual-review CURRENT_REVIEW
```

修正包括：首看和回归的Reviewer Agent与context都必须不同；每个源/过程/目标证据除核对当前无损索引/哈希/时间，还核对图像格式和宽高，实际解码PNG和当前视频对应时刻比较像素指纹。相同RGB字节但不同宽高也拒绝。索引自洽不能证明图像来自该媒体。判断仍由独立观察者完成，像素相同不证明数学解释有效。

旧v4.3和v1是保留的诊断实现，不能用于本轮正式稿安装或静音发布。当前v4.3.1必须经 `traceable_film_v2`；旧原生CLI没有自动接通额外核验。这不是新模型能力对比或安全认证。

所有状态延续原契约：作者在长期plan选重要动作；独立首看在短期session写真实观察；渲染和发布器写版本媒体与收据。媒体、源码、选择、报告、帧、时刻或上下文改变须重审；作者不代写通过。
