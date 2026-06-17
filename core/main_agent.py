"""
主 Agent 模块 (main_agent)

本模块实现了长期存活的主 Agent，负责意图理解、任务分发和结果综合。

设计思路：
    - 主 Agent 是用户交互的入口，长期存活
    - 核心流程：接收输入 → 判断意图 → 派生子 Agent / 调用 Skill → 综合结果 → 返回
    - 维护已加载的 Skill 列表和会话历史
    - Prompt 设计针对 Qwen3.5-2B 小模型优化：简洁、分步、明确指定格式

意图分类：
    - collect: 采集类任务（政策采集、新闻采集、市场数据采集）
    - analyze: 分析类任务（电网布局分析、调度策略分析）
    - report:  报告生成任务
    - general: 综合性任务（需要多步骤完成）
    - chat:    闲聊/问答（不需要调用技能）

为什么主 Agent 不自己执行任务？
    - 职责分离：主 Agent 负责理解和协调，子 Agent 负责执行
    - 可扩展性：添加新功能只需添加新 Skill，不需要修改主 Agent
    - 可维护性：每个 Skill 独立维护，互不影响

对应 OpenClaw 概念：
    - OpenClaw 中 Main Agent 是长期存活的，理解用户意图、分发任务、综合结果
    - 我们用 MainAgent 类实现了类似的设计

使用示例：
    main_agent = MainAgent(llm_client=llm_client, memory=memory)
    result = main_agent.execute("帮我调研电网布局调度相关政策")
"""

import json
import logging
from typing import Any, Dict, List, Optional

from core.base_agent import BaseAgent
from core.sub_agent import SubAgent
from core.skill_base import SkillRegistry
from llm.qwen_client import QwenClient
from core.memory import Memory
from core.toolbox import ToolBox
from core.session import Session

logger = logging.getLogger(__name__)


class MainAgent(BaseAgent):
    """
    主 Agent 类。

    长期存活的 Agent，负责理解用户意图、分发任务、综合结果。
    是用户与系统交互的入口。

    属性：
        skill_registry: 技能注册表，管理所有可用的 Skill
        sub_agents: 当前活跃的子 Agent 列表

    核心流程：
        1. 接收用户输入
        2. 用 LLM 判断意图（返回结构化 JSON）
        3. 根据意图选择执行策略：
           - collect → 调用采集类 Skill
           - analyze → 调用分析类 Skill
           - report  → 调用可视化 Skill
           - general → 多步骤执行
           - chat    → 直接回答
        4. 综合结果返回给用户

    使用示例：
        agent = MainAgent(llm_client=llm_client, memory=memory)
        result = agent.execute("帮我调研电网布局")
    """

    # ====== 意图与 Skill 的映射关系 ======
    # 定义每个意图对应的 Skill 名称
    # 这样设计是为了：当 LLM 返回意图后，能快速找到对应的 Skill
    INTENT_SKILL_MAP = {
        "collect_policy": "collector_policy",     # 政策法规采集
        "collect_news": "collector_news",         # 行业新闻采集
        "collect_market": "collector_market",     # 市场数据采集
        "analyze_grid": "analyzer_grid",          # 电网布局分析
        "analyze_dispatch": "analyzer_dispatch",  # 调度策略分析
        "report": "visualizer",                   # 可视化报告
    }

    # 采集类意图（可以批量执行）
    COLLECT_INTENTS = ["collect_policy", "collect_news", "collect_market"]

    # 分析类意图
    ANALYZE_INTENTS = ["analyze_grid", "analyze_dispatch"]

    def __init__(
        self,
        llm_client: QwenClient,
        memory: Memory,
        toolbox: Optional[ToolBox] = None,
        session: Optional[Session] = None,
    ):
        """
        初始化主 Agent。

        Args:
            llm_client: LLM 客户端实例
            memory: 记忆系统实例
            toolbox: 工具系统实例（可选）
            session: 会话实例（可选）
        """
        super().__init__(
            name="主Agent",
            description="电力系统市场调研主Agent，负责意图理解、任务分发和结果综合",
            llm_client=llm_client,
            memory=memory,
            toolbox=toolbox,
            session=session or Session(
                system_prompt=(
                    "你是电力系统市场调研助手，专注于电网布局调度方向。\n"
                    "你可以帮助用户：采集政策法规、采集行业新闻、采集市场数据、\n"
                    "分析电网布局、分析调度策略、生成可视化报告。\n"
                    "请用简洁的中文回答。"
                )
            ),
        )

        # 技能注册表
        self.skill_registry = SkillRegistry()

        # 当前活跃的子 Agent 列表
        self.sub_agents: List[SubAgent] = []

        logger.info("主 Agent 初始化完成")

    def initialize_skills(self) -> int:
        """
        初始化技能系统。

        自动发现并注册 skills/ 目录下的所有 Skill。

        Returns:
            int: 注册的技能数量
        """
        count = self.skill_registry.discover_skills()
        logger.info(f"技能初始化完成 | 注册: {count} 个技能")

        # 打印已注册的技能列表
        for info in self.skill_registry.list_skills():
            logger.info(f"  - {info['name']}: {info['description']}")

        return count

    def execute(self, task: str) -> Dict[str, Any]:
        """
        执行用户任务。

        主 Agent 的核心执行逻辑：
        1. 分析意图
        2. 根据意图选择执行策略
        3. 执行任务（调用 Skill 或派生子 Agent）
        4. 综合结果返回

        Args:
            task: 用户输入的任务描述

        Returns:
            Dict[str, Any]: 执行结果
        """
        logger.info(f"主 Agent 接收任务: {task[:80]}")

        try:
            # 第一步：分析用户意图
            intent = self._analyze_intent(task)
            logger.info(f"意图分析结果: {intent}")

            # 第二步：根据意图选择执行策略
            if intent.get("intent") == "chat":
                # 闲聊/问答：直接用 LLM 回答
                return self._handle_chat(task)
            elif intent.get("intent") == "collect":
                # 采集任务
                return self._handle_collect(task, intent)
            elif intent.get("intent") == "analyze":
                # 分析任务
                return self._handle_analyze(task, intent)
            elif intent.get("intent") == "report":
                # 报告生成
                return self._handle_report(task)
            elif intent.get("intent") == "general":
                # 综合任务：多步骤执行
                return self._handle_general(task)
            else:
                # 未知意图，尝试直接回答
                logger.warning(f"未知意图: {intent}，尝试直接回答")
                return self._handle_chat(task)

        except Exception as e:
            logger.error(f"主 Agent 执行失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"执行任务时出错: {e}",
            }

    def _analyze_intent(self, task: str) -> Dict[str, str]:
        """
        分析用户意图。

        使用 LLM 判断用户的意图类型。
        针对小模型优化：prompt 简洁、选项有限、格式明确。

        Args:
            task: 用户输入

        Returns:
            Dict[str, str]: 意图分析结果，格式如：
                {"intent": "collect", "topic": "政策法规"}
                intent 的可能值：collect, analyze, report, general, chat
        """
        # 构造意图识别的 Prompt
        # 针对小模型的关键优化：
        # 1. 明确列出所有可能的意图
        # 2. 给出每个意图的示例
        # 3. 要求 JSON 格式输出
        intent_prompt = (
            "判断用户意图，从以下选项中选择一个意图名称：\n"
            "- collect：数据采集（如：采集政策、采集新闻、采集市场数据）\n"
            "- analyze：数据分析（如：分析电网布局、分析调度策略）\n"
            "- report：生成报告（如：生成可视化报告、出报告）\n"
            "- general：综合任务（如：帮我调研、全流程分析）\n"
            "- chat：闲聊问答（如：你好、什么是电网调度）\n"
            f"\n用户输入：{task}\n"
            "\n请用JSON格式回答：{\"intent\": \"意图名称\", \"topic\": \"主题关键词\"}\n"
            "注意：intent字段必须是collect/analyze/report/general/chat中的一个，不要使用数字。\n"
            "只输出JSON，不要其他文字。"
        )

        # 使用结构化对话接口
        result = self.llm_client.structured_chat(
            system_prompt="你是意图识别系统，只输出JSON格式的意图判断结果。",
            user_prompt=intent_prompt,
        )

        if result and "intent" in result:
            # 修复：如果 LLM 返回的是数字，转换为对应的意图名称
            intent_value = result["intent"]
            if intent_value in ["1", "2", "3", "4", "5"]:
                intent_map = {
                    "1": "collect",
                    "2": "analyze",
                    "3": "report",
                    "4": "general",
                    "5": "chat"
                }
                result["intent"] = intent_map[intent_value]
                logger.info(f"将数字意图 {intent_value} 转换为 {result['intent']}")
            return result

        # 如果 LLM 无法正确判断，使用关键词匹配作为后备方案
        logger.warning("LLM 意图判断失败，使用关键词匹配")
        return self._fallback_intent(task)

    def _fallback_intent(self, task: str) -> Dict[str, str]:
        """
        后备意图判断：基于关键词匹配。

        当 LLM 无法正确判断意图时使用。
        这是因为小模型可能无法稳定输出 JSON 格式。

        Args:
            task: 用户输入

        Returns:
            Dict[str, str]: 意图判断结果
        """
        task_lower = task.lower()

        # 采集相关关键词
        collect_keywords = ["采集", "收集", "抓取", "获取", "爬取", "政策", "新闻", "市场数据"]
        # 分析相关关键词
        analyze_keywords = ["分析", "研究", "评估", "电网布局", "调度策略", "调度分析"]
        # 报告相关关键词
        report_keywords = ["报告", "报表", "可视化", "图表", "生成报告"]
        # 综合相关关键词
        general_keywords = ["调研", "全流程", "综合", "整体"]

        # 按关键词匹配
        if any(kw in task_lower for kw in collect_keywords):
            return {"intent": "collect", "topic": task}
        elif any(kw in task_lower for kw in analyze_keywords):
            return {"intent": "analyze", "topic": task}
        elif any(kw in task_lower for kw in report_keywords):
            return {"intent": "report", "topic": task}
        elif any(kw in task_lower for kw in general_keywords):
            return {"intent": "general", "topic": task}
        else:
            return {"intent": "chat", "topic": task}

    def _handle_chat(self, task: str) -> Dict[str, Any]:
        """
        处理闲聊/问答。

        Args:
            task: 用户输入

        Returns:
            Dict[str, Any]: 回答结果
        """
        response = self.think(
            prompt=task,
            system_prompt=(
                "你是电力系统市场调研助手，专注于电网布局调度方向。\n"
                "用简洁的中文回答用户的问题。如果不确定，请诚实说明。"
            ),
        )

        return {
            "success": True,
            "intent": "chat",
            "message": response,
        }

    def _handle_collect(self, task: str, intent: Dict[str, str]) -> Dict[str, Any]:
        """
        处理采集任务。

        根据意图中的 topic 判断需要调用哪个采集 Skill。
        如果无法确定具体 Skill，则依次执行所有采集类 Skill。

        Args:
            task: 用户输入
            intent: 意图分析结果

        Returns:
            Dict[str, Any]: 采集结果
        """
        topic = intent.get("topic", "")
        results = []

        # 根据主题关键词选择采集 Skill
        skill_names = self._match_collect_skills(topic)

        for skill_name in skill_names:
            skill = self.skill_registry.get_skill(skill_name)
            if skill:
                logger.info(f"执行采集技能: {skill_name}")
                result = self.skill_registry.execute_skill(
                    skill_name,
                    {"topic": topic, "task": task}
                )
                results.append({
                    "skill": skill_name,
                    "result": result,
                })

                # 将结果存入记忆
                if self.memory and result.get("success"):
                    self.remember(
                        key=f"采集结果-{skill_name}",
                        content=result,
                        tags=["采集", skill_name],
                    )
            else:
                logger.warning(f"采集技能未找到: {skill_name}")

        return {
            "success": True,
            "intent": "collect",
            "results": results,
            "message": f"采集完成，执行了 {len(results)} 个采集技能",
        }

    def _match_collect_skills(self, topic: str) -> List[str]:
        """
        根据主题关键词匹配采集类 Skill。

        Args:
            topic: 主题关键词

        Returns:
            List[str]: 匹配的 Skill 名称列表
        """
        topic_lower = topic.lower()

        # 默认执行所有采集类 Skill
        if not topic or "全部" in topic_lower or "所有" in topic_lower:
            return ["collector_policy", "collector_news", "collector_market"]

        skills = []

        # 根据关键词匹配
        if any(kw in topic_lower for kw in ["政策", "法规", "法律"]):
            skills.append("collector_policy")
        if any(kw in topic_lower for kw in ["新闻", "资讯", "动态"]):
            skills.append("collector_news")
        if any(kw in topic_lower for kw in ["市场", "数据", "交易", "价格"]):
            skills.append("collector_market")

        # 如果没有匹配到，执行全部
        return skills if skills else ["collector_policy", "collector_news", "collector_market"]

    def _handle_analyze(self, task: str, intent: Dict[str, str]) -> Dict[str, Any]:
        """
        处理分析任务。

        Args:
            task: 用户输入
            intent: 意图分析结果

        Returns:
            Dict[str, Any]: 分析结果
        """
        topic = intent.get("topic", "")
        results = []

        # 根据主题关键词选择分析 Skill
        skill_names = self._match_analyze_skills(topic)

        for skill_name in skill_names:
            logger.info(f"执行分析技能: {skill_name}")
            result = self.skill_registry.execute_skill(
                skill_name,
                {"topic": topic, "task": task}
            )
            results.append({
                "skill": skill_name,
                "result": result,
            })

            # 将结果存入记忆
            if self.memory and result.get("success"):
                self.remember(
                    key=f"分析结果-{skill_name}",
                    content=result,
                    tags=["分析", skill_name],
                )

        return {
            "success": True,
            "intent": "analyze",
            "results": results,
            "message": f"分析完成，执行了 {len(results)} 个分析技能",
        }

    def _match_analyze_skills(self, topic: str) -> List[str]:
        """
        根据主题关键词匹配分析类 Skill。

        Args:
            topic: 主题关键词

        Returns:
            List[str]: 匹配的 Skill 名称列表
        """
        topic_lower = topic.lower()

        # 默认执行所有分析类 Skill
        if not topic or "全部" in topic_lower or "综合" in topic_lower:
            return ["analyzer_grid", "analyzer_dispatch"]

        skills = []

        if any(kw in topic_lower for kw in ["电网", "布局", "网架", "输电"]):
            skills.append("analyzer_grid")
        if any(kw in topic_lower for kw in ["调度", "运行", "控制", "消纳"]):
            skills.append("analyzer_dispatch")

        return skills if skills else ["analyzer_grid", "analyzer_dispatch"]

    def _handle_report(self, task: str) -> Dict[str, Any]:
        """
        处理报告生成任务。

        Args:
            task: 用户输入

        Returns:
            Dict[str, Any]: 报告生成结果
        """
        logger.info("执行报告生成技能")
        result = self.skill_registry.execute_skill(
            "visualizer",
            {"task": task}
        )

        if result.get("success"):
            self.remember(
                key="报告生成结果",
                content=result,
                tags=["报告"],
            )

        return {
            "success": result.get("success", False),
            "intent": "report",
            "result": result,
            "message": "报告生成完成" if result.get("success") else "报告生成失败",
        }

    def _handle_general(self, task: str) -> Dict[str, Any]:
        """
        处理综合任务。

        综合任务按顺序执行：采集 → 分析 → 报告

        Args:
            task: 用户输入

        Returns:
            Dict[str, Any]: 综合结果
        """
        all_results = {}

        # 第一步：采集
        logger.info("综合任务 - 第1步：数据采集")
        collect_result = self._handle_collect(task, {"intent": "collect", "topic": task})
        all_results["collect"] = collect_result

        # 第二步：分析
        logger.info("综合任务 - 第2步：数据分析")
        analyze_result = self._handle_analyze(task, {"intent": "analyze", "topic": task})
        all_results["analyze"] = analyze_result

        # 第三步：报告
        logger.info("综合任务 - 第3步：生成报告")
        report_result = self._handle_report(task)
        all_results["report"] = report_result

        return {
            "success": True,
            "intent": "general",
            "results": all_results,
            "message": "综合任务完成（采集→分析→报告）",
        }

    def create_sub_agent(
        self,
        name: str,
        description: str,
        task_description: str,
    ) -> SubAgent:
        """
        创建子 Agent。

        主 Agent 可以通过此方法创建子 Agent 来执行特定任务。
        子 Agent 执行完任务后应该调用 deactivate() 销毁。

        Args:
            name: 子 Agent 名称
            description: 子 Agent 描述
            task_description: 任务描述

        Returns:
            SubAgent: 新创建的子 Agent 实例
        """
        sub_agent = SubAgent(
            name=name,
            description=description,
            llm_client=self.llm_client,
            task_description=task_description,
            parent_agent_id=self.agent_id,
            toolbox=self.toolbox,
        )

        self.sub_agents.append(sub_agent)
        logger.info(f"主 Agent 创建子 Agent: {name}")
        return sub_agent

    def cleanup_sub_agents(self) -> None:
        """
        清理所有已完成任务的子 Agent。

        子 Agent 完成任务后应该被销毁，释放资源。
        此方法会停用所有非活跃的子 Agent，并从列表中移除。
        """
        before = len(self.sub_agents)
        self.sub_agents = [sa for sa in self.sub_agents if sa.is_active]
        after = len(self.sub_agents)

        if before != after:
            logger.info(f"清理子 Agent | 清理前: {before} | 清理后: {after}")

    def get_status(self) -> Dict[str, Any]:
        """
        获取主 Agent 的状态信息。

        Returns:
            Dict[str, Any]: 状态信息
        """
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "is_active": self.is_active,
            "skills": self.skill_registry.list_skills(),
            "sub_agents_count": len(self.sub_agents),
            "session_messages": len(self.session),
        }

    def __repr__(self) -> str:
        return (
            f"MainAgent(id={self.agent_id}, skills={len(self.skill_registry.list_skills())}, "
            f"sub_agents={len(self.sub_agents)})"
        )
