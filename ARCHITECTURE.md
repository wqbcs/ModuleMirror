# ModuleMirror 架构设计

## 系统总览

ModuleMirror 采用**六边形架构（Hexagonal Architecture）**，核心业务逻辑与基础设施严格分离。

```
┌─────────────────────────────────────────────────────┐
│                    适配器层（Adapters）               │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │
│  │   CLI    │  │  Web API │  │   GitHub Client  │   │
│  │ (Click)  │  │ (FastAPI)│  │   (httpx)        │   │
│  └────┬─────┘  └────┬─────┘  └───────┬──────────┘   │
│       │              │                │              │
├───────┼──────────────┼────────────────┼──────────────┤
│       │        应用层（Application）   │              │
│       ▼              ▼                ▼              │
│  ┌─────────────────────────────────────────────┐    │
│  │          DetectionPipeline（编排器）          │    │
│  │  detect() · plagiarism() · add_to_db()      │    │
│  └────────────────────┬────────────────────────┘    │
│                       │                             │
├───────────────────────┼─────────────────────────────┤
│                       │    领域层（Domain）          │
│       ┌───────────────┼───────────────┐             │
│       │               ▼               │             │
│       │  ┌─────────────────────┐      │             │
│       │  │  FingerprintEngine  │      │             │
│       │  │  Winnowing + AST    │      │             │
│       │  └─────────┬───────────┘      │             │
│       │            │                  │             │
│       │  ┌─────────▼───────────┐      │             │
│       │  │  SimilarityEngine   │      │             │
│       │  │  Jaccard + Inverted │      │             │
│       │  │  Index + AST Verify │      │             │
│       │  └─────────┬───────────┘      │             │
│       │            │                  │             │
│       │  ┌─────────▼───────────┐      │             │
│       │  │  PlagiarismDetector │      │             │
│       │  └─────────────────────┘      │             │
│       └───────────────────────────────┘             │
│                                                     │
├─────────────────────────────────────────────────────┤
│                 基础设施层（Infrastructure）          │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │ FingerprintDB │ FingerprintCache │ NCD/jscpd │  │
│  │ (SQLite)      │ (SHA256+原子写) │ (zlib)    │  │
│  └──────────┘  └──────────┘  └──────────────────┘  │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │ Checkpoint    │ GitHub Client   │ Git Client │  │
│  │ (JSON断点)   │ (连接池复用)    │ (浅克隆)   │  │
│  └──────────┘  └──────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────┘
```

## 核心流程

### 自我审视检测（detect）

```
目标项目 ──→ ProjectFetcher ──→ ModuleExtractor ──→ FingerprintGenerator
                                                      │
候选项目 ──→ ProjectFetcher ──→ ModuleExtractor ──→ FingerprintGenerator
                                                      │
                                    SimilarityCalculator ◄──┘
                                          │
                                    ReportGenerator
                                          │
                                    HTML/JSON/Markdown 报告
```

### 抄袭溯源检测（plagiarism）

```
目标项目 ──→ FingerprintGenerator ──→ PlagiarismDetector
                                            │
                            FingerprintDB ◄──┘
                            (倒排索引候选 → AST 验证 → 置信度评分)
```

## 数据流

### 指纹生成流水线

```
源代码 → CodeTokenizer.tokenize() → token 流
    → Winnowing.generate_fingerprints() → 指纹集合
    → ASTParser → AST 结构指纹
    → FingerprintGenerator → ModuleFingerprint{winnowing, ast}
```

### 相似度计算流水线

```
目标指纹集 × 候选指纹集
    → InvertedIndex.build() (倒排索引)
    → InvertedIndex.get_candidates() (候选筛选, MIN_OVERLAP≥1)
    → Jaccard 相似度 (Winnowing权重0.6 + AST权重0.4)
    → ASTComparator.verify() (高相似度结果深度验证, >60%)
    → SimilarityMatch{similarity, reuse_suggestion}
```

## 关键设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 指纹算法 | Winnowing + AST 双重指纹 | Winnowing 快速筛选，AST 消除哈希碰撞 |
| 相似度度量 | Jaccard + 倒排索引 | 倒排索引避免 O(n²) 全量比对 |
| AST 验证阈值 | 60% 触发深度验证 | 平衡精度与性能 |
| 存储引擎 | SQLite | 嵌入式零部署，满足单机场景 |
| 项目获取 | API 优先 + clone 回退 | 减少网络开销，大项目回退克隆 |
| 并发模型 | ThreadPoolExecutor | IO 密集型任务，线程池足够 |
| 缓存策略 | SHA256 内容哈希 | 文件级缓存，避免重复指纹计算 |
| 哈希函数 | 确定性多项式哈希 | 避免 Python hash() 随机化问题 |

## 安全架构

```
请求 → API Key 认证中间件
     → CORS 白名单检查
     → 路径遍历防护 (_safe_report_path)
     → HTTP 安全头 (X-Content-Type-Options, X-Frame-Options, ...)
     → 业务处理
     → 脱敏输出 (报告中移除 token)
```

## 可扩展性设计

- **语言扩展**：新增 tree-sitter 语言包即可支持新语言
- **存储扩展**：FingerprintDB 抽象接口，可替换为 PostgreSQL
- **算法扩展**：SimilarityCalculator 支持多算法组合（SimHash/MinHash LSH 待实现）
- **输出扩展**：ReportGenerator 基于 Jinja2 模板，可自定义报告格式
- **获取扩展**：ProjectFetcher 可扩展 GitLab/Bitbucket 适配器

## 成熟度路线图

| 级别 | 标准 | 当前 |
|------|------|------|
| L1 可用 | 核心功能完整 | ✅ |
| L2 可靠 | CI 门禁 + 80% 覆盖率 | 🔄 60%→80% |
| L3 可扩展 | 插件化 + API 版本化 | ⬜ |
| L4 可观测 | 指标/日志/追踪三支柱 | 🔄 部分有 |
| L5 可贡献 | 完善文档 + 社区规范 | ⬜ |
