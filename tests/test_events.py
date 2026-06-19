"""
领域事件系统测试

Author: ModuleMirror
"""

from gh_similarity_detector.core.events import (
    EventBus,
    DomainEvent,
    DomainEventType,
    event_bus,
)


class TestDomainEvent:
    def test_event_auto_id(self):
        event = DomainEvent(event_type=DomainEventType.DETECTION_STARTED, payload={"url": "test"})
        assert event.event_id != ""
        assert event.event_id.startswith("detection_started_")

    def test_event_custom_id(self):
        event = DomainEvent(event_type=DomainEventType.DETECTION_COMPLETED, event_id="custom_123")
        assert event.event_id == "custom_123"

    def test_event_timestamp(self):
        event = DomainEvent(event_type=DomainEventType.DETECTION_STARTED)
        assert event.timestamp > 0


class TestEventBus:
    def test_subscribe_and_publish(self):
        bus = EventBus()
        received = []
        bus.subscribe(DomainEventType.DETECTION_STARTED, lambda e: received.append(e))
        event = DomainEvent(event_type=DomainEventType.DETECTION_STARTED, payload={"url": "test"})
        delivered = bus.publish(event)
        assert delivered == 1
        assert len(received) == 1
        assert received[0].payload["url"] == "test"

    def test_multiple_handlers(self):
        bus = EventBus()
        count = [0]
        bus.subscribe(DomainEventType.DETECTION_COMPLETED, lambda e: count.__setitem__(0, count[0] + 1))
        bus.subscribe(DomainEventType.DETECTION_COMPLETED, lambda e: count.__setitem__(0, count[0] + 1))
        bus.publish(DomainEvent(event_type=DomainEventType.DETECTION_COMPLETED))
        assert count[0] == 2

    def test_unsubscribe(self):
        bus = EventBus()
        received = []
        def handler(e):
            return received.append(e)
        bus.subscribe(DomainEventType.DETECTION_STARTED, handler)
        bus.unsubscribe(DomainEventType.DETECTION_STARTED, handler)
        bus.publish(DomainEvent(event_type=DomainEventType.DETECTION_STARTED))
        assert len(received) == 0

    def test_subscribe_all(self):
        bus = EventBus()
        received = []
        bus.subscribe_all(lambda e: received.append(e))
        bus.publish(DomainEvent(event_type=DomainEventType.DETECTION_STARTED))
        bus.publish(DomainEvent(event_type=DomainEventType.PROJECT_ADDED))
        assert len(received) == 2

    def test_handler_error_isolation(self):
        bus = EventBus()
        results = []
        bus.subscribe(DomainEventType.DETECTION_STARTED, lambda e: 1 / 0)
        bus.subscribe(DomainEventType.DETECTION_STARTED, lambda e: results.append("ok"))
        delivered = bus.publish(DomainEvent(event_type=DomainEventType.DETECTION_STARTED))
        assert len(results) == 1
        assert delivered == 1

    def test_publish_simple(self):
        bus = EventBus()
        received = []
        bus.subscribe(DomainEventType.FINGERPRINT_GENERATED, lambda e: received.append(e))
        bus.publish_simple(DomainEventType.FINGERPRINT_GENERATED, module_id="mod1")
        assert len(received) == 1
        assert received[0].payload["module_id"] == "mod1"

    def test_history(self):
        bus = EventBus()
        bus.publish(DomainEvent(event_type=DomainEventType.DETECTION_STARTED))
        bus.publish(DomainEvent(event_type=DomainEventType.DETECTION_COMPLETED))
        history = bus.get_history()
        assert len(history) == 2

    def test_history_filtered(self):
        bus = EventBus()
        bus.publish(DomainEvent(event_type=DomainEventType.DETECTION_STARTED))
        bus.publish(DomainEvent(event_type=DomainEventType.DETECTION_COMPLETED))
        bus.publish(DomainEvent(event_type=DomainEventType.DETECTION_STARTED))
        history = bus.get_history(event_type=DomainEventType.DETECTION_STARTED)
        assert len(history) == 2

    def test_history_limit(self):
        bus = EventBus()
        for i in range(20):
            bus.publish(DomainEvent(event_type=DomainEventType.DETECTION_STARTED, payload={"i": i}))
        history = bus.get_history(limit=5)
        assert len(history) == 5

    def test_clear_history(self):
        bus = EventBus()
        bus.publish(DomainEvent(event_type=DomainEventType.DETECTION_STARTED))
        bus.clear_history()
        assert len(bus.get_history()) == 0

    def test_handler_count(self):
        bus = EventBus()
        bus.subscribe(DomainEventType.DETECTION_STARTED, lambda e: None)
        bus.subscribe(DomainEventType.DETECTION_COMPLETED, lambda e: None)
        assert bus.handler_count == 2

    def test_event_types_with_handlers(self):
        bus = EventBus()
        bus.subscribe(DomainEventType.DETECTION_STARTED, lambda e: None)
        types = bus.event_types_with_handlers
        assert DomainEventType.DETECTION_STARTED in types


class TestGlobalEventBus:
    def test_global_instance(self):
        assert event_bus is not None
        assert isinstance(event_bus, EventBus)
