# API 原型快照

原 `backend/` 的七个 Python 文件完整归档于此。它们提供项目计划、任务状态和上下文的 FastAPI 原型，复用 `manimind` 内核。

这一快照采用客户端传入角色、可信本地调用边界。组内服务化应单独补齐认证、授权和部署验证；当前课程制作使用[监督式制作链](../../../ai/README.md)。

阅读入口：[main.py](main.py)、[项目接口](api/projects.py)、[任务接口](api/tasks.py)。历史启动命令和路径保留在原文档，迁移关系见[清单](../../migrations/20261103/manifest.json)。
