"""
CLI 输出格式化

参考 Black output.py + report.py 模式，
将输出渲染逻辑从 CLI 命令中分离出来。
"""

import click


def make_progress_callback():
    bar_width = 40

    def callback(progress: float):
        filled = int(bar_width * progress)
        bar = "█" * filled + "░" * (bar_width - filled)
        click.echo(f"\r进度: [{bar}] {progress * 100:.1f}%", nl=False)
        if progress >= 1.0:
            click.echo()

    return callback


def format_detection_header(target: str, candidate_count: int, granularity: str, threshold: float) -> None:
    click.echo(f"目标项目: {target}")
    click.echo(f"候选项目数: {candidate_count}")
    click.echo(f"模块粒度: {granularity}")
    click.echo(f"相似度阈值: {threshold}%")
    click.echo()


def format_detection_results(results: list) -> None:
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
                    location = (
                        f"\n       源: {s['source_file']}:{s['source_lines']}"
                        f" → 目标: {s['target_file']}:{s['target_lines']}"
                    )
                click.echo(
                    f"  {i}. {match.source_module_id} ↔ "
                    f"{match.target_module_id} "
                    f"({match.similarity:.2f}% - {match.reuse_suggestion.value})"
                    f"{location}"
                )


def format_plagiarism_header(target: str, db: str, threshold: float) -> None:
    click.echo("抄袭溯源检测")
    click.echo(f"  目标项目: {target}")
    click.echo(f"  指纹库: {db}")
    click.echo(f"  相似度阈值: {threshold}%")
    click.echo()


def format_plagiarism_results(results: list) -> None:
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


def format_search_results(results: list) -> None:
    if not results:
        click.echo("未找到匹配的仓库。")
        return

    click.echo(f"搜索结果 (共 {len(results)} 个):")
    click.echo()
    for i, repo in enumerate(results, 1):
        click.echo(f"  {i}. {repo['full_name']}")
        click.echo(f"     URL: {repo['url']}")
        click.echo(
            f"     Stars: {repo['stars']} | Forks: {repo['forks']} | 语言: {repo['language']}"
        )
        if repo["description"]:
            desc = repo["description"][:80]
            click.echo(f"     描述: {desc}")


def format_diff_result(result, file1: str, file2: str) -> None:
    click.echo(f"源: {file1} ({result.source_total} 行)")
    click.echo(f"目标: {file2} ({result.target_total} 行)")
    click.echo(f"相似率: {result.ratio * 100:.1f}%")
    click.echo(f"+{result.added} -{result.removed} ={result.unchanged}")
    click.echo()

    for line in result.lines:
        prefix = " "
        if line.tag == "add":
            prefix = "+"
        elif line.tag == "remove":
            prefix = "-"

        src_num = f"{line.source_line:>4}" if line.source_line else "    "
        tgt_num = f"{line.target_line:>4}" if line.target_line else "    "
        click.echo(f"{src_num} {tgt_num} {prefix}{line.content}")


def format_api_rate_info(info: dict) -> None:
    core = info.get("resources", {}).get("core", {})
    remaining = core.get("remaining")
    limit = core.get("limit")
    if remaining is not None and limit is not None:
        if remaining < 10:
            click.echo(f"警告: API 余额不足 ({remaining}/{limit})，可能触发速率限制", err=True)
        else:
            click.echo(f"API 余额: {remaining}/{limit}")
