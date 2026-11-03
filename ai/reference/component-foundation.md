# 模型无关的组件与工作流基础层

## 先划清三层

| 层级 | 做什么 | 当前例子 |
| --- | --- | --- |
| 底层引擎 | 画线、文字、坐标、变换、编码 | 复用ManimGL、SymPy、Pillow、FFmpeg，不重写引擎 |
| 通用教学组件 | 把数学数据绑定到图形，提供布局、时钟、可追溯测量 | `components/` 的坐标系、曲线、点、线段、向量、绑定公式、数值读数 |
| 组合演示 / 整片模板 | 决定教什么、怎样解释、按什么顺序出现 | 旧 `scene_spec/` 割线/切线演示是组合；`instantaneous_velocity.py` 是完整选题答案 |

**整片模板不算通用组件。** 新组件层没有汽车、固定速度模型、12段分镜或任何模型厂商配置。手写fixture属于工程校准，不算LLM成功样本。

## 组件目录

`manimgl_env/bin/python -m manimind.components.pipeline catalog` 输出实际注册目录和未实现清单。

| 当前组件 | 输入 / 绑定 | 边界 |
| --- | --- | --- |
| 坐标系 axes | 两轴范围、刻度、单位、是否等比例 | 二维，必须包含零，刻度数量有上限 |
| 函数曲线 curve | 安全表达式树、时间参数 | 每帧121点采样；不自动处理奇点、裁剪、不连续函数 |
| 动点 point | 两个坐标表达式 | 统一参数驱动；通用点不自动声称位于某条曲线上 |
| 线段 segment | 两个端点，可虚线 | 不允许退化或超出坐标范围 |
| 向量 vector | 起点和终点 | 必须等比例数学单位，避免方向、长度因拉伸误导 |
| 绑定公式 formula | 引用curve ID | 公式从同一表达式生成，不能另填不一致的TeX |
| 数值读数 readout | 表达式、精度、单位 | 固定锚点，数字与图形使用同一参数快照 |

数轴、角度弧、黎曼和、概率分布、公式步骤变换、真正通用的局部放大、矩阵变换、电路、受力图**尚未实现**。旧速度片的局部放大不能直接当成通用镜头登记。

## 数据契约

输入示例为 `configs/component-foundation.json`，协议版本 `components-0.1`。镜头数量、顺序和对象组合可变，不固定为某条教学片。每个镜头必须声明目标、字幕、坐标系、参数、组件和关键帧。参数关键帧完整给出状态；渲染、采样点、数值读数消费同一状态。

表达式只接受有限数值、已声明符号及 `op/args` 树；支持加减乘除、有限整数幂、sin/cos/sqrt/abs。不接受Python、TeX、文件路径、任意函数或代码字符串。使用显式SymPy构造生成公式，无 `eval/exec/sympify/parse_expr/lambdify`。限制节点数、深度、参数数量、表达式结果范围；零除、负平方根、越界、退化对象直接报错，不能静默删掉。

一期布局是二维图形区加固定说明区，最多6条组件说明；不是任意页面设计器。公式只在建立镜头时排版，数值用原生数字对象更新。刻度与数字共同使用原生刻度序列，数字置于绘图区外保护带，避免曲线和辅助线穿字。标签越界、碰撞、刻度与数字错位和读数/几何/可见填充与描边颜色不一致写入逐帧报告。布局报告不证明像素清晰度、美感或教学效果。

## 工作流

当前可运行：

```text
明确作者的镜头JSON
  -> 严格协议检查
  -> 按目标帧率逐帧数学预检
  -> 不可覆盖的渲染版本
  -> 实际对象几何/标签/数值测量
  -> 原帧 + 源码 + 时间位置 + 哈希证据包
  -> 独立Reviewer审片
  -> 绑定版本发布工程样片
```

每个镜头保留至少15%的终值停留。抽帧包含起始、变化过程、终值与停留，审片必须区分过渡与最终状态，不能把目标字幕提前出现本身当成数值错误。结构检查、数学检查、视觉审核、教学评价分开，不用“能渲染”替代“适合交付”。

这是先验收组件的**静音工程路径**。整片配音与逐句时间轴目前仍在 `postproduce/`；通用语音编译、教学规划、预算内自动修复、课程覆盖评测还未统一接入。后续模型适配只负责把输入转换成这个稳定协议并保存原回答，不允许每换模型就重写渲染器或题目模板。

### 复现

先安装现有渲染环境及 `components` 可选依赖（SymPy）。本轮不调用任何LLM或TTS API。

```bash
manimgl_env/bin/python -m manimind.components.pipeline check --plan configs/component-foundation.json
manimgl_env/bin/python -m manimind.components.pipeline init --plan configs/component-foundation.json
manimgl_env/bin/python -m manimind.components.pipeline render --project-id component-foundation-20261018 --quality h
manimgl_env/bin/python -m manimind.components.pipeline inspect --project-id component-foundation-20261018 --attempt 1
# 独立Reviewer写入 review-001.json，实际审看每段原帧之后：
manimgl_env/bin/python -m manimind.components.pipeline publish --project-id component-foundation-20261018 --attempt 1
```

已有项目不可再次init。改输入需新项目ID；修组件可对同一冻结计划生成新的attempt，旧失败和证据保留。命令中的attempt需使用实际渲染编号，不能借用旧版审批。当前CLI不自动请求模型修复，也不自动产生审核许可。

Reviewer文件必须含 `reviewer_role=reviewer`、独立的 `reviewer_id`、`status=approved`、空 `blockers`、完整 `hashes`、实际查看的 `inspected_frames`、四项 `checks=pass`，以及整个 `review-input.json` 文件的 `reviewed_input_sha256`。发布验证截图清单的镜头、时间、路径、SHA关联未变，并复核全部截图的实际内容哈希；只改截图和清单SHA也不能复用旧审批。

## 状态生命周期

| 路径 | 写入者 / 消费者 | 生命周期 / 失效 |
| --- | --- | --- |
| `runtime/projects/<id>/component-plan.json` | planner / worker、reviewer、assembler | 长期冻结计划；输入修改必须新ID |
| 同目录 `review-<attempt>.json` | 独立reviewer / publisher | 长期证据记录；代码、参数、配置、视频、测量或原帧变动失效 |
| `runtime/sessions/<id>-components/events.json` | coordinator / lead、reviewer | 本轮追加事件；保留失败，不写成长期数学事实 |
| 同目录 `command.lock` | 当前CLI / 其他CLI | 排他锁，命令结束释放；异常残留需核查进程后人工处理 |
| `outputs/<id>/plan.json`、`preflight.json` | 编译器 / renderer、reviewer | 冻结数据副本与可重建预检；输入变化失效 |
| `outputs/<id>/renders/<attempt>/` | renderer / reviewer | 每次独立源码、媒体、逐帧测量、原帧及证据；不覆盖历史版本 |
| `component-demo-v<attempt>.mp4`、`delivery-<attempt>.json` | publisher / 用户 | 通过独立审核的不可覆盖工程样片；不是已配音教学成片 |

作者及干预记录是显式元数据，不是安全认证。`pipeline_llm_requests=0`只说明本入口不调用模型，不能替上游模型调用背书；上游usage未接入前明确标为未验证。审核者角色字符串仍来自可信操作者，不是经过认证的多人审批系统。

本批渲染验证环境为macOS。初版使用Hiragino Sans GB；`studio-0.2`视觉样式使用本机PingFang SC与Helvetica Neue，两个字体文件内容均参与审核哈希，未复制系统字体进仓库。当前没有覆盖GPU驱动、系统LaTeX及全部第三方安装文件的环境指纹，不承诺跨机器逐像素复现。切换机器或工具链后需要重新渲染、审看原帧，跨平台字体配置和运行环境固定是后续部署工作。

## 视觉样式 studio-0.2

针对“线条和字体显得廉价”的反馈，仅改视觉层，不改冻结的镜头JSON、数学表达式、参数关键帧或27秒时长：

- 中文：PingFang SC，标题Semibold，正文Regular；标题/说明/字幕有独立字号和间距。
- 数字：Helvetica Neue，复用Pillow与ManimGL ImageMobject拼接字形，固定数字宽度和基线，保留ASCII负号、小数点及负零归零规则；不再使用逐字Pango拼接的DecimalNumber显示。
- 公式：仍使用安全表达式生成的原生Tex，字号提高，与普通说明分开。
- 线条：坐标轴1.2、边框0.85、辅助线1.7、主曲线3.1；箭头thickness由3调为1.5，tip_width_ratio由5调为3.8；轴标保留保护带。
- 色彩：主图保留蓝/黄/红/绿的语义分工并降低饱和度；多数说明改为中性文字，色彩集中在图形、标记与读数。
- 版式：扩大函数绘图区；公式、图例、读数按语义分组，读数与标签同排，不再均分成高大彩色列表。

`visual_style`由renderer写入每版逐帧报告，供Reviewer识别风格版本；代码/字体变化使该版证据失效。32项FreeType缓存只活在单进程，单个数字对象最多12种字形模板；均非长期或短期协作状态。`bitmap_colors`读取实际图像源像素，不用目标颜色参数代替证据；它仍不等于最终编码画面的逐像素审美验证。

本轮最终发布 `outputs/component-foundation-20261018/component-demo-v005.mp4`：27秒、1920x1080、30fps、静音。与003逐帧对比，810帧的时间、参数和数值均一致；全仓931项测试通过、1跳过。独立Reviewer审看005全部12张原帧、与003同帧对照及连续过零帧，复跑378项相关测试后写入 `review-005.json` 放行，发布清单为 `delivery-005.json`。004为同轮视觉候选，没有对外发布；003及旧审核保留。此次没有验证课堂投影、移动端和用户主观偏好，不把工程审核等同于达到3b1b质量。

## 原有任务板加固

`task_board.py` 对缺失依赖、重复ID、自依赖和环拒绝放行。已完成任务重新打开时，递归回退其下游任务，包含审核与打包，保留不相关支路。`invalidated_task_ids` 和 `graph_errors` 随既有CLI/API结果及运行日志返回，不另建混合上下文。独立审核任务不能由lead代签完成。

任务状态失效不删除旧媒体或历史review文件；真正发布仍必须校验当前产物哈希。旧自由代码 `pipeline-run` 与历史实验不因此自动成为统一的新组件路径，迁移需要逐步完成，不能把一处状态修复宣称为全系统无人值守。

## 验收与后续顺序

本轮fixture覆盖正弦平移、向量首尾相加、二次方程的图像解；同一套组件渲染不同数学对象，不复用速度片分镜。

### 2026-10-18 实测记录

- 全仓测试：900通过，1跳过；Reviewer另行复跑26项组件原生几何与发布关卡测试。
- 同一手写fixture实际渲染3版，前2版保留blocked报告，不算成功样本。
- 修复：Arrow/Dot原生填色默认值覆盖、非整数轴端点导致刻度/数字错位、辅助线穿刻度字、截图清单未完全绑定审批。
- 第3版：1920x1080、30fps、27秒、810帧；逐帧含9990条刻度测量与4050条颜色测量，机械检查零问题。
- 独立Reviewer实际查看12张原帧，逐镜头覆盖初态、变化与终态，批准范围仅为静音工程校准。
- 已发布 `outputs/component-foundation-20261018/component-demo-v003.mp4`，交付清单为同目录 `delivery-003.json`，审批为 `runtime/projects/component-foundation-20261018/review-003.json`。
- 本入口未调用外部LLM/TTS API。不代表模型首轮通过率、自动修复能力、课程覆盖或课堂教学效果已经验证。

### 后续顺序

1. 当前批次：数据契约、共享状态、布局及逐帧测量、依赖失效、独立审核。
2. 下一批：公式推导步骤、局部放大、数轴/面积/矩阵等高频教学组合；补正负例回归和音画事件对齐。
3. 随后：知识点事实与教学目标输入、教材来源、整片编排、有限修复、成本和干预统计。
4. 以上验收后：在冻结组件和同题输入上接入不同LLM，对比首轮通过率、修复率、真实审片问题和人工介入量。
