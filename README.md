# ModuleMirror

GitHub 项目代码相似度检测工具，支持两大核心用途：

- **自我审视**：检测自己项目与其他项目的相似模块，发现可复用代码
- **抄袭溯源**：检测目标项目是否复制了其他项目的代码，追溯来源

## 技术方案

- **双重指纹检测**：Winnowing 指纹算法（快速筛选）+ AST 结构指纹（精准确认）
- **AST 深度验证**：对高相似度结果进行节点级比对，消除哈希碰撞误报
- **tree-sitter 多语言解析**：Python / JavaScript / Java / TypeScript / Go / Rust / C / C++
- **Jaccard 相似度 + 倒排索引**：快速候选筛选 + 最小 overlap 预过滤
- **GitHub API 非克隆模式**：优先 API 获取文件内容，大项目/限流时回退 git clone
- **SQLite 指纹库**：持久化存储 + 增量更新 + 相似度缓存 + 异步任务管理
- **NCD 压缩距离**：项目整体相似度快速判断（50MB 内存限制）
- **交互式 HTML 报告**：搜索/过滤/排序/柱状图/代码差异对比/热力图
- **断点续传**：大规模检测中断后可恢复
- **并发检测**：ThreadPoolExecutor 并行处理多候选项目
- **API 安全**：认证中间件 + HTTP 安全头 + CORS 白名单 + 路径遍历防护

## 安装

```bash
pip install -e .
```

需要 tree-sitter 和语言解析器：

```bash
pip install tree-sitter tree-sitter-python tree-sitter-javascript tree-sitter-java tree-sitter-typescript
```

可选语言支持：

```bash
pip install tree-sitter-go tree-sitter-rust tree-sitter-c
```

## 使用

### 自我审视检测

```bash
gh-sim detect -t ./my-project -c https://github.com/other/project -l python --threshold 70
gh-sim detect -t ./my-project -c https://github.com/other/project --checkpoint cp.json  # 断点续传
```

### 抄袭溯源检测

```bash
gh-sim plagiarism -t ./suspect-project --db ./fingerprint_db.sqlite
gh-sim plagiarism -t ./suspect-project --db ./fingerprint_db.sqlite --update-db  # 同时入库
```

### 指纹库管理

```bash
gh-sim db init
gh-sim db add -p https://github.com/some/project
gh-sim db import -f projects.txt        # 批量导入
gh-sim db update -p https://github.com/some/project  # 增量更新
gh-sim db stats
gh-sim db list
gh-sim db delete -p some/project
```

### 配置管理

```bash
gh-sim config generate -o gh-sim.yaml   # 生成默认配置
gh-sim config validate -f gh-sim.yaml   # 验证配置文件
```

### 代码差异对比

```bash
gh-sim diff --file1 src/a.py --file2 src/b.py
gh-sim diff -1 src/a.py -2 src/b.py -u  # unified diff 格式
```

### 搜索候选项目

```bash
gh-sim search -q "web framework" -l python --max 10
```

### NCD 整体相似度

```bash
gh-sim ncd -s ./project-a -t ./project-b
```

### Web API

```bash
uvicorn gh_similarity_detector.api.app:app --host 0.0.0.0 --port 8000
```

API 端点：

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /detect | 执行检测 |
| POST | /ncd | 计算 NCD 相似度 |
| POST | /search | 搜索 GitHub 仓库 |
| GET | /db/stats | 指纹库统计 |
| GET | /db/projects | 列出项目 |
| POST | /db/add | 添加项目 |
| DELETE | /db/projects/{id} | 删除项目 |
| POST | /tasks | 创建异步检测任务 |
| GET | /tasks | 列出任务 |
| GET | /tasks/{id} | 获取任务详情 |
| DELETE | /tasks/{id} | 删除任务 |
| GET | /reports | 列出报告 |
| GET | /reports/{id} | 获取报告内容 |
| GET | /health | 健康检查 |

## 配置

| 环境变量 | 说明 |
|----------|------|
| GITHUB_TOKEN | GitHub API Token（推荐，提升速率限制） |
| MODULEMIRROR_API_KEY | API 认证密钥（设置后所有请求需携带 X-API-Key 头） |
| MODULEMIRROR_CORS_ORIGINS | CORS 允许域名（逗号分隔） |
| MODULEMIRROR_DB_PATH | 指纹库路径（默认 ./fingerprint_db.sqlite） |

## 性能基线

| 算法 | 规模 | mean | p95 |
|------|------|------|-----|
| CodeTokenizer.tokenize | 11KB 代码 | 2.85ms | 4.58ms |
| Winnowing.generate_fingerprints | 100 函数 | 21.95ms | 29.43ms |
| InvertedIndex.build | 500 模块 | 2.68ms | 11.85ms |
| InvertedIndex.get_candidates | 30 指纹查询 | 0.01ms | 0.02ms |

## 项目结构

```
gh_similarity_detector/
├── core/                  # 核心算法
│   ├── fingerprint/       # Winnowing + AST 指纹
│   ├── similarity/        # 相似度计算 + AST 深度验证
│   ├── module/            # tree-sitter 模块提取
│   ├── project/           # 项目获取（API 优先 + clone 回退 + 大文件限制）
│   ├── plagiarism/        # 抄袭溯源
│   ├── orchestration/     # 断点续传检查点
│   └── report/            # 报告生成（Jinja2 + autoescape + 脱敏）
├── infrastructure/        # 基础设施
│   ├── github_client/     # GitHub API（连接池复用 + 错误码分类）
│   ├── git_client/        # Git 浅克隆
│   ├── storage/           # SQLite 指纹库（批量写入 + 缓存 + 任务管理）
│   ├── cache/             # SHA256 内容哈希缓存（原子写入）
│   └── engines/           # NCD / jscpd 集成
├── api/                   # FastAPI 接口（认证 + 安全头 + CORS）
├── cli/                   # Click 命令行（db 子命令拆分）
│   ├── main.py            # 核心命令
│   └── db_commands.py     # 指纹库管理命令
├── models/                # 数据模型
├── config/                # 配置管理（YAML + .env + 未知字段过滤）
└── utils/                 # 工具（审计日志 + Jaccard + asyncio）
```

## 质量状态

- **316 测试全通过** | ruff 0 错误 | bandit 0 HIGH | 覆盖率 80%
- CI 流水线：ruff + pytest + bandit + 覆盖率门禁
- 质量评分：**A**

## 文档

| 文档 | 说明 |
|------|------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | 架构设计（六边形架构 + 核心流程 + 安全架构） |
| [ALGORITHM.md](ALGORITHM.md) | 算法文档（Winnowing + AST + Jaccard + NCD） |
| [API_REFERENCE.md](API_REFERENCE.md) | API 参考文档（FastAPI 所有端点） |
| [DEPLOYMENT.md](DEPLOYMENT.md) | 部署指南（本地/Docker/生产/Nginx） |
| [TUTORIAL.md](TUTORIAL.md) | 快速上手教程（5分钟入门） |
| [HOWTO.md](HOWTO.md) | 场景化操作指南（7个实战场景） |
| [PERFORMANCE.md](PERFORMANCE.md) | 性能调优指南（基线+参数+优化） |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | 故障排查指南（9个常见问题） |
| [CHANGELOG.md](CHANGELOG.md) | 变更日志（Keep a Changelog 格式） |
| [CONTRIBUTING.md](CONTRIBUTING.md) | 贡献指南（开发流程 + PR 规范） |
| [TASK_LIST.md](TASK_LIST.md) | 成熟度任务清单 v3.0（132 任务，11 里程碑） |
| [COMPETITOR_RESEARCH.md](COMPETITOR_RESEARCH.md) | 竞品调研 + 方法论洞察 |

## License

MIT
