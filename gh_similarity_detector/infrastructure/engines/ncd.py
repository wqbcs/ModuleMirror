"""
NCD (Normalized Compression Distance)

基于压缩算法的项目整体相似度度量。
语言无关，适合快速判断两个项目是否高度相似。

NCD(x,y) = (C(xy) - min(C(x), C(y))) / max(C(x), C(y))

其中 C(x) 是 x 的压缩后大小。
"""

from __future__ import annotations

import zlib
from typing import Optional, List, Tuple, Dict
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
from functools import partial

from ...utils.logger import logger


def _compress_size(data: bytes, level: int) -> int:
    return len(zlib.compress(data, level))


class NCD:
    """Normalized Compression Distance

    使用 zlib/gzip 作为压缩函数，计算两个代码库之间的整体相似度。
    NCD ≈ 0 表示高度相似，NCD ≈ 1 表示完全不同。
    支持并行压缩：多文件对同时计算。
    """

    MAX_TOTAL_BYTES = 50 * 1024 * 1024

    def __init__(self, compression_level: int = 6, max_workers: Optional[int] = None):
        self.compression_level = compression_level
        self.max_workers = max_workers

    def compress(self, data: bytes) -> int:
        """压缩数据并返回压缩后大小"""
        return len(zlib.compress(data, self.compression_level))

    def compute_distance(self, source: bytes, target: bytes) -> float:
        """计算 NCD 距离

        Args:
            source: 源数据
            target: 目标数据

        Returns:
            NCD 值，范围 [0, 1+]，0 表示完全相同
        """
        if not source and not target:
            return 0.0
        if not source or not target:
            return 1.0

        c_source = self.compress(source)
        c_target = self.compress(target)
        c_concat = self.compress(source + target)

        max_c = max(c_source, c_target)
        if max_c == 0:
            return 0.0

        ncd = (c_concat - min(c_source, c_target)) / max_c
        return max(0.0, ncd)

    def compute_similarity(self, source: bytes, target: bytes) -> float:
        """计算相似度 (1 - NCD)

        Args:
            source: 源数据
            target: 目标数据

        Returns:
            相似度，范围 [0, 100]
        """
        ncd = self.compute_distance(source, target)
        similarity = max(0.0, 1.0 - ncd) * 100
        return similarity

    def compute_project_similarity(
        self, source_dir: str, target_dir: str, extensions: Optional[List[str]] = None
    ) -> float:
        """计算两个项目目录的整体相似度

        Args:
            source_dir: 源项目目录
            target_dir: 目标项目目录
            extensions: 文件扩展名过滤

        Returns:
            相似度 [0, 100]
        """
        source_data = self._read_project(source_dir, extensions)
        target_data = self._read_project(target_dir, extensions)

        if not source_data or not target_data:
            logger.warning("项目目录为空或无法读取")
            return 0.0

        sim = self.compute_similarity(source_data, target_data)
        logger.info(
            f"NCD 项目相似度: {sim:.2f}% ({Path(source_dir).name} ↔ {Path(target_dir).name})"
        )
        return sim

    def _read_project(self, directory: str, extensions: Optional[List[str]] = None) -> bytes:
        """读取项目中所有代码文件并拼接，受 MAX_TOTAL_BYTES 限制"""
        dir_path = Path(directory)
        if not dir_path.exists():
            return b""

        chunks = []
        total_size = 0
        default_exts = {".py", ".js", ".ts", ".java", ".go", ".rs", ".c", ".cpp", ".h"}
        valid_exts = set(extensions) if extensions else default_exts

        for file_path in sorted(dir_path.rglob("*")):
            if not file_path.is_file():
                continue
            if file_path.suffix not in valid_exts:
                continue
            if any(
                p in file_path.parts
                for p in ("node_modules", ".git", "__pycache__", "venv", "vendor")
            ):
                continue
            try:
                content = file_path.read_bytes()
                total_size += len(content)
                if total_size > self.MAX_TOTAL_BYTES:
                    logger.warning(
                        f"NCD 输入超过 {self.MAX_TOTAL_BYTES // 1024 // 1024}MB 限制，截断"
                    )
                    break
                chunks.append(content)
            except Exception:
                continue

        return b"\n".join(chunks)

    def compute_distance_parallel(
        self,
        pairs: List[Tuple[bytes, bytes]],
    ) -> List[float]:
        """并行计算多对数据的 NCD 距离

        Args:
            pairs: (source, target) 字节对列表

        Returns:
            NCD 值列表，与 pairs 一一对应
        """
        if not pairs:
            return []
        compress_fn = partial(_compress_size, level=self.compression_level)
        all_data: List[bytes] = []
        index_map: List[Tuple[int, int, int, int]] = []
        for i, (src, tgt) in enumerate(pairs):
            si = len(all_data)
            all_data.append(src)
            ti = len(all_data)
            all_data.append(tgt)
            ci = len(all_data)
            all_data.append(src + tgt)
            index_map.append((si, ti, ci, i))
        if self.max_workers and self.max_workers > 1:
            compressed: Dict[int, int] = {}
            with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
                futures = {executor.submit(compress_fn, d): idx for idx, d in enumerate(all_data)}
                for future in as_completed(futures):
                    idx = futures[future]
                    compressed[idx] = future.result()
        else:
            compressed = {idx: compress_fn(d) for idx, d in enumerate(all_data)}
        results: List[float] = [0.0] * len(pairs)
        for si, ti, ci, pi in index_map:
            c_src = compressed[si]
            c_tgt = compressed[ti]
            c_concat = compressed[ci]
            max_c = max(c_src, c_tgt)
            if max_c == 0:
                results[pi] = 0.0
            else:
                results[pi] = max(0.0, (c_concat - min(c_src, c_tgt)) / max_c)
        return results

    def compute_similarity_parallel(
        self,
        pairs: List[Tuple[bytes, bytes]],
    ) -> List[float]:
        """并行计算多对数据的相似度

        Args:
            pairs: (source, target) 字节对列表

        Returns:
            相似度列表 [0, 100]，与 pairs 一一对应
        """
        distances = self.compute_distance_parallel(pairs)
        return [max(0.0, 1.0 - d) * 100 for d in distances]

    def compute_project_similarity_parallel(
        self,
        project_pairs: List[Tuple[str, str]],
        extensions: Optional[List[str]] = None,
    ) -> List[float]:
        """并行计算多对项目目录的相似度

        Args:
            project_pairs: (source_dir, target_dir) 路径对列表
            extensions: 文件扩展名过滤

        Returns:
            相似度列表 [0, 100]
        """
        data_pairs: List[Tuple[bytes, bytes]] = []
        for src_dir, tgt_dir in project_pairs:
            src_data = self._read_project(src_dir, extensions)
            tgt_data = self._read_project(tgt_dir, extensions)
            data_pairs.append((src_data, tgt_data))
        return self.compute_similarity_parallel(data_pairs)
