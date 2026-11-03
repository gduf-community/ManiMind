# 特征向量新题：作者交接

本目录是版本化、可重建的输入，不读取被忽略的 runtime 或旧视频、旧评审。
这是大学线代新题，不复用物理、导数、圆周率或其他场景实现。

- 场景：`examples/eigen_visual.py`，类名 `EigenDirectionsLesson`
- 视觉时钟：210 秒，30fps，共 6300 帧；8 章、26 事件、27 焦点
- Profile：`configs/visual-first-workflow-v3.1.json`，`revision_mode: fresh`
- `plan.json`、`narration-draft-v001.json` 是运行输入的可重建副本
- 已写入的运行输入位于 `runtime/projects/eigen-directions-20261028/`
- `native-clock-contract.json` 来自共享 `lesson_native_harness.native_run` 的完整执行；不是计划时间冒充测量，也不是像素渲染报告
- 真实 TeX 使用 `manim_renderer._render_environment()` 提供的 PATH；测试原生选择器、身份轨迹与清理，不创建 GL 相机或视频

## 复现

```bash
PYTHONPATH=src manimgl_env/bin/python -m pytest -q tests/test_eigen_visual.py
```

测试覆盖精确有理数矩阵插值、两个特征子空间、负倍数、零向量排除、非特征向量、分情况穷尽推理、分解恒等式、每帧网格/基向量端点、首尾相接重组、直接矩阵像、真实90度旋转、完整时钟/事件/focus、以及真实 TeX。
缺失本机 TeX 时仅真实 TeX 两项可跳过；已实测的作者环境中两项均通过。

## 科学主线

从 `Av=lambda v, v!=0` 到两个分量，作差得到 `(lambda-1)(x-y)=0`。
若 `x=y`，非零使 `x!=0`，第一分量化为 `3x=lambda x`，得到 `lambda=3` 和所有非零倍数 `(1,1)`。
若 `x!=y`，乘积为零使 `lambda=1`，代回得到 `x+y=0` 和所有非零倍数 `(1,-1)`。
不除以可能为零的分量，不以已知答案替代求解。这两种情况覆盖全部非零向量。

几何使用同一个纯函数 `transform(v,t)=((1-t)I+tA)v`；坐标轴不跟随网格。
一般向量不是长度缩放示意。两特征分量首尾相接，与直接矩阵像在全程重合。
旋转反例限定实数范围；非零实向量转90度与自身垂直，因而不能平行。
定义是“仍在同一直线上”，不要求特征值为正或长度不变；没有扩展负特征值专题。

## 冻结与边界

源码 SHA256：`9b28098232167167d994e346f6ea2ad61172936de0244d17f8d9acb7d0b5f2e1`

源码已通过完整 native 时钟和真实 TeX 检查后冻结。底部 y984 以后预留给后置字幕。
变量交换次序处只匹配不交叉的身份；不同垂直通道容纳未匹配语法淡入淡出。
占位几何和真实 TeX 检查不证明最终中文字形、瞬时完整像素无重叠或学生理解；主控还需真实渲染和两阶段独立审核。
草稿有27个意图段，未安装、未批准，不能冒充视觉通过后的正式稿或完整声音排程。
未渲染、未SSH/TTS、未批准、未发布、未提交git。没有已知运行阻断。

MIT官方课程来源见plan中的 `source_references`。只参考定义和课程范围，所有几何与构图自行创作，不复制其视频或图形。

此目录的写入者为线代作者，消费者为测试与主控；生命周期为可重建的版本化测试输入。
源码、计划、字体、运行时或时序变化需重跑并显式更新契约，不能把fixture作为审核批准。
