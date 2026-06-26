"""
配置热重载模块

监听 YAML 配置文件变更，自动重载配置无需重启服务。
支持:
- 文件系统轮询检测变更
- 配置变更回调通知
- 环境变量覆盖
- 手动触发重载

环境变量:
- MODULEMIRROR_CONFIG_PATH: 配置文件路径 (默认 config.yaml)
- MODULEMIRROR_CONFIG_POLL_INTERVAL: 轮询间隔秒数 (默认 5)
"""

from __future__ import annotations

import os
import time
import threading
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from ..utils.logger import logger


class ConfigReloader:
    def __init__(
        self,
        config_path: Optional[str] = None,
        poll_interval: float = 5.0,
    ) -> None:
        self._config_path = Path(config_path or os.getenv("MODULEMIRROR_CONFIG_PATH", "config.yaml"))
        self._poll_interval = poll_interval
        self._callbacks: List[Callable[[Dict[str, Any]], None]] = []
        self._last_mtime: Optional[float] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._config_cache: Dict[str, Any] = {}
        self._lock = threading.Lock()
        self._reload_count = 0

    @property
    def config_path(self) -> Path:
        return self._config_path

    @property
    def reload_count(self) -> int:
        return self._reload_count

    @property
    def is_running(self) -> bool:
        return self._running

    def on_change(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        self._callbacks.append(callback)

    def load_config(self) -> Dict[str, Any]:
        if not self._config_path.exists():
            return {}
        try:
            import yaml
            with open(self._config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            with self._lock:
                old_config = self._config_cache.copy()
                self._config_cache = data
            if old_config and old_config != data:
                self._reload_count += 1
                logger.info(f"配置已热重载: {self._config_path} (第{self._reload_count}次)")
                self._notify_callbacks(data)
            elif not old_config:
                with self._lock:
                    self._config_cache = data
            return data
        except Exception as e:
            logger.error(f"配置加载失败: {self._config_path}, error={e}")
            return self._config_cache

    def force_reload(self) -> Dict[str, Any]:
        self._last_mtime = None
        return self.load_config()

    def _notify_callbacks(self, config: Dict[str, Any]) -> None:
        for callback in self._callbacks:
            try:
                callback(config)
            except Exception as e:
                logger.error(f"配置变更回调异常: {callback.__name__}, error={e}")

    def _check_and_reload(self) -> bool:
        if not self._config_path.exists():
            return False
        try:
            mtime = self._config_path.stat().st_mtime
        except OSError:
            return False
        if self._last_mtime is not None and mtime <= self._last_mtime:
            return False
        self._last_mtime = mtime
        self.load_config()
        return True

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._last_mtime = None
        self._check_and_reload()
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
        logger.info(f"配置热重载已启动: path={self._config_path}, interval={self._poll_interval}s")

    def stop(self) -> None:
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=self._poll_interval * 2)
        logger.info("配置热重载已停止")

    def _poll_loop(self) -> None:
        while self._running:
            try:
                self._check_and_reload()
            except Exception as e:
                logger.error(f"配置轮询异常: {e}")
            time.sleep(self._poll_interval)

    @property
    def stats(self) -> Dict[str, Any]:
        return {
            "config_path": str(self._config_path),
            "config_exists": self._config_path.exists(),
            "poll_interval": self._poll_interval,
            "is_running": self._running,
            "reload_count": self._reload_count,
            "callback_count": len(self._callbacks),
            "last_mtime": self._last_mtime,
        }


config_reloader = ConfigReloader(
    poll_interval=float(os.getenv("MODULEMIRROR_CONFIG_POLL_INTERVAL", "5")),
)
