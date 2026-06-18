"""
依赖注入容器测试

Author: ModuleMirror
"""

from gh_similarity_detector.core.di_container import (
    DIContainer,
    ServiceLifetime,
    ServiceDescriptor,
    container,
)


class TestDIContainer:
    def test_register_singleton(self):
        c = DIContainer()
        c.register_singleton(str, factory=lambda: "test")
        result = c.resolve(str)
        assert result == "test"

    def test_singleton_returns_same_instance(self):
        c = DIContainer()
        call_count = [0]
        
        def factory():
            call_count[0] += 1
            return object()
        
        c.register_singleton(object, factory=factory)
        instance1 = c.resolve(object)
        instance2 = c.resolve(object)
        assert instance1 is instance2
        assert call_count[0] == 1

    def test_register_transient(self):
        c = DIContainer()
        c.register_transient(list, factory=lambda: [])
        instance1 = c.resolve(list)
        instance2 = c.resolve(list)
        assert instance1 is not instance2

    def test_register_instance(self):
        c = DIContainer()
        obj = {"key": "value"}
        c.register_instance(dict, obj)
        result = c.resolve(dict)
        assert result is obj

    def test_try_resolve_exists(self):
        c = DIContainer()
        c.register_singleton(int, factory=lambda: 42)
        result = c.try_resolve(int)
        assert result == 42

    def test_try_resolve_not_exists(self):
        c = DIContainer()
        result = c.try_resolve(str)
        assert result is None

    def test_is_registered(self):
        c = DIContainer()
        assert c.is_registered(str) is False
        c.register_singleton(str, factory=lambda: "")
        assert c.is_registered(str) is True

    def test_resolve_unregistered_raises(self):
        c = DIContainer()
        try:
            c.resolve(str)
            assert False, "Should raise KeyError"
        except KeyError:
            pass

    def test_get_all_services(self):
        c = DIContainer()
        c.register_singleton(str, factory=lambda: "")
        c.register_transient(int, factory=lambda: 0)
        services = c.get_all_services()
        assert str in services
        assert int in services

    def test_get_instance_singleton(self):
        c1 = DIContainer.get_instance()
        c2 = DIContainer.get_instance()
        assert c1 is c2

    def test_reset(self):
        DIContainer.reset()
        DIContainer.get_instance()
        DIContainer.reset()
        c = DIContainer.get_instance()
        assert c is not None


class TestServiceDescriptor:
    def test_singleton_lifetime(self):
        desc = ServiceDescriptor(
            interface=str,
            implementation=str,
            lifetime=ServiceLifetime.SINGLETON,
        )
        assert desc.lifetime == ServiceLifetime.SINGLETON

    def test_transient_lifetime(self):
        desc = ServiceDescriptor(
            interface=int,
            implementation=int,
            lifetime=ServiceLifetime.TRANSIENT,
        )
        assert desc.lifetime == ServiceLifetime.TRANSIENT
