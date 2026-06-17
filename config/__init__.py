"""
配置模块 (config)

本模块负责加载和管理项目全局配置。
所有敏感信息（如 API Key）从 .env 文件读取，绝不硬编码。

使用方式：
    from config.settings import settings
    api_key = settings.QWEN_API_KEY
"""

from config.settings import settings

__all__ = ["settings"]
