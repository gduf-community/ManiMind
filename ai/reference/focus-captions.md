# 焦点字幕后处理

`postproduce/focus_captions.py` 只消费已审整句 `alignment.json` 和原有声 `delivery.json`，不改讲稿、术语、视觉、WAV 或旧冻结产物，不调用模型/SSH。物理术语必须由上游讲稿审核修正后重新渲染和配音；字幕不把“横速”自行替换为另一说法。入口复用 `understanding_film.audio_bindings` 验证全部实际 WAV、首条收据、计划、源讲稿/视觉/焦点语义链及原音频审核，无固定课程或 47 句限制。

## 接入

```bash
PYTHONPATH=src manimgl_env/bin/python -m manimind.postproduce.focus_captions prepare \
  --alignment /absolute/alignment.json --delivery /absolute/voiced/delivery.json \
  --output /absolute/outputs/project/captions-v001 --producer-agent caption-author
PYTHONPATH=src manimgl_env/bin/python -m manimind.postproduce.focus_captions bindings \
  --candidate /absolute/outputs/project/captions-v001
PYTHONPATH=src manimgl_env/bin/python -m manimind.postproduce.focus_captions release \
  --candidate /absolute/outputs/project/captions-v001 \
  --review /absolute/runtime/sessions/session/captions-review.json \
  --output /absolute/outputs/project/playback-v001
```

`prepare` 可用 `--style /absolute/style-options.json` 提供部分白名单字段；默认 `fontname=PingFang SC, fontsize=40, margin_v=24, outline=2, shadow=0, max_width=30`。字体只允许 PingFang SC、Heiti SC、Arial；数值有界，不接受任意 ASS/force_style。修改样式必须另建候选，不能覆盖原 freeze。实际字体是否命中、字形是否齐全、底部是否撞内容，仍由主控和独立 Reviewer 看真实像素。

## 候选与计时

新目录保存 `style.json`、`support/captions.ass`、`captions.json`、`source-receipts.json`、`candidate.json`、`bindings.json`、`candidate.mp4`。ASS 与播放 MP4 分目录，不作为自动加载外挂。它是 `candidate_not_released` 审看片，没有 delivery 收据，不是正式发布。失败尝试也保留，重试换目录。

单套、底部居中、禁自动换行，不缩小或平移原画。超过约 30 个汉字宽度时，优先在宽度内最后一个标点后分割；无标点才按 Unicode 显示宽度估计切分。原换行是句内边界，不增加同时显示行数；原字符完整保存在 `captions.json`，逐段拼接必须与原文相等，不清洗空格或改写术语。宽度只是估计，不替代像素验收。

空白前缀夹换行也不能生成 ASS 硬换行；显示时安全展开为单行空格，纯空白尾部并回前段。canonical 清单仍保留原始字符，不能用直接删字掩盖边界错误。这些前导、内部与尾部空白组合有独立回归测试。

整句使用实测 WAV start/end；ASS 向内量化为百分秒，起点向上、终点向下，不经过毫秒舍入。拆分时仅按原字符数比例近似分配，在整句量化范围内保证每段至少一个百分秒、无重叠、不越 WAV。不是词级 ASR，不声称精确逐词同步。过短而不能安全分配则拒绝，不裁剪声音。

文本拒绝控制字符、双向及隐藏格式控制；原换行转义或作为拆分边界。花括号转义为字面字符，反斜杠后内部插入不可见 word joiner，阻止原文 `\N/\n/\h` 被 libass 当指令。不能仅用双反斜杠，因为 libass 不把它还原成单一字面反斜杠；实现参考 [libass 原生解析器](https://github.com/libass/libass/blob/master/libass/ass_parse.c)。内部编码不修改 canonical caption text。

使用现有 `pilot.FFMPEG/probe/run`，先检测 `ass`/libass 过滤器，再烧录；只用 libx264 重编码视频，显式映射一视频、一音频，音频 `copy`，不重生成、增益、重采样或剪裁。比较源/候选复制音频 packet SHA256，检查两轨、尺寸、时长并全解码。候选支持文件只有 ASS/JSON，不生成 SRT；正式播放目录仅复制 MP4 和 delivery.json，没有软字幕轨、同名或语言后缀外挂字幕。

## 独立字幕审核

Reviewer 消费候选真实帧、ASS、原讲稿、字幕清单、来源收据和 **当前** `bindings` 输出。报告由独立上下文写到 `runtime/sessions/<session_id>/`，不由候选作者代签。最小结构：

```json
{
  "stage": "captions",
  "status": "pass",
  "release_authorized": true,
  "reviewer_role": "independent",
  "reviewer_agent": "separate-pixel-reviewer",
  "bindings": {"...": "完整原样填入当前 bindings 输出，不是这个占位对象"},
  "blocking_findings": [],
  "listening_reviewed": false,
  "checks": {
    "layout": {"status": "pass", "evidence": [{"finding": "实际时间点的字幕与内容距离、单行状态"}]},
    "text_consistency": {"status": "pass", "evidence": [{"finding": "与原稿逐字和标点核对的范围、结果"}]},
    "frame_evidence": {"status": "pass", "evidence": [
      {"time": 1.5, "path": "/absolute/candidate-frame.png", "sha256": "实际帧文件哈希", "finding": "真实候选像素结论"}
    ]}
  }
}
```

这是结构示例，不是审核结果。主控确定足够的实际帧覆盖，尤其长句切换前/中/后和可能碰撞处；抽帧数量不被硬编码。模块检查 frame 文件哈希与时间范围，但不能认证审片者身份或证明帧来自该视频，不能把 JSON pass 当像素事实。独立 Reviewer 必须亲自检查当前候选。字幕审核不是听审，`listening_reviewed` 必须为 false；不产生新的声音、学员理解或新旧内容回归批准。

`release` 重新验证全部来源、实际 candidate 文件与冻结 bindings、独立字幕 stage/pass/授权及帧哈希，再检验音频 packet hash 和完整解码。通过后 create-only 复制候选，不再次编码；只写新播放目录和来源/审核哈希 delivery 收据。它是显式工具，不自动执行发布。

## 生命周期

| 状态 | 写入者 | 消费者 | 生命周期与失效 |
| --- | --- | --- | --- |
| 原计划、讲稿、对齐及有声交付 | 上游既有独立阶段 | 本模块、Reviewer | 只读；上游校验失败即停止 |
| style/ASS/captions/source receipts/candidate/bindings | 字幕后处理作者 | 独立像素 Reviewer、release | 单次候选，create-only；源交付、关联文件、文字、样式、音视频、模块变化须新建，不能原地重绑定 |
| 字幕审核 JSON 与帧证据 | 独立 Reviewer | release、审计者 | 当前 bindings；候选、来源、帧或授权变化即失效 |
| 播放 MP4 与 delivery 收据 | release 门禁 | 用户、审计者 | 单次交付，create-only；复制媒体或来源/审核变化即失效 |

媒体与派生清单放 `outputs/<project_id>/`；短期审片/帧证据放 `runtime/sessions/<session_id>/`。本模块不新增长期项目事实、不混写长期与短期状态。主控负责架构文档同步及真实候选像素验收。

离线测试：`manimgl_env/bin/python -m pytest -q tests/test_focus_captions.py`。工程测试用临时 structured fixtures、真实小 WAV/收据和 mocked ffmpeg，不依赖 runtime、outputs、网络或 GPU；测试通过不表示实际像素或实际成片已通过。
