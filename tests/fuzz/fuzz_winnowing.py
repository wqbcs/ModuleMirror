#!/usr/bin/env python3
"""
Winnowing 模糊测试

运行: python tests/fuzz/fuzz_winnowing.py
"""

import sys
import atheris

from gh_similarity_detector.core.fingerprint.winnowing import Winnowing


@atheris.instrument
def test_winnowing(data: bytes) -> None:
    try:
        w = Winnowing(window_size=5, kgram_size=15)
        code = data.decode("utf-8", errors="ignore")
        fps = w.generate_fingerprints_from_code(code)
    except Exception:
        pass


if __name__ == "__main__":
    atheris.Setup(sys.argv, test_winnowing)
    atheris.Fuzz()
