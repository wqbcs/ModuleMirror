"""
Prometheus 指标导出模块

提供检测耗时/指纹命中率/DB查询/API请求等核心指标:
- 检测耗时直方图
- 指纹生成/查询计数
- DB查询耗时
- API请求计数+耗时
- Circuit Breaker状态
"""

from ... import __version__
from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    Info,
    CollectorRegistry,
    generate_latest,
    CONTENT_TYPE_LATEST,
)

registry = CollectorRegistry()

DETECTION_DURATION = Histogram(
    "ghsim_detection_duration_seconds",
    "检测耗时(秒)",
    ["preset", "language"],
    registry=registry,
)

FINGERPRINT_GENERATION_TOTAL = Counter(
    "ghsim_fingerprint_generation_total",
    "指纹生成次数",
    ["language"],
    registry=registry,
)

FINGERPRINT_HIT_TOTAL = Counter(
    "ghsim_fingerprint_hit_total",
    "指纹命中次数(在指纹库中找到匹配)",
    ["fp_type"],
    registry=registry,
)

FINGERPRINT_MISS_TOTAL = Counter(
    "ghsim_fingerprint_miss_total",
    "指纹未命中次数",
    ["fp_type"],
    registry=registry,
)

DB_QUERY_DURATION = Histogram(
    "ghsim_db_query_duration_seconds",
    "数据库查询耗时(秒)",
    ["operation"],
    registry=registry,
)

DB_QUERY_TOTAL = Counter(
    "ghsim_db_query_total",
    "数据库查询次数",
    ["operation"],
    registry=registry,
)

API_REQUEST_TOTAL = Counter(
    "ghsim_api_request_total",
    "API请求次数",
    ["method", "endpoint", "status"],
    registry=registry,
)

API_REQUEST_DURATION = Histogram(
    "ghsim_api_request_duration_seconds",
    "API请求耗时(秒)",
    ["method", "endpoint"],
    registry=registry,
)

ACTIVE_DETECTIONS = Gauge(
    "ghsim_active_detections",
    "当前正在进行的检测数量",
    registry=registry,
)

CIRCUIT_BREAKER_STATE = Gauge(
    "ghsim_circuit_breaker_state",
    "Circuit Breaker状态(0=CLOSED,1=OPEN,2=HALF_OPEN)",
    ["name"],
    registry=registry,
)

PROJECT_INFO = Info(
    "ghsim_project",
    "ModuleMirror项目信息",
    registry=registry,
)

PROJECT_INFO.info({"version": __version__, "language": "python"})


def get_metrics() -> bytes:
    """生成Prometheus格式的指标数据"""
    return generate_latest(registry)


def get_content_type() -> str:
    """获取Prometheus指标Content-Type"""
    return CONTENT_TYPE_LATEST


class MetricsCollector:
    """指标收集器 - 便捷方法"""

    @staticmethod
    def record_detection(
        duration: float, preset: str = "balanced", language: str = "python"
    ) -> None:
        DETECTION_DURATION.labels(preset=preset, language=language).observe(duration)

    @staticmethod
    def record_fingerprint_generation(language: str = "python") -> None:
        FINGERPRINT_GENERATION_TOTAL.labels(language=language).inc()

    @staticmethod
    def record_fingerprint_hit(fp_type: str = "winnowing") -> None:
        FINGERPRINT_HIT_TOTAL.labels(fp_type=fp_type).inc()

    @staticmethod
    def record_fingerprint_miss(fp_type: str = "winnowing") -> None:
        FINGERPRINT_MISS_TOTAL.labels(fp_type=fp_type).inc()

    @staticmethod
    def record_db_query(duration: float, operation: str = "select") -> None:
        DB_QUERY_TOTAL.labels(operation=operation).inc()
        DB_QUERY_DURATION.labels(operation=operation).observe(duration)

    @staticmethod
    def record_api_request(
        duration: float, method: str = "GET", endpoint: str = "/", status: int = 200
    ) -> None:
        API_REQUEST_TOTAL.labels(method=method, endpoint=endpoint, status=str(status)).inc()
        API_REQUEST_DURATION.labels(method=method, endpoint=endpoint).observe(duration)

    @staticmethod
    def set_active_detections(count: int) -> None:
        ACTIVE_DETECTIONS.set(count)

    @staticmethod
    def set_circuit_breaker_state(name: str, state: int) -> None:
        CIRCUIT_BREAKER_STATE.labels(name=name).set(state)
