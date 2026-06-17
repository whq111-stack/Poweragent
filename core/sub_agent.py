"""
子 Agent 模块 (sub_agent)

本模块实现了短生命周期的子 Agent，用于执行具体任务。

设计思路：
    - 子 Agent 是被主 Agent 创建的，执行完任务后即销毁
    - 子 Agent 没有技能系统和记忆系统（保持简单）
    - 子 Agent 的 Prompt 是简化的，专注于当前任务
    - 子 Agent 完成任务后通过 report() 方法向主 Agent 汇报结果

为什么需要子 Agent？
    - 主 Agent 不应该自己执行具体任务，而是分发任务
    - 子 Agent 可以并行执行，提高效率
    - 子 Agent 隔离了执行环境，一个子 Agent 失败不影响其他
    - 类似于人类组织中的"部门"或"小组"

对应 OpenClaw 概念：
    - OpenClaw 中 Sub Agent 是短生命周期的，专注于特定任务
    - 子 Agent 完成后向主 Agent 报告结果，然后销毁
    - 我们用 SubAgent 类实现了类似的设计

使用示例：
    sub = SubAgent(
        name="政策采集子Agent",
        description="负责采集电力政策法规",
        llm_client=llm_client,
        task_description="采集国家能源局最新的电力政策法规"
    )
    result = sub.execute("采集政策法规")
    report = sub.report()
    sub.deactivate()  # 任务完成，销毁
"""

import logging
from typing import Any, Dict, Optional

from core.base_agent import BaseAgent
from llm.qwen_client import QwenClient
from core.toolbox import ToolBox
from core.session import Session

logger = logging.getLogger(__name__)


class SubAgent(BaseAgent):
    """
    子 Agent 类。

    短生命周期的 Agent，被主 Agent 创建，执行具体任务后销毁。
    与主 Agent 的区别：
        - 没有技能系统（不维护 Skill 列表）
        - 没有记忆系统（不持久化记忆）
        - 简化的 Prompt（专注于当前任务）
        - 有明确的任务描述（task_description）

    属性：
        task_description: 当前任务描述
        result: 任务执行结果
        parent_agent_id: 创建此子 Agent 的主 Agent ID

    使用示例：
        sub = SubAgent(
            name="政策采集子Agent",
            description="负责采集电力政策法规",
            llm_client=llm_client,
            task_description="采集国家能源局最新的电力政策法规"
        )
        result = sub.execute("采集政策法规")
        report = sub.report()
    """

    def __init__(
        self,
        name: str,
        description: str,
        llm_client: QwenClient,
        task_description: str = "",
        parent_agent_id: Optional[str] = None,
        toolbox: Optional[ToolBox] = None,
    ):
        """
        初始化子 Agent。

        Args:
            name: 子 Agent 名称，如 "政策采集子Agent"
            description: 子 Agent 描述
            llm_client: LLM 客户端实例
            task_description: 任务描述，说明要执行什么任务
            parent_agent_id: 创建此子 Agent 的主 Agent ID
            toolbox: 工具系统实例（可选）
        """
        # 调用父类初始化
        # 注意：子 Agent 不传 memory（不需要记忆系统）
        # 子 Agent 创建新的会话（独立的对话上下文）
        super().__init__(
            name=name,
            description=description,
            llm_client=llm_client,
            memory=None,  # 子 Agent 不需要记忆
            toolbox=toolbox,
            session=Session(),  # 独立的会话
        )

        # 子 Agent 特有属性
        self.task_description: str = task_description
        self.result: Optional[Dict[str, Any]] = None
        self.parent_agent_id: Optional[str] = parent_agent_id

        logger.info(
            f"子 Agent 创建 | ID: {self.agent_id} | 名称: {self.name} | "
            f"任务: {task_description[:50] if task_description else '未指定'}"
        )

    def execute(self, task: str) -> Dict[str, Any]:
        """
        执行任务。

        子 Agent 的执行逻辑比主 Agent 简单：
        1. 接收任务描述
        2. 构造针对当前任务的 Prompt
        3. 调用 LLM 执行
        4. 返回结果

        为什么子 Agent 的执行逻辑比主 Agent 简单？
            - 子 Agent 只需要专注于一个具体任务
            - 不需要判断意图、分发任务、综合结果
            - Prompt 更短更精确，适合小模型

        Args:
            task: 任务描述

        Returns:
            Dict[str, Any]: 执行结果，包含 success、data、error 等字段
        """
        logger.info(f"子 Agent [{self.name}] 开始执行任务: {task[:50]}")

        try:
            # 构造子 Agent 的系统提示词
            # 针对小模型优化：简洁、明确、指定输出格式
            system_prompt = self._build_system_prompt()

            # 构造用户提示词
            # 将任务描述和上下文合并
            user_prompt = self._build_user_prompt(task)

            # 调用 LLM 执行
            response = self.think(
                prompt=user_prompt,
                system_prompt=system_prompt,
            )

            if not response:
                self.result = {
                    "success": False,
                    "error": "LLM 返回为空",
                    "agent_name": self.name,
                }
                return self.result

            # 存储结果
            self.result = {
                "success": True,
                "data": response,
                "agent_name": self.name,
                "task": task,
            }

            logger.info(f"子 Agent [{self.name}] 任务完成")
            return self.result

        except Exception as e:
            logger.error(f"子 Agent [{self.name}] 执行失败: {e}")
            self.result = {
                "success": False,
                "error": str(e),
                "agent_name": self.name,
            }
            return self.result

    def _build_system_prompt(self) -> str:
        """
        构造子 Agent 的系统提示词。

        针对小模型（Qwen3.5-2B）优化：
        - 简洁明确，不超过 500 字
        - 指定角色和输出格式
        - 不需要复杂的指令

        Returns:
            str: 系统提示词
        """
        return (
            f"你是一个专注于特定任务的助手。\n"
            f"你的名称：{self.name}\n"
            f"你的职责：{self.description}\n"
            f"\n"
            f"要求：\n"
            f"1. 专注于当前任务，不要偏题\n"
            f"2. 用简洁的中文回答\n"
            f"3. 如果涉及数据，请用 JSON 格式输出\n"
            f"4. 不要编造数据，基于已知信息回答\n"
        )

    def _build_user_prompt(self, task: str) -> str:
        """
        构造用户提示词。

        Args:
            task: 任务描述

        Returns:
            str: 用户提示词
        """
        prompt = f"任务：{task}\n"

        # 如果有任务描述，添加上下文
        if self.task_description:
            prompt += f"背景：{self.task_description}\n"

        prompt += "\n请完成任务并给出结果。"
        return prompt

    def report(self) -> Dict[str, Any]:
        """
        向主 Agent 汇报结果。

        子 Agent 完成任务后调用此方法，返回执行结果。
        主 Agent 收到结果后进行综合处理。

        Returns:
            Dict[str, Any]: 执行结果报告，包含以下字段：
                - success: 是否成功
                - data: 结果数据（成功时）
                - error: 错误信息（失败时）
                - agent_name: 子 Agent 名称
                - task: 任务描述
        """
        if self.result is None:
            return {
                "success": False,
                "error": "任务尚未执行",
                "agent_name": self.name,
            }

        logger.info(f"子 Agent [{self.name}] 汇报结果")
        return self.result

    def __repr__(self) -> str:
        return (
            f"SubAgent(id={self.agent_id}, name={self.name}, "
            f"task={self.task_description[:30] if self.task_description else 'None'})"
        )
