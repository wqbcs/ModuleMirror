"""
核心层抽象接口 (DIP - Dependency Inversion Principle)

定义核心层依赖的基础设施抽象接口，
实现依赖倒置：core 不依赖 infrastructure 具体实现。

Author: ModuleMirror
"""

from typing import Protocol, Dict, Set, List, Any, Optional
from abc import abstractmethod

from ..models.entities import Module, FingerprintSet


class IStorage(Protocol):
    @abstractmethod
    def save_fingerprints(self, fingerprints: FingerprintSet) -> None: ...

    @abstractmethod
    def load_fingerprints(self, module_id: str) -> Optional[FingerprintSet]: ...

    @abstractmethod
    def get_all_fingerprints(self) -> Dict[str, Set[int]]: ...


class ICache(Protocol):
    @abstractmethod
    def get(self, key: str) -> Optional[Any]: ...

    @abstractmethod
    def put(self, key: str, value: Any) -> None: ...

    @abstractmethod
    def invalidate(self, key: str) -> bool: ...


class IGitHubClient(Protocol):
    @abstractmethod
    async def get_repository(self, owner: str, repo: str) -> Dict[str, Any]: ...

    @abstractmethod
    async def get_file_content(self, owner: str, repo: str, path: str) -> str: ...

    @abstractmethod
    async def search_repositories(
        self, query: str, max_results: int = 10
    ) -> List[Dict[str, Any]]: ...


class IParser(Protocol):
    @abstractmethod
    def parse(self, code: str, language: str) -> Any: ...

    @abstractmethod
    def extract_functions(self, code: str, language: str) -> List[Module]: ...

    @abstractmethod
    def extract_classes(self, code: str, language: str) -> List[Module]: ...


class ILogger(Protocol):
    @abstractmethod
    def info(self, message: str, **kwargs: Any) -> None: ...

    @abstractmethod
    def warning(self, message: str, **kwargs: Any) -> None: ...

    @abstractmethod
    def error(self, message: str, **kwargs: Any) -> None: ...

    @abstractmethod
    def debug(self, message: str, **kwargs: Any) -> None: ...


class IMetrics(Protocol):
    @abstractmethod
    def increment(self, name: str, value: int = 1, tags: Dict[str, str] = None) -> None: ...

    @abstractmethod
    def gauge(self, name: str, value: float, tags: Dict[str, str] = None) -> None: ...

    @abstractmethod
    def timing(self, name: str, value: float, tags: Dict[str, str] = None) -> None: ...


class IConfiguration(Protocol):
    @abstractmethod
    def get(self, key: str, default: Any = None) -> Any: ...

    @abstractmethod
    def set(self, key: str, value: Any) -> None: ...

    @abstractmethod
    def validate(self) -> bool: ...


class IEventBus(Protocol):
    @abstractmethod
    def publish(self, event_type: str, payload: Dict[str, Any]) -> None: ...

    @abstractmethod
    def subscribe(self, event_type: str, handler: Any) -> None: ...


class IRateLimiter(Protocol):
    @abstractmethod
    def acquire(self, key: str, tokens: int = 1) -> bool: ...

    @abstractmethod
    def get_remaining(self, key: str) -> int: ...
