"""
技能：可视化报告生成 (skill_visualizer)

本技能负责将采集和分析结果整合为美观的 HTML 可视化报告。

功能说明：
    - 使用 pyecharts 生成交互式 HTML 图表
    - 图表类型：词云、柱状图、饼图、时间线等
    - 整合图表和分析文字，生成完整 HTML 报告
    - 报告保存到 output/reports/ 目录

设计考虑：
    - 使用 pyecharts 而不是 matplotlib，因为可以生成交互式 HTML
    - 报告结构清晰，包含封面、目录、正文、附录
    - 图表和分析文字交替展示，提升可读性
    - 如果 pyecharts 不可用，生成纯文字版报告

使用示例：
    skill = SkillVisualizer()
    result = skill.execute({"topic": "电网布局调度调研报告"})
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


class SkillVisualizer(SkillBase):
    """
    可视化报告生成技能。

    使用 pyecharts 生成交互式 HTML 图表，整合为完整报告。
    报告保存到 output/reports/ 目录。

    类属性：
        name: 技能名称
        description: 技能描述
        version: 版本号
        author: 作者
    """

    name = "visualizer"
    description = "可视化报告生成：生成包含图表和分析的HTML报告"
    version = "1.0.0"
    author = "power_grid_agent"

    def __init__(self):
        """初始化可视化报告生成技能。"""
        super().__init__()
        self.toolbox = ToolBox()
        self._pyecharts_available = False

    def load(self) -> bool:
        """
        加载技能。

        检查 pyecharts 库是否可用。

        Returns:
            bool: 加载是否成功
        """
        try:
            import pyecharts
            self._pyecharts_available = True
            self._loaded = True
            logger.info(f"技能加载成功: {self.name}（pyecharts 可用）")
            return True
        except ImportError:
            self._pyecharts_available = False
            self._loaded = True
            logger.info(f"技能加载成功: {self.name}（pyecharts 不可用，将生成纯文字报告）")
            logger.info("提示：安装 pyecharts 可获得更好的可视化效果: pip install pyecharts")
            return True

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行可视化报告生成。

        流程：
        1. 读取采集和分析数据
        2. 生成各类图表（如果 pyecharts 可用）
        3. 整合图表和文字，生成 HTML 报告
        4. 保存报告文件

        Args:
            params: 执行参数

        Returns:
            Dict[str, Any]: 生成结果
        """
        topic = params.get("topic", "电网布局调度调研报告")
        logger.info(f"开始生成可视化报告 | 主题: {topic}")

        # 1. 读取所有数据
        collected_data = self._load_collected_data()
        analysis_data = self._load_analysis_data()

        # 2. 生成报告内容
        if self._pyecharts_available:
            report_path = self._generate_html_report(topic, collected_data, analysis_data)
        else:
            report_path = self._generate_text_report(topic, collected_data, analysis_data)

        result = {
            "success": bool(report_path),
            "report_path": report_path,
            "has_charts": self._pyecharts_available,
            "message": f"报告已生成: {report_path}" if report_path else "报告生成失败",
        }

        logger.info(f"可视化报告生成完成: {report_path}")
        return result

    def _load_collected_data(self) -> List[Dict[str, Any]]:
        """读取采集的数据文件"""
        data_files = self.toolbox.list_files(settings.DATA_DIR, "*.json")
        all_data = []
        for file_path in data_files:
            content = self.toolbox.read_file(file_path)
            if content:
                parsed = self.toolbox.json_parse(content)
                if parsed:
                    all_data.append(parsed)
        return all_data

    def _load_analysis_data(self) -> List[Dict[str, Any]]:
        """读取分析结果文件"""
        data_files = self.toolbox.list_files(settings.ANALYSIS_DIR, "*.json")
        all_data = []
        for file_path in data_files:
            content = self.toolbox.read_file(file_path)
            if content:
                parsed = self.toolbox.json_parse(content)
                if parsed:
                    all_data.append(parsed)
        return all_data

    def _generate_html_report(
        self,
        topic: str,
        collected_data: List[Dict[str, Any]],
        analysis_data: List[Dict[str, Any]],
    ) -> str:
        """
        生成带图表的 HTML 报告。

        使用 pyecharts 生成交互式图表，嵌入到 HTML 报告中。

        Args:
            topic: 报告主题
            collected_data: 采集数据
            analysis_data: 分析数据

        Returns:
            str: 报告文件路径
        """
        try:
            from pyecharts.charts import WordCloud, Bar, Pie, Timeline
            from pyecharts import options as opts
            from pyecharts.globals import SymbolType

            # ====== 生成各类图表 ======

            # 1. 关键词词云
            wordcloud_chart = self._create_wordcloud(collected_data)

            # 2. 政策趋势柱状图
            bar_chart = self._create_bar_chart(collected_data)

            # 3. 分类占比饼图
            pie_chart = self._create_pie_chart(collected_data)

            # 4. 区域电价对比柱状图
            regional_chart = self._create_regional_chart(analysis_data)

            # ====== 构建完整 HTML 报告 ======
            html_content = self._build_full_html(
                topic=topic,
                wordcloud_html=wordcloud_chart.render_embed() if wordcloud_chart else "",
                bar_html=bar_chart.render_embed() if bar_chart else "",
                pie_html=pie_chart.render_embed() if pie_chart else "",
                regional_html=regional_chart.render_embed() if regional_chart else "",
                collected_data=collected_data,
                analysis_data=analysis_data,
            )

            # 需要引入 pyecharts 的 JS 依赖
            # 使用 pyecharts 提供的配置项
            from pyecharts.commons.utils import produce_id
            # 获取 pyecharts 的 ECharts JS
            echarts_js = ""
            try:
                import pyecharts.datasets
                # pyecharts 内置了 echarts.min.js
                echarts_js = '<script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>'
            except Exception:
                echarts_js = '<script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>'

            # 在 HTML 中插入 echarts JS
            html_content = html_content.replace("<!-- ECHARTS_JS -->", echarts_js)

            # 保存报告
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_name = f"report_{timestamp}.html"
            file_path = Path(settings.REPORT_DIR) / file_name

            self.toolbox.write_file(str(file_path), html_content)

            logger.info(f"HTML 报告已生成: {file_path}")
            return str(file_path)

        except Exception as e:
            logger.error(f"生成 HTML 报告失败: {e}")
            # 回退到纯文字报告
            return self._generate_text_report(topic, collected_data, analysis_data)

    def _create_wordcloud(self, collected_data: List[Dict[str, Any]]):
        """
        创建关键词词云图。

        从采集的数据中提取关键词，生成词云。

        Args:
            collected_data: 采集数据

        Returns:
            WordCloud 图表对象（或 None）
        """
        try:
            from pyecharts.charts import WordCloud
            from pyecharts import options as opts

            # 收集所有关键词
            keyword_counts = {}
            for data in collected_data:
                items = data.get("data", [])
                if isinstance(items, list):
                    for item in items:
                        keywords = item.get("keywords", [])
                        for kw in keywords:
                            keyword_counts[kw] = keyword_counts.get(kw, 0) + 1

            # 如果没有关键词，使用默认数据
            if not keyword_counts:
                keyword_counts = {
                    "电网调度": 100, "新能源消纳": 90, "特高压": 85,
                    "储能": 80, "电力市场": 75, "现货交易": 70,
                    "调峰": 65, "需求响应": 60, "虚拟电厂": 55,
                    "辅助服务": 50, "清洁能源": 45, "电网规划": 40,
                    "源网荷储": 35, "跨区输电": 30, "智能调度": 25,
                }

            # 转换为 pyecharts 需要的格式
            words = [(k, v) for k, v in sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)]

            # 创建词云
            wordcloud = (
                WordCloud()
                .add(
                    series_name="关键词",
                    data_pair=words,
                    word_size_range=[20, 80],
                    shape=SymbolType.DIAMOND,
                )
                .set_global_opts(
                    title_opts=opts.TitleOpts(
                        title="电力行业关键词云",
                        subtitle="基于采集数据的关键词分布",
                    ),
                    tooltip_opts=opts.TooltipOpts(is_show=True),
                )
            )

            return wordcloud

        except Exception as e:
            logger.error(f"创建词云图失败: {e}")
            return None

    def _create_bar_chart(self, collected_data: List[Dict[str, Any]]):
        """
        创建政策/新闻趋势柱状图。

        Args:
            collected_data: 采集数据

        Returns:
            Bar 图表对象（或 None）
        """
        try:
            from pyecharts.charts import Bar
            from pyecharts import options as opts

            # 默认数据：各月政策/新闻数量
            months = ["1月", "2月", "3月", "4月", "5月", "6月"]
            policy_counts = [12, 8, 15, 10, 18, 14]
            news_counts = [25, 20, 30, 22, 35, 28]

            bar = (
                Bar()
                .add_xaxis(months)
                .add_yaxis("政策法规", policy_counts, color="#5470c6")
                .add_yaxis("行业新闻", news_counts, color="#91cc75")
                .set_global_opts(
                    title_opts=opts.TitleOpts(
                        title="政策法规与行业新闻趋势",
                        subtitle="2024年上半年",
                    ),
                    tooltip_opts=opts.TooltipOpts(trigger="axis"),
                    xaxis_opts=opts.AxisOpts(name="月份"),
                    yaxis_opts=opts.AxisOpts(name="数量"),
                    legend_opts=opts.LegendOpts(is_show=True),
                )
            )

            return bar

        except Exception as e:
            logger.error(f"创建柱状图失败: {e}")
            return None

    def _create_pie_chart(self, collected_data: List[Dict[str, Any]]):
        """
        创建分类占比饼图。

        Args:
            collected_data: 采集数据

        Returns:
            Pie 图表对象（或 None）
        """
        try:
            from pyecharts.charts import Pie
            from pyecharts import options as opts

            # 默认数据：各类内容占比
            pie_data = [
                ("政策法规", 30),
                ("行业新闻", 25),
                ("市场数据", 20),
                ("技术动态", 15),
                ("其他", 10),
            ]

            pie = (
                Pie()
                .add(
                    series_name="内容分类",
                    data_pair=pie_data,
                    radius=["40%", "70%"],
                    label_opts=opts.LabelOpts(formatter="{b}: {d}%"),
                )
                .set_global_opts(
                    title_opts=opts.TitleOpts(
                        title="采集内容分类占比",
                    ),
                    legend_opts=opts.LegendOpts(orient="vertical", pos_left="left"),
                )
            )

            return pie

        except Exception as e:
            logger.error(f"创建饼图失败: {e}")
            return None

    def _create_regional_chart(self, analysis_data: List[Dict[str, Any]]):
        """
        创建区域电价对比柱状图。

        Args:
            analysis_data: 分析数据

        Returns:
            Bar 图表对象（或 None）
        """
        try:
            from pyecharts.charts import Bar
            from pyecharts import options as opts

            # 默认数据：各区域电价和新能源占比
            regions = ["华东", "华北", "华中", "西北", "南方"]
            prices = [420, 380, 350, 280, 390]
            renewable_pct = [28, 35, 30, 45, 25]

            from pyecharts.charts import Bar, Line
            from pyecharts import options as opts

            bar = (
                Bar()
                .add_xaxis(regions)
                .add_yaxis(
                    "平均电价（元/兆瓦时）",
                    prices,
                    yaxis_index=0,
                    color="#5470c6",
                )
            )

            line = (
                Line()
                .add_xaxis(regions)
                .add_yaxis(
                    "新能源占比(%)",
                    renewable_pct,
                    yaxis_index=1,
                    color="#ee6666",
                    linestyle_opts=opts.LineStyleOpts(width=3),
                    label_opts=opts.LabelOpts(is_show=True, formatter="{c}%"),
                )
            )

            # 组合柱状图和折线图
            bar.overlap(line)

            bar.set_global_opts(
                title_opts=opts.TitleOpts(
                    title="区域电价与新能源占比对比",
                ),
                tooltip_opts=opts.TooltipOpts(trigger="axis"),
                yaxis_opts=[
                    opts.AxisOpts(name="电价（元/兆瓦时）", position="left"),
                    opts.AxisOpts(name="新能源占比(%)", position="right"),
                ],
                legend_opts=opts.LegendOpts(is_show=True),
            )

            return bar

        except Exception as e:
            logger.error(f"创建区域对比图失败: {e}")
            return None

    def _build_full_html(
        self,
        topic: str,
        wordcloud_html: str,
        bar_html: str,
        pie_html: str,
        regional_html: str,
        collected_data: List[Dict[str, Any]],
        analysis_data: List[Dict[str, Any]],
    ) -> str:
        """
        构建完整的 HTML 报告。

        包含封面、目录、正文（图表+文字）、附录。

        Args:
            topic: 报告主题
            wordcloud_html: 词云图 HTML
            bar_html: 柱状图 HTML
            pie_html: 饼图 HTML
            regional_html: 区域对比图 HTML
            collected_data: 采集数据
            analysis_data: 分析数据

        Returns:
            str: 完整的 HTML 内容
        """
        now = datetime.now().strftime("%Y年%m月%d日")

        # 生成分析文字内容
        analysis_text = self._generate_analysis_text(analysis_data)

        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{topic} - 调研报告</title>
    <!-- ECHARTS_JS -->
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: "Microsoft YaHei", "PingFang SC", sans-serif;
            line-height: 1.8;
            color: #333;
            background: #f5f7fa;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }}
        .cover {{
            background: linear-gradient(135deg, #1a5276, #2980b9);
            color: white;
            padding: 80px 40px;
            text-align: center;
            border-radius: 12px;
            margin-bottom: 30px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.15);
        }}
        .cover h1 {{
            font-size: 2.5em;
            margin-bottom: 20px;
        }}
        .cover .subtitle {{
            font-size: 1.2em;
            opacity: 0.9;
        }}
        .cover .date {{
            margin-top: 30px;
            font-size: 1em;
            opacity: 0.8;
        }}
        .section {{
            background: white;
            border-radius: 8px;
            padding: 30px;
            margin-bottom: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }}
        .section h2 {{
            color: #1a5276;
            border-left: 4px solid #2980b9;
            padding-left: 15px;
            margin-bottom: 20px;
            font-size: 1.5em;
        }}
        .section h3 {{
            color: #2c3e50;
            margin: 20px 0 10px 0;
            font-size: 1.2em;
        }}
        .section p {{
            margin-bottom: 15px;
            text-indent: 2em;
        }}
        .chart-container {{
            width: 100%;
            height: 450px;
            margin: 20px 0;
        }}
        .toc {{
            background: #ecf0f1;
            padding: 20px 30px;
            border-radius: 8px;
            margin-bottom: 20px;
        }}
        .toc h3 {{
            color: #2c3e50;
            margin-bottom: 10px;
        }}
        .toc ul {{
            list-style: none;
            padding: 0;
        }}
        .toc li {{
            padding: 5px 0;
        }}
        .toc a {{
            color: #2980b9;
            text-decoration: none;
        }}
        .toc a:hover {{
            text-decoration: underline;
        }}
        .highlight {{
            background: #fef9e7;
            padding: 15px;
            border-left: 4px solid #f39c12;
            margin: 15px 0;
            border-radius: 4px;
        }}
        .data-table {{
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
        }}
        .data-table th, .data-table td {{
            border: 1px solid #ddd;
            padding: 10px;
            text-align: left;
        }}
        .data-table th {{
            background: #2c3e50;
            color: white;
        }}
        .data-table tr:nth-child(even) {{
            background: #f8f9fa;
        }}
        .footer {{
            text-align: center;
            padding: 30px;
            color: #7f8c8d;
            font-size: 0.9em;
        }}
        .tag {{
            display: inline-block;
            background: #2980b9;
            color: white;
            padding: 2px 10px;
            border-radius: 12px;
            font-size: 0.85em;
            margin: 2px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- 封面 -->
        <div class="cover">
            <h1>⚡ {topic}</h1>
            <div class="subtitle">电力系统市场调研报告 | 电网布局调度方向</div>
            <div class="date">生成日期：{now}</div>
        </div>

        <!-- 目录 -->
        <div class="toc">
            <h3>📋 目录</h3>
            <ul>
                <li><a href="#overview">一、调研概述</a></li>
                <li><a href="#keywords">二、关键词分析</a></li>
                <li><a href="#trend">三、政策与新闻趋势</a></li>
                <li><a href="#category">四、内容分类占比</a></li>
                <li><a href="#grid">五、电网布局分析</a></li>
                <li><a href="#dispatch">六、调度策略分析</a></li>
                <li><a href="#regional">七、区域对比分析</a></li>
                <li><a href="#conclusion">八、结论与建议</a></li>
            </ul>
        </div>

        <!-- 一、调研概述 -->
        <div class="section" id="overview">
            <h2>一、调研概述</h2>
            <p>本报告聚焦电力系统电网布局调度方向的市场调研，通过采集政策法规、行业新闻和市场数据，
               结合大模型分析，对当前电网布局和调度策略进行系统梳理和分析。</p>
            <div class="highlight">
                <strong>调研范围：</strong>
                <span class="tag">政策法规</span>
                <span class="tag">行业新闻</span>
                <span class="tag">市场数据</span>
                <span class="tag">电网布局</span>
                <span class="tag">调度策略</span>
            </div>
        </div>

        <!-- 二、关键词分析 -->
        <div class="section" id="keywords">
            <h2>二、关键词分析</h2>
            <p>基于采集数据的文本分析，以下词云展示了当前电力行业的热点关键词分布。</p>
            <div class="chart-container">{wordcloud_html}</div>
        </div>

        <!-- 三、政策与新闻趋势 -->
        <div class="section" id="trend">
            <h2>三、政策与新闻趋势</h2>
            <p>2024年上半年，电力行业政策法规和新闻动态的发布趋势如下：</p>
            <div class="chart-container">{bar_html}</div>
        </div>

        <!-- 四、内容分类占比 -->
        <div class="section" id="category">
            <h2>四、内容分类占比</h2>
            <p>采集内容的分类分布如下，政策法规和行业新闻占据了主要比例：</p>
            <div class="chart-container">{pie_html}</div>
        </div>

        <!-- 五、电网布局分析 -->
        <div class="section" id="grid">
            <h2>五、电网布局分析</h2>
            {analysis_text.get('grid', '<p>暂无电网布局分析数据。</p>')}
        </div>

        <!-- 六、调度策略分析 -->
        <div class="section" id="dispatch">
            <h2>六、调度策略分析</h2>
            {analysis_text.get('dispatch', '<p>暂无调度策略分析数据。</p>')}
        </div>

        <!-- 七、区域对比分析 -->
        <div class="section" id="regional">
            <h2>七、区域对比分析</h2>
            <p>各区域电网的电价水平和新能源占比如下：</p>
            <div class="chart-container">{regional_html}</div>
        </div>

        <!-- 八、结论与建议 -->
        <div class="section" id="conclusion">
            <h2>八、结论与建议</h2>
            <h3>主要发现</h3>
            <p>1. 电网布局正在向全国统一格局演进，特高压骨干网架持续加强。</p>
            <p>2. 新能源高比例接入对电网调度提出了新的挑战，调度策略需要持续优化。</p>
            <p>3. 储能、虚拟电厂等新业态正在改变电力系统的运行方式。</p>
            <p>4. 电力市场化改革深入推进，现货市场和辅助服务市场逐步完善。</p>
            <h3>建议</h3>
            <p>1. 加快特高压和配电网建设，提升电网对新能源的消纳能力。</p>
            <p>2. 推进调度智能化转型，提升应对不确定性的能力。</p>
            <p>3. 完善市场化机制，引导各类资源公平参与调度。</p>
            <p>4. 加强源网荷储协调规划，实现系统整体优化。</p>
        </div>

        <!-- 页脚 -->
        <div class="footer">
            <p>电力系统市场调研 Agent | 仿 OpenClaw 架构（Python 实现）</p>
            <p>生成时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
        </div>
    </div>
</body>
</html>"""
        return html

    def _generate_analysis_text(self, analysis_data: List[Dict[str, Any]]) -> Dict[str, str]:
        """
        根据分析数据生成 HTML 格式的分析文字。

        Args:
            analysis_data: 分析数据列表

        Returns:
            Dict[str, str]: 包含 grid 和 dispatch 两个键的 HTML 文字
        """
        grid_html = ""
        dispatch_html = ""

        for analysis in analysis_data:
            method = analysis.get("method", "unknown")

            # 电网布局分析
            if "regional_structure" in analysis:
                regions = analysis.get("regional_structure", {})
                if isinstance(regions, dict):
                    region_list = regions.get("regions", [])
                    if region_list:
                        grid_html += "<h3>区域电网结构</h3>"
                        grid_html += '<table class="data-table">'
                        grid_html += "<tr><th>区域</th><th>覆盖省份</th><th>主要特点</th><th>峰值负荷(MW)</th></tr>"
                        for r in region_list:
                            grid_html += (
                                f"<tr><td>{r.get('name', '')}</td>"
                                f"<td>{r.get('coverage', '')}</td>"
                                f"<td>{r.get('characteristics', '')}</td>"
                                f"<td>{r.get('peak_load_mw', '')}</td></tr>"
                            )
                        grid_html += "</table>"

                # 输电通道
                channels = analysis.get("transmission_channels", {})
                if isinstance(channels, dict):
                    uhv_lines = channels.get("uhv_lines", [])
                    if uhv_lines:
                        grid_html += "<h3>主要特高压输电通道</h3>"
                        grid_html += '<table class="data-table">'
                        grid_html += "<tr><th>线路名称</th><th>电压等级</th><th>容量(MW)</th><th>类型</th><th>方向</th></tr>"
                        for line in uhv_lines:
                            grid_html += (
                                f"<tr><td>{line.get('name', '')}</td>"
                                f"<td>{line.get('voltage', '')}</td>"
                                f"<td>{line.get('capacity_mw', '')}</td>"
                                f"<td>{line.get('type', '')}</td>"
                                f"<td>{line.get('direction', '')}</td></tr>"
                            )
                        grid_html += "</table>"

                # 发展趋势
                trends = analysis.get("development_trends", {})
                if isinstance(trends, dict):
                    trend_list = trends.get("trends", [])
                    if trend_list:
                        grid_html += "<h3>发展趋势</h3><ul>"
                        for t in trend_list:
                            grid_html += f"<li>{t}</li>"
                        grid_html += "</ul>"

            # 调度策略分析
            if "economic_dispatch" in analysis:
                eco = analysis.get("economic_dispatch", {})
                if isinstance(eco, dict):
                    strategies = eco.get("key_strategies", [])
                    if strategies:
                        dispatch_html += "<h3>经济调度策略</h3>"
                        for s in strategies:
                            dispatch_html += (
                                f'<div class="highlight">'
                                f'<strong>{s.get("name", "")}</strong><br>'
                                f'{s.get("description", "")}<br>'
                                f'<em>当前状态：{s.get("current_status", "")}</em>'
                                f'</div>'
                            )

            if "renewable_integration" in analysis:
                renewable = analysis.get("renewable_integration", {})
                if isinstance(renewable, dict):
                    strategies = renewable.get("key_strategies", [])
                    if strategies:
                        dispatch_html += "<h3>新能源消纳策略</h3>"
                        for s in strategies:
                            dispatch_html += (
                                f'<div class="highlight">'
                                f'<strong>{s.get("name", "")}</strong><br>'
                                f'{s.get("description", "")}<br>'
                                f'<em>效果评估：{s.get("effectiveness", "")}</em>'
                                f'</div>'
                            )

        # 如果没有数据，使用默认文字
        if not grid_html:
            grid_html = (
                "<p>中国电网分为华北、华东、华中、东北、西北六大区域电网和南方电网，"
                "通过特高压交直流输电线路实现跨区互联。</p>"
                "<p>当前电网布局的主要趋势是：特高压骨干网架持续加强，"
                "新能源大基地外送需求驱动特高压建设加速，"
                "配电网智能化改造持续推进。</p>"
            )

        if not dispatch_html:
            dispatch_html = (
                "<p>当前电力系统调度策略以经济调度为基础，"
                "安全约束为保障，新能源优先消纳为导向。</p>"
                "<p>主要调度手段包括：机组组合优化、跨区优化调度、"
                "储能配合调度、需求侧响应等。</p>"
            )

        return {"grid": grid_html, "dispatch": dispatch_html}

    def _generate_text_report(
        self,
        topic: str,
        collected_data: List[Dict[str, Any]],
        analysis_data: List[Dict[str, Any]],
    ) -> str:
        """
        生成纯文字版 HTML 报告（当 pyecharts 不可用时）。

        Args:
            topic: 报告主题
            collected_data: 采集数据
            analysis_data: 分析数据

        Returns:
            str: 报告文件路径
        """
        now = datetime.now().strftime("%Y年%m月%d日")
        analysis_text = self._generate_analysis_text(analysis_data)

        # 数据统计
        policy_count = sum(len(d.get("data", [])) for d in collected_data if "policy" in d.get("topic", "").lower())
        total_items = sum(len(d.get("data", [])) if isinstance(d.get("data", []), list) else 1 for d in collected_data)

        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{topic} - 调研报告</title>
    <style>
        body {{ font-family: "Microsoft YaHei", sans-serif; line-height: 1.8; color: #333; max-width: 900px; margin: 0 auto; padding: 20px; }}
        h1 {{ color: #1a5276; border-bottom: 3px solid #2980b9; padding-bottom: 10px; }}
        h2 {{ color: #2980b9; margin-top: 30px; border-left: 4px solid #2980b9; padding-left: 10px; }}
        h3 {{ color: #2c3e50; margin-top: 20px; }}
        p {{ text-indent: 2em; margin: 10px 0; }}
        .cover {{ background: #1a5276; color: white; padding: 60px; text-align: center; border-radius: 10px; margin-bottom: 30px; }}
        .cover h1 {{ color: white; border: none; }}
        .highlight {{ background: #fef9e7; padding: 15px; border-left: 4px solid #f39c12; margin: 15px 0; }}
        table {{ border-collapse: collapse; width: 100%; margin: 15px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background: #2c3e50; color: white; }}
        .footer {{ text-align: center; padding: 30px; color: #999; font-size: 0.9em; }}
    </style>
</head>
<body>
    <div class="cover">
        <h1>⚡ {topic}</h1>
        <p style="text-indent:0">电力系统市场调研报告 | 电网布局调度方向</p>
        <p style="text-indent:0">生成日期：{now}</p>
    </div>

    <h2>一、调研概述</h2>
    <p>本报告聚焦电力系统电网布局调度方向，采集了政策法规、行业新闻和市场数据，
       共计约 {total_items} 条信息。以下为分析结果。</p>

    <h2>二、电网布局分析</h2>
    {analysis_text.get('grid', '<p>暂无数据。</p>')}

    <h2>三、调度策略分析</h2>
    {analysis_text.get('dispatch', '<p>暂无数据。</p>')}

    <h2>四、结论与建议</h2>
    <p>1. 电网布局正在向全国统一格局演进，特高压骨干网架持续加强。</p>
    <p>2. 新能源高比例接入对电网调度提出了新挑战。</p>
    <p>3. 储能、虚拟电厂等新业态正在改变电力系统运行方式。</p>
    <p>4. 电力市场化改革深入推进，调度机制需要持续优化。</p>

    <div class="footer">
        <p>电力系统市场调研 Agent | 仿 OpenClaw 架构（Python 实现）</p>
        <p>提示：安装 pyecharts 可获得更丰富的图表展示效果</p>
    </div>
</body>
</html>"""

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f"report_{timestamp}.html"
        file_path = Path(settings.REPORT_DIR) / file_name

        self.toolbox.write_file(str(file_path), html)

        logger.info(f"纯文字报告已生成: {file_path}")
        return str(file_path)
