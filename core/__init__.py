"""
核心框架模块 (core)

本模块实现了仿 OpenClaw 架构的核心组件，包括：
- Gateway（网关）：系统入口，管理全局状态
- BaseAgent（Agent 基类）：主/子 Agent 的公共逻辑
- MainAgent（主 Agent）：意图理解、任务分发、结果综合
- SubAgent（子 Agent）：执行具体任务的短生命周期 Agent
- SkillBase（技能基类）：所有 Skill 的抽象模板
- Memory（记忆系统）：按日期存储、搜索、检索
- ToolBox（工具系统）：文件、网络、命令等工具封装
- Session（会话管理）：维护对话历史和状态

架构对应关系（OpenClaw → 本项目）：
    Gateway       → Gateway 类（主控中心）
    Main Agent    → MainAgent 类（长期存活，理解意图）
    Sub Agent     → SubAgent 类（短生命周期，执行任务）
    Skills System → Skill 基类 + 电力调研 Skills
    Memory System → Memory 类（按日期归档）
    Tool System   → ToolBox 类（可调用工具）
"""

__all__ = [
    "Gateway",
    "BaseAgent",
    "MainAgent",
    "SubAgent",
    "SkillBase",
    "Memory",
    "ToolBox",
    "Session",
]
