"""
语义Diff代码差异展示

参考 sem (semantic diff) 的实体级变更分析思路:
不按文本行做diff，而是按代码实体(函数/类/变量)做语义级差异对比。

核心思路:
1. 用tree-sitter提取源码和目标码的代码实体
2. 按实体类型+名称匹配
3. 对匹配的实体做内部diff(新增/删除/修改参数/修改逻辑)
4. 生成语义级差异描述

Author: ModuleMirror
"""

import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum


class ChangeType(Enum):
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
    RENAMED = "renamed"
    UNCHANGED = "unchanged"
    MOVED = "moved"


@dataclass
class CodeEntity:
    name: str
    entity_type: str
    start_line: int
    end_line: int
    source: str
    params: List[str] = field(default_factory=list)
    body_hash: str = ""

    def __post_init__(self):
        if not self.body_hash and self.source:
            self.body_hash = self._compute_hash()

    def _compute_hash(self) -> str:
        normalized = re.sub(r"\s+", "", self.source)
        return hex(hash(normalized) & 0xFFFFFFFF)[2:]


@dataclass
class SemanticChange:
    entity_name: str
    entity_type: str
    change_type: ChangeType
    source_range: Optional[Tuple[int, int]] = None
    target_range: Optional[Tuple[int, int]] = None
    description: str = ""
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_name": self.entity_name,
            "entity_type": self.entity_type,
            "change_type": self.change_type.value,
            "source_range": self.source_range,
            "target_range": self.target_range,
            "description": self.description,
            "details": self.details,
        }


class CodeEntityExtractor:
    def extract(self, code: str, language: str = "python") -> List[CodeEntity]:
        if language == "python":
            return self._extract_python(code)
        return self._extract_generic(code)

    def _extract_python(self, code: str) -> List[CodeEntity]:
        entities = []
        lines = code.split("\n")
        i = 0

        while i < len(lines):
            line = lines[i].strip()

            if line.startswith("def "):
                name, params, end_line = self._parse_function(lines, i)
                source = "\n".join(lines[i:end_line])
                entities.append(
                    CodeEntity(
                        name=name,
                        entity_type="function",
                        start_line=i + 1,
                        end_line=end_line,
                        source=source,
                        params=params,
                    )
                )
                i = end_line
                continue

            if line.startswith("class "):
                name, end_line = self._parse_class(lines, i)
                source = "\n".join(lines[i:end_line])
                entities.append(
                    CodeEntity(
                        name=name,
                        entity_type="class",
                        start_line=i + 1,
                        end_line=end_line,
                        source=source,
                    )
                )
                i = end_line
                continue

            i += 1

        return entities

    def _extract_generic(self, code: str) -> List[CodeEntity]:
        entities = []
        lines = code.split("\n")

        func_patterns = [
            (
                re.compile(
                    r"^\s*(?:public|private|protected)?\s*(?:static\s+)?(?:\w+\s+)+(\w+)\s*\(([^)]*)\)\s*\{?"
                ),
                "function",
            ),
            (re.compile(r"^\s*func\s+(\w+)\s*\(([^)]*)\)"), "function"),
            (re.compile(r"^\s*fn\s+(\w+)\s*\(([^)]*)\)"), "function"),
            (re.compile(r"^\s*function\s+(\w+)\s*\(([^)]*)\)"), "function"),
        ]

        class_patterns = [
            (re.compile(r"^\s*(?:public\s+)?class\s+(\w+)"), "class"),
            (re.compile(r"^\s*struct\s+(\w+)"), "class"),
            (re.compile(r"^\s*interface\s+(\w+)"), "class"),
            (re.compile(r"^\s*type\s+(\w+)\s+struct"), "class"),
        ]

        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue

            for pattern, etype in func_patterns:
                m = pattern.match(stripped)
                if m:
                    name = m.group(1)
                    params = (
                        [p.strip() for p in m.group(2).split(",") if p.strip()]
                        if m.lastindex >= 2
                        else []
                    )
                    entities.append(
                        CodeEntity(
                            name=name,
                            entity_type=etype,
                            start_line=i + 1,
                            end_line=i + 1,
                            source=stripped,
                            params=params,
                        )
                    )
                    break

            for pattern, etype in class_patterns:
                m = pattern.match(stripped)
                if m:
                    entities.append(
                        CodeEntity(
                            name=m.group(1),
                            entity_type=etype,
                            start_line=i + 1,
                            end_line=i + 1,
                            source=stripped,
                        )
                    )
                    break

        return entities

    def _parse_function(self, lines: List[str], start: int) -> Tuple[str, List[str], int]:
        header = lines[start].strip()
        name_match = re.search(r"def\s+(\w+)", header)
        name = name_match.group(1) if name_match else f"func_{start}"

        params_match = re.search(r"\(([^)]*)\)", header)
        params = []
        if params_match:
            raw = params_match.group(1)
            params = [
                p.strip().split(":")[0].split("=")[0].strip() for p in raw.split(",") if p.strip()
            ]
            params = [p for p in params if p and p != "self"]

        end = self._find_block_end(lines, start)
        return name, params, end

    def _parse_class(self, lines: List[str], start: int) -> Tuple[str, int]:
        header = lines[start].strip()
        name_match = re.search(r"class\s+(\w+)", header)
        name = name_match.group(1) if name_match else f"class_{start}"
        end = self._find_block_end(lines, start)
        return name, end

    def _find_block_end(self, lines: List[str], start: int) -> int:
        if start >= len(lines):
            return start + 1

        first_line = lines[start]
        base_indent = len(first_line) - len(first_line.lstrip())

        end = start + 1
        while end < len(lines):
            if lines[end].strip() == "":
                end += 1
                continue
            current_indent = len(lines[end]) - len(lines[end].lstrip())
            if current_indent <= base_indent and lines[end].strip():
                break
            end += 1

        while end > start + 1 and lines[end - 1].strip() == "":
            end -= 1

        return end


class SemanticDiffer:
    def __init__(self):
        self._extractor = CodeEntityExtractor()

    def diff(
        self,
        source_code: str,
        target_code: str,
        source_language: str = "python",
        target_language: str = "python",
    ) -> List[SemanticChange]:
        source_entities = self._extractor.extract(source_code, source_language)
        target_entities = self._extractor.extract(target_code, target_language)

        source_map = {e.name: e for e in source_entities}
        target_map = {e.name: e for e in target_entities}

        source_names = set(source_map.keys())
        target_names = set(target_map.keys())

        changes = []

        for name in source_names - target_names:
            se = source_map[name]
            renamed = self._find_renamed(
                se,
                target_map,
                source_names - target_names,
                existing_source_names=source_names & target_names,
            )
            if renamed:
                te = target_map[renamed]
                changes.append(
                    SemanticChange(
                        entity_name=f"{name} → {renamed}",
                        entity_type=se.entity_type,
                        change_type=ChangeType.RENAMED,
                        source_range=(se.start_line, se.end_line),
                        target_range=(te.start_line, te.end_line),
                        description=f"{se.entity_type} '{name}' renamed to '{renamed}'",
                        details={"original_name": name, "new_name": renamed},
                    )
                )
            else:
                changes.append(
                    SemanticChange(
                        entity_name=name,
                        entity_type=se.entity_type,
                        change_type=ChangeType.REMOVED,
                        source_range=(se.start_line, se.end_line),
                        description=f"{se.entity_type} '{name}' removed",
                    )
                )

        for name in target_names - source_names:
            te = target_map[name]
            if not any(
                c.change_type == ChangeType.RENAMED and name in c.entity_name for c in changes
            ):
                changes.append(
                    SemanticChange(
                        entity_name=name,
                        entity_type=te.entity_type,
                        change_type=ChangeType.ADDED,
                        target_range=(te.start_line, te.end_line),
                        description=f"{te.entity_type} '{name}' added",
                    )
                )

        for name in source_names & target_names:
            se = source_map[name]
            te = target_map[name]

            if se.body_hash == te.body_hash:
                if se.start_line != te.start_line:
                    changes.append(
                        SemanticChange(
                            entity_name=name,
                            entity_type=se.entity_type,
                            change_type=ChangeType.MOVED,
                            source_range=(se.start_line, se.end_line),
                            target_range=(te.start_line, te.end_line),
                            description=f"{se.entity_type} '{name}' moved from line {se.start_line} to {te.start_line}",
                        )
                    )
                continue

            details = {}
            if se.params != te.params:
                details["param_changes"] = self._diff_params(se.params, te.params)

            changes.append(
                SemanticChange(
                    entity_name=name,
                    entity_type=se.entity_type,
                    change_type=ChangeType.MODIFIED,
                    source_range=(se.start_line, se.end_line),
                    target_range=(te.start_line, te.end_line),
                    description=f"{se.entity_type} '{name}' modified",
                    details=details,
                )
            )

        return changes

    def _find_renamed(
        self,
        source_entity: CodeEntity,
        target_map: Dict[str, CodeEntity],
        excluded_names: set,
        existing_source_names: set = None,
    ) -> Optional[str]:
        existing = existing_source_names or set()
        for name, te in target_map.items():
            if name in excluded_names:
                continue
            if name in existing:
                continue
            if te.entity_type != source_entity.entity_type:
                continue
            if te.body_hash == source_entity.body_hash:
                return name
            param_sim = self._param_similarity(source_entity.params, te.params)
            if param_sim > 0.7 and te.entity_type == source_entity.entity_type:
                return name
        return None

    @staticmethod
    def _param_similarity(params1: List[str], params2: List[str]) -> float:
        if not params1 and not params2:
            return 1.0
        if not params1 or not params2:
            return 0.0
        common = set(params1) & set(params2)
        union = set(params1) | set(params2)
        return len(common) / len(union) if union else 0.0

    @staticmethod
    def _diff_params(old_params: List[str], new_params: List[str]) -> Dict[str, Any]:
        old_set = set(old_params)
        new_set = set(new_params)
        return {
            "added": list(new_set - old_set),
            "removed": list(old_set - new_set),
            "unchanged": list(old_set & new_set),
        }

    def format_changes(self, changes: List[SemanticChange]) -> str:
        if not changes:
            return "无差异"

        lines = []
        change_icons = {
            ChangeType.ADDED: "+",
            ChangeType.REMOVED: "-",
            ChangeType.MODIFIED: "~",
            ChangeType.RENAMED: ">",
            ChangeType.MOVED: "^",
            ChangeType.UNCHANGED: "=",
        }

        for c in changes:
            icon = change_icons.get(c.change_type, "?")
            lines.append(f"  {icon} {c.description}")

        return "\n".join(lines)
