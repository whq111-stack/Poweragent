# ⚡ 电力系统市场调研 Agent

> 专注方向：**电网布局调度** | 架构：仿 OpenClaw 设计（Python 实现）

## 📋 项目简介

本项目是一个面向电力系统市场调研的智能 Agent 系统，专注于**电网布局调度**方向。系统仿照 OpenClaw 的核心架构，用纯 Python 实现，不依赖 Node.js。

核心能力：
- 📋 **数据采集**：从政府网站、行业平台采集政策法规、新闻动态、市场数据
- 📊 **智能分析**：基于大模型分析电网布局和调度策略
- 📈 **报告生成**：自动生成包含交互式图表的 HTML 可视化报告

## 🏗️ 架构说明

本项目仿照 OpenClaw 的核心设计思想，用 Python 实现了以下组件：

```
┌─────────────────────────────────────────────────────────┐
│                     Gateway（网关）                       │
│  系统入口，管理全局状态、日志、配置                         │
├─────────────────────────────────────────────────────────┤
│                   MainAgent（主Agent）                    │
│  长期存活，理解用户意图、分发任务、综合结果                   │
│  ┌─────────┐ ┌──────────┐ ┌─────────┐                  │
│  │ Skill   │ │ Memory   │ │ Session │                  │
│  │ 注册表   │ │ 记忆系统  │ │ 会话管理 │                  │
│  └────┬────┘ └──────────┘ └─────────┘                  │
│       │                                                 │
│  ┌────┴──────────────────────────────────────┐         │
│  │              Skills（技能系统）              │         │
│  │  ┌─────────┐ ┌─────────┐ ┌────────────┐  │         │
│  │  │政策采集  │ │新闻采集  │ │市场数据采集 │  │         │
│  │  └─────────┘ └─────────┘ └────────────┘  │         │
│  │  ┌─────────┐ ┌─────────┐ ┌────────────┐  │         │
│  │  │电网分析  │ │调度分析  │ │可视化报告   │  │         │
│  │  └─────────┘ └─────────┘ └────────────┘  │         │
│  └───────────────────────────────────────────┘         │
│                                                         │
│  ┌──────────────────────────────────────────┐          │
│  │        SubAgent（子Agent，短生命周期）      │          │
│  │  执行具体任务 → 返回结果 → 销毁            │          │
│  └──────────────────────────────────────────┘          │
├─────────────────────────────────────────────────────────┤
│  ┌──────────┐ ┌──────────┐ ┌──────────────────┐       │
│  │ToolBox   │ │ QwenClient│ │   Memory         │       │
│  │工具系统   │ │ 大模型调用 │ │   记忆系统       │       │
│  └──────────┘ └──────────┘ └──────────────────┘       │
└─────────────────────────────────────────────────────────┘
```

### 核心概念

| 概念 | 说明 | 对应 OpenClaw |
|------|------|---------------|
| **Gateway** | 系统入口，管理全局状态 | OpenClaw Gateway |
| **MainAgent** | 长期存活，意图理解+任务分发 | OpenClaw Main Agent |
| **SubAgent** | 短生命周期，执行具体任务 | OpenClaw Sub Agent |
| **Skill** | 可插拔的功能模块 | OpenClaw Skills System |
| **Memory** | 按日期存储的持久化记忆 | OpenClaw Memory System |
| **ToolBox** | 文件/网络/命令等工具封装 | OpenClaw Tool System |
| **Session** | 对话历史和状态管理 | OpenClaw 会话管理 |

## 📁 项目结构

```
power_grid_agent/
├── core/                           # 核心框架层（仿 OpenClaw 架构）
│   ├── gateway.py                  # 网关：系统入口
│   ├── base_agent.py               # Agent 基类
│   ├── main_agent.py               # 主 Agent：意图理解、任务分发
│   ├── sub_agent.py                # 子 Agent：执行具体任务
│   ├── skill_base.py               # 技能基类 + 技能注册表
│   ├── memory.py                   # 记忆系统
│   ├── toolbox.py                  # 工具系统
│   └── session.py                  # 会话管理
├── skills/                         # 技能层（可插拔）
│   ├── skill_collector_policy.py   # 政策法规采集
│   ├── skill_collector_news.py     # 行业新闻采集
│   ├── skill_collector_market.py   # 市场数据采集
│   ├── skill_analyzer_grid.py      # 电网布局分析
│   ├── skill_analyzer_dispatch.py  # 调度策略分析
│   └── skill_visualizer.py         # 可视化报告生成
├── llm/                            # 大模型调用层
│   └── qwen_client.py             # 千问大模型封装
├── config/                         # 配置层
│   └── settings.py                # 全局配置
├── output/                         # 运行时输出
│   ├── data/                      # 采集数据
│   ├── analysis/                  # 分析结果
│   ├── reports/                   # HTML 报告
│   └── memory/                    # 记忆文件
├── main.py                         # 主入口
├── requirements.txt                # 依赖
├── .env.example                    # 环境变量示例
└── README.md                       # 本文件
```

## 🔧 环境要求

- Python 3.9+
- Windows 操作系统
- 网络连接（用于调用大模型 API 和采集数据）

## 📦 安装步骤

### 1. 克隆/下载项目

```bash
cd power_grid_agent
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

```bash
# 复制示例文件
copy .env.example .env

# 编辑 .env 文件，填写您的 API Key
# QWEN_API_KEY=your_api_key_here  ← 替换为真实密钥
```

### 4. 运行

```bash
# 交互模式（默认）
python main.py

# 或指定参数
python main.py --all --topic "电网布局调度"
```

## ⚙️ 配置说明

所有配置项在 `.env` 文件中设置，不会硬编码到代码中。

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `QWEN_API_BASE` | 讯飞 MaaS API 地址 | `https://maas-api.cn-huabei-1.xf-yun.com/v2` |
| `QWEN_API_KEY` | API 密钥（必填） | - |
| `QWEN_MODEL_NAME` | 模型名称 | `xop35qwen2b` |
| `TEMPERATURE` | 生成温度（0-1） | `0.3` |
| `MAX_TOKENS` | 最大生成 token | `2048` |
| `REQUEST_TIMEOUT` | 请求超时（秒） | `60` |
| `MAX_RETRIES` | 最大重试次数 | `3` |
| `LOG_LEVEL` | 日志级别 | `INFO` |

## 🚀 使用示例

### 交互模式

```bash
python main.py --interactive
```

进入交互循环后：

```
⚡ 请输入指令 > 帮我采集电力政策法规
⚡ 请输入指令 > 分析电网布局
⚡ 请输入指令 > 生成调研报告
⚡ 请输入指令 > 帮我全面调研电网调度
⚡ 请输入指令 > 什么是电网调度？
⚡ 请输入指令 > quit
```

### 命令行模式

```bash
# 仅采集
python main.py --collect --topic "电力政策"

# 仅分析
python main.py --analyze --topic "电网布局"

# 仅生成报告
python main.py --report --topic "电网布局调度"

# 全流程（采集→分析→报告）
python main.py --all --topic "电网布局调度"
```

## 🔌 扩展指南：如何添加新 Skill

1. 在 `skills/` 目录下创建新文件，如 `skill_my_feature.py`

2. 继承 `SkillBase`，实现 `execute()` 方法：

```python
from core.skill_base import SkillBase

class SkillMyFeature(SkillBase):
    name = "my_feature"          # 技能名称（唯一标识）
    description = "我的自定义技能"  # 技能描述
    version = "1.0.0"

    def execute(self, params):
        # 在这里实现你的功能
        result = do_something(params)
        return {"success": True, "data": result}
```

3. 系统会自动发现和注册新 Skill（文件名以 `skill_` 开头）

4. 在 `MainAgent` 的 `INTENT_SKILL_MAP` 中添加映射关系

## ⚠️ 注意事项

1. **API Key**：必须配置有效的讯飞 MaaS API Key，否则大模型功能不可用
2. **小模型优化**：Qwen3.5-2B 是 2B 参数的小模型，所有 Prompt 都针对小模型做了优化
3. **模拟数据**：当无法从真实网站采集数据时，系统会自动使用模拟数据
4. **编码**：所有文件使用 UTF-8 编码，兼容 Windows 环境
5. **安全**：API Key 等敏感信息从 .env 文件读取，不硬编码

## 📝 许可

本项目仅供学习和研究使用。
