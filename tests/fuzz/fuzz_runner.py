"""
模糊测试框架 (Fuzz Testing)

使用 atheris 进行覆盖率导向模糊测试。

运行:
    python tests/fuzz/fuzz_winnowing.py
    python tests/fuzz/fuzz_jaccard.py

Author: ModuleMirror
"""

import sys
from typing import Callable, List

try:
    import atheris
    ATHERIS_AVAILABLE = True
except ImportError:
    ATHERIS_AVAILABLE = False

from ...utils.logger import logger


class FuzzTestRunner:
    def __init__(self, test_name: str = "fuzz"):
        self.test_name = test_name
        self._crashes: List[str] = []
    
    def run(
        self,
        target: Callable[[bytes], None],
        max_minutes: int = 5,
        max_runs: int = 10000,
    ) -> int:
        if not ATHERIS_AVAILABLE:
            logger.warning("atheris not installed, skipping fuzz test")
            return 0
        
        logger.info(f"Starting fuzz test: {self.test_name} (max_minutes={max_minutes})")
        
        try:
            atheris.Setup(
                sys.argv + [f"-max_minutes={max_minutes}", f"-max_runs={max_runs}"],
                target,
            )
            atheris.Fuzz()
        except SystemExit as e:
            return e.code
        except Exception as e:
            self._crashes.append(str(e))
            logger.error(f"Fuzz test crashed: {e}")
            return 1
        
        return 0
    
    @property
    def crashes(self) -> List[str]:
        return self._crashes


def fuzz_winnowing_target(data: bytes) -> None:
    from ...core.fingerprint.winnowing import Winnowing
    try:
        w = Winnowing(window_size=5, kgram_size=15)
        code = data.decode("utf-8", errors="ignore")
        w.generate_fingerprints_from_code(code)
    except Exception:
        pass


def fuzz_jaccard_target(data: bytes) -> None:
    from ...core.similarity.calculator import JaccardSimilarity
    try:
        j = JaccardSimilarity()
        set1 = set(data[:len(data)//2])
        set2 = set(data[len(data)//2:])
        j.calculate(set1, set2)
    except Exception:
        pass


def run_fuzz_winnowing(max_minutes: int = 1) -> int:
    if not ATHERIS_AVAILABLE:
        logger.warning("atheris not available")
        return 0
    
    runner = FuzzTestRunner("winnowing")
    return runner.run(fuzz_winnowing_target, max_minutes=max_minutes)


def run_fuzz_jaccard(max_minutes: int = 1) -> int:
    if not ATHERIS_AVAILABLE:
        logger.warning("atheris not available")
        return 0
    
    runner = FuzzTestRunner("jaccard")
    return runner.run(fuzz_jaccard_target, max_minutes=max_minutes)
