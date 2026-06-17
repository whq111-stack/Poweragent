"""
记忆系统模块 (memory)

本模块实现了按日期归档的持久化记忆系统，支持存储、搜索和检索。

设计思路：
    - 记忆按日期存储为 JSON 文件（output/memory/YYYY-MM-DD.json）
    - 每条记忆包含：timestamp（时间戳）、type（类型）、content（内容）、tags（标签）
    - 支持关键词搜索和最近 N 条检索
    - 当记忆过长时，可调用 LLM 进行压缩摘要

为什么需要记忆系统？
    - Agent 需要记住之前的交互结果，避免重复工作
    - 跨会话的持久化存储，下次启动仍可访问
    - 支持搜索，快速定位相关信息

对应 OpenClaw 概念：
    - OpenClaw 中 Memory System 负责长期记忆管理
    - 我们用简单的文件系统实现了类似功能，不依赖数据库

使用示例：
    memory = Memory()
    memory.store("政策采集", {"policies": [...]}, tags=["政策", "采集"])
    results = memory.search("政策")
    recent = memory.get_recent(5)
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

from config.settings import settings

logger = logging.getLogger(__name__)


class Memory:
    """
    记忆系统类。

    按日期存储记忆到 JSON 文件，支持搜索和检索。
    记忆是 Agent 的长期知识库，用于存储采集的数据、分析结果等。

    属性：
        memory_dir: 记忆文件存储目录
        llm_client: LLM 客户端（可选，用于压缩摘要）

    使用示例：
        memory = Memory()
        # 存储记忆
        memory.store("电网政策", {"source": "能源局", "count": 10}, tags=["政策"])
        # 搜索记忆
        results = memory.search("电网")
        # 获取最近 5 条
        recent = memory.get_recent(5)
    """

    def __init__(self, memory_dir: Optional[str] = None, llm_client=None):
        """
        初始化记忆系统。

        Args:
            memory_dir: 记忆文件存储目录，默认从 settings 读取
            llm_client: LLM 客户端实例（可选），用于压缩摘要
                       如果不提供，summarize() 功能将不可用
        """
        self.memory_dir = Path(memory_dir or settings.MEMORY_DIR)
        self.llm_client = llm_client

        # 确保记忆目录存在
        self.memory_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"记忆系统初始化完成 | 目录: {self.memory_dir}")

    def _get_today_file(self) -> Path:
        """
        获取今天的记忆文件路径。

        文件名格式：YYYY-MM-DD.json
        每天一个文件，方便按日期查找和管理。

        Returns:
            Path: 今天的记忆文件路径
        """
        today = datetime.now().strftime("%Y-%m-%d")
        return self.memory_dir / f"{today}.json"

    def _read_memory_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """
        读取一个记忆文件的内容。

        Args:
            file_path: 记忆文件路径

        Returns:
            List[Dict[str, Any]]: 记忆列表，每条记忆是一个字典
        """
        if not file_path.exists():
            return []

        try:
            # 使用 utf-8 编码读取，避免 Windows 中文乱码
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                # 确保返回的是列表
                if isinstance(data, list):
                    return data
                else:
                    logger.warning(f"记忆文件格式异常（期望列表）: {file_path}")
                    return []
        except json.JSONDecodeError as e:
            logger.error(f"记忆文件 JSON 解析失败: {file_path} | 错误: {e}")
            return []
        except Exception as e:
            logger.error(f"读取记忆文件失败: {file_path} | 错误: {e}")
            return []

    def _write_memory_file(self, file_path: Path, memories: List[Dict[str, Any]]) -> None:
        """
        写入记忆文件。

        使用 utf-8 编码和缩进格式写入，方便人工查看和调试。

        Args:
            file_path: 记忆文件路径
            memories: 记忆列表
        """
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                # ensure_ascii=False 保留中文字符
                # indent=2 使用缩进格式，方便阅读
                json.dump(memories, f, ensure_ascii=False, indent=2)
            logger.debug(f"记忆文件已写入: {file_path} | 条数: {len(memories)}")
        except Exception as e:
            logger.error(f"写入记忆文件失败: {file_path} | 错误: {e}")

    def store(
        self,
        key: str,
        content: Any,
        memory_type: str = "general",
        tags: Optional[List[str]] = None,
    ) -> bool:
        """
        存储一条记忆。

        记忆会被追加到今天的记忆文件中。
        每条记忆包含以下字段：
        - id: 自增序号
        - timestamp: 存储时间
        - key: 记忆标题/键
        - type: 记忆类型（如 collect/analysis/report/general）
        - content: 记忆内容（任意可序列化为 JSON 的数据）
        - tags: 标签列表（方便搜索和分类）

        Args:
            key: 记忆标题/键，简短描述这条记忆是什么
            content: 记忆内容，可以是字符串、字典、列表等
            memory_type: 记忆类型，如 "collect"（采集）、"analysis"（分析）、"report"（报告）
            tags: 标签列表，方便后续搜索

        Returns:
            bool: 存储是否成功

        使用示例：
            memory.store(
                key="电网政策采集结果",
                content={"source": "能源局", "count": 10, "items": [...]},
                memory_type="collect",
                tags=["政策", "电网"]
            )
        """
        try:
            # 获取今天的记忆文件
            today_file = self._get_today_file()

            # 读取已有的记忆
            memories = self._read_memory_file(today_file)

            # 构造新的记忆条目
            new_memory = {
                "id": len(memories) + 1,  # 自增 ID
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "key": key,
                "type": memory_type,
                "content": content,
                "tags": tags or [],
            }

            # 追加到列表
            memories.append(new_memory)

            # 写入文件
            self._write_memory_file(today_file, memories)

            logger.info(f"记忆已存储 | 键: {key} | 类型: {memory_type} | 标签: {tags}")
            return True

        except Exception as e:
            logger.error(f"存储记忆失败: {e}")
            return False

    def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        搜索记忆。

        在所有记忆文件中搜索包含关键词的记忆。
        搜索范围包括：key、content（字符串部分）、tags。
        搜索是简单的关键词匹配，不支持语义搜索。

        为什么不实现语义搜索？
            - 语义搜索需要向量数据库（如 FAISS），增加复杂度
            - 对于小规模记忆（本项目），关键词匹配够用
            - 保持简单，方便 Python 初学者理解

        Args:
            query: 搜索关键词
            limit: 最多返回的结果数量

        Returns:
            List[Dict[str, Any]]: 匹配的记忆列表

        使用示例：
            results = memory.search("电网政策")
            for r in results:
                print(r["key"], r["timestamp"])
        """
        results = []
        query_lower = query.lower()

        # 遍历记忆目录下的所有 JSON 文件
        # 按文件名倒序排列，优先搜索最新的文件
        memory_files = sorted(self.memory_dir.glob("*.json"), reverse=True)

        for file_path in memory_files:
            memories = self._read_memory_file(file_path)

            for mem in memories:
                # 在 key 中搜索
                if query_lower in str(mem.get("key", "")).lower():
                    results.append(mem)
                    continue

                # 在 content 中搜索（如果是字符串）
                content = mem.get("content", "")
                if isinstance(content, str) and query_lower in content.lower():
                    results.append(mem)
                    continue

                # 在 content 的 JSON 字符串形式中搜索（如果是字典/列表）
                if not isinstance(content, str):
                    content_str = json.dumps(content, ensure_ascii=False).lower()
                    if query_lower in content_str:
                        results.append(mem)
                        continue

                # 在 tags 中搜索
                tags = mem.get("tags", [])
                if any(query_lower in str(tag).lower() for tag in tags):
                    results.append(mem)
                    continue

                # 已找到足够多的结果，提前退出
                if len(results) >= limit:
                    break

            if len(results) >= limit:
                break

        logger.info(f"搜索完成 | 关键词: {query} | 结果数: {len(results)}")
        return results[:limit]

    def get_recent(self, n: int = 5) -> List[Dict[str, Any]]:
        """
        获取最近的 n 条记忆。

        从最新的记忆文件开始，往前查找，直到凑够 n 条。

        Args:
            n: 需要获取的记忆条数

        Returns:
            List[Dict[str, Any]]: 最近的 n 条记忆

        使用示例：
            recent = memory.get_recent(5)
            for r in recent:
                print(r["key"], r["timestamp"])
        """
        results = []

        # 按文件名倒序排列，优先读取最新的文件
        memory_files = sorted(self.memory_dir.glob("*.json"), reverse=True)

        for file_path in memory_files:
            memories = self._read_memory_file(file_path)

            # 从最新的记忆开始取
            for mem in reversed(memories):
                results.append(mem)
                if len(results) >= n:
                    break

            if len(results) >= n:
                break

        logger.debug(f"获取最近 {n} 条记忆 | 实际获取: {len(results)} 条")
        return results

    def get_all_dates(self) -> List[str]:
        """
        获取所有有记忆的日期。

        Returns:
            List[str]: 日期列表，格式为 "YYYY-MM-DD"，按时间倒序排列
        """
        dates = []
        for file_path in self.memory_dir.glob("*.json"):
            # 文件名就是日期，如 "2024-01-15.json"
            date_str = file_path.stem
            dates.append(date_str)

        # 按日期倒序排列
        dates.sort(reverse=True)
        return dates

    def summarize(self, max_items: int = 20) -> str:
        """
        用 LLM 总结记忆。

        当记忆过长时，调用 LLM 对最近的记忆进行压缩摘要。
        这样可以在不丢失关键信息的情况下，减少上下文长度。

        注意：此功能需要 llm_client，如果没有初始化，会返回简单的文本摘要。

        Args:
            max_items: 最多总结多少条记忆

        Returns:
            str: 记忆的摘要文本

        使用示例：
            summary = memory.summarize(max_items=10)
            print(summary)
        """
        # 获取最近的记忆
        recent = self.get_recent(max_items)

        if not recent:
            return "暂无记忆。"

        # 构造记忆文本
        memory_text = "\n".join([
            f"[{m.get('timestamp', '')}] [{m.get('type', '')}] {m.get('key', '')}"
            for m in recent
        ])

        # 如果有 LLM 客户端，使用 LLM 进行摘要
        if self.llm_client:
            try:
                # 针对小模型的简洁 prompt
                summary = self.llm_client.simple_chat(
                    system_prompt="你是一个记忆摘要助手。用简洁的中文总结以下记忆内容。",
                    user_prompt=f"请总结以下记忆的要点（不超过200字）：\n\n{memory_text}"
                )
                return summary
            except Exception as e:
                logger.warning(f"LLM 记忆摘要失败: {e}，回退到文本摘要")

        # 没有 LLM 客户端或 LLM 失败，返回简单的文本摘要
        return f"最近 {len(recent)} 条记忆：\n{memory_text}"

    def __repr__(self) -> str:
        dates = self.get_all_dates()
        return f"Memory(dir={self.memory_dir}, dates={len(dates)})"
