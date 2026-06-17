"""
Agent 基类模块 (base_agent)

本模块定义了所有 Agent 的抽象基类，包括主 Agent 和子 Agent 的公共逻辑。

设计思路：
    - BaseAgent 是主 Agent（MainAgent）和子 Agent（SubAgent）的父类
    - 提供了 LLM 调用（think）、工具使用（use_tool）、记忆存取（remember/recall）等通用方法
    - execute() 是抽象方法，由子类实现具体的执行逻辑
    - 所有 Agent 共享 LLM 客户端、记忆系统、工具系统等资源

为什么用抽象基类？
    - 统一主 Agent 和子 Agent 的接口
    - 避免代码重复，公共逻辑只需写一次
    - 方便后续扩展新的 Agent 类型

对应 OpenClaw 概念：
    - OpenClaw 中 Agent 有基类，主 Agent 和子 Agent 继承自同一基类
    - 主 Agent 长期存活，负责理解和分发
    - 子 Agent 短生命周期，执行具体任务后销毁
    - 我们用 Python 抽象基类实现了类似的设计

使用示例：
    # BaseAgent 不能直接实例化，需要通过子类使用
    # 参见 MainAgent 和 SubAgent 的实现
"""

import uuid
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional

from llm.qwen_client import QwenClient
from core.memory import Memory
from core.toolbox import ToolBox
from core.session import Session

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Agent 抽象基类。

    所有 Agent（主 Agent 和子 Agent）都继承此类。
    提供了 LLM 调用、工具使用、记忆存取等通用方法。

    属性：
        agent_id: Agent 唯一标识（UUID 格式，取前 8 位）
        name: Agent 名称
        description: Agent 描述
        llm_client: LLM 客户端实例，用于调用大模型
        memory: 记忆系统实例，用于存储和检索记忆
        toolbox: 工具系统实例，用于调用各种工具
        session: 会话实例，维护对话历史

    设计决策说明：
        - agent_id 使用 UUID 而不是递增数字，因为子 Agent 是动态创建和销毁的
        - llm_client 由外部注入，而不是在 Agent 内部创建，方便共享和测试
        - memory 和 toolbox 也是外部注入，遵循依赖注入原则

    使用示例：
        # 不能直接实例化 BaseAgent，需要通过子类
        # 参见 MainAgent 和 SubAgent
    """

    def __init__(
        self,
        name: str,
        description: str,
        llm_client: QwenClient,
        memory: Optional[Memory] = None,
        toolbox: Optional[ToolBox] = None,
        session: Optional[Session] = None,
    ):
        """
        初始化 Agent。

        Args:
            name: Agent 名称，如 "主Agent"、"政策采集子Agent"
            description: Agent 描述，简要说明功能
            llm_client: LLM 客户端实例，必须提供
            memory: 记忆系统实例，可选（子 Agent 不需要记忆）
            toolbox: 工具系统实例，可选（不提供时会自动创建）
            session: 会话实例，可选（不提供时会自动创建）
        """
        # Agent 唯一标识
        self.agent_id: str = str(uuid.uuid4())[:8]
        self.name: str = name
        self.description: str = description

        # LLM 客户端（必须提供）
        self.llm_client: QwenClient = llm_client

        # 记忆系统（子 Agent 不需要记忆，所以是可选的）
        self.memory: Optional[Memory] = memory

        # 工具系统（如果不提供，自动创建一个）
        self.toolbox: ToolBox = toolbox or ToolBox()

        # 会话（如果不提供，自动创建一个）
        self.session: Session = session or Session()

        # Agent 创建时间
        self.created_at: str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Agent 状态
        self._is_active: bool = True

        logger.info(f"Agent 创建 | ID: {self.agent_id} | 名称: {self.name}")

    def think(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        调用 LLM 进行思考。

        这是 Agent 最核心的能力：将问题交给大模型，获取回答。
        支持 system_prompt 定义角色，也支持多轮对话上下文。

        为什么叫 think？
            - 在 OpenClaw 中，Agent 的推理过程就是"思考"
            - 命名为 think 更符合 Agent 的设计理念
            - 与 use_tool（使用工具）、remember（记忆）形成语义对照

        Args:
            prompt: 思考的输入，即用户的问题或任务描述
            system_prompt: 系统提示词，定义 Agent 在本次思考中的角色。
                          如果不提供，使用会话中已有的 system 消息。

        Returns:
            str: LLM 的回复文本

        使用示例：
            # 简单思考
            answer = agent.think("什么是电网调度？")

            # 带角色的思考
            answer = agent.think(
                prompt="分析电网布局",
                system_prompt="你是电力系统专家，用简洁的语言回答"
            )
        """
        try:
            # 构造消息列表
            messages = []

            # 如果有 system_prompt，添加到消息列表开头
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})

            # 添加对话历史（如果有）
            # 对于小模型，限制历史长度，避免上下文过长
            history = self.session.get_history(limit=6)  # 最近 6 条
            messages.extend(history)

            # 添加当前输入
            messages.append({"role": "user", "content": prompt})

            # 调用 LLM
            response = self.llm_client.chat(messages)

            if response:
                # 将对话添加到会话历史
                self.session.add_message("user", prompt)
                self.session.add_message("assistant", response)

            return response

        except Exception as e:
            logger.error(f"Agent 思考失败: {self.name} | 错误: {e}")
            return f"[思考失败: {e}]"

    def use_tool(self, tool_name: str, **kwargs) -> Any:
        """
        调用工具。

        Agent 通过此方法使用 ToolBox 中的工具。
        工具名称对应 ToolBox 中的方法名。

        为什么需要 use_tool 方法？
            - 统一工具调用接口
            - 可以在调用前后添加日志和异常处理
            - 未来可以添加权限控制

        Args:
            tool_name: 工具名称，对应 ToolBox 的方法名。
                      可选值：read_file, write_file, http_get, http_post,
                             run_command, search_web, json_parse 等
            **kwargs: 传递给工具方法的参数

        Returns:
            Any: 工具方法的返回值

        使用示例：
            # 读取文件
            content = agent.use_tool("read_file", file_path="output/data/test.json")
            # 发送 HTTP 请求
            html = agent.use_tool("http_get", url="https://example.com")
        """
        try:
            # 检查工具是否存在
            if not hasattr(self.toolbox, tool_name):
                logger.error(f"工具不存在: {tool_name}")
                return None

            # 获取工具方法
            tool_method = getattr(self.toolbox, tool_name)

            # 检查是否是可调用的方法
            if not callable(tool_method):
                logger.error(f"不是可调用的工具: {tool_name}")
                return None

            # 调用工具
            logger.info(f"Agent [{self.name}] 调用工具: {tool_name} | 参数: {list(kwargs.keys())}")
            result = tool_method(**kwargs)

            return result

        except Exception as e:
            logger.error(f"工具调用失败: {tool_name} | 错误: {e}")
            return None

    def remember(self, key: str, content: Any, tags: Optional[List[str]] = None) -> bool:
        """
        存入记忆。

        将信息存储到记忆系统中，供后续检索使用。
        只有主 Agent 需要记忆，子 Agent 通常不使用此方法。

        为什么叫 remember？
            - 与 recall（回忆）形成语义对照
            - 更符合 Agent 的"记忆"概念

        Args:
            key: 记忆标题/键
            content: 记忆内容
            tags: 标签列表，方便搜索

        Returns:
            bool: 存储是否成功

        使用示例：
            agent.remember("政策采集结果", {"count": 10}, tags=["政策"])
        """
        if self.memory is None:
            logger.warning(f"Agent [{self.name}] 没有记忆系统，无法存储记忆")
            return False

        return self.memory.store(
            key=key,
            content=content,
            memory_type="agent_memory",
            tags=tags or [self.name],
        )

    def recall(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        检索记忆。

        从记忆系统中搜索相关信息。
        只有主 Agent 需要记忆，子 Agent 通常不使用此方法。

        Args:
            query: 搜索关键词
            limit: 最多返回的结果数量

        Returns:
            List[Dict[str, Any]]: 匹配的记忆列表

        使用示例：
            results = agent.recall("电网政策")
            for r in results:
                print(r["key"], r["content"])
        """
        if self.memory is None:
            logger.warning(f"Agent [{self.name}] 没有记忆系统，无法检索记忆")
            return []

        return self.memory.search(query, limit)

    @abstractmethod
    def execute(self, task: str) -> Any:
        """
        执行任务（抽象方法）。

        这是 Agent 的核心执行方法，子类必须实现。
        主 Agent 和子 Agent 有不同的执行逻辑。

        Args:
            task: 任务描述

        Returns:
            Any: 执行结果

        子类实现示例：
            # 主 Agent
            def execute(self, task):
                intent = self._analyze_intent(task)
                result = self._dispatch_task(intent, task)
                return result

            # 子 Agent
            def execute(self, task):
                result = self.think(task)
                return result
        """
        pass

    @property
    def is_active(self) -> bool:
        """Agent 是否处于活跃状态"""
        return self._is_active

    def deactivate(self) -> None:
        """
        停用 Agent。

        子 Agent 完成任务后调用此方法，标记为非活跃状态。
        主 Agent 通常不会被停用。
        """
        self._is_active = False
        logger.info(f"Agent 已停用 | ID: {self.agent_id} | 名称: {self.name}")

    def __repr__(self) -> str:
        return (
            f"BaseAgent(id={self.agent_id}, name={self.name}, "
            f"active={self._is_active})"
        )
