import click
from pathlib import Path

from ..config.config import DetectionConfig
from ..core import DetectionPipeline
from ..infrastructure.storage.fingerprint_db import FingerprintDB


def register_db_commands(main):
    @main.group()
    def db():
        """指纹库管理"""
        pass

    @db.command("init")
    @click.option("--path", default="./fingerprint_db.sqlite", help="数据库路径")
    def db_init(path: str):
        """初始化指纹库"""
        fp_db = FingerprintDB(path)
        stats = fp_db.get_stats()

        click.echo(f"指纹库已初始化: {path}")
        click.echo(f"  项目数: {stats['project_count']}")
        click.echo(f"  模块数: {stats['module_count']}")
        click.echo(f"  指纹数: {stats['fingerprint_count']}")

    @db.command("add")
    @click.option("--project", "-p", required=True, help="项目 URL 或路径")
    @click.option("--db", "db_path", default="./fingerprint_db.sqlite", help="数据库路径")
    @click.option("--language", "-l", multiple=True, default=["python"], help="编程语言")
    @click.option("--min-tokens", type=int, default=50, help="最小 token 长度")
    def db_add(project: str, db_path: str, language: tuple, min_tokens: int):
        """添加项目到指纹库"""
        config = DetectionConfig(supported_languages=list(language), min_token_length=min_tokens)
        pipeline = DetectionPipeline(config, db_path=db_path)

        click.echo(f"添加项目: {project}")

        with click.progressbar(length=100, label="处理中") as bar:

            def progress(p):
                bar.update(int(p * 100) - bar.pos)

            success = pipeline.add_to_db(project, progress)

        if success:
            stats = pipeline.fingerprint_db.get_stats()
            click.echo("项目已添加到指纹库")
            click.echo(f"  总项目数: {stats['project_count']}")
            click.echo(f"  总模块数: {stats['module_count']}")
        else:
            click.echo("添加失败。", err=True)

    @db.command("update")
    @click.option("--project", "-p", required=True, help="项目 GitHub URL")
    @click.option("--db", "db_path", default="./fingerprint_db.sqlite", help="数据库路径")
    @click.option("--language", "-l", multiple=True, default=["python"], help="编程语言")
    @click.option("--min-tokens", type=int, default=50, help="最小 token 长度")
    def db_update(project: str, db_path: str, language: tuple, min_tokens: int):
        """增量更新指纹库中的项目（检测新提交后更新）"""
        config = DetectionConfig(supported_languages=list(language), min_token_length=min_tokens)
        pipeline = DetectionPipeline(config, db_path=db_path)

        click.echo(f"检查更新: {project}")

        with click.progressbar(length=100, label="处理中") as bar:

            def progress(p):
                bar.update(int(p * 100) - bar.pos)

            updated = pipeline.update_db(project, progress)

        if updated:
            click.echo("项目指纹已更新")
        else:
            click.echo("项目指纹已是最新")

    @db.command("stats")
    @click.option("--db", "db_path", default="./fingerprint_db.sqlite", help="数据库路径")
    def db_stats(db_path: str):
        """查看指纹库统计信息"""
        if not Path(db_path).exists():
            click.echo(f"指纹库不存在: {db_path}")
            return

        fp_db = FingerprintDB(db_path)
        stats = fp_db.get_stats()
        projects = fp_db.list_projects()

        click.echo(f"指纹库: {db_path}")
        click.echo(f"  项目数: {stats['project_count']}")
        click.echo(f"  模块数: {stats['module_count']}")
        click.echo(f"  指纹数: {stats['fingerprint_count']}")

        if projects:
            click.echo()
            click.echo("项目列表:")
            for p in projects:
                click.echo(f"  - {p['name']} ({p['language']}, {p['module_count']} 模块)")

    @db.command("list")
    @click.option("--db", "db_path", default="./fingerprint_db.sqlite", help="数据库路径")
    def db_list(db_path: str):
        """列出指纹库中的所有项目"""
        if not Path(db_path).exists():
            click.echo(f"指纹库不存在: {db_path}")
            return

        fp_db = FingerprintDB(db_path)
        projects = fp_db.list_projects()

        if not projects:
            click.echo("指纹库为空。")
            return

        click.echo(f"指纹库项目列表 (共 {len(projects)} 个):")
        click.echo()
        for p in projects:
            click.echo(f"  {p['name']}")
            click.echo(
                f"    语言: {p['language']} | 模块数: {p['module_count']} | 更新: {p['updated_at']}"
            )

    @db.command("delete")
    @click.option("--project-id", "-p", required=True, help="项目 ID")
    @click.option("--db", "db_path", default="./fingerprint_db.sqlite", help="数据库路径")
    @click.option("--force", "-f", is_flag=True, help="跳过确认提示")
    def db_delete(project_id: str, db_path: str, force: bool):
        """从指纹库中删除项目"""
        if not force:
            if not click.confirm(f"确认删除项目 '{project_id}'？此操作不可恢复"):
                return

        fp_db = FingerprintDB(db_path)

        if fp_db.delete_project(project_id):
            click.echo(f"项目已删除: {project_id}")
        else:
            click.echo(f"项目不存在: {project_id}", err=True)

    @db.command("import")
    @click.option(
        "--file",
        "-f",
        "import_file",
        required=True,
        type=click.Path(exists=True),
        help="项目列表文件（每行一个 URL）",
    )
    @click.option("--db", "db_path", default="./fingerprint_db.sqlite", help="数据库路径")
    @click.option("--language", "-l", multiple=True, default=["python"], help="编程语言")
    @click.option("--min-tokens", type=int, default=50, help="最小 token 长度")
    @click.option(
        "--continue-on-error", is_flag=True, default=True, help="单个项目失败时继续（默认开启）"
    )
    def db_import(
        import_file: str, db_path: str, language: tuple, min_tokens: int, continue_on_error: bool
    ):
        """从文件批量导入项目到指纹库

        每行一个项目 URL 或路径，支持 # 开头注释行和空行。
        """
        config = DetectionConfig(supported_languages=list(language), min_token_length=min_tokens)
        pipeline = DetectionPipeline(config, db_path=db_path)

        with open(import_file, "r", encoding="utf-8") as f:
            lines = [
                line.strip() for line in f if line.strip() and not line.strip().startswith("#")
            ]

        if not lines:
            click.echo("项目列表为空。")
            return

        click.echo(f"批量导入: {len(lines)} 个项目")

        succeeded = 0
        failed = []

        for i, project_source in enumerate(lines, 1):
            click.echo(f"\n[{i}/{len(lines)}] {project_source}")

            try:
                with click.progressbar(length=100, label="处理中") as bar:

                    def progress(p):
                        bar.update(int(p * 100) - bar.pos)

                    success = pipeline.add_to_db(project_source, progress)

                if success:
                    succeeded += 1
                    click.echo("  已添加")
                else:
                    failed.append((project_source, "添加失败"))
                    click.echo("  失败")
            except Exception as e:
                failed.append((project_source, str(e)))
                click.echo(f"  异常: {e}")
                if not continue_on_error:
                    break

        click.echo()
        click.echo(f"导入完成: {succeeded}/{len(lines)} 成功")
        if failed:
            click.echo(f"失败 {len(failed)} 个:")
            for src, reason in failed:
                click.echo(f"  - {src}: {reason}")
