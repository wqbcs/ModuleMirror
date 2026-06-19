# ModuleMirror

[![version](https://img.shields.io/badge/version-1.0.0-blue.svg)](https://github.com/wqbcs/ModuleMirror/releases/tag/v1.0.0)
[![license](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![tests](https://img.shields.io/badge/tests-1538%20passed-brightgreen.svg)](tests/)
[![ruff](https://img.shields.io/badge/ruff-0%20errors-brightgreen.svg)](https://docs.astral.sh/ruff/)

GitHub 项目代码相似度检测工具，支持两大核心用途：

- **自我审视**：检测自己项目与其他项目的相似模块，发现可复用代码
- **抄袭溯源**：检测目标项目是否复制了其他项目的代码，追溯来源

## 核心特性

| 特性 | 说明 |
|------|------|
| ⚡ Winnowing 指纹 | 快速代码指纹提取，O(n) 时间复杂度 |
| 🌳 AST 结构指纹 | tree-sitter 多语言解析，节点级比对 |
| 📊 MinHash LSH | 大规模近似匹配，datasketch 驱动 |
| 🔍 抄袭溯源 | 反向查找 + 时间线分析 + 置信度评分 |
| 🗄️ SQLite 持久化 | 指纹库增量更新 + 相似度缓存 |
| 📐 YAML 规则引擎 | 自定义检测规则（类 ESLint） |
| 📈 交互式可视化 | pyecharts 热力图/关系图 + pyvis 网络图 |
| ⚙️ SSE 实时进度 | Server-Sent Events 推送检测进度 |
| 🚀 orjson 加速 | JSON 序列化 9x 性能提升 |
| 🐳 Docker 支持 | 一键容器化部署 |

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
| `gh-sim detect` | 自我审视检测 |
| `gh-sim plagiarism` | 抄袭溯源检测 |
| `gh-sim ncd` | NCD 整体相似度 |
| `gh-sim diff` | 代码差异对比 |
| `gh-sim search` | 搜索 GitHub 仓库 |
| `gh-sim db` | 指纹库管理 |
| `gh-sim config` | 配置管理 |
| `gh-sim dashboard` | 检测仪表盘 |

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/detect` | 执行检测 |
| POST | `/ncd` | 计算 NCD 相似度 |
| POST | `/search` | 搜索 GitHub 仓库 |
| GET | `/db/stats` | 指纹库统计 |
| POST | `/db/add` | 添加项目 |
| POST | `/tasks` | 创建异步检测任务 |
| GET | `/health` | 健康检查 |

## 支持语言

Python | JavaScript | TypeScript | Java | Go | Rust | C | C++

## 配置

| 环境变量 | 必填 | 说明 |
|----------|------|------|
| `GITHUB_TOKEN` | 否 | GitHub API Token（提升速率限制至 5000/h） |
| `MODULEMIRROR_API_KEY` | 否 | API 认证密钥（设置后强制认证） |
| `MODULEMIRROR_CORS_ORIGINS` | 否 | CORS 允许域名（逗号分隔） |
| `MODULEMIRROR_DB_PATH` | 否 | 指纹库路径（默认 `./fingerprint_db.sqlite`） |

## 性能基线

| 算法 | 规模 | 耗时 |
|------|------|------|
| CodeTokenizer.tokenize | 11KB 代码 | 2.85ms |
| Winnowing.generate_fingerprints | 100 函数 | 21.95ms |
| InvertedIndex.build | 500 模块 | 2.68ms |
| InvertedIndex.get_candidates | 30 指纹查询 | 0.01ms |
| orjson 序列化 | 大数据集 | **9x 加速** |

## 项目结构

```
gh_similarity_detector/
├── core/                  # 核心算法
│   ├── fingerprint/       # Winnowing + AST 指纹 + 向量化Hash
│   ├── similarity/        # 相似度计算 + MinHash LSH + polars批处理
│   ├── module/            # tree-sitter 模块提取
│   ├── project/           # 项目获取（API 优先 + clone 回退）
│   ├── plagiarism/        # 抄袭溯源（时间线 + 置信度）
│   ├── rules/             # YAML 规则引擎
│   ├── orchestration/     # 检测流水线 + 断点续传
│   └── report/            # 报告生成（Jinja2 + HTML + Markdown）
├── infrastructure/        # 基础设施
│   ├── github_client/     # GitHub API（连接池 + 熔断器）
│   ├── git_client/        # Git 浅克隆
│   ├── storage/           # SQLite 指纹库 + 连接池
│   ├── cache/             # LRU 内容缓存
│   ├── resilience/        # 熔断器 + 降级 + 限流
│   ├── observability/     # Metrics + SSE + 告警
│   └── reports/           # pyecharts + pyvis 可视化
├── api/                   # FastAPI REST API
├── cli/                   # Click 命令行
├── models/                # 数据模型
├── config/                # 配置管理
├── tools/                 # 性能分析 + 文档生成
└── utils/                 # orjson + 日志 + 审计
```

## 质量状态

- **1538 测试全通过** | ruff 0 错误 | 87% 覆盖率
- CI 流水线：ruff + pytest + bandit

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

## License

MIT
