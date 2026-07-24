"""
i18n 核心实现

基于消息键查找的国际化系统，支持：
- 多语言消息注册
- 带插值参数的消息模板
- 回退链 (locale -> default -> key)
- 线程安全 locale 切换

Author: ModuleMirror
"""

from __future__ import annotations

import threading
from typing import Dict, Optional, Any

_DEFAULT_LOCALE = "zh"
_SUPPORTED_LOCALES = {"zh", "en"}

_MESSAGES: Dict[str, Dict[str, str]] = {
    "zh": {
        "error.config.invalid": "配置无效: {detail}",
        "error.config.missing_field": "缺少必填配置项: {field}",
        "error.db.connection": "数据库连接失败: {detail}",
        "error.db.query": "数据库查询失败: {detail}",
        "error.db.migration": "数据库迁移失败: {from_ver} -> {to_ver}",
        "error.db.transaction": "事务失败: {detail}",
        "error.detect.no_fingerprints": "模块 {module} 无指纹数据",
        "error.detect.no_modules": "未找到可检测的模块",
        "error.detect.threshold_invalid": "相似度阈值无效: {value} (应在 0-1 之间)",
        "error.detect.project_not_found": "项目未找到: {project}",
        "error.io.file_not_found": "文件未找到: {path}",
        "error.io.read_failed": "文件读取失败: {path}",
        "error.io.write_failed": "文件写入失败: {path}",
        "error.io.parse_failed": "文件解析失败: {path} ({detail})",
        "error.auth.unauthorized": "未授权: {detail}",
        "error.auth.forbidden": "无权限: {detail}",
        "error.auth.token_expired": "Token 已过期",
        "error.auth.token_invalid": "Token 无效: {detail}",
        "error.rate_limit.exceeded": "速率限制: {detail}",
        "error.security.ssrf": "SSRF 防护: URL 不在白名单中 ({url})",
        "error.security.hash_mismatch": "依赖哈希不匹配: {name}",
        "error.security.audit_tampered": "审计日志被篡改: 行 {line}",
        "error.network.timeout": "网络超时: {url}",
        "error.network.connection": "网络连接失败: {url}",
        "error.network.rate_limited": "请求被限流: 请稍后重试",
        "error.github.api": "GitHub API 错误: {status} {detail}",
        "error.github.repo_not_found": "仓库未找到: {repo}",
        "error.github.auth_failed": "GitHub 认证失败",
        "info.detect.start": "开始检测: {project}",
        "info.detect.complete": "检测完成: 发现 {count} 个相似模块",
        "info.detect.progress": "检测进度: {current}/{total} ({pct}%)",
        "info.fingerprint.generate": "生成指纹: {module} ({count} 个指纹)",
        "info.fingerprint.cache_hit": "指纹缓存命中: {module}",
        "info.fingerprint.cache_miss": "指纹缓存未命中: {module}",
        "info.db.migration": "数据库迁移: {from_ver} -> {to_ver}",
        "info.db.backup": "数据库备份: {path}",
        "info.release.created": "发布创建: v{version}",
        "info.release.changelog": "变更日志生成: v{version}",
        "warn.detect.low_similarity": "相似度低于阈值: {sim} < {threshold}",
        "warn.detect.large_file": "大文件可能影响性能: {path} ({size})",
        "warn.config.deprecated": "配置项已弃用: {key} (请使用 {alternative})",
        "warn.security.insecure_token": "Token 使用不安全存储方式",
        "warn.rate_limit.approaching": "接近速率限制: {remaining} 次剩余",
        "success.detect.save": "检测结果已保存: {path}",
        "success.fingerprint.store": "指纹已存储: {module}",
        "success.auth.login": "登录成功: {user}",
        "error.resilience.circuit_open": "断路器已断开: {service} (请 {retry_after} 秒后重试)",
        "error.resilience.pool_exhausted": "连接池耗尽: {pool}",
        "error.infrastructure.connection": "基础设施连接失败: {detail}",
        "error.dependency.missing": "可选依赖 {package} 不可用（{feature} 功能需要）",
        "error.config.invalid_threshold": "相似度阈值 {value} 无效，有效范围: {valid_range}",
        "error.config.unsupported_language": "不支持的语言: {language}",
        "error.fingerprint.tokenization": "Tokenization 失败 (language={language}): {reason}",
        "error.fingerprint.winnowing": "Winnowing 计算失败: {reason}",
        "error.similarity.empty_fingerprint": "模块 {module_id} 指纹为空，无法计算相似度",
        "error.storage.database": "数据库操作失败: {reason}",
        "error.storage.cache": "缓存操作失败: {reason}",
        "error.project.fetch": "项目获取失败 ({source}): {reason}",
        "error.project.module_extraction": "模块提取失败 ({file_path}): {reason}",
        "error.api.rate_limit": "API 限流，请 {retry_after:.0f} 秒后重试",
        "error.api.auth": "认证失败",
        "error.api.not_found": "资源不存在: {resource}",
        "error.api.circuit_open": "断路器已断开 ({service})，请 {recovery_timeout:.0f} 秒后重试",
        "error.infra.pool": "连接池错误: {reason}",
        "error.infra.resilience": "弹性组件错误 ({component}): {reason}",
        "error.infra.ssrf": "SSRF 防护拦截: {reason}",
        "cli.detect.no_target": "未指定目标项目，请使用 -t 或 --target 参数",
        "cli.detect.no_candidates": "未指定候选项目，请使用 -c 或 --candidates 参数",
        "cli.detect.invalid_language": "不支持的语言: {language}，支持: {supported}",
        "cli.detect.invalid_threshold": "阈值 {value} 无效，有效范围: 0-100",
        "cli.detect.starting": "开始检测 {target} vs {candidates}...",
        "cli.detect.completed": "检测完成: {count} 个匹配 (耗时 {elapsed:.1f}s)",
        "cli.detect.no_matches": "未发现相似模块 (阈值: {threshold}%)",
        "cli.plagiarism.no_db": "指纹库不存在: {path}，请先使用 gh-sim db add 构建",
        "cli.plagiarism.tracing": "追踪克隆来源: {project}...",
        "cli.plagiarism.found": "发现 {count} 个抄袭嫌疑 (置信度: {confidence}%)",
        "cli.ncd.computing": "计算 NCD 压缩距离...",
        "cli.ncd.result": "NCD 相似度: {similarity:.2%}",
        "cli.db.adding": "添加项目到指纹库: {project}...",
        "cli.db.added": "已添加 {modules} 个模块 ({fingerprints} 个指纹)",
        "cli.db.removing": "移除项目: {project_id}...",
        "cli.db.stats": "指纹库: {projects} 项目, {modules} 模块, {fingerprints} 指纹",
        "cli.search.searching": "搜索 GitHub: {query}...",
        "cli.search.results": "找到 {count} 个仓库",
        "cli.config.show": "当前配置:",
        "cli.config.saved": "配置已保存: {path}",
        "cli.config.reloaded": "配置已重新加载",
        "cli.export.no_results": "无可导出的检测结果",
        "cli.export.exported": "结果已导出: {path} ({format})",
        "cli.init.welcome": "欢迎使用 ModuleMirror! 让我们完成首次检测配置",
        "cli.init.step": "步骤 {step}/3: {description}",
        "cli.init.complete": "配置完成! 运行 gh-sim detect 开始检测",
        "report.generating": "生成报告: {format}...",
        "report.generated": "报告已生成: {path}",
        "report.pdf.failed": "PDF 生成失败: {reason}",
        "report.sarif.failed": "SARIF 生成失败: {reason}",
        "report.html.failed": "HTML 生成失败: {reason}",
        "report.csv.exported": "CSV 已导出: {path} ({rows} 行)",
        "cluster.computing": "计算聚类分析 ({algorithm})...",
        "cluster.completed": "聚类完成: {n_clusters} 个簇, 轮廓系数: {silhouette:.3f}",
        "cluster.no_data": "聚类分析需要至少 2 个检测结果",
        "frequency.analyzing": "分析匹配频率...",
        "frequency.rare_matches": "稀有匹配: {count} 个 (权重: {weighting})",
        "frequency.strategy": "频率策略: {strategy}",
        "crosslang.detecting": "跨语言检测: {source_lang} -> {target_lang}...",
        "crosslang.ir_channel": "IR 通道相似度: {score:.2%}",
        "crosslang.embedding_channel": "Embedding 通道相似度: {score:.2%}",
        "crosslang.fused": "融合相似度: {score:.2%} (IR={ir_weight}, Emb={emb_weight})",
        "lineage.tracing": "追踪克隆血统: {module_id}...",
        "lineage.depth": "血统深度: {depth}, 分支: {branches}",
        "lineage.root": "克隆源头: {project} ({timestamp})",
        "quality.evaluating": "评估质量门禁 ({gate_type})...",
        "quality.passed": "质量门禁通过 ✓ ({score}/{max_score})",
        "quality.failed": "质量门禁未通过 ✗ ({score}/{max_score}, 最低: {threshold})",
        "sbp.analyzing": "SBP 分析: 检测相似但已修补的代码...",
        "sbp.cve_match": "CVE 模式匹配: {cve_id} (严重度: {severity})",
        "sbp.security_patch": "安全补丁检测: {count} 个匹配",
        "sbp.fingerprint_diff": "指纹差集: {added} 新增, {removed} 移除",
        "task.created": "异步任务已创建: {task_id}",
        "task.running": "任务运行中: {progress:.0%} ({step})",
        "task.completed": "任务完成: {task_id}",
        "task.failed": "任务失败: {task_id} ({reason})",
        "task.cancelled": "任务已取消: {task_id}",
        "webhook.received": "Webhook 事件: {event_type}",
        "webhook.triggered": "触发检测: {repo}/{branch}",
        "webhook.invalid_signature": "Webhook 签名验证失败",
        "plugin.loaded": "插件加载: {name} v{version}",
        "plugin.not_found": "插件未找到: {name}",
        "plugin.error": "插件执行错误 ({name}): {reason}",
    },
    "en": {
        "error.config.invalid": "Invalid configuration: {detail}",
        "error.config.missing_field": "Missing required config field: {field}",
        "error.db.connection": "Database connection failed: {detail}",
        "error.db.query": "Database query failed: {detail}",
        "error.db.migration": "Database migration failed: {from_ver} -> {to_ver}",
        "error.db.transaction": "Transaction failed: {detail}",
        "error.detect.no_fingerprints": "Module {module} has no fingerprint data",
        "error.detect.no_modules": "No modules found for detection",
        "error.detect.threshold_invalid": "Invalid similarity threshold: {value} (should be 0-1)",
        "error.detect.project_not_found": "Project not found: {project}",
        "error.io.file_not_found": "File not found: {path}",
        "error.io.read_failed": "File read failed: {path}",
        "error.io.write_failed": "File write failed: {path}",
        "error.io.parse_failed": "File parse failed: {path} ({detail})",
        "error.auth.unauthorized": "Unauthorized: {detail}",
        "error.auth.forbidden": "Forbidden: {detail}",
        "error.auth.token_expired": "Token expired",
        "error.auth.token_invalid": "Invalid token: {detail}",
        "error.rate_limit.exceeded": "Rate limit exceeded: {detail}",
        "error.security.ssrf": "SSRF protection: URL not in whitelist ({url})",
        "error.security.hash_mismatch": "Dependency hash mismatch: {name}",
        "error.security.audit_tampered": "Audit log tampered: line {line}",
        "error.network.timeout": "Network timeout: {url}",
        "error.network.connection": "Network connection failed: {url}",
        "error.network.rate_limited": "Rate limited: please retry later",
        "error.github.api": "GitHub API error: {status} {detail}",
        "error.github.repo_not_found": "Repository not found: {repo}",
        "error.github.auth_failed": "GitHub authentication failed",
        "info.detect.start": "Detection started: {project}",
        "info.detect.complete": "Detection complete: {count} similar modules found",
        "info.detect.progress": "Detection progress: {current}/{total} ({pct}%)",
        "info.fingerprint.generate": "Generating fingerprints: {module} ({count} fingerprints)",
        "info.fingerprint.cache_hit": "Fingerprint cache hit: {module}",
        "info.fingerprint.cache_miss": "Fingerprint cache miss: {module}",
        "info.db.migration": "Database migration: {from_ver} -> {to_ver}",
        "info.db.backup": "Database backup: {path}",
        "info.release.created": "Release created: v{version}",
        "info.release.changelog": "Changelog generated: v{version}",
        "warn.detect.low_similarity": "Similarity below threshold: {sim} < {threshold}",
        "warn.detect.large_file": "Large file may impact performance: {path} ({size})",
        "warn.config.deprecated": "Deprecated config: {key} (use {alternative})",
        "warn.security.insecure_token": "Token using insecure storage",
        "warn.rate_limit.approaching": "Approaching rate limit: {remaining} remaining",
        "success.detect.save": "Detection results saved: {path}",
        "success.fingerprint.store": "Fingerprints stored: {module}",
        "success.auth.login": "Login successful: {user}",
        "error.resilience.circuit_open": "Circuit breaker open: {service} (retry after {retry_after}s)",
        "error.resilience.pool_exhausted": "Connection pool exhausted: {pool}",
        "error.infrastructure.connection": "Infrastructure connection failed: {detail}",
        "error.dependency.missing": "Optional dependency {package} unavailable ({feature} required)",
        "error.config.invalid_threshold": "Invalid similarity threshold {value}, valid range: {valid_range}",
        "error.config.unsupported_language": "Unsupported language: {language}",
        "error.fingerprint.tokenization": "Tokenization failed (language={language}): {reason}",
        "error.fingerprint.winnowing": "Winnowing computation failed: {reason}",
        "error.similarity.empty_fingerprint": "Module {module_id} has empty fingerprints, cannot compute similarity",
        "error.storage.database": "Database operation failed: {reason}",
        "error.storage.cache": "Cache operation failed: {reason}",
        "error.project.fetch": "Project fetch failed ({source}): {reason}",
        "error.project.module_extraction": "Module extraction failed ({file_path}): {reason}",
        "error.api.rate_limit": "API rate limited, retry after {retry_after:.0f}s",
        "error.api.auth": "Authentication failed",
        "error.api.not_found": "Resource not found: {resource}",
        "error.api.circuit_open": "Circuit breaker open ({service}), retry after {recovery_timeout:.0f}s",
        "error.infra.pool": "Connection pool error: {reason}",
        "error.infra.resilience": "Resilience component error ({component}): {reason}",
        "error.infra.ssrf": "SSRF protection blocked: {reason}",
        "cli.detect.no_target": "No target project specified, use -t or --target",
        "cli.detect.no_candidates": "No candidate projects specified, use -c or --candidates",
        "cli.detect.invalid_language": "Unsupported language: {language}, supported: {supported}",
        "cli.detect.invalid_threshold": "Invalid threshold {value}, valid range: 0-100",
        "cli.detect.starting": "Starting detection {target} vs {candidates}...",
        "cli.detect.completed": "Detection complete: {count} matches (elapsed {elapsed:.1f}s)",
        "cli.detect.no_matches": "No similar modules found (threshold: {threshold}%)",
        "cli.plagiarism.no_db": "Fingerprint DB not found: {path}, run gh-sim db add first",
        "cli.plagiarism.tracing": "Tracing clone sources: {project}...",
        "cli.plagiarism.found": "Found {count} plagiarism suspects (confidence: {confidence}%)",
        "cli.ncd.computing": "Computing NCD compression distance...",
        "cli.ncd.result": "NCD similarity: {similarity:.2%}",
        "cli.db.adding": "Adding project to fingerprint DB: {project}...",
        "cli.db.added": "Added {modules} modules ({fingerprints} fingerprints)",
        "cli.db.removing": "Removing project: {project_id}...",
        "cli.db.stats": "Fingerprint DB: {projects} projects, {modules} modules, {fingerprints} fingerprints",
        "cli.search.searching": "Searching GitHub: {query}...",
        "cli.search.results": "Found {count} repositories",
        "cli.config.show": "Current configuration:",
        "cli.config.saved": "Configuration saved: {path}",
        "cli.config.reloaded": "Configuration reloaded",
        "cli.export.no_results": "No detection results to export",
        "cli.export.exported": "Results exported: {path} ({format})",
        "cli.init.welcome": "Welcome to ModuleMirror! Let's set up your first detection",
        "cli.init.step": "Step {step}/3: {description}",
        "cli.init.complete": "Setup complete! Run gh-sim detect to start",
        "report.generating": "Generating report: {format}...",
        "report.generated": "Report generated: {path}",
        "report.pdf.failed": "PDF generation failed: {reason}",
        "report.sarif.failed": "SARIF generation failed: {reason}",
        "report.html.failed": "HTML generation failed: {reason}",
        "report.csv.exported": "CSV exported: {path} ({rows} rows)",
        "cluster.computing": "Computing cluster analysis ({algorithm})...",
        "cluster.completed": "Clustering done: {n_clusters} clusters, silhouette: {silhouette:.3f}",
        "cluster.no_data": "Cluster analysis requires at least 2 detection results",
        "frequency.analyzing": "Analyzing match frequency...",
        "frequency.rare_matches": "Rare matches: {count} (weighting: {weighting})",
        "frequency.strategy": "Frequency strategy: {strategy}",
        "crosslang.detecting": "Cross-language detection: {source_lang} -> {target_lang}...",
        "crosslang.ir_channel": "IR channel similarity: {score:.2%}",
        "crosslang.embedding_channel": "Embedding channel similarity: {score:.2%}",
        "crosslang.fused": "Fused similarity: {score:.2%} (IR={ir_weight}, Emb={emb_weight})",
        "lineage.tracing": "Tracing clone lineage: {module_id}...",
        "lineage.depth": "Lineage depth: {depth}, branches: {branches}",
        "lineage.root": "Clone root: {project} ({timestamp})",
        "quality.evaluating": "Evaluating quality gate ({gate_type})...",
        "quality.passed": "Quality gate passed ({score}/{max_score})",
        "quality.failed": "Quality gate failed ({score}/{max_score}, minimum: {threshold})",
        "sbp.analyzing": "SBP analysis: detecting similar but patched code...",
        "sbp.cve_match": "CVE pattern match: {cve_id} (severity: {severity})",
        "sbp.security_patch": "Security patch detection: {count} matches",
        "sbp.fingerprint_diff": "Fingerprint diff: {added} added, {removed} removed",
        "task.created": "Async task created: {task_id}",
        "task.running": "Task running: {progress:.0%} ({step})",
        "task.completed": "Task completed: {task_id}",
        "task.failed": "Task failed: {task_id} ({reason})",
        "task.cancelled": "Task cancelled: {task_id}",
        "webhook.received": "Webhook event: {event_type}",
        "webhook.triggered": "Detection triggered: {repo}/{branch}",
        "webhook.invalid_signature": "Webhook signature verification failed",
        "plugin.loaded": "Plugin loaded: {name} v{version}",
        "plugin.not_found": "Plugin not found: {name}",
        "plugin.error": "Plugin execution error ({name}): {reason}",
    },
}


class I18n:
    _instance: Optional["I18n"] = None
    _lock = threading.Lock()

    def __init__(self, locale: str = _DEFAULT_LOCALE):
        self._locale = locale
        self._messages: Dict[str, Dict[str, str]] = {}
        for lang, msgs in _MESSAGES.items():
            self._messages[lang] = dict(msgs)

    @classmethod
    def get_instance(cls) -> "I18n":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        with cls._lock:
            cls._instance = None

    @property
    def locale(self) -> str:
        return self._locale

    @locale.setter
    def locale(self, value: str) -> None:
        if value not in _SUPPORTED_LOCALES:
            raise ValueError(f"Unsupported locale: {value}. Supported: {_SUPPORTED_LOCALES}")
        self._locale = value

    @property
    def supported_locales(self) -> set[str]:
        return set(_SUPPORTED_LOCALES)

    def translate(self, key: str, **kwargs: Any) -> str:
        msg = self._lookup(key)
        if kwargs:
            try:
                return msg.format(**kwargs)
            except KeyError:
                return msg
        return msg

    def register_messages(self, locale: str, messages: Dict[str, str]) -> None:
        if locale not in self._messages:
            self._messages[locale] = {}
        self._messages[locale].update(messages)

    def _lookup(self, key: str) -> str:
        if self._locale in self._messages:
            msg = self._messages[self._locale].get(key)
            if msg is not None:
                return msg
        if _DEFAULT_LOCALE in self._messages:
            msg = self._messages[_DEFAULT_LOCALE].get(key)
            if msg is not None:
                return msg
        return key

    def get_all_keys(self, locale: Optional[str] = None) -> set[str]:
        lang = locale or self._locale
        if lang in self._messages:
            return set(self._messages[lang].keys())
        return set()

    def has_key(self, key: str, locale: Optional[str] = None) -> bool:
        lang = locale or self._locale
        return lang in self._messages and key in self._messages[lang]


def set_locale(locale: str) -> None:
    I18n.get_instance().locale = locale


def get_locale() -> str:
    return I18n.get_instance().locale


def t(key: str, **kwargs: Any) -> str:
    return I18n.get_instance().translate(key, **kwargs)


def register_messages(locale: str, messages: Dict[str, str]) -> None:
    I18n.get_instance().register_messages(locale, messages)
