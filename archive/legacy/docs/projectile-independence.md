# 平抛：水平速度与落地时间无关（2026-10-24）

## 边界

这是一条由 Harness 主 Agent 规划、编写、渲染、看图、返工并送独立审核的高中物理讲解片，不是全自动 API 执行器产物，也不是学生学习效果实验。复用仓库已有的 `postproduce/freeform_pilot.py` 制作链、`components/typography.py` 中文字形和 ManimGL 渲染器；没有覆盖旧平抛试片，也没有把本片的分镜升格为通用模板。

- 成片：`outputs/projectile-independence-20261024/projectile-independence.mp4`
- 讲稿/事实：`configs/projectile-independence-20261024.json`
- 场景：`examples/projectile_independence.py`
- 时间轴：`outputs/projectile-independence-20261024/timeline.json`
- 审核：`runtime/projects/projectile-independence-20261024/review.json`
- 独立审核原答：同目录 `review-a.json`、`review-b.json`

## 教学结构

| cue | 时间 | 作用 |
| --- | --- | --- |
| setup | 0.00–11.70 | 同高度、同一点、同时水平射出；先让观众预测谁先落地 |
| together | 11.70–23.70 | 标题保持中性；慢放同飞，画面时钟显示真实物理时间；0.5 s 时等高，1.00 s 同时落地 |
| freeze | 23.70–33.70 | 回到 t=0.5 s：x=1.5/3 m，y 相同 |
| horizontal | 33.70–49.10 | 说明忽略空气阻力；离手后水平方向无合力；每 0.25 s 水平位移等距 |
| vertical | 49.10–63.00 | 竖直初速度与重力相同；墙面投影重合；下落距离 1:3:5:7 |
| time_rule | 63.00–75.23 | 从竖直运动得到 h=½gT²、T=√(2h/g)=1 s，式中无 vx |
| range_rule | 75.23–86.43 | 同样 1 s 内，R=vxT：3 m 与 6 m |
| predict | 86.43–102.63 | 只改高度（5 m→20 m），保留 3.8 s 预测时间，不显示答案 |
| answer | 102.63–119.73 | 两球同时出发；先看 5 m 球 1 s 落地，再看 20 m 球 2 s 落地；随后给出 T、R 都变 2 倍 |
| recap | 119.73–129.73 | 横向速度决定每秒走多远，高度决定走多久，R=vxT |

总时长 129.73 s，1920×1080，30 fps，中文配音 10 段。

## 物理口径

忽略空气阻力；初速度水平、竖直初速度为零；只受竖直向下重力；`g=10 m/s²` 为教学近似。坐标取抛出点 (0,h)，地面 y=0，向上为正：

`x = vx t`，`y = h − ½ g t²`，`T = √(2h/g)`，`R = vx T`。

5 m、g=10 时 T=1 s；vx=3/6 时 R=3/6 m；t=0.5 s 时 x=1.5/3 m、y=3.75 m；20 m 时 T=2 s、vx=6 时 R=12 m。每 0.25 s 的下落距离为 0.3125/0.9375/1.5625/2.1875 m（1:3:5:7）。

## 复现

从仓库根目录执行。`render` 会执行本地场景源码，必须先读源码确认；本链不是远程不可信代码沙箱。

```sh
manimgl_env/bin/python -m manimind.postproduce.freeform_pilot prepare \
  --spec configs/projectile-independence-20261024.json
manimgl_env/bin/python -m manimind.postproduce.freeform_pilot render \
  --spec configs/projectile-independence-20261024.json --quality h --allow-local-code
manimgl_env/bin/python -m manimind.postproduce.freeform_pilot inspect \
  --spec configs/projectile-independence-20261024.json
# 独立审核写入 runtime/projects/<id>/review.json 后才可：
manimgl_env/bin/python -m manimind.postproduce.freeform_pilot assemble \
  --spec configs/projectile-independence-20261024.json
```

`prepare` 使用 Edge TTS `zh-CN-YunxiNeural`、`+3%` 语速，按句保存 `SentenceBoundary`，字幕只显示当前正在说的句子。`inspect` 按每 cue 的 18%/43%/70%/94% 抽 4 张原帧、生成联系表、混音并写 `review-input.json`。`assemble` 校验审核哈希、逐 cue 覆盖、音画时长与全片解码后才合成。

场景额外写 `science-samples.json`（实际球心逐帧反算的 x/y 与时钟）和 `sound-events.json`（发射/落地短音），两者都进入审核哈希；它们不是审核批准。

## 本次通用改动

`freeform_pilot.py` 增加可选的 `video_name` / `subtitle_name` 配置，默认仍为 `projectile-story.mp4` / `.srt`，因此旧实验行为不变；新增测试拒绝带路径分隔符的文件名。原因是新项目不能靠覆盖旧成片名交付，同时不复制一份试片工具。

## 限制

- 审核是两次全新上下文的子 Agent 审片（像素首看 + 源码/时序复核），不是人工审片、不同模型家族共识或学生理解测试。
- 没有做人耳听审：只核对了 TTS 文本、句级时长、响度、非静音和音画时长；发音、语气、音质未评价。
- 连续观看覆盖为每 cue 四帧 + 每 2 s 联系表抽查；任意短暂故障仍可能漏检。
- 画面使用真实比例尺和慢放时钟；20 m 段与 5 m 对照在同一比例尺下绘制，5 m 轨迹因此较小。

## 审核与返工

第一轮两个全新上下文：

- 像素首看 A：approved，83.8；critical 维度均 ≥3。提出开场两球重合、答案数值偏晚、墙面投影不清等非阻断问题。
- 源码/时序 B：rejected，68.8；3 个 blocker：
  1. 5 m 对照球 103.53 s 已落地，但 6 m 与 12 m 落点环一起在 105.93 s（t=2 s）才亮，把 1 s 落地标成 2 s；
  2. `together` 标题「同时落地」在 11.70 s 就给出结论，两球 19.20 s 才落地；
  3. 口播说「水平方向没有力」，但全片未口播/上屏「忽略空气阻力」。

返工：

- 答案段拆分共用时钟：5 m 球在 t=1 时独立落点环与「1 s」，20 m 球在 t=2 时独立落点环与「2 s」，并各写一次 land 音事件。
- `together` 标题改为中性的「同时出发」；落点结果只由画面时钟、落点环和字幕给出。
- 答案段先播「两颗球同时出发 / 5 m 球用1秒 / 20 m 球到2秒才落地」，等 1 s 与 2 s 落点都出现后，才给出 T=2 s、×2、R=12 m 与 T∝√h。
- cue 4 增加独立句「忽略空气阻力。」，两处舞台脚注改为「忽略空气阻力 · g = 10 m/s²（教学近似）」。
- 回看改为把共享时钟从 1.00 倒回 0.50，不再瞬移；竖直段补墙面、投影方向线和「墙」标记；公式段拆出「得到1秒。」；射程 bars 落到地面附近并只留 3 m/6 m 端标；答案箭头与数值同时出现；结尾右栏文案延后到对应句。

第二轮（v021）用两个新的空上下文复审：A2 rejected 82.5（图例圆环压住「子」字）；B2 rejected 80.0（审核期间源码又被修改，证据 stale；另有备注早于 2 s 落地）。返工后 v022–v025 分别修正图例位置、冻结帧等高连线、预测段 5 m/20 m 标签、答案段“先看 1 s/2 s 落地，再给 T/R”，并把末段文案改成符号缩写。

第三轮（v025，129.73 s）终审：A3 与 B3 均 approved，86.3 分，blockers=0；B3 核对 source 哈希 67468161… 与 examples、渲染副本 `story-v025-h.py` 三方一致，40 张原帧与时间轴哈希一致。合并后的发布门禁为 `runtime/projects/projectile-independence-20261024/review.json`。

合成后的 `projectile-independence.mp4` 另做技术校验：H.264 1920×1080 + AAC 双流、时长 129.733 s、全片解码通过、mean_volume −20.1 dB / max −1.4 dB、SRT 38 句；最终音轨未经人耳听审。

## 限制补充

- 第一轮审核基于 124.03 s 版本，第二轮基于 126.63 s 版本，均保留但不用于发布；发布门禁对应 129.73 s 的 v025。
- 5 m 与 20 m 在同一比例尺下绘制，5 m 对照球和轨迹因此明显更小；这是比例尺结果，不是渲染错误。
