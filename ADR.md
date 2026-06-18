# 架构决策记录 (ADR)

本目录记录 ModuleMirror 项目的关键技术决策。每条 ADR 包含：上下文、决策、后果。

## ADR 索引

| 编号 | 标题 | 状态 | 日期 |
|------|------|------|------|
| ADR-001 | 选择 Winnowing 作为核心指纹算法 | 已接受 | 2024-01 |
| ADR-002 | 使用 SQLite 作为指纹存储引擎 | 已接受 | 2024-01 |
| ADR-003 | tree-sitter 多语言 AST 解析 | 已接受 | 2024-02 |
| ADR-004 | FastAPI + Click 双接口(API+CLI) | 已接受 | 2024-02 |
| ADR-005 | Jaccard 相似度 + 倒排索引加速 | 已接受 | 2024-02 |
| ADR-006 | 连接池替代逐次创建SQLite连接 | 已接受 | 2026-05 |
| ADR-007 | API路由拆分为routes/子模块 | 已接受 | 2026-05 |
| ADR-008 | Circuit Breaker保护GitHub API | 已接受 | 2026-05 |
| ADR-009 | Token连续性(k-gram)精确度优化 | 已接受 | 2026-05 |
| ADR-010 | LRU缓存驱逐策略(OrderedDict) | 已接受 | 2026-05 |
| ADR-011 | Fallback模式: CircuitBreaker联动本地缓存兜底 | 已接受 | 2026-05 |
| ADR-012 | 幂等性保障: 确定性哈希+IdempotencyGuard | 已接受 | 2026-05 |
| ADR-013 | tracemalloc内存画像: 运行时泄露检测 | 已接受 | 2026-05 |
| ADR-014 | GracefulShutdown: 请求排空+关闭钩子+超时保护 | 已接受 | 2026-05 |
| ADR-015 | Dependabot自动化依赖更新(pip+actions) | 已接受 | 2026-05 |
| ADR-016 | FingerprintDB拆分: schema/migrations/queries | 已接受 | 2026-05 |
| ADR-017 | ResourceTracker: atexit+连接池资源泄露审计 | 已接受 | 2026-05 |
| ADR-018 | AlertManager: Prometheus指标驱动告警规则 | 已接受 | 2026-05 |
| ADR-019 | APIInventory: OWASP API9端点生命周期管理 | 已接受 | 2026-05 |
| ADR-020 | ThirdPartyAPIValidator: OWASP API10响应验证 | 已接受 | 2026-05 |
| ADR-021 | MultiRepositoryComparator: 一对多/多对多/矩阵对比 | 已接受 | 2026-05 |
| ADR-022 | BatchDetector: txt/csv/json批量任务加载 | 已接受 | 2026-05 |
| ADR-023 | 确定性多项式哈希替代Python hash() | 已接受 | 2026-05 |
| ADR-024 | OpenAPI Tags增强: Swagger UI分组+Try-it-out | 已接受 | 2026-05 |
| ADR-025 | StreamReader: 大文件流式处理(逐行/分块/智能) | 已接受 | 2026-05 |
| ADR-026 | AdaptiveRateLimiter: GitHub响应头驱动速率调整 | 已接受 | 2026-05 |
