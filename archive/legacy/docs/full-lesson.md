# 完整讲解片

`postproduce/full_lesson.py` 将固定选题的可信视觉组件扩展为独立完整讲解。候选模型通过 `model_dialogue` 生成12段讲稿、标题、最短时长，严格校验数据后，由组件连续完成汽车测量、割线逼近、非零差商、局部放大和结论。候选输出不是Python代码，也不是审核许可。

## 运行

使用 `manimgl_env/bin/python -m manimind.postproduce.full_lesson`：

1. `init --answer outputs/<dialogue-case>/dialogue-02.json`
2. `prepare --provider edge`
3. `render --quality h`
4. `inspect`
5. 独立Reviewer查看每一段的实际抽帧、源码与音轨时间轴，写入项目目录 `review.json`。
6. `assemble`

可指定 `--project-id`，不允许覆盖已有初始化。离线配音只能显式选择 `--provider say`；不隐式降级。每段保留0.3秒引入和至少0.65秒语音后留白，不整体拉伸音画。

## 状态归属

| 状态 | 写入者 / 消费者 | 生命周期与失效 |
| --- | --- | --- |
| `runtime/projects/<id>/production.json` | coordinator / worker、reviewer、lead | 长期；记录事实、原稿来源与组件版本；改变输入需新项目或重审 |
| 同目录 `review.json` | 独立reviewer / assembler | 长期；绑定组件快照、讲稿、配置、时间轴、音轨、编排、视频；任一改变失效 |
| `runtime/sessions/<id>-production/` | coordinator / reviewer、lead | 当前制作；保存语音状态和逐次渲染结果，不覆盖失败记录 |
| `outputs/<id>/` | worker、编排 / reviewer、用户 | 派生媒体；保留原模型稿、工程组件源码快照、逐次视频、原帧、字幕与成片，可重建 |
| 原始API调用 | model_dialogue / coordinator、reviewer | 独立协作case的长短期路径与预算规则不变 |

完整片必须每段至少有一张实际被独立审核的原帧；审核及输入哈希验证通过后才执行音画封装，随后全片解码与音视频时长检查。此项不是跨课程无人值守能力证明，也不是音质、学生理解度或审美的自动证明。旧试片文件不覆盖；新的组件挂钩改变了源码时，旧审核不能用来授权新渲染。
