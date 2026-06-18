"""
jscpd 集成适配器

将 jscpd 作为辅助检测引擎，用于 Token + 滚动哈希检测。
jscpd 支持 170+ 语言的代码克隆检测，作为 Winnowing 的交叉验证。

使用前需安装: npm install -g jscpd
"""

import json
import subprocess
import tempfile
from typing import List, Dict, Optional
from pathlib import Path

from ...models.results import SimilarityResult
from ...utils.logger import logger


class JscpdAdapter:
    """jscpd 适配器

    调用 jscpd CLI 进行代码克隆检测，将结果转换为 SimilarityResult。
    """

    def __init__(self, min_lines: int = 5, min_tokens: int = 50):
        self.min_lines = min_lines
        self.min_tokens = min_tokens
        self._available = self._check_available()

    def _check_available(self) -> bool:
        try:
            result = subprocess.run(
                ['jscpd', '--version'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                logger.info(f"jscpd 可用，版本: {result.stdout.strip()}")
                return True
            else:
                logger.warning("jscpd 不可用，请安装: npm install -g jscpd")
                return False
        except (FileNotFoundError, subprocess.TimeoutExpired):
            logger.warning("jscpd 未安装，辅助检测不可用。安装: npm install -g jscpd")
            return False

    @property
    def is_available(self) -> bool:
        return self._available

    def detect(
        self,
        source_path: str,
        target_path: str,
        languages: Optional[List[str]] = None
    ) -> List[SimilarityResult]:
        """使用 jscpd 检测两个目录间的代码克隆

        Args:
            source_path: 源项目路径
            target_path: 目标项目路径
            languages: 编程语言过滤

        Returns:
            相似度结果列表
        """
        if not self.is_available:
            logger.warning("jscpd 不可用，跳过辅助检测")
            return []

        cmd = [
            'jscpd', source_path, target_path,
            '--min-lines', str(self.min_lines),
            '--min-tokens', str(self.min_tokens),
            '--reporters', 'json',
            '--format', ','.join(languages) if languages else 'python,javascript,java',
        ]

        try:
            with tempfile.TemporaryDirectory(prefix='jscpd_') as tmp_dir:
                cmd.extend(['--output', tmp_dir])
                subprocess.run(
                    cmd, capture_output=True, text=True, timeout=120
                )

                result_path = Path(tmp_dir) / "jscpd-report.json"
                if not result_path.exists():
                    logger.warning("jscpd 未生成报告文件")
                    return []

                with open(result_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

            return self._convert_results(data, source_path, target_path)

        except subprocess.TimeoutExpired:
            logger.error("jscpd 检测超时")
            return []
        except Exception as e:
            logger.error(f"jscpd 检测失败: {e}")
            return []

    def _convert_results(
        self,
        data: Dict,
        source_path: str,
        target_path: str
    ) -> List[SimilarityResult]:
        """将 jscpd 结果转换为 SimilarityResult"""
        results = []
        duplicates = data.get('duplicates', [])

        for dup in duplicates:
            fragments = dup.get('files', [])
            if len(fragments) < 2:
                continue

            for i in range(len(fragments)):
                for j in range(i + 1, len(fragments)):
                    f1 = fragments[i]
                    f2 = fragments[j]

                    source_file = f1.get('name', '')
                    target_file = f2.get('name', '')

                    if not (source_file.startswith(source_path) or target_file.startswith(target_path)):
                        if not (source_file.startswith(target_path) or target_file.startswith(source_path)):
                            continue

                    lines = dup.get('lines', 0)
                    tokens = dup.get('tokens', 0)

                    fraction = dup.get('fraction', 0)
                    similarity = min(100.0, fraction * 100) if fraction > 0 else min(100.0, (tokens / max(self.min_tokens, 1)) * 50)

                    result = SimilarityResult(
                        source_module_id=f"{source_file}:{f1.get('start', 0)}-{f1.get('end', 0)}",
                        target_module_id=f"{target_file}:{f2.get('start', 0)}-{f2.get('end', 0)}",
                        similarity=similarity,
                        matched_code_snippet={
                            "source_file": source_file,
                            "source_lines": f"{f1.get('start', 0)}-{f1.get('end', 0)}",
                            "target_file": target_file,
                            "target_lines": f"{f2.get('start', 0)}-{f2.get('end', 0)}",
                            "duplicated_lines": lines,
                            "duplicated_tokens": tokens,
                        }
                    )
                    results.append(result)

        results.sort(key=lambda x: x.similarity, reverse=True)
        logger.info(f"jscpd 检测完成: {len(results)} 个克隆对")
        return results
