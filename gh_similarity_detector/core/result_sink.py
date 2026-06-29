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
    @abstractmethod
    def write(self, result: Any) -> None: ...

    @abstractmethod
    def write_batch(self, results: List[Any]) -> None: ...

    @abstractmethod
    def flush(self) -> None: ...


class JsonFileSink(ResultSink):
    def __init__(self, output_path: str):
        self.output_path = Path(output_path)
        self._buffer: List[Any] = []

    def write(self, result: Any) -> None:
        self._buffer.append(result)

    def write_batch(self, results: List[Any]) -> None:
        self._buffer.extend(results)

    def flush(self) -> None:
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.output_path, "w", encoding="utf-8") as f:
            json.dump(self._buffer, f, indent=2, ensure_ascii=False, default=str)
        logger.info(f"结果已写入 JSON: {self.output_path} ({len(self._buffer)} 条)")
        self._buffer.clear()


class InMemorySink(ResultSink):
    def __init__(self, max_size: int = 10000):
        self.max_size = max_size
        self.results: List[Any] = []

    def write(self, result: Any) -> None:
        self.results.append(result)
        if len(self.results) > self.max_size:
            self.results = self.results[-self.max_size :]

    def write_batch(self, results: List[Any]) -> None:
        self.results.extend(results)

    def flush(self) -> None:
        ...

    def get_latest(self, n: int = 1) -> List[Any]:
        return self.results[-n:]

    @property
    def count(self) -> int:
        return len(self.results)


class CompositeSink(ResultSink):
    def __init__(self, sinks: List[ResultSink]):
        self.sinks = sinks

    def write(self, result: Any) -> None:
        for sink in self.sinks:
            try:
                sink.write(result)
            except (OSError, ValueError, RuntimeError) as e:
                logger.error("result_sink_failed", error=str(e))

    def write_batch(self, results: List[Any]) -> None:
        for sink in self.sinks:
            try:
                sink.write_batch(results)
            except (OSError, ValueError, RuntimeError) as e:
                logger.error("result_sink_failed", error=str(e))

    def flush(self) -> None:
        for sink in self.sinks:
            try:
                sink.flush()
            except (OSError, ValueError, RuntimeError) as e:
                logger.error("result_sink_failed", error=str(e))
