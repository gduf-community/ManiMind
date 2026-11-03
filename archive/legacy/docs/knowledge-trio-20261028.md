# 三题动画制作记录

本批为一个物理、两个数学的全新主题，范围为高中物理、高中导数/大学微积分入门、大学线性代数。沿用理解优先v3.1和既有ManimGL渲染、独立审核、后写讲稿及后配音入口；不是平抛模板换标题。初次交付时5080尚未开机，先制作并审核静音主片，不调用离线主机或用替身声音。用户随后确认开机，沿已选本地VoxCPM2 V01接续，实际配音、阅读区返工和新交付见[配音接续记录](knowledge-trio-voice-20261028.md)。

## 物理：电磁感应与能量

将开路电荷分离与闭合回路分开呈现。开路时电子向下偏，分离电荷建立向下电场，稳态力的大小平衡给出端电压；闭路只计负载电阻并忽略自感，用扫过矩形面积、带符号磁通变化得到同一动生电动势。方向取纸外/逆时针为正，能量链从外力做功连接到电阻发热。物理依据：[OpenStax 动生电动势](https://openstax.org/books/college-physics/pages/23-3-motional-emf)。

模型 `conductor_state` 统一驱动杆位置、电流正负与面积；纯函数检验左右运动、停止、机械输入/热功率相等和速度倍增后的平方关系。开路电场平衡不套用于持续闭路电流。

## 数学：导数与局部线性

从两个点的平均变化率进入两侧割线极限，保留展开、提取公因子和在非零增量下约分；再展示共同尺度的局部放大及尖点左右斜率的区别。基础定义：[OpenStax 导数的定义](https://openstax.org/books/calculus-volume-1/pages/3-1-defining-the-derivative)。局部放大采用函数的真实坐标变换，而不是随意拉直曲线。

## 数学：特征向量与不变方向

用户明确排除圆周率，第三题改为大学线性代数。用真实矩阵变换寻找保持在同一直线上的非零向量，保留特征方程推理、特征方向分解及重组，再用90度旋转说明实数特征方向并非总存在。参考：[MIT 18.06SC，Eigenvalues and Eigenvectors](https://ocw.mit.edu/courses/18-06sc-linear-algebra-fall-2011/pages/least-squares-determinants-and-eigenvalues/eigenvalues-and-eigenvectors/)。

此前π尝试保留在`outputs/pi-bounds-20261028/`及同名计划/审核目录，仅作制作历史，不加入本批交付，不因退出选题而删除已有证据。其测试fixture保护数值区间与几何计算，不代表本批主题选择。

## 产物与状态

长期主题与科学摘要：`runtime/projects/knowledge-trio-20261028/brief.json`及各课程plan。
单轮协作状态：`runtime/sessions/knowledge-trio-20261028/state.json`，由主控写、当前协作者及接续者读，随任务结束或来源变化失效。
真实媒体分别在`outputs/induction-energy-20261028/`、`outputs/derivative-local-20261028/`、`outputs/eigen-directions-20261028/`。每题独立首看后才安装正式稿，另一上下文审核讲稿后才发布静音主片和准备声音计划。

三份全新源码只依赖仓库通用运行时、字形与语义公式辅助，不依赖旧平抛输出。`tests/lesson_native_harness.py`仅供新测试复用既有native插值模式，替换字形为矢量占位并捕获内存文件，不能当作真实字体、像素、配音或审核批准。

## 重建与接续

计划和讲稿的可追踪测试副本分别保存在`tests/fixtures/induction-visual/`、`tests/fixtures/derivative-visual/`、`tests/fixtures/eigen-visual/`。新环境先按README恢复ManimGL依赖，再将主题计划复制到对应的`runtime/projects/<project_id>/plan.json`。不要将本机outputs或旧审核当成新机器上的有效批准。

物理课程的重建示例（输出目录必须是未存在的新尝试）：

```sh
PYTHONPATH=src manimgl_env/bin/python -m manimind.postproduce.understanding_render render \
  --plan runtime/projects/induction-energy-20261028/plan.json \
  --output outputs/induction-energy-20261028/new-attempt
```

其余两题更换project_id即可。实际像素、源码、配置及焦点重新绑定后，要依次取得独立视觉审核、安装讲稿、另一个上下文的文字审核，最后调用`understanding_film release-silent`，不能跳过门禁直接把渲染缓存称作通过成片。

当前批次的配音接续原则：主机开机后先验证既有Tailscale/SSH和GPU维护条件，校验各声音计划的来源绑定；未知结果或失败的first take不自动重跑。入口仍为`scripts/run-windows-flexible-voxcpm.ps1`与既有`understanding_film align`。实际音频排布、整句语义焦点、听感及单套字幕均需分别检查；没有实际听辨时保留未听审标记。不预先宣称语速能排下，也不以总时长吻合代替句级审查。静音交付阶段没有连接主机、启动声音任务或后台监控；开机后的维护另按配音记录核验，不声称整卡独占。

静音批准不等于声音必然排得下。若真实语音超出焦点，保留已成立的推理与运动，局部调整讲稿或稳定阅读区，再对变动版本重新绑定、复审；不要为塞进声音而删掉有效推导、强制提速或让结果词指向尚未出现的画面。

## 本批提炼的复用检查

这些是下一批作者与审核者的语义检查提示，不限定题材、布局或解法，也不修改冻结的v3.1生产配置。

- 状态文字应跟随真实对象状态更新。组容器中的旧Text可能在原生Transform后被重新加入，测试时不能只证明新文本曾被创建，要看起动、过程中及停止后的真实帧
- 涉及“几倍某色箭头”时，先分清未缩放的方向代表向量和已缩放的分量。颜色不能代替对象身份，不应让听者把已缩放分量再缩放一次
- 旁白应描述当前可见代数状态。若提取、展开等动作已经结束，要明确回指前式，或直接解释新式的结构，不能把已经不在屏上的“两项”当作当前对象
- 问句、公式量纲与结果单位需要一致，例如功和功率不能由相同的日常措辞混用
- 能量、概率或代数等式的最后一项应落回可见对象和意义，不以观众知道终态公式来替影片补齐缺失因果

## 本次发布记录

三条均通过各自独立视觉审核和另一个上下文的讲稿审核，发布门禁完成整片解码，未生成任何语音。最终候选：

| 题材 | 时长 | 静音发布目录 | 通过稿 |
| --- | --- | --- | --- |
| 电磁感应与能量 | 240秒 | `outputs/induction-energy-20261028/v002/delivery-silent-v001/` | narration/plan-v001.json |
| 导数与局部线性 | 234秒 | `outputs/derivative-local-20261028/v001/delivery-silent-v001/` | narration/plan-v002.json |
| 特征向量与不变方向 | 210秒 | `outputs/eigen-directions-20261028/v001/delivery-silent-v001/` | narration/plan-v002.json |

物理v001及两条数学的首版文字审核曾提出修改，原报告和原正式稿均保留，没有把失败状态改写成通过。π尝试不在此发布清单。

修复后的全量测试为2067通过、2跳过；执行命令为`PYTHONPATH=src manimgl_env/bin/python -c 'import manimlib,pytest;raise SystemExit(pytest.main(["-q"]))'`。真实审核与测试是不同证据，未把占位字体时钟测试冒充像素或学生实验。

桌面和iCloud的批次文件夹均命名为`三题知识动画-静音待配音-20261028`，只放当前三条合格静音主片以及对应文本、源码和审核记录。`manifest.json`记录逐文件哈希；后续配音计划在三个主题的`runtime/projects/<project_id>/tts-plan-v001.json`，合计73段待生成文本。配音后仍需新的句级语义对齐、听审及单套字幕审核；现有少量公式过渡残影和分解段文字密度问题已在独立报告中记为非阻断建议。
