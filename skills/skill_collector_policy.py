"""
技能：政策法规采集 (skill_collector_policy)

本技能负责从政府网站采集电力行业政策法规信息。

功能说明：
    - 从国家能源局、国家发改委等网站采集电力政策法规
    - 使用 requests + BeautifulSoup 解析网页内容
    - 采集结果保存为 JSON 文件到 output/data/ 目录
    - 返回采集的政策列表

设计考虑：
    - 网站结构可能变化，所以解析逻辑要健壮
    - 采集频率要有节制，避免给目标网站造成压力
    - 保存原始数据，方便后续分析使用
    - 由于目标网站可能无法访问（网络限制等），提供模拟数据后备方案

对应 OpenClaw 概念：
    - OpenClaw 中每个 Skill 是独立模块，包含描述和执行逻辑
    - 本 Skill 对应 OpenClaw 的"采集器"角色

使用示例：
    skill = SkillCollectorPolicy()
    result = skill.execute({"topic": "电力政策法规"})
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


class SkillCollectorPolicy(SkillBase):
    """
    政策法规采集技能。

    从政府网站采集电力行业政策法规信息。
    采集结果保存为 JSON 文件。

    类属性：
        name: 技能名称（唯一标识）
        description: 技能描述
        version: 版本号
        author: 作者
    """

    name = "collector_policy"
    description = "政策法规采集：从国家能源局、发改委等采集电力政策法规"
    version = "1.0.0"
    author = "power_grid_agent"

    # 目标网站列表
    # 这些是电力行业政策的主要发布渠道
    TARGET_SITES = [
        {
            "name": "国家能源局",
            "url": "http://www.nea.gov.cn",
            "description": "国家能源局官方网站，发布电力行业政策法规",
        },
        {
            "name": "国家发改委",
            "url": "https://www.ndrc.gov.cn",
            "description": "国家发改委官网，发布能源领域宏观政策",
        },
        {
            "name": "国务院",
            "url": "https://www.gov.cn",
            "description": "国务院官网，发布国家级政策法规",
        },
    ]

    def __init__(self):
        """初始化政策法规采集技能。"""
        super().__init__()
        self.toolbox = ToolBox()  # 工具箱，用于网络请求和文件操作

    def load(self) -> bool:
        """
        加载技能。

        检查依赖库是否可用（requests、beautifulsoup4）。

        Returns:
            bool: 加载是否成功
        """
        try:
            # 检查 requests 库
            import requests
            # 检查 BeautifulSoup
            from bs4 import BeautifulSoup

            self._loaded = True
            logger.info(f"技能加载成功: {self.name}")
            return True
        except ImportError as e:
            logger.error(f"技能加载失败: {self.name} | 缺少依赖: {e}")
            logger.error("请执行: pip install requests beautifulsoup4")
            return False

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行政策法规采集。

        采集流程：
        1. 确定采集主题
        2. 遍历目标网站，尝试采集
        3. 如果网站不可访问，使用模拟数据
        4. 保存采集结果为 JSON 文件
        5. 返回采集结果

        Args:
            params: 执行参数，可包含：
                - topic: 采集主题（如 "电力政策法规"）
                - task: 原始任务描述

        Returns:
            Dict[str, Any]: 采集结果，格式如：
                {
                    "success": True,
                    "data": [...],  # 政策列表
                    "count": 10,    # 采集数量
                    "file_path": "output/data/policy_20240115.json",
                    "source": "real/mock",  # 数据来源
                }
        """
        topic = params.get("topic", "电力政策法规")
        logger.info(f"开始采集政策法规 | 主题: {topic}")

        # 尝试从真实网站采集
        policies = self._collect_from_websites(topic)

        # 如果真实采集失败，使用模拟数据
        data_source = "real"
        if not policies:
            logger.info("真实采集未获取到数据，使用模拟数据")
            policies = self._generate_mock_data(topic)
            data_source = "mock"

        # 保存采集结果
        file_path = self._save_data(policies, topic)

        result = {
            "success": True,
            "data": policies,
            "count": len(policies),
            "file_path": file_path,
            "source": data_source,
            "message": f"政策法规采集完成 | 数量: {len(policies)} | 来源: {data_source}",
        }

        logger.info(f"政策法规采集完成 | 数量: {len(policies)}")
        return result

    def _collect_from_websites(self, topic: str) -> List[Dict[str, Any]]:
        """
        从目标网站采集政策法规。

        Args:
            topic: 采集主题

        Returns:
            List[Dict[str, Any]]: 采集到的政策列表
        """
        policies = []

        for site in self.TARGET_SITES:
            try:
                logger.info(f"正在访问: {site['name']} ({site['url']})")

                # 发送 HTTP 请求
                html = self.toolbox.http_get(site["url"], timeout=15)

                if html:
                    # 尝试解析网页内容
                    site_policies = self._parse_html(html, site["name"], topic)
                    policies.extend(site_policies)
                    logger.info(f"  从 {site['name']} 采集到 {len(site_policies)} 条政策")
                else:
                    logger.warning(f"  无法访问 {site['name']}")

            except Exception as e:
                logger.error(f"  采集 {site['name']} 失败: {e}")

        return policies

    def _parse_html(self, html: str, source_name: str, topic: str) -> List[Dict[str, Any]]:
        """
        解析网页 HTML，提取政策法规信息。

        使用 BeautifulSoup 解析 HTML，提取标题、链接、日期等信息。

        Args:
            html: 网页 HTML 内容
            source_name: 来源网站名称
            topic: 采集主题

        Returns:
            List[Dict[str, Any]]: 提取的政策列表
        """
        policies = []

        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html, "lxml")

            # 查找包含政策链接的元素
            # 不同网站结构不同，这里使用通用的解析策略
            # 查找所有 a 标签，筛选与电力/能源相关的链接
            for link in soup.find_all("a", href=True):
                title = link.get_text(strip=True)

                # 过滤条件：标题不为空，且包含关键词
                keywords = ["电力", "能源", "电网", "调度", "发电", "输电", "配电"]
                if title and any(kw in title for kw in keywords):
                    href = link["href"]

                    # 补全相对链接
                    if href.startswith("/"):
                        for site in self.TARGET_SITES:
                            if site["name"] == source_name:
                                href = site["url"] + href
                                break

                    policy = {
                        "title": title,
                        "url": href,
                        "source": source_name,
                        "topic": topic,
                        "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    }
                    policies.append(policy)

        except ImportError:
            logger.warning("BeautifulSoup 未安装，无法解析 HTML")
        except Exception as e:
            logger.error(f"解析 HTML 失败: {e}")

        return policies

    def _generate_mock_data(self, topic: str) -> List[Dict[str, Any]]:
        """
        生成模拟数据。

        当无法从真实网站采集时，使用模拟数据。
        模拟数据基于真实的电力行业政策格式，但内容是示例性的。

        为什么需要模拟数据？
            - 开发和测试时目标网站可能无法访问
            - 保证系统功能完整性，不会因为网络问题完全不可用
            - 方便演示和展示

        Args:
            topic: 采集主题

        Returns:
            List[Dict[str, Any]]: 模拟的政策列表
        """
        mock_policies = [
            {
                "title": "关于加强电力系统调峰能力建设的指导意见",
                "url": "https://www.ndrc.gov.cn/example/policy_001",
                "source": "国家发改委",
                "topic": topic,
                "publish_date": "2024-06-15",
                "summary": "为提升电力系统调峰能力，保障新能源消纳，提出加快抽水蓄能、新型储能等调峰资源建设。",
                "keywords": ["调峰", "储能", "新能源消纳"],
                "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            },
            {
                "title": "电力现货市场基本规则（试行）",
                "url": "https://www.nea.gov.cn/example/policy_002",
                "source": "国家能源局",
                "topic": topic,
                "publish_date": "2024-05-20",
                "summary": "规范电力现货市场运营，明确市场成员、交易品种、价格机制等基本规则。",
                "keywords": ["现货市场", "电力交易", "价格机制"],
                "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            },
            {
                "title": "关于促进新时代新能源高质量发展的实施方案",
                "url": "https://www.gov.cn/example/policy_003",
                "source": "国务院",
                "topic": topic,
                "publish_date": "2024-04-10",
                "summary": "推动风电、光伏发电等新能源高质量发展，完善新能源并网和消纳机制。",
                "keywords": ["新能源", "风电", "光伏", "并网"],
                "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            },
            {
                "title": "电网调度管理条例（修订草案征求意见稿）",
                "url": "https://www.nea.gov.cn/example/policy_004",
                "source": "国家能源局",
                "topic": topic,
                "publish_date": "2024-03-25",
                "summary": "修订电网调度管理相关条例，适应新型电力系统建设需要，强化安全调度和优先调度新能源。",
                "keywords": ["电网调度", "安全调度", "新能源优先"],
                "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            },
            {
                "title": "关于推进电力源网荷储一体化和多能互补发展的指导意见",
                "url": "https://www.ndrc.gov.cn/example/policy_005",
                "source": "国家发改委",
                "topic": topic,
                "publish_date": "2024-02-18",
                "summary": "推进源网荷储一体化，实现电力系统多能互补优化运行，提升系统整体效率。",
                "keywords": ["源网荷储", "多能互补", "系统优化"],
                "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            },
            {
                "title": "跨省跨区电力交易管理办法",
                "url": "https://www.nea.gov.cn/example/policy_006",
                "source": "国家能源局",
                "topic": topic,
                "publish_date": "2024-01-30",
                "summary": "规范跨省跨区电力交易，促进电力资源优化配置和清洁能源大范围消纳。",
                "keywords": ["跨省交易", "清洁能源", "资源优化"],
                "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            },
            {
                "title": "关于加强电网规划建设的指导意见",
                "url": "https://www.ndrc.gov.cn/example/policy_007",
                "source": "国家发改委",
                "topic": topic,
                "publish_date": "2024-01-10",
                "summary": "加强电网规划与建设的统筹协调，推动主干网架和配电网协调发展，保障电力可靠供应。",
                "keywords": ["电网规划", "主干网架", "配电网"],
                "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            },
            {
                "title": "新型电力系统发展蓝皮书",
                "url": "https://www.nea.gov.cn/example/policy_008",
                "source": "国家能源局",
                "topic": topic,
                "publish_date": "2023-12-20",
                "summary": "系统阐述新型电力系统的内涵特征、发展阶段和重点任务，为电力系统转型提供指导。",
                "keywords": ["新型电力系统", "转型", "发展阶段"],
                "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            },
            {
                "title": "电力辅助服务市场建设方案",
                "url": "https://www.nea.gov.cn/example/policy_009",
                "source": "国家能源局",
                "topic": topic,
                "publish_date": "2023-11-15",
                "summary": "建立健全电力辅助服务市场机制，鼓励各类主体提供调频、调峰、备用等辅助服务。",
                "keywords": ["辅助服务", "调频", "备用"],
                "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            },
            {
                "title": "关于完善能源绿色低碳转型体制机制和政策措施的意见",
                "url": "https://www.ndrc.gov.cn/example/policy_010",
                "source": "国家发改委",
                "topic": topic,
                "publish_date": "2023-10-08",
                "summary": "完善能源绿色低碳转型的体制机制，推动电力系统清洁低碳转型，构建新型电力系统。",
                "keywords": ["绿色低碳", "清洁转型", "新型电力系统"],
                "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            },
        ]

        return mock_policies

    def _save_data(self, data: List[Dict[str, Any]], topic: str) -> str:
        """
        保存采集数据到 JSON 文件。

        文件命名格式：policy_YYYYMMDD_HHMMSS.json
        保存到 output/data/ 目录。

        Args:
            data: 采集到的政策列表
            topic: 采集主题

        Returns:
            str: 保存的文件路径
        """
        # 构造文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f"policy_{timestamp}.json"
        file_path = Path(settings.DATA_DIR) / file_name

        # 保存数据
        save_data = {
            "topic": topic,
            "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "count": len(data),
            "data": data,
        }

        success = self.toolbox.write_file(str(file_path), save_data)

        if success:
            logger.info(f"政策数据已保存: {file_path}")
            return str(file_path)
        else:
            logger.error(f"政策数据保存失败: {file_path}")
            return ""
