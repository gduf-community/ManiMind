# 课程单元与连续意群工作流

日期：2026-10-28。接续[教学研究](research/teaching-system-20261028.md)与[配音研究](research/narration-prosody-20261028.md)。新监督入口另立版本，不修改旧逐句发布器、旧声线选择或旧片批准。具体实机进展以本轮交付记录为准。

## 创作层给引导

目录与单元教案说明本课新增理解、假设先修及前后课意图。作者可选演绎、情景、比较、预测或其他方式，不规定钩子、幕数、片长、字数、每段长度或一定有测验。

开场先帮助观众定位：可用清楚的本课标题，配一段自然引入，把眼前的问题与已有知识接起来，再进入需要追踪的对象或推理。系列课还可轻接前课留下的问题。不要一开口就要求辨认尚未介绍的颜色、符号或操作；也不必朗读整页标题、列一长串目标、预告全部答案或添加宣传口号。标题页、情景或直接提出问题都可采用，停留长短服从实际引入与可读性，不规定所有视频统一片头秒数。

给已审成片补片头时，单独制作和审核引入，保留正文全部有效内容、原始节奏和既有字幕；核查衔接处的音量、停顿与字幕退场。新增片头不授权剪掉正文解释，也不能直接沿用旧片批准来批准新合片。片头只需完成定位与引入，不承担本应由正文讲清的难点。

已有单套字幕正文的补片头监督入口见[片头扩展](lesson-opening.md)，本次三课的实际返修、保留核验和交付边界见[机械波开场记录](wave-openings-20261029.md)。不把监督式新入口宣称为旧自主执行器已自动支持。

`curriculum.py`从当前CSV和编辑者拥有的`unit.json`提取一课所需出口与相邻意图，不注入整套教材、旧作品或临时失败日志。先修无环不代表最优教学顺序；无诊断时明确`assumed_not_tested`。课程条目和学生掌握状态不随MP4生成自动完成。

2026-10-28首轮profile为`configs/visual-first-workflow-v4-unit.json`：底层渲染兼容v3，交付契约另标连续意群。新发布器复核`lesson_context`及全部课程来源；当前语言返修选择下述v4.2，早先版本保留。

### 正向解释与整节通读

2026-10-29的`configs/visual-first-workflow-v4.1-unit.json`沿用现有交付、科学和时序协议，为新制作及语言返修提供正向讲述引导；其后v4.2补充口语表达，成为当前监督返修的选择。历史来源保留；旧自主执行器仍需实际接入和端到端验证。

讲解从对象的真实行为、关系和原因向前推进。例如空间图解释“同一时刻，各位置的位移分布”，半波长解释“从波峰走到相邻波谷是半个波长，再走半个波长到下一波峰”，相消过程解释“合位移为零时，图中标出的质点仍有速度，后续形变随运动继续发展”。图形和过程承担依据，语言带观众看清这些依据。

讲稿审核增加整节通读：逐段说明各句引入的新信息和它与前后句、画面的联系，检查是否反复回应观众尚未提出的错误猜测。重复的纠错语气可以整段重写；有教学作用的因果、单位、条件、变量连续性和观察过程仍须在实际作品中保留。换成“而非”“不意味着”等近义结构，叙述关注点可能依旧没有改变，审核要看整段意义。

必要比较、反例、数学否定和科学条件各自承担明确的推理任务。词语搜索用于定位，编辑判断依据句意与整节观看体验；工作流没有否定词数量上限、全局禁词表或按词频自动放行。

语言返修会同步处理画面文字、完整意群配音和字幕，并重新审核当前时序。新文案采用独立版本；原声音、旧批准和当前云盘版本作为基线保留，待完整返修通过实际门禁再替换交付。

### 通俗的口语

`configs/visual-first-workflow-v4.2-unit.json`把讲稿定位为说给观众听的解释。具体说清谁在动、哪里变了、过了多久、为什么，少用抽象名词堆叠和长定语。语气平实、连贯；合适的引导和停顿随内容安排，不靠每句加“注意看”“也就是说”制造口语感。

必要术语在具体对象上解释并保持一致，例如位移、波长、周期和质点。“空间分布”可以落到“这一刻，各个位置分别有多高”；“下方依次记录更晚的时刻”可以说成“下面这张图越往右，记录的时间就越晚”。这些例子说明表达方向，不是固定替换表；位移的正负、参考位置等科学含义仍须由上下文交代准确。

审核者把整节讲稿按口语通读，检查只靠听能否顺着指代和理由跟上，再结合画面判断需要补充什么。通俗重写须保留有效推理、条件、单位和术语，不能只剩结论或类比。口语通读只是文字检查，配音的发音、语气及连贯听感仍由真实听审判断。

## 实际阶段

1. 定位单元及各课理解增量，准备版本化课程context。
2. 设计视觉原型、模型事实摘要与口语草稿，允许两者互相检查。
3. 独立上下文按公共目标与课程位置看真实静音过程，不读作者稿来补解释。
4. 按实际画面安装意群稿，独立复核科学含义、段内指称、详略与前后课衔接。
5. 每个完整意群一次TTS；教学步骤、字幕行和标点不自动拆成新调用。
6. 估计原WAV段内子句时间，联合多个实际focus求可行排程；无解就返工，不截音、不变速、不伪造平均时间。
7. 独立审核当前声音来源、时序与实际帧后封装待听审片；单套字幕候选另审后交付。
8. 连续听感、公式读法与学生理解分别记录，像素/时序通过不能冒充这些验收。

作者、编排者和审核者记录实际Agent及上下文身份，不能靠改一个角色标签让作者自审。声音时序审核逐条引用当前子句区间与真实帧，不接受无证据的`pass`。这些是独立审核与来源完整性要求，不规定课程如何讲。

视觉先行不等于第一次静音版的偶然停顿永久冻结。声音出来后可改局部阅读、显现或转场并重渲染/重审；不伸缩科学时钟，不让旧总长压过解释。

过程句可先用真实原声和轻量时间线试排，留意“先、再、一直、完成”等关系：观众听到过程时是否能看到相应变化，后面的总结是否有刚才过程的依据。单纯让整句落进focus，或在讲运动时只留下终态/历史记录，并不自动等于同步。记录可以支持回看，但不能替代观众尚未看到的必要过程；按具体句意和实际画面判断，不制定统一动作数量、停留秒数或逐词卡帧规则。

跨课共享的是已建立的模型与表示，不必把所有场景写进同一个生产源文件。本案例把每课scene分开，复用`wave_unit_shared.py`与`wave_unit_model.py`，按真实依赖绑定来源；单课节奏变化只重做受影响的课，共享科学模型变化则重审所有消费者。失效范围服务正确返工，不要求所有课程采用同一种文件布局。

## 意群与段内指向

schema3讲稿的`units`每项有`id`、`cue`、`text`、`references`；每个reference有`id`、`focus`、`text`。reference文字按顺序拼接必须等于完整意群。指向多少个对象由内容决定，不是统一教学模板。

复用schema2 Windows worker时，一个transport segment就是一个完整意群。兼容字段`focus=unit.id`显式标为`meaning_unit_not_visual_focus`，不是实测focus，不能交给旧逐句发布器。新模块逐个校验段内references，不能以一个大窗掩盖状态变化。

`phrase_alignment.py`在独立环境复用stable-ts和多语言Whisper，以既定原文估计子句的相对时刻。记录模型、软件、源码、计划与原音哈希，不按字数造时间。强制对齐不证明字音读对，也不是人工听审。

声学工具偶尔给出起止相同的单字时间点。只在完整子句仍有正时长、词序和区间均合法时保留这种原始估计，并标记`instantaneous_word_indices`与`word_timing_warning`；不把它当作实测发音区间，不补写时长，也不用于证明某个符号恰好与该字同步。倒序、越界、非有限值、重叠词及零时长子句仍拒绝。涉及状态切换的指称须结合真实前中后画面检查，不能仅靠区间求交成功宣布音画匹配。

生产发布同时复核原始请求、声学结果、完成收据及实际工具环境，结果或来源漂移即失效。测试注入与安装smoke显式隔离，不可拿来给课程排程；不需要签名认证的本地一致性检查也不冒充对抗性安全证明。

若某子句原音相对区间是`[a,b]`、真实可读窗是`[s,e]`，整个意群起点需落入`[s-a,e-b]`；再与当前cue、完整WAV边界及其他声音不重叠条件求交集。交集为空时保留失败并明确返工。原音始终完整保留，混音只用透明恒定增益。

字幕可以消费子句估计时间。`unit_film.caption_candidate(..., timing_mode="word_estimates")`可选用已有字词估计，在完整词边界分行并取各组首尾时间；不按字数插值，不重跑配音或改动原始对齐记录。词文不符、时间无序、越界或整组无正时长时拒绝生成；组内零时长词保留不确定标记，仍待实际画面和听审核对。默认`phrase_ratio`保留旧版按字数近似的行为，旧批准不升级为词级实测。选择、工具哈希和派生事件写入当前字幕候选，源码、原文、估计、样式或媒体变化即失效；字幕审核仍独立进行。

## 同文声音资产复用

原TTS计划、生成源码、参数、参考音、原文、WAV与收据不可篡改。只改视觉阅读时间且所有意群ID/原文相同，允许新对齐显式引用原声音；当前视觉/讲稿仍须重新独立批准。

这不把旧视觉许可改绑到新片。声音只证明对应文字的合成来源；新语义指向由当前视觉与排程审核。文字、参考或生成来源改变必须另立声音版本，不能因同名或同长度复用。

当前实现的复用还要求`references`完全相同；正文未变但重新切分指称，尚未拆出独立于原TTS计划的对齐计划。这是本轮保守的工程边界，不是教学规则，也不把它宣称为所有同文返工都已免重生成。本次样本在声音生成前先修正已发现的指称问题；后续可单独验证更细的声音资产/对齐计划解耦。

## 入口

```bash
# 首次安装仅新建独立工具环境；不要安装进manimgl_env。
manimgl_env/bin/python -m venv runtime/tools/meaning-alignment-env
runtime/tools/meaning-alignment-env/bin/python -m pip install \
  -r scripts/requirements-phrase-alignment.txt

# 新环境写入明确的本仓库导入路径；已有环境先核对，不重复初始化。
runtime/tools/meaning-alignment-env/bin/python -c \
  'from pathlib import Path; import site; p=Path(site.getsitepackages()[0])/"manimind_local_src.pth"; f=p.open("x"); f.write(str(Path.cwd()/"src")+"\n"); f.close()'

# Whisper公共API准备官方多语言base权重，不运行声学对齐。
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  runtime/tools/meaning-alignment-env/bin/python -c \
  'import whisper; from manimind.postproduce.phrase_alignment import ENV_ROOT, MODEL_SHA256, sha256; whisper.load_model("base",device="cpu",download_root=str(ENV_ROOT/"models")); assert sha256(ENV_ROOT/"models/base.pt")==MODEL_SHA256["base"]'

PYTHONPATH=src manimgl_env/bin/python -m manimind.curriculum build \
  --unit runtime/projects/UNIT/unit.json --project LESSON \
  --output runtime/projects/LESSON/context-v001.json

PYTHONPATH=src manimgl_env/bin/python -m manimind.postproduce.understanding_render render \
  --plan runtime/projects/LESSON/plan.json --output outputs/LESSON/v001

# 新发布器的bindings/install-narration/release-silent/speech-plan
PYTHONPATH=src manimgl_env/bin/python -m manimind.postproduce.unit_film --help

PYTHONPATH=src runtime/tools/meaning-alignment-env/bin/python \
  -m manimind.postproduce.phrase_alignment --plan TTS_PLAN --speech SPEECH_DIR \
  --output NEW_TIMINGS_JSON --model base --device cpu
```

之后使用新入口的`align`、`audio-bindings`、`release-voiced`、`caption-candidate`、`caption-bindings`、`release-captioned`，参数以`--help`为准。各关卡消费独立报告和当前绑定，不由作者标成功直接跳过。

## 状态与失效

| 资料 | 写入者 / 消费者 | 生命周期与失效 |
| --- | --- | --- |
| CSV目录与profile | 教研维护者 / builder、作者、审核 | 版本编辑资料；范围/受众变化检查受影响设计，不改写旧片历史 |
| `runtime/projects/UNIT/unit.json` | 单元负责人 / builder、各课作者、课程审核 | 本单元及目录版本；改变后重建context |
| `runtime/projects/LESSON/context-v*.json` | 课程builder / 作者、讲稿、审核、unit发布器 | 当前unit、目录与builder；源变动失效，create-only |
| 视觉plan、模型摘要与schema3稿 | 作者/正式安装器 / 渲染、审核、声音计划 | 当前课题版本；改动重审相关阶段，草稿不是批准 |
| Windows声音与收据 | 原固定V01 worker / 对齐、审核、运维 | 当前文本/参考/模型/源码；每意群一次，失败保留；不授权当前视觉 |
| 对齐JSON | phrase_alignment / 多事件排程与审核 | 当前计划、WAV和工具；原文/原声变化失效，非听审证明 |
| `runtime/sessions/SESSION/` | 操作者及独立Reviewer / 运维、门禁 | 本轮脚本、取证、原评语、失败；不成为永久进程许可或学生画像 |
| `outputs/LESSON/`新版本 | 渲染、排程、发布器 / 用户与审计 | 当前媒体和独立报告；候选、静音、有声待听审、字幕交付分开 |
| `runtime/tools/meaning-alignment-env/` | 依赖安装者 / ASR辅助工具 | 隔离工具环境、忽略Git；依赖/模型变化需记录，不冒充旧工具身份 |

课间衔接还需独立看整个小单元：后课是否真的调用前课出口，哪些基础可略，哪些桥梁首次出现，不要求统一叙事。

## 首个单元与边界

`wave-unit-20261028`覆盖形成传播、时空读图、波的叠加，不等于完整“振动与波”。已有振动/坐标为明确假设，三课难点依次是介质与相位、图像切片、相遇前中后与瞬时相消。多普勒等未覆盖的问题留给后续，不标已学。

这是可复用的监督编排，不宣称旧DeepSeek/Sol自主执行器已自动支持课程和GPU声音。其他模型接入仍需消费相同context/schema并做端到端验证。

## 实现验证

本轮核心实现独立代码复查见`runtime/sessions/wave-unit-20261028/code-review-v002.json`，首次审查的四项来源/独立性/create-only问题均已复查闭合。主控全量测试`tests-full-v002.xml`为2412通过、2跳过，独立Reviewer只核对该XML，不冒称自己重跑全量。

ManimGL导入会解析命令行，完整测试用Python入口先令`sys.argv`只含程序名，再调用`pytest.main(...)`；直接把pytest额外选项留在`sys.argv`会在原生组件收集时退出。此次保留的`tests-full-v001.xml`是该收集失败，不是通过记录。

代码测试和来源复查不批准课程内容或配音。静音像素、口语稿、真实声音排程、单套字幕及最终小单元各自按当前产物审查；成片状态以实际交付记录为准。
