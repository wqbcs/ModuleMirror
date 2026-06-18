"""
领域事件系统

EventBus 发布-订阅模式，解耦核心模块间通信。
支持同步/异步事件处理、事件历史、错误隔离。

Author: ModuleMirror
"""

import time
from typing import Dict, List, Callable, Any, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict

from ..utils.logger import logger


class DomainEventType(Enum):
    DETECTION_STARTED = "detection_started"
    DETECTION_COMPLETED = "detection_completed"
    DETECTION_FAILED = "detection_failed"
    FINGERPRINT_GENERATED = "fingerprint_generated"
    SIMILARITY_FOUND = "similarity_found"
    PLAGIARISM_FOUND = "plagiarism_found"
    PROJECT_ADDED = "project_added"
    PROJECT_DELETED = "project_deleted"
    MODULE_PROCESSED = "module_processed"
    INDEX_UPDATED = "index_updated"


@dataclass
class DomainEvent:
    event_type: DomainEventType
    payload: Dict[str, Any] = field(default_factory=dict)
    source: str = ""
    timestamp: float = field(default_factory=time.time)
    event_id: str = ""

    def __post_init__(self):
        if not self.event_id:
            self.event_id = f"{self.event_type.value}_{self.timestamp:.6f}"


EventHandler = Callable[[DomainEvent], None]


class EventBus:
    def __init__(self):
        self._handlers: Dict[DomainEventType, List[EventHandler]] = defaultdict(list)
        self._wildcard_handlers: List[EventHandler] = []
        self._history: List[DomainEvent] = []
        self._max_history = 1000

    def subscribe(self, event_type: DomainEventType, handler: EventHandler) -> None:
        self._handlers[event_type].append(handler)
        logger.debug(f"EventBus 订阅: {event_type.value} -> {handler.__name__}")

    def subscribe_all(self, handler: EventHandler) -> None:
        self._wildcard_handlers.append(handler)
        logger.debug(f"EventBus 全局订阅: {handler.__name__}")

    def unsubscribe(self, event_type: DomainEventType, handler: EventHandler) -> None:
        handlers = self._handlers.get(event_type, [])
        if handler in handlers:
            handlers.remove(handler)

    def publish(self, event: DomainEvent) -> int:
        self._add_to_history(event)
        delivered = 0

        for handler in self._handlers.get(event.event_type, []):
            try:
                handler(event)
                delivered += 1
            except Exception as e:
                logger.error(f"EventBus 处理器异常: {handler.__name__}, 事件={event.event_type.value}, 错误={e}")

        for handler in self._wildcard_handlers:
            try:
                handler(event)
                delivered += 1
            except Exception as e:
                logger.error(f"EventBus 全局处理器异常: {handler.__name__}, 错误={e}")

        logger.debug(f"EventBus 发布: {event.event_type.value}, 投递={delivered}")
        return delivered

    def publish_simple(self, event_type: DomainEventType, **kwargs) -> DomainEvent:
        event = DomainEvent(event_type=event_type, payload=kwargs)
        self.publish(event)
        return event

    def _add_to_history(self, event: DomainEvent) -> None:
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

    def get_history(
        self, event_type: Optional[DomainEventType] = None, limit: int = 100
    ) -> List[DomainEvent]:
        if event_type:
            filtered = [e for e in self._history if e.event_type == event_type]
        else:
            filtered = self._history
        return filtered[-limit:]

    def clear_history(self) -> None:
        self._history.clear()

    @property
    def handler_count(self) -> int:
        count = len(self._wildcard_handlers)
        for handlers in self._handlers.values():
            count += len(handlers)
        return count

    @property
    def event_types_with_handlers(self) -> Set[DomainEventType]:
        return set(self._handlers.keys())


event_bus = EventBus()
