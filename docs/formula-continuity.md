# 看得见的公式变化

2026-11-03。一次导数修片暴露出两个不同问题：首次差商直接整行淡入；后续虽有符号移动，却先在目标行显现副本，观众看不到量从上一步来到这一步。终式正确、推导行齐全和代码有 `Transform` 都不足以说明连续表达成立。

## 制作引导

先选择真正承担推理的动作：从图形关系构建比值、把已知关系代入、合并同类项、提出共同因子、约去非零因子、从具体位置推广到一般位置等。让观众知道当前跟踪的是哪个量、它现在担任什么角色、这一步进行了什么运算。

保留可读旧式时，可以复制相关变量或完整项，从它的实际位置可见地进入下一步。同字形的不同角色分别标识，新产生的项明确作为新项出现。项的整体移动、错峰、局部强调、图形联系或其他能说明关系的方法均可选择，不要求每个字符都飞、不规定统一路径、秒数或镜头数。

先在目标行淡入一份旧式，再隐藏语法、横移少量字形，容易产生“另起一行”的断裂；整式被拆成散字时也可能看不出运算。在正常节奏下观察实际源、过程和目标，必要时调整空间与时间，不能用终态停留替代必要过程。简单新标签允许直接显现。

原配音能复用时保留完整意群和实际来源，但不要为保持旧总长压缩复杂解释。文字、focus或节奏变化均须重新做当前原音时序与单套字幕审核。优化保留当前有效推导、图形联系、单位、条件；把“旧版已有的保留项”和“本轮新增的改进目标”分开。

## 已实现的监督入口

新制作或返修选 `configs/visual-first-workflow-v4.3-unit.json`。旧profile、旧发布器和旧媒体冻结，不修改历史批准。

渲染前的plan中写 `formula_transitions`，每项为 `id/operation/source/target/purpose`。作者按本课选重要关系，不要求固定数量；该选择随plan、源码和真实渲染一起绑定。`sources`显式包含本文件、`src/manimind/postproduce/traceable_film.py`，使用新复制辅助时也包含 `src/manimind/components/formula_transfer.py`。

独立视觉首看报告保留原有全部质量字段和当前bindings，另写：

```json
{
  "formula_continuity": {
    "checks": [{
      "id": "ratio_construction",
      "traceable": true,
      "identity_finding": "从当前真实画面说明同一个量的来路与去向",
      "operation_finding": "从画面说明这一步的数学关系与条件",
      "evidence": [
        {"phase": "before", "time": 1.0, "frame": "/absolute/current-frame-before.png", "sha256": "实际帧哈希", "finding": "真实观察"},
        {"phase": "during", "time": 2.0, "frame": "/absolute/current-frame-during.png", "sha256": "实际帧哈希", "finding": "真实观察"},
        {"phase": "after", "time": 3.0, "frame": "/absolute/current-frame-after.png", "sha256": "实际帧哈希", "finding": "真实观察"}
      ]
    }]
  }
}
```

以上是字段示意，不是真实审核或可发布报告。实际证据来自当前 `review-input.json` 的帧和时间；需要的动作时点应在渲染前加入 `review_times`。门禁核对帧真实存在、哈希与当前媒体索引/时刻一致、选中动作完整和独立身份。它不能自动证明审核描述符合画面，仍须独立观察，不能把有证据字段当作看过。

正式稿安装和静音发布用新监督适配器：

```bash
PYTHONPATH=src manimgl_env/bin/python -m manimind.postproduce.traceable_film gate --attempt CURRENT_ATTEMPT --visual-review CURRENT_REVIEW
PYTHONPATH=src manimgl_env/bin/python -m manimind.postproduce.traceable_film install --attempt CURRENT_ATTEMPT --visual-review CURRENT_REVIEW --draft DRAFT --output NEW_NARRATION
PYTHONPATH=src manimgl_env/bin/python -m manimind.postproduce.traceable_film silent --attempt CURRENT_ATTEMPT --visual-review CURRENT_REVIEW --narration NEW_NARRATION --narration-review CURRENT_TEXT_REVIEW --output NEW_SILENT
```

新入口先核验连续性，再复用原生科学/视觉独立审核和另一个上下文的新旧内容回归。它不代写批准、不改TeX引擎，也不调用TTS。后续 `unit_film` 原音对齐、声音与字幕发布继续绑定不可变的已审静音来源；追加审核字段变化同样使来源失效。

这是**明确选择的新监督入口**，不是所有旧CLI已自动升级。v4.3不得绕回旧install/silent命令规避新增核验；旧自主模型执行器尚未自动接通，不宣称已具备端到端量产能力。

## 生命周期

| 状态 | 写入者与消费者 | 生命周期与失效 |
| --- | --- | --- |
| plan中的动作选择 | 作者 / 渲染器、独立首看、门禁 | 当前课版本；数学、选择或源码改变须新版本 |
| 可见复制动画 | 作者与原生运行时 / 场景、像素审查 | 一次动画；只在源当前位置创建副本，cleanup保留旧式并安装目标；不担保任意路径无碰撞 |
| 独立连续性观察 | 当前首看Reviewer / traceable_film、发布来源链 | 当前绑定媒体与实际帧；任何来源、报告、时间或帧改变失效 |
| 新静音及后续有声交付 | 原发布器 / 对齐、字幕、观众、审计 | 继承当前批准与原声来源；不继承旧片批准，不表示已听审或学生测试 |
