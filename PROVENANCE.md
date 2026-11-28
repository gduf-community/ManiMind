# ManiMind 原始 Git 历史与来源记录

本文件记录由现存 Git 对象直接验证的事实，以便区分早期代码来源与后续组织开发贡献。此记录不判断历史变更的主观原因。

## 原始历史（2026 年 4 月 28 日）

组织仓库的 `main` 分支保留了两次原始提交：

- [`088c9ddf`（#001）](https://github.com/gduf-community/ManiMind/commit/088c9ddfce5c3de5ee656f152fb6bc8697395ba5)：作者署名 `proffitteoy`，根提交，新增 188 个文件。
- [`2af2c499`（#002）](https://github.com/gduf-community/ManiMind/commit/2af2c499ced17a465dda58fc0dc0d72cd02b70e0)：作者署名 `proffitteoy`，改动 35 个文件，提交后源码树共有 209 个文件。

这些原始提交的 SHA、作者、日期和文件内容均未修改。它们早于组织当前 `develop` 分支的根提交。

## 后续独立历史（2026 年 5 月 9 日）

[`fa6377c`](https://github.com/gduf-community/ManiMind/commit/fa6377c56ecbf14bc4332391cdfc32f494553ad9) 是当前 `develop` 历史的独立根提交，提交中记录的作者是 `iam2n2`（GitHub 关联 `AnApple02`）。

比较 4 月 28 日 `#002` 与 5 月 9 日根提交：前者 209 个路径都存在于后者，其中 207 个文件的 Git Blob SHA 完全一致，两个文件发生修改；后者还增加 17 个文件。相同文件包含项目架构文档、编排代码、测试及部分第三方资源。因此可以核实源码连续性，但不应把相同文件都认定为任何单一作者的原创成果。

原始 `main` 和后来的 `develop` 此前没有共同祖先。仅凭现存 Git 历史不能确定是否执行过 force push，也不能判断当事人的操作意图。

## 2026 年 11 月：恢复历史关联

恢复提交以原 `develop` 为第一父提交、2026 年 4 月 28 日的 `main` 提交 `2af2c499` 为第二父提交，使用 `ours` 合并策略：保留当前 `develop` 的文件树，不用旧代码覆盖新开发成果。随后单独增加本来源说明。

- 旧作者、旧日期、旧提交 SHA 不变；
- 组织后续所有提交与贡献者信息保留；
- 不改写 `develop` 既有历史、不进行 force push；
- GitHub 对旧提交的账号关联及 Contributors 统计取决于 GitHub 的邮箱映射和统计规则，历史链接恢复不保证这些 UI 指标即时变化。

注意：合并此修复 PR 时必须采用 **Create a merge commit**，不得 Squash 或 Rebase，否则可能丢失恢复的祖先链。
