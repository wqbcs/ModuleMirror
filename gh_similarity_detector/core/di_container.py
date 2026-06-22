"""
依赖注入容器 (Dependency Injection Container)

简化依赖管理和测试替换。

Author: ModuleMirror
"""

from __future__ import annotations

from typing import Dict, Type, Any, Callable, Optional, TypeVar
from dataclasses import dataclass
from enum import Enum

from .interfaces import (
    ILogger,
    IEventBus,
)
from ..utils.logger import logger


T = TypeVar("T")


class ServiceLifetime(Enum):
    SINGLETON = "singleton"
    TRANSIENT = "transient"
    SCOPED = "scoped"


@dataclass
class ServiceDescriptor:
    interface: Type[Any]
    implementation: Type[Any]
    lifetime: ServiceLifetime
    factory: Optional[Callable[..., Any]] = None
    instance: Optional[Any] = None


class DIContainer:
    _instance: Optional["DIContainer"] = None

    def __init__(self) -> None:
        self._services: Dict[Type[Any], ServiceDescriptor] = {}
        self._singletons: Dict[Type[Any], Any] = {}

    @classmethod
    def get_instance(cls) -> "DIContainer":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        cls._instance = None

    def register_singleton(
        self,
        interface: Type[T],
        implementation: Optional[Type[T]] = None,
        factory: Optional[Callable[..., Any]] = None,
    ) -> None:
        impl = implementation or interface
        self._services[interface] = ServiceDescriptor(
            interface=interface,
            implementation=impl,
            lifetime=ServiceLifetime.SINGLETON,
            factory=factory,
        )

    def register_transient(
        self,
        interface: Type[T],
        implementation: Optional[Type[T]] = None,
        factory: Optional[Callable[..., Any]] = None,
    ) -> None:
        impl = implementation or interface
        self._services[interface] = ServiceDescriptor(
            interface=interface,
            implementation=impl,
            lifetime=ServiceLifetime.TRANSIENT,
            factory=factory,
        )

    def register_instance(self, interface: Type[T], instance: T) -> None:
        self._services[interface] = ServiceDescriptor(
            interface=interface,
            implementation=type(instance),
            lifetime=ServiceLifetime.SINGLETON,
            instance=instance,
        )
        self._singletons[interface] = instance

    def resolve(self, interface: Type[T]) -> T:
        if interface not in self._services:
            raise KeyError(f"Service not registered: {interface}")

        descriptor = self._services[interface]

        if descriptor.lifetime == ServiceLifetime.SINGLETON:
            if interface in self._singletons:
                return self._singletons[interface]  # type: ignore[no-any-return]

            if descriptor.instance is not None:
                self._singletons[interface] = descriptor.instance
                return descriptor.instance  # type: ignore[no-any-return]

            instance = self._create_instance(descriptor)
            self._singletons[interface] = instance
            return instance  # type: ignore[no-any-return]

        return self._create_instance(descriptor)  # type: ignore[no-any-return]

    def _create_instance(self, descriptor: ServiceDescriptor) -> Any:
        if descriptor.factory:
            return descriptor.factory()

        return descriptor.implementation()

    def try_resolve(self, interface: Type[T]) -> Optional[T]:
        try:
            return self.resolve(interface)
        except KeyError:
            return None

    def is_registered(self, interface: Type[Any]) -> bool:
        return interface in self._services

    def get_all_services(self) -> Dict[Type[Any], ServiceDescriptor]:
        return dict(self._services)


def configure_default_services() -> DIContainer:
    container = DIContainer.get_instance()

    from .events import EventBus

    if not container.is_registered(ILogger):
        container.register_singleton(ILogger, factory=lambda: logger)  # type: ignore[type-abstract]

    if not container.is_registered(IEventBus):
        container.register_singleton(IEventBus, factory=lambda: EventBus())  # type: ignore[type-abstract]

    return container


container = DIContainer.get_instance()
