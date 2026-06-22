"""
可选依赖统一管理测试
"""

from gh_similarity_detector.utils.deps import DependencyRegistry, DepStatus


class TestDependencyRegistry:
    def test_singleton(self):
        r1 = DependencyRegistry.get_instance()
        r2 = DependencyRegistry.get_instance()
        assert r1 is r2

    def test_is_available_datasketch(self):
        r = DependencyRegistry.get_instance()
        assert r.is_available("datasketch") is True

    def test_is_available_numpy(self):
        r = DependencyRegistry.get_instance()
        assert r.is_available("numpy") is True

    def test_is_available_mmh3(self):
        r = DependencyRegistry.get_instance()
        assert r.is_available("mmh3") is True

    def test_is_unavailable_unknown(self):
        r = DependencyRegistry.get_instance()
        assert r.is_available("nonexistent_package") is False

    def test_report(self):
        r = DependencyRegistry.get_instance()
        report = r.report
        assert "datasketch" in report
        assert "numpy" in report
        assert report["datasketch"] == "available"

    def test_require_available(self):
        r = DependencyRegistry.get_instance()
        r.require("datasketch")

    def test_require_unavailable(self):
        from gh_similarity_detector.utils.exceptions import DependencyError

        DependencyRegistry.get_instance()
        registry = DependencyRegistry()
        registry.register("fake_pkg", "fake_package_xyz", "测试", "test")
        try:
            registry.require("fake_pkg")
            assert False, "应抛出 DependencyError"
        except DependencyError as e:
            assert "fake_pkg" in e.message

    def test_register_custom(self):
        registry = DependencyRegistry()
        registry.register("test_dep", "os", "测试依赖", "")
        registry.check_all()
        assert registry.is_available("test_dep") is True

    def test_check_all(self):
        r = DependencyRegistry.get_instance()
        result = r.check_all()
        assert isinstance(result, dict)
        assert "datasketch" in result
        assert result["datasketch"].status == DepStatus.AVAILABLE
