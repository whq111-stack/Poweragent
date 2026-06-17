"""
电力系统市场调研 Agent - 主入口

本文件是整个系统的入口，支持两种运行模式：
1. 命令行模式：通过参数指定要执行的任务
2. 交互模式：启动 Gateway 的命令行循环

架构说明（仿 OpenClaw 设计）：
    Gateway（网关）→ MainAgent（主Agent）→ SubAgent（子Agent）/ Skill（技能）
    其中：
    - Gateway 是系统入口，管理全局状态
    - MainAgent 理解用户意图，分发任务
    - SubAgent 执行具体任务（短生命周期）
    - Skill 是可插拔的功能模块

使用方式：
    # 交互模式（默认）
    python main.py --interactive

    # 仅采集
    python main.py --collect --topic "电网政策"

    # 仅分析
    python main.py --analyze --topic "电网布局"

    # 仅生成报告
    python main.py --report

    # 全流程
    python main.py --all --topic "电网布局调度"
"""

import sys
import argparse
import logging

from config.settings import settings

logger = logging.getLogger(__name__)


def parse_args():
    """
    解析命令行参数。

    Returns:
        argparse.Namespace: 解析后的参数
    """
    parser = argparse.ArgumentParser(
        description="⚡ 电力系统市场调研 Agent - 电网布局调度方向",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例：
  python main.py --interactive           # 交互模式
  python main.py --collect               # 仅采集
  python main.py --analyze               # 仅分析
  python main.py --report                # 仅生成报告
  python main.py --all                   # 全流程
  python main.py --all --topic "新能源"   # 指定主题
        """,
    )

    # 运行模式参数（互斥）
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="交互模式：启动命令行对话循环（默认模式）",
    )
    mode_group.add_argument(
        "--collect", "-c",
        action="store_true",
        help="仅执行数据采集（政策、新闻、市场数据）",
    )
    mode_group.add_argument(
        "--analyze", "-a",
        action="store_true",
        help="仅执行数据分析（电网布局、调度策略）",
    )
    mode_group.add_argument(
        "--report", "-r",
        action="store_true",
        help="仅生成可视化报告",
    )
    mode_group.add_argument(
        "--all",
        action="store_true",
        help="全流程：采集 → 分析 → 报告",
    )

    # 主题参数
    parser.add_argument(
        "--topic", "-t",
        type=str,
        default="电网布局调度",
        help="调研主题（默认：电网布局调度）",
    )

    # 调试参数
    parser.add_argument(
        "--debug", "-d",
        action="store_true",
        help="启用调试模式（用于 VSCode 调试）",
    )

    parser.add_argument(
        "--debug-input",
        type=str,
        default="",
        help="调试模式下的预设输入（用 | 分隔多个输入）",
    )

    return parser.parse_args()


def run_interactive(debug_mode: bool = False, debug_inputs: list = None):
    """
    启动交互模式。

    创建 Gateway 实例，启动命令行交互循环。
    这是最常用的运行模式。

    Args:
        debug_mode: 是否启用调试模式
        debug_inputs: 调试模式下的预设输入列表
    """
    from core.gateway import Gateway

    logger.info("启动交互模式..." + (" [调试模式]" if debug_mode else ""))
    gateway = Gateway(debug_mode=debug_mode, debug_inputs=debug_inputs)
    gateway.run()


def run_collect(topic: str):
    """
    执行数据采集。

    依次执行政策采集、新闻采集、市场数据采集。

    Args:
        topic: 采集主题
    """
    from core.gateway import Gateway

    logger.info(f"执行数据采集 | 主题: {topic}")
    gateway = Gateway()

    # 执行采集任务
    result = gateway.run_task(f"采集{topic}相关的政策法规、行业新闻和市场数据")

    # 显示结果
    print(f"\n✅ 采集完成")
    if result.get("results"):
        for key, value in result["results"].items():
            if isinstance(value, dict):
                msg = value.get("message", "")
                print(f"  - {key}: {msg}")


def run_analyze(topic: str):
    """
    执行数据分析。

    执行电网布局分析和调度策略分析。

    Args:
        topic: 分析主题
    """
    from core.gateway import Gateway

    logger.info(f"执行数据分析 | 主题: {topic}")
    gateway = Gateway()

    # 执行分析任务
    result = gateway.run_task(f"分析{topic}的电网布局和调度策略")

    # 显示结果
    print(f"\n✅ 分析完成")
    if result.get("results"):
        for key, value in result["results"].items():
            if isinstance(value, dict):
                msg = value.get("message", "")
                print(f"  - {key}: {msg}")


def run_report(topic: str):
    """
    生成可视化报告。

    Args:
        topic: 报告主题
    """
    from core.gateway import Gateway

    logger.info(f"生成可视化报告 | 主题: {topic}")
    gateway = Gateway()

    # 执行报告生成任务
    result = gateway.run_task(f"生成{topic}的调研报告")

    # 显示结果
    print(f"\n✅ 报告生成完成")
    if result.get("result"):
        report_path = result["result"].get("report_path", "")
        if report_path:
            print(f"  📄 报告路径: {report_path}")


def run_all(topic: str):
    """
    执行全流程：采集 → 分析 → 报告。

    Args:
        topic: 调研主题
    """
    from core.gateway import Gateway

    logger.info(f"执行全流程 | 主题: {topic}")
    gateway = Gateway()

    # 执行全流程任务
    result = gateway.run_task(f"全面调研{topic}，包括数据采集、分析和报告生成")

    # 显示结果
    print(f"\n✅ 全流程完成")
    if result.get("results"):
        results = result["results"]
        for phase in ["collect", "analyze", "report"]:
            if phase in results:
                phase_result = results[phase]
                if isinstance(phase_result, dict):
                    msg = phase_result.get("message", "")
                    print(f"  📋 {phase}: {msg}")

    # 查找报告路径
    report_info = results.get("report", {})
    if isinstance(report_info, dict) and report_info.get("result"):
        report_path = report_info["result"].get("report_path", "")
        if report_path:
            print(f"\n  📄 调研报告: {report_path}")


def main():
    """
    主函数。

    解析命令行参数，选择对应的运行模式。
    """
    args = parse_args()

    # 打印启动信息
    print("=" * 60)
    print("  ⚡ 电力系统市场调研 Agent")
    print("  专注方向：电网布局调度")
    print("  架构：仿 OpenClaw 设计（Python 实现）")
    print("=" * 60)

    try:
        # 解析调试输入
        debug_inputs = []
        if args.debug_input:
            debug_inputs = args.debug_input.split("|")
        
        if args.interactive or (not args.collect and not args.analyze
                                and not args.report and not args.all):
            # 默认模式：交互模式
            run_interactive(debug_mode=args.debug, debug_inputs=debug_inputs)
        elif args.collect:
            run_collect(args.topic)
        elif args.analyze:
            run_analyze(args.topic)
        elif args.report:
            run_report(args.topic)
        elif args.all:
            run_all(args.topic)

    except KeyboardInterrupt:
        print("\n\n⚠️  程序被用户中断")
        sys.exit(0)
    except Exception as e:
        logger.error(f"程序运行出错: {e}")
        print(f"\n❌ 出错了: {e}")
        print("请检查配置文件(.env)是否正确，以及网络连接是否正常。")
        sys.exit(1)


if __name__ == "__main__":
    main()
