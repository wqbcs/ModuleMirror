"""
结果输出解耦 (ResultSink)

抽象结果输出接口，支持多种输出方式（JSON/HTML/Markdown/Stream）。
解耦检测流程与结果存储/展示。

Author: ModuleMirror
"""

from typing import List, Any
from abc import ABC, abstractmethod
from pathlib import Path
import json

from ..utils.logger import logger


class ResultSink(ABC):
    """结果输出抽象基类，定义写入、批量写入和刷新接口"""

    @abstractmethod
    def write(self, result: Any) -> None: ...

    @abstractmethod
    def write_batch(self, results: List[Any]) -> None: ...

    @abstractmethod
    def flush(self) -> None: ...


class JsonFileSink(ResultSink):
    """JSON 文件输出_sink，将结果缓冲后一次性写入 JSON 文件"""

    def __init__(self, output_path: str):
        self.output_path = Path(output_path)
        self._buffer: List[Any] = []

    def write(self, result: Any) -> None:
        """写入单条结果到缓冲区

        Args:
            result: 待写入的结果对象
        """
        self._buffer.append(result)

    def write_batch(self, results: List[Any]) -> None:
        """批量写入结果到缓冲区

        Args:
            results: 待写入的结果对象列表
        """
        self._buffer.extend(results)

    def flush(self) -> None:
        """将缓冲区中的所有结果写入 JSON 文件并清空缓冲区"""
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.output_path, "w", encoding="utf-8") as f:
            json.dump(self._buffer, f, indent=2, ensure_ascii=False, default=str)
        logger.info(f"结果已写入 JSON: {self.output_path} ({len(self._buffer)} 条)")
        self._buffer.clear()


class InMemorySink(ResultSink):
    """内存结果_sink，将结果保存在内存列表中，适用于测试和小规模数据"""

    def __init__(self, max_size: int = 10000):
        self.max_size = max_size
        self.results: List[Any] = []

    def write(self, result: Any) -> None:
        """写入单条结果，超过最大容量时自动淘汰最早的数据

        Args:
            result: 待写入的结果对象
        """
        self.results.append(result)
        if len(self.results) > self.max_size:
            self.results = self.results[-self.max_size :]

    def write_batch(self, results: List[Any]) -> None:
        """批量写入结果

        Args:
            results: 待写入的结果对象列表
        """
        self.results.extend(results)

    def flush(self) -> None:
        """内存_sink 无需刷新，此方法为空操作"""
        ...

    def get_latest(self, n: int = 1) -> List[Any]:
        """获取最近的 n 条结果

        Args:
            n: 获取的结果条数，默认1

        Returns:
            最近 n 条结果的列表
        """
        return self.results[-n:]

    @property
    def count(self) -> int:
        """返回当前结果总数"""
        return len(self.results)


class CompositeSink(ResultSink):
    """组合_sink，将结果同时写入多个子_sink，单个_sink失败不影响其他"""

    def __init__(self, sinks: List[ResultSink]):
        self.sinks = sinks

    def write(self, result: Any) -> None:
        """将结果写入所有子_sink

        Args:
            result: 待写入的结果对象
        """
        for sink in self.sinks:
            try:
                sink.write(result)
            except (OSError, ValueError, RuntimeError) as e:
                logger.error("result_sink_failed", error=str(e))

    def write_batch(self, results: List[Any]) -> None:
        """将批量结果写入所有子_sink

        Args:
            results: 待写入的结果对象列表
        """
        for sink in self.sinks:
            try:
                sink.write_batch(results)
            except (OSError, ValueError, RuntimeError) as e:
                logger.error("result_sink_failed", error=str(e))

    def flush(self) -> None:
        """刷新所有子_sink"""
        for sink in self.sinks:
            try:
                sink.flush()
            except (OSError, ValueError, RuntimeError) as e:
                logger.error("result_sink_failed", error=str(e))
