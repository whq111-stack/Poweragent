"""
技能：市场数据采集 (skill_collector_market)

本技能负责从各省电力交易平台采集市场数据。

功能说明：
    - 从各省电力交易中心采集市场数据
    - 包括：电价数据、交易量、供需比等
    - 采集结果保存为 JSON 文件到 output/data/ 目录
    - 返回采集的市场数据

设计考虑：
    - 各省电力交易平台格式不同，需要适配
    - 市场数据对时效性要求高
    - 提供模拟数据后备方案

使用示例：
    skill = SkillCollectorMarket()
    result = skill.execute({"topic": "电力市场数据"})
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


class SkillCollectorMarket(SkillBase):
    """
    市场数据采集技能。

    从各省电力交易平台采集市场数据。
    采集结果保存为 JSON 文件。

    类属性：
        name: 技能名称（唯一标识）
        description: 技能描述
        version: 版本号
        author: 作者
    """

    name = "collector_market"
    description = "市场数据采集：从各省电力交易平台采集市场数据"
    version = "1.0.0"
    author = "power_grid_agent"

    # 主要电力交易平台
    TARGET_SITES = [
        {
            "name": "北京电力交易中心",
            "url": "https://www.bj.sgcc.com.cn",
            "description": "负责跨省跨区电力交易",
        },
        {
            "name": "广州电力交易中心",
            "url": "https://www.gz.csg.cn",
            "description": "负责南方区域电力交易",
        },
        {
            "name": "电力市场化交易平台",
            "url": "https://pmos.sgcc.com.cn",
            "description": "国家电网电力市场运营系统",
        },
    ]

    def __init__(self):
        """初始化市场数据采集技能。"""
        super().__init__()
        self.toolbox = ToolBox()

    def load(self) -> bool:
        """
        加载技能。

        Returns:
            bool: 加载是否成功
        """
        try:
            import requests
            self._loaded = True
            logger.info(f"技能加载成功: {self.name}")
            return True
        except ImportError as e:
            logger.error(f"技能加载失败: {self.name} | 缺少依赖: {e}")
            return False

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行市场数据采集。

        Args:
            params: 执行参数

        Returns:
            Dict[str, Any]: 采集结果
        """
        topic = params.get("topic", "电力市场数据")
        logger.info(f"开始采集市场数据 | 主题: {topic}")

        # 尝试从真实网站采集
        market_data = self._collect_from_websites(topic)

        # 如果真实采集失败，使用模拟数据
        data_source = "real"
        if not market_data:
            logger.info("真实采集未获取到数据，使用模拟数据")
            market_data = self._generate_mock_data(topic)
            data_source = "mock"

        # 保存采集结果
        file_path = self._save_data(market_data, topic)

        result = {
            "success": True,
            "data": market_data,
            "count": len(market_data) if isinstance(market_data, list) else 1,
            "file_path": file_path,
            "source": data_source,
            "message": f"市场数据采集完成 | 来源: {data_source}",
        }

        logger.info(f"市场数据采集完成")
        return result

    def _collect_from_websites(self, topic: str) -> Optional[Dict[str, Any]]:
        """
        从目标网站采集市场数据。

        注意：电力交易平台的页面通常是动态加载的，
        简单的 HTTP GET 请求可能无法获取完整数据。
        实际项目中可能需要使用 Selenium 或 API 接口。

        Args:
            topic: 采集主题

        Returns:
            Optional[Dict[str, Any]]: 采集到的市场数据
        """
        for site in self.TARGET_SITES:
            try:
                logger.info(f"正在访问: {site['name']} ({site['url']})")
                html = self.toolbox.http_get(site["url"], timeout=15)

                if html:
                    # 电力交易平台通常是动态页面，简单解析可能无法获取数据
                    # 这里只做基本尝试，实际项目中需要更复杂的方案
                    logger.info(f"  访问 {site['name']} 成功，但动态页面可能需要更高级的采集方案")
                else:
                    logger.warning(f"  无法访问 {site['name']}")

            except Exception as e:
                logger.error(f"  采集 {site['name']} 失败: {e}")

        # 电力交易平台数据通常无法通过简单 HTTP 请求获取
        # 返回 None，使用模拟数据
        return None

    def _generate_mock_data(self, topic: str) -> Dict[str, Any]:
        """
        生成模拟市场数据。

        包含：电价数据、交易量、供需情况等。
        数据格式参考真实的电力市场数据格式。

        Args:
            topic: 采集主题

        Returns:
            Dict[str, Any]: 模拟的市场数据
        """
        mock_data = {
            "topic": topic,
            "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "summary": {
                "total_trade_volume_mwh": 1250000,     # 总交易电量（兆瓦时）
                "average_price_yuan_mwh": 365.5,       # 平均电价（元/兆瓦时）
                "peak_price_yuan_mwh": 520.0,          # 峰时电价
                "valley_price_yuan_mwh": 210.0,        # 谷时电价
                "supply_demand_ratio": 1.12,           # 供需比
                "renewable_ratio_pct": 32.5,           # 新能源占比（%）
            },
            "regional_data": [
                {
                    "region": "华东",
                    "trade_volume_mwh": 350000,
                    "avg_price_yuan_mwh": 420.0,
                    "peak_load_mw": 185000,
                    "renewable_pct": 28.0,
                    "interconnection": "通过特高压与华北、华中互联",
                },
                {
                    "region": "华北",
                    "trade_volume_mwh": 280000,
                    "avg_price_yuan_mwh": 380.0,
                    "peak_load_mw": 210000,
                    "renewable_pct": 35.0,
                    "interconnection": "特高压外送基地，向华东、华中送电",
                },
                {
                    "region": "华中",
                    "trade_volume_mwh": 250000,
                    "avg_price_yuan_mwh": 350.0,
                    "peak_load_mw": 165000,
                    "renewable_pct": 30.0,
                    "interconnection": "三峡外送枢纽，连接华东、华南",
                },
                {
                    "region": "西北",
                    "trade_volume_mwh": 180000,
                    "avg_price_yuan_mwh": 280.0,
                    "peak_load_mw": 95000,
                    "renewable_pct": 45.0,
                    "interconnection": "新能源外送基地，通过特高压外送",
                },
                {
                    "region": "南方",
                    "trade_volume_mwh": 190000,
                    "avg_price_yuan_mwh": 390.0,
                    "peak_load_mw": 175000,
                    "renewable_pct": 25.0,
                    "interconnection": "西电东送主要通道，云南水电外送",
                },
            ],
            "price_trend": [
                {"month": "2024-01", "avg_price": 355.0},
                {"month": "2024-02", "avg_price": 340.0},
                {"month": "2024-03", "avg_price": 330.0},
                {"month": "2024-04", "avg_price": 325.0},
                {"month": "2024-05", "avg_price": 345.0},
                {"month": "2024-06", "avg_price": 365.5},
            ],
            "key_metrics": {
                "cross_regional_trade_mwh": 420000,     # 跨区交易电量
                "ancillary_service_ratio_pct": 8.5,     # 辅助服务占比
                "demand_response_capacity_mw": 15000,   # 需求响应容量
                "energy_storage_capacity_mw": 25000,    # 储能装机容量
                "virtual_power_plant_count": 35,         # 虚拟电厂数量
            },
        }

        return mock_data

    def _save_data(self, data: Any, topic: str) -> str:
        """
        保存采集数据到 JSON 文件。

        Args:
            data: 采集到的市场数据
            topic: 采集主题

        Returns:
            str: 保存的文件路径
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f"market_{timestamp}.json"
        file_path = Path(settings.DATA_DIR) / file_name

        save_data = {
            "topic": topic,
            "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "data": data,
        }

        success = self.toolbox.write_file(str(file_path), save_data)

        if success:
            logger.info(f"市场数据已保存: {file_path}")
            return str(file_path)
        else:
            logger.error(f"市场数据保存失败: {file_path}")
            return ""
