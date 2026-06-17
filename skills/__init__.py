"""
技能模块 (skills)

本模块包含电力系统市场调研的所有可插拔技能。
每个 Skill 是独立模块，专注于一个特定任务。

技能分类：
    采集类：
        - collector_policy: 政策法规采集
        - collector_news: 行业新闻采集
        - collector_market: 市场数据采集

    分析类：
        - analyzer_grid: 电网布局分析
        - analyzer_dispatch: 调度策略分析

    可视化类：
        - visualizer: 可视化报告生成

扩展指南：
    要添加新 Skill，只需在 skills/ 目录下创建新文件，
    继承 SkillBase 类，实现 execute() 方法，
    系统会自动发现和注册。
"""

__all__ = []
