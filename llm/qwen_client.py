"""
千问大模型调用客户端 (qwen_client)

本模块封装了通过 OpenAI 兼容接口调用讯飞 MaaS 平台上 Qwen3.5-2B 模型的逻辑。

核心设计考虑：
    1. Qwen3.5-2B 是 2B 参数的小模型，能力有限，因此：
       - 所有 prompt 要简洁明确，不超过 2000 tokens
       - 明确指定输出格式（如"请用 JSON 格式回答"）
       - 分步骤引导，不要一次性要求太多
       - temperature 建议默认 0.3，保证输出稳定

    2. 异常处理和重试机制：
       - 网络请求可能失败，最多重试 3 次
       - LLM 输出可能不是预期格式，提供 JSON 解析容错
       - 所有异常都记录日志，不让程序崩溃

    3. 使用 openai 库的 OpenAI 兼容模式：
       - 讯飞 MaaS 平台提供 OpenAI 兼容接口
       - 只需修改 base_url 和 api_key 即可接入

对应 OpenClaw 概念：
    - OpenClaw 中 LLM Provider 负责与不同大模型交互
    - 我们用 QwenClient 类实现了类似功能，但针对讯飞平台做了优化

使用示例：
    client = QwenClient()
    response = client.chat([{"role": "user", "content": "你好"}])
    print(response)

    # 解析 JSON 格式的回复
    result = client.parse_json_response(response)
"""

import json
import time
import logging
from typing import Optional, Dict, Any, List, Generator

# 尝试导入 openai 库
try:
    from openai import OpenAI, APIError, APIConnectionError, RateLimitError
except ImportError:
    print("【错误】openai 库未安装。请执行: pip install openai>=1.0.0")
    raise

from config.settings import settings

logger = logging.getLogger(__name__)


class QwenClient:
    """
    千问大模型调用客户端。

    封装了与讯飞 MaaS 平台上 Qwen3.5-2B 模型的交互逻辑。
    使用 OpenAI 兼容接口，支持单轮/多轮对话和流式输出。

    属性：
        client: OpenAI 客户端实例
        model_name: 模型名称
        temperature: 生成温度
        max_tokens: 最大生成 token 数
        max_retries: 最大重试次数
        timeout: 请求超时时间（秒）

    使用示例：
        client = QwenClient()
        # 单轮对话
        response = client.chat([{"role": "user", "content": "你好"}])
        # 多轮对话
        messages = [
            {"role": "system", "content": "你是一个电力系统专家"},
            {"role": "user", "content": "什么是电网调度？"}
        ]
        response = client.chat(messages)
    """

    def __init__(
        self,
        api_base: Optional[str] = None,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        max_retries: Optional[int] = None,
        timeout: Optional[int] = None,
    ):
        """
        初始化千问客户端。

        所有参数都是可选的，未提供的参数会从全局配置（settings）中读取。
        这样设计是为了：既支持全局统一配置，也支持特殊场景下覆盖配置。

        Args:
            api_base: API 地址，默认从 settings 读取
            api_key:  API 密钥，默认从 settings 读取
            model_name: 模型名称，默认从 settings 读取
            temperature: 生成温度，默认从 settings 读取
            max_tokens: 最大 token 数，默认从 settings 读取
            max_retries: 最大重试次数，默认从 settings 读取
            timeout: 请求超时（秒），默认从 settings 读取
        """
        # 从全局配置中读取默认值，允许参数覆盖
        self.api_base = api_base or settings.QWEN_API_BASE
        self.api_key = api_key or settings.QWEN_API_KEY
        self.model_name = model_name or settings.QWEN_MODEL_NAME
        self.temperature = temperature if temperature is not None else settings.TEMPERATURE
        self.max_tokens = max_tokens or settings.MAX_TOKENS
        self.max_retries = max_retries or settings.MAX_RETRIES
        self.timeout = timeout or settings.REQUEST_TIMEOUT

        # 创建 OpenAI 客户端实例
        # 使用 base_url 参数指向讯飞 MaaS 平台
        try:
            self.client = OpenAI(
                base_url=self.api_base,
                api_key=self.api_key,
                timeout=self.timeout,
            )
            logger.info(f"QwenClient 初始化成功 | 模型: {self.model_name} | 地址: {self.api_base}")
        except Exception as e:
            logger.error(f"QwenClient 初始化失败: {e}")
            # 不抛出异常，允许程序继续运行（但调用时会失败）
            self.client = None

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stream: bool = False,
    ) -> str:
        """
        发送对话请求并获取回复。

        这是主要的对话接口，支持单轮和多轮对话。
        内置重试机制，网络异常时自动重试。

        Args:
            messages: 消息列表，格式为 [{"role": "user", "content": "..."}, ...]
                      role 可以是 "system"、"user"、"assistant"
            temperature: 本次请求的温度，不传则使用实例默认值
            max_tokens: 本次请求的最大 token 数，不传则使用实例默认值
            stream: 是否使用流式输出（暂未完全实现，预留接口）

        Returns:
            str: 模型的回复文本。如果请求失败，返回空字符串。

        使用示例：
            messages = [
                {"role": "system", "content": "你是电力系统专家"},
                {"role": "user", "content": "什么是电网调度？"}
            ]
            response = client.chat(messages)
        """
        # 安全检查：客户端是否初始化成功
        if self.client is None:
            logger.error("OpenAI 客户端未初始化，无法发送请求")
            return ""

        # 安全检查：messages 不能为空
        if not messages:
            logger.warning("messages 为空，跳过请求")
            return ""

        # 使用传入的参数或实例默认值
        _temperature = temperature if temperature is not None else self.temperature
        _max_tokens = max_tokens or self.max_tokens

        # 重试机制：最多重试 max_retries 次
        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.debug(f"发送请求 (第 {attempt}/{self.max_retries} 次)...")

                # 调用 OpenAI 兼容接口
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    temperature=_temperature,
                    max_tokens=_max_tokens,
                    stream=stream,
                )

                # 提取回复文本
                # response.choices[0].message.content 是模型回复的内容
                result = response.choices[0].message.content

                # 记录 token 使用情况（如果有的话）
                if hasattr(response, 'usage') and response.usage:
                    logger.debug(
                        f"Token 使用: prompt={response.usage.prompt_tokens}, "
                        f"completion={response.usage.completion_tokens}, "
                        f"total={response.usage.total_tokens}"
                    )

                logger.info(f"请求成功 | 回复长度: {len(result)} 字符")
                return result

            except RateLimitError as e:
                # 速率限制错误：请求太频繁，等待后重试
                wait_time = attempt * 5  # 递增等待时间：5s, 10s, 15s
                logger.warning(f"触发速率限制，等待 {wait_time} 秒后重试... 错误: {e}")
                last_error = e
                time.sleep(wait_time)

            except APIConnectionError as e:
                # 网络连接错误：检查网络后重试
                wait_time = attempt * 3
                logger.warning(f"网络连接错误，等待 {wait_time} 秒后重试... 错误: {e}")
                last_error = e
                time.sleep(wait_time)

            except APIError as e:
                # API 返回错误：可能是参数错误等
                logger.error(f"API 错误 (尝试 {attempt}/{self.max_retries}): {e}")
                last_error = e
                # API 错误通常重试也没用，但还是尝试一下
                if attempt < self.max_retries:
                    time.sleep(2)

            except Exception as e:
                # 其他未知错误
                logger.error(f"未知错误 (尝试 {attempt}/{self.max_retries}): {type(e).__name__}: {e}")
                last_error = e
                if attempt < self.max_retries:
                    time.sleep(2)

        # 所有重试都失败了
        logger.error(f"请求失败，已重试 {self.max_retries} 次。最后错误: {last_error}")
        return ""

    def chat_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Generator[str, None, None]:
        """
        流式对话接口。

        逐字返回模型的回复，适合实时显示的场景。
        注意：流式输出不支持重试，网络中断后不会自动恢复。

        Args:
            messages: 消息列表
            temperature: 生成温度
            max_tokens: 最大 token 数

        Yields:
            str: 模型逐字输出的文本片段

        使用示例：
            for chunk in client.chat_stream(messages):
                print(chunk, end="", flush=True)
        """
        if self.client is None:
            logger.error("OpenAI 客户端未初始化，无法发送请求")
            return

        _temperature = temperature if temperature is not None else self.temperature
        _max_tokens = max_tokens or self.max_tokens

        try:
            stream = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=_temperature,
                max_tokens=_max_tokens,
                stream=True,
            )

            for chunk in stream:
                # chunk.choices[0].delta.content 可能是 None（流结束标记）
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            logger.error(f"流式请求失败: {e}")
            yield f"\n[错误] 流式请求失败: {e}"

    def parse_json_response(self, response: str) -> Optional[Dict[str, Any]]:
        """
        解析 LLM 返回的 JSON 格式回复。

        由于 Qwen3.5-2B 是小模型，输出的 JSON 可能格式不完美。
        本方法提供多重容错机制：
        1. 直接解析
        2. 提取 ```json ... ``` 代码块
        3. 提取第一个 { ... } 或 [ ... ] 区间
        4. 全部失败返回 None

        Args:
            response: LLM 的回复文本

        Returns:
            Optional[Dict[str, Any]]: 解析成功的字典，失败返回 None

        使用示例：
            response = '{"intent": "collect", "topic": "政策法规"}'
            result = client.parse_json_response(response)
            # result = {"intent": "collect", "topic": "政策法规"}
        """
        if not response or not response.strip():
            logger.warning("回复为空，无法解析 JSON")
            return None

        text = response.strip()

        # 方法 1：直接尝试解析
        try:
            result = json.loads(text)
            logger.debug("直接解析 JSON 成功")
            return result
        except json.JSONDecodeError:
            pass

        # 方法 2：提取 ```json ... ``` 代码块
        # 小模型可能把 JSON 包在 markdown 代码块中
        import re
        json_block_pattern = r"```(?:json)?\s*\n?(.*?)\n?\s*```"
        match = re.search(json_block_pattern, text, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group(1).strip())
                logger.debug("从代码块中提取 JSON 成功")
                return result
            except json.JSONDecodeError:
                pass

        # 方法 3：提取第一个 { ... } 区间
        # 小模型可能在 JSON 前后添加额外文字
        brace_pattern = r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}"
        match = re.search(brace_pattern, text, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group(0))
                logger.debug("从文本中提取 JSON 成功")
                return result
            except json.JSONDecodeError:
                pass

        # 方法 4：提取 [ ... ] 数组格式
        bracket_pattern = r"\[[^\[\]]*(?:\[[^\[\]]*\][^\[\]]*)*\]"
        match = re.search(bracket_pattern, text, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group(0))
                logger.debug("从文本中提取 JSON 数组成功")
                return result
            except json.JSONDecodeError:
                pass

        # 全部失败
        logger.warning(f"无法从回复中解析 JSON。回复前 200 字: {text[:200]}")
        return None

    def simple_chat(self, system_prompt: str, user_prompt: str) -> str:
        """
        简化的对话接口。

        适用于简单的"一问一答"场景，不需要手动构造 messages 列表。

        Args:
            system_prompt: 系统提示词（定义角色和行为规范）
            user_prompt: 用户输入

        Returns:
            str: 模型回复

        使用示例：
            response = client.simple_chat(
                system_prompt="你是电力系统专家，用简洁的语言回答",
                user_prompt="什么是电网调度？"
            )
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        return self.chat(messages)

    def structured_chat(self, system_prompt: str, user_prompt: str) -> Optional[Dict[str, Any]]:
        """
        结构化对话接口。

        发送请求并尝试将回复解析为 JSON。
        适用于需要 LLM 返回结构化数据的场景（如意图判断、信息提取等）。

        Args:
            system_prompt: 系统提示词
            user_prompt: 用户输入

        Returns:
            Optional[Dict[str, Any]]: 解析成功的 JSON 字典，失败返回 None

        使用示例：
            result = client.structured_chat(
                system_prompt="你是意图识别系统，用 JSON 格式回答",
                user_prompt="帮我采集一下电力政策法规"
            )
            # 期望返回: {"intent": "collect", "topic": "政策法规"}
        """
        # 在 user_prompt 末尾追加 JSON 格式提示
        # 这是针对小模型的技巧：明确告诉它输出格式
        enhanced_prompt = (
            f"{user_prompt}\n\n"
            f"请严格按照 JSON 格式回答，不要添加其他文字。"
        )

        response = self.simple_chat(system_prompt, enhanced_prompt)
        return self.parse_json_response(response)
