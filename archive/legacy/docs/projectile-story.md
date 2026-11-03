# 自由叙事试片：飞得更快，会落得更晚吗？

这是 Codex 监督创作的原创试片，不是低价模型隔离对照，也不是学生学习效果实验。

## 制作边界

主 Agent 负责选题、事实、叙事引导、配音和编排；独立 Manim Worker 编写 `examples/projectile_story.py`；另一 Reviewer 检查实际渲染画面后决定是否放行。复用已有字形处理和 ManimGL 渲染器，不复制第三方引擎，不改写旧实验产物。

本片经过协作修复：主 Agent 提供实际帧反馈并补充项目路径、逐句字幕同步的集成修改；Worker 修正图形、过渡与叙事时序。这些干预均属于本片制作，不可计为任何候选模型无辅助生成的结果。

创作采用连续的探测球配送实验。研究依据见 [动画案例研究](research/learning-video-20261020/07-animation-vs-knowledge.md)。本片自定叙事、配色和角色，不将它们升格为所有选题必须遵守的模板。音效为程序合成的原创短音，不使用 Alan Becker 的角色、美术素材、音乐或分镜。

物理事实采用 [OpenStax 平抛模型](https://openstax.org/books/physics/pages/5-3-projectile-motion)：忽略空气阻力，初始竖直速度为零，统一重力加速度。在教学近似 `g=10 m/s²`、高度 5 m 下，飞行时间 1 s，水平速度 3/6 m/s 对应水平位移 3/6 m。将高度变成 20 m，时间变为 2 s；6 m/s 对应位移 12 m。图形以球心代表模型质点，慢放仍须显示真实物理时间。

## 复现

从仓库根目录执行。`render` 会执行场景源码，必须先读源码确认；本流程不是远程不可信代码沙箱。

```sh
manimgl_env/bin/python -m manimind.postproduce.freeform_pilot prepare
manimgl_env/bin/python -m manimind.postproduce.freeform_pilot render --quality h --allow-local-code
manimgl_env/bin/python -m manimind.postproduce.freeform_pilot inspect
```

独立 Reviewer 消费 `outputs/projectile-story-20261020/review-input.json`、实际原帧、源码、时间轴和音频证据，在 `runtime/projects/projectile-story-20261020/review.json` 写入审核。通过后：

```sh
manimgl_env/bin/python -m manimind.postproduce.freeform_pilot assemble
```

默认 Edge TTS 中文旁白；`prepare --provider say` 才显式使用 macOS 离线语音，不静默降级。线上 TTS 接收公开旁白文本，不接收项目凭据。

当前平抛场景的关键动作依赖 Edge 的句级边界，复现本片应使用默认 provider；`say` 音轨准备入口存在，但本片未适配其缺少句级边界的情况。

Edge TTS 的句级边界保存为 `audio/*-sentences.jsonl`，并以绝对视频时刻写入 `timeline.json` 的 `spoken_spans`，用于核对接收、落地和结论出现的时机。它是语音服务的段落时间估计，不替代听审；相邻边界可能有约 50 ms 的重叠。已有渲染后重新 prepare，会先将当前音轨、时间轴和审核输入归档到短期会话 `before-prepare-*`，避免覆盖上一版的核查依据。

画面字幕与导出的 SRT 共用 `subtitle_segments`，只显示当前正在说的句子，保留至下一句开始或 cue 结束，避免整段字幕提前透露尚未发生的结果。

## 状态生命周期

| 状态 | 写入者 | 消费者 | 生命周期及失效 |
| --- | --- | --- | --- |
| `configs/projectile-story.json`、场景源码 | 主 Agent、Manim Worker 各自负责 | 制作入口、Reviewer | 项目源文件；修改后旧音轨或渲染及审核失效 |
| `runtime/projects/<id>/production-context.json` | 编排器 | Worker、Reviewer | 项目级事实、脚本及任务记录；prepare 依据当前配置刷新 |
| `runtime/projects/<id>/review.json` | 独立 Reviewer | assemble | 当前媒体版本；任何绑定输入或媒体变化即失效 |
| `runtime/sessions/<id>-production/` | 编排器 | 主 Agent、Reviewer | 本次制作日志、渲染回执、旧音轨和历史样本；不能当作长期事实 |
| `outputs/<id>/timeline.json`、`audio/` | prepare、inspect | 场景、Reviewer、合成器 | 配音与音效派生物；文本、语速、音色、音效变更失效 |
| `outputs/<id>/story-v*`、帧证据 | render、inspect | Reviewer | 按版本保留；源码或渲染依赖修改后不能用于新审核 |
| `sound-events.json`、`science-samples.json` | 场景（可选） | 混音、Reviewer | 本次渲染的事件及状态样本；重渲染前归档旧样本 |
| `review-input.json`、`delivery.json`、成片 | inspect、审核后的 assemble | Reviewer、用户 | 当前版本索引与发布证据；旧审核不能发布新版本 |

审核检查数学正确性、叙事可理解性、实际画面和配音时序，不以规定镜头形式代替质量。每段必须检查真实像素；听审、动态观看和学生理解测试未覆盖的部分必须记录为限制，不作虚假完成声明。技术检查涵盖音轨非静音、时间轴偏差、审核哈希及最终完整解码。

当前入口是受监督原型：没有渲染沙箱、自动审核身份认证、并发项目锁或通用无人值守重试。其成功不能计为其他国产模型的独立成功率。
