# 瞬时速度试片

本实验用于检验经过逐镜头设计、实际渲染和独立审核后，ManimGL 能否比旧版生成视频更清晰。它是 Agent 主导的精修试片，不代表现有 `pipeline-run` 已具备无人干预的同等能力。

## 内容与分工

- 只解释一个问题：对于理想运动 `s(t)=4t²`，第二秒这一瞬间的速度是多少。
- 先展示汽车运动与平均速度，再用同一组数据建立割线、缩小时间窗口、排除直接除以零、化简差商、真实局部放大，最后回到汽车。
- Planner 的结构化事实、旁白与分镜在 `configs/velocity-pilot.json`；数学事实来自直接代数推导，不伪装成论文结论。
- Manim Worker 维护 `examples/instantaneous_velocity.py`，Reviewer 只读取结构化上下文、源码、渲染视频和抽帧，输出独立审核结论。
- 只使用 ManimGL 原生图形。汽车是原创程序化图形，不复制第三方模板，也不修改 `resources/`。

## 复现

先启用 `manimgl_env`，安装可选试片配音依赖 `python -m pip install -r configs/velocity-pilot-requirements.txt`。试片依赖独立列出，不改变主工作流的锁定环境。

```bash
python -m manimind.postproduce.pilot prepare
python -m manimind.postproduce.pilot render --quality m
python -m manimind.postproduce.pilot inspect
# 审核草稿、修订源码，然后重新渲染：
python -m manimind.postproduce.pilot render --quality h
python -m manimind.postproduce.pilot inspect
# 独立 Reviewer 检查本次 review-input.json 对应的画面并写入 review.json。
python -m manimind.postproduce.pilot assemble
```

配音默认使用 `edge-tts==7.3.1` 的 `zh-CN-YunxiNeural`，会向 Edge 在线语音服务发送这份公开性质的数学旁白，不发送仓库、密钥或用户资料。网络不可用时可显式 `prepare --provider say` 使用 macOS Tingting，产物会记录实际引擎，不静默替换。

每句先生成语音，实测长度，预留 0.3 秒视觉准备与至少 0.65 秒收尾，再向上对齐 30fps。动画使用相同时间轴，合成时不使用整体变速。字幕在 Manim 场景中绘制；导出的 SRT 是旁路交付，不再二次烧录。

本机实际像素测试发现，ManimGL 下 PingFang SC 的“小”、Heiti SC 的“点”等字形有填充缺损；Hiragino Sans GB 的局部测试正常，但完整标题中的“谈”仍出现缺损。因此最终采用 Pillow/FreeType 以四倍字形尺寸生成中文透明贴图，再由 ManimGL 原生 `ImageMobject` 显示，避免中文轮廓三角化路径。数学公式、曲线、动态数字仍为原生 ManimGL 对象。中文布局沿用 Pango 的尺寸，不把第三方字体文件复制进仓库。此实验明确依赖本机 `/System/Library/Fonts/Hiragino Sans GB.ttc`，跨平台复现需替换字体路径并审片。

字体对照图保存在 `outputs/velocity-pilot/font-diagnostic/`，临时诊断源码在本轮 session 中。换机器或字体后应重新检查中文，而不能只确认字体名称存在。

## 状态生命周期

| 路径 | 写入者 | 消费者 | 生命周期与失效规则 |
| --- | --- | --- | --- |
| `configs/velocity-pilot.json` | Planner | 配音、Manim Worker、Reviewer | 长期源配置；修改后重新 prepare、render、review |
| `runtime/projects/velocity-pilot/production-context.json` | Planner | Worker、Reviewer、Lead | 长期项目事实、分工、叙事；源配置改变时重建 |
| `runtime/projects/velocity-pilot/review.json` | 独立 Reviewer | 合成器、Lead | 长期审核结论；源码、配置、时间轴、音频或视频哈希变化立即失效 |
| `runtime/sessions/velocity-pilot-20261014/` | Coordinator、渲染器 | Lead、Reviewer | 这次协作的临时状态、失败记录和渲染日志，不作为长期事实 |
| `outputs/velocity-pilot/audio/` | 配音准备器 | 动画时间轴、合成器 | 可重建媒体；文本、音色、语速、服务改变时失效 |
| `outputs/velocity-pilot/timeline.json` | 配音准备器 | Manim Worker、Reviewer、合成器 | 精确到帧的媒体时间轴；旁白变化时重建 |
| `outputs/velocity-pilot/text-assets/` | Manim Worker 场景代码 | ManimGL ImageMobject、Reviewer | 可重建的中文贴图；每次渲染按文本、字号、颜色和字体重新生成，不复用旧像素 |
| `outputs/velocity-pilot/render.json`、`frames/`、`review-input.json` | 渲染器、抽帧器 | Reviewer | 当前渲染证据；重渲染或任一输入变化后重新生成 |
| `outputs/velocity-pilot/instantaneous-velocity.mp4`、`delivery.json` | 合成器 | 用户 | 审核通过后的可回放交付；不覆盖旧项目成片 |

审核必须包含身份、实际看过的抽帧、数学/视觉布局/叙事/时间轴/真实放大五项检查、阻塞项及哈希。工具只验证报告完整性和版本一致性，无法靠哈希证明审美质量。Reviewer 需要诚实记录未验证内容，不能把抽帧对比度当成“精良”评分。

## 已知边界

此版本仍是固定选题的实验入口，不替代主工作流。合成语音不等于真人配音；抽帧和代码审核不等于连续播放的完整感官审核；数学正确也不等于学生确实理解。片长、分辨率、实际审核与最终文件以生成的 `delivery.json` 为准。
