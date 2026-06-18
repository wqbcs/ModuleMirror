"""
报告生成器

生成多种格式的相似度检测报告。
使用 Jinja2 模板引擎渲染 HTML 报告。

Author: GitHub 项目代码相似度检测工具
"""

import json
import re
from typing import List, Optional, Dict, Any
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from markupsafe import Markup

from ...models.results import DetectionResult
from ...models.enums import ReportFormat
from ...utils.logger import logger
from ...config.config import DetectionConfig


class ReportSanitizer:
    SENSITIVE_PATTERNS = [
        (r'api[_-]?key\s*[:=]\s*[\'"].+?[\'"]', 'api_key = \'***REDACTED***\''),
        (r'password\s*[:=]\s*[\'"].+?[\'"]', 'password = \'***REDACTED***\''),
        (r'secret\s*[:=]\s*[\'"].+?[\'"]', 'secret = \'***REDACTED***\''),
        (r'token\s*[:=]\s*[\'"].+?[\'"]', 'token = \'***REDACTED***\''),
        (r'credential\s*[:=]\s*[\'"].+?[\'"]', 'credential = \'***REDACTED***\''),
        (r'private[_-]?key\s*[:=]\s*[\'"].+?[\'"]', 'private_key = \'***REDACTED***\''),
        (r'access[_-]?key\s*[:=]\s*[\'"].+?[\'"]', 'access_key = \'***REDACTED***\''),
        (r'secret[_-]?key\s*[:=]\s*[\'"].+?[\'"]', 'secret_key = \'***REDACTED***\''),
        (r'connection[_-]?string\s*[:=]\s*[\'"].+?[\'"]', 'connection_string = \'***REDACTED***\''),
        (r'database[_-]?url\s*[:=]\s*[\'"].+?[\'"]', 'database_url = \'***REDACTED***\''),
        (r'-----BEGIN (?:RSA |DSA |EC )?PRIVATE KEY-----[\s\S]+?-----END', '***REDACTED PRIVATE KEY***'),
    ]

    def sanitize(self, text: str) -> str:
        for pattern, replacement in self.SENSITIVE_PATTERNS:
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        return text


class ReportGenerator:

    def __init__(self, config: DetectionConfig):
        self.config = config
        self.sanitizer = ReportSanitizer()
        template_dir = Path(__file__).parent / "templates"
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=True
        )

    def generate_report(
        self,
        results: List[DetectionResult],
        output_path: Optional[str] = None
    ) -> str:
        if output_path is None:
            output_path = str(self.config.output_path)

        if self.config.report_format == ReportFormat.JSON:
            content = self._generate_json_report(results)
        elif self.config.report_format == ReportFormat.HTML:
            content = self._generate_html_report(results)
        elif self.config.report_format == ReportFormat.MARKDOWN:
            content = self._generate_markdown_report(results)
        else:
            content = self._generate_markdown_report(results)

        content = self.sanitizer.sanitize(content)

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        ext = self.config.report_format.value
        file_path = path if path.suffix else path.with_suffix(f'.{ext}')

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        logger.info(f"报告已生成: {file_path}")
        return str(file_path)

    def _generate_markdown_report(self, results: List[DetectionResult]) -> str:
        lines = [
            "# GitHub 项目代码相似度检测报告",
            "",
            f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "---",
            ""
        ]

        for i, result in enumerate(results, 1):
            lines.extend(self._format_result_markdown(result, i))

        lines.extend([
            "---",
            "",
            "**免责声明**: 本报告仅供参考，不作为法律依据。",
            ""
        ])

        return '\n'.join(lines)

    def _format_result_markdown(
        self,
        result: DetectionResult,
        index: int
    ) -> List[str]:
        lines = [
            f"## 检测 {index}: `{result.source_project}` ↔ `{result.target_project}`",
            "",
            "### 统计摘要",
            "",
            "| 指标 | 值 |",
            "|------|-----|",
            f"| 总匹配数 | {len(result.matches)} |",
            f"| 平均相似度 | {result.statistics.get('avg_similarity', 0):.2f}% |",
            f"| 最高相似度 | {result.statistics.get('max_similarity', 0):.2f}% |",
            f"| 相似度 ≥ 90% | {result.statistics.get('count_90', 0)} 个 |",
            f"| 相似度 80-90% | {result.statistics.get('count_80', 0)} 个 |",
            f"| 相似度 70-80% | {result.statistics.get('count_70', 0)} 个 |",
            ""
        ]

        if result.matches:
            lines.extend([
                "### 详细匹配列表",
                "",
                "| 序号 | 源模块 | 目标模块 | 相似度 | 建议 |",
                "|------|--------|----------|--------|------|"
            ])

            for j, match in enumerate(result.matches, 1):
                lines.append(
                    f"| {j} | "
                    f"`{match.source_module_id}` | "
                    f"`{match.target_module_id}` | "
                    f"**{match.similarity:.2f}%** | "
                    f"{match.reuse_suggestion.value} |"
                )

            lines.append("")

        return lines

    def _generate_json_report(self, results: List[DetectionResult]) -> str:
        data = {
            'generated_at': datetime.now().isoformat(),
            'results': []
        }

        for result in results:
            result_data = {
                'source_project': result.source_project,
                'target_project': result.target_project,
                'statistics': result.statistics,
                'matches': [
                    {
                        'source_module_id': m.source_module_id,
                        'target_module_id': m.target_module_id,
                        'similarity': m.similarity,
                        'winnowing_overlap': m.winnowing_overlap,
                        'winnowing_union': m.winnowing_union,
                        'ast_similarity': m.ast_similarity,
                        'reuse_suggestion': m.reuse_suggestion.value
                    }
                    for m in result.matches
                ]
            }
            data['results'].append(result_data)

        return json.dumps(data, ensure_ascii=False, indent=2)

    def _generate_html_report(self, results: List[DetectionResult]) -> str:
        all_matches_data = self._build_matches_data(results)
        project_pairs = self._build_project_pairs(results)
        heatmap_data = self._build_heatmap_data(results)

        template = self.jinja_env.get_template("report.html.j2")
        html = template.render(
            generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            matches_data=Markup(json.dumps(all_matches_data, ensure_ascii=False)),  # nosec B704: JSON output is already escaped by json.dumps
            heatmap_data=Markup(json.dumps(heatmap_data, ensure_ascii=False)),  # nosec B704: JSON output is already escaped by json.dumps
            project_pairs=project_pairs,
        )

        return html

    def _build_matches_data(self, results: List[DetectionResult]) -> List[Dict[str, Any]]:
        all_matches_data = []
        for result in results:
            for match in result.matches:
                snippet = {}
                source_code = ""
                target_code = ""
                if match.matched_code_snippet:
                    s = match.matched_code_snippet
                    snippet = {
                        "source_file": s.get("source_file", ""),
                        "source_lines": s.get("source_lines", ""),
                        "target_file": s.get("target_file", ""),
                        "target_lines": s.get("target_lines", ""),
                    }
                    if "ast_verified" in s:
                        snippet["ast_verified"] = s["ast_verified"]
                    if "ast_node_sim" in s:
                        snippet["ast_node_sim"] = s["ast_node_sim"]
                    if "ast_struct_sim" in s:
                        snippet["ast_struct_sim"] = s["ast_struct_sim"]
                    source_code = s.get("source_code", "")
                    target_code = s.get("target_code", "")
                    max_lines = self.config.max_diff_lines if hasattr(self.config, 'max_diff_lines') else 200
                    source_code = self._truncate_code(source_code, max_lines)
                    target_code = self._truncate_code(target_code, max_lines)
                all_matches_data.append({
                    "source_project": result.source_project,
                    "target_project": result.target_project,
                    "source_module": match.source_module_id,
                    "target_module": match.target_module_id,
                    "similarity": round(match.similarity, 2),
                    "winnowing_overlap": match.winnowing_overlap,
                    "ast_similarity": round(match.ast_similarity, 2) if match.ast_similarity else None,
                    "suggestion": match.reuse_suggestion.value,
                    "snippet": snippet,
                    "source_code": source_code,
                    "target_code": target_code,
                })
        return all_matches_data

    @staticmethod
    def _build_project_pairs(results: List[DetectionResult]) -> List[Dict[str, Any]]:
        pairs = []
        for result in results:
            pairs.append({
                "source": result.source_project,
                "target": result.target_project,
                "match_count": len(result.matches),
                "avg_sim": round(result.statistics.get('avg_similarity', 0), 1),
                "max_sim": round(result.statistics.get('max_similarity', 0), 1),
            })
        return pairs

    @staticmethod
    def _build_heatmap_data(results: List[DetectionResult]) -> Dict[str, int]:
        heatmap = {}
        for result in results:
            key = f"{result.source_project}-{result.target_project}"
            avg = round(result.statistics.get('avg_similarity', 0))
            heatmap[key] = avg
        return heatmap

    @staticmethod
    def _truncate_code(code: str, max_lines: int) -> str:
        if not code:
            return code
        lines = code.split('\n')
        if len(lines) <= max_lines:
            return code
        return '\n'.join(lines[:max_lines]) + f'\n... (截断，共 {len(lines)} 行)'
