"""
大模型调用模块 (llm)

本模块封装了与千问大模型的交互逻辑。
使用 OpenAI 兼容接口调用讯飞 MaaS 平台上的 Qwen3.5-2B 模型。

对应 OpenClaw 概念：
    - OpenClaw 中有 LLM Provider 的概念，负责与不同的大模型交互
    - 我们用 QwenClient 类实现了类似的功能，专门针对讯飞 MaaS 平台
"""

from llm.qwen_client import QwenClient

__all__ = ["QwenClient"]
