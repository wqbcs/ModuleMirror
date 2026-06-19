"""
代码差异对比器

使用 difflib 生成匹配代码之间的差异视图，
帮助用户直观理解两段代码的异同。
"""

import difflib
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class DiffLine:
    tag: str
    content: str
    source_line: Optional[int] = None
    target_line: Optional[int] = None


@dataclass
class DiffResult:
    source_name: str
    target_name: str
    lines: List[DiffLine]
    ratio: float
    source_total: int
    target_total: int
    added: int
    removed: int
    unchanged: int


class CodeDiffer:
    """代码差异对比器

    使用 Python difflib.SequenceMatcher 计算行级差异。
    """

    def diff(
        self,
        source_code: str,
        target_code: str,
        source_name: str = "source",
        target_name: str = "target",
        context_lines: int = 3,
    ) -> DiffResult:
        """计算两段代码的差异

        Args:
            source_code: 源代码
            target_code: 目标代码
            source_name: 源模块名
            target_name: 目标模块名
            context_lines: 上下文行数

        Returns:
            DiffResult
        """
        source_lines = source_code.splitlines(keepends=True)
        target_lines = target_code.splitlines(keepends=True)

        matcher = difflib.SequenceMatcher(None, source_lines, target_lines)
        ratio = matcher.ratio()

        diff_lines = []
        added = removed = unchanged = 0

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                for k in range(i2 - i1):
                    diff_lines.append(
                        DiffLine(
                            tag="equal",
                            content=source_lines[i1 + k].rstrip("\n\r"),
                            source_line=i1 + k + 1,
                            target_line=j1 + k + 1,
                        )
                    )
                    unchanged += 1
            elif tag == "replace":
                for k in range(i1, i2):
                    diff_lines.append(
                        DiffLine(
                            tag="remove", content=source_lines[k].rstrip("\n\r"), source_line=k + 1
                        )
                    )
                    removed += 1
                for k in range(j1, j2):
                    diff_lines.append(
                        DiffLine(
                            tag="add", content=target_lines[k].rstrip("\n\r"), target_line=k + 1
                        )
                    )
                    added += 1
            elif tag == "delete":
                for k in range(i1, i2):
                    diff_lines.append(
                        DiffLine(
                            tag="remove", content=source_lines[k].rstrip("\n\r"), source_line=k + 1
                        )
                    )
                    removed += 1
            elif tag == "insert":
                for k in range(j1, j2):
                    diff_lines.append(
                        DiffLine(
                            tag="add", content=target_lines[k].rstrip("\n\r"), target_line=k + 1
                        )
                    )
                    added += 1

        return DiffResult(
            source_name=source_name,
            target_name=target_name,
            lines=diff_lines,
            ratio=ratio,
            source_total=len(source_lines),
            target_total=len(target_lines),
            added=added,
            removed=removed,
            unchanged=unchanged,
        )

    def format_unified_diff(
        self,
        source_code: str,
        target_code: str,
        source_name: str = "source",
        target_name: str = "target",
        context_lines: int = 3,
    ) -> str:
        """生成 unified diff 格式的差异

        Args:
            source_code: 源代码
            target_code: 目标代码

        Returns:
            unified diff 文本
        """
        source_lines = source_code.splitlines(keepends=True)
        target_lines = target_code.splitlines(keepends=True)

        diff = difflib.unified_diff(
            source_lines, target_lines, fromfile=source_name, tofile=target_name, n=context_lines
        )

        return "".join(diff)

    def format_html_diff(self, diff_result: DiffResult) -> str:
        """生成 HTML 格式的差异视图

        Args:
            diff_result: 差异结果

        Returns:
            HTML 片段
        """
        rows = []
        for line in diff_result.lines:
            css_class = f"diff-{line.tag}"
            src_num = f'<td class="line-num">{line.source_line or ""}</td>'
            tgt_num = f'<td class="line-num">{line.target_line or ""}</td>'
            content = line.content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            prefix = ""
            if line.tag == "add":
                prefix = "+"
            elif line.tag == "remove":
                prefix = "-"
            rows.append(
                f'<tr class="{css_class}">{src_num}{tgt_num}'
                f'<td class="diff-content"><span class="diff-prefix">{prefix}</span>{content}</td></tr>'
            )

        stats = (
            f'<div class="diff-stats">'
            f"相似率: {diff_result.ratio * 100:.1f}% | "
            f"源: {diff_result.source_total} 行 | 目标: {diff_result.target_total} 行 | "
            f'<span class="added">+{diff_result.added}</span> '
            f'<span class="removed">-{diff_result.removed}</span> '
            f'<span class="unchanged">={diff_result.unchanged}</span>'
            f"</div>"
        )

        table = (
            f'<table class="diff-table">'
            f"<thead><tr><th>源</th><th>目标</th><th>内容</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table>"
        )

        return stats + table
