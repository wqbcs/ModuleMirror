"""
Polars DataFrame批处理 - 大规模数据处理

使用polars替代pandas进行大规模相似度结果处理。
polars比pandas快10x以上，内存占用更低。

Author: ModuleMirror
"""

from __future__ import annotations

from typing import Dict, List, Any, Optional
from pathlib import Path

try:
    import polars as pl

    HAS_POLARS = True
except ImportError:
    HAS_POLARS = False
    pl = None  # type: ignore[assignment]

from ...utils.logger import logger


class SimilarityDataFrame:
    """相似度结果DataFrame（Polars实现）

    对比pandas实现:
    - 性能：10x+加速
    - 内存：减少50%+
    - 并行：自动多线程

    使用场景:
    - 批量检测结果聚合
    - 相似度矩阵计算
    - 报告数据导出
    """

    def __init__(self) -> None:
        if not HAS_POLARS:
            raise ImportError("polars未安装，请运行: pip install polars")
        self._df: Optional[Any] = None

    def from_results(self, results: List[Dict[str, Any]]) -> "SimilarityDataFrame":
        """从检测结果创建DataFrame

        Args:
            results: 检测结果列表

        Returns:
            self（链式调用）
        """
        if not results:
            self._df = pl.DataFrame(
                schema={
                    "source_module": str,
                    "target_module": str,
                    "similarity": float,
                    "source_file": str,
                    "target_file": str,
                }
            )
            return self

        rows = []
        for result in results:
            matches = result.get("matches", [])
            for match in matches:
                rows.append(
                    {
                        "source_module": result.get("source_module", ""),
                        "target_module": result.get("target_module", ""),
                        "similarity": match.get("similarity", 0.0),
                        "source_file": match.get("source_file", ""),
                        "target_file": match.get("target_file", ""),
                    }
                )

        self._df = pl.DataFrame(rows)
        return self

    def filter_by_threshold(self, min_similarity: float = 0.7) -> "SimilarityDataFrame":
        """按相似度阈值过滤

        Args:
            min_similarity: 最小相似度

        Returns:
            self（链式调用）
        """
        if self._df is not None:
            self._df = self._df.filter(pl.col("similarity") >= min_similarity)
        return self

    def group_by_module(self) -> Any:
        """按模块聚合统计

        Returns:
            聚合结果DataFrame
        """
        if self._df is None or self._df.is_empty():
            return pl.DataFrame()

        return self._df.group_by(["source_module", "target_module"]).agg(
            [
                pl.col("similarity").mean().alias("avg_similarity"),
                pl.col("similarity").max().alias("max_similarity"),
                pl.col("similarity").min().alias("min_similarity"),
                pl.len().alias("match_count"),
            ]
        )

    def top_similar_pairs(self, top_k: int = 100) -> Any:
        """获取TopK相似模块对

        Args:
            top_k: 返回数量

        Returns:
            TopK结果
        """
        if self._df is None or self._df.is_empty():
            return pl.DataFrame()

        return (
            self._df.group_by(["source_module", "target_module"])
            .agg([pl.col("similarity").mean().alias("avg_similarity")])
            .sort("avg_similarity", descending=True)
            .head(top_k)
        )

    def build_similarity_matrix(self) -> Any:
        """构建相似度矩阵

        Returns:
            相似度矩阵（宽表格式）
        """
        if self._df is None or self._df.is_empty():
            return pl.DataFrame()

        aggregated = self._df.group_by(["source_module", "target_module"]).agg(
            [pl.col("similarity").mean().alias("similarity")]
        )

        modules = aggregated.select(["source_module"]).unique().rename({"source_module": "module"})
        other_modules = (
            aggregated.select(["target_module"]).unique().rename({"target_module": "module"})
        )
        all_modules = modules.vstack(other_modules).unique()
        _ = all_modules

        matrix = aggregated.pivot(
            values="similarity",
            index="source_module",
            on="target_module",
        )

        return matrix

    def export_csv(self, output_path: str) -> str:
        """导出为CSV

        Args:
            output_path: 输出路径

        Returns:
            输出路径
        """
        if self._df is None:
            logger.warning("DataFrame为空，跳过导出")
            return ""

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        self._df.write_csv(output_path)
        logger.info(f"CSV已导出: {output_path}")
        return output_path

    def export_json(self, output_path: str) -> str:
        """导出为JSON

        Args:
            output_path: 输出路径

        Returns:
            输出路径
        """
        if self._df is None:
            logger.warning("DataFrame为空，跳过导出")
            return ""

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        rows = self._df.to_dicts()

        from ...utils.json_utils import dumps

        Path(output_path).write_text(dumps(rows, ensure_ascii=False, indent=True), encoding="utf-8")

        logger.info(f"JSON已导出: {output_path}")
        return output_path

    def statistics(self) -> Dict[str, Any]:
        """统计信息

        Returns:
            统计字典
        """
        if self._df is None or self._df.is_empty():
            return {
                "total_rows": 0,
                "unique_modules": 0,
                "avg_similarity": 0.0,
                "max_similarity": 0.0,
                "min_similarity": 0.0,
            }

        modules = (
            self._df.select(["source_module"])
            .unique()
            .vstack(
                self._df.select(["target_module"])
                .unique()
                .rename({"target_module": "source_module"})
            )
            .unique()
            .height
        )

        return {
            "total_rows": self._df.height,
            "unique_modules": modules,
            "avg_similarity": self._df["similarity"].mean(),
            "max_similarity": self._df["similarity"].max(),
            "min_similarity": self._df["similarity"].min(),
        }

    @property
    def df(self) -> Optional[pl.DataFrame]:
        """获取内部DataFrame"""
        return self._df

    @property
    def row_count(self) -> int:
        """行数"""
        return self._df.height if self._df is not None else 0
