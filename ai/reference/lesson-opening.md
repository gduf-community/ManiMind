# 已发布正文的监督式片头扩展

`postproduce/lesson_opening.py`只消费`unit_film.release_captioned`已发布正文和已经制作好的片头，不生成标题画面、不调用TTS/GPU、不编辑正文或旧发布器。这是有界的人工监督入口，不是自动工作流。输出为带单套烧录字幕的完整预览，仍待人类听审；技术连续性不能证明声音自然度、发音或学生理解。

## API

```python
from manimind.postproduce import lesson_opening

lesson_opening.opening_bindings(plan_path)  # 返回当前片头审核bindings
lesson_opening.require_opening_review(plan_path, opening_review_path)  # 验证并返回报告
lesson_opening.candidate(plan_path, opening_review_path, candidate_dir)  # 返回候选bindings
lesson_opening.bindings(candidate_dir)  # 重新验证来源与冻结工件
lesson_opening.release(candidate_dir, regression_review_path, final_review_path, output_dir)
```

所有路径参数可为`str|Path`，返回JSON兼容字典。候选和发布目标必须不存在，包括悬空符号链接；失败尝试保留，重试换目录。无正文覆盖、裁切、变速、缩放或重新编码视频选项。CLI对应`python -m manimind.postproduce.lesson_opening`的`opening-bindings / require-opening-review / candidate / bindings / release`；参数依次为`--plan`、`--review`、`--candidate`、`--regression-review`、`--final-review`、`--output`，只填写该动作实际需要的参数。

## 计划与制作收据

计划放在`runtime/projects/<project_id>/opening-plan-v*.json`，schema固定为1：

```json
{
  "schema_version": 1,
  "author_agent": "actual-opening-author",
  "author_context": "actual-author-context-id",
  "body_delivery": {"path": "/absolute/body/delivery.json", "sha256": "64hex"},
  "title": "标题",
  "question": "引入问题？",
  "text": "完整引入旁白。",
  "subtitle_clauses": [{"id": "c1", "text": "完整引入旁白。", "start": 0.0, "end": 3.0}],
  "intro": {
    "video": {"path": "/absolute/intro.mp4", "sha256": "64hex"},
    "wav": {"path": "/absolute/intro.wav", "sha256": "64hex"},
    "receipt": {"path": "/absolute/intro-receipt.json", "sha256": "64hex"},
    "sources": [{"path": "/absolute/opening-source.py", "sha256": "64hex"}]
  },
  "revision_contract": "/absolute/runtime/projects/project/revision-contract-v001.json"
}
```

`intro-receipt.json`含`schema_version=1`、真实`author_agent/author_context`、与计划相同的`video / wav / sources`，以及`script: {title, question, text, subtitle_clauses}`。不含其自身receipt，避免循环哈希。素材与源文件使用精确`{path, sha256}`对象和绝对路径，不接受自动推断作者身份。收据中的原作者、脚本与源文件必须一致；这里的身份是操作者可追溯声明，不是认证系统。

子句ID唯一、按顺序且不重叠，不使用保留subject名`title/question/body`；文本无改写拼接为完整`text`，时间单位为秒，落在完整WAV及片头视频内。需要的恒定响度增益只应用到制作阶段的最终片头WAV，再冻结收据和独立复核；合片模块没有增益功能。片头MP4应呈现同一完整配音和烧录字幕，实际文稿/画面/时序一致性由独立Reviewer判断，不能拿绑定成功代替看图。

视频必须是零起点CFR H.264/yuv420p，一视频一零起点AAC音频，无字幕轨；非零音轨起点直接拒绝，不能解码后悄悄平移正文声音。片头与正文的profile、level、尺寸、time_base、帧率及SAR一致。实现不固定1080p30、三条课、题材或片长；不兼容时只返工片头。原正文仍须通过原发布器的来源、完整原音、时序及字幕审核门禁，重新检查当前receipt、原review、AAC包哈希和字幕候选绑定，不能信任孤立delivery声明。

## 片头独立审核

片头审核写到`runtime/sessions/<session_id>/opening-review-v*.json`，在任何concat前通过。通用报告头：

```json
{
  "stage": "opening",
  "reviewer_role": "independent",
  "reviewer_agent": "actual-reviewer",
  "reviewer_context": "actual-independent-context-id",
  "status": "pass",
  "release_authorized": true,
  "blocking_findings": [],
  "bindings": {},
  "listening_reviewed": false,
  "listening_status": "not_performed",
  "student_tested": false,
  "checks": {}
}
```

`bindings`必须原样填入当前`opening_bindings(plan)`完整结果，示例空对象不允许发布。`checks`必含`pixels / script / timing`，每项为`{status: "pass", evidence: [...]}`。证据均含非空`finding`、`subject`、当前片头内`time`；`pixels/script`的subject集合必须完整覆盖`title / question / 所有子句ID`，`timing`覆盖所有子句。子句证据必须位于该子句的声明时间窗。

像素证据额外含`path / sha256 / video_sha256`，分别为实际无损抽帧路径、抽帧文件哈希及当前片头视频哈希。入口用ffmpeg将图片解码像素与该视频该时刻真实帧比较，不接受仅文件存在或文字描述。文件哈希和像素匹配不替代真正的独立编辑判断。禁止片头作者、正文原作者/生产者以同agent或同context自审。

当前批次听审诚实标记`false/not_performed`，不强制虚构自然度通过。若真实独立听审，才可使用`true/performed`，同时增加`checks.listening`，逐子句给出带subject/time/finding的实际听审证据。无听审不得宣称`naturalness_approved/pronunciation_approved`。不支持ASR或学生实验认证。

## 保留正文

候选目录保存`candidate.mp4 / candidate.json / bindings.json / preservation.json`，以及`support/concat.txt / video.mp4 / intro.wav / body.wav / mix.wav / reference-audio.m4a / reference-audio.wav / candidate-audio.wav`。候选没有delivery，不能当作正式交付。

1. ffmpeg concat只映射视频，以`-c:v copy`拼接；显式用片头帧时钟指定concat边界，避免AAC padding让正文视频产生空隙。最终封装仍复制视频，不重编码正文。
2. 对片头、完整正文、最终候选逐帧全量解码，比较完整像素哈希序列、每帧PTS及duration。framehash显式`-enc_time_base:v demux`并核对输出时基与ffprobe原流time_base相等，避免默认1/30时基把15360tbn上的亚帧抖动四舍五入。候选必须等于完整片头加严格相等的正文后缀，frame offset为片头实际帧数，time offset为片头真实帧时长之和。保存像素与归零时钟的聚合SHA、帧数和offset，不保存庞大的逐帧日志。发布时重新全量比较。
3. 片头使用计划中的完整最终WAV，正文使用原MP4完整音轨；以正文原sample rate/channels解码PCM16。仅片头可为兼容正文而重采样；正文不重采样到新规格、无增益、无裁切、无加速。
4. 片头PCM不足画面时只补尾部零值静音；长于画面或边界无法落在整数样本时拒绝，不截音。完整PCM拼接后一次AAC编码，不使用`-shortest`、音频trim、tempo、淡入淡出或响度归一化。
5. 保存完整PCM、输入媒体路径/哈希、样本数、正文PCM后缀哈希及零值padding检查。候选和发布时再对原正文/片头源进行完整PCM hash解码，避免只证明两份保存的PCM相等。AAC为有损编码，PCM证明是编码前完整性，不声称最终AAC像素式无损或原AAC包保持。
6. 完整`mix.wav`独立编码为参考AAC容器`reference-audio.m4a`；参考及候选AAC packet SHA须等于同一原生AAC参数的完整编码指纹。再分别完整解码参考/实际候选，比较呈现PCM样本数、内容SHA及逐块原始sample PTS/nb_samples时钟，核验保存的PCM确为当前容器的完整呈现。发布时重做。这样相同payload但MP4 edit/skip裁掉5~50ms也拒绝，不能只比较AAC包。参考是独立的一次有损编码，不把候选再转码，也不要求AAC解码与编码前PCM无损相等；仍不等于听审。

## 最终双审核

计划的`revision_contract`必须是[现有内容回归协议](../../docs/content-regression.md)的schema1合同；`assets`仅含`body`，其媒体路径、SHA和duration必须等于当前已发布完整正文。`units/features`由任务选择，建议每个正文cue记录真实教学功能及process feature，不在通用代码里硬编码课数或功能。

回归报告`stage=content_regression`，通用报告头与上方相同，`bindings`改为`bindings(candidate_dir)`当前完整结果；报告`units/features/outcome/evidence`直接沿用现有协议。发布真实调用`content_regression.contract_bindings`及`validate_comparison`，缺项、lost、陈旧绑定或process只有终态都拒绝，质量总分不能抵消。回归Reviewer context须不同于片头首看及最终seam Reviewer context；最终Reviewer可以与片头Reviewer是同一人。

每条feature evidence在原协议`time/finding/phase`基础上加入实际候选的`path/sha256/video_sha256`，并加入`baseline: {time, finding, path, sha256, video_sha256}`。baseline为实际正文抽帧，位于该unit的`baseline_interval`内；candidate time必须等于baseline time加真实intro offset。两份图均做实际像素来源比对，process继续要求before/during/after三阶段。

最终报告`stage=opening_final`，同一候选bindings，必含`checks.seam / checks.captions`。seam证据为接缝前、接缝时、接缝后的真实候选帧，标记`phase=before/during/after`；during time为intro offset，JSON数值容差最多1微秒以支持308/30等非终止小数，实际媒体时钟仍严格相等，前后各在一秒内。captions证据subject覆盖每个片头子句和`body`；子句证据必须在该子句真实时间窗，body证据必须在原正文`captions.json`某个实际`start_cs/end_cs`区间加intro offset后的窗口，不能引用正文空白帧或片头冒充。实际核对新字幕、原字幕及接缝清洁，不以字幕JSON代替像素。当前听审仍`false/not_performed`；若真实进行了听审，`true/performed`另需`checks.audio_continuity`在同一接缝前中后给出time/phase/finding，仍不升级原正文的历史听审状态。

两报告通过后才全量复验视频/PCM并逐字节复制为`lesson.mp4`，输出仅含该MP4和`delivery.json`，不放自动加载外挂字幕。交付绑定原body delivery、片头批准、回归及最终批准哈希、候选全工件与保留证明；报告声明完整预览仍待人类听审，不升级为自然度或学生理解认证。

## 状态与失效

| 状态 | 写入者 / 消费者 | 生命周期与失效 |
| --- | --- | --- |
| `runtime/projects/<id>/opening-plan-v*.json`及revision合同 | 主控/片头作者 / 片头审核、合片器、回归审核 | 长期版本；body、脚本、作者、声音、源文件、合同改变另建版本 |
| `runtime/sessions/<id>/*review*.json`及实际PNG | 对应独立Reviewer / 合片器或发布器 | 单轮证据；来源、绑定、画面、时间、模块或报告变化失效；不由作者代签 |
| `outputs/<id>/<candidate>/` | 合片器 / 回归、最终审核、发布器 | create-only候选及完整PCM；任何工件/来源/批准变化失效，失败不覆盖重试 |
| `outputs/<id>/<release>/delivery.json`与MP4 | 发布器 / 观众、审计者 | create-only复制交付；精确绑定全部来源/审核/保留证明，改变需重新验证与发布 |

不向长期计划混写短期Reviewer记录，不修改原body或旧receipt。离线测试只验证门禁行为及临时合成素材的FFmpeg兼容性，不表示真实课片已审、已听或已交付。
