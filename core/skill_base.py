"""
技能基类模块 (skill_base)

本模块定义了所有 Skill 的抽象模板，以及自动发现和加载技能的机制。

设计思路：
    - 每个 Skill 是一个独立的模块，有 name、description、version、author 等元数据
    - Skill 有三个生命周期方法：load() → execute() → unload()
    - 技能发现机制：自动扫描 skills/ 目录下的模块，动态加载
    - 这种设计让技能可插拔，添加新 Skill 只需在 skills/ 目录下创建新文件

为什么用抽象基类？
    - 强制子类实现 execute() 方法，确保接口统一
    - 提供 load/unload 的默认实现，子类可选择性覆盖
    - 方便类型提示和 IDE 自动补全

对应 OpenClaw 概念：
    - OpenClaw 中每个 Skill 是独立模块，包含 SKILL.md 式的描述和执行逻辑
    - 我们用 Python 抽象基类实现了类似的功能
    - SKILL.md 的信息对应到 Skill 类的 name、description 等属性

使用示例：
    # 定义一个新的 Skill
    class MySkill(SkillBase):
        name = "my_skill"
        description = "我的自定义技能"

        def execute(self, params):
            return {"result": "执行成功"}

    # 自动发现和加载技能
    registry = SkillRegistry()
    registry.discover_skills()
    skill = registry.get_skill("my_skill")
    result = skill.execute({})
"""

import importlib
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

logger = logging.getLogger(__name__)


class SkillBase(ABC):
    """
    技能基类。

    所有 Skill 都必须继承此类，并实现 execute() 方法。
    Skill 是 Agent 能力的扩展单元，每个 Skill 专注于一个特定任务。

    类属性（子类必须设置）：
        name: 技能名称（唯一标识，如 "collector_policy"）
        description: 技能描述（简短说明功能，如 "政策法规采集"）
        version: 版本号（默认 "1.0.0"）
        author: 作者（默认 "power_grid_agent"）

    生命周期：
        1. load() - 加载技能，初始化资源
        2. execute(params) - 执行技能，返回结果
        3. unload() - 卸载技能，释放资源

    使用示例：
        class MySkill(SkillBase):
            name = "my_skill"
            description = "我的自定义技能"

            def execute(self, params):
                return {"result": "执行成功"}
    """

    # ====== 子类必须设置的类属性 ======
    name: str = "base_skill"           # 技能名称（唯一标识）
    description: str = "技能基类"       # 技能描述
    version: str = "1.0.0"             # 版本号
    author: str = "power_grid_agent"   # 作者

    def __init__(self):
        """
        初始化技能。

        子类可以覆盖此方法来添加自定义初始化逻辑，
        但必须调用 super().__init__()。
        """
        self._loaded = False  # 标记技能是否已加载
        logger.debug(f"技能实例化: {self.name} v{self.version}")

    def load(self) -> bool:
        """
        加载技能。

        在技能首次使用前调用，用于初始化资源（如数据库连接、模型加载等）。
        子类可以覆盖此方法添加自定义加载逻辑。

        Returns:
            bool: 加载是否成功

        使用示例：
            skill = MySkill()
            if skill.load():
                result = skill.execute(params)
        """
        if self._loaded:
            logger.debug(f"技能已加载，跳过: {self.name}")
            return True

        try:
            # 子类可以覆盖此方法添加自定义加载逻辑
            # 默认实现只是标记为已加载
            self._loaded = True
            logger.info(f"技能加载成功: {self.name}")
            return True
        except Exception as e:
            logger.error(f"技能加载失败: {self.name} | 错误: {e}")
            return False

    @abstractmethod
    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行技能。

        这是技能的核心方法，子类必须实现。
        所有技能的执行逻辑都写在这里。

        Args:
            params: 执行参数，字典格式。
                   不同技能需要的参数不同，具体看各 Skill 的文档。

        Returns:
            Dict[str, Any]: 执行结果，字典格式。
                           建议包含 "success" 字段表示是否成功。

        子类实现示例：
            def execute(self, params):
                topic = params.get("topic", "默认主题")
                # ... 执行采集/分析/报告逻辑 ...
                return {"success": True, "data": result}
        """
        pass

    def unload(self) -> None:
        """
        卸载技能。

        在技能不再使用时调用，用于释放资源。
        子类可以覆盖此方法添加自定义卸载逻辑。

        注意：大多数简单技能不需要覆盖此方法，
        因为 Python 的垃圾回收机制会自动清理不再使用的对象。
        """
        self._loaded = False
        logger.info(f"技能已卸载: {self.name}")

    @property
    def is_loaded(self) -> bool:
        """技能是否已加载"""
        return self._loaded

    def get_info(self) -> Dict[str, str]:
        """
        获取技能的元信息。

        Returns:
            Dict[str, str]: 技能元信息字典
        """
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "author": self.author,
            "loaded": str(self._loaded),
        }

    def __repr__(self) -> str:
        return f"Skill(name={self.name}, v{self.version}, loaded={self._loaded})"


class SkillRegistry:
    """
    技能注册表。

    管理所有已注册的技能，提供技能的发现、加载、获取等功能。
    技能发现机制：自动扫描 skills/ 目录下的 Python 模块，
    找到继承自 SkillBase 的类并自动注册。

    为什么需要注册表？
        - 统一管理所有技能，避免手动导入
        - 按名称获取技能，方便 MainAgent 调用
        - 自动发现机制让添加新 Skill 变得简单

    使用示例：
        registry = SkillRegistry()
        registry.discover_skills()
        skill = registry.get_skill("collector_policy")
        if skill:
            result = skill.execute({"topic": "电网政策"})
    """

    def __init__(self):
        """初始化技能注册表。"""
        # 技能字典：name → Skill 实例
        self._skills: Dict[str, SkillBase] = {}
        logger.info("技能注册表初始化完成")

    def register(self, skill: SkillBase) -> bool:
        """
        注册一个技能。

        将技能实例添加到注册表中，以技能名称为键。
        如果技能名称已存在，会记录警告并覆盖。

        Args:
            skill: 技能实例

        Returns:
            bool: 注册是否成功
        """
        if not isinstance(skill, SkillBase):
            logger.error(f"注册失败: 不是 SkillBase 的子类 | 类型: {type(skill)}")
            return False

        if skill.name in self._skills:
            logger.warning(f"技能已存在，将覆盖: {skill.name}")

        self._skills[skill.name] = skill
        logger.info(f"技能已注册: {skill.name} | 描述: {skill.description}")
        return True

    def get_skill(self, name: str) -> Optional[SkillBase]:
        """
        按名称获取技能。

        Args:
            name: 技能名称

        Returns:
            Optional[SkillBase]: 技能实例，不存在则返回 None
        """
        skill = self._skills.get(name)
        if skill is None:
            logger.warning(f"技能不存在: {name}")
        return skill

    def list_skills(self) -> List[Dict[str, str]]:
        """
        列出所有已注册的技能。

        Returns:
            List[Dict[str, str]]: 技能信息列表
        """
        return [skill.get_info() for skill in self._skills.values()]

    def discover_skills(self, skills_dir: Optional[str] = None) -> int:
        """
        自动发现并注册技能。

        扫描 skills/ 目录下的 Python 模块，
        找到继承自 SkillBase 的类并自动注册。

        发现规则：
            1. 扫描 skills/ 目录下的 .py 文件
            2. 排除以 _ 开头的文件（如 __init__.py）
            3. 导入模块，查找 SkillBase 的子类
            4. 实例化并注册

        Args:
            skills_dir: 技能目录路径，默认为项目根目录下的 skills/

        Returns:
            int: 发现并注册的技能数量
        """
        # 确定技能目录
        if skills_dir is None:
            # 默认使用项目根目录下的 skills/ 目录
            project_root = Path(__file__).resolve().parent.parent
            skills_dir = str(project_root / "skills")

        skills_path = Path(skills_dir)

        if not skills_path.exists():
            logger.warning(f"技能目录不存在: {skills_path}")
            return 0

        count = 0

        # 遍历目录下的 .py 文件
        for file_path in skills_path.glob("skill_*.py"):
            # 排除以 _ 开头的文件
            if file_path.name.startswith("_"):
                continue

            # 构造模块名
            # 例如：skills/skill_collector_policy.py → skills.skill_collector_policy
            module_name = f"skills.{file_path.stem}"

            try:
                # 动态导入模块
                module = importlib.import_module(module_name)

                # 在模块中查找 SkillBase 的子类
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)

                    # 检查是否是类、是否是 SkillBase 的子类、是否不是 SkillBase 本身
                    if (isinstance(attr, type) and
                        issubclass(attr, SkillBase) and
                        attr is not SkillBase):

                        try:
                            # 实例化并注册
                            skill_instance = attr()
                            if self.register(skill_instance):
                                count += 1
                        except Exception as e:
                            logger.error(f"技能实例化失败: {module_name}.{attr_name} | 错误: {e}")

            except ImportError as e:
                logger.error(f"技能模块导入失败: {module_name} | 错误: {e}")
            except Exception as e:
                logger.error(f"技能发现异常: {file_path} | 错误: {e}")

        logger.info(f"技能发现完成 | 发现: {count} 个技能")
        return count

    def execute_skill(self, name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        按名称执行技能。

        这是便捷方法，整合了获取技能、加载、执行的流程。

        Args:
            name: 技能名称
            params: 执行参数

        Returns:
            Dict[str, Any]: 执行结果。如果技能不存在或执行失败，
                           返回 {"success": False, "error": "错误信息"}
        """
        # 获取技能
        skill = self.get_skill(name)
        if skill is None:
            return {"success": False, "error": f"技能不存在: {name}"}

        # 加载技能（如果还没加载）
        if not skill.is_loaded:
            if not skill.load():
                return {"success": False, "error": f"技能加载失败: {name}"}

        # 执行技能
        try:
            result = skill.execute(params)
            # 确保结果包含 success 字段
            if "success" not in result:
                result["success"] = True
            return result
        except Exception as e:
            logger.error(f"技能执行异常: {name} | 错误: {e}")
            return {"success": False, "error": str(e)}

    def __repr__(self) -> str:
        return f"SkillRegistry(skills={list(self._skills.keys())})"
