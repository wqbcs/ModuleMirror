"""
优雅关闭管理器

实现 12-Factor App 第9条（易处置性）：
1. SIGTERM/SIGINT 信号捕获
2. 拒绝新请求
3. 排空进行中的请求
4. 关闭数据库连接池
5. 刷新缓存到磁盘
6. 关闭外部连接（HTTP client等）
7. 超时保护（强制退出）
"""

import asyncio
import signal
import time
from typing import Optional, Callable, List, Dict, Any
from dataclasses import dataclass
from enum import Enum

from ...utils.logger import logger


class ShutdownState(Enum):
    RUNNING = "running"
    DRAINING = "draining"
    SHUTDOWN = "shutdown"


@dataclass
class ShutdownHook:
    """关闭钩子"""

    name: str
    callback: Callable
    priority: int = 100
    timeout: float = 30.0


class GracefulShutdown:
    """优雅关闭管理器

    信号触发后进入 draining 状态：
    - 拒绝新请求
    - 等待进行中请求完成
    - 按优先级执行关闭钩子
    - 超时后强制退出
    """

    def __init__(self, drain_timeout: float = 30.0, force_timeout: float = 60.0):
        self._state = ShutdownState.RUNNING
        self._drain_timeout = drain_timeout
        self._force_timeout = force_timeout
        self._hooks: List[ShutdownHook] = []
        self._active_requests = 0
        self._shutdown_started_at: Optional[float] = None
        self._registered = False

    @property
    def state(self) -> ShutdownState:
        return self._state

    @property
    def is_running(self) -> bool:
        return self._state == ShutdownState.RUNNING

    @property
    def is_draining(self) -> bool:
        return self._state == ShutdownState.DRAINING

    def register_hook(
        self,
        name: str,
        callback: Callable,
        priority: int = 100,
        timeout: float = 30.0,
    ) -> None:
        """注册关闭钩子

        priority越小越先执行。
        """
        hook = ShutdownHook(name=name, callback=callback, priority=priority, timeout=timeout)
        self._hooks.append(hook)
        self._hooks.sort(key=lambda h: h.priority)
        logger.debug(f"注册关闭钩子: {name} (priority={priority})")

    def register_signals(self) -> None:
        """注册信号处理器"""
        if self._registered:
            return
        try:
            signal.signal(signal.SIGTERM, self._signal_handler)
            signal.signal(signal.SIGINT, self._signal_handler)
            self._registered = True
            logger.info("优雅关闭信号处理器已注册")
        except (OSError, ValueError) as e:
            logger.warning(f"信号注册失败（非主线程?）: {e}")

    def _signal_handler(self, signum: int, frame) -> None:
        logger.info(f"收到信号 {signum}，启动优雅关闭...")
        self.initiate_shutdown()

    def initiate_shutdown(self) -> None:
        """启动优雅关闭"""
        if self._state != ShutdownState.RUNNING:
            return
        self._state = ShutdownState.DRAINING
        self._shutdown_started_at = time.monotonic()
        logger.info(
            f"进入 DRAINING 状态 (drain_timeout={self._drain_timeout}s, "
            f"active_requests={self._active_requests})"
        )

    def begin_request(self) -> bool:
        """开始处理请求

        Returns:
            True=允许处理, False=正在关闭拒绝
        """
        if self._state != ShutdownState.RUNNING:
            return False
        self._active_requests += 1
        return True

    def end_request(self) -> None:
        """请求处理完成"""
        self._active_requests = max(0, self._active_requests - 1)

    @property
    def active_requests(self) -> int:
        return self._active_requests

    async def execute_shutdown(self) -> Dict[str, Any]:
        """执行关闭流程

        Returns:
            各钩子执行结果
        """
        if self._state == ShutdownState.SHUTDOWN:
            return {}

        self._state = ShutdownState.DRAINING
        if self._shutdown_started_at is None:
            self._shutdown_started_at = time.monotonic()

        drain_start = time.monotonic()
        while self._active_requests > 0:
            elapsed = time.monotonic() - drain_start
            if elapsed > self._drain_timeout:
                logger.warning(
                    f"排空超时 ({self._drain_timeout}s), "
                    f"剩余 {self._active_requests} 个活跃请求, 强制关闭"
                )
                break
            logger.info(f"等待请求排空: {self._active_requests} 个活跃, 已等待 {elapsed:.1f}s")
            await asyncio.sleep(0.5)

        logger.info("请求排空完成，执行关闭钩子...")
        results = {}

        for hook in self._hooks:
            try:
                start = time.monotonic()
                if asyncio.iscoroutinefunction(hook.callback):
                    await asyncio.wait_for(hook.callback(), timeout=hook.timeout)
                else:
                    hook.callback()

                elapsed = time.monotonic() - start
                results[hook.name] = {"status": "ok", "elapsed": round(elapsed, 3)}
                logger.info(f"关闭钩子完成: {hook.name} ({elapsed:.3f}s)")
            except asyncio.TimeoutError:
                results[hook.name] = {"status": "timeout", "timeout": hook.timeout}
                logger.warning(f"关闭钩子超时: {hook.name} ({hook.timeout}s)")
            except Exception as e:
                results[hook.name] = {"status": "error", "error": str(e)}
                logger.error(f"关闭钩子失败: {hook.name} - {e}")

        self._state = ShutdownState.SHUTDOWN
        logger.info("优雅关闭完成")
        return results

    @property
    def stats(self) -> Dict[str, Any]:
        elapsed = 0.0
        if self._shutdown_started_at is not None:
            elapsed = time.monotonic() - self._shutdown_started_at
        return {
            "state": self._state.value,
            "active_requests": self._active_requests,
            "hook_count": len(self._hooks),
            "drain_timeout": self._drain_timeout,
            "force_timeout": self._force_timeout,
            "elapsed_since_shutdown": round(elapsed, 2) if self._shutdown_started_at else None,
        }


graceful_shutdown = GracefulShutdown()
