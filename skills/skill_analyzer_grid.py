"""
技能：电网布局分析 (skill_analyzer_grid)

本技能负责分析电网布局信息，包括区域电网结构、输电通道、互联情况等。

功能说明：
    - 读取采集的数据（政策、新闻、市场数据）
    - 构造 prompt 让 LLM 分析电网布局
    - 因为是 Qwen3.5-2B 小模型，prompt 要分步骤、简洁明确
    - 分析结果保存为 JSON 文件

设计考虑（针对小模型优化）：
    - 分步骤引导 LLM 分析，不要一次性要求太多
    - prompt 简洁明确，不超过 2000 tokens
    - 明确指定输出格式
    - 如果 LLM 分析失败，使用规则化的分析方法

分析维度：
    1. 区域电网结构（华北、华东、华中、西北、南方等）
    2. 输电通道（特高压线路、跨区输电）
    3. 互联情况（区域间互联、省间互联）
    4. 薄弱环节（供需缺口、通道瓶颈）
    5. 发展趋势（新建项目、规划方向）

使用示例：
    skill = SkillAnalyzerGrid()
    result = skill.execute({"topic": "电网布局分析"})
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


class SkillAnalyzerGrid(SkillBase):
    """
    电网布局分析技能。

    读取采集的数据，使用 LLM 或规则化方法分析电网布局。
    分析结果保存为 JSON 文件。

    类属性：
        name: 技能名称
        description: 技能描述
        version: 版本号
        author: 作者
    """

    name = "analyzer_grid"
    description = "电网布局分析：分析区域电网结构、输电通道、互联情况"
    version = "1.0.0"
    author = "power_grid_agent"

    def __init__(self):
        """初始化电网布局分析技能。"""
        super().__init__()
        self.toolbox = ToolBox()
        self._llm_client = None  # LLM 客户端（延迟初始化）

    def load(self) -> bool:
        """
        加载技能。

        Returns:
            bool: 加载是否成功
        """
        try:
            # 延迟导入 LLM 客户端，避免循环依赖
            from llm.qwen_client import QwenClient
            self._llm_client = QwenClient()

            self._loaded = True
            logger.info(f"技能加载成功: {self.name}")
            return True
        except Exception as e:
            logger.error(f"技能加载失败: {self.name} | 错误: {e}")
            # 即使 LLM 不可用，也可以使用规则化分析方法
            self._loaded = True
            logger.info(f"技能加载（降级模式）: {self.name} | 将使用规则化分析")
            return True

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行电网布局分析。

        分析流程：
        1. 读取已采集的数据
        2. 尝试使用 LLM 分析
        3. 如果 LLM 失败，使用规则化分析
        4. 保存分析结果

        Args:
            params: 执行参数，包含：
                - topic: 意图识别提取的主题关键词
                - task: 用户的完整原始问题

        Returns:
            Dict[str, Any]: 分析结果
        """
        # 优先使用用户的完整问题，如果没有则使用 topic
        full_question = params.get("task", params.get("topic", "电网布局"))
        topic = params.get("topic", "电网布局")
        logger.info(f"开始电网布局分析 | 主题: {topic} | 完整问题: {full_question}")

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
            "message": f"电网布局分析完成",
        }

        logger.info("电网布局分析完成")
        return result

    def _load_collected_data(self) -> List[Dict[str, Any]]:
        """
        读取已采集的数据文件。

        从 output/data/ 目录读取所有采集的 JSON 文件。

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
        使用 LLM 分析电网布局。

        针对小模型的 Prompt 设计：
        - 根据用户主题动态生成分析内容
        - 简洁明确，不超过 2000 tokens
        - 明确指定 JSON 输出格式

        Args:
            full_question: 用户的完整原始问题
            topic: 意图识别提取的主题关键词
            collected_data: 已采集的数据

        Returns:
            Optional[Dict[str, Any]]: 分析结果，失败返回 None
        """
        if not self._llm_client:
            return None

        try:
            # 构造数据摘要（避免过长的 prompt）
            data_summary = self._summarize_data(collected_data)

            # 分析用户问题，确定分析维度
            analysis_dimensions = self._determine_dimensions(full_question)

            # 根据用户主题和数据进行综合分析
            main_prompt = (
                f"作为电力系统专家，请针对以下问题进行电网布局分析：\n\n"
                f"用户问题：{full_question}\n"
                f"主题关键词：{topic}\n\n"
                f"参考数据：\n{data_summary}\n\n"
                f"请从以下维度进行分析：\n"
                f"{analysis_dimensions}\n\n"
                f"请用JSON格式回答，包含分析内容和关键发现。"
            )

            analysis_result = self._llm_client.structured_chat(
                system_prompt="你是电力系统专家，擅长电网布局分析。请根据用户的具体问题，提供详细、准确的分析报告。回答必须与用户的问题紧密相关，不要提供无关的通用信息。",
                user_prompt=main_prompt,
            )

            # 综合分析结果
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

    def _determine_dimensions(self, topic: str) -> str:
        """
        根据用户主题确定分析维度。

        Args:
            topic: 用户的分析主题

        Returns:
            str: 分析维度列表
        """
        topic_lower = topic.lower()
        
        dimensions = []
        
        # 根据关键词确定分析维度
        if any(region in topic_lower for region in ["华北", "华东", "华中", "西北", "东北", "南方", "区域", "地区"]):
            dimensions.append("1. 区域电网结构分析（覆盖范围、主要特点、负荷情况）")
        
        if any(word in topic_lower for word in ["输电", "通道", "线路", "特高压", "外送"]):
            dimensions.append("2. 输电通道分析（特高压线路、跨区输电能力）")
        
        if any(word in topic_lower for word in ["互联", "联络", "连接"]):
            dimensions.append("3. 区域互联分析（区域间联络情况）")
        
        if any(word in topic_lower for word in ["薄弱", "瓶颈", "问题", "挑战"]):
            dimensions.append("4. 薄弱环节分析（供需缺口、通道瓶颈）")
        
        if any(word in topic_lower for word in ["趋势", "发展", "规划", "未来"]):
            dimensions.append("5. 发展趋势分析（新建项目、规划方向）")
        
        # 如果没有匹配到特定维度，使用默认维度
        if not dimensions:
            dimensions = [
                "1. 区域电网结构分析",
                "2. 输电通道分析",
                "3. 发展趋势分析",
            ]
        
        return "\n".join(dimensions)

    def _analyze_with_rules(self, full_question: str, topic: str, collected_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        使用规则化方法分析电网布局。

        当 LLM 不可用时，使用预定义的知识库和规则进行分析。
        根据用户的具体问题筛选相关信息，避免返回无关内容。

        Args:
            full_question: 用户的完整原始问题
            topic: 意图识别提取的主题关键词
            collected_data: 已采集的数据

        Returns:
            Dict[str, Any]: 分析结果
        """
        topic_lower = full_question.lower()
        
        # 区域电网数据
        all_regions = {
            "华北": {
                "name": "华北电网",
                "coverage": "北京、天津、河北、山西、山东、内蒙古西部",
                "characteristics": "煤电基地集中，新能源发展迅速，特高压外送能力突出",
                "peak_load_mw": 210000,
                "installed_capacity_mw": 350000,
            },
            "华东": {
                "name": "华东电网",
                "coverage": "上海、江苏、浙江、安徽、福建",
                "characteristics": "负荷中心，用电需求大，受端电网，依赖区外受电",
                "peak_load_mw": 185000,
                "installed_capacity_mw": 280000,
            },
            "华中": {
                "name": "华中电网",
                "coverage": "湖北、湖南、河南、江西、四川、重庆",
                "characteristics": "三峡水电基地，西电东送枢纽，水火互济",
                "peak_load_mw": 165000,
                "installed_capacity_mw": 260000,
            },
            "东北": {
                "name": "东北电网",
                "coverage": "辽宁、吉林、黑龙江、内蒙古东部",
                "characteristics": "风电富集，供需相对宽松，外送能力待提升",
                "peak_load_mw": 65000,
                "installed_capacity_mw": 120000,
            },
            "西北": {
                "name": "西北电网",
                "coverage": "陕西、甘肃、青海、宁夏、新疆",
                "characteristics": "新能源外送基地，风光资源丰富，特高压外送通道密集",
                "peak_load_mw": 95000,
                "installed_capacity_mw": 230000,
            },
            "南方": {
                "name": "南方电网",
                "coverage": "广东、广西、云南、贵州、海南",
                "characteristics": "西电东送主通道，云南水电外送，广东负荷中心",
                "peak_load_mw": 175000,
                "installed_capacity_mw": 300000,
            },
        }

        # 根据用户问题筛选相关区域
        relevant_regions = []
        for region_name, region_data in all_regions.items():
            if region_name in topic_lower:
                relevant_regions.append(region_data)
        
        # 如果没有匹配到特定区域，返回所有区域
        if not relevant_regions:
            relevant_regions = list(all_regions.values())

        # 输电通道数据（按方向筛选）
        all_channels = [
            {"name": "准东-皖南", "voltage": "±1100kV", "capacity_mw": 12000, "type": "直流", "direction": "西北→华东"},
            {"name": "锡盟-山东", "voltage": "1000kV", "capacity_mw": 9000, "type": "交流", "direction": "华北→华东"},
            {"name": "哈密-郑州", "voltage": "±800kV", "capacity_mw": 8000, "type": "直流", "direction": "西北→华中"},
            {"name": "溪洛渡-浙江", "voltage": "±800kV", "capacity_mw": 8000, "type": "直流", "direction": "华中→华东"},
            {"name": "滇西北-广东", "voltage": "±800kV", "capacity_mw": 5000, "type": "直流", "direction": "南方→南方(广东)"},
            {"name": "酒泉-湖南", "voltage": "±800kV", "capacity_mw": 8000, "type": "直流", "direction": "西北→华中"},
            {"name": "扎鲁特-青州", "voltage": "±800kV", "capacity_mw": 10000, "type": "直流", "direction": "东北→华东"},
            {"name": "青海-河南", "voltage": "±800kV", "capacity_mw": 8000, "type": "直流", "direction": "西北→华中"},
        ]

        # 筛选相关通道
        relevant_channels = []
        if relevant_regions:
            region_names = [r["name"][:-2] for r in relevant_regions]  # 提取区域名称（去掉"电网"）
            for channel in all_channels:
                direction = channel["direction"]
                if any(region in direction for region in region_names):
                    relevant_channels.append(channel)
        
        # 如果没有匹配到特定通道，返回所有通道
        if not relevant_channels:
            relevant_channels = all_channels

        # 构建分析结果
        analysis = {
            "method": "rule_based",
            "topic": topic,
            "full_question": full_question,
            "analyzed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        # 只添加与用户问题相关的分析维度
        if any(region in topic_lower for region in ["华北", "华东", "华中", "西北", "东北", "南方", "区域", "地区"]):
            analysis["regional_structure"] = {
                "description": f"{topic} 的电网结构分析",
                "regions": relevant_regions,
            }

        if any(word in topic_lower for word in ["输电", "通道", "线路", "特高压", "外送"]):
            analysis["transmission_channels"] = {
                "description": f"{topic} 相关的输电通道分析",
                "uhv_lines": relevant_channels,
            }

        if any(word in topic_lower for word in ["互联", "联络", "连接"]):
            analysis["interconnection"] = {
                "description": "区域电网互联情况",
                "key_interconnections": self._get_relevant_interconnections(topic_lower),
            }

        if any(word in topic_lower for word in ["薄弱", "瓶颈", "问题", "挑战"]):
            analysis["weak_points"] = {
                "description": "电网薄弱环节和瓶颈",
                "issues": self._get_relevant_weak_points(topic_lower),
            }

        if any(word in topic_lower for word in ["趋势", "发展", "规划", "未来"]):
            analysis["development_trends"] = {
                "description": "电网布局发展趋势",
                "trends": self._get_relevant_trends(topic_lower),
            }

        # 如果没有特定维度匹配，添加默认分析
        if not analysis.keys() - {"method", "topic", "analyzed_at"}:
            analysis["regional_structure"] = {
                "description": f"{topic} 的电网结构分析",
                "regions": relevant_regions,
            }
            analysis["transmission_channels"] = {
                "description": f"{topic} 相关的输电通道分析",
                "uhv_lines": relevant_channels,
            }

        return analysis

    def _get_relevant_interconnections(self, topic_lower: str) -> list:
        """根据用户问题获取相关的区域互联信息"""
        all_interconnections = {
            "华北": ["华北-华东：通过锡盟-山东等特高压交流/直流互联", "华北-华中：通过1000kV交流特高压互联"],
            "华东": ["华北-华东：通过锡盟-山东等特高压交流/直流互联", "华中-华东：通过溪洛渡-浙江等特高压直流互联", "东北-华东：通过扎鲁特-青州特高压直流互联"],
            "华中": ["西北-华中：通过哈密-郑州、酒泉-湖南等特高压直流互联", "华中-华东：通过溪洛渡-浙江等特高压直流互联", "华北-华中：通过1000kV交流特高压互联"],
            "东北": ["东北-华东：通过扎鲁特-青州特高压直流互联"],
            "西北": ["西北-华中：通过哈密-郑州、酒泉-湖南等特高压直流互联", "西北-华东：通过准东-皖南特高压直流互联"],
            "南方": ["南方电网独立运行，通过直流与国家电网异步互联", "滇西北-广东特高压直流通道"],
        }

        # 获取相关区域的互联信息
        result = []
        for region, connections in all_interconnections.items():
            if region in topic_lower:
                result.extend(connections)
        
        # 如果没有匹配，返回所有
        return result if result else [
            "华北-华东：通过锡盟-山东等特高压交流/直流互联",
            "西北-华中：通过哈密-郑州、酒泉-湖南等特高压直流互联",
            "华中-华东：通过溪洛渡-浙江等特高压直流互联",
            "华北-华中：通过1000kV交流特高压互联",
            "南方电网独立运行，通过直流与国家电网异步互联",
        ]

    def _get_relevant_weak_points(self, topic_lower: str) -> list:
        """根据用户问题获取相关的薄弱环节信息"""
        all_weak_points = {
            "华北": ["特高压落点集中，短路电流超标风险", "京津冀负荷中心供电压力"],
            "华东": ["受端电网依赖区外受电，通道安全至关重要", "长三角负荷密度高，局部网架薄弱"],
            "华中": ["三峡水电外送通道压力", "川渝水电消纳问题"],
            "东北": ["外送通道不足，弃风弃光问题", "网架结构相对薄弱"],
            "西北": ["新能源集中地区外送通道不足", "新疆与主网联系相对薄弱"],
            "南方": ["云南水电外送通道饱和", "广东负荷中心供电安全"],
        }

        result = []
        for region, points in all_weak_points.items():
            if region in topic_lower:
                result.extend(points)
        
        return result if result else [
            "部分区域特高压落点集中，短路电流超标风险",
            "新能源集中地区外送通道不足，弃风弃光问题",
            "局部电网网架结构薄弱，N-1/N-2 校验不满足",
            "跨区输电通道利用率不均衡",
            "配电网接入分布式电源能力不足",
        ]

    def _get_relevant_trends(self, topic_lower: str) -> list:
        """根据用户问题获取相关的发展趋势信息"""
        all_trends = {
            "华北": ["特高压环网建设加强", "京津冀一体化电网发展", "新能源消纳能力提升"],
            "华东": ["受端电网智能化升级", "长三角柔性交流输电技术应用", "海上风电并网规模扩大"],
            "华中": ["三峡后续工程建设", "川渝特高压交流环网", "抽水蓄能电站建设"],
            "东北": ["新能源基地外送通道建设", "东北-华北联网加强", "智能电网技术应用"],
            "西北": ["风光大基地外送通道建设", "特高压直流密集布局", "新型电力系统示范区建设"],
            "南方": ["粤港澳大湾区智能电网", "海上风电规模化发展", "西电东送能力提升"],
        }

        result = []
        for region, trends in all_trends.items():
            if region in topic_lower:
                result.extend(trends)
        
        return result if result else [
            "特高压骨干网架持续加强，形成全国统一电网格局",
            "新能源大基地外送需求驱动特高压建设加速",
            "分布式能源渗透率提升推动配电网智能化改造",
            "储能规模化应用改变电网运行方式",
            "数字电网和智能化调度水平持续提升",
            "源网荷储一体化项目推动电网形态演进",
        ]

    def _summarize_data(self, collected_data: List[Dict[str, Any]]) -> str:
        """
        将采集数据摘要为简短文本，用于 LLM prompt。

        避免过长的 prompt，只保留关键信息。

        Args:
            collected_data: 采集的数据

        Returns:
            str: 数据摘要文本
        """
        if not collected_data:
            return "暂无采集数据。"

        summary_parts = []
        for item in collected_data[:3]:  # 最多取 3 个文件
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
        file_name = f"grid_analysis_{timestamp}.json"
        file_path = Path(settings.ANALYSIS_DIR) / file_name

        success = self.toolbox.write_file(str(file_path), analysis)

        if success:
            logger.info(f"电网布局分析结果已保存: {file_path}")
            return str(file_path)
        else:
            logger.error(f"分析结果保存失败: {file_path}")
            return ""
