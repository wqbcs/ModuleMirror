"""
混沌测试验证

Author: ModuleMirror
"""

import pytest
from tests.chaos import (
    ChaosMonkey,
    FaultType,
    FaultInjection,
    ChaosResult,
)


class TestFaultInjection:
    def test_should_inject_disabled(self):
        f = FaultInjection(fault_type=FaultType.NETWORK_ERROR, probability=1.0, enabled=False)
        assert f.should_inject() is False

    def test_should_inject_zero_probability(self):
        f = FaultInjection(fault_type=FaultType.NETWORK_ERROR, probability=0.0)
        assert f.should_inject() is False

    def test_should_inject_full_probability(self):
        f = FaultInjection(fault_type=FaultType.NETWORK_ERROR, probability=1.0)
        assert f.should_inject() is True


class TestChaosMonkey:
    def test_configure_fault(self):
        cm = ChaosMonkey(seed=42)
        cm.configure_fault(FaultInjection(fault_type=FaultType.NETWORK_ERROR, probability=0.5))
        assert FaultType.NETWORK_ERROR in cm._faults

    def test_disable_fault(self):
        cm = ChaosMonkey(seed=42)
        cm.configure_fault(FaultInjection(fault_type=FaultType.DB_ERROR, probability=1.0))
        cm.disable_fault(FaultType.DB_ERROR)
        assert cm._faults[FaultType.DB_ERROR].enabled is False

    def test_disable_all(self):
        cm = ChaosMonkey(seed=42)
        cm.configure_fault(FaultInjection(fault_type=FaultType.NETWORK_ERROR, probability=1.0))
        cm.configure_fault(FaultInjection(fault_type=FaultType.DB_ERROR, probability=1.0))
        cm.disable_all()
        assert all(not f.enabled for f in cm._faults.values())

    def test_run_with_chaos_no_injection(self):
        cm = ChaosMonkey(seed=42)
        cm.configure_fault(FaultInjection(fault_type=FaultType.NETWORK_ERROR, probability=0.0))
        result = cm.run_with_chaos(lambda: 42, FaultType.NETWORK_ERROR)
        assert result == 42
        assert cm.result.operations_survived == 1

    def test_run_with_chaos_with_fallback(self):
        cm = ChaosMonkey(seed=42)
        cm.configure_fault(FaultInjection(fault_type=FaultType.NETWORK_ERROR, probability=1.0))
        result = cm.run_with_chaos(
            operation=lambda: 42,
            fault_type=FaultType.NETWORK_ERROR,
            fallback=lambda: -1,
        )
        assert result == -1
        assert cm.result.injections_triggered == 1

    def test_run_with_chaos_injection_raises(self):
        cm = ChaosMonkey(seed=42)
        cm.configure_fault(FaultInjection(fault_type=FaultType.DB_ERROR, probability=1.0))
        with pytest.raises(RuntimeError, match="Chaos fault injected"):
            cm.run_with_chaos(lambda: 42, FaultType.DB_ERROR)

    def test_inject_context_manager(self):
        cm = ChaosMonkey(seed=42)
        cm.configure_fault(FaultInjection(fault_type=FaultType.API_ERROR, probability=0.0))
        with cm.inject(FaultType.API_ERROR) as injected:
            assert injected is False

    def test_result_tracking(self):
        cm = ChaosMonkey(seed=42)
        cm.configure_fault(FaultInjection(fault_type=FaultType.NETWORK_ERROR, probability=0.0))
        cm.run_with_chaos(lambda: 1, FaultType.NETWORK_ERROR)
        cm.run_with_chaos(lambda: 2, FaultType.NETWORK_ERROR)
        assert cm.result.operations_survived == 2
        assert cm.result.survival_rate == 1.0

    def test_reset(self):
        cm = ChaosMonkey(seed=42)
        cm.configure_fault(FaultInjection(fault_type=FaultType.NETWORK_ERROR, probability=0.0))
        cm.run_with_chaos(lambda: 1, FaultType.NETWORK_ERROR)
        cm.reset()
        assert cm.result.operations_survived == 0


class TestChaosResult:
    def test_survival_rate(self):
        r = ChaosResult(operations_survived=8, operations_failed=2)
        assert abs(r.survival_rate - 0.8) < 0.001

    def test_injection_rate(self):
        r = ChaosResult(injections_attempted=10, injections_triggered=5)
        assert abs(r.injection_rate - 0.5) < 0.001

    def test_zero_division(self):
        r = ChaosResult()
        assert r.survival_rate == 0.0
        assert r.injection_rate == 0.0
