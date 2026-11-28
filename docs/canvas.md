# Canvas 主舞台

2026-11-28 起，新课程画面以 Canvas 为主舞台：每支片写成一个网页场景，画面是时刻 t 的纯函数 `seek(t)`，由锁定版本的 [HyperFrames](../resources/references/hyperframes/docs/guides/rendering.mdx) 逐帧渲染。ManimGL 退为素材源，负责 3D、路径级形变/笔画描出和 KaTeX 排不了的 LaTeX，以透明通道片段并入。已发布的 ManimGL 课程不回改。

**发布边界**：监督入口和独立审核链接入 Canvas 之前，Canvas 成片只作样片，不进入发布。

## 组成

| 位置 | 内容 |
| --- | --- |
| `src/manimind/canvas/assets/` | 仓库自有的浏览器端库：`motion.js`（缓动、弹簧、拖尾光点、光环、火花、滚动数字、荧光笔、字幕），`engine.js`（平面与镜头、线性变换、箭头、逐字弹入文字、KaTeX 公式及逐符号连续变形），`adapter.js`（把 `seek(t)` 挂到 HyperFrames 的 GSAP 时间轴），`base.css` |
| `src/manimind/canvas/project.py` | 把场景目录组装成静音 HyperFrames 工程 |
| `src/manimind/canvas/render.py` | 调用锁定版本渲染，做确定性检查，写回执 |
| `src/manimind/canvas/voice.py` | 配音按恒定增益规则混入，视频流无损封装 |
| `src/manimind/canvas/timing.py` | 从逐字对齐生成场景时间表和字幕行 |
| `tools/hyperframes/` | 锁定 hyperframes 0.9.43、gsap 3.14.2、katex 0.19.1 |
| `examples/canvas/` | `eigen-intro`（特征向量入门，55.5 秒）、`eigen-derive`（特征值求解推导，与 ManimGL 版同一配音） |

## 准备

```bash
cd tools/hyperframes && npm ci
```

需要 Node.js 22 以上、仓库内 `manimgl_env/bin/ffmpeg`，以及锁定的 chrome-headless-shell（默认取 Playwright 缓存的 151.0.7922.34，可用环境变量 `MANIMIND_CANVAS_BROWSER` 指定）。

## 场景目录

```text
scene.json   id、duration、layers（自下而上的 canvas / fx 层）、scripts、fonts、可选 audio
*.js         场景脚本；其中一个定义 window.createFilm = () => ({ duration, seek(t) })
```

`audio` 是完整配音句子的列表 `[{"src", "start", "volume"}]`，`src` 相对仓库根目录。

## 渲染

```bash
PYTHONPATH=src manimgl_env/bin/python -m manimind.canvas.render examples/canvas/eigen-intro --out outputs/<project>/<attempt> --check 27.5:28.5
```

流程：组装静音工程 → `hyperframes lint` → `hyperframes render` 出画面 → 配音混入并封装为 `film.mp4` → 确定性检查 → `receipt.json`。输出目录只能新建，已存在就拒绝。

`--check START:END` 只组装这一段（同一份场景代码、同样的片中时刻），用 1 个和 3 个 worker 各渲染一遍 PNG 并逐字节比对。并行 worker 会打乱帧的渲染顺序，比对通过说明画面与渲染顺序无关。每支片至少选一段有公式变形或淡入淡出的时间做检查。

## 场景必须遵守

- **同一个 t，同样的像素。** 不用 `Math.random()`（用 `M.rng(seed)`），不用 `Date`，不在帧之间保留状态。每次 `seek` 先清空画布，并调用 `F.reset()`。
- **公式层保持合成状态。** `base.css` 给 `.fx`、`.mm-fx` 设置了 `will-change`，不要去掉。否则透明度变化后浏览器会换栅格化路径，跳回同一时刻时会有几个像素不同（2026-11-28 在 KaTeX 括号边缘实测出现过）。
- **画布固定走 CPU。** `adapter.js` 会在场景代码之前用 `willReadFrequently: true` 取得每个画布的 2D 上下文。场景不要自己另建画布或换上下文参数：Chrome 默认会在画了若干帧后把画布切到 GPU，导致每个 worker 的第一帧抗锯齿不同（2026-11-28 用测试场景实测到）。
- **发光画在 Canvas 上。** 不用 CSS `text-shadow`，用 `M.halo` 在公式下层的画布上画。
- **时间只来自时间表。** 动作时刻取自配音的逐字对齐（`timing.py`），场景代码里不写死秒数。配音变了只要重新生成时间表，画面自动跟着重排。

## 配音

完整句子原样按片中时刻放置：不剪、不变速、不压缩、不做动态归一化。整轨只加一个恒定增益，目标 −16 LUFS，真峰值不超过 −1 dBTP，两者冲突时以峰值为准。画面视频流直接复制，不重新编码。HyperFrames 自带的混音会额外抬高约 2.7 dB、导致削波，所以不用。

## 状态

| 状态 | 写入者 → 读取者 | 生命周期与失效 |
| --- | --- | --- |
| 场景目录（`scene.json`、脚本、生成的 `timing.js`） | 作者、时间表生成脚本 → `project.py` | 随场景版本保存；配音或画面变化时重新生成 |
| 渲染尝试 `outputs/<project>/<attempt>/` | `render.py` → 审核者、发布者 | 一次性创建；所列输入、版本或浏览器任一变化即失效；失败保留，重跑写新目录 |
| `tools/hyperframes/node_modules` | `npm ci` → `render.py` | 随 lockfile；版本变化须重新渲染 |
