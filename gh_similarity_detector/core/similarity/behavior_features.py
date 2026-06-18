"""
行为特征集成 - 执行信号 + 代码属性

参考 GraphCodeBERT+: 利用代码行为特征增强克隆检测
不依赖运行时执行，而是通过静态分析提取行为信号:
- 函数调用模式(API调用序列)
- I/O操作模式(读写文件/网络)
- 异常处理模式(try/catch结构)
- 并发模式(thread/async)
- 数据变换模式(map/filter/reduce)

Author: ModuleMirror
"""

import re
from typing import Dict, List, Any
from dataclasses import dataclass, field
from enum import Enum


class BehaviorCategory(Enum):
    API_CALL = "api_call"
    IO_OPERATION = "io_operation"
    EXCEPTION_HANDLING = "exception_handling"
    CONCURRENCY = "concurrency"
    DATA_TRANSFORM = "data_transform"
    ALGORITHM = "algorithm"
    SECURITY = "security"


API_PATTERNS = {
    "http_request": [re.compile(r'\b(requests|httpx|urllib|fetch|axios)\.\w+\(', re.I)],
    "database": [re.compile(r'\b(sqlite|mysql|postgres|mongo|redis|sqlalchemy)\.\w+\(', re.I)],
    "file_io": [re.compile(r'\bopen\s*\(|\bread\s*\(|\bwrite\s*\(|\.read\(|\.write\(', re.I)],
    "network": [re.compile(r'\bsocket\s*\(|\.connect\s*\(|\.bind\s*\(', re.I)],
    "logging": [re.compile(r'\blogger\.\w+\(|logging\.\w+\(', re.I)],
    "testing": [re.compile(r'\bassert\s+|\bpytest|unittest|\.assertEqual', re.I)],
    "serialization": [re.compile(r'\bjson\.\w+\(|\.dumps\(|\.loads\(|pickle\.\w+\(', re.I)],
    "cli": [re.compile(r'\bargparse|click|sys\.argv', re.I)],
}

EXCEPTION_PATTERNS = [
    re.compile(r'\btry\s*:', re.I),
    re.compile(r'\bexcept\s+\w+', re.I),
    re.compile(r'\bfinally\s*:', re.I),
    re.compile(r'\braise\s+\w+', re.I),
    re.compile(r'\bthrow\s+\w+', re.I),
]

CONCURRENCY_PATTERNS = [
    re.compile(r'\bthreading\.\w+|Thread\s*\(', re.I),
    re.compile(r'\basync\s+def|await\s+', re.I),
    re.compile(r'\bmultiprocessing\.\w+|Process\s*\(', re.I),
    re.compile(r'\bconcurrent\.\w+', re.I),
    re.compile(r'\bmutex|Lock\s*\(|Semaphore', re.I),
]

DATA_TRANSFORM_PATTERNS = [
    re.compile(r'\bmap\s*\(|\.map\s*\(', re.I),
    re.compile(r'\bfilter\s*\(|\.filter\s*\(', re.I),
    re.compile(r'\breduce\s*\(', re.I),
    re.compile(r'\bsorted\s*\(|\.sort\s*\(', re.I),
    re.compile(r'\bsum\s*\(|max\s*\(|min\s*\(', re.I),
    re.compile(r'\bgroupby\s*\(', re.I),
]

ALGORITHM_PATTERNS = {
    "sorting": re.compile(r'\bsort|sorted|qsort|mergesort', re.I),
    "searching": re.compile(r'\bbinary_search|bsearch|find|index', re.I),
    "graph": re.compile(r'\bbfs|dfs|dijkstra|bellman|floyd', re.I),
    "dynamic_programming": re.compile(r'\bmemoriz|dp\[|fibonacci', re.I),
    "hashing": re.compile(r'\bhash|md5|sha256|digest', re.I),
    "encryption": re.compile(r'\bencrypt|decrypt|cipher|aes|rsa', re.I),
}

SECURITY_PATTERNS = [
    re.compile(r'\bsanitiz|escape|encode|validate', re.I),
    re.compile(r'\bauth|permission|token|jwt|csrf', re.I),
    re.compile(r'\bpassword|secret|credential', re.I),
]


@dataclass
class BehaviorSignature:
    code_id: str
    categories: Dict[BehaviorCategory, List[str]] = field(default_factory=dict)
    api_calls: List[str] = field(default_factory=list)
    has_exception_handling: bool = False
    has_concurrency: bool = False
    has_security: bool = False
    algorithm_indicators: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code_id": self.code_id,
            "categories": {k.value: v for k, v in self.categories.items()},
            "api_calls": self.api_calls,
            "has_exception_handling": self.has_exception_handling,
            "has_concurrency": self.has_concurrency,
            "has_security": self.has_security,
            "algorithm_indicators": self.algorithm_indicators,
        }

    def behavior_hash(self) -> str:
        import hashlib
        cats = ":".join(f"{k.value}={','.join(sorted(v))}" for k, v in sorted(self.categories.items()))
        return hashlib.md5(cats.encode()).hexdigest()[:12]

    def similarity(self, other: "BehaviorSignature") -> float:
        cats_a = set()
        cats_b = set()
        for cat, items in self.categories.items():
            for item in items:
                cats_a.add(f"{cat.value}:{item}")
        for cat, items in other.categories.items():
            for item in items:
                cats_b.add(f"{cat.value}:{item}")

        if not cats_a and not cats_b:
            return 1.0
        if not cats_a or not cats_b:
            return 0.0

        intersection = cats_a & cats_b
        union = cats_a | cats_b
        jaccard = len(intersection) / len(union)

        structural = 0.0
        checks = [
            (self.has_exception_handling, other.has_exception_handling),
            (self.has_concurrency, other.has_concurrency),
            (self.has_security, other.has_security),
        ]
        matching = sum(1 for a, b in checks if a == b)
        structural = matching / len(checks)

        return jaccard * 0.6 + structural * 0.4


class BehaviorExtractor:
    def extract(self, code: str, code_id: str = "") -> BehaviorSignature:
        sig = BehaviorSignature(code_id=code_id or "anonymous")

        for api_name, patterns in API_PATTERNS.items():
            for pattern in patterns:
                if pattern.search(code):
                    sig.api_calls.append(api_name)
                    sig.categories.setdefault(BehaviorCategory.API_CALL, []).append(api_name)
                    break

        for pattern in EXCEPTION_PATTERNS:
            if pattern.search(code):
                sig.has_exception_handling = True
                sig.categories.setdefault(BehaviorCategory.EXCEPTION_HANDLING, []).append("try_catch")
                break

        for pattern in CONCURRENCY_PATTERNS:
            if pattern.search(code):
                sig.has_concurrency = True
                sig.categories.setdefault(BehaviorCategory.CONCURRENCY, []).append("concurrent")
                break

        for pattern in DATA_TRANSFORM_PATTERNS:
            m = pattern.search(code)
            if m:
                sig.categories.setdefault(BehaviorCategory.DATA_TRANSFORM, []).append(m.group(0)[:20])

        for algo_name, pattern in ALGORITHM_PATTERNS.items():
            if pattern.search(code):
                sig.algorithm_indicators.append(algo_name)
                sig.categories.setdefault(BehaviorCategory.ALGORITHM, []).append(algo_name)

        for pattern in SECURITY_PATTERNS:
            if pattern.search(code):
                sig.has_security = True
                sig.categories.setdefault(BehaviorCategory.SECURITY, []).append("security_aware")
                break

        file_io = API_PATTERNS.get("file_io", [])
        for pattern in file_io:
            if pattern.search(code):
                sig.categories.setdefault(BehaviorCategory.IO_OPERATION, []).append("file_io")
                break

        return sig

    def compute_similarity(self, sig_a: BehaviorSignature, sig_b: BehaviorSignature) -> float:
        return sig_a.similarity(sig_b)
