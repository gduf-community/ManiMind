# ManiMind

ManiMind 是一个面向数学科普动画生产的多 Agent 编排项目。输入论文和笔记，输出可审核的讲解脚本、分镜、Manim 数学动画、HTML 科普片段，以及后续配音、字幕、剪辑拼接所需的结构化产物。

仓库定位是“编排层”，不重写外部渲染引擎内部实现。
`ClaudeCode/` 仅作为可选参考源码包，其可复用编排能力已抽取到 `src/manimind/`。

## 当前架构要点

1. 预启动阶段加载文档与配置，检测工具链，注册能力路径。
2. 主 Agent 解析论文与笔记，产出研究总结、公式目录与项目状态。
3. 协调 Agent 切分分镜并并发派发 HTML / Manim / SVG 子任务。
4. 子 Agent 分别回写长期上下文和短期协作上下文。
5. 审核 Agent 通过后，进入配音、字幕、剪辑拼接。

## 课程目录与单元制作

关键公式连续表达的新监督返修选[v4.3.1绘图引导与v3监督门禁](docs/formula-continuity-v3.md)：按本课选推理承重的公式变化，独立核对同一量的可见来路、去向与运算，过程帧实际解码对照当前媒体及时间，核验全部声明图像和联系表。正式稿安装和静音发布经 `traceable_film_v3` 再复用旧原声/字幕流程；审核器单独绑定取证包，不因纯核验升级重绘相同动画。不把所有字符动画化，也不宣称旧自主执行器已自动接通。

[公式动画创作引导](docs/公式动画创作引导.md)补充具体到一般的数值/条件处理、原位更新与历史对照、完整项的可追踪性和理解节奏；它是跨题目建议，不是规定所有变量移动或固定片长的模板。

已有[高中课程总目录](docs/curricula/README.md)：[数学17单元、92个候选课题](docs/curricula/high-school-mathematics-v0.1.csv)，[物理17单元、103个候选课题](docs/curricula/high-school-physics-v0.1.csv)。各课记录主要先修、新增理解、可复用基础、出口任务及建议拆分边界；195个课题插槽不是已完成视频数，也不强制一项一条。当前为v0.1教研初稿，尚未逐项核对最新版课标和教材，未落实年级、学期及必修/选择性必修分册。

课程单元沿用[连续意群工作流](docs/course-unit-workflow.md)的课程context、口语稿和完整意群协议；新课程及关键公式返修优先选择上述`configs/visual-first-workflow-v4.3.1-unit.json`与v3监督入口。v4.2保留为既有语言基线，不代表新公式审核已自动启用。由课程位置决定本课理解增量，先审核视觉与讲稿，再按完整意群生成原声；实际音画、内容回归和单套字幕分别审核。创作保留引导，审核不规定统一镜头数、片长或教学方法。[机械波首轮记录](docs/wave-unit-trial-20261028.md)保留真实失败和版本证据；旧profile来源不改写。

[机械波三课原声对齐记录](docs/wave-audio-alignment-20261031.md)说明完整原音复用、动画细节保留、字词估计字幕、独立审核及桌面/iCloud交付状态。完整媒体、实际来源和同步观察分别记录，不以本地复制替代云端上传确认。

这是已实现的监督式入口；旧Sol/DeepSeek自主执行器尚未自动支持全部新课程context、声音和字幕环节，不能只替换profile就宣称已能自动量产。

开场先用清楚的本课标题和自然引入帮助定位，再进入对象或推理；不统一规定片头秒数。已审单套字幕正文可用[监督式片头扩展](docs/lesson-opening.md)补片头：新增引入独立审核，完整正文视频不重编码、不变速，新旧内容回归和接缝像素复核后才交付。它仍是监督制作入口，技术连续性不等于已听审。

## 视觉优先制作

后续制作可选`configs/visual-first-workflow-v3.1.json`：按理解难度分配解释，精简低价值重复，用画面解决歧义而不以免责声明补救。沿用v3审核契约，旧版冻结配置不变；详见[创作引导](docs/understanding-workflow.md#把解释用在难点)。

监督式有声成片可使用[单套字幕后处理](docs/focus-captions.md)：从当前已审讲稿和真实声音生成字幕候选，独立像素审核后才发布；术语同时核对画面、旁白与字幕，不只替换字幕。既有自主模型入口尚未自动接入这一新增阶段。

已有作品的监督优化现使用[v3有效内容回归](docs/content-regression.md)：先记录任务选定基线的解释功能，允许换布局和等价表达，但不能以简洁或高分掩盖关键步骤/动效丢失。新版首看和新旧比较由不同上下文执行，回归未过时正式稿与发布门禁拒绝。既有自主入口还没有基线比较动作，不能只换提示词就当作已自动接通。

单条视频也可使用[理解优先v2工作流](docs/understanding-workflow.md)：创作端提供跨题目引导，审核端验证可见推理、注意力、认知节奏、整句语义对应和迁移支持；不固定分镜、角色或时长。监督入口支持真实可读区间与完整WAV对齐；声音主机离线时只交付标明静音的主片及可续配音计划，不硬拼旧声。新Sol自主适配器实际注入并复核编辑标准，但尚未自动接通新focus数据和Windows声音阶段；本轮监督样片与冻结模型对比明确分开。

当前新增[视觉优先工作流](docs/visual-first-workflow.md)：先生成并独立审核无配音、无朗读字幕的动画主片，再依据实测视觉事件写后配音讲稿。由GPT-6.1 Sol三角色自主制作与返工，最终开源语音生成后置。该入口与下面保留的受约束组件实验、旧配音先行流程分开，不把静音主片当作最终有声成片。

Windows 5080 主机已实测独立SSH、双向文件校验和Tailscale跨网络调用：Mac切到手机热点后仍能生成并接收Qwen样音。连接、恢复和限制见[连接说明](docs/windows-5080-connection.md)。[独立GPU配音接口](docs/remote-speech.md)支持本地固定预设试听及独立VoiceDesign原创中文选声，保留原音、参数和来源收据，不自动合成或发布；整机重启、真实听审和音画同步仍须独立验收。

## 受约束镜头实验

当前的低价模型验证路径为 `scene_spec/`：模型生成受约束 JSON，可信 ManimGL 组件执行，逐帧检查后交独立 Reviewer，审核通过才合成。它是独立于 `pipeline-run` 的有界实验入口，目前只覆盖多项式割线/切线镜头，不代表任意课程已可自动量产。命令、实测与失败记录见 [模型实验文档](docs/model-benchmark.md#scenespec-10-组件实验)。

## 通用组件优先

新增模型无关的 `components/` 基础层，把坐标系、曲线、点、线段、向量、绑定公式和数值读数与固定选题模板分离。先用不同题目的手写fixture验收，再做模型适配；工程样片不计为LLM生成成功。能力清单、离线命令、工作流及尚未完成的边界见 [组件基础层](docs/component-foundation.md)。

## 目录结构

```text
ManiMind/
├─ AGENTS.md
├─ README.md
├─ docs/
├─ configs/
├─ scripts/
├─ src/manimind/
├─ tests/
├─ resources/
│  ├─ skills/html-animation/
│  ├─ skills/manim/
│  └─ references/hyperframes/
├─ runtime/
├─ outputs/
└─ logs/
```

## 初始化步骤

### macOS

Apple Silicon Mac 可用用户级工具链完成恢复，不要求 Homebrew：

```bash
bash scripts/setup-manimgl.sh
source manimgl_env/bin/activate
python -m manimind.main doctor
pytest -q
```

脚本会创建 Python 3.12 隔离环境，在项目环境内准备 ManimGL 与静态
FFmpeg，并使用用户目录下的 TinyTeX 提供 XeLaTeX/CTeX。详细接管状态见
[`MAC_START_HERE.md`](MAC_START_HERE.md)。

### Windows

1. 初始化目录与占位文件：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\init-workspace.ps1
```

2. 同步第三方精选资产（白名单）：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\sync-thirdparty-assets.ps1
```

源仓库不在项目根目录时，可显式传路径：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\sync-thirdparty-assets.ps1 `
  -HtmlSkillSource "<AI-Animation-Skill-main 路径>" `
  -HyperframesSource "<hyperframes-main 路径>"
```

3. 检查依赖：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\check-prerequisites.ps1
```

默认数学动画后端为 ManimGL。首次使用先创建隔离环境：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup-manimgl.ps1
```

渲染器会自动加载根目录 `manimgl.yml`，使用精简 XeLaTeX/CTeX 模板并固定背景与中文字体默认值，兼容 Windows MiKTeX。

## 关键约束

- 第三方资产统一放在 `resources/`，不再使用独立 `vendor/`。
- 长期上下文只写 `runtime/projects/<project_id>/`。
- 短期协作上下文只写 `runtime/sessions/<session_id>/`。
- 审核未通过不得进入后处理。

## 编排 CLI（新增）

以下为保留的基础CLI，运行成功不等于内容审核通过；其中旧拼接入口不具备本轮独立公式审核和内容回归的发布门禁。课程成片请使用上方的v3监督入口及其后续原音/字幕链，不用旧`assemble-video`代替验收。仓库只读审计及适用范围见[现状报告](docs/仓库现状审计-20261103.md)。

- `plan <manifest.json>`：生成标准项目计划。
- `context-pack <manifest.json> <role_id> <stage>`：生成角色上下文包。
- `context-pack ... --render-prompt-sections`：额外输出提示词分段渲染结果。
- `task-update <manifest.json> <task_id> <status> <actor_role>`：按状态机推进任务。
- `context-pack` 默认会阻断角色非法阶段请求；需要显式放行时使用 `--allow-disallowed-stage`。
- 三个命令支持 `--session-id`，并会把状态与事件日志落盘到 `runtime/projects/<project_id>/` 与 `runtime/sessions/<session_id>/`。
- `pipeline-run <manifest.json> --render-manim`：在 Manim Worker 生成 ManimGL 代码后立即渲染视频并抽取关键帧，作为审核 Agent 的视频级证据来源；渲染、抽帧、黑屏、低对比、低细节、跨帧几乎无运动、缺少解释性动画信号、公式缺少视觉 companion 或跨镜头变量颜色冲突会强制阻塞审核。
- `pipeline-run <manifest.json> --manim-backend manimgl|manimce`：选择代码生成和渲染后端，默认 `manimgl`，旧项目需要兼容时可显式选 `manimce`。
- `quality-audit <manifest.json>`：不调用 LLM，读取已有 Manim 代码与渲染证据，复用确定性审核规则生成 `outputs/<project_id>/quality-audit.json` 与人工审片用的 `outputs/<project_id>/quality-summary.md`。
- `assemble-video <manifest.json>`：读取长期上下文中的 Manim 渲染证据，按清单镜头顺序拼接分段视频，生成 `outputs/<project_id>/<project_id>-final.mp4`；可用 `--output-name` 指定文件名。
- `build-subtitles <manifest.json>`：读取旁白脚本和分段视频真实时长，生成 `outputs/<project_id>/<project_id>.srt`。
- `mux-subtitles <manifest.json>`：把 SRT 作为软字幕轨封装进成片，生成 `outputs/<project_id>/<project_id>-final-subtitled.mp4`。
- `burn-subtitles <manifest.json>`：把 SRT 烧录进画面，生成平台通用的 `outputs/<project_id>/<project_id>-final-burned.mp4`。
- `build-voiceover <manifest.json>`：按平台使用 Windows SAPI 或 macOS `say`，根据旁白脚本生成离线 WAV 旁白。
- `mux-voiceover <manifest.json>`：把旁白合成进烧录字幕版视频；如果旁白和视频时长不一致，会按旁白长度缩放视频节奏。

## Web API 骨架（新增）

- 新增 `backend/` FastAPI 骨架，直接复用编排内核：
  - `POST /api/projects/plan`
  - `GET /api/projects/{project_id}/runtime`
  - `POST /api/projects/tasks`
  - `POST /api/projects/tasks/update`
  - `POST /api/projects/context-pack`
- 启动示例（安装 `api` 依赖后）：

```bash
python -m pip install -e ".[api]"
python -m uvicorn backend.main:app --reload
```

## 文档入口

- [课程单元与连续意群制作](docs/course-unit-workflow.md)：课程context、跨课衔接及多事件声音排程的新监督入口；不覆盖旧逐句路径
- [课程体系与讲课研究](docs/research/teaching-system-20261028.md)、[高中物理/数学视频填充目录](docs/curricula/README.md)（研究初稿，尚未接入自动制作）
- [docs/README.md](docs/README.md)
- [docs/通用项目架构模板.md](docs/通用项目架构模板.md)
- [docs/上下文与状态设计.md](docs/上下文与状态设计.md)
- [docs/第三方整合.md](docs/第三方整合.md)
- [docs/ClaudeCode抽取清单.md](docs/ClaudeCode抽取清单.md)
