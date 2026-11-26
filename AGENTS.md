# ManiMind Agent 入口

默认使用中文。

**独立审核任务**只读[审核者规则卡](ai/contracts/审核者规则卡.md)和派发给你的阶段契约，不必读下面的完整链。**组员投稿任务**（整理、上传组员用 DeepSeek 等工具做的视频）只读[投稿指南](作品/投稿/投稿指南.md)和[经验库](作品/投稿/经验库.md)，只改自己的成员文件夹（`作品/投稿/<GitHub 用户名小写>/`）。其他任务开始前读取 [ai/AGENT_RULES.md](ai/AGENT_RULES.md)。

文档优先级（全仓库只在此处维护）：
1. 当前用户任务及本文件
2. `ai/AGENT_RULES.md`
3. `ai/contracts/强前置条件约束.md`
4. `ai/architecture/执行架构详解.md`
5. `ai/architecture/模块与状态详解.md`
6. [ai/README.md](ai/README.md) 中当前制作链的原生契约

先核对任务保护范围与原生依赖闭包，再编辑或移动文件；保留其他作者改动、来源路径、媒体、基线和版本绑定。

长期事实放 `runtime/projects/`，本轮协作放 `runtime/sessions/`，媒体放 `outputs/`。独立审核是发布强制关卡。渲染后从已完成媒体断点继续取证，不重复已确定的渲染或收费请求。

组员阅读入口：[README.md](README.md)。历史与迁移：[archive/README.md](archive/README.md)、[ai/migrations/README.md](ai/migrations/README.md)。
