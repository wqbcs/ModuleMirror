"""
CLI 命令行接口

提供 gh-sim 命令行工具。

Author: GitHub 项目代码相似度检测工具
"""

import click
import sys
import asyncio
from pathlib import Path

from ..config.config import DetectionConfig
from ..models.enums import ModuleType, ReportFormat
from ..models.results import DetectionResult
from ..core import DetectionPipeline
from ..core.similarity.differ import CodeDiffer
from ..infrastructure.github_client.client import (
    GitHubClient, GitHubAPIError, RateLimitError, NotFoundError, GitHubPermissionError,
)
from ..infrastructure.engines.ncd import NCD
from .db_commands import register_db_commands

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.tree import Tree
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

EXIT_RATE_LIMIT = 2
EXIT_NOT_FOUND = 3
EXIT_PERMISSION = 4
EXIT_API_ERROR = 5


def _handle_cli_error(e: Exception) -> None:
    if isinstance(e, RateLimitError):
        msg = "GitHub API 速率限制"
        if e.retry_after:
            msg += f"，请在 {e.retry_after} 秒后重试"
        click.echo(f"\n错误: {msg}", err=True)
        click.echo("提示: 可设置 GITHUB_TOKEN 环境变量提高速率限制", err=True)
        sys.exit(EXIT_RATE_LIMIT)
    elif isinstance(e, NotFoundError):
        click.echo(f"\n错误: 项目或资源不存在 ({e.message})", err=True)
        sys.exit(EXIT_NOT_FOUND)
    elif isinstance(e, GitHubPermissionError):
        click.echo(f"\n错误: 权限不足 ({e.message})", err=True)
        click.echo("提示: 请检查 GITHUB_TOKEN 是否有效，或项目是否为私有仓库", err=True)
        sys.exit(EXIT_PERMISSION)
    elif isinstance(e, GitHubAPIError):
        click.echo(f"\n错误: GitHub API 异常 ({e.message})", err=True)
        sys.exit(EXIT_API_ERROR)
    else:
        click.echo(f"\n检测失败: {e}", err=True)
        sys.exit(1)


def _check_api_rate_limit(token: str) -> None:
    if not token:
        return
    try:
        client = GitHubClient(token=token)
        info = asyncio.run(client.check_rate_limit())
        core = info.get('resources', {}).get('core', {})
        remaining = core.get('remaining')
        limit = core.get('limit')
        if remaining is not None and limit is not None:
            if remaining < 10:
                click.echo(f"警告: API 余额不足 ({remaining}/{limit})，可能触发速率限制", err=True)
            else:
                click.echo(f"API 余额: {remaining}/{limit}")
    except Exception:
        pass


def _make_progress_callback():
    bar_width = 40
    def callback(progress: float):
        filled = int(bar_width * progress)
        bar = '█' * filled + '░' * (bar_width - filled)
        click.echo(f"\r进度: [{bar}] {progress*100:.1f}%", nl=False)
        if progress >= 1.0:
            click.echo()
    return callback


@click.group()
@click.version_option(version="0.1.0", prog_name="gh-sim")
def main():
    """GitHub 项目代码相似度检测工具
    
    用于自我审视（发现可复用模块）和抄袭检测（追溯代码来源）。
    """
    pass


@main.command()
@click.option(
    "--target", "-t",
    required=True,
    help="目标项目路径或 GitHub URL"
)
@click.option(
    "--candidates", "-c",
    required=True,
    multiple=True,
    help="候选项目路径或 GitHub URL（可指定多个）"
)
@click.option(
    "--candidates-file", "-f",
    type=click.Path(exists=True),
    help="候选项目列表文件（每行一个 URL）"
)
@click.option(
    "--granularity", "-g",
    type=click.Choice(["file", "function", "class"]),
    default="function",
    help="模块粒度（默认: function）"
)
@click.option(
    "--language", "-l",
    multiple=True,
    default=["python"],
    help="编程语言（默认: python）"
)
@click.option(
    "--threshold",
    type=float,
    default=70.0,
    help="相似度阈值（0-100，默认: 70）"
)
@click.option(
    "--output", "-o",
    default="./report",
    help="报告输出路径（默认: ./report）"
)
@click.option(
    "--format",
    "report_format",
    type=click.Choice(["json", "html", "markdown"]),
    default="html",
    help="报告格式（默认: html）"
)
@click.option(
    "--token",
    envvar="GITHUB_TOKEN",
    help="GitHub API Token（也可通过 GITHUB_TOKEN 环境变量设置）"
)
@click.option(
    "--parallelism", "-p",
    type=int,
    default=4,
    help="并行度（默认: 4）"
)
@click.option(
    "--checkpoint",
    default=None,
    help="检查点文件路径（启用断点续传）"
)
@click.option(
    "--retry",
    type=int,
    default=0,
    help="失败候选项目重试次数（默认: 0）"
)
def detect(
    target: str,
    candidates: tuple,
    candidates_file: str,
    granularity: str,
    language: tuple,
    threshold: float,
    output: str,
    report_format: str,
    token: str,
    parallelism: int,
    checkpoint: str,
    retry: int
):
    """执行自我审视检测
    
    检测目标项目与候选项目之间的相似模块。
    """
    granularity_map = {
        "file": ModuleType.FILE,
        "function": ModuleType.FUNCTION,
        "class": ModuleType.CLASS
    }
    
    format_map = {
        "json": ReportFormat.JSON,
        "html": ReportFormat.HTML,
        "markdown": ReportFormat.MARKDOWN
    }
    
    config = DetectionConfig(
        module_granularity=granularity_map[granularity],
        supported_languages=list(language),
        similarity_threshold=threshold,
        report_format=format_map[report_format],
        output_path=Path(output),
        parallelism=parallelism,
        github_token=token
    )
    
    config.validate()
    
    all_candidates = list(candidates)
    if candidates_file:
        with open(candidates_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    all_candidates.append(line)
    
    if not all_candidates:
        click.echo("错误: 必须指定至少一个候选项目", err=True)
        sys.exit(1)
    
    click.echo(f"目标项目: {target}")
    click.echo(f"候选项目数: {len(all_candidates)}")
    click.echo(f"模块粒度: {granularity}")
    click.echo(f"相似度阈值: {threshold}%")
    click.echo()
    
    pipeline = DetectionPipeline(config)
    progress_callback = _make_progress_callback()

    _check_api_rate_limit(token)

    try:
        results = pipeline.detect(target, all_candidates, progress_callback, checkpoint_path=checkpoint)
        
        for result in results:
            click.echo()
            click.echo(f"{'=' * 60}")
            click.echo(f"检测: {result.source_project} ↔ {result.target_project}")
            click.echo(f"{'=' * 60}")
            click.echo(f"  总匹配数: {len(result.matches)}")
            click.echo(f"  平均相似度: {result.statistics.get('avg_similarity', 0):.2f}%")
            click.echo(f"  最高相似度: {result.statistics.get('max_similarity', 0):.2f}%")
            
            if result.matches:
                click.echo()
                click.echo("Top 匹配:")
                for i, match in enumerate(result.matches[:5], 1):
                    location = ""
                    if match.matched_code_snippet:
                        s = match.matched_code_snippet
                        location = f"\n       源: {s['source_file']}:{s['source_lines']} → 目标: {s['target_file']}:{s['target_lines']}"
                    click.echo(
                        f"  {i}. {match.source_module_id} ↔ "
                        f"{match.target_module_id} "
                        f"({match.similarity:.2f}% - {match.reuse_suggestion.value})"
                        f"{location}"
                    )
    
    except Exception as e:
        _handle_cli_error(e)


@main.command()
@click.option(
    "--target", "-t",
    required=True,
    help="被检测项目路径或 GitHub URL"
)
@click.option(
    "--db",
    default="./fingerprint_db.sqlite",
    help="指纹库路径（默认: ./fingerprint_db.sqlite）"
)
@click.option(
    "--language", "-l",
    multiple=True,
    default=["python"],
    help="编程语言（默认: python）"
)
@click.option(
    "--threshold",
    type=float,
    default=70.0,
    help="相似度阈值（0-100，默认: 70）"
)
@click.option(
    "--output", "-o",
    default="./plagiarism_report",
    help="溯源报告输出路径"
)
@click.option(
    "--update-db", is_flag=True, default=False,
    help="检测同时将目标项目添加到指纹库"
)
def plagiarism(target: str, db: str, language: tuple, threshold: float, output: str, update_db: bool):
    """执行抄袭溯源检测
    
    检测目标项目是否抄袭了指纹库中的项目代码。
    """
    
    db_path = db
    if not Path(db_path).exists():
        click.echo(f"错误: 指纹库不存在: {db_path}", err=True)
        click.echo("请先使用 'gh-sim db add' 构建指纹库。", err=True)
        sys.exit(1)
    
    config = DetectionConfig(
        supported_languages=list(language),
        similarity_threshold=threshold,
        output_path=Path(output)
    )

    click.echo("抄袭溯源检测")
    click.echo(f"  目标项目: {target}")
    click.echo(f"  指纹库: {db}")
    click.echo(f"  相似度阈值: {threshold}%")
    click.echo()
    
    pipeline = DetectionPipeline(config, db_path=db_path)
    progress_callback = _make_progress_callback()

    try:
        results = pipeline.plagiarism(target, progress_callback)
        
        if results:
            click.echo()
            click.echo(f"{'=' * 60}")
            click.echo("抄袭溯源结果")
            click.echo(f"{'=' * 60}")
            
            for i, result in enumerate(results, 1):
                click.echo()
                click.echo(f"来源 {i}: {result.source_project_id}")
                click.echo(f"  置信度: {result.confidence_score:.2f}/100")
                click.echo(f"  贡献比例: {result.contribution_ratio:.2f}%")
                click.echo(f"  相似模块数: {result.similar_module_count}")
                click.echo(f"  平均相似度: {result.average_similarity:.2f}%")
                click.echo(f"  时间关系: {result.time_relation.value}")
        else:
            click.echo("未发现疑似抄袭来源。")

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
                detection_results.append(DetectionResult(
                    source_project=target,
                    target_project=pr.source_project_id,
                    matches=pr.matched_modules,
                    statistics={
                        'avg_similarity': pr.average_similarity,
                        'max_similarity': max((m.similarity for m in pr.matched_modules), default=0),
                        'count_90': sum(1 for m in pr.matched_modules if m.similarity >= 90),
                        'count_80': sum(1 for m in pr.matched_modules if 80 <= m.similarity < 90),
                        'count_70': sum(1 for m in pr.matched_modules if 70 <= m.similarity < 80),
                    }
                ))
            report_path = pipeline.report_generator.generate_report(detection_results)
            click.echo(f"\n报告已生成: {report_path}")
    
    except Exception as e:
        _handle_cli_error(e)


@main.command()
@click.option("--query", "-q", required=True, help="搜索关键词")
@click.option("--language", "-l", default=None, help="编程语言过滤（如 python, java）")
@click.option("--sort", type=click.Choice(["stars", "forks", "updated"]), default="stars", help="排序方式")
@click.option("--max", "max_results", type=int, default=20, help="最大返回数")
@click.option("--token", envvar="GITHUB_TOKEN", help="GitHub API Token")
def search(query: str, language: str, sort: str, max_results: int, token: str):
    """搜索 GitHub 仓库

    根据关键词搜索相关项目，可作为 detect 命令的候选项目来源。
    """
    _check_api_rate_limit(token)

    client = GitHubClient(token=token)

    try:
        results = asyncio.run(
            client.search_repositories(query, language=language, sort=sort, max_results=max_results)
        )

        if not results:
            click.echo("未找到匹配的仓库。")
            return

        click.echo(f"搜索结果 (共 {len(results)} 个):")
        click.echo()
        for i, repo in enumerate(results, 1):
            click.echo(f"  {i}. {repo['full_name']}")
            click.echo(f"     URL: {repo['url']}")
            click.echo(f"     Stars: {repo['stars']} | Forks: {repo['forks']} | 语言: {repo['language']}")
            if repo['description']:
                desc = repo['description'][:80]
                click.echo(f"     描述: {desc}")

    except Exception as e:
        _handle_cli_error(e)


@main.command()
@click.option("--source", "-s", required=True, help="源项目目录路径")
@click.option("--target", "-t", required=True, help="目标项目目录路径")
@click.option("--extensions", "-e", multiple=True, default=[], help="文件扩展名过滤（如 .py .js）")
def ncd(source: str, target: str, extensions: tuple):
    """计算两项目整体相似度 (NCD)

    使用归一化压缩距离快速判断两个项目是否整体相似。
    """
    ncd_calc = NCD()
    exts = list(extensions) if extensions else ['.py', '.js', '.java', '.ts']
    sim = ncd_calc.compute_project_similarity(source, target, exts)

    click.echo(f"NCD 项目相似度: {sim:.2f}%")


@main.command()
@click.option("--file1", "-1", required=True, help="第一个文件路径")
@click.option("--file2", "-2", required=True, help="第二个文件路径")
@click.option("--context", "-c", type=int, default=3, help="上下文行数（默认: 3）")
@click.option("--unified", "-u", is_flag=True, help="输出 unified diff 格式")
def diff(file1: str, file2: str, context: int, unified: bool):
    """对比两个文件的代码差异

    显示两段代码之间的行级差异，帮助理解相似模块的具体区别。
    """
    differ = CodeDiffer()

    try:
        with open(file1, 'r', encoding='utf-8') as f:
            code1 = f.read()
        with open(file2, 'r', encoding='utf-8') as f:
            code2 = f.read()
    except FileNotFoundError as e:
        click.echo(f"文件不存在: {e}", err=True)
        sys.exit(1)
    except UnicodeDecodeError as e:
        click.echo(f"文件编码错误: {e}", err=True)
        sys.exit(1)

    differ = CodeDiffer()

    if unified:
        result = differ.format_unified_diff(code1, code2, file1, file2, context)
        if result:
            click.echo(result)
        else:
            click.echo("两文件内容完全相同。")
    else:
        result = differ.diff(code1, code2, file1, file2, context)

        click.echo(f"源: {file1} ({result.source_total} 行)")
        click.echo(f"目标: {file2} ({result.target_total} 行)")
        click.echo(f"相似率: {result.ratio * 100:.1f}%")
        click.echo(f"+{result.added} -{result.removed} ={result.unchanged}")
        click.echo()

        for line in result.lines:
            prefix = ' '
            if line.tag == 'add':
                prefix = '+'
            elif line.tag == 'remove':
                prefix = '-'

            src_num = f"{line.source_line:>4}" if line.source_line else "    "
            tgt_num = f"{line.target_line:>4}" if line.target_line else "    "
            click.echo(f"{src_num} {tgt_num} {prefix}{line.content}")


register_db_commands(main)


@main.group()
def config():
    """配置管理"""
    pass


@config.command("generate")
@click.option("--output", "-o", default="gh-sim.yaml", help="输出文件路径")
def config_generate(output: str):
    """生成默认配置文件"""
    cfg = DetectionConfig()
    cfg.to_yaml(output)
    click.echo(f"配置文件已生成: {output}")


@config.command("validate")
@click.option("--file", "-f", "config_file", required=True, type=click.Path(exists=True), help="配置文件路径")
def config_validate(config_file: str):
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
def browse(db: str):
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
            proj_name = project.name if hasattr(project, 'name') else str(project)
            proj_node = tree.add(f"📦 {proj_name}")
            try:
                modules = fingerprint_db.get_project_modules(project.id if hasattr(project, 'id') else project)
                for module in modules[:10]:
                    mod_name = module.file_path if hasattr(module, 'file_path') else str(module)
                    proj_node.add(f"📄 {mod_name}")
                if len(modules) > 10:
                    proj_node.add(f"... 还有 {len(modules) - 10} 个模块")
            except Exception:
                pass

        console.print(tree)
        console.print(f"\n[green]共 {len(projects)} 个项目[/green]")
    except Exception as e:
        console.print(f"[red]浏览失败: {e}[/red]")
        sys.exit(1)


@main.command()
@click.option("--db", default="./fingerprint_db.sqlite", help="指纹库路径")
def dashboard(db: str):
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
    info_table.add_row("版本", "0.1.0")
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
