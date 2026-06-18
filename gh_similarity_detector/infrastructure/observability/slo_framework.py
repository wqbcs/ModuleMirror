"""
SLI/SLO 框架

定义服务级别指标(SLI)、目标(SLO)和自动告警。

Author: ModuleMirror
"""

import time
from typing import Dict, List, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from collections import deque
import statistics

from ...utils.logger import logger


@dataclass
class SLIDefinition:
    name: str
    description: str
    unit: str = "ms"
    good_events_metric: str = ""
    total_events_metric: str = ""


@dataclass
class SLOTarget:
    sli_name: str
    target_percentage: float
    warning_threshold: float
    error_budget: float = 0.0
    
    def __post_init__(self):
        if self.error_budget == 0.0:
            self.error_budget = 100.0 - self.target_percentage


@dataclass
class SLIMeasurement:
    timestamp: float
    value: float
    is_good: bool
    metadata: Dict[str, str] = field(default_factory=dict)


class SLICollector:
    def __init__(self, definition: SLIDefinition, window_size: int = 1000):
        self.definition = definition
        self.window_size = window_size
        self._measurements: deque = deque(maxlen=window_size)
    
    def record(self, value: float, is_good: bool = None, metadata: Dict[str, str] = None) -> None:
        if is_good is None:
            is_good = value <= 100
        
        measurement = SLIMeasurement(
            timestamp=time.time(),
            value=value,
            is_good=is_good,
            metadata=metadata or {},
        )
        self._measurements.append(measurement)
    
    def compute_sli(self) -> float:
        if not self._measurements:
            return 100.0
        
        good_count = sum(1 for m in self._measurements if m.is_good)
        total = len(self._measurements)
        
        return (good_count / total) * 100.0
    
    def get_percentile(self, percentile: float) -> float:
        if not self._measurements:
            return 0.0
        
        values = sorted(m.value for m in self._measurements)
        idx = int(len(values) * percentile / 100)
        idx = min(idx, len(values) - 1)
        return values[idx]
    
    def get_stats(self) -> Dict[str, float]:
        if not self._measurements:
            return {"count": 0, "sli": 100.0, "p50": 0.0, "p95": 0.0, "p99": 0.0}
        
        values = [m.value for m in self._measurements]
        return {
            "count": len(values),
            "sli": self.compute_sli(),
            "p50": self.get_percentile(50),
            "p95": self.get_percentile(95),
            "p99": self.get_percentile(99),
            "mean": statistics.mean(values),
            "min": min(values),
            "max": max(values),
        }


class SLOMonitor:
    def __init__(self):
        self._sli_collectors: Dict[str, SLICollector] = {}
        self._slo_targets: Dict[str, SLOTarget] = {}
        self._alert_handlers: List[Callable] = []
    
    def register_sli(self, definition: SLIDefinition) -> SLICollector:
        collector = SLICollector(definition)
        self._sli_collectors[definition.name] = collector
        logger.info(f"SLI 已注册: {definition.name}")
        return collector
    
    def register_slo(self, target: SLOTarget) -> None:
        self._slo_targets[target.sli_name] = target
        logger.info(f"SLO 已注册: {target.sli_name} -> {target.target_percentage}%")
    
    def add_alert_handler(self, handler: Callable) -> None:
        self._alert_handlers.append(handler)
    
    def record(self, sli_name: str, value: float, is_good: bool = None, metadata: Dict[str, str] = None) -> None:
        if sli_name not in self._sli_collectors:
            return
        
        collector = self._sli_collectors[sli_name]
        collector.record(value, is_good, metadata)
        
        self._check_slo(sli_name)
    
    def _check_slo(self, sli_name: str) -> None:
        if sli_name not in self._slo_targets:
            return
        
        target = self._slo_targets[sli_name]
        collector = self._sli_collectors[sli_name]
        
        current_sli = collector.compute_sli()
        
        if current_sli < target.target_percentage:
            alert = {
                "type": "slo_breach",
                "sli_name": sli_name,
                "current_sli": current_sli,
                "target_slo": target.target_percentage,
                "error_budget_remaining": current_sli - (100.0 - target.error_budget),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            self._emit_alert(alert)
        elif current_sli < target.warning_threshold:
            alert = {
                "type": "slo_warning",
                "sli_name": sli_name,
                "current_sli": current_sli,
                "warning_threshold": target.warning_threshold,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            self._emit_alert(alert)
    
    def _emit_alert(self, alert: Dict[str, Any]) -> None:
        logger.warning(f"SLO 告警: {alert}")
        for handler in self._alert_handlers:
            try:
                handler(alert)
            except Exception as e:
                logger.error(f"告警处理器失败: {e}")
    
    def get_slo_report(self) -> Dict[str, Any]:
        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "slis": {},
            "slos": {},
        }
        
        for name, collector in self._sli_collectors.items():
            report["slis"][name] = collector.get_stats()
        
        for name, target in self._slo_targets.items():
            if name in self._sli_collectors:
                current_sli = self._sli_collectors[name].compute_sli()
                report["slos"][name] = {
                    "target": target.target_percentage,
                    "current": current_sli,
                    "status": "healthy" if current_sli >= target.target_percentage else "breached",
                    "error_budget_remaining": current_sli - (100.0 - target.error_budget),
                }
        
        return report


DEFAULT_SLI_DEFINITIONS = [
    SLIDefinition(
        name="latency_p99",
        description="请求延迟 P99",
        unit="ms",
    ),
    SLIDefinition(
        name="availability",
        description="服务可用性",
        unit="%",
    ),
    SLIDefinition(
        name="error_rate",
        description="错误率",
        unit="%",
    ),
    SLIDefinition(
        name="throughput",
        description="吞吐量",
        unit="req/s",
    ),
]


def create_default_slo_monitor() -> SLOMonitor:
    monitor = SLOMonitor()
    
    for sli_def in DEFAULT_SLI_DEFINITIONS:
        monitor.register_sli(sli_def)
    
    monitor.register_slo(SLOTarget(
        sli_name="latency_p99",
        target_percentage=95.0,
        warning_threshold=97.0,
    ))
    
    monitor.register_slo(SLOTarget(
        sli_name="availability",
        target_percentage=99.9,
        warning_threshold=99.5,
    ))
    
    monitor.register_slo(SLOTarget(
        sli_name="error_rate",
        target_percentage=95.0,
        warning_threshold=97.0,
    ))
    
    return monitor
