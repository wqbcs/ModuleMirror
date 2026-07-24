# ModuleMirror

[![version](https://img.shields.io/badge/version-2.0.0-blue.svg)](https://github.com/wqbcs/ModuleMirror/releases/tag/v2.0.0)
[![license](https://img.shields.io/badge/license-Apache--2.0-green.svg)](LICENSE)
[![python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![tests](https://img.shields.io/badge/tests-1924%20passed-brightgreen.svg)](tests/)
[![ruff](https://img.shields.io/badge/ruff-0%20errors-brightgreen.svg)](https://docs.astral.sh/ruff/)

GitHub 项目代码相似度检测工具，支持两大核心用途：

- **自我审视**：检测自己项目与其他项目的相似模块，发现可复用代码
- **抄袭溯源**：检测目标项目是否复制了其他项目的代码，追溯来源

## 核心特性

| 特性 | 说明 |
|------|------|
| Winnowing 指纹 | 快速代码指纹提取，O(n) 时间复杂度 |
| AST 结构指纹 | tree-sitter 多语言解析，节点级比对 |
| MinHash LSH | 大规模近似匹配，datasketch 驱动 |
| Rust 核心加速 | PyO3 六大模块加速 5-50x（Winnowing/MinHash/SIMD/Code2Vec/Diff/Tokenizer） |
| 跨语言检测 | IR 结构指纹 + Embedding 向量双通道融合 |
| 抄袭溯源 | 反向查找 + 时间线分析 + 置信度评分 |
| 克隆血统追踪 | 传播树 + 血缘关系图谱 |
| YAML 规则引擎 | 自定义检测规则（类 ESLint） |
| SBP 过滤器 | 安全衍生识别 + CVE/安全模式/指纹差集三重检测 |
| 行为特征提取 | API/IO/异常/并发 4 维融合权重 |
| 多视图融合 | 自适应权重引擎（EMA 平滑 + 区分度动态调整） |
| 语义差异 | 实体级变更分析（新增/删除/修改/重命名） |
| SQLite 持久化 | 指纹库增量更新 + 相似度缓存 |
| JWT 认证 | Token 黑名单 + API Key 管理 + 角色权限 |
| 交互式 TUI | Trogon 自动 TUI + Textual 专业级仪表盘 |
| 实时推送 | WebSocket + SSE 双协议进度推送 |
| PDF 报告 | fpdf2 专业级报告 + 相似度热力条 |
| SARIF 2.1.0 | 标准化安全报告导出 |
| Prometheus | 指标导出 + 断路器状态监控 |
| 配置热重载 | YAML 文件监听 + 回调通知 |
| Docker 支持 | 一键容器化部署 |

## 快速开始

### 安装

```bash
pip install -e .

# 带全部功能
pip install -e ".[all]"

# 仅 API 服务
pip install -e ".[api]"

# 仅可视化
pip install -e ".[visualization-enhanced]"
```

### 自我审视检测

```bash
gh-sim detect -t ./my-project -c https://github.com/other/project -l python --threshold 70
```

### 抄袭溯源检测

```bash
gh-sim plagiarism -t ./suspect-project --db ./fingerprint_db.sqlite
```

### Web API

```bash
uvicorn gh_similarity_detector.api.app:app --host 0.0.0.0 --port 8000
```

### Docker

```bash
docker build -t modulemirror:latest .
docker run -d -p 8000:8000 -e GITHUB_TOKEN=ghp_xxx modulemirror:latest
```

## CLI 命令

| 命令 | 说明 |
|------|------|
| `gh-sim init` | 交互式配置向导（3步完成首次检测配置） |
| `gh-sim detect` | 自我审视检测 |
| `gh-sim plagiarism` | 抄袭溯源检测 |
| `gh-sim ncd` | NCD 整体相似度 |
| `gh-sim diff` | 代码差异对比 |
| `gh-sim search` | 搜索 GitHub 仓库 |
| `gh-sim db` | 指纹库管理 |
| `gh-sim config` | 配置管理 |
| `gh-sim export` | 导出检测结果（CSV/JSON） |
| `gh-sim dashboard` | 交互式 Web 仪表盘 |
| `gh-sim tui` | 终端 TUI 模式 |

## API 端点

### 检测

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/detect` | 执行自我审视检测 |
| POST | `/plagiarism` | 执行抄袭溯源检测 |
| POST | `/ncd` | 计算 NCD 压缩距离相似度 |
| POST | `/quality-gate` | 评估检测结果质量门禁 |
| POST | `/sbp-analyze` | SBP 分析: 识别相似但已修补的代码 |

### 指纹库

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/db/stats` | 指纹库统计信息 |
| GET | `/db/projects` | 列出所有项目 |
| POST | `/db/add` | 添加项目到指纹库 |
| DELETE | `/db/projects/{project_id}` | 删除项目 |

### 异步任务

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/tasks` | 创建异步检测任务 |
| GET | `/tasks` | 列出所有任务 |
| GET | `/tasks/{task_id}` | 获取任务详情 |
| DELETE | `/tasks/{task_id}` | 删除任务 |
| GET | `/tasks/{task_id}/stream` | SSE 推送任务进度 |

### 报告

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/reports` | 列出所有检测报告 |
| GET | `/reports/{report_id}` | 获取报告内容 |
| GET | `/reports/{report_id}/summary` | 获取报告摘要 |
| GET | `/reports/visual/latest` | 获取最新可视化报告 |

### 认证

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/auth/login` | API Key 换取 JWT Token |
| POST | `/auth/refresh` | 刷新 JWT Token |
| POST | `/auth/revoke` | 吊销 Token 或 API Key |
| POST | `/auth/api-keys` | 创建 API Key（管理员） |
| GET | `/auth/api-keys` | 列出所有 API Key |
| DELETE | `/auth/api-keys/{key_id}` | 吊销 API Key（管理员） |
| GET | `/auth/me` | 获取当前认证用户信息 |

### 高级分析

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/analysis/dataframe` | Polars DataFrame 高级分析 |
| POST | `/analysis/batch/load` | 从文件加载批量任务列表 |
| POST | `/analysis/batch/execute` | 执行批量检测 |
| POST | `/analysis/multi-repo` | 多仓库对比检测 |
| POST | `/analysis/compare` | 对比两次检测结果差异 |
| POST | `/analysis/minhash-tune` | MinHash 参数调优 |
| POST | `/analysis/cluster` | 聚类分析（Agglomerative/Spectral） |
| POST | `/analysis/frequency` | 频率分析（稀有匹配加权） |
| POST | `/analysis/merge` | 匹配合并（反混淆） |

### 规则引擎

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/rules` | 列出所有规则 |
| POST | `/rules` | 添加规则 |
| DELETE | `/rules/{rule_id}` | 删除规则 |
| POST | `/rules/load-yaml` | 从 YAML 加载规则 |
| POST | `/rules/evaluate` | 评估规则匹配 |

### 语义差异

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/semantic-diff/analyze` | 语义级差异分析 |
| POST | `/semantic-diff/batch` | 批量语义差异分析 |

### 克隆血统

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/lineage/stats` | 血统追踪统计信息 |
| POST | `/lineage/trace` | 追踪克隆传播路径 |

### 算法插件

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/algorithms` | 列出所有算法插件 |
| GET | `/algorithms/{name}` | 获取算法元信息 |
| POST | `/algorithms/{name}/similarity` | 用指定算法计算相似度 |

### Webhook

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/webhook/github` | 接收 GitHub Webhook 事件 |
| GET | `/webhook/github/config` | 获取 Webhook 配置 |

### 检测历史

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/history` | 列出检测历史记录 |
| GET | `/history/trend/{target_project}` | 获取项目检测趋势 |

### 系统运维

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查（含 DB/GitHub/磁盘/断路器状态） |
| GET | `/circuit-breakers` | 断路器和隔离仓状态 |
| GET | `/metrics` | Prometheus 指标端点 |
| GET | `/migrations` | 数据库迁移状态 |
| GET | `/config/reload` | 配置热重载状态 |
| POST | `/config/reload` | 手动触发配置热重载 |
| POST | `/search` | 搜索 GitHub 仓库 |

### 仪表盘

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/dashboard` | 交互式 Web 仪表盘（HTML） |

### WebSocket

| 协议 | 路径 | 说明 |
|------|------|------|
| WS | `/ws/dashboard` | 仪表盘全局事件流 |
| WS | `/ws/tasks/{task_id}/progress` | 任务进度实时推送 |

### 版本化

所有端点均可通过 `/v1` 前缀访问（如 `/v1/detect`、`/v1/auth/login`）。

## 支持语言

Python | JavaScript | TypeScript | Java | Go | Rust | C | C++

## 配置

| 环境变量 | 必填 | 说明 |
|----------|------|------|
| `GITHUB_TOKEN` | 否 | GitHub API Token（提升速率限制至 5000/h） |
| `MODULEMIRROR_API_KEY` | 否 | API 认证密钥（设置后强制认证） |
| `MODULEMIRROR_CORS_ORIGINS` | 否 | CORS 允许域名（逗号分隔） |
| `MODULEMIRROR_DB_PATH` | 否 | 指纹库路径（默认 `./fingerprint_db.sqlite`） |
| `MODULEMIRROR_JWT_SECRET` | 否 | JWT 签名密钥（生产环境必须设置） |

## Rust 加速性能

| 模块 | 基准 | 加速比 |
|------|------|--------|
| Winnowing 指纹 | 单文件生成 | 5.7x |
| MinHash 签名 | 批量 1000 条 | 10-50x |
| SIMD Jaccard | 双指针批量 | 5-20x |
| Code2Vec 嵌入 | cosine/euclidean | 10-30x |
| Diff 引擎 | AST 比对 | 5-15x |
| CodeTokenizer | tokenize | 3-10x |

## 项目结构

```
gh_similarity_detector/
├── core/                  # 核心算法
│   ├── fingerprint/       # Winnowing + AST 指纹 + 向量化Hash
│   ├── similarity/        # 相似度计算 + MinHash LSH + 多视图融合
│   ├── module/            # tree-sitter 模块提取
│   ├── project/           # 项目获取（API 优先 + clone 回退）
│   ├── plagiarism/        # 抄袭溯源（时间线 + 置信度）
│   ├── rules/             # YAML 规则引擎
│   ├── orchestration/     # 检测流水线 + 断点续传
│   └── report/            # 报告生成（HTML + PDF + SARIF）
├── infrastructure/        # 基础设施
│   ├── github_client/     # GitHub API（连接池 + 熔断器）
│   ├── git_client/        # Git 浅克隆
│   ├── storage/           # SQLite 指纹库 + 连接池
│   ├── cache/             # LRU 内容缓存
│   ├── resilience/        # 熔断器 + 降级 + 限流 + 特性开关
│   ├── observability/     # Metrics + SSE + WebSocket + 告警
│   ├── security/          # JWT + API Key + IP 过滤 + CORS
│   └── i18n/              # 国际化（zh/en 双语言）
├── api/                   # FastAPI REST API（47 端点 + v1 版本化）
│   └── routes/            # 14 路由模块
├── cli/                   # Click 命令行 + TUI
├── models/                # 数据模型
├── config/                # 配置管理 + 热重载
├── tools/                 # 性能分析 + 文档生成
└── utils/                 # Rust 后端 + orjson + 日志 + 审计 + 异常体系
src/_module_mirror_rust/   # Rust 核心加速（6 模块）
```

## 质量状态

- **1924 测试全通过** | ruff 0 错误
- CI 流水线：ruff + pytest + bandit + mypy + 覆盖率门禁

## 文档

| 文档 | 说明 |
|------|------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | 架构设计 |
| [ALGORITHM.md](ALGORITHM.md) | 算法文档 |
| [API_REFERENCE.md](API_REFERENCE.md) | API 参考 |
| [DEPLOYMENT.md](DEPLOYMENT.md) | 部署指南 |
| [TUTORIAL.md](TUTORIAL.md) | 快速上手 |
| [PERFORMANCE.md](PERFORMANCE.md) | 性能调优 |
| [CHANGELOG.md](CHANGELOG.md) | 变更日志 |
| [CONTRIBUTING.md](CONTRIBUTING.md) | 贡献指南 |
| [SECURITY.md](SECURITY.md) | 安全策略 |
| [ADR.md](ADR.md) | 架构决策记录 |

## License

Apache-2.0
