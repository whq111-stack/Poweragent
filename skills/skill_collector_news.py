"""
技能：行业新闻采集 (skill_collector_news)

本技能负责从电力行业新闻网站采集行业动态和新闻信息。

功能说明：
    - 从北极星电力网、中电联等网站采集行业新闻
    - 使用 requests + BeautifulSoup 解析网页内容
    - 采集结果保存为 JSON 文件到 output/data/ 目录
    - 返回采集的新闻列表

设计考虑：
    - 新闻时效性强，采集最新内容
    - 不同网站结构不同，解析逻辑需要健壮
    - 保存原始数据方便后续分析
    - 提供模拟数据后备方案

使用示例：
    skill = SkillCollectorNews()
    result = skill.execute({"topic": "电网调度新闻"})
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


class SkillCollectorNews(SkillBase):
    """
    行业新闻采集技能。

    从电力行业新闻网站采集行业动态和新闻信息。
    采集结果保存为 JSON 文件。

    类属性：
        name: 技能名称（唯一标识）
        description: 技能描述
        version: 版本号
        author: 作者
    """

    name = "collector_news"
    description = "行业新闻采集：从北极星电力网、中电联等采集电力行业新闻"
    version = "1.0.0"
    author = "power_grid_agent"

    # 目标新闻网站列表
    TARGET_SITES = [
        {
            "name": "北极星电力网",
            "url": "https://power.bjx.com.cn",
            "description": "电力行业综合信息平台",
        },
        {
            "name": "中国电力企业联合会",
            "url": "https://www.cec.org.cn",
            "description": "中电联官网，发布行业动态",
        },
        {
            "name": "中国电力报",
            "url": "http://www.cpnn.com.cn",
            "description": "电力行业权威媒体",
        },
    ]

    def __init__(self):
        """初始化行业新闻采集技能。"""
        super().__init__()
        self.toolbox = ToolBox()

    def load(self) -> bool:
        """
        加载技能。

        检查依赖库是否可用。

        Returns:
            bool: 加载是否成功
        """
        try:
            import requests
            from bs4 import BeautifulSoup
            self._loaded = True
            logger.info(f"技能加载成功: {self.name}")
            return True
        except ImportError as e:
            logger.error(f"技能加载失败: {self.name} | 缺少依赖: {e}")
            return False

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行行业新闻采集。

        Args:
            params: 执行参数，可包含：
                - topic: 采集主题
                - task: 原始任务描述

        Returns:
            Dict[str, Any]: 采集结果
        """
        topic = params.get("topic", "电网调度新闻")
        logger.info(f"开始采集行业新闻 | 主题: {topic}")

        # 尝试从真实网站采集
        news_list = self._collect_from_websites(topic)

        # 如果真实采集失败，使用模拟数据
        data_source = "real"
        if not news_list:
            logger.info("真实采集未获取到数据，使用模拟数据")
            news_list = self._generate_mock_data(topic)
            data_source = "mock"

        # 保存采集结果
        file_path = self._save_data(news_list, topic)

        result = {
            "success": True,
            "data": news_list,
            "count": len(news_list),
            "file_path": file_path,
            "source": data_source,
            "message": f"行业新闻采集完成 | 数量: {len(news_list)} | 来源: {data_source}",
        }

        logger.info(f"行业新闻采集完成 | 数量: {len(news_list)}")
        return result

    def _collect_from_websites(self, topic: str) -> List[Dict[str, Any]]:
        """
        从目标网站采集行业新闻。

        Args:
            topic: 采集主题

        Returns:
            List[Dict[str, Any]]: 采集到的新闻列表
        """
        news_list = []

        for site in self.TARGET_SITES:
            try:
                logger.info(f"正在访问: {site['name']} ({site['url']})")
                html = self.toolbox.http_get(site["url"], timeout=15)

                if html:
                    site_news = self._parse_html(html, site["name"], topic)
                    news_list.extend(site_news)
                    logger.info(f"  从 {site['name']} 采集到 {len(site_news)} 条新闻")
                else:
                    logger.warning(f"  无法访问 {site['name']}")

            except Exception as e:
                logger.error(f"  采集 {site['name']} 失败: {e}")

        return news_list

    def _parse_html(self, html: str, source_name: str, topic: str) -> List[Dict[str, Any]]:
        """
        解析网页 HTML，提取新闻信息。

        Args:
            html: 网页 HTML 内容
            source_name: 来源网站名称
            topic: 采集主题

        Returns:
            List[Dict[str, Any]]: 提取的新闻列表
        """
        news_list = []

        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html, "lxml")

            # 查找包含新闻标题的链接
            keywords = ["电力", "电网", "调度", "能源", "新能源", "光伏", "风电", "储能"]
            for link in soup.find_all("a", href=True):
                title = link.get_text(strip=True)
                if title and len(title) > 8 and any(kw in title for kw in keywords):
                    news_item = {
                        "title": title,
                        "url": link["href"],
                        "source": source_name,
                        "topic": topic,
                        "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    }
                    news_list.append(news_item)

        except ImportError:
            logger.warning("BeautifulSoup 未安装，无法解析 HTML")
        except Exception as e:
            logger.error(f"解析 HTML 失败: {e}")

        return news_list

    def _generate_mock_data(self, topic: str) -> List[Dict[str, Any]]:
        """
        生成模拟新闻数据。

        Args:
            topic: 采集主题

        Returns:
            List[Dict[str, Any]]: 模拟的新闻列表
        """
        mock_news = [
            {
                "title": "国家电网加快特高压建设，推动清洁能源大范围配置",
                "url": "https://power.bjx.com.cn/example/news_001",
                "source": "北极星电力网",
                "topic": topic,
                "publish_date": "2024-06-20",
                "summary": "国家电网公司加快推进特高压工程建设，计划年内投运多条特高压线路，提升清洁能源跨区输送能力。",
                "category": "电网建设",
                "keywords": ["特高压", "清洁能源", "跨区输送"],
                "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            },
            {
                "title": "新型储能装机突破5000万千瓦，调度管理面临新挑战",
                "url": "https://power.bjx.com.cn/example/news_002",
                "source": "北极星电力网",
                "topic": topic,
                "publish_date": "2024-06-18",
                "summary": "截至6月底，全国新型储能装机容量突破5000万千瓦，储能调度管理成为电网运行新课题。",
                "category": "储能",
                "keywords": ["新型储能", "调度管理", "电网运行"],
                "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            },
            {
                "title": "南方电网推进数字化转型，建设数字电网调度系统",
                "url": "https://www.cec.org.cn/example/news_003",
                "source": "中电联",
                "topic": topic,
                "publish_date": "2024-06-15",
                "summary": "南方电网公司加快推进数字化转型，建设新一代数字电网调度系统，提升调度智能化水平。",
                "category": "数字化",
                "keywords": ["数字化转型", "数字电网", "智能调度"],
                "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            },
            {
                "title": "全国电力需求侧响应能力持续提升，有效缓解调峰压力",
                "url": "https://power.bjx.com.cn/example/news_004",
                "source": "北极星电力网",
                "topic": topic,
                "publish_date": "2024-06-12",
                "summary": "通过需求侧响应机制，全国可调节负荷能力持续提升，有效缓解了高峰时段调峰压力。",
                "category": "需求侧",
                "keywords": ["需求侧响应", "调峰", "可调节负荷"],
                "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            },
            {
                "title": "省级电力现货市场全覆盖加速推进，市场机制逐步完善",
                "url": "https://www.cec.org.cn/example/news_005",
                "source": "中电联",
                "topic": topic,
                "publish_date": "2024-06-10",
                "summary": "截至目前，全国已有多个省份开展电力现货市场试运行，市场机制和规则体系逐步完善。",
                "category": "市场机制",
                "keywords": ["现货市场", "市场机制", "试运行"],
                "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            },
            {
                "title": "西北电网新能源消纳率创新高，调度策略持续优化",
                "url": "https://power.bjx.com.cn/example/news_006",
                "source": "北极星电力网",
                "topic": topic,
                "publish_date": "2024-06-08",
                "summary": "西北电网通过优化调度策略，新能源消纳率创历史新高，风电光伏利用率显著提升。",
                "category": "新能源消纳",
                "keywords": ["新能源消纳", "调度策略", "风电光伏"],
                "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            },
            {
                "title": "虚拟电厂参与电网调度取得积极进展",
                "url": "https://www.cec.org.cn/example/news_007",
                "source": "中电联",
                "topic": topic,
                "publish_date": "2024-06-05",
                "summary": "多地虚拟电厂项目陆续投入运营，参与电网调峰调频辅助服务，调度模式创新取得进展。",
                "category": "虚拟电厂",
                "keywords": ["虚拟电厂", "调峰调频", "辅助服务"],
                "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            },
            {
                "title": "2024年迎峰度夏电力保供方案发布，多措并举保障供电",
                "url": "https://power.bjx.com.cn/example/news_008",
                "source": "北极星电力网",
                "topic": topic,
                "publish_date": "2024-06-01",
                "summary": "国家发改委、国家能源局联合发布迎峰度夏电力保供方案，从供给侧、需求侧多措并举保障电力供应。",
                "category": "电力保供",
                "keywords": ["迎峰度夏", "电力保供", "供需平衡"],
                "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            },
        ]

        return mock_news

    def _save_data(self, data: List[Dict[str, Any]], topic: str) -> str:
        """
        保存采集数据到 JSON 文件。

        Args:
            data: 采集到的新闻列表
            topic: 采集主题

        Returns:
            str: 保存的文件路径
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f"news_{timestamp}.json"
        file_path = Path(settings.DATA_DIR) / file_name

        save_data = {
            "topic": topic,
            "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "count": len(data),
            "data": data,
        }

        success = self.toolbox.write_file(str(file_path), save_data)

        if success:
            logger.info(f"新闻数据已保存: {file_path}")
            return str(file_path)
        else:
            logger.error(f"新闻数据保存失败: {file_path}")
            return ""
