"""
全局配置模块 (settings)

本模块负责从环境变量和 .env 文件中加载所有配置项。
使用 python-dotenv 库实现 .env 文件的自动加载。

设计思路：
    - 所有敏感信息（API Key 等）统一从 .env 文件读取，不硬编码到代码中
    - 每个配置项都有默认值，即使没有 .env 文件也能运行（但功能受限）
    - 使用 dataclass 管理配置，类型安全，方便 IDE 自动补全
    - 全局单例模式（settings），避免重复加载

对应 OpenClaw 概念：
    - OpenClaw 中也有类似的配置系统，管理平台连接、模型参数等
    - 我们用 Python dataclass 替代了 OpenClaw 的 YAML 配置

使用示例：
    from config.settings import settings
    print(settings.QWEN_API_KEY)
    print(settings.OUTPUT_DIR)
"""

import os
import sys
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

# 尝试导入 python-dotenv，如果不存在则给出友好提示
try:
    from dotenv import load_dotenv
except ImportError:
    print("【警告】python-dotenv 未安装，无法加载 .env 文件。请执行: pip install python-dotenv")
    # 提供一个空的 load_dotenv 函数，避免后续代码报错
    def load_dotenv(*args, **kwargs):
        pass


logger = logging.getLogger(__name__)


def _find_project_root() -> Path:
    """
    查找项目根目录。

    从当前文件向上查找，直到找到包含 main.py 的目录。
    这样无论从哪个目录运行脚本，都能正确找到 .env 文件。

    Returns:
        Path: 项目根目录的绝对路径
    """
    current = Path(__file__).resolve().parent
    # 最多向上查找 5 层，避免无限循环
    for _ in range(5):
        if (current / "main.py").exists():
            return current
        current = current.parent
    # 如果找不到，就使用 config 目录的父目录
    return Path(__file__).resolve().parent.parent


def _load_env_file():
    """
    加载 .env 环境变量文件。

    优先从项目根目录加载 .env 文件。
    如果 .env 不存在，会记录警告但不中断运行。
    """
    project_root = _find_project_root()
    env_path = project_root / ".env"

    if env_path.exists():
        load_dotenv(env_path)
        logger.info(f"已加载环境变量文件: {env_path}")
    else:
        logger.warning(f".env 文件不存在: {env_path}")
        logger.warning("请复制 .env.example 为 .env 并填写配置项")


@dataclass
class Settings:
    """
    全局配置类。

    所有配置项都从这里读取。每个属性都有详细的中文注释说明用途。

    属性说明：
        --- 千问大模型配置 ---
        QWEN_API_BASE: 讯飞 MaaS 平台的 API 地址（OpenAI 兼容格式）
        QWEN_API_KEY:  讯飞 MaaS 平台的 API 密钥（从 .env 读取，绝不硬编码）
        QWEN_MODEL_NAME: 模型名称（如 xop35qwen2b）

        --- 模型参数 ---
        TEMPERATURE: 生成温度，0-1 之间。越低越确定，越高越随机。
                     对于 Qwen3.5-2B 小模型，建议 0.3，保证输出稳定
        MAX_TOKENS: 单次生成的最大 token 数。
                    小模型建议不超过 2048，避免输出质量下降
        REQUEST_TIMEOUT: HTTP 请求超时时间（秒）
        MAX_RETRIES: 请求失败时的最大重试次数

        --- 输出目录 ---
        OUTPUT_DIR: 输出根目录
        MEMORY_DIR: 记忆文件存储目录
        DATA_DIR: 采集数据存储目录
        ANALYSIS_DIR: 分析结果存储目录
        REPORT_DIR: 可视化报告存储目录

        --- 日志 ---
        LOG_LEVEL: 日志级别（DEBUG/INFO/WARNING/ERROR）

    使用示例：
        settings = Settings()
        print(settings.QWEN_API_BASE)
        print(settings.TEMPERATURE)
    """

    # ====== 千问大模型配置 ======
    # 讯飞 MaaS 平台的 API 地址（OpenAI 兼容格式）
    # 对应 .env 中的 QWEN_API_BASE
    # 注意：使用 `or` 运算符处理环境变量为空字符串的情况
    QWEN_API_BASE: str = field(default_factory=lambda: os.getenv(
        "QWEN_API_BASE", ""
    ) or "https://maas-api.cn-huabei-1.xf-yun.com/v2")

    # 讯飞 MaaS 平台的 API 密钥
    # ⚠️ 重要：不要硬编码密钥！必须从 .env 文件读取
    QWEN_API_KEY: str = field(default_factory=lambda: os.getenv(
        "QWEN_API_KEY", ""
    ) or "")

    # 模型名称（在讯飞 MaaS 平台上的模型标识）
    QWEN_MODEL_NAME: str = field(default_factory=lambda: os.getenv(
        "QWEN_MODEL_NAME", ""
    ) or "xop35qwen2b")

    # ====== 模型参数 ======
    # 生成温度（0-1 之间）
    # 对于 Qwen3.5-2B 小模型，建议使用较低的值（0.3），
    # 因为小模型在高温度下容易产生不稳定的输出
    TEMPERATURE: float = field(default_factory=lambda: float(os.getenv(
        "TEMPERATURE", ""
    ) or "0.3"))

    # 单次生成的最大 token 数
    # 小模型建议不超过 2048，过长的输出质量会下降
    MAX_TOKENS: int = field(default_factory=lambda: int(os.getenv(
        "MAX_TOKENS", ""
    ) or "2048"))

    # HTTP 请求超时时间（秒）
    # 考虑到小模型推理可能较慢，设置较大的超时值
    REQUEST_TIMEOUT: int = field(default_factory=lambda: int(os.getenv(
        "REQUEST_TIMEOUT", ""
    ) or "60"))

    # 请求失败时的最大重试次数
    # 网络不稳定时自动重试，提高可靠性
    MAX_RETRIES: int = field(default_factory=lambda: int(os.getenv(
        "MAX_RETRIES", ""
    ) or "3"))

    # ====== 输出目录 ======
    # 项目根目录，所有相对路径的基准
    _PROJECT_ROOT: Path = field(default_factory=_find_project_root, repr=False)

    # 输出根目录
    OUTPUT_DIR: str = field(default_factory=lambda: os.getenv(
        "OUTPUT_DIR", ""
    ) or "output")

    # 记忆文件存储目录
    MEMORY_DIR: str = field(default_factory=lambda: os.getenv(
        "MEMORY_DIR", ""
    ) or "output/memory")

    # 采集数据存储目录
    DATA_DIR: str = field(default_factory=lambda: os.getenv(
        "DATA_DIR", ""
    ) or "output/data")

    # 分析结果存储目录
    ANALYSIS_DIR: str = field(default_factory=lambda: os.getenv(
        "ANALYSIS_DIR", ""
    ) or "output/analysis")

    # 可视化报告存储目录
    REPORT_DIR: str = field(default_factory=lambda: os.getenv(
        "REPORT_DIR", ""
    ) or "output/reports")

    # ====== 日志配置 ======
    # 日志级别：DEBUG（最详细）/ INFO（常规）/ WARNING（警告）/ ERROR（仅错误）
    LOG_LEVEL: str = field(default_factory=lambda: os.getenv(
        "LOG_LEVEL", ""
    ) or "INFO")

    def __post_init__(self):
        """
        初始化后的处理。

        主要完成以下工作：
        1. 加载 .env 文件
        2. 重新读取环境变量（因为 .env 可能刚被加载）
        3. 创建必要的输出目录
        4. 验证关键配置项
        """
        # 1. 加载 .env 文件
        _load_env_file()

        # 2. 重新读取环境变量（.env 文件刚被加载，需要刷新）
        # 使用 `or` 运算符处理环境变量为空字符串的情况
        # 这是因为 .env 文件中可能存在空值，如 MAX_TOKENS=
        self.QWEN_API_BASE = os.getenv("QWEN_API_BASE") or self.QWEN_API_BASE
        self.QWEN_API_KEY = os.getenv("QWEN_API_KEY") or self.QWEN_API_KEY
        self.QWEN_MODEL_NAME = os.getenv("QWEN_MODEL_NAME") or self.QWEN_MODEL_NAME
        # 数值类型需要安全转换：空值时使用当前值（默认值）
        _temp = os.getenv("TEMPERATURE")
        self.TEMPERATURE = float(_temp) if _temp else self.TEMPERATURE
        _mt = os.getenv("MAX_TOKENS")
        self.MAX_TOKENS = int(_mt) if _mt else self.MAX_TOKENS
        _rt = os.getenv("REQUEST_TIMEOUT")
        self.REQUEST_TIMEOUT = int(_rt) if _rt else self.REQUEST_TIMEOUT
        _mr = os.getenv("MAX_RETRIES")
        self.MAX_RETRIES = int(_mr) if _mr else self.MAX_RETRIES
        self.OUTPUT_DIR = os.getenv("OUTPUT_DIR") or self.OUTPUT_DIR
        self.MEMORY_DIR = os.getenv("MEMORY_DIR") or self.MEMORY_DIR
        self.DATA_DIR = os.getenv("DATA_DIR") or self.DATA_DIR
        self.ANALYSIS_DIR = os.getenv("ANALYSIS_DIR") or self.ANALYSIS_DIR
        self.REPORT_DIR = os.getenv("REPORT_DIR") or self.REPORT_DIR
        self.LOG_LEVEL = os.getenv("LOG_LEVEL") or self.LOG_LEVEL

        # 3. 创建必要的输出目录（如果不存在则自动创建）
        self._ensure_directories()

        # 4. 验证关键配置项
        self._validate()

    def _ensure_directories(self) -> None:
        """
        确保所有输出目录存在。

        使用 pathlib.Path 处理路径，兼容 Windows 和 Linux。
        parents=True 表示自动创建父目录。
        exist_ok=True 表示目录已存在时不报错。
        """
        for dir_path in [self.OUTPUT_DIR, self.MEMORY_DIR, self.DATA_DIR,
                         self.ANALYSIS_DIR, self.REPORT_DIR]:
            Path(dir_path).mkdir(parents=True, exist_ok=True)
            logger.debug(f"目录已就绪: {dir_path}")

    def _validate(self) -> None:
        """
        验证关键配置项是否有效。

        如果 API Key 为空，记录警告但不中断运行。
        因为用户可能只是先看项目结构，还没配置 API Key。
        """
        if not self.QWEN_API_KEY or self.QWEN_API_KEY == "your_api_key_here":
            logger.warning("=" * 60)
            logger.warning("⚠️  QWEN_API_KEY 未配置！")
            logger.warning("请复制 .env.example 为 .env 并填写您的 API Key")
            logger.warning("=" * 60)
        else:
            logger.info("API Key 已配置 ✓")

        # 验证温度范围
        if not (0.0 <= self.TEMPERATURE <= 1.0):
            logger.warning(f"TEMPERATURE={self.TEMPERATURE} 不在有效范围 [0, 1]，已自动修正为 0.3")
            self.TEMPERATURE = 0.3

        logger.info(f"配置加载完成 | 模型: {self.QWEN_MODEL_NAME} | 温度: {self.TEMPERATURE}")


# ====== 全局单例 ======
# 整个项目中通过 from config.settings import settings 使用
# 这样确保配置只加载一次，且全局一致
settings = Settings()
