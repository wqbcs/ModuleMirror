"""
特性开关测试

Author: ModuleMirror
"""

from gh_similarity_detector.infrastructure.resilience.feature_flags import (
    FeatureFlag,
    EvaluationContext,
    FeatureFlagProvider,
    FeatureFlags,
    create_default_feature_flags,
)


class TestFeatureFlag:
    def test_create(self):
        flag = FeatureFlag(
            key="test_flag",
            default_value=True,
            description="测试开关",
        )
        assert flag.key == "test_flag"
        assert flag.default_value is True


class TestEvaluationContext:
    def test_get_attribute(self):
        ctx = EvaluationContext(
            targeting_key="user123",
            attributes={"role": "admin", "age": 30},
        )
        assert ctx.get("role") == "admin"
        assert ctx.get("age") == 30
        assert ctx.get("nonexistent", "default") == "default"


class TestFeatureFlagProvider:
    def test_register_flag(self):
        provider = FeatureFlagProvider()
        flag = FeatureFlag(key="test", default_value=True)
        provider.register_flag(flag)

        assert provider.evaluate("test") is True

    def test_evaluate_nonexistent(self):
        provider = FeatureFlagProvider()
        result = provider.evaluate("nonexistent", default_value=False)
        assert result is False

    def test_evaluate_with_context(self):
        provider = FeatureFlagProvider()
        flag = FeatureFlag(
            key="targeted_flag",
            default_value=False,
            targeting_rules=[
                {
                    "conditions": [{"key": "role", "operator": "eq", "values": ["admin"]}],
                    "variant": "true",
                }
            ],
        )
        provider.register_flag(flag)

        ctx_admin = EvaluationContext(attributes={"role": "admin"})
        assert provider.evaluate("targeted_flag", context=ctx_admin) is True

        ctx_user = EvaluationContext(attributes={"role": "user"})
        assert provider.evaluate("targeted_flag", context=ctx_user) is False

    def test_evaluate_variant(self):
        provider = FeatureFlagProvider()
        flag = FeatureFlag(
            key="variant_flag",
            default_value=False,
            variants={"a": True, "b": False},
            targeting_rules=[
                {
                    "conditions": [{"key": "group", "operator": "eq", "values": ["a"]}],
                    "variant": "a",
                },
                {
                    "conditions": [{"key": "group", "operator": "eq", "values": ["b"]}],
                    "variant": "b",
                },
            ],
        )
        provider.register_flag(flag)

        ctx_a = EvaluationContext(attributes={"group": "a"})
        assert provider.evaluate_variant("variant_flag", "default", ctx_a) == "a"

        ctx_b = EvaluationContext(attributes={"group": "b"})
        assert provider.evaluate_variant("variant_flag", "default", ctx_b) == "b"

    def test_register_flags_from_dict(self):
        provider = FeatureFlagProvider()
        flags_data = {
            "flag1": {"default": True, "description": "开关1"},
            "flag2": {"default": False, "description": "开关2"},
        }
        provider.register_flags_from_dict(flags_data)

        assert provider.evaluate("flag1") is True
        assert provider.evaluate("flag2") is False

    def test_list_flags(self):
        provider = FeatureFlagProvider()
        provider.register_flag(FeatureFlag(key="a", default_value=True))
        provider.register_flag(FeatureFlag(key="b", default_value=False))

        flags = provider.list_flags()
        assert "a" in flags
        assert "b" in flags

    def test_get_flag_metadata(self):
        provider = FeatureFlagProvider()
        provider.register_flag(
            FeatureFlag(
                key="test",
                default_value=True,
                description="测试",
            )
        )

        meta = provider.get_flag_metadata("test")
        assert meta["key"] == "test"
        assert meta["default_value"] is True


class TestFeatureFlags:
    def test_enabled(self):
        FeatureFlags.initialize()
        provider = FeatureFlags.get_provider()
        provider.register_flag(FeatureFlag(key="test", default_value=True))

        assert FeatureFlags.enabled("test") is True

    def test_variant(self):
        FeatureFlags.initialize()
        provider = FeatureFlags.get_provider()
        provider.register_flag(
            FeatureFlag(
                key="variant_test",
                default_value=False,
                variants={"v1": True},
            )
        )

        variant = FeatureFlags.variant("variant_test", "default")
        assert variant == "default"


class TestCreateDefaultFeatureFlags:
    def test_create(self):
        provider = create_default_feature_flags()
        flags = provider.list_flags()

        assert "use_simd_batch" in flags
        assert "enable_ast_vectorization" in flags
        assert "use_process_pool" in flags
