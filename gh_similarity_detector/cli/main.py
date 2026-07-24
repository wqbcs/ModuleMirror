from __future__ import annotations

import click
import sys
import asyncio
from pathlib import Path

from ..config.config import DetectionConfig
from ..models.enums import ModuleType, ReportFormat
from ..models.results import DetectionResult
from ..core import DetectionPipeline
from ..core.similarity.differ import CodeDiffer
from ..infrastructure.github_client.client import GitHubClient
from ..infrastructure.engines.ncd import NCD
from ..utils.logger import logger
from .. import __version__
from .db_commands import register_db_commands
from .error_handler import handle_cli_error
from .formatters import (
    make_progress_callback,
    format_detection_header,
    format_detection_results,
    format_plagiarism_header,
    format_plagiarism_results,
    format_search_results,
    format_diff_result,
    format_api_rate_info,
)
from .validators import InputValidator

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.tree import Tree

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

try:
    from trogon import tui

    TROGON_AVAILABLE = True
except ImportError:
    TROGON_AVAILABLE = False


def _check_api_rate_limit(token: str) -> None:
    if not token:
        return
    try:
        client = GitHubClient(token=token)
        info = asyncio.run(client.check_rate_limit())
        format_api_rate_info(info)
    except (OSError, RuntimeError):
        click.echo("API 余额: 无法获取", err=True)


if TROGON_AVAILABLE:
    _tui_decorator = tui(command="tui", help="Open interactive TUI")
else:
    def _tui_decorator(f):
        return f


@_tui_decorator
@click.group()
@click.version_option(version=__version__, prog_name="gh-sim")
def main() -> None:
    """GitHub 项目代码相似度检测工具

    用于自我审视（发现可复用模块）和抄袭检测（追溯代码来源）。

    \b
    常用命令:
      gh-sim detect user/repo --candidates user/repo2    自我审视检测
      gh-sim plagiarism user/repo --db ./fp.sqlite      抄袭溯源检测
      gh-sim db init && gh-sim db add user/repo          指纹库管理
      gh-sim app                                          交互式TUI
    """


@main.command()
@click.option("--target", "-t", required=True, help="目标项目路径或 GitHub URL")
@click.option(
    "--candidates",
    "-c",
    required=True,
    multiple=True,
    help="候选项目路径或 GitHub URL（可指定多个）",
)
@click.option(
    "--candidates-file", "-f", type=click.Path(exists=True), help="候选项目列表文件（每行一个 URL）"
)
@click.option(
    "--granularity",
    "-g",
    type=click.Choice(["file", "function", "class"]),
    default="function",
    help="模块粒度（默认: function）",
)
@click.option(
    "--language", "-l", multiple=True, default=["python"], help="编程语言（默认: python）"
)
@click.option("--threshold", type=float, default=70.0, help="相似度阈值（0-100，默认: 70）")
@click.option("--output", "-o", default="./report", help="报告输出路径（默认: ./report）")
@click.option(
    "--format",
    "report_format",
    type=click.Choice(["json", "html", "markdown"]),
    default="html",
    help="报告格式（默认: html）",
)
@click.option(
    "--token", envvar="GITHUB_TOKEN", help="GitHub API Token（也可通过 GITHUB_TOKEN 环境变量设置）"
)
@click.option("--parallelism", "-p", type=int, default=4, help="并行度（默认: 4）")
@click.option("--checkpoint", default=None, help="检查点文件路径（启用断点续传）")
@click.option("--retry", type=int, default=0, help="失败候选项目重试次数（默认: 0）")
def detect(
    target: str,
    candidates: tuple[str, ...],
    candidates_file: str,
    granularity: str,
    language: tuple[str, ...],
    threshold: float,
    output: str,
    report_format: str,
    token: str,
    parallelism: int,
    checkpoint: str,
    retry: int,
) -> None:
    """执行自我审视检测

    检测目标项目与候选项目之间的相似模块。
    """
    InputValidator.validate_all([
        InputValidator.validate_threshold(threshold),
    ])

    granularity_map = {
        "file": ModuleType.FILE,
        "function": ModuleType.FUNCTION,
        "class": ModuleType.CLASS,
    }

    format_map = {
        "json": ReportFormat.JSON,
        "html": ReportFormat.HTML,
        "markdown": ReportFormat.MARKDOWN,
    }

    config = DetectionConfig(
        module_granularity=granularity_map[granularity],
        supported_languages=list(language),
        similarity_threshold=threshold,
        report_format=format_map[report_format],
        output_path=Path(output),
        parallelism=parallelism,
        github_token=token,
    )

    config.validate()

    all_candidates = list(candidates)
    if candidates_file:
        with open(candidates_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    all_candidates.append(line)

    if not all_candidates:
        click.echo("错误: 必须指定至少一个候选项目", err=True)
        sys.exit(1)

    format_detection_header(target, len(all_candidates), granularity, threshold)

    pipeline = DetectionPipeline(config)
    progress_callback = make_progress_callback()

    _check_api_rate_limit(token)

    try:
        results = pipeline.detect(
            target, all_candidates, progress_callback, checkpoint_path=checkpoint
        )
        format_detection_results(results)

    except Exception as e:
        handle_cli_error(e)


@main.command()
@click.option("--target", "-t", required=True, help="被检测项目路径或 GitHub URL")
@click.option(
    "--db", default="./fingerprint_db.sqlite", help="指纹库路径（默认: ./fingerprint_db.sqlite）"
)
@click.option(
    "--language", "-l", multiple=True, default=["python"], help="编程语言（默认: python）"
)
@click.option("--threshold", type=float, default=70.0, help="相似度阈值（0-100，默认: 70）")
@click.option("--output", "-o", default="./plagiarism_report", help="溯源报告输出路径")
@click.option("--update-db", is_flag=True, default=False, help="检测同时将目标项目添加到指纹库")
def plagiarism(
    target: str, db: str, language: tuple[str, ...], threshold: float, output: str, update_db: bool
) -> None:
    """执行抄袭溯源检测

    检测目标项目是否抄袭了指纹库中的项目代码。
    """
    InputValidator.validate_all([
        InputValidator.validate_db_path(db),
        InputValidator.validate_threshold(threshold),
    ])

    config = DetectionConfig(
        supported_languages=list(language), similarity_threshold=threshold, output_path=Path(output)
    )

    format_plagiarism_header(target, db, threshold)

    pipeline = DetectionPipeline(config, db_path=db)
    progress_callback = make_progress_callback()

    try:
        results = pipeline.plagiarism(target, progress_callback)

        format_plagiarism_results(results)

        if update_db:
            click.echo("\n正在将目标项目添加到指纹库...")
            success = pipeline.add_to_db(target)
            if success:
                click.echo("目标项目已添加到指纹库")
            else:
                click.echo("添加失败", err=True)

        if results:
            detection_results = []
            for pr in results:
                detection_results.append(
                    DetectionResult(
                        source_project=target,
                        target_project=pr.source_project_id,
                        matches=pr.matched_modules,
                        statistics={
                            "avg_similarity": pr.average_similarity,
                            "max_similarity": max(
                                (m.similarity for m in pr.matched_modules), default=0
                            ),
                            "count_90": sum(1 for m in pr.matched_modules if m.similarity >= 90),
                            "count_80": sum(
                                1 for m in pr.matched_modules if 80 <= m.similarity < 90
                            ),
                            "count_70": sum(
                                1 for m in pr.matched_modules if 70 <= m.similarity < 80
                            ),
                        },
                    )
                )
            report_path = pipeline.report_generator.generate_report(detection_results)
            click.echo(f"\n报告已生成: {report_path}")

    except Exception as e:
        handle_cli_error(e)


@main.command()
@click.option("--query", "-q", required=True, help="搜索关键词")
@click.option("--language", "-l", default=None, help="编程语言过滤（如 python, java）")
@click.option(
    "--sort", type=click.Choice(["stars", "forks", "updated"]), default="stars", help="排序方式"
)
@click.option("--max", "max_results", type=int, default=20, help="最大返回数")
@click.option("--token", envvar="GITHUB_TOKEN", help="GitHub API Token")
def search(query: str, language: str, sort: str, max_results: int, token: str) -> None:
    """搜索 GitHub 仓库

    根据关键词搜索相关项目，可作为 detect 命令的候选项目来源。
    """
    _check_api_rate_limit(token)

    client = GitHubClient(token=token)

    try:
        results = asyncio.run(
            client.search_repositories(query, language=language, sort=sort, max_results=max_results)
        )
        format_search_results(results)

    except Exception as e:
        handle_cli_error(e)


@main.command()
@click.option("--source", "-s", required=True, help="源项目目录路径")
@click.option("--target", "-t", required=True, help="目标项目目录路径")
@click.option("--extensions", "-e", multiple=True, default=[], help="文件扩展名过滤（如 .py .js）")
def ncd(source: str, target: str, extensions: tuple[str, ...]) -> None:
    """计算两项目整体相似度 (NCD)

    使用归一化压缩距离快速判断两个项目是否整体相似。
    """
    ncd_calc = NCD()
    exts = list(extensions) if extensions else [".py", ".js", ".java", ".ts"]
    sim = ncd_calc.compute_project_similarity(source, target, exts)

    click.echo(f"NCD 项目相似度: {sim:.2f}%")


@main.command()
@click.option("--file1", "-1", required=True, help="第一个文件路径")
@click.option("--file2", "-2", required=True, help="第二个文件路径")
@click.option("--context", "-c", type=int, default=3, help="上下文行数（默认: 3）")
@click.option("--unified", "-u", is_flag=True, help="输出 unified diff 格式")
def diff(file1: str, file2: str, context: int, unified: bool) -> None:
    """对比两个文件的代码差异

    显示两段代码之间的行级差异，帮助理解相似模块的具体区别。
    """
    try:
        with open(file1, "r", encoding="utf-8") as f:
            code1 = f.read()
        with open(file2, "r", encoding="utf-8") as f:
            code2 = f.read()
    except FileNotFoundError as e:
        click.echo(f"文件不存在: {e}", err=True)
        sys.exit(1)
    except UnicodeDecodeError as e:
        click.echo(f"文件编码错误: {e}", err=True)
        sys.exit(1)

    differ = CodeDiffer()

    if unified:
        unified_result = differ.format_unified_diff(code1, code2, file1, file2, context)
        if unified_result:
            click.echo(unified_result)
        else:
            click.echo("两文件内容完全相同。")
    else:
        diff_result = differ.diff(code1, code2, file1, file2, context)
        format_diff_result(diff_result, file1, file2)


register_db_commands(main)


@main.group()
def config() -> None:
    """配置管理"""


@config.command("generate")
@click.option("--output", "-o", default="gh-sim.yaml", help="输出文件路径")
def config_generate(output: str) -> None:
    """生成默认配置文件"""
    cfg = DetectionConfig()
    cfg.to_yaml(output)
    click.echo(f"配置文件已生成: {output}")


@config.command("validate")
@click.option(
    "--file", "-f", "config_file", required=True, type=click.Path(exists=True), help="配置文件路径"
)
def config_validate(config_file: str) -> None:
    """验证配置文件"""
    try:
        cfg = DetectionConfig.from_yaml(config_file)
        cfg.validate()
        click.echo("配置文件有效")
        click.echo(f"  模块粒度: {cfg.module_granularity.value}")
        click.echo(f"  语言: {cfg.supported_languages}")
        click.echo(f"  阈值: {cfg.similarity_threshold}%")
        click.echo(f"  Winnowing: k={cfg.winnowing_kgram_size}, w={cfg.winnowing_window_size}")
    except Exception as e:
        click.echo(f"配置无效: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()


@main.command()
@click.option("--db", default="./fingerprint_db.sqlite", help="指纹库路径")
def browse(db: str) -> None:
    """交互式浏览指纹库内容

    使用 Rich TUI 展示指纹库中的项目和模块信息。
    """
    if not RICH_AVAILABLE:
        click.echo("需要安装 rich 库: pip install rich", err=True)
        sys.exit(1)

    console = Console()
    db_path = Path(db)
    if not db_path.exists():
        console.print(f"[red]指纹库不存在: {db}[/red]")
        sys.exit(1)

    from ..infrastructure.storage.fingerprint_db import FingerprintDB

    fingerprint_db = FingerprintDB(str(db_path))

    try:
        projects = fingerprint_db.list_projects()
        if not projects:
            console.print("[yellow]指纹库为空[/yellow]")
            return

        tree = Tree("📁 指纹库")
        for project in projects:
            proj_name = project.name if hasattr(project, "name") else str(project)
            proj_node = tree.add(f"📦 {proj_name}")
            try:
                modules = fingerprint_db.get_project_modules(  # type: ignore[attr-defined]
                    project.id if hasattr(project, "id") else project
                )
                for module in modules[:10]:
                    mod_name = module.file_path if hasattr(module, "file_path") else str(module)
                    proj_node.add(f"📄 {mod_name}")
                if len(modules) > 10:
                    proj_node.add(f"... 还有 {len(modules) - 10} 个模块")
            except (OSError, AttributeError):
                logger.debug(f"模块列表渲染跳过: {proj_name}")

        console.print(tree)
        console.print(f"\n[green]共 {len(projects)} 个项目[/green]")
    except Exception as e:
        console.print(f"[red]浏览失败: {e}[/red]")
        sys.exit(1)


@main.command()
@click.option("--db", default="./fingerprint_db.sqlite", help="指纹库路径")
def dashboard(db: str) -> None:
    """显示检测仪表盘概览

    使用 Rich TUI 展示系统状态、指纹库统计和最近检测结果。
    """
    if not RICH_AVAILABLE:
        click.echo("需要安装 rich 库: pip install rich", err=True)
        sys.exit(1)

    console = Console()

    console.print(Panel("ModuleMirror 检测仪表盘", style="bold blue"))

    info_table = Table(title="系统信息")
    info_table.add_column("指标", style="cyan")
    info_table.add_column("值", style="green")
    info_table.add_row("版本", "1.1.0")
    info_table.add_row("Python", sys.version.split()[0])
    info_table.add_row("平台", sys.platform)
    console.print(info_table)

    db_path = Path(db)
    if db_path.exists():
        from ..infrastructure.storage.fingerprint_db import FingerprintDB

        fingerprint_db = FingerprintDB(str(db_path))
        try:
            stats = fingerprint_db.get_stats()
            db_table = Table(title="指纹库统计")
            db_table.add_column("指标", style="cyan")
            db_table.add_column("值", style="green")
            for key, value in stats.items():
                db_table.add_row(str(key), str(value))
            console.print(db_table)
        except Exception as e:
            console.print(f"[yellow]统计获取失败: {e}[/yellow]")
    else:
        console.print(f"[yellow]指纹库未创建: {db}[/yellow]")


@main.command()
@click.option(
    "--shell",
    type=click.Choice(["bash", "zsh", "fish"]),
    required=True,
    help="目标 shell 类型",
)
@click.option("--output", "-o", type=click.Path(), help="输出文件路径（默认输出到stdout）")
def completion(shell: str, output: str) -> None:
    """生成 shell 自动补全脚本

    用法:
      bash:  gh-sim completion --shell bash >> ~/.bashrc
      zsh:   gh-sim completion --shell zsh >> ~/.zshrc
      fish:  gh-sim completion --shell fish > ~/.config/fish/completions/gh-sim.fish
    """
    prog_name = "gh-sim"
    if shell == "bash":
        script = f'eval "$({prog_name} --bash-complete {prog_name})"'
    elif shell == "zsh":
        script = f'eval "$({prog_name} --zsh-complete {prog_name})"'
    elif shell == "fish":
        script = f"{prog_name} --fish-complete {prog_name}"
    else:
        click.echo(f"不支持的 shell: {shell}", err=True)
        sys.exit(1)

    if output:
        from pathlib import Path as P
        P(output).parent.mkdir(parents=True, exist_ok=True)
        P(output).write_text(script, encoding="utf-8")
        click.echo(f"补全脚本已写入: {output}")
    else:
        click.echo(script)


@main.command()
def app() -> None:
    """启动交互式TUI应用

    打开ModuleMirror文本界面仪表盘，包含检测向导、结果查看器和指纹库浏览器。
    """
    try:
        from .tui_app import ModuleMirrorTUI

        ModuleMirrorTUI().run()
    except ImportError:
        click.echo(
            "TUI requires 'textual' package. Install with: pip install textual",
            err=True,
        )
        sys.exit(1)


@main.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.option(
    "-f",
    "--format",
    "fmt",
    type=click.Choice(["csv", "json"]),
    default="csv",
    help="导出格式",
)
@click.option("-o", "--output", "output_path", default=None, help="输出文件路径")
def export(input_file: str, fmt: str, output_path: str | None) -> None:
    """导出检测结果为CSV或JSON格式

    INPUT_FILE 为检测结果文件路径（JSON格式）
    """
    import json as _json

    from ..infrastructure.i18n import t

    P = Path
    data = P(input_file).read_text(encoding="utf-8")
    try:
        results_data = _json.loads(data)
    except _json.JSONDecodeError:
        click.echo(f"错误: 无法解析 JSON 文件: {input_file}", err=True)
        sys.exit(1)

    if not results_data.get("results"):
        click.echo(t("cli.export.no_results"))
        return

    if output_path is None:
        output_path = str(P(input_file).with_suffix(f".{fmt}"))

    if fmt == "csv":
        import csv as _csv
        import io as _io

        output = _io.StringIO()
        writer = _csv.writer(output)
        writer.writerow([
            "source_project", "target_project", "source_module",
            "target_module", "similarity", "reuse_suggestion",
        ])
        for result in results_data["results"]:
            src_proj = result.get("source_project", "")
            tgt_proj = result.get("target_project", "")
            for match in result.get("matches", []):
                writer.writerow([
                    src_proj,
                    tgt_proj,
                    match.get("source_module_id", ""),
                    match.get("target_module_id", ""),
                    match.get("similarity", ""),
                    match.get("reuse_suggestion", ""),
                ])
        P(output_path).write_text(output.getvalue(), encoding="utf-8")
    else:
        P(output_path).write_text(
            _json.dumps(results_data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    click.echo(t("cli.export.exported", path=output_path, format=fmt))


@main.command()
@click.option("--github-token", envvar="GITHUB_TOKEN", default=None, help="GitHub API Token")
@click.option("--api-key", envvar="MODULEMIRROR_API_KEY", default=None, help="API 认证密钥")
@click.option("--db-path", default="./fingerprint_db.sqlite", help="指纹库路径")
@click.option("--non-interactive", is_flag=True, default=False, help="非交互模式（使用默认值）")
def init(github_token: str, api_key: str, db_path: str, non_interactive: bool) -> None:
    """交互式配置向导 — 3步完成首次检测配置
    
    步骤1: 配置 GitHub Token（可选，提升API速率限制）
    步骤2: 配置认证密钥（可选，保护API端点）
    步骤3: 验证配置并生成 .env 文件
    """
    if non_interactive:
        _init_non_interactive(github_token, api_key, db_path)
        return

    click.echo("\n" + "=" * 50)
    click.echo("  ModuleMirror 配置向导")
    click.echo("=" * 50 + "\n")

    if not github_token:
        click.echo("步骤1/3: GitHub Token")
        click.echo("  设置 GitHub Token 可将 API 速率限制从 60/h 提升至 5000/h")
        github_token = click.prompt("  请输入 GitHub Token（留空跳过）", default="")
        click.echo()

    if not api_key:
        click.echo("步骤2/3: API 认证密钥")
        click.echo("  设置密钥后，所有 API 请求需携带 X-API-Key 请求头")
        api_key = click.prompt("  请输入 API Key（留空跳过）", default="")
        click.echo()

    click.echo("步骤3/3: 验证配置")
    click.echo(f"  GitHub Token: {'已设置 ✓' if github_token else '未设置'}")
    click.echo(f"  API Key:      {'已设置 ✓' if api_key else '未设置'}")
    click.echo(f"  指纹库路径:   {db_path}")

    if not click.confirm("\n  确认生成 .env 文件？", default=True):
        click.echo("  已取消配置")
        return

    env_content = _generate_env_file(github_token, api_key, db_path)
    env_path = Path(".env")
    env_path.write_text(env_content, encoding="utf-8")
    click.echo(f"\n  配置文件已生成: {env_path.absolute()}")

    if github_token:
        click.echo("\n  提示: 运行以下命令验证配置:")
        click.echo("    gh-sim detect -t https://github.com/user/repo -c https://github.com/other/repo")
    else:
        click.echo("\n  提示: 设置 GitHub Token 后可获得更好的体验")
        click.echo("    编辑 .env 文件添加 GITHUB_TOKEN=ghp_xxx")


def _init_non_interactive(github_token: str, api_key: str, db_path: str) -> None:
    """非交互模式初始化"""
    env_content = _generate_env_file(github_token, api_key, db_path)
    env_path = Path(".env")
    env_path.write_text(env_content, encoding="utf-8")
    click.echo(f"配置文件已生成: {env_path.absolute()}")


def _generate_env_file(github_token: str, api_key: str, db_path: str) -> str:
    """生成 .env 文件内容"""
    lines = [
        "# ModuleMirror 环境配置（由 gh-sim init 生成）",
        "",
    ]
    if github_token:
        lines.append(f"GITHUB_TOKEN={github_token}")
    else:
        lines.append("GITHUB_TOKEN=")
    if api_key:
        lines.append(f"MODULEMIRROR_API_KEY={api_key}")
    else:
        lines.append("MODULEMIRROR_API_KEY=")
    lines.append(f"MODULEMIRROR_DB_PATH={db_path}")
    lines.append("MODULEMIRROR_JWT_SECRET=change-me-in-production")
    lines.append("MODULEMIRROR_LOG_LEVEL=info")
    lines.append("")
    return "\n".join(lines)