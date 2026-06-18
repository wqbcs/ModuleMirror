"""
Mutation Testing 配置

使用 mutmut 验证测试有效性，识别测试覆盖盲区。

运行:
    mutmut run --paths-to-mutate gh_similarity_detector/core/fingerprint/
    mutmut results
    mutmut show <mutation-id>

Author: ModuleMirror
"""

import subprocess
import sys
from pathlib import Path
from typing import List, Tuple, Optional
from dataclasses import dataclass

from ...utils.logger import logger


@dataclass
class MutationResult:
    total_mutations: int
    killed: int
    survived: int
    timeout: int
    suspicious: int
    
    @property
    def mutation_score(self) -> float:
        if self.total_mutations == 0:
            return 0.0
        return (self.killed / self.total_mutations) * 100
    
    @property
    def is_adequate(self) -> bool:
        return self.mutation_score >= 80.0


class MutationTestRunner:
    def __init__(self, project_dir: str = "."):
        self.project_dir = Path(project_dir)
    
    def run(
        self,
        paths: List[str],
        timeout: int = 300,
        workers: int = 4,
    ) -> MutationResult:
        cmd = [
            sys.executable, "-m", "mutmut", "run",
            "--paths-to-mutate", ",".join(paths),
            "--timeout", str(timeout),
            "--workers", str(workers),
        ]
        
        logger.info(f"Mutation testing: {paths}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=self.project_dir,
            timeout=timeout + 60,
        )
        
        return self._parse_output(result.stdout + result.stderr)
    
    def _parse_output(self, output: str) -> MutationResult:
        total = killed = survived = timeout = suspicious = 0
        for line in output.splitlines():
            if "mutmut" in line.lower():
                parts = line.split()
                for i, part in enumerate(parts):
                    if part.isdigit():
                        if i > 0 and "killed" in parts[i-1].lower():
                            killed = int(part)
                        elif i > 0 and "survived" in parts[i-1].lower():
                            survived = int(part)
                        elif i > 0 and "timeout" in parts[i-1].lower():
                            timeout = int(part)
        total = killed + survived + timeout + suspicious
        return MutationResult(
            total_mutations=total,
            killed=killed,
            survived=survived,
            timeout=timeout,
            suspicious=suspicious,
        )
    
    def get_results(self) -> Optional[str]:
        try:
            result = subprocess.run(
                [sys.executable, "-m", "mutmut", "results"],
                capture_output=True,
                text=True,
                cwd=self.project_dir,
                timeout=30,
            )
            return result.stdout
        except Exception:
            return None
    
    def show_surviving(self) -> List[str]:
        try:
            result = subprocess.run(
                [sys.executable, "-m", "mutmut", "results"],
                capture_output=True,
                text=True,
                cwd=self.project_dir,
                timeout=30,
            )
            surviving = []
            for line in result.stdout.splitlines():
                if "survived" in line.lower():
                    surviving.append(line.strip())
            return surviving
        except Exception:
            return []


def run_mutation_test(
    paths: List[str] = None,
    threshold: float = 80.0,
) -> Tuple[bool, MutationResult]:
    if paths is None:
        paths = ["gh_similarity_detector/core/fingerprint/winnowing.py"]
    
    runner = MutationTestRunner()
    result = runner.run(paths)
    
    logger.info(
        f"Mutation score: {result.mutation_score:.1f}% "
        f"({result.killed}/{result.total_mutations} killed)"
    )
    
    passed = result.mutation_score >= threshold
    if not passed:
        logger.warning(
            f"Mutation score below threshold: {result.mutation_score:.1f}% < {threshold}%"
        )
    
    return passed, result
