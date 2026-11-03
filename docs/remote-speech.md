# 独立 GPU 配音服务

## 范围

这是已有静音动画之后的声音生成层，不更改冻结的 Sol 视觉优先实验，也不重写 Qwen 推理实现。服务生成 WAV 和可追溯记录，不承担听审、不改变动画时钟，也没有自动合成/发布权限。

`postproduce/qwen_service.py`使用 FastAPI 和官方 `qwen_tts`，固定为本地已下载的 1.7B CustomVoice 模型。启动时验证模型类型、CUDA 和权重指纹；选择 PyTorch SDPA，不依赖 Windows 上另编译 FlashAttention。代码可作为单文件脚本交给 Windows 独立环境运行，无需复制整个 ManiMind 或修改其他项目。

## 连接边界

Windows 服务仅监听 `127.0.0.1:8766`，所有请求都需私有令牌。Mac 的 SSH 本地转发使用 `127.0.0.1:17666`；令牌只放在两端权限受控的私有文件，不出现在命令行参数、仓库或诊断收据中。无需把端口开放给整个局域网。

`GET /health`只证明模型已加载；`POST /v1/audio/speech`才产生实际声音。请求支持 `input`、内置 `voice`、`instructions`、`language`，返回单声道 PCM16 WAV。默认模型名为 `qwen3-tts-1.7b-customvoice`。不接受任意模型路径、音频 URL 或克隆参考音频，避免读取其他项目的真人音色或私有素材。

GPU 同时只执行一个生成任务，忙时返回503且没有开始该次生成。文本、音色、模型权重及服务代码指纹一致时使用缓存。鉴权、请求大小和字段检查在推理前执行；音频不可因失败被记作审核通过。

## 5080 实测

2026-10-25，独立目录`F:\ManiMind-Remote`、Python 3.12.13、PyTorch/torchaudio 2.11.0+cu128、qwen-tts 0.1.1、Transformers 4.57.3；官方模型revision为`0c0e3051f131929182e2c023b9537f8b1c68adfe`。两份权重已与官方LFS SHA256核对，实际使用RTX5080、bfloat16、SDPA生成，不是CPU回退或其他项目现成音频。

同一已审讲稿摘录、同一语气指令、种子1729，未调速、未降噪或响度归一化：

| 内置音色 | 音频秒数 | 服务端生成秒数（非缓存） |
| --- | ---: | ---: |
| Uncle_Fu | 19.60 | 18.00 |
| Serena | 16.88 | 15.13 |
| Vivian | 22.24 | 19.58 |

WAV均为24kHz单声道PCM16，完整解码成功，无满幅削波；Serena的原始RMS约-26.15dBFS，明显比另两条安静，尚未做最终响度处理。生成过程的一次整卡显存快照为8435/16303MiB，包含其他进程，不是本模型的独占峰值或最低配置承诺。三条样音及参数/收据在`outputs/sol61-visual-first-voice-20261025/`，具体哈希和机械检查在单次连接记录中。

未鉴权/错误令牌均返回401；缓存回放、配音任务重启和Mac隧道重启后回放均保持相同WAV哈希。Mac切换手机热点后，私网SSH、文件校验及新6.96秒音频生成成功，生成耗时6.61秒。当前健康和样音证明工程链路，不证明漏字、术语、语气或教学效果已经通过听审。相同文本在三种音色下时长相差5.36秒，不能直接按旧动画时间槽机械拼接。

## 试听反馈与语气基线

2026-10-25，用户试听上述三种音色后明确认为“这三版都不太行，别刻意做的像老师那样”。因此旧组仅保留工程证据和失败对照，不作为声音质量通过或推荐音色。

原请求包含“像自然讲课的物理老师”等指令。这可能影响语气，但不是已经查明的唯一原因。新组`outputs/sol61-visual-first-voice-neutral-20261025/`仅清空`instructions`，文案、对应音色、模型、种子和输出处理保持不变；worker和模型不重部署，不将修改后的输出归因于模型升级。当前是未听审的对照样音，不自动接入整片。

默认先试听无语气指令的原音，不因为是知识内容就替用户添加老师、主播等职业人设；需要改变语气时以实际听感反馈为依据。接口已有的空`instructions`就是这个基线，不新增强制模板或语气限制。请求字段为空时官方Qwen推理接收`instruct=None`。

本轮选声状态位于`runtime/projects/manimind-voice-selection-20261025/selection.json`，由试听协调者记录原始用户反馈和候选组，用户/听审者及后续配音制作消费；保留旧组否决结论直到新的明确判断，对应文本、模型、音色、指令、处理或媒体哈希变化使偏好结论失效。不得把可解码或已生成记成用户接受。

后续用户澄清，Serena的问题不是读错，而是“每一句的末尾收太快了”。此条归为句尾收束/韵律反馈，不能写成已经证实的发音错误，也不能据此否决另两条无指令样音。新组`outputs/sol61-visual-first-voice-serena-cadence-20261025/`只为Serena比较两种句尾引导：读完整后收住，以及末词稍缓；原文、模型、种子和引擎不变，无额外全局变速或人工补静音。参数改变及总时长变化不等于句尾质量已通过，仍需试听原始WAV。

用户随后偏向A，认为风格到位，但明确指出仍有合成感。将A保存为表达方向，不把Serena记作最终音色通过；新声音仍需重新试听，不声称同一段指令能固定跨模型的实际韵律。当前Qwen调用没有MP3压缩、重采样、变速或满幅削波，安装版本的CustomVoice默认`non_streaming_mode=True`；这排除已检查的工程处理因素，不证明合成感一定来自某一层模型。

## 合成感对照入口

`postproduce/cosyvoice_audition.py`复用已安装的CosyVoice3公共API，提供独立的一次性试听，不扩展或替换常驻Qwen服务。`scripts/setup-windows-cosyvoice-audition.ps1`在`F:\ManiMind-Remote\models\Fun-CosyVoice3-0.5B-2512`准备固定revision `29e01c4e8d000f4bcd70751be16fa94bf3d85a18`的14份官方文件；大权重与官方LFS SHA256匹配后才从本机复制，小配置从固定官方revision下载。不复制或读取原项目的私人音色库，独立目录存在`spk2info.pt`即拒绝。

参考声从官方仓库固定commit的`asset/zero_shot_prompt.wav`下载，记录URL及SHA256，只作这轮内部试听。演示素材公开不代表已经取得商业声音授权，正式售校成片应改用明确授权的人声参考，并另做试听/权利检查。新引擎和参考声同时变化，这是听感探索，不是只变模型的严格因果排名。

`scripts/run-windows-cosyvoice-audition.ps1`先确认Qwen无未完成请求，再临时停止本次Qwen任务释放显存；仅运行一个新尝试，最后恢复原任务，不停止其他应用或改原环境包。CosyVoice在原有独立Python环境中只读调用引擎源码，缓存和输出定向到本项目独立目录；不安装或升级其包、不写源码、不保存speaker信息。运行前验证所有声明模型文件和参考声，记录引擎来源、关键源码及包版本、随机种子、加载/生成时间和WAV哈希。使用`inference_instruct2`、FP32、非流式、`speed=1.0`、`text_frontend=False`，保留原文和A的语气引导，不做后期变速或补静音。

首次初始化可能下载WeText的公开FST资源，即使目标文本已关闭frontend仍需构造其组件；这不是云语音生成请求，不发送讲稿进行云端合成。后续运行应记录所用缓存与依赖，不能仅凭HF离线开关声称整个引擎从未联网。

适配器排他创建单次输出目录；有同名尝试时拒绝覆盖或重跑。`state.json`/`generation.log`由该次进程写、操作者读取，描述该进程的阶段/故障，退出或输入/源码变化即失效，保留失败证据；媒体及`receipt.json`由适配器写、用户/听审者/维护者读取，绑定此候选及其模型/参考/软件/文本指纹，任一输入或音频变化失效。准备清单属安装器写入的长期部署证据，变更需重验；Mac接回`outputs/<audition_id>/`，长期选声反馈仍单独保存在原selection记录。不自动接入完整视频或授予发布批准。

首轮实际生成在`outputs/sol61-visual-first-voice-naturalness-20261025/`：16.76秒音频、6.594秒生成，首启构造/公开文本资源准备189.531秒另计；Torch进程峰值allocated约3553MiB，不含其他进程和全部驱动内存，不能当最低显存承诺。接回WAV与服务器SHA256一致、24kHz单声道PCM16、完整解码成功、无满幅削波。原Qwen任务恢复后鉴权健康接口正常、worker哈希未变。自然度和新句尾听感仍等待用户判断，未批准完整视频。

后续用户明确认为本条CosyVoice3更差，候选已否决；上述工程通过不转为听感通过，也不推断所有CosyVoice配置都更差。用户转而要求主流预设列表，下一步先呈现官方目录和试听入口，不再自动用演示参考批量换声。保留A的表达方向、最终音色仍未选定。云端预设库与本地开源预设必须区分，同名声音不代表同一权重/相同听感；建议试音顺序也不冒充使用量或自然度的客观排行榜。

## 本地中文预设同文试听

用户明确要求能本地部署，并授权将前述Qwen五种中文预设和Kokoro八种中文预设全部制作同文试听。`postproduce/preset_audition.py`仅编排此次试听，调用Qwen既有鉴权客户端和Kokoro官方`KModel`/`KPipeline`；不更换旧worker、不使用云TTS、不借用真人参考。统一沿用原文，Qwen清空instructions，Kokoro默认speed=1，种子1729逐音色重置，不加教师或主播人设。Dylan/Eric标明北京/四川口音，不当作标准普通话音色。

`scripts/setup-windows-kokoro.ps1`在`F:\ManiMind-Remote\.kokoro-venv`创建独立环境，不安装到Qwen或其他项目环境；固定官方`hexgrad/Kokoro-82M` revision `f3ff3571791e39611d31c381e3a41a3af07b4987`，核对主权重及八个预设包的官方LFS SHA256，保存配置、许可和环境freeze。模型以本地文件传入公共API，推理不调用云接口；首次安装联网下载公开包/权重不等于云合成。显式CUDA，不允许无声CPU回退。

输出`outputs/local-chinese-presets-20261025/`包含共享request、各原始WAV/来源收据、manifest和无需服务端即可打开的index.html。固定音量副本只施加单一增益：目标RMS -23dBFS，采样峰值上限-1dBFS；这是试听便利，不是LUFS/真峰值归一化，不变速、不压缩动态、不降噪、不改原音。网页可切回原始音量、逐条或连续试听、筛选和导出候选编号；导出的选择不是最终配音审核。缓存复用明示，不冒充新推理。

状态分工：部署清单由安装器写、worker/运维读取，随依赖或权重变化失效；Windows单次kokoro/state.json由生成进程写、运维读取，描述本次进程，退出/输入变化失效且保留故障；候选收据和Mac manifest由对应生成器/打包器写、用户/听审消费，绑定全部输入及媒体，任何变化失效，均无发布批准。长期偏好仍由试听协调者维护在原selection.json，不混入进程状态。既有媒体不覆盖，不将样音自动拼入视频。

2026-10-25已实际生成全部13种。Qwen前三条复用同参数/同worker的缓存，Dylan/Eric分别18.72/18.32秒，新推理17.25/16.515秒；Kokoro八条13.00至16.825秒，首条1.422秒、余条约0.109至0.125秒生成，模型构造另计，不作为并发或跨设备性能承诺。13份原音和13份固定增益副本均完整解码、24kHz单声道PCM16，原音无满幅削波，接回哈希与收据匹配。Kokoro公共G2P的完整原文保留为295字符音素序列，无长度截断；这不是逐词听审。原Qwen服务仍ready、worker哈希不变，静音主片SHA256未改变。

离线试听页已通过Chromium实际加载13份音频元数据、连续播放跳转/单播放器、筛选/导出及1440/390像素布局检查，未发现脚本错误或溢出。应用内浏览器拒绝file协议，所以不通过绕过协议限制来打开；交付本地HTML/WAV文件包，由用户在普通浏览器或播放器选择。独立代码审核后补严封闭请求/模型来源、配置Git blob核对，并修复取消候选仍残留播放队列的问题；回归后集中测试57通过，全仓库1357通过、2跳过。现有13条原音和13条试听副本哈希全部未变，Windows实际模型/配置另做只读官方核对，没有重推理。Qwen-engine来自鉴权健康接口并绑定每次请求ID；Kokoro归档生成时适配器，后续校验器修订不篡改生成来源。这些仅是工程验收，最终音色仍待用户听选。

```text
PYTHONPATH=src manimgl_env/bin/python -m manimind.postproduce.preset_audition prepare --output outputs/NEW_AUDITION
PYTHONPATH=src manimgl_env/bin/python -m manimind.postproduce.preset_audition qwen --output outputs/NEW_AUDITION --token-file PRIVATE_TOKEN_FILE
# Windows独立环境：preset_audition.py kokoro --output NEW_REMOTE_AUDITION --request request.json --setup-receipt kokoro-setup-receipt.json
# 将Windows生成的kokoro/、generation-adapter.py、kokoro-setup-receipt.json完整接回同一试听目录后：
PYTHONPATH=src manimgl_env/bin/python -m manimind.postproduce.preset_audition package --output outputs/NEW_AUDITION
```

## VoiceDesign 中文选声

用户确认广告中满意的是普通话声音；旧工程的晓晓/晓伊实际由在线Edge TTS生成，不能作为本地模型预设冒充。用户随后明确授权另做本地VoiceDesign中文声线，不要求复制那些在线声线或真人录音。

`postproduce/voicedesign_audition.py`调用已安装的官方`Qwen3TTSModel.generate_voice_design`，与固定speaker入口分开。计划为D01至D10、6女4男，同一原文、Chinese、种子1729、`non_streaming_mode=True`和2048 token上限；仅声线音高/厚度/明亮度等描述变化，共同要求自然口语、句尾完整、不要老师/播音/推销腔或模仿具体人物。每个描述先生成一次，标签是目标而非已听审特征，不筛选后冒充首条。

`scripts/setup-windows-voicedesign.ps1`只准备专用官方模型副本，固定revision `5ecdb67327fd37bb2e042aab12ff7391903235d3`；逐份核对2份safetensors官方LFS SHA及11份普通文件Git blob，并拒绝整个模型目录中的清单外文件。已装广告模型可作为只读公开文件缓存，核对后才复制，不复制旧录音、额外配置或speaker库；不修改旧项目环境/文件。运行器复用当前专用Qwen环境，以命名互斥量及排他输出避免重复，不杀其他GPU程序，不新增网络服务。

本轮初版在唯一已知客户端空闲时停止原服务，完成10条后恢复；执行脚本快照单独保留，随后实际鉴权确认ready和原worker指纹。独立审核指出busy查询/停止之间不具备多客户端原子排空保证，所以后续运行器移除自动Stop能力：检测原任务运行或8766监听就拒绝生成，必须先安排独占维护窗口并由操作者暂停原服务。维护结束finally重启原任务，限时90秒验证鉴权健康及原worker/模型身份，失败单独记录、不得重新推理。它不是多用户在线调度器，部署团队共享服务前仍需真正的原子接单/排空协议。

长期`runtime/projects/manimind-voice-selection-20261025/voicedesign-plan.json`由选声协调者写，worker/打包器/用户/审核者消费，保存本组选声计划；文案、描述、参数变化失效。Windows单次`state.json`由worker写、操作者读，仅描述该进程并保留失败，退出或输入/源码变化失效；plan、setup、原始WAV、逐条receipt和生成时两份source归档随候选保存，任何输入/媒体变化失效，不表示听审通过。

打包器验证新10条收据、官方模型清单及归档源码，并重新验证旧13条原音和试听副本后，才在新输出目录组合23条；旧目录不覆盖、不重新推理。新声音保留原音，试听副本复用原固定增益算法；无变速、降噪、补停顿或动态压缩。共用离线HTML以manifest分组，把新VoiceDesign与旧固定预设明确分开，可仅筛设计声线。组合manifest由打包器写、用户/听审读取，随本组保存，任意来源/媒体/选择变化失效；用户偏好继续在原selection记录，进程状态不混入。无完整视频合成或自动发布。

2026-10-25实际完成D01至D10共10次推理，音频总长176.96秒，生成总耗时154.671秒、模型构造2.594秒；单次进程含校验/归档等从06:18:58至06:21:44 UTC约166秒，不是全部制作/检查工时。组合产物位于`outputs/local-chinese-voices-with-design-20261025/`，旧26份原音/试听副本逐字节保持不变。46份选用WAV均完整解码，新原音无满幅削波；实际专用模型目录精确13份官方文件。Chromium对13/23两种包的分组、筛选、连续播放、跨组互斥、取消队列、原音切换、导出及1440/390布局均通过。集中测试78通过，全仓库1378通过、2跳过；新运行器在原Qwen在线时的拒绝路径已实际验证，未新增推理或打断服务，未做恢复故障注入。桌面现有试听页更新为23条，旧13版页面另保留于其baseline目录；仍等待用户听选，不据工程通过判断自然度，选定后需另测长段及跨句声线一致性。

```text
PYTHONPATH=src manimgl_env/bin/python -m manimind.postproduce.voicedesign_audition prepare --output runtime/projects/manimind-voice-selection-20261025/voicedesign-plan.json
# Windows：先协调独占维护窗口并暂停原Qwen服务；运行器不会自动打断在线请求
# run-windows-voicedesign-audition.ps1 -Output NEW_ATTEMPT
# 接回整份新候选目录后，创建新的组合目录而不是覆盖旧试听：
PYTHONPATH=src manimgl_env/bin/python -m manimind.postproduce.voicedesign_audition package --baseline outputs/local-chinese-presets-20261025 --design outputs/voicedesign-chinese-20261025 --output outputs/local-chinese-voices-with-design-20261025
```

### 极简女声补测

用户反馈最新女声“像乙游”，随后明确要求按极简描述只补三条、同一段话、普通人自然说话、不老师腔和角色腔，追加原页。该反馈不擅自扩展为男声或所有历史预设均被否决，也不把提示词或训练数据猜测当作已查明原因。

`voicedesign_audition.plan('minimal-female')`增加独立N01至N03计划：成年女性正常音量平实说普通话；第二条仅增加中音，第三条仅增加音高略低。每条`instructions`就是自己的短描述，不拼接原DELIVERY，不在实际输入中堆叠温柔/亲近/明亮或老师/乙游等标签。模型、revision、SDK、原文、种子1729及生成参数保持不变，每条一次完整生成。原original计划逐字段保持兼容，旧描述、收据及媒体不改写。

长期计划为`runtime/projects/manimind-voice-selection-20261025/voicedesign-minimal-plan.json`，由选声协调者写、worker/打包器/审核者/用户消费，仅绑定这组三条，描述/参数变化失效。单次维护/恢复/日志在`runtime/sessions/voicedesign-minimal-female-20261025/`由操作者记录、运维和审核者消费，结束后只是历史证据，不能当后续主机状态。执行时先暂卸唯一已知Mac专用语音转发、等Windows既有推理结束，再由操作者暂停本项目服务；运行器仍拒绝自行中断在线服务，结束后验证原Qwen及恢复Mac转发，不改SSH/Tailscale或其他项目进程。本轮一次远端启动因命令行长度在执行前失败，已确认无尝试目录，原服务/转发恢复后才换短命令启动；只发生3次模型调用，没有重推理旧片。

`append-minimal`先重新核对原23条来源及46份音频，再创建新26条目录，原manifest/index/README保留为`*-23`快照，原音与原试听副本字节不变。N组另做透明固定增益副本，沿用RMS/采样峰值规则；新manifest绑定原manifest SHA。模板用group priority把新minimal组放最上，`kind=design`让设计声线筛选涵盖新旧两组，另有仅极简女声选项。候选/manifest继续由生成器/打包器写、用户/听审消费，绑定本组输入与来源，任意修改失效；长期用户偏好仍单独保存，不自动接入成片或授予听审通过。

实际完成3次推理，50.40秒原音、44.188秒生成，模型构造2.578秒，单次进程约55.28秒，维护恢复/接回/验收另计。52份选用WAV完整解码，新原音无满幅削波；原23条46份媒体保持字节不变。增益工具增加纯内存payload复用，校验器同时检查每个声线既定试听路径、从对应原音重算的完整增益记录/哈希及实际文件；追加前先拒绝输入/输出重合或嵌套，避免写入旧包。独立增量复核两项问题已闭合，集中77项、全仓库1388项通过，2项跳过。26条页面的极简/设计/固定预设筛选、顺序播放、跨组互斥、原音切换、导出及1440/390布局通过；这些不证明自然度或角色腔已解决，等待用户试听。

```text
PYTHONPATH=src manimgl_env/bin/python -m manimind.postproduce.voicedesign_audition prepare --profile-set minimal-female --output runtime/projects/manimind-voice-selection-20261025/voicedesign-minimal-plan.json
# 协调独占维护窗口后，Windows运行器可显式传入 -Plan、-WorkerDirectory；日志按唯一Output目录名保存
PYTHONPATH=src manimgl_env/bin/python -m manimind.postproduce.voicedesign_audition append-minimal --previous outputs/local-chinese-voices-with-design-20261025 --design outputs/voicedesign-minimal-female-20261025 --output outputs/local-chinese-voices-with-minimal-20261025
```

## VoxCPM2 无参考补测

用户要求“先拿vox试试”，本轮只测官方`openbmb/VoxCPM2`的无参考TTS，固定revision `32279effe8c19989596f05d353d1447f51d9e915`，SDK `voxcpm==2.0.3`。官方[模型卡](https://huggingface.co/openbmb/VoxCPM2)标注Apache-2.0及48kHz输出；这是模型授权说明，不是任何第三方声音素材的使用许可。

`setup-windows-voxcpm2.ps1`在`F:\ManiMind-Remote\.venv-voxcpm2`安装Python 3.12、CUDA PyTorch及固定直接依赖，依赖全量freeze独立保存。只下载专用`models\VoxCPM2`，逐份核对官方LFS SHA或Git blob后才接纳；不改原Qwen/Kokoro/广告环境。首次准备允许从保留的下载断点恢复，安装收据存在时拒绝重新安装，不能把准备断点当作推理重试。

`voxcpm_audition.py`输入仍是原试听段落，种子42/43/44各一次，未提供参考录音、音色描述或角色提示。`cfg_value=2.0`、`inference_timesteps=10`、`normalize=False`、`denoise=False`、`retry_badcase=False`；`optimize=False`避免Windows编译依赖及构造时隐藏warmup生成。三个随机首条全部保留，不保证性别或跨条相同声线，也不称为固定预设。原音保留48kHz，不变速、不补停顿、不做动态压缩；试听复制沿用透明固定增益。

发布的SDK 2.0.3与仓库最新示例不同，`generate`不接受`seed`。适配器明确在每次调用前设置Python、NumPy和PyTorch随机源，不向API传入该字段；收据同时保留种子、设置方法和实际生成参数。首次生成前在已装环境绑定真实函数签名，单元测试用严格参数签名，不能靠宽松mock把兼容问题藏过去。

长计划在`runtime/projects/manimind-voice-selection-20261025/voxcpm2-plan.json`，由协调者写、操作者/审核者/用户读，随这组选声保留，输入/参数变化失效。安装收据由安装器写、worker/运维读，随专用环境存在，权重/依赖变化失效。单次`state.json`及请求、收据、源码归档在新的候选目录由worker写、打包器/审核者读，过程状态退出后仅作历史证据；来源或音频变化失效。短期运维/恢复记录在`runtime/sessions/voxcpm2-audition-20261025/`，只描述该次维护；长期偏好仍在独立selection中，三条生成不等于选声通过。

维护运行器与VoiceDesign共享命名GPU互斥量；在线Qwen或8766监听时立即拒绝，不自动停止请求。操作者先卸载Mac唯一已知语音转发、等现有请求结束，再暂停本项目Qwen，运行新worker；finally限时恢复原任务、核对原worker及模型哈希，再恢复Mac转发并鉴权验收。不暂停SSH/Tailscale、不杀其他GPU进程、不开放新服务。这只覆盖当前单一已知客户端，不是多人服务的原子排空协议。

追加器只创建新的组合包，验证原包全部原音与对应固定增益后逐字节保留，绑定旧manifest，新Vox组置前、原A保留。新包manifest由打包器写、用户/审核者读，输入、源码、权重、WAV变化失效；没有自动听审或成片批准。

### 本轮实测与复现

2026-10-25在RTX 5080实际完成V01/V02/V03，种子42/43/44各一次，共48.00秒音频；纯生成分别9.141、7.656、8.094秒，合计24.891秒。模型加载9.672秒，worker含校验、加载、生成和收据约40.343秒，首次下载安装、传输、维护和验收另计。PyTorch峰值allocated约5731.57MiB，不代表全进程或整卡总显存；不以官方速度宣传代替本次测量。

原音和浮点证据位于`outputs/voxcpm2-no-reference-20261025/`；最终组合为`outputs/local-chinese-voices-with-vox-20261025-v2/`，桌面原试听页同步为30条。此前草稿组合保留，v2仅重新打包并加强SDK/种子记录验证，没有重推理。旧27条54份选用音频保持字节不变，全部60份选用WAV完整解码，新三条无满幅削波；Chromium对最终包和桌面包的播放、原音切换、筛选、顺序播放及1440/390布局均通过。聚焦测试89项、全仓库1477项通过，2项跳过。原Qwen实际89个依赖与原清单一致，维护后Windows及Mac回环鉴权都确认ready、busy false且原指纹不变。不据这些结果认定自然度、发音或音色通过。

权重首次由Windows下载过慢，精确停止该下载子进程、保留安装失败日志和部分文件，未发起推理；改由Mac下载OpenBMB官方ModelScope镜像，校验字节等于固定HF revision的权重SHA后私网传输，安装器再次验证。发布SDK的seed差异亦在加载权重前发现并修正，没有把失败或重试包装成三条首轮样音。

```text
# Windows安装与维护运行；维护窗口须先由操作者协调，禁止中断在线请求
# setup-windows-voxcpm2.ps1
# run-windows-voxcpm2-audition.ps1 -Output NEW_ATTEMPT -WorkerDirectory PINNED_WORKER_DIRECTORY
# Mac接回新尝试后，仅打包，不调用模型
PYTHONPATH=src manimgl_env/bin/python -m manimind.postproduce.voxcpm_package package --previous outputs/local-chinese-voices-reference-a-20261025 --vox outputs/voxcpm2-no-reference-20261025 --output NEW_COMPARISON_DIRECTORY
```

## 选定 V01 后的完整配音

2026-10-27的[理解优先v2](understanding-workflow.md)另增可变句数`flexible_voxcpm.py`，不修改下述冻结的17句制作器。新片先批准视觉及后写讲稿，再创建schema 2声音计划；完整实际WAV必须落在审核过的可读focus区间，不能只满足起点锚点。5080离线期间只保存待执行计划，不能将旧V01旁白或本机替身声音当作新版已配音。

新worker自己获取跨引擎GPU互斥量；不要直接套用已经持有同一把锁的旧`run-windows-voxcpm2-narration.ps1`。恢复时仍先协调空闲维护窗口、核对模型/源码/参考及现有服务，按新worker的`generate --help`双文件部署运行，最后独立验证服务归还、接回首条、整句时序和听感。离线单测通过不代表这个新Windows入口已经实机通过。

### Windows 桌面维护核验

2026-10-28三题续配音时，在读取状态文件同期出现Windows原子替换`WinError 5`：第17句的原音及收据已写完，固定`state.json.tmp`重命名却失败，错误处理又遇到残留临时文件。现象符合短暂共享锁竞争；未另行定位实际持锁进程，不把具体读者身份当成已证实结论。失败尝试、17份收据和原音保留，不回写为完整成功。修复只针对状态发布：每次使用独立暂存文件，仅对Windows `winerror=5/32`的替换操作最多尝试8次、总等待不超过0.7秒，其他错误立即抛出；不再次调用模型、不更改生成参数或声音、不丢弃失败证据。成功替换消耗暂存文件；最终失败保留它供运维审计，下一次异常快照使用新的文件名。后台状态读取不应成为重新生成声音的触发器。

新增回归检查在模拟“推理完成后文件读锁”时验证模型仍恰好调用一次；持久读锁、非Windows权限异常和异常快照分别验证有界失败与独立暂存证据。该修复不改变模块边界、长短期上下文路径、模型或发布关卡。重部署使用新worker目录和新尝试，旧worker、失败输出和已交付媒体均保留；旧worker哈希的收据不能冒充新worker来源。

2026-10-27重新连接5080，原Qwen鉴权健康为ready、busy=false，模型与worker指纹仍匹配。该次驱动的`nvidia-smi --query-compute-apps`同时列出桌面、资源管理器、壁纸及厂商控制程序，不能把“列表非空”直接等同于另一个模型正在推理，也不能因此终止这些应用。

可变句数worker的可选GPU维护快照仅用于操作者已逐项核验的当前桌面进程。快照需显式批准共享占用，固定GPU/驱动和进程PID、类型、完整路径，短期有效；新增或变更的占用、解释器/模型进程、无法解析的状态仍拒绝。它不是长期进程白名单，不证明整卡独占、最低显存或性能承诺。无快照仍保留严格拒绝路径；共享互斥量和Qwen任务/端口停用检查都不能省略。

新`scripts/run-windows-flexible-voxcpm.ps1`只封装已协调维护窗口内的一次新尝试，不自动暂停在线Qwen、不在worker生成时重复取得其互斥量。只接受已启用且Ready的Qwen任务；子进程退出后，恢复阶段重新取得同一把锁，确认没有其他worker占用才启动并鉴权核验原Qwen身份。锁忙或遗弃状态明确记录失败，不抢占GPU、不重做推理。操作员另行排空/暂停本项目Mac专用客户端，结束后恢复转发；不停止SSH、Tailscale或其他应用。输入快照、部署文件、stdout/stderr及恢复收据保存在当前`runtime/sessions/<id>/`和对应远端尝试目录，进程结束后仅作历史证据，后续运行重新检查。

跨机器核验须在快照所属时钟域比较。2026-10-28恢复机械波配音时，Windows时钟比Mac快约28秒，首次维护在模型调用前被负快照年龄拒绝，失败和恢复证据保留，未因此重发推理。该会话的运维适配器通过带随机nonce的SSH响应读取Windows UTC，结合往返时间和本机单调经过时间构造远端当前时刻的保守上下界：基线不能晚于下界，快照到期使用上界检查。原始时间戳不修改，不硬编码偏移，不更改两端系统时间；校准只对当前进程有效，不成为长期GPU许可。当前具体适配脚本及离线时钟测试位于`runtime/sessions/wave-unit-20261028/remote-voice/v002/`，尚非通用跨平台服务能力。

本轮`projectile-paced-20261027`已在5080实际生成47段V01新声：一次加载、47次调用、无重推理，原音共134.56秒，模型加载9.375秒、推理累计75.545秒、worker含验证/归档共101.375秒。PyTorch单进程峰值allocated约6081MiB，不含其他应用和驱动，不能作为最低显存承诺。原生48kHz PCM、完整回执和浮点证据接回`outputs/projectile-paced-20261027/speech-v001/`；47句原速均通过完整焦点排程，最小结束余量约0.68秒，但不等于已听审或已确认发音自然。

新恢复封装另在Windows 5.1通过8个无模型模拟场景，1个无法安全注入的mutex权限场景明确跳过。首轮测试夹具因脚本作用域失败，保留原始证据；改为独立子进程内共享模拟状态后通过，不把夹具失败或这些模拟次数计为语音推理。测试没有调用真实任务/HTTP，外围操作者暂停并恢复的是唯一已知的空闲Qwen。随后实际47句任务退出0、恢复收据为`restored_ready`，核验了原worker/模型身份。Mac转发恢复另行检查；原始模拟、失败、部署、实际恢复收据和审核分别保存在当前session，不覆盖旧17句入口与旧媒体。

用户明确选择第一条Vox音色并要求做成片。`voxcpm_narration.py`使用该用户自选AI生成V01的原始WAV（SHA `b36f1c933b6d452df52e85571bd8de995f8513c2033e8c3d1d923a7cb79c0be9`）作为`reference_wav_path`和`prompt_wav_path`，`prompt_text`为生成该样音的准确原文；不是只用相同随机种子猜测声线延续，也不引用真人、广告库或Serena A。模型内部参考音频预处理不等于对最终输出修音；所有输出保留原生48kHz和浮点证据。参考接口不保证主观音色相似度满分，仍需听审。

沿用原114秒静音主片和已经独立审核的17条讲稿，先用原`SolVisualFirst.verify/approval`验证视觉与讲稿来源链，再准备新项目`runtime/projects/sol61-visual-first-vox-v01-20261025/tts-plan.json`。worker固定官方VoxCPM2/SDK 2.0.3及原helper哈希，种子42、cfg2、10步、无文本规范化/降噪/隐藏重试/编译warmup，每句一次；逐句收据绑定实际参数、参考、计划、原音和源代码。原视觉项目和无参考试听不改写。

`visual_narration.align`只根据实际完整WAV长度排程：before整句在事件前完成，after不早于可见事件，句间至少0.25秒，完整音频不越过镜头真实边界。不为任意尾部余量剪字、加速或变动物理时钟。`release`强制要求独立审核Agent给出绑定当前时序表/计划/视觉的pass；原文本审核不替代最终时序审核。通过后才混音，整轨只做透明恒定增益；视频码流直接复制，主片严格只有视频/音频两轨，无内嵌/烧录/播放目录同名外挂字幕，可选SRT只在support目录。它是完整观看预览，不授予声音听审或课堂批准。

首次封装v1发现MP4的mov_text实际被标记default=1，尽管传入了关闭disposition参数，所以不交付该诊断版；最终v2明确只映射视频与音频，可选SRT分开放，防止播放器自动叠字。v1/v2时序JSON逐字节一致，沿用同一真实独立时序批准；只重封装，不重新调用TTS或改变声音时钟。

新状态归属：长计划由协调者写，worker/时序适配器/审核者读，对应选声及原视觉/文案版本，任一输入变化失效；Windows单次state、requests、逐段receipt及源码归档由worker写，消费者为操作者/适配器/审核者，进程退出后状态仅作历史证据，输入/媒体变化失效。`outputs/<id>/aligned-v*/alignment.json`由时序适配器写，独立审核者/发布器读，对应一次完整音频尝试，任何媒体/参数变化失效。`runtime/sessions/<id>/`保存本次维护日志、故障证据与独立审核原结论，消费者是运维/审核/发布门禁，后续进程或来源变化不能沿用。新delivery由发布器写、用户/审计读，绑定原码流、声音和独立审核；不会把未听审标成已听审。

维护仍只暂停本项目唯一已知Mac客户端及空闲Qwen任务，使用跨引擎互斥量，结束后验证原Windows服务和Mac隧道。首次完整生成的wrapper在读完17条completed后因PowerShell未保留进程Handle取得空退出码而报错：保留原脚本、stdout/stderr、完整state及原音，不重复合成；逐条验证完成证据后接回。新运行器提前缓存Handle并区分未知退出码与非零退出码，使用退出7的无模型测试进程实际验证。未知生成结果始终不能靠自动重试恢复。

## 运行方式

本次独立部署目录为`F:\ManiMind-Remote`。`scripts/setup-windows-qwen.ps1`只在该目录创建Python 3.12专用环境，先安装官方CUDA版PyTorch，再安装`configs/qwen-5080-requirements.txt`。它从官方模型API取得固定revision，以匿名方式下载CustomVoice并核对两份权重的官方SHA256，保存环境freeze与`setup-receipt.json`，不修改原有广告项目环境。当前CUDA依赖为PyTorch/torchaudio 2.11.0+cu128。

安装脚本在Windows使用进程级`RemoteSigned`运行；没有修改MachinePolicy、UserPolicy、CurrentUser或LocalMachine的执行策略。全局策略若由组织强制管理，不应绕过它。

`scripts/register-windows-speech.ps1`在部署和私有令牌就绪后注册唯一的`ManiMind-QwenVoice-5080`计划任务：当前用户、S4U、Limited权限，开机/登录触发、同任务不重复启动、失败最多三次重试。它不保存Windows密码，不使用Codex运行时，不会重启电脑；实际启动、GPU推理及重启恢复仍需分别实测。已存在同名任务会停止注册，不能静默覆盖。

在已核查的 Windows Qwen 环境中执行下面的入口，其中实际路径应来自本机检测，不照抄其他电脑路径：

```text
python qwen_service.py --model-path MODEL_DIRECTORY --cache AUDIO_CACHE_DIRECTORY --token-file PRIVATE_TOKEN_FILE
```

Mac 客户端关闭环境代理，只向 SSH 转发的回环端口发送私有令牌。示例：

```text
PYTHONPATH=src manimgl_env/bin/python -m manimind.postproduce.remote_speech --token-file PRIVATE_TOKEN_FILE --request REQUEST_JSON --output NEW_WAV_PATH
```

客户端验证响应类型、WAV 格式和服务器 SHA256，再保存新音频及 `.receipt.json`，拒绝覆盖既有产物；不跟随HTTP重定向，防止私有令牌被带到另一地址，也不自动重发未知结果的生成请求。重新生成相同请求可由服务端缓存回放，但调用方需明确选择新的接收路径。

## 状态生命周期

| 状态 | 写入者与消费者 | 生命周期与失效 |
| --- | --- | --- |
| 主机身份、公钥指纹、部署参数 | 接入执行者；运维、连接检查器 | 长期保存在`runtime/projects/<connection_project_id>/`；网络、身份、密钥和配置变化需再验 |
| 只读调查、登录/传输/启停记录 | 接入执行者；运维、审计 | 单次`runtime/sessions/<connection_session_id>/`；对应检查时刻，不替代后续可用性 |
| Windows 服务私有令牌与 SSH 私钥 | 两端部署操作者；SSH/服务鉴权 | 只在用户私有配置目录，不进入仓库或普通日志；轮换后旧客户端授权失效 |
| Windows音频缓存和生成收据 | GPU worker；客户端、审计 | 专用缓存目录；请求、权重、代码、音频指纹变化失效；仅生成数据，不表示听审通过 |
| Windows专用环境、`setup-receipt.json`、`requirements-frozen.txt` | 专用安装器；GPU worker、运维 | 对应安装环境和固定模型revision；依赖、权重或权限变化后重新校验 |
| Windows计划任务及导出的`speech-task.xml` | 注册脚本；Task Scheduler、运维 | 当前部署的启动配置；路径、账号、权限改变后失效，不能当作重启已验收 |
| Tailscale设备身份、Mac隧道及私网SSH配置 | 接入执行者；Tailscale、SSH、launchd、运维 | 对应当前两台设备，私有凭证留在客户端；退出/移除设备、密钥到期、地址或权限变化需再验，详见连接说明 |
| 受保护的私网SSH开机检查及JSONL | 注册器/启动任务；Task Scheduler、运维 | 开机或指定用户登录时有限等待，已监听不重启；只维护SSH就绪，不代表整机重启或媒体审核已通过 |
| Mac 接收的 WAV 与`.receipt.json` | 配音客户端；对齐器、审核者、用户 | 新`outputs/<project_id>/`；文本、参数、引擎收据或音频变化失效，不覆盖旧静音交付 |

缓存和原始收据不自动清除。确认不再需要时由运维清理专用缓存，不能泛化删除其他项目、模型或用户目录。

## 验收顺序

先完成不经过 Codex 的 SSH 和双向文件校验，再测健康接口、拒绝错误令牌、真实短句合成与缓存回放。记录GPU、依赖、源文件与模型指纹、音频秒数和生成时间。延迟和显存未压测前，不承诺并发或实时性能。

先交付试听音频，核对术语、漏字、停顿及自然度；之后才做整片事件对齐和独立媒体审核。原来的静音审核不能批准新增声音。没有真实听审和学生理解测试，不将模型评分、WAV 可解码或波形有信号当作这些验收已经完成。

## 来源

- [Qwen3-TTS 官方推理说明](https://github.com/QwenLM/Qwen3-TTS)
- [官方 1.7B CustomVoice 配置](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice/blob/main/config.json)
- [CosyVoice 官方源码与示例](https://github.com/QwenAudio/CosyVoice)
- [Fun-CosyVoice3 官方固定模型](https://huggingface.co/FunAudioLLM/Fun-CosyVoice3-0.5B-2512/tree/29e01c4e8d000f4bcd70751be16fa94bf3d85a18)

仅调用其公共 API，没有复制第三方模型内部实现或修改`resources/`。
