"""
工具系统模块 (toolbox)

本模块封装了 Agent 可调用的常用工具方法，包括文件操作、网络请求、命令执行等。

设计思路：
    - 每个工具方法都是独立的，可被任何 Agent 调用
    - 所有方法都有安全检查和异常处理，不会导致程序崩溃
    - run_command 方法有白名单机制，防止执行危险命令
    - http_get/http_post 方法有超时和重试机制

为什么需要工具系统？
    - Agent 需要与外部世界交互（读文件、访问网页、执行命令）
    - 统一封装可以确保安全性和一致性
    - 方便后续扩展新的工具

对应 OpenClaw 概念：
    - OpenClaw 中 Tool System 提供可调用的工具集
    - 我们用 ToolBox 类实现了类似功能，用 Python 方法替代了 OpenClaw 的工具函数

使用示例：
    toolbox = ToolBox()
    content = toolbox.read_file("output/data/policies.json")
    html = toolbox.http_get("https://example.com")
    toolbox.write_file("output/data/test.json", {"key": "value"})
"""

import json
import logging
import subprocess
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

# 尝试导入 requests 库
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    logger_temp = logging.getLogger(__name__)
    logger_temp.warning("requests 库未安装，网络请求功能不可用。请执行: pip install requests")

from config.settings import settings

logger = logging.getLogger(__name__)


class ToolBox:
    """
    工具系统类。

    封装了 Agent 可调用的常用工具方法。
    所有方法都有安全检查和异常处理，不会导致程序崩溃。

    属性：
        allowed_commands: 允许执行的命令白名单（用于 run_command 安全限制）

    使用示例：
        toolbox = ToolBox()
        # 读取文件
        content = toolbox.read_file("output/data/policies.json")
        # 写入文件
        toolbox.write_file("output/data/test.txt", "Hello, World!")
        # HTTP 请求
        html = toolbox.http_get("https://example.com")
    """

    # 允许执行的系统命令白名单
    # 为什么需要白名单？防止 Agent 执行危险命令（如 rm -rf /）
    # 只有白名单中的命令前缀才允许执行
    ALLOWED_COMMANDS = [
        "python",       # Python 脚本
        "pip",          # 包管理
        "dir",          # 查看目录（Windows）
        "ls",           # 查看目录（Linux）
        "echo",         # 输出文本
        "type",         # 查看文件内容（Windows）
        "cat",          # 查看文件内容（Linux）
    ]

    def __init__(self):
        """初始化工具系统。"""
        logger.info("工具系统初始化完成")

    def read_file(self, file_path: str, encoding: str = "utf-8") -> Optional[str]:
        """
        读取文件内容。

        支持文本文件读取，自动处理编码问题。
        对于 JSON 文件，建议使用 json_parse 方法配合使用。

        Args:
            file_path: 文件路径（相对路径或绝对路径均可）
            encoding: 文件编码，默认 utf-8

        Returns:
            Optional[str]: 文件内容字符串，失败返回 None

        使用示例：
            content = toolbox.read_file("output/data/policies.json")
            if content:
                data = json.loads(content)
        """
        try:
            path = Path(file_path)

            # 检查文件是否存在
            if not path.exists():
                logger.warning(f"文件不存在: {file_path}")
                return None

            # 检查是否是文件（而不是目录）
            if not path.is_file():
                logger.warning(f"路径不是文件: {file_path}")
                return None

            # 读取文件内容
            with open(path, "r", encoding=encoding) as f:
                content = f.read()

            logger.debug(f"文件读取成功: {file_path} | 大小: {len(content)} 字符")
            return content

        except UnicodeDecodeError:
            # 编码错误，尝试其他编码
            try:
                with open(path, "r", encoding="gbk") as f:
                    content = f.read()
                logger.debug(f"文件读取成功（GBK 编码）: {file_path}")
                return content
            except Exception as e2:
                logger.error(f"文件编码错误: {file_path} | 尝试 UTF-8 和 GBK 均失败: {e2}")
                return None

        except Exception as e:
            logger.error(f"读取文件失败: {file_path} | 错误: {e}")
            return None

    def write_file(
        self,
        file_path: str,
        content: Any,
        encoding: str = "utf-8",
        ensure_dir: bool = True,
    ) -> bool:
        """
        写入文件内容。

        支持写入字符串、字典、列表等类型。
        字典和列表会自动转为 JSON 格式写入。

        Args:
            file_path: 文件路径
            content: 要写入的内容。字符串直接写入，字典/列表转 JSON
            encoding: 文件编码，默认 utf-8
            ensure_dir: 是否自动创建父目录，默认 True

        Returns:
            bool: 写入是否成功

        使用示例：
            toolbox.write_file("output/data/test.txt", "Hello, World!")
            toolbox.write_file("output/data/test.json", {"key": "value"})
        """
        try:
            path = Path(file_path)

            # 自动创建父目录
            if ensure_dir:
                path.parent.mkdir(parents=True, exist_ok=True)

            # 根据内容类型决定写入方式
            if isinstance(content, (dict, list)):
                # 字典/列表转 JSON 格式写入
                text = json.dumps(content, ensure_ascii=False, indent=2)
            else:
                # 其他类型直接转字符串
                text = str(content)

            # 写入文件
            with open(path, "w", encoding=encoding) as f:
                f.write(text)

            logger.debug(f"文件写入成功: {file_path} | 大小: {len(text)} 字符")
            return True

        except Exception as e:
            logger.error(f"写入文件失败: {file_path} | 错误: {e}")
            return False

    def http_get(
        self,
        url: str,
        timeout: int = 30,
        headers: Optional[Dict[str, str]] = None,
    ) -> Optional[str]:
        """
        发送 HTTP GET 请求。

        用于采集网页内容，如政策法规、行业新闻等。
        内置超时和重试机制。

        Args:
            url: 请求的 URL
            timeout: 超时时间（秒），默认 30 秒
            headers: 自定义请求头，默认使用浏览器 User-Agent

        Returns:
            Optional[str]: 响应文本，失败返回 None

        使用示例：
            html = toolbox.http_get("https://www.nea.gov.cn")
            if html:
                print(f"页面大小: {len(html)} 字符")
        """
        if not REQUESTS_AVAILABLE:
            logger.error("requests 库未安装，无法发送 HTTP 请求")
            return None

        # 默认使用浏览器 User-Agent，避免被网站拒绝
        default_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }

        # 合并自定义请求头
        if headers:
            default_headers.update(headers)

        try:
            response = requests.get(
                url,
                headers=default_headers,
                timeout=timeout,
                # 允许重定向
                allow_redirects=True,
            )
            response.raise_for_status()  # 检查 HTTP 状态码

            # 尝试自动检测编码
            response.encoding = response.apparent_encoding or "utf-8"

            logger.info(f"HTTP GET 成功: {url} | 状态码: {response.status_code} | 大小: {len(response.text)} 字符")
            return response.text

        except requests.Timeout:
            logger.error(f"HTTP 请求超时: {url} | 超时: {timeout} 秒")
            return None
        except requests.ConnectionError:
            logger.error(f"HTTP 连接错误: {url}")
            return None
        except requests.HTTPError as e:
            logger.error(f"HTTP 状态码错误: {url} | 状态码: {e.response.status_code}")
            return None
        except Exception as e:
            logger.error(f"HTTP GET 失败: {url} | 错误: {e}")
            return None

    def http_post(
        self,
        url: str,
        data: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        timeout: int = 30,
        headers: Optional[Dict[str, str]] = None,
    ) -> Optional[str]:
        """
        发送 HTTP POST 请求。

        用于提交表单数据或 API 请求。

        Args:
            url: 请求的 URL
            data: 表单数据（字典）
            json_data: JSON 数据（字典）
            timeout: 超时时间（秒）
            headers: 自定义请求头

        Returns:
            Optional[str]: 响应文本，失败返回 None

        使用示例：
            result = toolbox.http_post(
                "https://api.example.com/data",
                json_data={"query": "电力政策"}
            )
        """
        if not REQUESTS_AVAILABLE:
            logger.error("requests 库未安装，无法发送 HTTP 请求")
            return None

        try:
            response = requests.post(
                url,
                data=data,
                json=json_data,
                headers=headers,
                timeout=timeout,
            )
            response.raise_for_status()
            response.encoding = response.apparent_encoding or "utf-8"

            logger.info(f"HTTP POST 成功: {url} | 状态码: {response.status_code}")
            return response.text

        except Exception as e:
            logger.error(f"HTTP POST 失败: {url} | 错误: {e}")
            return None

    def run_command(
        self,
        cmd: str,
        timeout: int = 60,
        cwd: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        执行系统命令。

        出于安全考虑，只有白名单中的命令才允许执行。
        运行结果以字典形式返回，包含 stdout、stderr、returncode。

        Args:
            cmd: 要执行的命令字符串
            timeout: 命令超时时间（秒），默认 60 秒
            cwd: 工作目录，默认为当前目录

        Returns:
            Dict[str, Any]: 执行结果，格式为：
                {
                    "success": bool,      # 是否执行成功
                    "stdout": str,        # 标准输出
                    "stderr": str,        # 标准错误
                    "returncode": int,    # 返回码
                }

        使用示例：
            result = toolbox.run_command("dir")
            if result["success"]:
                print(result["stdout"])
        """
        # 安全检查：命令是否在白名单中
        cmd_parts = cmd.strip().split()
        if not cmd_parts:
            return {"success": False, "stdout": "", "stderr": "空命令", "returncode": -1}

        # 检查命令前缀是否在白名单中
        command_name = Path(cmd_parts[0]).stem.lower()  # 取命令名（去掉路径）
        is_allowed = any(
            command_name.startswith(allowed) or command_name == allowed
            for allowed in self.ALLOWED_COMMANDS
        )

        if not is_allowed:
            logger.warning(f"命令不在白名单中，已拒绝执行: {cmd}")
            return {
                "success": False,
                "stdout": "",
                "stderr": f"命令 '{command_name}' 不在允许列表中。允许的命令: {self.ALLOWED_COMMANDS}",
                "returncode": -1,
            }

        try:
            # 使用 subprocess 执行命令
            # shell=True 在 Windows 上需要，但注意安全风险
            # 我们通过白名单机制限制可执行的命令
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd,
                encoding="utf-8",
                errors="replace",  # 编码错误时替换字符，不抛异常
            )

            success = result.returncode == 0

            if success:
                logger.info(f"命令执行成功: {cmd} | 返回码: {result.returncode}")
            else:
                logger.warning(f"命令执行失败: {cmd} | 返回码: {result.returncode}")

            return {
                "success": success,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }

        except subprocess.TimeoutExpired:
            logger.error(f"命令执行超时: {cmd} | 超时: {timeout} 秒")
            return {
                "success": False,
                "stdout": "",
                "stderr": f"命令执行超时（{timeout}秒）",
                "returncode": -1,
            }
        except Exception as e:
            logger.error(f"命令执行异常: {cmd} | 错误: {e}")
            return {
                "success": False,
                "stdout": "",
                "stderr": str(e),
                "returncode": -1,
            }

    def search_web(self, query: str, max_results: int = 5) -> List[Dict[str, str]]:
        """
        网络搜索（简化版）。

        注意：这是一个简化实现，直接返回搜索关键词和提示信息。
        实际的网络搜索需要接入搜索 API（如百度搜索 API、必应搜索 API 等）。
        在本项目中，数据采集主要通过各 Skill 直接访问目标网站实现。

        Args:
            query: 搜索关键词
            max_results: 最大结果数（本简化版不使用）

        Returns:
            List[Dict[str, str]]: 搜索结果列表

        使用示例：
            results = toolbox.search_web("电力政策法规")
            for r in results:
                print(r["title"], r["url"])
        """
        # 简化实现：返回提示信息
        # 实际项目中应该接入搜索 API
        logger.info(f"网络搜索请求: {query}（简化版，返回预设结果）")

        # 预设一些常用的电力行业网站
        preset_results = [
            {
                "title": "国家能源局",
                "url": "https://www.nea.gov.cn",
                "description": "国家能源局官方网站，发布电力行业政策法规",
            },
            {
                "title": "北极星电力网",
                "url": "https://power.bjx.com.cn",
                "description": "电力行业综合信息平台，提供新闻和数据",
            },
            {
                "title": "中国电力企业联合会",
                "url": "https://www.cec.org.cn",
                "description": "中电联官网，发布行业标准和统计数据",
            },
            {
                "title": "国家发改委",
                "url": "https://www.ndrc.gov.cn",
                "description": "国家发改委官网，发布能源领域宏观政策",
            },
        ]

        # 根据关键词简单过滤
        filtered = []
        query_lower = query.lower()
        for result in preset_results:
            if (query_lower in result["title"].lower() or
                query_lower in result["description"].lower()):
                filtered.append(result)

        # 如果没有匹配的，返回全部
        return filtered[:max_results] if filtered else preset_results[:max_results]

    def json_parse(self, text: str) -> Optional[Any]:
        """
        安全解析 JSON 文本。

        提供多重容错机制：
        1. 直接解析
        2. 去除首尾空白后解析
        3. 提取第一个 { ... } 区间后解析

        Args:
            text: 要解析的 JSON 文本

        Returns:
            Optional[Any]: 解析结果（字典/列表/原始值），失败返回 None

        使用示例：
            data = toolbox.json_parse('{"name": "电网调度", "level": 3}')
            # data = {"name": "电网调度", "level": 3}
        """
        if not text or not text.strip():
            return None

        # 方法 1：直接解析
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 方法 2：去除首尾空白后解析
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            pass

        # 方法 3：提取第一个 JSON 对象区间
        import re
        # 匹配 { ... } 格式
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        # 匹配 [ ... ] 格式
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        logger.warning(f"JSON 解析失败 | 文本前 200 字: {text[:200]}")
        return None

    def append_file(self, file_path: str, content: str, encoding: str = "utf-8") -> bool:
        """
        追加内容到文件末尾。

        Args:
            file_path: 文件路径
            content: 要追加的内容
            encoding: 文件编码

        Returns:
            bool: 是否追加成功
        """
        try:
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)

            with open(path, "a", encoding=encoding) as f:
                f.write(content)

            logger.debug(f"文件追加成功: {file_path}")
            return True

        except Exception as e:
            logger.error(f"文件追加失败: {file_path} | 错误: {e}")
            return False

    def file_exists(self, file_path: str) -> bool:
        """
        检查文件是否存在。

        Args:
            file_path: 文件路径

        Returns:
            bool: 文件是否存在
        """
        return Path(file_path).exists()

    def list_files(self, dir_path: str, pattern: str = "*") -> List[str]:
        """
        列出目录下的文件。

        Args:
            dir_path: 目录路径
            pattern: 文件匹配模式，如 "*.json"，默认 "*"（所有文件）

        Returns:
            List[str]: 文件路径列表

        使用示例：
            files = toolbox.list_files("output/data", "*.json")
        """
        try:
            path = Path(dir_path)
            if not path.exists():
                return []
            return [str(f) for f in path.glob(pattern) if f.is_file()]
        except Exception as e:
            logger.error(f"列出文件失败: {dir_path} | 错误: {e}")
            return []

    def __repr__(self) -> str:
        return "ToolBox(工具系统)"
