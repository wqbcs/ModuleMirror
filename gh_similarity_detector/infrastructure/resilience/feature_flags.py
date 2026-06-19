"""
特性开关 (Feature Flags)

支持灰度发布、A/B测试、渐进式交付。

Author: ModuleMirror
"""

from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass, field
import json

from ...utils.logger import logger


@dataclass
class FeatureFlag:
    key: str
    default_value: bool
    description: str = ""
    variants: Dict[str, Any] = field(default_factory=dict)
    targeting_rules: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class EvaluationContext:
    targeting_key: str = ""
    attributes: Dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        return self.attributes.get(key, default)


class FeatureFlagProvider:
    def __init__(self):
        self._flags: Dict[str, FeatureFlag] = {}
        self._hooks: List[Callable] = []

    def register_flag(self, flag: FeatureFlag) -> None:
        self._flags[flag.key] = flag
        logger.info(f"特性开关已注册: {flag.key} = {flag.default_value}")

    def register_flags_from_dict(self, flags_data: Dict[str, Dict[str, Any]]) -> None:
        for key, data in flags_data.items():
            flag = FeatureFlag(
                key=key,
                default_value=data.get("default", False),
                description=data.get("description", ""),
                variants=data.get("variants", {}),
                targeting_rules=data.get("targeting_rules", []),
            )
            self.register_flag(flag)

    def register_flags_from_file(self, filepath: str) -> None:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.register_flags_from_dict(data.get("flags", {}))
        except Exception as e:
            logger.error(f"加载特性开关文件失败: {e}")

    def evaluate(
        self,
        flag_key: str,
        default_value: bool = False,
        context: EvaluationContext = None,
    ) -> bool:
        if flag_key not in self._flags:
            return default_value

        flag = self._flags[flag_key]

        if context and flag.targeting_rules:
            for rule in flag.targeting_rules:
                if self._match_rule(rule, context):
                    variant = rule.get("variant", "true")
                    if variant in flag.variants:
                        return bool(flag.variants[variant])
                    return variant == "true"

        return flag.default_value

    def evaluate_variant(
        self,
        flag_key: str,
        default_variant: str,
        context: EvaluationContext = None,
    ) -> str:
        if flag_key not in self._flags:
            return default_variant

        flag = self._flags[flag_key]

        if context and flag.targeting_rules:
            for rule in flag.targeting_rules:
                if self._match_rule(rule, context):
                    return rule.get("variant", default_variant)

        return default_variant

    def _match_rule(self, rule: Dict[str, Any], context: EvaluationContext) -> bool:
        conditions = rule.get("conditions", [])

        for condition in conditions:
            attr_key = condition.get("key")
            operator = condition.get("operator")
            values = condition.get("values", [])

            actual = context.get(attr_key)

            if operator == "eq":
                if actual not in values:
                    return False
            elif operator == "ne":
                if actual in values:
                    return False
            elif operator == "in":
                if actual not in values:
                    return False
            elif operator == "not_in":
                if actual in values:
                    return False
            elif operator == "contains":
                if not any(v in str(actual) for v in values):
                    return False
            elif operator == "percentage":
                if actual:
                    import hashlib

                    hash_val = int(hashlib.md5(str(actual).encode()).hexdigest(), 16)
                    percentage = int(hash_val % 100)
                    if percentage > values[0] if values else 0:
                        return False

        return True

    def add_hook(self, hook: Callable) -> None:
        self._hooks.append(hook)

    def list_flags(self) -> List[str]:
        return list(self._flags.keys())

    def get_flag_metadata(self, flag_key: str) -> Optional[Dict[str, Any]]:
        if flag_key not in self._flags:
            return None

        flag = self._flags[flag_key]
        return {
            "key": flag.key,
            "default_value": flag.default_value,
            "description": flag.description,
            "variants": flag.variants,
        }


class FeatureFlags:
    _provider: Optional[FeatureFlagProvider] = None

    @classmethod
    def initialize(cls, provider: FeatureFlagProvider = None) -> None:
        cls._provider = provider or FeatureFlagProvider()

    @classmethod
    def get_provider(cls) -> FeatureFlagProvider:
        if cls._provider is None:
            cls.initialize()
        return cls._provider

    @classmethod
    def enabled(
        cls, flag_key: str, default: bool = False, context: EvaluationContext = None
    ) -> bool:
        return cls.get_provider().evaluate(flag_key, default, context)

    @classmethod
    def variant(cls, flag_key: str, default: str, context: EvaluationContext = None) -> str:
        return cls.get_provider().evaluate_variant(flag_key, default, context)


def create_default_feature_flags() -> FeatureFlagProvider:
    provider = FeatureFlagProvider()

    provider.register_flag(
        FeatureFlag(
            key="use_simd_batch",
            default_value=True,
            description="使用 SIMD 批处理优化",
        )
    )

    provider.register_flag(
        FeatureFlag(
            key="enable_ast_vectorization",
            default_value=True,
            description="启用 AST 向量化",
        )
    )

    provider.register_flag(
        FeatureFlag(
            key="use_process_pool",
            default_value=False,
            description="使用进程池替代线程池",
        )
    )

    provider.register_flag(
        FeatureFlag(
            key="enable_progress_stream",
            default_value=True,
            description="启用进度实时推送",
        )
    )

    provider.register_flag(
        FeatureFlag(
            key="new_algorithm_v2",
            default_value=False,
            description="新算法 V2 灰度",
            variants={
                "control": False,
                "treatment": True,
            },
            targeting_rules=[
                {
                    "conditions": [{"key": "user_id", "operator": "percentage", "values": [10]}],
                    "variant": "treatment",
                }
            ],
        )
    )

    return provider
