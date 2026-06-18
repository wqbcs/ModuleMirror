"""
SBP 过滤器 - Similar But Patched

基于 FVF 论文的相似但已修补代码识别。
核心思想：代码虽然高度相似，但如果已包含安全补丁修复，
则不应被标记为抄袭，而是"安全衍生"。

识别策略：
1. 提交消息关键词匹配（CVE/fix/security/patch/vulnerability）
2. 代码差异中的安全修复模式（边界检查、输入验证、权限校验）
3. 指纹差集分析（新增指纹集中在安全函数）

Author: ModuleMirror
"""

import re
from typing import Dict, List, Set, Optional, Any
from dataclasses import dataclass, field
from enum import Enum


class PatchStatus(Enum):
    UNPATCHED = "unpatched"
    PATCHED = "patched"
    PARTIALLY_PATCHED = "partially_patched"
    UNKNOWN = "unknown"


@dataclass
class SBPResult:
    source_id: str
    target_id: str
    similarity: float
    patch_status: PatchStatus
    confidence: float
    patch_indicators: List[str] = field(default_factory=list)
    security_patterns_found: List[str] = field(default_factory=list)
    new_fingerprint_ratio: float = 0.0

    @property
    def is_safe_derivative(self) -> bool:
        return self.patch_status in (PatchStatus.PATCHED, PatchStatus.PARTIALLY_PATCHED) and self.confidence >= 0.6

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "similarity": self.similarity,
            "patch_status": self.patch_status.value,
            "confidence": round(self.confidence, 3),
            "is_safe_derivative": self.is_safe_derivative,
            "patch_indicators": self.patch_indicators,
            "security_patterns_found": self.security_patterns_found,
            "new_fingerprint_ratio": round(self.new_fingerprint_ratio, 3),
        }


COMMIT_KEYWORDS = [
    re.compile(r'\bcve[-_]\d{4}[-_]\d+', re.IGNORECASE),
    re.compile(r'\bfix\s+(security|vuln|vulnerability)', re.IGNORECASE),
    re.compile(r'\b(security|vulnerability)\s+fix', re.IGNORECASE),
    re.compile(r'\bpatch\s+(security|vuln)', re.IGNORECASE),
    re.compile(r'\b(address|resolve|close)\s+(cve|vuln|security)', re.IGNORECASE),
    re.compile(r'\b(xss|injection|csrf|ssrf|rce)\b', re.IGNORECASE),
    re.compile(r'\bfix\s+(xss|injection|csrf|ssrf|rce)', re.IGNORECASE),
    re.compile(r'\bbuffer\s+overflow', re.IGNORECASE),
    re.compile(r'\bprivilege\s+escalation', re.IGNORECASE),
]

SECURITY_CODE_PATTERNS = [
    (re.compile(r'\binput_sanitiz\w+', re.IGNORECASE), "input_sanitization"),
    (re.compile(r'\bparam\w*_check\w*', re.IGNORECASE), "parameter_check"),
    (re.compile(r'\bbound\w*_check\w*', re.IGNORECASE), "boundary_check"),
    (re.compile(r'\b(length|size|count)\s*[<>=!]+\s*\w+', re.IGNORECASE), "length_validation"),
    (re.compile(r'\b(escape|encode|sanitize)\s*\(', re.IGNORECASE), "output_encoding"),
    (re.compile(r'\b(auth|permission|access)_check\w*', re.IGNORECASE), "access_control"),
    (re.compile(r'\b(prepared|parameterized)\s*statement', re.IGNORECASE), "sql_injection_prevention"),
    (re.compile(r'\bcrypt\w*_compare\w*', re.IGNORECASE), "timing_safe_compare"),
    (re.compile(r'\b(csrf|token)_verify', re.IGNORECASE), "csrf_protection"),
    (re.compile(r'\brate\s*limit', re.IGNORECASE), "rate_limiting"),
]


class SBPFilter:
    def __init__(
        self,
        similarity_threshold: float = 60.0,
        patch_confidence_threshold: float = 0.6,
        new_fingerprint_ratio_threshold: float = 0.15,
    ):
        self.similarity_threshold = similarity_threshold
        self.patch_confidence_threshold = patch_confidence_threshold
        self.new_fingerprint_ratio_threshold = new_fingerprint_ratio_threshold

    def analyze(
        self,
        source_id: str,
        target_id: str,
        similarity: float,
        source_fingerprints: Set[int],
        target_fingerprints: Set[int],
        commit_messages: Optional[List[str]] = None,
        source_code: Optional[str] = None,
    ) -> SBPResult:
        if similarity < self.similarity_threshold:
            return SBPResult(
                source_id=source_id,
                target_id=target_id,
                similarity=similarity,
                patch_status=PatchStatus.UNKNOWN,
                confidence=0.0,
            )

        patch_indicators = []
        security_patterns = []
        confidence = 0.0

        if commit_messages:
            msg_matches = self._check_commit_messages(commit_messages)
            patch_indicators.extend(msg_matches)
            if msg_matches:
                confidence += 0.4 * min(len(msg_matches), 3) / 3

        if source_code:
            code_matches = self._check_security_patterns(source_code)
            security_patterns.extend(code_matches)
            if code_matches:
                confidence += 0.3 * min(len(code_matches), 3) / 3

        new_fp_ratio = 0.0
        if source_fingerprints and target_fingerprints:
            new_in_target = target_fingerprints - source_fingerprints
            new_fp_ratio = len(new_in_target) / len(target_fingerprints) if target_fingerprints else 0.0
            if new_fp_ratio >= self.new_fingerprint_ratio_threshold:
                confidence += 0.3
                patch_indicators.append(f"new_fingerprint_ratio={new_fp_ratio:.2f}")

        confidence = min(confidence, 1.0)

        if confidence >= 0.7:
            status = PatchStatus.PATCHED
        elif confidence >= self.patch_confidence_threshold:
            status = PatchStatus.PARTIALLY_PATCHED
        elif confidence > 0.0:
            status = PatchStatus.PARTIALLY_PATCHED
        else:
            status = PatchStatus.UNPATCHED

        return SBPResult(
            source_id=source_id,
            target_id=target_id,
            similarity=similarity,
            patch_status=status,
            confidence=confidence,
            patch_indicators=patch_indicators,
            security_patterns_found=security_patterns,
            new_fingerprint_ratio=new_fp_ratio,
        )

    def filter_results(
        self,
        results: List[Dict[str, Any]],
        fingerprint_map: Optional[Dict[str, Set[int]]] = None,
        commit_message_map: Optional[Dict[str, List[str]]] = None,
        code_map: Optional[Dict[str, str]] = None,
    ) -> List[Dict[str, Any]]:
        filtered = []
        for r in results:
            source_id = r.get("source_project", r.get("source_module", ""))
            target_id = r.get("target_project", r.get("target_module", ""))
            similarity = r.get("statistics", {}).get("avg_similarity", 0)

            source_fps = (fingerprint_map or {}).get(source_id, set())
            target_fps = (fingerprint_map or {}).get(target_id, set())
            commits = (commit_message_map or {}).get(target_id, [])
            code = (code_map or {}).get(target_id)

            sbp = self.analyze(
                source_id=source_id,
                target_id=target_id,
                similarity=similarity,
                source_fingerprints=source_fps,
                target_fingerprints=target_fps,
                commit_messages=commits,
                source_code=code,
            )

            r_copy = dict(r)
            r_copy["sbp_analysis"] = sbp.to_dict()

            if not sbp.is_safe_derivative:
                filtered.append(r_copy)
            else:
                r_copy["filtered_reason"] = "safe_derivative"
                filtered.append(r_copy)

        return filtered

    def _check_commit_messages(self, messages: List[str]) -> List[str]:
        matches = []
        for msg in messages:
            for pattern in COMMIT_KEYWORDS:
                if pattern.search(msg):
                    matches.append(msg[:100])
                    break
        return matches

    def _check_security_patterns(self, code: str) -> List[str]:
        matches = []
        for pattern, name in SECURITY_CODE_PATTERNS:
            if pattern.search(code):
                matches.append(name)
        return matches
