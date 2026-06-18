"""
混沌测试框架

随机故障注入（网络/DB/API），验证系统弹性。
参考: Chaos Engineering principles — Netflix/Simian Army

Author: ModuleMirror
"""

import random
import time
from typing import Callable, List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
from contextlib import contextmanager


class FaultType(Enum):
    NETWORK_DELAY = "network_delay"
    NETWORK_ERROR = "network_error"
    DB_TIMEOUT = "db_timeout"
    DB_ERROR = "db_error"
    API_ERROR = "api_error"
    API_RATE_LIMIT = "api_rate_limit"
    DISK_FULL = "disk_full"
    MEMORY_PRESSURE = "memory_pressure"


@dataclass
class FaultInjection:
    fault_type: FaultType
    probability: float = 0.5
    duration_seconds: float = 1.0
    enabled: bool = True

    def should_inject(self) -> bool:
        if not self.enabled:
            return False
        return random.random() < self.probability


@dataclass
class ChaosResult:
    injections_attempted: int = 0
    injections_triggered: int = 0
    operations_survived: int = 0
    operations_failed: int = 0
    faults_triggered: List[str] = field(default_factory=list)

    @property
    def survival_rate(self) -> float:
        total = self.operations_survived + self.operations_failed
        return self.operations_survived / total if total > 0 else 0.0

    @property
    def injection_rate(self) -> float:
        return self.injections_triggered / self.injections_attempted if self.injections_attempted > 0 else 0.0


class ChaosMonkey:
    def __init__(self, seed: Optional[int] = None):
        self._rng = random.Random(seed)
        self._faults: Dict[FaultType, FaultInjection] = {}
        self._result = ChaosResult()

    def configure_fault(self, fault: FaultInjection) -> None:
        self._faults[fault.fault_type] = fault

    def enable_fault(self, fault_type: FaultType) -> None:
        if fault_type in self._faults:
            self._faults[fault_type].enabled = True

    def disable_fault(self, fault_type: FaultType) -> None:
        if fault_type in self._faults:
            self._faults[fault_type].enabled = False

    def disable_all(self) -> None:
        for fault in self._faults.values():
            fault.enabled = False

    @contextmanager
    def inject(self, fault_type: FaultType):
        fault = self._faults.get(fault_type)
        self._result.injections_attempted += 1

        if fault and fault.should_inject():
            self._result.injections_triggered += 1
            self._result.faults_triggered.append(fault_type.value)
            try:
                yield True
            finally:
                pass
        else:
            try:
                yield False
            finally:
                pass

    def run_with_chaos(
        self,
        operation: Callable[[], Any],
        fault_type: FaultType,
        fallback: Optional[Callable[[], Any]] = None,
    ) -> Any:
        with self.inject(fault_type) as injected:
            if injected:
                if fallback:
                    try:
                        result = fallback()
                        self._result.operations_survived += 1
                        return result
                    except Exception as e:
                        self._result.operations_failed += 1
                        raise
                else:
                    self._result.operations_failed += 1
                    raise RuntimeError(f"Chaos fault injected: {fault_type.value}")
            else:
                try:
                    result = operation()
                    self._result.operations_survived += 1
                    return result
                except Exception as e:
                    self._result.operations_failed += 1
                    raise

    @property
    def result(self) -> ChaosResult:
        return self._result

    def reset(self) -> None:
        self._result = ChaosResult()


STeady_State = Dict[str, Any]


def steady_state_hypothesis(
    check_fn: Callable[[], bool],
    chaos: ChaosMonkey,
    fault_type: FaultType,
    iterations: int = 10,
) -> Dict[str, Any]:
    results = {"passed": 0, "failed": 0, "total": iterations}
    for _ in range(iterations):
        try:
            ok = check_fn()
            if ok:
                results["passed"] += 1
            else:
                results["failed"] += 1
        except Exception:
            results["failed"] += 1
    results["survival_rate"] = results["passed"] / iterations
    return results
