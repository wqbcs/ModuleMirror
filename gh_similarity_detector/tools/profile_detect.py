"""
性能分析工具 - Scalene & Memray集成

自动化CPU/内存性能分析，生成报告。
Scalene: CPU+内存+GPU分析（推荐）
Memray: 内存泄露检测（C扩展友好）

Usage:
    python -m gh_similarity_detector.tools.profile_detect --scalene
    python -m gh_similarity_detector.tools.profile_detect --memray

Author: ModuleMirror
"""

import subprocess
from pathlib import Path
from typing import Optional, List
import argparse

from ..utils.logger import logger


def check_scalene_installed() -> bool:
    try:
        subprocess.run(["scalene", "--version"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def check_memray_installed() -> bool:
    try:
        subprocess.run(["memray", "--help"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def run_scalene_profile(
    script_path: str,
    output_dir: str = "profile_reports",
    extra_args: Optional[List[str]] = None,
) -> Optional[str]:
    if not check_scalene_installed():
        logger.error("scalene未安装，请运行: pip install scalene")
        return None

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    html_output = output / "scalene_report.html"

    cmd = [
        "scalene",
        "--html",
        f"--outfile={html_output}",
        "--reduced-profile",
        script_path,
    ]

    if extra_args:
        cmd.extend(extra_args)

    logger.info(f"运行scalene分析: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, check=False)
        if result.returncode == 0:
            logger.info(f"Scalene报告已生成: {html_output}")
            return str(html_output)
        else:
            logger.error(f"Scalene分析失败，返回码: {result.returncode}")
            return None
    except Exception as e:
        logger.error(f"Scalene执行异常: {e}")
        return None


def run_memray_profile(
    script_path: str,
    output_dir: str = "profile_reports",
    extra_args: Optional[List[str]] = None,
) -> Optional[str]:
    if not check_memray_installed():
        logger.error("memray未安装，请运行: pip install memray")
        return None

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    bin_output = output / "memray.bin"
    html_output = output / "memray_report.html"

    run_cmd = [
        "memray",
        "run",
        f"--output={bin_output}",
        "--native",
        script_path,
    ]

    if extra_args:
        run_cmd.extend(extra_args)

    logger.info(f"运行memray分析: {' '.join(run_cmd)}")
    try:
        result = subprocess.run(run_cmd, check=False)
        if result.returncode != 0:
            logger.error(f"Memray运行失败，返回码: {result.returncode}")
            return None

        flame_cmd = [
            "memray",
            "flamegraph",
            f"--output={html_output}",
            str(bin_output),
        ]

        logger.info(f"生成memray火焰图: {' '.join(flame_cmd)}")
        subprocess.run(flame_cmd, check=True)

        logger.info(f"Memray报告已生成: {html_output}")
        return str(html_output)
    except subprocess.CalledProcessError as e:
        logger.error(f"Memray分析失败: {e}")
        return None
    except Exception as e:
        logger.error(f"Memray执行异常: {e}")
        return None


def profile_similarity_detect(
    repo_path: str,
    output_dir: str = "profile_reports",
    use_scalene: bool = True,
    use_memray: bool = False,
) -> dict:
    results = {}

    script_code = f'''
import sys
sys.path.insert(0, "{Path(__file__).parent.parent.parent.parent}")
from gh_similarity_detector.cli.main import main
sys.argv = ["gh-sim", "detect", "{repo_path}"]
main()
'''

    script_path = Path(output_dir) / "profile_detect_script.py"
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text(script_code, encoding="utf-8")

    if use_scalene:
        results["scalene"] = run_scalene_profile(str(script_path), output_dir)

    if use_memray:
        results["memray"] = run_memray_profile(str(script_path), output_dir)

    return results


def main():
    parser = argparse.ArgumentParser(description="性能分析工具")
    parser.add_argument("--scalene", action="store_true", help="使用Scalene进行CPU+内存分析")
    parser.add_argument("--memray", action="store_true", help="使用Memray进行内存分析")
    parser.add_argument("--script", type=str, help="要分析的脚本路径")
    parser.add_argument("--repo", type=str, help="要分析的仓库路径（使用内置检测脚本）")
    parser.add_argument("--output", type=str, default="profile_reports", help="输出目录")

    args = parser.parse_args()

    if not args.scalene and not args.memray:
        args.scalene = True

    if args.script:
        results = {}
        if args.scalene:
            results["scalene"] = run_scalene_profile(args.script, args.output)
        if args.memray:
            results["memray"] = run_memray_profile(args.script, args.output)
    elif args.repo:
        results = profile_similarity_detect(
            args.repo, args.output, use_scalene=args.scalene, use_memray=args.memray
        )
    else:
        parser.print_help()
        return

    for tool, report_path in results.items():
        if report_path:
            print(f"{tool}报告: {report_path}")
        else:
            print(f"{tool}分析失败")


if __name__ == "__main__":
    main()
