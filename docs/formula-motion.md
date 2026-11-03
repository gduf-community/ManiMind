# 公式的连续推导

## 原因与用法

旧平抛片的公式已经是ManimGL矢量`Tex`，但推导使用多条新公式的`FadeIn`，只在射程处对整对象`Transform`。缺少符号身份、等价操作和连续轨迹，不是ManimGL无法实现变量移动。

`components/formula_motion.py`只编排官方原生`Tex`与`TransformMatchingParts`。作者可给同一变量跨式沿用语义ID；同样字形的不同数学对象分别命名，例如分母/系数的`factor`与平方指数`power`。重复字面用明确occurrence选择，不靠字符形状猜对应；未配对符号走原生淡入淡出。它不代写数学步骤、不解析任意代数，也不要求所有公式都必须动画。

```python
from manimind.components.formula_motion import SemanticFormula, matching_transform

left = SemanticFormula(r"gT^2=2h", tokens={
    "gravity": "g", "time": "T", "power": ("2", 0),
    "factor": ("2", 1), "height": "h", "eq": "="})
right = SemanticFormula(r"T^2=\frac{2h}{g}", tokens={
    "gravity": "g", "time": "T", "power": ("2", 0),
    "factor": ("2", 1), "height": "h", "eq": "="})
scene.play(matching_transform(left, right, path_arc=1.0))
```

新作品的引导：先决定需要观众跟住哪个量，再安排它的去向、保留时间和等价操作提示；分步移动比分散字符同时乱飞更重要。审核看真实中间帧，不仅看终态公式；检查身份误配、暂时/持续遮挡、重复残影、负根条件、与图形及旁白的时序。动画存在不等于解释成立，分数或像素运动量不能替代判断。

`matching_transform(..., unmatched_in_place=True)`只让显式匹配的量移动，未配对的括号、运算符、根号原位淡出/淡入，避免原生匹配器将它们拉向整式中心。该选项用公开原生`Transform/FadeIn/FadeOut/AnimationGroup`编排，默认关闭以保留旧场景行为，不复制第三方内部匹配实现。整项换成更复杂表达式时，可以先在原位置收去旧符号，再从同一位置展开新项，而不把一个字形强行扭成整串字符。

## 当前精修

`examples/projectile_formula_motion.py`是明确标注的人工监督精修，不修改原隔离模型作品或声线实验。只重做原V01成片38–58秒的落地推导，保持114秒总时钟和原AAC旁白。`y=0`、公式关联及正根完成事件仍位于局部8、2.4、13秒。示范包括同加重力下落项、同乘2、同除g、在T>0条件下取正根；所有步骤在h>0、g>0下等价。

`postproduce/formula_refinement.py`复用原渲染命令/抽帧/探测工具，创建新版本、归档源码与逐帧符号位置；当前独立Reviewer绑定计划、补丁视频、基础视频、帧证据、轨迹和事件六份指纹，通过后才拼接。内部无损校验master用于逐帧确认其余2820帧与原解码像素相同；播放版从该master以普通H.264 High/yuv420p重编码，避免无损High 4:4:4 Predictive在原生播放器的兼容问题。播放版仍验证3420帧、原AAC包一致及全解码，不能把压缩后的播放版像素声称为逐字节无损。

## 全片精修

`examples/projectile_formula_motion_full.py`在原稿之外复用原物理绘图工具，升级竖直运动相等、射程和数值代入、高度四倍关系、结尾公式组合；落地章通过`play_landing_derivation(scene, start=38, previous_page=...)`组合，不依赖继承示例的布局方法。原稿与旧补丁均保留，不原地改写。

移项将完整重力项视作一组，抬高、横移、落位，使分式线与分母一起移动；0和负号原地消失，避开固定等号和h。细粒度/整项语义视图重绑定不应产生像素跳变。抬高不是任意代数规则，只是作者显式规划的可见轨迹。其余步骤仍须检查中间帧，不能凭终态公式判断没有交汇。

`postproduce/formula_film.py`读取长期`runtime/projects/projectile-formula-film-20261026/plan.json`，归档源码与114秒原时间轴，单次全片渲染。新视觉事件检查17句既有旁白的先后关系；实际运动和帧像素绑定独立Reviewer，通过后才复制新视觉码流和原V01 AAC，检查原生播放器兼容、3420帧及完整解码。没有重调语速、静音重排或新TTS，不声称其余画面与旧片逐像素相同。

全片几何采样保留实际动画字形引用，直接从实时点计算包围框；不使用被Scene重组后可能变空的临时VGroup缓存。空几何显式标记`valid=false`，不能作零碰撞证明。最终审核还需`release_authorized=true`；只有pass状态而另有不发布结论的报告不会放行。

```text
PYTHONPATH=src manimgl_env/bin/python -m manimind.postproduce.formula_film render --plan runtime/projects/projectile-formula-film-20261026/plan.json --output NEW_FULL_ATTEMPT
PYTHONPATH=src manimgl_env/bin/python -m manimind.postproduce.formula_film bindings --output NEW_FULL_ATTEMPT
# 独立Reviewer检查真实帧并返回当前绑定后：
PYTHONPATH=src manimgl_env/bin/python -m manimind.postproduce.formula_film release --output NEW_FULL_ATTEMPT --review CURRENT_REVIEW_JSON
```

## 生命周期

本次全片交付为`outputs/projectile-formula-film-20261026/v004/`。独立Reviewer实看90个清单时点的15张联系表、19张原帧和3张补帧，确认原移项交汇、结尾T复制交汇和展开碎形已修复，五组推导/原20锚点/17句时序通过并明确授权封装。最终114秒/3420帧1080p30，原AAC与新审核视频码流均未改，完整解码通过；全仓库1622通过、2跳过。仍保留短暂原位淡影、射程字形变换与4条退化点几何采样的限制；退化记录被排除，不能用valid=true证明没有碰撞。没有新听审或学生测试。v001透明度读取异常、v002不发布、v003因源码绑定变化被挡，均保留证据，不包装为最终版。

2026-10-26实测交付为`outputs/projectile-formula-motion-20261026/v005/`：新段600帧，完整3420帧/114秒；原AAC包不变，内部无损master其余2820帧解码像素相同，播放版为兼容High/yuv420p。独立Reviewer检查17个真实时点及595条轨迹采样，保留约0.2秒移项交汇的minor问题；未听审/未学生测试。全仓库1576项通过、2项跳过。v004拼接曾回落25fps，已被校验挡住；最终显式30fps，并将framemd5限制到视频轨，两个回归项均纳入测试。没有重新调用TTS，没有覆写旧成片。

| 状态 | 写入者与消费者 | 生命周期及失效 |
| --- | --- | --- |
| `runtime/projects/projectile-formula-motion-20261026/plan.json` | 协调者；渲染器/审核者/发布器 | 本次精修计划；数学、源片、替换区间变化失效，历史副本随版本保留 |
| `runtime/projects/projectile-formula-film-20261026/plan.json` | 全片协调者；制作/渲染/审核/发布 | 全片精修，明确数学步骤、源文件及旁白；输入、时钟或原片变化失效 |
| `SemanticFormula`语义选择器 | 构造者；tag/原生动画 | 单对象进程内元数据；LaTeX或字形结构更换后重建，无外部隐式状态 |
| `outputs/<id>/v*/source/`、render、events、motion-samples、full-formula-motion、review-input | 渲染器/Scene；Reviewer/发布门禁 | 单次版本及其真实轨迹/像素；源码、模型时钟或媒体变化撤销绑定 |
| `runtime/sessions/<id>/`审核与技术日志 | 独立Reviewer/协调者；发布门禁/审计 | 仅绑定当次版本的原始结论，不能沿用旧片批准覆盖新画面 |
| 新delivery及播放文件 | 发布器；用户/审计 | 当前衍生片；源片、源码、帧、音频或审核变化失效，不覆盖旧成片 |

```text
PYTHONPATH=src manimgl_env/bin/python -m manimind.postproduce.formula_refinement render --plan runtime/projects/projectile-formula-motion-20261026/plan.json --output NEW_ATTEMPT
PYTHONPATH=src manimgl_env/bin/python -m manimind.postproduce.formula_refinement bindings --output NEW_ATTEMPT
# 独立Reviewer真实检查并返回上述六项绑定后：
PYTHONPATH=src manimgl_env/bin/python -m manimind.postproduce.formula_refinement release --output NEW_ATTEMPT --review CURRENT_REVIEW_JSON
```

本功能不改第三方资源、不重新实现TeX/视频引擎、不重新生成TTS，不宣称已达到3Blue1Brown整体制作水准。最终仍需用户观看和学生理解测试。
