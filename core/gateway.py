"""
网关模块 (gateway)

本模块是整个系统的入口，管理全局状态、创建主 Agent、启动命令行交互。

设计思路：
    - Gateway 是系统的"总管"，负责初始化和管理所有核心组件
    - 初始化顺序：加载配置 → 创建 LLM Client → 创建 Memory → 创建 ToolBox → 创建 MainAgent
    - 提供 run() 方法启动命令行交互循环
    - 提供 shutdown() 方法优雅关闭
    - 持有全局配置、日志器、LLM 实例等

为什么需要 Gateway？
    - 统一的系统入口，管理组件生命周期
    - 初始化逻辑集中，不会散落在各处
    - 优雅关闭时可以保存状态、释放资源

对应 OpenClaw 概念：
    - OpenClaw 中 Gateway 是主控中心，管理 Agent 生命周期、会话、技能加载
    - 我们用 Gateway 类实现了类似的功能
    - OpenClaw Gateway 用 TypeScript 实现，我们用 Python 实现

使用示例：
    gateway = Gateway()
    gateway.run()       # 启动交互循环
    gateway.shutdown()  # 优雅关闭
"""

import sys
import logging
from typing import Optional

from config.settings import settings
from llm.qwen_client import QwenClient
from core.memory import Memory
from core.toolbox import ToolBox
from core.main_agent import MainAgent
from core.session import Session

logger = logging.getLogger(__name__)


class Gateway:
    """
    网关类。

    整个系统的主控中心，负责初始化和管理所有核心组件。
    对应 OpenClaw 中的 Gateway 概念。

    属性：
        llm_client: LLM 客户端实例
        memory: 记忆系统实例
        toolbox: 工具系统实例
        main_agent: 主 Agent 实例
        is_running: 是否正在运行
        debug_inputs: 调试模式下的预设输入列表

    使用示例：
        # 正常运行
        gateway = Gateway()
        gateway.run()

        # 调试模式
        gateway = Gateway(debug_mode=True, debug_inputs=["分析电网布局", "quit"])
        gateway.run()
    """

    def __init__(self, debug_mode: bool = False, debug_inputs: list = None):
        """
        初始化网关。

        按顺序创建所有核心组件：
        1. 配置日志系统
        2. 创建 LLM 客户端
        3. 创建记忆系统
        4. 创建工具系统
        5. 创建主 Agent
        6. 初始化技能系统

        Args:
            debug_mode: 是否启用调试模式
            debug_inputs: 调试模式下的预设输入列表
        """
        self.is_running: bool = False
        self.debug_mode: bool = debug_mode
        self.debug_inputs: list = debug_inputs or []
        self.debug_input_index: int = 0

        # 第一步：配置日志系统
        self._setup_logging()

        logger.info("=" * 60)
        logger.info("电力系统市场调研 Agent - 网关初始化")
        logger.info("=" * 60)

        # 第二步：创建 LLM 客户端
        logger.info("[1/5] 创建 LLM 客户端...")
        self.llm_client: QwenClient = self._create_llm_client()

        # 第三步：创建记忆系统
        logger.info("[2/5] 创建记忆系统...")
        self.memory: Memory = Memory(llm_client=self.llm_client)

        # 第四步：创建工具系统
        logger.info("[3/5] 创建工具系统...")
        self.toolbox: ToolBox = ToolBox()

        # 第五步：创建主 Agent
        logger.info("[4/5] 创建主 Agent...")
        self.main_agent: MainAgent = MainAgent(
            llm_client=self.llm_client,
            memory=self.memory,
            toolbox=self.toolbox,
        )

        # 第六步：初始化技能系统
        logger.info("[5/5] 初始化技能系统...")
        skill_count = self.main_agent.initialize_skills()

        logger.info("=" * 60)
        logger.info(f"网关初始化完成！已加载 {skill_count} 个技能")
        logger.info("输入 'help' 查看帮助，输入 'quit' 退出")
        logger.info("=" * 60)

    def _setup_logging(self) -> None:
        """
        配置日志系统。

        日志输出到控制台，格式为：
        [时间] [级别] [模块名] 消息

        日志级别从 settings.LOG_LEVEL 读取。
        """
        # 日志格式
        log_format = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
        date_format = "%H:%M:%S"

        # 配置根日志器
        logging.basicConfig(
            level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
            format=log_format,
            datefmt=date_format,
            # 强制重新配置（避免重复配置）
            force=True,
        )

        # 降低第三方库的日志级别，避免干扰
        logging.getLogger("openai").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("httpx").setLevel(logging.WARNING)

        logger.info(f"日志系统已配置 | 级别: {settings.LOG_LEVEL}")

    def _create_llm_client(self) -> QwenClient:
        """
        创建 LLM 客户端。

        如果 API Key 未配置，返回 None（但不会中断初始化）。
        后续调用 LLM 时会检查客户端是否可用。

        Returns:
            QwenClient: LLM 客户端实例
        """
        try:
            client = QwenClient()
            logger.info(
                f"LLM 客户端创建成功 | 模型: {settings.QWEN_MODEL_NAME} | "
                f"地址: {settings.QWEN_API_BASE}"
            )
            return client
        except Exception as e:
            logger.error(f"LLM 客户端创建失败: {e}")
            logger.error("请检查 .env 文件中的 API 配置")
            # 创建一个空的客户端（后续调用会失败，但不会崩溃）
            return QwenClient(api_key="invalid_key")

    def run(self) -> None:
        """
        启动命令行交互循环。

        这是系统的主要运行模式。
        用户输入指令，系统处理后返回结果，循环往复。

        交互命令：
            - 直接输入自然语言：系统自动判断意图并执行
            - help: 显示帮助信息
            - status: 显示系统状态
            - skills: 显示已加载的技能
            - memory: 显示最近的记忆
            - clear: 清空会话
            - quit / exit: 退出系统
        """
        self.is_running = True

        # 打印欢迎信息
        self._print_welcome()

        # 主循环
        while self.is_running:
            try:
                # 读取用户输入（调试模式下使用预设输入）
                if self.debug_mode and self.debug_input_index < len(self.debug_inputs):
                    user_input = self.debug_inputs[self.debug_input_index]
                    self.debug_input_index += 1
                    print(f"\n⚡ [调试模式] 预设输入: {user_input}")
                else:
                    user_input = input("\n⚡ 请输入指令 > ").strip()

                # 空输入跳过
                if not user_input:
                    continue

                # 处理特殊命令
                if user_input.lower() in ("quit", "exit", "q"):
                    self.shutdown()
                    break
                elif user_input.lower() == "help":
                    self._print_help()
                    continue
                elif user_input.lower() == "status":
                    self._print_status()
                    continue
                elif user_input.lower() == "skills":
                    self._print_skills()
                    continue
                elif user_input.lower() == "memory":
                    self._print_memory()
                    continue
                elif user_input.lower() == "clear":
                    self.main_agent.session.clear()
                    print("✅ 会话已清空")
                    continue

                # 执行用户任务
                print("\n🔍 正在处理您的请求...")
                result = self.main_agent.execute(user_input)

                # 显示结果
                self._display_result(result)

                # 清理已完成的子 Agent
                self.main_agent.cleanup_sub_agents()

            except KeyboardInterrupt:
                # Ctrl+C 中断
                print("\n\n⚠️  检测到中断信号，输入 quit 退出系统")
                continue
            except EOFError:
                # 输入流结束（如管道输入）
                break
            except Exception as e:
                logger.error(f"处理用户输入时出错: {e}")
                print(f"\n❌ 处理出错: {e}")

    def _print_welcome(self) -> None:
        """打印欢迎信息。"""
        print("\n" + "=" * 60)
        print("  ⚡ 电力系统市场调研 Agent ⚡")
        print("  专注方向：电网布局调度")
        print("  架构：仿 OpenClaw 设计（Python 实现）")
        print("=" * 60)
        print("\n  可用功能：")
        print("    📋 采集 - 政策法规 / 行业新闻 / 市场数据")
        print("    📊 分析 - 电网布局 / 调度策略")
        print("    📈 报告 - 可视化 HTML 报告")
        print("    💬 问答 - 电力系统知识问答")
        print("\n  输入 'help' 查看详细帮助")
        print("=" * 60)

    def _print_help(self) -> None:
        """打印帮助信息。"""
        print("\n" + "-" * 60)
        print("📖 帮助信息")
        print("-" * 60)
        print("\n  命令：")
        print("    help       - 显示帮助信息")
        print("    status     - 显示系统状态")
        print("    skills     - 显示已加载的技能")
        print("    memory     - 显示最近的记忆")
        print("    clear      - 清空当前会话")
        print("    quit/exit  - 退出系统")
        print("\n  示例输入：")
        print('    "采集电力政策法规"')
        print('    "分析电网布局"')
        print('    "生成调研报告"')
        print('    "帮我全面调研电网调度"')
        print('    "什么是电网调度？"')
        print("-" * 60)

    def _print_status(self) -> None:
        """打印系统状态。"""
        status = self.main_agent.get_status()
        print("\n" + "-" * 60)
        print("📊 系统状态")
        print("-" * 60)
        print(f"  Agent ID:    {status['agent_id']}")
        print(f"  Agent 名称:  {status['name']}")
        print(f"  活跃状态:    {'✅ 是' if status['is_active'] else '❌ 否'}")
        print(f"  已加载技能:  {len(status['skills'])} 个")
        print(f"  子Agent数:   {status['sub_agents_count']} 个")
        print(f"  会话消息数:  {status['session_messages']} 条")
        print(f"  模型:        {settings.QWEN_MODEL_NAME}")
        print("-" * 60)

    def _print_skills(self) -> None:
        """打印已加载的技能列表。"""
        skills = self.main_agent.skill_registry.list_skills()
        print("\n" + "-" * 60)
        print("🔧 已加载技能")
        print("-" * 60)
        if skills:
            for i, skill in enumerate(skills, 1):
                print(f"  {i}. {skill['name']} - {skill['description']} (v{skill['version']})")
        else:
            print("  暂无已加载的技能")
        print("-" * 60)

    def _print_memory(self) -> None:
        """打印最近的记忆。"""
        recent = self.memory.get_recent(5)
        print("\n" + "-" * 60)
        print("🧠 最近记忆")
        print("-" * 60)
        if recent:
            for i, mem in enumerate(recent, 1):
                print(f"  {i}. [{mem.get('timestamp', '')}] {mem.get('key', '')}")
                print(f"     类型: {mem.get('type', '')} | 标签: {mem.get('tags', [])}")
        else:
            print("  暂无记忆")
        print("-" * 60)

    def _display_result(self, result: dict) -> None:
        """
        显示执行结果。

        Args:
            result: 执行结果字典
        """
        print("\n" + "-" * 60)

        if result.get("success"):
            print("✅ 执行成功")
        else:
            print("❌ 执行失败")

        # 显示意图
        if "intent" in result:
            print(f"  意图: {result['intent']}")

        # 显示消息
        if "message" in result:
            print(f"  消息: {result['message']}")

        # 显示详细结果（如果有）
        if "results" in result:
            print(f"\n  📊 详细结果:")
            results = result["results"]
            if isinstance(results, dict):
                for key, value in results.items():
                    if isinstance(value, dict) and "message" in value:
                        print(f"    - {key}: {value['message']}")
                    elif isinstance(value, dict) and "success" in value:
                        status = "✅" if value.get("success") else "❌"
                        print(f"    - {key}: {status}")
                    else:
                        print(f"    - {key}: {str(value)[:100]}")
            elif isinstance(results, list):
                for item in results:
                    if isinstance(item, dict):
                        skill = item.get("skill", "未知")
                        r = item.get("result", {})
                        status = "✅" if r.get("success") else "❌"
                        print(f"    - {skill}: {status}")

        # 显示聊天回复
        if "message" in result and result.get("intent") == "chat":
            print(f"\n  💬 回复:")
            print(f"  {result['message']}")

        # 显示错误
        if "error" in result:
            print(f"  ❌ 错误: {result['error']}")

        print("-" * 60)

    def run_task(self, task: str) -> dict:
        """
        执行单个任务（非交互模式）。

        用于命令行参数直接指定任务时调用。

        Args:
            task: 任务描述

        Returns:
            dict: 执行结果
        """
        logger.info(f"非交互模式执行任务: {task[:80]}")
        result = self.main_agent.execute(task)
        self.main_agent.cleanup_sub_agents()
        return result

    def shutdown(self) -> None:
        """
        优雅关闭系统。

        执行以下操作：
        1. 停止主循环
        2. 清理子 Agent
        3. 释放资源
        4. 记录日志
        """
        self.is_running = False

        # 清理子 Agent
        if hasattr(self, 'main_agent'):
            self.main_agent.cleanup_sub_agents()

        logger.info("系统已优雅关闭")
        print("\n👋 再见！感谢使用电力系统市场调研 Agent")

    def __repr__(self) -> str:
        return f"Gateway(running={self.is_running})"
