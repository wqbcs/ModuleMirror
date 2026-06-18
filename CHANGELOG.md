# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-05-27

### Added - 第18-19轮迭代
- 指纹计算并行化（ThreadPoolExecutor batch processing）
- DetectionPipeline 迁移到 orchestration/pipeline.py
- API 路由拆分到 routes/ 5个子模块
- SQLite 连接池（Queue-based _ConnectionPool）
- LRU 缓存层（OrderedDict + max_entries=1024）
- Circuit Breaker 弹性模式（CLOSED/OPEN/HALF_OPEN三状态）
- 请求追踪ID透传（X-Request-ID中间件）
- 检测历史趋势（detection_history表 + /history API路由）
- Token串匹配精确度（k-gram连续性 + 三维度组合）
- 全局错误处理（领域异常体系 exceptions.py + 17子类）
- 依赖漏洞扫描（pip-audit集成到CI）
- 覆盖率门禁提升 60%→80%（当前83%）
- 数据校验层（Pydantic v2 全覆盖 + 运行时契约检查）
- 输入消毒全覆盖（路径遍历 + 命令注入 + ReDoS防护）
- SSRF防护（GitHub URL白名单 + 私有IP过滤 + DNS重绑定防护）
- 结构化日志增强（correlation_id + 模块级日志 + threading.local隔离）
- Retry策略增强（tenacity集成: github_api/db_query/file_read/network/custom）
- Prometheus metrics导出（检测耗时/指纹命中率/DB查询/API请求 + /metrics端点）
- 倒排索引增量更新（add_module/remove_module/update_module）
- OWASP API1对象级授权（ProjectAuthorization + Permission分级）
- Property-based testing（Hypothesis 24属性测试）

### Security
- SSRF防护（URL白名单 + 私有IP过滤）
- 输入消毒（路径遍历/命令注入/ReDoS）
- 对象级授权检查（read/write/admin三级）
- 依赖漏洞扫描（pip-audit）

### Changed
- RollingHash 替换为确定性多项式哈希（跨会话一致性）
- Jaccard 空集数学正确性（Jaccard(∅,∅)=100%）
- MIN_OVERLAP_THRESHOLD 从2改为1

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
