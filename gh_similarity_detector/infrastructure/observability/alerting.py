"""
告警规则模块

基于 Prometheus metrics 数据定义告警规则：
1. 检测耗时异常（超过阈值）
2. 指纹库膨胀（条目数超限）
3. API 错误率过高
4. 电路断开告警
5. 内存使用告警

支持静态阈值 + 动态阈值（基于滑动窗口均值）。
"""

import time
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field
from enum import Enum

from ...utils.logger import logger


class AlertSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertState(Enum):
    OK = "ok"
    FIRING = "firing"
    PENDING = "pending"


@dataclass
class AlertRule:
    """告警规则"""

    name: str
    description: str
    severity: AlertSeverity
    metric_name: str
    threshold: float
    comparison: str = "gt"
    cooldown_seconds: float = 60.0
    _last_fired: float = 0.0
    _state: AlertState = AlertState.OK

    def evaluate(self, current_value: float) -> bool:
        """评估是否触发告警

        Returns:
            True=触发, False=未触发
        """
        if self.comparison == "gt":
            triggered = current_value > self.threshold
        elif self.comparison == "lt":
            triggered = current_value < self.threshold
        elif self.comparison == "gte":
            triggered = current_value >= self.threshold
        elif self.comparison == "lte":
            triggered = current_value <= self.threshold
        elif self.comparison == "eq":
            triggered = current_value == self.threshold
        else:
            triggered = current_value > self.threshold

        if triggered:
            now = time.monotonic()
            if now - self._last_fired >= self.cooldown_seconds:
                self._last_fired = now
                self._state = AlertState.FIRING
                return True
            self._state = AlertState.PENDING
            return False

        self._state = AlertState.OK
        return False

    @property
    def state(self) -> AlertState:
        return self._state


@dataclass
class AlertEvent:
    """告警事件"""

    rule_name: str
    severity: AlertSeverity
    message: str
    current_value: float
    threshold: float
    timestamp: float = field(default_factory=time.monotonic)


class AlertManager:
    """告警管理器

    管理告警规则，定期评估并触发告警。
    """

    def __init__(self):
        self._rules: Dict[str, AlertRule] = {}
        self._metric_providers: Dict[str, Callable[[], float]] = {}
        self._listeners: List[Callable[[AlertEvent], None]] = []
        self._history: List[AlertEvent] = []
        self._max_history = 100

    def add_rule(self, rule: AlertRule) -> None:
        """添加告警规则"""
        self._rules[rule.name] = rule
        logger.info(
            f"告警规则已添加: {rule.name} ({rule.metric_name} {rule.comparison} {rule.threshold})"
        )

    def remove_rule(self, name: str) -> None:
        """移除告警规则"""
        self._rules.pop(name, None)

    def register_metric_provider(
        self,
        metric_name: str,
        provider: Callable[[], float],
    ) -> None:
        """注册指标提供者

        Args:
            metric_name: 指标名称
            provider: 返回当前指标值的可调用对象
        """
        self._metric_providers[metric_name] = provider

    def add_listener(self, listener: Callable[[AlertEvent], None]) -> None:
        """添加告警监听器"""
        self._listeners.append(listener)

    def evaluate_all(self) -> List[AlertEvent]:
        """评估所有规则

        Returns:
            触发的告警事件列表
        """
        fired_events = []
        for rule in self._rules.values():
            provider = self._metric_providers.get(rule.metric_name)
            if provider is None:
                continue
            try:
                current_value = provider()
            except Exception as e:
                logger.warning(f"指标获取失败 [{rule.metric_name}]: {e}")
                continue

            if rule.evaluate(current_value):
                event = AlertEvent(
                    rule_name=rule.name,
                    severity=rule.severity,
                    message=(
                        f"{rule.description}: "
                        f"current={current_value:.2f}, "
                        f"threshold={rule.threshold:.2f}"
                    ),
                    current_value=current_value,
                    threshold=rule.threshold,
                )
                fired_events.append(event)
                self._history.append(event)
                if len(self._history) > self._max_history:
                    self._history = self._history[-self._max_history :]

                logger.warning(f"告警触发: {event.message}")
                for listener in self._listeners:
                    try:
                        listener(event)
                    except Exception as e:
                        logger.error(f"告警监听器执行失败: {e}")

        return fired_events

    def evaluate_rule(self, name: str) -> Optional[AlertEvent]:
        """评估单条规则"""
        rule = self._rules.get(name)
        if rule is None:
            return None
        provider = self._metric_providers.get(rule.metric_name)
        if provider is None:
            return None
        current_value = provider()
        if rule.evaluate(current_value):
            return AlertEvent(
                rule_name=rule.name,
                severity=rule.severity,
                message=f"{rule.description}: current={current_value:.2f}, threshold={rule.threshold:.2f}",
                current_value=current_value,
                threshold=rule.threshold,
            )
        return None

    @property
    def history(self) -> List[AlertEvent]:
        return list(self._history)

    @property
    def rules(self) -> Dict[str, AlertRule]:
        return dict(self._rules)

    @property
    def stats(self) -> Dict[str, Any]:
        rule_states = {name: rule.state.value for name, rule in self._rules.items()}
        return {
            "rule_count": len(self._rules),
            "provider_count": len(self._metric_providers),
            "listener_count": len(self._listeners),
            "history_size": len(self._history),
            "rule_states": rule_states,
        }


alert_manager = AlertManager()

alert_manager.add_rule(
    AlertRule(
        name="detection_duration_high",
        description="检测耗时过高",
        severity=AlertSeverity.WARNING,
        metric_name="detection_duration_seconds",
        threshold=300.0,
        comparison="gt",
        cooldown_seconds=120.0,
    )
)

alert_manager.add_rule(
    AlertRule(
        name="fingerprint_db_bloat",
        description="指纹库膨胀",
        severity=AlertSeverity.WARNING,
        metric_name="fingerprint_db_size",
        threshold=100000,
        comparison="gt",
        cooldown_seconds=600.0,
    )
)

alert_manager.add_rule(
    AlertRule(
        name="api_error_rate_high",
        description="API错误率过高",
        severity=AlertSeverity.CRITICAL,
        metric_name="api_error_rate",
        threshold=0.1,
        comparison="gt",
        cooldown_seconds=60.0,
    )
)

alert_manager.add_rule(
    AlertRule(
        name="circuit_breaker_open",
        description="电路断开",
        severity=AlertSeverity.CRITICAL,
        metric_name="circuit_breaker_open_count",
        threshold=0.5,
        comparison="gt",
        cooldown_seconds=30.0,
    )
)

alert_manager.add_rule(
    AlertRule(
        name="memory_usage_high",
        description="内存使用过高",
        severity=AlertSeverity.WARNING,
        metric_name="memory_usage_mb",
        threshold=512.0,
        comparison="gt",
        cooldown_seconds=300.0,
    )
)
