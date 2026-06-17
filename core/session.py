"""
会话管理模块 (session)

本模块负责维护对话历史和状态，是 Agent 进行多轮对话的基础。

设计思路：
    - 每个会话有一个唯一的 session_id
    - 对话历史以消息列表形式存储，每条消息包含 role 和 content
    - 支持 get_history 获取最近 n 条历史，避免发送过长上下文给小模型
    - 支持 format_for_llm 将历史格式化为 LLM 可接受的输入格式

对应 OpenClaw 概念：
    - OpenClaw 中会话管理负责维护对话上下文
    - 我们用简单的 Python 类实现了类似功能

使用示例：
    session = Session()
    session.add_message("user", "帮我分析电网布局")
    session.add_message("assistant", "好的，我来为您分析...")
    history = session.get_history(5)
    llm_input = session.format_for_llm()
"""

import uuid
import logging
from datetime import datetime
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class Session:
    """
    会话管理类。

    维护一轮对话的历史消息和状态。
    每个 Session 对应一次完整的交互过程。

    属性：
        session_id: 会话唯一标识（UUID 格式）
        messages: 消息列表，每条消息是 {"role": str, "content": str, "timestamp": str}
        created_at: 会话创建时间
        system_prompt: 系统提示词（可选，放在消息列表开头）

    使用示例：
        session = Session(system_prompt="你是电力系统专家")
        session.add_message("user", "什么是电网调度？")
        session.add_message("assistant", "电网调度是...")
        print(len(session))  # 输出: 2（不包含 system prompt）
    """

    def __init__(self, system_prompt: Optional[str] = None):
        """
        初始化会话。

        Args:
            system_prompt: 系统提示词，定义 Agent 的角色和行为规范。
                          如果提供，会作为第一条 system 消息添加到历史中。
                          对于小模型，好的 system_prompt 能显著提升输出质量。
        """
        # 生成唯一的会话 ID
        self.session_id: str = str(uuid.uuid4())[:8]  # 取前 8 位即可，方便日志查看

        # 消息列表
        # 每条消息格式: {"role": "user/assistant/system", "content": "...", "timestamp": "..."}
        self.messages: List[Dict[str, str]] = []

        # 会话创建时间
        self.created_at: str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 如果有系统提示词，添加到消息列表开头
        if system_prompt:
            self.add_message("system", system_prompt)

        logger.debug(f"会话已创建 | ID: {self.session_id}")

    def add_message(self, role: str, content: str) -> None:
        """
        添加一条消息到会话历史。

        Args:
            role: 消息角色，必须是 "system"、"user" 或 "assistant" 之一
                  - "system": 系统提示，定义行为规范
                  - "user": 用户输入
                  - "assistant": 模型回复
            content: 消息内容

        注意：
            role 不合法时会记录警告并跳过，不会抛出异常。
        """
        # 验证 role 的合法性
        valid_roles = {"system", "user", "assistant"}
        if role not in valid_roles:
            logger.warning(f"无效的消息角色: {role}，合法值: {valid_roles}")
            return

        # 添加消息，包含时间戳
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        self.messages.append(message)

        logger.debug(f"消息已添加 | 角色: {role} | 内容长度: {len(content)} 字符")

    def get_history(self, limit: Optional[int] = None) -> List[Dict[str, str]]:
        """
        获取对话历史。

        Args:
            limit: 最多返回的消息条数。None 表示返回全部。
                   对于小模型，建议限制在 10 条以内，避免上下文过长。

        Returns:
            List[Dict[str, str]]: 消息列表（不包含 timestamp 字段，因为 LLM 不需要）

        使用示例：
            # 获取最近 5 条消息
            recent = session.get_history(5)
            # 获取全部消息
            all_msgs = session.get_history()
        """
        if limit is None:
            messages = self.messages
        else:
            # 取最近的 limit 条消息
            # 但保留 system 消息（通常在列表开头）
            system_msgs = [m for m in self.messages if m["role"] == "system"]
            non_system_msgs = [m for m in self.messages if m["role"] != "system"]

            # 对非 system 消息取最近的 limit 条
            recent_non_system = non_system_msgs[-limit:] if limit < len(non_system_msgs) else non_system_msgs

            # 合并：system 消息 + 最近的非 system 消息
            messages = system_msgs + recent_non_system

        # 返回时去掉 timestamp 字段（LLM 不需要时间戳）
        return [{"role": m["role"], "content": m["content"]} for m in messages]

    def format_for_llm(self, limit: Optional[int] = None) -> List[Dict[str, str]]:
        """
        将会话历史格式化为 LLM 输入格式。

        这是 get_history 的别名，语义更明确。
        返回的格式可以直接传给 QwenClient.chat() 的 messages 参数。

        Args:
            limit: 最多返回的消息条数（建议小模型不超过 10 条）

        Returns:
            List[Dict[str, str]]: 格式化的消息列表

        使用示例：
            messages = session.format_for_llm(limit=6)
            response = llm_client.chat(messages)
        """
        return self.get_history(limit)

    def clear(self) -> None:
        """
        清空会话历史。

        注意：这会删除所有消息，包括 system prompt。
        如果需要保留 system prompt，请在清空后重新添加。
        """
        self.messages.clear()
        logger.debug(f"会话已清空 | ID: {self.session_id}")

    def get_last_user_message(self) -> Optional[str]:
        """
        获取最后一条用户消息。

        在判断用户意图时很有用。

        Returns:
            Optional[str]: 最后一条用户消息的内容，没有则返回 None
        """
        for msg in reversed(self.messages):
            if msg["role"] == "user":
                return msg["content"]
        return None

    def __len__(self) -> int:
        """返回消息数量（不包含 system 消息）"""
        return sum(1 for m in self.messages if m["role"] != "system")

    def __repr__(self) -> str:
        return f"Session(id={self.session_id}, messages={len(self.messages)})"
