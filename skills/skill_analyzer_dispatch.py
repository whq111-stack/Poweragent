"""
技能：调度策略分析 (skill_analyzer_dispatch)

本技能负责分析电力系统调度策略，包括经济调度、安全约束、新能源消纳等。

功能说明：
    - 读取采集的数据
    - 构造 prompt 让 LLM 分析调度策略
    - 针对 Qwen3.5-2B 小模型优化 prompt
    - 分析结果保存为 JSON 文件

分析维度：
    1. 经济调度策略（发电成本优化、机组组合）
    2. 安全约束调度（N-1/N-2 校验、断面控制）
    3. 新能源消纳策略（优先调度、储能配合）
    4. 辅助服务机制（调频、调峰、备用）
    5. 市场化调度（现货市场、辅助服务市场）

使用示例：
    skill = SkillAnalyzerDispatch()
    result = skill.execute({"topic": "调度策略分析"})
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.skill_base import SkillBase
from core.toolbox import ToolBox
from config.settings import settings

logger = logging.getLogger(__name__)


class SkillAnalyzerDispatch(SkillBase):
    """
    调度策略分析技能。

    读取采集的数据，使用 LLM 或规则化方法分析调度策略。
    分析结果保存为 JSON 文件。

    类属性：
        name: 技能名称
        description: 技能描述
        version: 版本号
        author: 作者
    """

    name = "analyzer_dispatch"
    description = "调度策略分析：分析经济调度、安全约束、新能源消纳等调度策略"
    version = "1.0.0"
    author = "power_grid_agent"

    def __init__(self):
        """初始化调度策略分析技能。"""
        super().__init__()
        self.toolbox = ToolBox()
        self._llm_client = None

    def load(self) -> bool:
        """
        加载技能。

        Returns:
            bool: 加载是否成功
        """
        try:
            from llm.qwen_client import QwenClient
            self._llm_client = QwenClient()

            self._loaded = True
            logger.info(f"技能加载成功: {self.name}")
            return True
        except Exception as e:
            logger.error(f"技能加载失败: {self.name} | 错误: {e}")
            self._loaded = True
            logger.info(f"技能加载（降级模式）: {self.name} | 将使用规则化分析")
            return True

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行调度策略分析。

        Args:
            params: 执行参数，包含：
                - topic: 意图识别提取的主题关键词
                - task: 用户的完整原始问题

        Returns:
            Dict[str, Any]: 分析结果
        """
        # 优先使用用户的完整问题，如果没有则使用 topic
        full_question = params.get("task", params.get("topic", "调度策略"))
        topic = params.get("topic", "调度策略")
        logger.info(f"开始调度策略分析 | 主题: {topic} | 完整问题: {full_question}")

        # 1. 读取已采集的数据
        collected_data = self._load_collected_data()

        # 2. 尝试使用 LLM 分析
        analysis = None
        if self._llm_client:
            analysis = self._analyze_with_llm(full_question, topic, collected_data)

        # 3. 如果 LLM 分析失败，使用规则化分析
        if not analysis:
            logger.info("LLM 分析不可用，使用规则化分析")
            analysis = self._analyze_with_rules(full_question, topic, collected_data)

        # 4. 保存分析结果
        file_path = self._save_analysis(analysis, topic)

        result = {
            "success": True,
            "analysis": analysis,
            "file_path": file_path,
            "data_sources": len(collected_data),
            "message": f"调度策略分析完成",
        }

        logger.info("调度策略分析完成")
        return result

    def _load_collected_data(self) -> List[Dict[str, Any]]:
        """
        读取已采集的数据文件。

        Returns:
            List[Dict[str, Any]]: 采集的数据列表
        """
        data_files = self.toolbox.list_files(settings.DATA_DIR, "*.json")
        all_data = []

        for file_path in data_files:
            content = self.toolbox.read_file(file_path)
            if content:
                parsed = self.toolbox.json_parse(content)
                if parsed:
                    all_data.append({
                        "file": file_path,
                        "data": parsed,
                    })

        logger.info(f"已加载 {len(all_data)} 个数据文件")
        return all_data

    def _analyze_with_llm(self, full_question: str, topic: str, collected_data: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        使用 LLM 分析调度策略。

        根据用户主题动态生成分析内容。

        Args:
            full_question: 用户的完整原始问题
            topic: 意图识别提取的主题关键词
            collected_data: 已采集的数据

        Returns:
            Optional[Dict[str, Any]]: 分析结果
        """
        if not self._llm_client:
            return None

        try:
            data_summary = self._summarize_data(collected_data)

            # 根据用户主题确定分析维度
            analysis_dimensions = self._determine_dimensions(full_question)

            # 根据用户主题和数据进行综合分析
            main_prompt = (
                f"作为电力调度专家，请针对以下问题进行调度策略分析：\n\n"
                f"用户问题：{full_question}\n"
                f"主题关键词：{topic}\n\n"
                f"参考数据：\n{data_summary}\n\n"
                f"请从以下维度进行分析：\n"
                f"{analysis_dimensions}\n\n"
                f"请用JSON格式回答，包含分析内容和关键发现。"
            )

            analysis_result = self._llm_client.structured_chat(
                system_prompt="你是电力调度专家，擅长分析电力系统调度策略。请根据用户的具体问题，提供详细、准确的分析报告。回答必须与用户的问题紧密相关，不要提供无关的通用信息。",
                user_prompt=main_prompt,
            )

            analysis = {
                "method": "llm",
                "topic": topic,
                "full_question": full_question,
                "analysis": analysis_result or "LLM 分析不可用",
                "analyzed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }

            return analysis

        except Exception as e:
            logger.error(f"LLM 分析失败: {e}")
            return None

    def _determine_dimensions(self, full_question: str) -> str:
        """
        根据用户主题确定分析维度。

        Args:
            full_question: 用户的完整原始问题

        Returns:
            str: 分析维度列表
        """
        topic_lower = full_question.lower()
        
        dimensions = []
        
        if any(word in topic_lower for word in ["经济", "成本", "优化", "机组组合"]):
            dimensions.append("1. 经济调度策略（发电成本优化、机组组合）")
        
        if any(word in topic_lower for word in ["安全", "约束", "N-1", "断面"]):
            dimensions.append("2. 安全约束调度（N-1/N-2 校验、断面控制）")
        
        if any(word in topic_lower for word in ["新能源", "消纳", "风电", "光伏"]):
            dimensions.append("3. 新能源消纳策略（优先调度、储能配合）")
        
        if any(word in topic_lower for word in ["辅助服务", "调频", "调峰", "备用"]):
            dimensions.append("4. 辅助服务机制（调频、调峰、备用）")
        
        if any(word in topic_lower for word in ["市场", "现货", "交易"]):
            dimensions.append("5. 市场化调度（现货市场、辅助服务市场）")
        
        if not dimensions:
            dimensions = [
                "1. 经济调度策略",
                "2. 新能源消纳策略",
                "3. 安全约束调度",
            ]
        
        return "\n".join(dimensions)

    def _analyze_with_rules(self, full_question: str, topic: str, collected_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        使用规则化方法分析调度策略。

        Args:
            full_question: 用户的完整原始问题
            topic: 意图识别提取的主题关键词
            collected_data: 已采集的数据

        Returns:
            Dict[str, Any]: 分析结果
        """
        analysis = {
            "method": "rule_based",
            "topic": topic,
            "full_question": full_question,
            "analyzed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "economic_dispatch": {
                "description": "经济调度策略分析",
                "key_strategies": [
                    {
                        "name": "机组组合优化",
                        "description": "根据负荷预测，优化启停机组组合，降低系统总运行成本",
                        "current_status": "多数省级调度已实现日前机组组合优化",
                        "challenges": ["新能源出力不确定性增加优化难度", "储能等新资源需要新的建模方法"],
                    },
                    {
                        "name": "负荷经济分配",
                        "description": "在运行的机组间按边际成本最优分配发电出力",
                        "current_status": "常规经济调度已较成熟",
                        "challenges": ["新能源零边际成本改变了传统经济调度秩序"],
                    },
                    {
                        "name": "跨区优化调度",
                        "description": "利用区域间资源互补特性，实现跨区优化配置",
                        "current_status": "特高压通道利用率持续提升",
                        "challenges": ["省间壁垒影响优化效果", "交易与调度协调需加强"],
                    },
                ],
            },
            "security_constraints": {
                "description": "安全约束调度分析",
                "key_constraints": [
                    {
                        "name": "N-1/N-2 安全校验",
                        "description": "确保任意1个/2个元件故障后系统仍能安全运行",
                        "current_status": "日常调度中严格执行N-1校验",
                        "challenges": ["新能源高比例接入后，静态安全分析更复杂"],
                    },
                    {
                        "name": "断面控制",
                        "description": "控制关键输电断面潮流不超限",
                        "current_status": "主要断面已实现在线监控和自动控制",
                        "challenges": ["断面越限风险随新能源波动增加"],
                    },
                    {
                        "name": "电压稳定控制",
                        "description": "维持系统电压在合理范围内",
                        "current_status": "AVC自动电压控制系统广泛应用",
                        "challenges": ["新能源无功支撑能力弱，电压控制难度增大"],
                    },
                ],
            },
            "renewable_integration": {
                "description": "新能源消纳调度策略",
                "key_strategies": [
                    {
                        "name": "新能源优先调度",
                        "description": "在满足安全约束的前提下，优先消纳新能源发电",
                        "current_status": "国家政策要求新能源优先上网",
                        "effectiveness": "有效但存在限电风险",
                    },
                    {
                        "name": "储能配合调度",
                        "description": "利用储能系统平抑新能源波动，提升消纳能力",
                        "current_status": "新型储能装机快速增长，调度规则逐步完善",
                        "effectiveness": "储能调峰效果显著",
                    },
                    {
                        "name": "需求侧响应",
                        "description": "引导用户调整用电行为，匹配新能源出力曲线",
                        "current_status": "可调节负荷资源逐步纳入调度",
                        "effectiveness": "潜力大但市场化机制待完善",
                    },
                    {
                        "name": "跨区消纳",
                        "description": "通过特高压通道将新能源电力输送到负荷中心消纳",
                        "current_status": "西北新能源外送规模持续扩大",
                        "effectiveness": "有效但受通道容量限制",
                    },
                ],
            },
            "ancillary_services": {
                "description": "辅助服务调度机制",
                "service_types": [
                    {"type": "调频服务", "description": "维持系统频率稳定", "market_status": "部分地区已建立市场"},
                    {"type": "调峰服务", "description": "平衡负荷峰谷差", "market_status": "多数省份已建立补偿机制"},
                    {"type": "备用服务", "description": "提供运行备用容量", "market_status": "正在逐步市场化"},
                    {"type": "无功服务", "description": "维持电压水平", "market_status": "以补偿为主"},
                ],
            },
            "market_dispatch": {
                "description": "市场化调度发展趋势",
                "trends": [
                    "电力现货市场建设加速，价格信号引导资源优化配置",
                    "辅助服务市场逐步完善，各类资源公平参与",
                    "容量市场机制探索中，保障长期电力供应安全",
                    "绿色电力交易机制建立，促进新能源消纳",
                    "虚拟电厂和负荷聚合商参与市场交易",
                ],
            },
        }

        return analysis

    def _summarize_data(self, collected_data: List[Dict[str, Any]]) -> str:
        """
        将采集数据摘要为简短文本。

        Args:
            collected_data: 采集的数据

        Returns:
            str: 数据摘要
        """
        if not collected_data:
            return "暂无采集数据。"

        summary_parts = []
        for item in collected_data[:3]:
            data = item.get("data", {})
            topic = data.get("topic", "未知")
            count = data.get("count", 0)
            summary_parts.append(f"- {topic}: {count} 条记录")

        return "\n".join(summary_parts)

    def _save_analysis(self, analysis: Dict[str, Any], topic: str) -> str:
        """
        保存分析结果到 JSON 文件。

        Args:
            analysis: 分析结果
            topic: 分析主题

        Returns:
            str: 保存的文件路径
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f"dispatch_analysis_{timestamp}.json"
        file_path = Path(settings.ANALYSIS_DIR) / file_name

        success = self.toolbox.write_file(str(file_path), analysis)

        if success:
            logger.info(f"调度策略分析结果已保存: {file_path}")
            return str(file_path)
        else:
            logger.error(f"分析结果保存失败: {file_path}")
            return ""
