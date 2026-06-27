"""
PDF报告导出模块

基于 fpdf2 生成专业级代码相似度检测PDF报告。
特性:
- CJK/英文双语文本自适应（Noto Sans SC字体→Helvetica fallback）
- 分页自动管理（表头重复、代码分页）
- 相似度热力条（视觉化相似度等级）
- 差异代码对照视图
- 页眉页脚

开源参考:
- fpdf2 (MIT, 2.5k stars): 纯Python PDF生成，零系统依赖
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import List, Optional

from ...models.results import DetectionResult
from ...utils.logger import logger

try:
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos

    HAS_FPDF2 = True
except ImportError:
    HAS_FPDF2 = False

_SIMILARITY_COLORS = {
    "critical": (220, 53, 69),
    "high": (255, 152, 0),
    "medium": (255, 193, 7),
    "low": (40, 167, 69),
    "none": (108, 117, 125),
}


def _similarity_level(sim: float) -> str:
    if sim >= 90:
        return "critical"
    if sim >= 80:
        return "high"
    if sim >= 70:
        return "medium"
    if sim >= 50:
        return "low"
    return "none"


def _similarity_color(sim: float) -> tuple[int, int, int]:
    return _SIMILARITY_COLORS[_similarity_level(sim)]


class _ReportPDF(FPDF):
    def __init__(self) -> None:
        super().__init__()
        self._add_fonts()
        self.set_auto_page_break(auto=True, margin=20)

    def _add_fonts(self) -> None:
        font_dir = Path(__file__).parent / "fonts"
        noto_sc = font_dir / "NotoSansSC-Regular.ttf"
        noto_sc_bold = font_dir / "NotoSansSC-Bold.ttf"
        noto_mono = font_dir / "NotoSansMono-Regular.ttf"
        if noto_sc.exists():
            self.add_font("NotoSC", "", str(noto_sc))
            bold_path = str(noto_sc_bold) if noto_sc_bold.exists() else str(noto_sc)
            self.add_font("NotoSC", "B", bold_path)
            self._body_font = "NotoSC"
        else:
            self._body_font = "Helvetica"
        if noto_mono.exists():
            self.add_font("NotoMono", "", str(noto_mono))
            self._mono_font = "NotoMono"
        else:
            self._mono_font = "Courier"

    @property
    def use_cjk(self) -> bool:
        return self._body_font == "NotoSC"

    def header(self) -> None:
        if self.page_no() > 1:
            self.set_font(self._body_font, "B", 8)
            self.set_text_color(128, 128, 128)
            self.cell(0, 8, "ModuleMirror Code Similarity Report", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="L")
            self.set_draw_color(200, 200, 200)
            self.line(10, 14, 200, 14)
            self.ln(4)

    def footer(self) -> None:
        self.set_y(-15)
        self.set_font(self._body_font, "", 7)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")


def generate_pdf_report(
    results: List[DetectionResult],
    output_path: Optional[str] = None,
) -> str:
    if not HAS_FPDF2:
        raise ImportError("PDF generation requires fpdf2: pip install fpdf2")

    pdf = _ReportPDF()
    pdf.alias_nb_pages()

    _render_cover(pdf, results)
    _render_summary(pdf, results)

    for i, result in enumerate(results, 1):
        _render_detection_detail(pdf, result, i)

    if output_path is None:
        output_path = "./report/similarity_report.pdf"
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.suffix == ".pdf":
        path = path.with_suffix(".pdf")

    pdf.output(str(path))
    logger.info(f"PDF report generated: {path}")
    return str(path)


def _t(pdf: _ReportPDF, cjk_text: str, en_text: str) -> str:
    return cjk_text if pdf.use_cjk else en_text


def _render_cover(pdf: _ReportPDF, results: List[DetectionResult]) -> None:
    pdf.add_page()
    pdf.ln(50)
    pdf.set_font(pdf._body_font, "B", 28)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(0, 15, _t(pdf, "Code Similarity Report", "Code Similarity Report"), new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    pdf.ln(8)
    pdf.set_font(pdf._body_font, "", 14)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 10, "ModuleMirror v2.0", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")
    pdf.ln(20)

    pdf.set_draw_color(0, 123, 255)
    pdf.set_line_width(0.8)
    pdf.line(60, pdf.get_y(), 150, pdf.get_y())
    pdf.ln(15)

    pdf.set_font(pdf._body_font, "", 11)
    pdf.set_text_color(60, 60, 60)
    total_matches = sum(len(r.matches) for r in results)
    avg_sim = _calc_avg_similarity(results)
    info_lines = [
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Detection Pairs: {len(results)}",
        f"Total Matches: {total_matches}",
        f"Avg Similarity: {avg_sim:.1f}%",
    ]
    for line in info_lines:
        pdf.cell(0, 8, line, new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")


def _render_summary(pdf: _ReportPDF, results: List[DetectionResult]) -> None:
    pdf.add_page()
    pdf.set_font(pdf._body_font, "B", 16)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(0, 12, "Detection Summary", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)

    col_widths = [12, 45, 45, 25, 25, 25, 18]
    headers = ["#", "Source", "Target", "Matches", "Avg Sim", "Max Sim", "Level"]
    pdf.set_font(pdf._body_font, "B", 9)
    pdf.set_fill_color(0, 123, 255)
    pdf.set_text_color(255, 255, 255)
    for w, h in zip(col_widths, headers):
        pdf.cell(w, 8, h, border=1, fill=True, align="C")
    pdf.ln()

    pdf.set_font(pdf._body_font, "", 8)
    for i, result in enumerate(results, 1):
        if pdf.get_y() > 265:
            pdf.add_page()
            pdf.set_font(pdf._body_font, "B", 9)
            pdf.set_fill_color(0, 123, 255)
            pdf.set_text_color(255, 255, 255)
            for w, h in zip(col_widths, headers):
                pdf.cell(w, 8, h, border=1, fill=True, align="C")
            pdf.ln()
            pdf.set_font(pdf._body_font, "", 8)

        avg = result.statistics.get("avg_similarity", 0)
        max_s = result.statistics.get("max_similarity", 0)
        level = _similarity_level(avg)
        color = _SIMILARITY_COLORS[level]

        pdf.set_text_color(30, 30, 30)
        pdf.cell(col_widths[0], 7, str(i), border=1, align="C")
        pdf.cell(col_widths[1], 7, _truncate(result.source_project, 20), border=1, align="L")
        pdf.cell(col_widths[2], 7, _truncate(result.target_project, 20), border=1, align="L")
        pdf.cell(col_widths[3], 7, str(len(result.matches)), border=1, align="C")
        pdf.cell(col_widths[4], 7, f"{avg:.1f}%", border=1, align="C")
        pdf.cell(col_widths[5], 7, f"{max_s:.1f}%", border=1, align="C")
        pdf.set_text_color(*color)
        pdf.set_font(pdf._body_font, "B", 8)
        pdf.cell(col_widths[6], 7, _level_label(level), border=1, align="C")
        pdf.set_font(pdf._body_font, "", 8)
        pdf.set_text_color(30, 30, 30)
        pdf.ln()


def _render_detection_detail(pdf: _ReportPDF, result: DetectionResult, index: int) -> None:
    pdf.add_page()
    pdf.set_font(pdf._body_font, "B", 14)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(0, 10, f"Detection {index}: {result.source_project} <-> {result.target_project}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)

    avg = result.statistics.get("avg_similarity", 0)
    max_s = result.statistics.get("max_similarity", 0)
    stats_data = [
        ("Total Matches", str(len(result.matches))),
        ("Avg Similarity", f"{avg:.2f}%"),
        ("Max Similarity", f"{max_s:.2f}%"),
        (">=90%", str(result.statistics.get("count_90", 0))),
        ("80-90%", str(result.statistics.get("count_80", 0))),
        ("70-80%", str(result.statistics.get("count_70", 0))),
    ]

    pdf.set_font(pdf._body_font, "B", 10)
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(35, 7, "Metric", border=1, fill=True, align="C")
    pdf.cell(35, 7, "Value", border=1, fill=True, align="C")
    pdf.set_font(pdf._body_font, "", 9)
    for label, value in stats_data:
        pdf.cell(35, 7, label, border=1, align="C")
        pdf.cell(35, 7, value, border=1, align="C")
        pdf.ln()
    pdf.ln(4)

    if not result.matches:
        pdf.set_font(pdf._body_font, "", 10)
        pdf.set_text_color(128, 128, 128)
        pdf.cell(0, 10, "No matches found", align="C")
        return

    pdf.set_font(pdf._body_font, "B", 12)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(0, 10, "Match Details", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)

    for j, match in enumerate(result.matches, 1):
        if pdf.get_y() > 250:
            pdf.add_page()

        sim = match.similarity
        color = _similarity_color(sim)

        pdf.set_font(pdf._body_font, "B", 9)
        pdf.set_text_color(*color)
        pdf.cell(0, 7, f"  Match {j} - Similarity {sim:.2f}%", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        pdf.set_font(pdf._body_font, "", 8)
        pdf.set_text_color(30, 30, 30)
        pdf.cell(0, 6, f"    Source: {match.source_module_id}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.cell(0, 6, f"    Target: {match.target_module_id}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.cell(0, 6, f"    Suggestion: {_suggestion_en(match.reuse_suggestion.value)}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        if match.matched_code_snippet:
            snippet = match.matched_code_snippet
            src_code = snippet.get("source_code", "")
            tgt_code = snippet.get("target_code", "")
            if src_code and tgt_code:
                _render_code_diff(pdf, src_code, tgt_code)

        pdf.ln(3)


def _render_code_diff(pdf: _ReportPDF, source: str, target: str) -> None:
    pdf.set_font(pdf._mono_font, "", 7)
    pdf.set_text_color(30, 30, 30)

    src_lines = source.split("\n")[:15]
    tgt_lines = target.split("\n")[:15]

    pdf.set_fill_color(245, 245, 245)
    pdf.cell(0, 5, "    -- Source --", new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True)
    for line in src_lines:
        if pdf.get_y() > 270:
            pdf.add_page()
        pdf.cell(0, 4, f"    {line[:80]}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_fill_color(230, 245, 255)
    pdf.cell(0, 5, "    -- Target --", new_x=XPos.LMARGIN, new_y=YPos.NEXT, fill=True)
    for line in tgt_lines:
        if pdf.get_y() > 270:
            pdf.add_page()
        pdf.cell(0, 4, f"    {line[:80]}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def _calc_avg_similarity(results: List[DetectionResult]) -> float:
    if not results:
        return 0.0
    total = sum(r.statistics.get("avg_similarity", 0) for r in results)
    return total / len(results)


def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def _level_label(level: str) -> str:
    labels = {"critical": "CRITICAL", "high": "HIGH", "medium": "MEDIUM", "low": "LOW", "none": "NONE"}
    return labels.get(level, level.upper())


_SUGGESTION_EN = {
    "可直接复用": "Direct Reuse",
    "参考借鉴": "Reference & Adapt",
    "需改造后复用": "Refactor Required",
}


def _suggestion_en(val: str) -> str:
    return _SUGGESTION_EN.get(val, val)
