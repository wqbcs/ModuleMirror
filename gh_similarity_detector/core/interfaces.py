"""
核心层抽象接口 (DIP - Dependency Inversion Principle)

定义核心层依赖的基础设施抽象接口，
实现依赖倒置：core 不依赖 infrastructure 具体实现。

Author: ModuleMirror
"""

from __future__ import annotations

from typing import Protocol, Dict, Set, List, Any, Optional
from abc import abstractmethod

from ..models.entities import Module, FingerprintSet


class IStorage(Protocol):
    """存储抽象接口，定义指纹数据的持久化操作"""

    @abstractmethod
    def save_fingerprints(self, fingerprints: FingerprintSet) -> None:
        """保存指纹集合到存储
        
        Args:
            fingerprints: 待保存的指纹集合对象
        """
        ...

    @abstractmethod
    def load_fingerprints(self, module_id: str) -> Optional[FingerprintSet]:
        """从存储加载指定模块的指纹集合
        
        Args:
            module_id: 模块唯一标识符
            
        Returns:
            指纹集合对象，模块不存在时返回None
        """
        ...

    @abstractmethod
    def get_all_fingerprints(self) -> Dict[str, Set[int]]:
        """获取所有模块的指纹映射
        
        Returns:
            字典，键为模块ID，值为指纹集合
        """
        ...


class ICache(Protocol):
    """缓存抽象接口，定义键值缓存操作"""

    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """从缓存获取值
        
        Args:
            key: 缓存键
            
        Returns:
            缓存值，键不存在时返回None
        """
        ...

    @abstractmethod
    def put(self, key: str, value: Any) -> None:
        """写入缓存
        
        Args:
            key: 缓存键
            value: 缓存值
        """
        ...

    @abstractmethod
    def invalidate(self, key: str) -> bool:
        """使指定缓存键失效
        
        Args:
            key: 缓存键
            
        Returns:
            是否成功失效
        """
        ...


class IGitHubClient(Protocol):
    """GitHub客户端抽象接口，定义与GitHub API的交互操作"""

    @abstractmethod
    async def get_repository(self, owner: str, repo: str) -> Dict[str, Any]:
        """获取仓库信息
        
        Args:
            owner: 仓库所有者
            repo: 仓库名称
            
        Returns:
            仓库信息的字典
        """
        ...

    @abstractmethod
    async def get_file_content(self, owner: str, repo: str, path: str) -> str:
        """获取仓库文件内容
        
        Args:
            owner: 仓库所有者
            repo: 仓库名称
            path: 文件路径
            
        Returns:
            文件内容字符串
        """
        ...

    @abstractmethod
    async def search_repositories(
        self, query: str, max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """搜索仓库
        
        Args:
            query: 搜索查询字符串
            max_results: 最大返回结果数，默认为10
            
        Returns:
            仓库信息字典列表
        """
        ...


class IParser(Protocol):
    """解析器抽象接口，定义代码解析和模块提取操作"""

    @abstractmethod
    def parse(self, code: str, language: str) -> Any:
        """解析源代码
        
        Args:
            code: 源代码字符串
            language: 编程语言标识
            
        Returns:
            解析后的AST或语法树对象
        """
        ...

    @abstractmethod
    def extract_functions(self, code: str, language: str) -> List[Module]:
        """从源代码提取函数模块
        
        Args:
            code: 源代码字符串
            language: 编程语言标识
            
        Returns:
            提取的函数模块列表
        """
        ...

    @abstractmethod
    def extract_classes(self, code: str, language: str) -> List[Module]:
        """从源代码提取类模块
        
        Args:
            code: 源代码字符串
            language: 编程语言标识
            
        Returns:
            提取的类模块列表
        """
        ...


class ILogger(Protocol):
    """日志抽象接口，定义日志记录操作"""

    @abstractmethod
    def info(self, message: str, **kwargs: Any) -> None:
        """记录INFO级别日志
        
        Args:
            message: 日志消息
            **kwargs: 附加关键字参数
        """
        ...

    @abstractmethod
    def warning(self, message: str, **kwargs: Any) -> None:
        """记录WARNING级别日志
        
        Args:
            message: 日志消息
            **kwargs: 附加关键字参数
        """
        ...

    @abstractmethod
    def error(self, message: str, **kwargs: Any) -> None:
        """记录ERROR级别日志
        
        Args:
            message: 日志消息
            **kwargs: 附加关键字参数
        """
        ...

    @abstractmethod
    def debug(self, message: str, **kwargs: Any) -> None:
        """记录DEBUG级别日志
        
        Args:
            message: 日志消息
            **kwargs: 附加关键字参数
        """
        ...


class IMetrics(Protocol):
    """指标抽象接口，定义度量数据采集操作"""

    @abstractmethod
    def increment(self, name: str, value: int = 1, tags: Optional[Dict[str, str]] = None) -> None:
        """递增计数器指标
        
        Args:
            name: 指标名称
            value: 递增值，默认为1
            tags: 可选的标签字典
        """
        ...

    @abstractmethod
    def gauge(self, name: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
        """设置仪表盘指标值
        
        Args:
            name: 指标名称
            value: 指标值
            tags: 可选的标签字典
        """
        ...

    @abstractmethod
    def timing(self, name: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
        """记录计时指标
        
        Args:
            name: 指标名称
            value: 耗时值（秒）
            tags: 可选的标签字典
        """
        ...


class IConfiguration(Protocol):
    """配置抽象接口，定义配置读写和校验操作"""

    @abstractmethod
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值
        
        Args:
            key: 配置键
            default: 键不存在时的默认值
            
        Returns:
            配置值
        """
        ...

    @abstractmethod
    def set(self, key: str, value: Any) -> None:
        """设置配置值
        
        Args:
            key: 配置键
            value: 配置值
        """
        ...

    @abstractmethod
    def validate(self) -> bool:
        """校验配置有效性
        
        Returns:
            配置是否有效
        """
        ...


class IEventBus(Protocol):
    """事件总线抽象接口，定义事件发布与订阅操作"""

    @abstractmethod
    def publish(self, event_type: str, payload: Dict[str, Any]) -> None:
        """发布事件
        
        Args:
            event_type: 事件类型标识
            payload: 事件负载数据字典
        """
        ...

    @abstractmethod
    def subscribe(self, event_type: str, handler: Any) -> None:
        """订阅事件
        
        Args:
            event_type: 事件类型标识
            handler: 事件处理函数
        """
        ...


class IRateLimiter(Protocol):
    """限流器抽象接口，定义令牌桶限流操作"""

    @abstractmethod
    def acquire(self, key: str, tokens: int = 1) -> bool:
        """尝试获取令牌
        
        Args:
            key: 限流键标识
            tokens: 请求的令牌数，默认为1
            
        Returns:
            是否成功获取令牌
        """
        ...

    @abstractmethod
    def get_remaining(self, key: str) -> int:
        """获取剩余可用令牌数
        
        Args:
            key: 限流键标识
            
        Returns:
            剩余令牌数量
        """
        ...
