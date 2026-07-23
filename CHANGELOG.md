# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2026-07-23

### Added — Rust 核心扩展（6 Phase）

- PyO3 Winnowing/RollingHash 加速 5.7x
- Rust MinHash 引擎 + LSH 索引集成（基于 gaoya crate）10-50x 加速
- Rust SIMD 批处理 + 倒排索引（双指针 Jaccard）5-20x 加速
- Rust Code2Vec 嵌入 + simsimd 向量运算（cosine/euclidean）10-30x 加速
- Rust Diff 引擎 + AST 比对（similar crate）5-15x 加速
- Rust 分词器 + 全链路零拷贝（CodeTokenizer）3-10x 加速

### Added — 产品化功能

- 交互式 Web 仪表盘（Linear Aesthetic + Mermaid 图表）
- WebSocket 实时进度推送 + 自动重连 + SSE 回退
- SARIF 2.1.0 标准导出
- 异步任务队列（TaskQueue + 进度追踪）
- GitHub Webhook 集成（push/PR 事件自动触发检测）
- JWT 认证 + API Key 管理（AuthManager/TokenBlacklist/APIKeyStore/UserRole）
- PDF 报告导出（fpdf2 专业级报告 + 相似度热力条 + 代码差异视图）
- 配置热重载（YAML 文件监听/回调通知/手动触发 API）
- Docker 一键部署 + CI/Release 流水线

### Added — 高级分析引擎

- 跨语言检测管道（IR 结构指纹 + Embedding 向量双通道融合）
- 多视图融合自适应权重引擎（AdaptiveFusionEngine + EMA 平滑）
- 行为特征提取（BehaviorExtractor: API/IO/异常/并发 4 维融合）
- 克隆血统追踪（trace_lineage + 传播树 + 血缘 API）
- 规则引擎（YAML DSL 自定义规则 + CRUD + 评估）
- SBP 过滤器（安全衍生识别 + CVE/安全模式/指纹差集三重检测）
- 语义差异引擎（SemanticDiffer 实体级变更分析）
- MinHash 参数调优（tune_minhash + 6 API 端点）
- 高级分析（DataFrame/批量检测/多仓库对比/结果对比）
- 质量门禁（evaluate_quality 默认/严格/自定义门禁 + CI 评估）

### Added — 可观测性与安全

- API /v1 版本化
- 可观测性三支柱（Prometheus metrics + structlog JSON + OpenTelemetry 接线）
- 健康检查增强（bulkhead 状态 + /circuit-breakers 端点）
- 安全中间件增强（IP 过滤/细粒度 CORS/请求体限制/CSP）
- 数据库迁移管理增强（v3 迁移/回滚/锁/状态 API）
- OpenAPI 文档全面增强

### Added — CLI 体验

- CLI 交互式 TUI 模式（Trogon 自动 TUI + Textual 专业级仪表盘）
- CLI 职责分离（main.py 616 行拆分为 4 模块）
- CLI 帮助文本 i18n 统一（中文帮助 + 常用命令示例）
- Git 增量检测增强（mmh3 确定性哈希 + GitDeltaDetector）

### Added — 插件化与算法

- 插件化算法架构（AlgorithmPlugin ABC + 算法注册表）
- SimHash 算法实现
- 算法插件接入核心 SimilarityCalculator

### Changed

- 确定性哈希修复（替换 Python hash() 为 mmh3）
- MinHash update_batch 优化（逐元素 update → 批量 update_batch）
- SQL 参数化模板抽取（20 条 SQL 内联 → 30 个模块级常量）
- 异常消息 i18n 改造（硬编码字符串 → i18n 键）
- mypy strict mode 全量修复（440→0 errors, 142 源文件全部通过）
- structlog 真正接管日志输出（info/warning/error/debug/exception 走 structlog 管道）

### Fixed

- 宽泛异常捕获消除（8 文件 except Exception → 具体异常类型）
- 空_pass_语句消除（tui_app/task_queue/migrations → ...或 debug 日志）
- 硬编码配置化（CLI version_option 改用 __version__ 动态读取）
- LICENSE 统一 Apache-2.0
- README 版本号 1.0.0 → 2.0.0
- dev-secret 安全警告（warnings.warn）
- Rust 后端死代码集成（batch_stable_hash/l2_normalize/batch_cosine_similarity 接入实际管道）
- API 全局异常处理器（ModuleMirrorError + 通用异常统一错误响应格式）
- CI 流水线全挂问题修复
- ruff format 和 pytest 命令格式修复

### Security

- JWT 认证 + Token 黑名单
- API Key 管理与权限分级
- IP 过滤 + 细粒度 CORS
- 请求体大小限制
- Content-Security-Policy 头
- dev-secret 启动警告

## [1.1.0] - 2026-06-15

### Added — v1.1 细致打磨

- 可选依赖统一管理（DependencyRegistry: 7 模块 try-except ImportError → 注册表）
- numpy 向量化 cosine_similarity + batch（math_utils 性能优化）
- mypy/pre-commit 配置增强（polars/fpdf 忽略 + check-toml 钩子）
- structlog 集成（桥接方案保持接口不变）
- i18n 子系统扩展（zh/en 双语言，89 个消息键）
- 可观测性增强（健康检查 + bulkhead 状态）
- CLI 补全与硬编码配置化

### Fixed

- 确定性哈希修复（Python hash() → mmh3）
- 宽泛异常捕获消除
- 空_pass_语句消除
- ruff lint 错误修复

## [1.0.0] - 2026-05-27

### Added

- Winnowing 指纹算法 + AST 结构指纹双重检测
- tree-sitter 多语言解析（Python/JS/Java/TS/Go/Rust/C/C++）
- Jaccard 相似度 + 倒排索引加速
- 抄袭溯源检测（PlagiarismDetector + 置信度评分）
- SQLite 指纹库（批量写入 + 缓存 + 异步任务管理）
- FastAPI Web API（认证 + 安全头 + CORS）
- Click CLI（detect/plagiarism/db/config/diff/search/ncd）
- 交互式 HTML 报告（搜索/过滤/排序/柱状图/代码差异对比）
- 断点续传（Checkpoint JSON）
- 并发检测（ThreadPoolExecutor）
- SHA256 内容哈希缓存（原子写入）
- NCD 归一化压缩距离（50MB 内存限制）
- GitHub API 客户端（连接池复用 + API 优先/clone 回退）
- CI 流水线（ruff + pytest + bandit + 覆盖率门禁）
- 性能基线测试（benchmark.py）

### Security

- API Key 认证中间件
- HTTP 安全头
- CORS 白名单
- 路径遍历防护
- 确定性多项式哈希（替代 Python hash() 随机化）
- 大文件限制（MAX_FILE_SIZE=1MB）
- NCD 内存限制（MAX_TOTAL_BYTES=50MB）

## [0.2.0] - 2026-05-27

### Added

- 指纹计算并行化（ThreadPoolExecutor batch processing）
- DetectionPipeline 迁移到 orchestration/pipeline.py
- API 路由拆分到 routes/ 5 个子模块
- SQLite 连接池（Queue-based _ConnectionPool）
- LRU 缓存层（OrderedDict + max_entries=1024）
- Circuit Breaker 弹性模式（CLOSED/OPEN/HALF_OPEN 三状态）
- 请求追踪 ID 透传（X-Request-ID 中间件）
- 检测历史趋势（detection_history 表 + /history API 路由）
- Token 串匹配精确度（k-gram 连续性 + 三维度组合）
- 全局错误处理（领域异常体系 exceptions.py + 17 子类）
- 依赖漏洞扫描（pip-audit 集成到 CI）
- 覆盖率门禁提升 60%→80%（当前 83%）
- 数据校验层（Pydantic v2 全覆盖 + 运行时契约检查）
- 输入消毒全覆盖（路径遍历 + 命令注入 + ReDoS 防护）
- SSRF 防护（GitHub URL 白名单 + 私有 IP 过滤 + DNS 重绑定防护）
- 结构化日志增强（correlation_id + 模块级日志 + threading.local 隔离）
- Retry 策略增强（tenacity 集成: github_api/db_query/file_read/network/custom）
- Prometheus metrics 导出（检测耗时/指纹命中率/DB 查询/API 请求 + /metrics 端点）
- 倒排索引增量更新（add_module/remove_module/update_module）
- OWASP API1 对象级授权（ProjectAuthorization + Permission 分级）
- Property-based testing（Hypothesis 24 属性测试）

### Security

- SSRF 防护（URL 白名单 + 私有 IP 过滤）
- 输入消毒（路径遍历/命令注入/ReDoS）
- 对象级授权检查（read/write/admin 三级）
- 依赖漏洞扫描（pip-audit）

### Changed

- RollingHash 替换为确定性多项式哈希（跨会话一致性）
- Jaccard 空集数学正确性（Jaccard(∅,∅)=100%）
- MIN_OVERLAP_THRESHOLD 从 2 改为 1

## [0.1.0] - 2026-05-27

### Added

- Winnowing 指纹算法 + AST 结构指纹双重检测
- tree-sitter 多语言解析（Python/JS/Java/TS/Go/Rust/C/C++）
- Jaccard 相似度 + 倒排索引加速
- 抄袭溯源检测（PlagiarismDetector + 置信度评分）
- SQLite 指纹库（批量写入 + 缓存 + 异步任务管理）
- FastAPI Web API（认证 + 安全头 + CORS）
- Click CLI（detect/plagiarism/db/config/diff/search/ncd）
- 交互式 HTML 报告（搜索/过滤/排序/柱状图/代码差异对比）
- 断点续传（Checkpoint JSON）
- 并发检测（ThreadPoolExecutor）
- SHA256 内容哈希缓存（原子写入）
- NCD 归一化压缩距离（50MB 内存限制）
- GitHub API 客户端（连接池复用 + API 优先/clone 回退）
- CI 流水线（ruff + pytest + bandit + 覆盖率门禁）
- 性能基线测试（benchmark.py）

### Security

- API Key 认证中间件
- HTTP 安全头（X-Content-Type-Options/X-Frame-Options/X-XSS-Protection/Cache-Control/Referrer-Policy）
- CORS 白名单
- 路径遍历防护
- 确定性多项式哈希（替代 Python hash() 随机化）
- 大文件限制（MAX_FILE_SIZE=1MB）
- NCD 内存限制（MAX_TOTAL_BYTES=50MB）
