"""
ModuleMirror Textual TUI — 专业级终端交互界面

基于 Textual 框架构建的交互式终端应用，提供：
- 检测配置向导（交互式选择参数）
- 指纹库浏览器（树形浏览项目和模块）
- 检测结果查看器（排序、筛选、详情展开）
- 系统仪表盘（状态概览）

开源参考:
- Textual (Textualize): 36.4k stars, MIT, Python TUI框架顶配
  https://github.com/Textualize/textual
- Trogon: 2.8k stars, Click CLI自动TUI生成
  https://github.com/Textualize/trogon
- textual-file-browser: 文件浏览组件
  https://github.com/AlexWjChen/textual-file-browser
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    ProgressBar,
    Select,
    TabbedContent,
    TabPane,
    Tree,
)

try:
    from ..config.config import DetectionConfig
    from ..models.enums import ModuleType, ReportFormat
    from ..core import DetectionPipeline
    from ..infrastructure.storage.fingerprint_db import FingerprintDB

    _CORE_AVAILABLE = True
except ImportError:
    _CORE_AVAILABLE = False


CSS = """
Screen {
    background: $surface;
}

#main-container {
    height: 1fr;
}

.tab-title {
    text-style: bold;
    color: $primary;
    padding: 1 2;
}

.dashboard-stats {
    height: auto;
    padding: 1 2;
}

.stat-card {
    background: $panel;
    border: tall $primary;
    padding: 1 2;
    margin: 0 1;
    height: auto;
    min-width: 20;
}

.stat-label {
    color: $text-muted;
    text-style: italic;
}

.stat-value {
    text-style: bold;
    color: $accent;
}

#wizard-form {
    padding: 1 2;
}

.wizard-field {
    margin: 1 0;
    height: auto;
}

.wizard-label {
    color: $primary;
    text-style: bold;
    margin-bottom: 0;
}

#run-button {
    margin-top: 1;
}

#progress-area {
    height: auto;
    padding: 1 2;
}

.result-row {
    height: auto;
    padding: 0 1;
}

.result-high {
    color: $success;
}

.result-medium {
    color: $warning;
}

.result-low {
    color: $error;
}

#result-detail {
    padding: 1 2;
    height: auto;
    border: tall $accent;
    margin: 1 2;
}
"""


class DashboardScreen(Screen):
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("d", "show_dashboard", "Dashboard"),
        Binding("w", "show_wizard", "Wizard"),
        Binding("r", "show_results", "Results"),
        Binding("b", "show_browser", "Browser"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with TabbedContent():
            with TabPane("Dashboard", id="tab-dashboard"):
                yield self._compose_dashboard()
            with TabPane("Detect Wizard", id="tab-wizard"):
                yield self._compose_wizard()
            with TabPane("Results", id="tab-results"):
                yield self._compose_results()
            with TabPane("Fingerprint DB", id="tab-browser"):
                yield self._compose_browser()
        yield Footer()

    def _compose_dashboard(self) -> ComposeResult:
        with VerticalScroll(id="dashboard-scroll"):
            with Horizontal(classes="dashboard-stats"):
                with Vertical(classes="stat-card"):
                    yield Label("Version", classes="stat-label")
                    yield Label("2.0.0", classes="stat-value", id="stat-version")
                with Vertical(classes="stat-card"):
                    yield Label("Python", classes="stat-label")
                    yield Label(f"{sys.version.split()[0]}", classes="stat-value", id="stat-python")
                with Vertical(classes="stat-card"):
                    yield Label("Platform", classes="stat-label")
                    yield Label(sys.platform, classes="stat-value", id="stat-platform")
                with Vertical(classes="stat-card"):
                    yield Label("Rust Backend", classes="stat-label")
                    yield Label(self._rust_status(), classes="stat-value", id="stat-rust")
            yield Label("", id="db-stats-area")

    def _compose_wizard(self) -> ComposeResult:
        with VerticalScroll(id="wizard-form"):
            yield Label("Target Project", classes="wizard-label")
            yield Input(placeholder="GitHub URL or local path", id="input-target")
            yield Label("Candidate Projects", classes="wizard-label")
            yield Input(placeholder="Comma-separated URLs or paths", id="input-candidates")
            yield Label("Granularity", classes="wizard-label")
            yield Select(
                [("File", "file"), ("Function", "function"), ("Class", "class")],
                value="function",
                id="select-granularity",
            )
            yield Label("Language", classes="wizard-label")
            yield Select(
                [("Python", "python"), ("JavaScript", "javascript"), ("Java", "java"), ("TypeScript", "typescript")],
                value="python",
                id="select-language",
            )
            yield Label("Similarity Threshold", classes="wizard-label")
            yield Input(value="70", id="input-threshold")
            yield Label("Report Format", classes="wizard-label")
            yield Select(
                [("HTML", "html"), ("JSON", "json"), ("Markdown", "markdown")],
                value="html",
                id="select-format",
            )
            yield Label("Parallelism", classes="wizard-label")
            yield Input(value="4", id="input-parallelism")
            yield Button("Run Detection", variant="primary", id="run-button")
            yield Label("", id="progress-area")
            yield ProgressBar(id="detect-progress")

    def _compose_results(self) -> ComposeResult:
        with VerticalScroll(id="results-scroll"):
            table = DataTable(id="results-table")
            table.add_columns("Source", "Target", "Similarity", "Winnowing", "AST", "Suggestion")
            yield table
            yield Label("", id="result-detail")

    def _compose_browser(self) -> ComposeResult:
        with Horizontal(id="browser-container"):
            with Vertical(id="browser-tree-area"):
                yield Tree("Fingerprint DB", id="db-tree")
            with Vertical(id="browser-detail-area"):
                yield Label("Select a project or module to view details", id="browser-detail")

    @staticmethod
    def _rust_status() -> str:
        try:
            from ..utils.rust_backend import RUST_AVAILABLE

            return "Available" if RUST_AVAILABLE else "Not Available"
        except ImportError:
            return "Not Available"

    def on_mount(self) -> None:
        self._load_db_stats()
        self._load_db_tree()

    def _load_db_stats(self) -> None:
        if not _CORE_AVAILABLE:
            return
        default_db = Path("./fingerprint_db.sqlite")
        if not default_db.exists():
            self.query_one("#db-stats-area", Label).update(
                "[dim]No fingerprint database found at ./fingerprint_db.sqlite[/dim]"
            )
            return
        try:
            db = FingerprintDB(str(default_db))
            stats = db.get_stats()
            lines = ["[bold]Fingerprint DB Statistics[/bold]"]
            for k, v in stats.items():
                lines.append(f"  {k}: [cyan]{v}[/cyan]")
            self.query_one("#db-stats-area", Label).update("\n".join(lines))
        except Exception as e:
            self.query_one("#db-stats-area", Label).update(f"[red]Error loading stats: {e}[/red]")

    def _load_db_tree(self) -> None:
        if not _CORE_AVAILABLE:
            return
        default_db = Path("./fingerprint_db.sqlite")
        tree = self.query_one("#db-tree", Tree)
        if not default_db.exists():
            tree.root.add_leaf("[dim]No database found[/dim]")
            return
        try:
            db = FingerprintDB(str(default_db))
            projects = db.list_projects()
            if not projects:
                tree.root.add_leaf("[dim]Empty database[/dim]")
                return
            for project in projects:
                name = project.name if hasattr(project, "name") else str(project)
                proj_node = tree.root.add(f"📁 {name}")
                try:
                    modules = db.get_project_modules(
                        project.id if hasattr(project, "id") else project
                    )
                    for module in modules[:20]:
                        mod_path = module.file_path if hasattr(module, "file_path") else str(module)
                        proj_node.add_leaf(f"📄 {mod_path}")
                    if len(modules) > 20:
                        proj_node.add_leaf(f"... +{len(modules) - 20} more")
                except Exception:
                    pass
        except Exception as e:
            tree.root.add_leaf(f"[red]Error: {e}[/red]")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "run-button":
            self._run_detection()

    def _run_detection(self) -> None:
        if not _CORE_AVAILABLE:
            self.query_one("#progress-area", Label).update("[red]Core module not available[/red]")
            return

        target = self.query_one("#input-target", Input).value.strip()
        candidates_str = self.query_one("#input-candidates", Input).value.strip()
        granularity = self.query_one("#select-granularity", Select).value
        language = self.query_one("#select-language", Select).value
        threshold_str = self.query_one("#input-threshold", Input).value.strip()
        report_format = self.query_one("#select-format", Select).value
        parallelism_str = self.query_one("#input-parallelism", Input).value.strip()

        if not target or not candidates_str:
            self.query_one("#progress-area", Label).update("[red]Target and candidates are required[/red]")
            return

        try:
            threshold = float(threshold_str)
            parallelism = int(parallelism_str)
        except ValueError:
            self.query_one("#progress-area", Label).update("[red]Invalid threshold or parallelism value[/red]")
            return

        granularity_map = {"file": ModuleType.FILE, "function": ModuleType.FUNCTION, "class": ModuleType.CLASS}
        format_map = {"json": ReportFormat.JSON, "html": ReportFormat.HTML, "markdown": ReportFormat.MARKDOWN}

        config = DetectionConfig(
            module_granularity=granularity_map.get(granularity, ModuleType.FUNCTION),
            supported_languages=[language] if language else ["python"],
            similarity_threshold=threshold,
            report_format=format_map.get(report_format, ReportFormat.HTML),
            parallelism=parallelism,
        )

        candidates = [c.strip() for c in candidates_str.split(",") if c.strip()]
        progress_label = self.query_one("#progress-area", Label)
        progress_bar = self.query_one("#detect-progress", ProgressBar)

        progress_label.update("[cyan]Starting detection...[/cyan]")
        progress_bar.update(progress=0)

        pipeline = DetectionPipeline(config)

        def progress_callback(current: int, total: int, message: str = "") -> None:
            if total > 0:
                progress_bar.update(progress=int(current / total * 100))
            if message:
                progress_label.update(f"[cyan]{message}[/cyan]")

        async def _run() -> None:
            try:
                results = pipeline.detect(target, candidates, progress_callback)
                progress_bar.update(progress=100)
                progress_label.update(f"[green]Detection complete: {len(results)} results found[/green]")
                self._display_results(results)
            except Exception as e:
                progress_label.update(f"[red]Error: {e}[/red]")

        asyncio.create_task(_run())

    def _display_results(self, results: list) -> None:
        table = self.query_one("#results-table", DataTable)
        table.clear()
        for r in results:
            sim = r.similarity
            sim_str = f"{sim:.1f}%"
            suggestion = r.reuse_suggestion.value if hasattr(r.reuse_suggestion, "value") else str(r.reuse_suggestion)
            table.add_row(
                r.source_module_id[:40],
                r.target_module_id[:40],
                sim_str,
                f"{r.winnowing_overlap}",
                f"{getattr(r, 'ast_similarity', 0):.1f}",
                suggestion,
            )

    def action_show_dashboard(self) -> None:
        self.query_one(TabbedContent).active = "tab-dashboard"

    def action_show_wizard(self) -> None:
        self.query_one(TabbedContent).active = "tab-wizard"

    def action_show_results(self) -> None:
        self.query_one(TabbedContent).active = "tab-results"

    def action_show_browser(self) -> None:
        self.query_one(TabbedContent).active = "tab-browser"


class ModuleMirrorTUI(App):
    TITLE = "ModuleMirror"
    SUB_TITLE = "Code Similarity Detection TUI"
    CSS = CSS

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("ctrl+q", "quit", "Quit"),
    ]

    def on_mount(self) -> None:
        self.push_screen(DashboardScreen())
