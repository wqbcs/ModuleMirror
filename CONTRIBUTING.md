# 贡献指南

感谢你对 ModuleMirror 的关注！本文档将帮助你快速上手开发。

## 目录

- [开发环境搭建](#开发环境搭建)
- [项目结构](#项目结构)
- [架构概览](#架构概览)
- [开发流程](#开发流程)
- [代码规范](#代码规范)
- [提交前检查](#提交前检查)
- [测试](#测试)
- [调试指南](#调试指南)
- [PR 规范](#pr-规范)
- [问题报告](#问题报告)
- [发布流程](#发布流程)

## 开发环境搭建

### 前置要求

- Python 3.9+
- Git 2.30+
- Poetry 1.7+（包管理）
- tree-sitter C 编译器（用于解析器编译）

### 快速开始

```bash
# 1. 克隆仓库
git clone https://github.com/your-org/ModuleMirror.git
cd ModuleMirror

# 2. 安装 Poetry（如未安装）
pip install poetry

# 3. 安装所有依赖（含开发依赖）
poetry install

# 4. 安装 API 可选依赖
poetry install --extras api

# 5. 安装 pre-commit 钩子
poetry run pre-commit install

# 6. 验证安装
poetry run python -c "import gh_similarity_detector; print('OK')"
poetry run pytest tests/ -q --tb=no  # 快速验证测试
```

### 使用 pip 替代 Poetry

```bash
pip install -e ".[api]"
pip install -e ".[dev]"
```

### 环境变量

| 变量 | 用途 | 默认值 |
|------|------|--------|
| `MODULEMIRROR_LOG_LEVEL` | 日志级别 | `INFO` |
| `MODULEMIRROR_LOG_FORMAT` | 日志格式 (`text`/`json`) | `text` |
| `GITHUB_TOKEN` | GitHub API Token | 无 |
| `MODULEMIRROR_DB_PATH` | SQLite 数据库路径 | `./fingerprints.db` |

### IDE 配置

#### VS Code

推荐扩展：
- `ms-python.python` - Python 语言支持
- `charliermarsh.ruff` - Ruff linter
- `matangover.mypy` - 类型检查

`.vscode/settings.json` 推荐配置：
```json
{
  "python.testing.pytestEnabled": true,
  "python.testing.pytestArgs": ["tests", "-v"],
  "editor.formatOnSave": true,
  "[python]": {
    "editor.defaultFormatter": "charliermarsh.ruff"
  },
  "ruff.lineLength": 100
}
```

#### PyCharm

- 设置 pytest 为默认测试运行器
- 配置 ruff 为外部工具
- 启用 mypy 检查器插件

## 项目结构

```
gh_similarity_detector/
├── api/                    # Web API 层（FastAPI）
│   ├── app.py              # FastAPI 应用入口
│   └── routes/             # API 路由子模块
│       ├── detect.py       # 检测路由
│       ├── history.py      # 历史记录路由
│       ├── health.py       # 健康检查路由
│       └── metrics.py      # Prometheus metrics 路由
├── cli/                    # CLI 层（Click）
│   ├── main.py             # CLI 入口
│   └── db_commands.py      # 数据库管理命令
├── config/                 # 配置层
│   └── config.py           # DetectionConfig（Pydantic v2）
├── core/                   # 核心领域层
│   ├── fingerprint/        # 指纹计算
│   │   ├── winnowing.py    # Winnowing 算法（O(n)优化）
│   │   ├── generator.py    # 指纹生成器（并行化）
│   │   └── language_plugins.py  # 语言插件体系
│   ├── similarity/         # 相似度计算
│   │   ├── calculator.py   # Jaccard + 倒排索引 + 增量更新
│   │   └── ast_comparator.py    # AST 深度比对
│   ├── plagiarism/         # 抄袭溯源
│   │   └── detector.py     # PlagiarismDetector
│   ├── comparison/         # 多仓库对比
│   │   ├── multi_repo.py   # MultiRepositoryComparator
│   │   ├── batch_detector.py    # BatchDetector
│   │   └── result_comparator.py # ResultComparator
│   ├── orchestration/      # 流程编排
│   │   ├── pipeline.py     # DetectionPipeline（含幂等性守卫）
│   │   └── checkpoint.py   # 断点续传
│   ├── delta_detector.py   # 增量检测
│   ├── project/            # 项目获取
│   ├── module/             # 模块提取
│   └── report/             # 报告生成
├── infrastructure/         # 基础设施层
│   ├── storage/            # 持久化（SQLite，已拆分）
│   │   ├── fingerprint_db.py   # FingerprintDB 门面
│   │   ├── schema.py       # DDL + 版本管理
│   │   ├── migrations.py   # 迁移逻辑
│   │   ├── queries.py      # CRUD 查询
│   │   └── _connection_pool.py  # 连接池
│   ├── cache/              # 缓存（LRU + SHA256）
│   ├── github_client/      # GitHub API 客户端（含 Fallback）
│   ├── resilience/         # 弹性模式
│   │   ├── circuit_breaker.py   # 断路器
│   │   ├── retry_strategies.py  # 重试策略
│   │   ├── bulkhead.py     # 并发隔离
│   │   ├── fallback.py     # 降级策略
│   │   ├── timeout.py      # 超时控制
│   │   ├── ssrf_protection.py   # SSRF 防护
│   │   └── adaptive_rate_limiter.py  # 自适应限流
│   ├── observability/      # 可观测性
│   │   ├── metrics.py      # Prometheus 指标
│   │   ├── memory_profiler.py   # 内存画像
│   │   └── alerting.py     # 告警规则
│   ├── security/           # 安全
│   │   ├── authorization.py    # 对象级授权
│   │   ├── api_security.py     # API 安全管理
│   │   └── owasp_compliance.py # OWASP 合规
│   ├── lifecycle/          # 生命周期
│   │   └── graceful_shutdown.py  # 优雅关闭
│   └── io/                 # IO 流式处理
│       └── stream_reader.py    # 大文件流式读取
├── models/                 # 数据模型
├── utils/                  # 工具集
│   ├── exceptions.py       # 领域异常体系
│   ├── validation.py       # Pydantic v2 校验
│   ├── sanitizer.py        # 输入消毒
│   ├── logger.py           # 结构化日志
│   ├── idempotency.py      # 幂等性守卫
│   ├── resource_tracker.py # 资源泄露检测
│   ├── audit.py            # 审计日志
│   └── math_utils.py       # 数学工具
tests/                      # 测试套件（890+ 测试）
├── conftest.py             # 共享 fixtures + 工厂
├── test_property_based.py  # Hypothesis 属性测试
└── ...                     # 各模块测试文件
```

## 架构概览

ModuleMirror 采用**六边形架构（Hexagonal Architecture）**，核心业务逻辑与基础设施严格分离：

```
适配器层（CLI / Web API / GitHub Client）
    ↓
应用层（DetectionPipeline 编排器）
    ↓
领域层（FingerprintEngine + SimilarityEngine + PlagiarismDetector）
    ↓
基础设施层（SQLite / Cache / Resilience / Observability）
```

### 关键设计决策

详见 [ADR.md](ADR.md)，当前共 26 条架构决策记录。核心决策：

- **ADR-001**: Winnowing 算法选型（局部敏感性 + 全局稳定性）
- **ADR-002**: 六边形架构（领域与基础设施隔离）
- **ADR-006**: tree-sitter 多语言解析（统一 AST 抽象）
- **ADR-011**: SQLite 指纹库（嵌入式零部署）
- **ADR-016**: 幂等性守卫（DeterministicContext + result_hash）

### 数据流

```
源代码 → CodeTokenizer → k-gram → RollingHash → Winnowing指纹
                                                     ↓
目标代码 → ... → Winnowing指纹 → Jaccard相似度 → AST验证 → 置信度评分
                                                     ↓
                                              HTML/JSON/Markdown 报告
```

## 开发流程

### 分支策略

- `main` - 稳定发布分支
- `develop` - 开发集成分支
- `feature/xxx` - 功能分支
- `fix/xxx` - 修复分支
- `refactor/xxx` - 重构分支

### 标准流程

1. **Fork 仓库** → 克隆到本地
2. **创建分支** `git checkout -b feature/xxx`
3. **编写代码** + 测试 → 确保所有检查通过
4. **本地验证** `make check`（lint + type + test + security）
5. **提交 PR** → 填写 PR 模板 → 等待审查

### 添加新语言支持

1. 在 `language_plugins.py` 中创建新的 `LanguagePlugin` 子类
2. 安装对应的 `tree-sitter-<lang>` 包
3. 在 `PluginRegistry` 中注册
4. 编写测试用例（参考 `tests/test_language_plugins.py`）

### 添加新弹性模式

1. 在 `infrastructure/resilience/` 下创建模块
2. 遵循 CircuitBreaker/Bulkhead 的设计模式
3. 集成到 `DetectionPipeline` 或 `GitHubClient`
4. 编写单元测试 + 集成测试

## 代码规范

### 格式化与 Lint

- **格式化**：ruff（line-length=100）
- **类型检查**：mypy（strict 模式，`disallow_untyped_defs=true`）
- **安全扫描**：bandit（0 HIGH 问题）
- **测试**：pytest（覆盖率 ≥ 80%）

### 命名约定

| 类型 | 风格 | 示例 |
|------|------|------|
| 模块/包 | snake_case | `delta_detector.py` |
| 类 | PascalCase | `FingerprintGenerator` |
| 函数/方法 | snake_case | `compute_jaccard()` |
| 常量 | UPPER_SNAKE | `DEFAULT_KGRAM_SIZE` |
| 私有方法 | _前缀 | `_normalize_value()` |
| Pydantic 模型 | PascalCase + Config/Result 后缀 | `DetectionConfig`, `SimilarityResult` |

### 导入顺序

按 ruff 默认规则：标准库 → 第三方 → 本项目，各组之间空一行。

### 异常处理

使用项目定义的领域异常体系（`utils/exceptions.py`）：

```python
from gh_similarity_detector.utils.exceptions import (
    ModuleMirrorError,       # 基类
    FingerprintError,        # 指纹计算错误
    SimilarityError,         # 相似度计算错误
    StorageError,            # 存储层错误
    ValidationError,         # 数据校验错误
    SecurityError,           # 安全错误
    InfrastructureError,     # 基础设施错误
)
```

不要使用裸 `Exception`，始终使用或定义领域异常子类。

### 日志

使用结构化日志：

```python
from gh_similarity_detector.utils.logger import logger

logger.info("Detection completed", extra={
    "module_count": 10,
    "similarity_threshold": 0.8,
    "correlation_id": "req-123",
})
```

不要使用 `print()` 输出调试信息。

## 提交前检查

```bash
# 完整检查（推荐）
ruff check .
mypy gh_similarity_detector/
pytest tests/ -v --cov=gh_similarity_detector --cov-fail-under=80
bandit -r gh_similarity_detector/ -ll

# 快速检查（日常开发）
ruff check .
pytest tests/ -x -q        # -x: 首个失败即停
```

### 使用 Makefile（如有）

```bash
make lint      # ruff + mypy
make test      # pytest + 覆盖率
make security  # bandit
make check     # 全部检查
```

## 测试

### 运行测试

```bash
pytest tests/ -v                           # 全量测试
pytest tests/test_xxx.py -v               # 单文件测试
pytest tests/test_xxx.py::test_func -v    # 单测试函数
pytest tests/ -k "winnowing" -v           # 按关键词筛选
pytest tests/ --cov --cov-report=html     # 覆盖率报告
pytest tests/ -n auto                     # 并行测试（xdist）
```

### 测试分类

| 文件 | 类型 | 说明 |
|------|------|------|
| `test_*.py` | 单元测试 | 各模块功能测试 |
| `test_property_based.py` | 属性测试 | Hypothesis 驱动的属性验证 |
| `test_integration.py` | 集成测试 | 跨模块集成验证 |
| `conftest.py` | Fixtures | 共享测试夹具 + 工厂 |

### 编写测试

- 每个新功能必须附带测试
- 使用 `conftest.py` 中的工厂函数创建测试数据
- 属性测试使用 Hypothesis（参考 `test_property_based.py`）
- Mock 外部依赖（GitHub API、文件系统），不依赖网络

```python
# 使用工厂创建测试数据
def test_similarity(sample_modules, sample_fingerprints):
    result = calculator.calculate(sample_fingerprints[0], sample_fingerprints[1])
    assert result.jaccard_similarity >= 0.0
    assert result.jaccard_similarity <= 1.0
```

### 覆盖率要求

- 新代码覆盖率 ≥ 80%
- 核心算法（Winnowing/Jaccard）覆盖率 ≥ 90%
- 不允许覆盖率回退

## 调试指南

### 常见问题排查

#### 1. tree-sitter 解析失败

```python
# 检查语言是否支持
from gh_similarity_detector.core.fingerprint.language_plugins import PluginRegistry
registry = PluginRegistry()
print(registry.list_languages())  # 查看已注册语言

# 检查 tree-sitter 版本
import tree_sitter
print(tree_sitter.__version__)  # 应为 0.25+
```

**常见错误**：`language.query()` 已废弃，使用 `Query(language, query_str)` + `QueryCursor`。

#### 2. 指纹不一致（跨会话）

Python 3.3+ 的 `hash()` 默认随机化，导致指纹跨会话不一致。项目已使用确定性多项式哈希替代。

验证：
```python
from gh_similarity_detector.core.fingerprint.winnowing import Winnowing
w = Winnowing(kgram_size=5, window_size=4)
fps1 = w.generate_fingerprints_from_code("def foo(): pass")
fps2 = w.generate_fingerprints_from_code("def foo(): pass")
assert fps1 == fps2  # 必须一致
```

#### 3. SQLite 数据库锁定

```python
# 检查连接池状态
from gh_similarity_detector.infrastructure.storage.fingerprint_db import FingerprintDB
db = FingerprintDB("test.db")
# 查看连接池大小
print(db._pool.size())  # 默认 5
```

如遇 `database is locked`，检查是否有未关闭的连接或长事务。

#### 4. GitHub API 限流

```python
# 查看 Circuit Breaker 状态
from gh_similarity_detector.infrastructure.resilience.circuit_breaker import github_circuit
print(github_circuit.state)  # CLOSED / OPEN / HALF_OPEN

# 查看自适应限流
from gh_similarity_detector.infrastructure.resilience.adaptive_rate_limiter import adaptive_limiter
print(adaptive_limiter.get_wait_time())
```

#### 5. 内存问题

```python
# 使用内存画像分析
from gh_similarity_detector.infrastructure.observability.memory_profiler import MemoryProfiler
profiler = MemoryProfiler()
with profiler.track_allocations("detection"):
    # ... 你的代码 ...
snapshot = profiler.take_snapshot()
print(snapshot)
```

### 日志调试

```bash
# 启用 DEBUG 级别日志
MODULEMIRROR_LOG_LEVEL=DEBUG pytest tests/ -v

# JSON 格式日志（适合生产环境）
MODULEMIRROR_LOG_FORMAT=json python -m gh_similarity_detector.cli.main detect ...

# 查看特定模块日志
MODULEMIRROR_LOG_LEVEL=DEBUG python -c "
from gh_similarity_detector.utils.logger import logger
import logging
logger.setLevel(logging.DEBUG)
# ... 你的调试代码 ...
"
```

### 性能调试

```python
# Prometheus 指标查看
import requests
resp = requests.get("http://localhost:8000/metrics")
print(resp.text)

# Winnowing 性能基准
import time
from gh_similarity_detector.core.fingerprint.winnowing import Winnowing
w = Winnowing(kgram_size=5, window_size=4)
code = "def foo():\n" + "    x = 1\n" * 10000
start = time.perf_counter()
fps = w.generate_fingerprints_from_code(code)
elapsed = time.perf_counter() - start
print(f"Generated {len(fps)} fingerprints in {elapsed:.3f}s")
```

### 断点调试

在测试中使用 `breakpoint()` 或 `import pdb; pdb.set_trace()`：

```python
def test_something():
    result = complex_calculation()
    breakpoint()  # Python 3.7+ 内置
    assert result.is_valid
```

## PR 规范

### 标题格式

遵循 [Conventional Commits](https://www.conventionalcommits.org/)：

- `feat: 新功能描述`
- `fix: 修复描述`
- `refactor: 重构描述`
- `docs: 文档变更`
- `test: 测试补充`
- `perf: 性能优化`
- `chore: 构建/工具变更`
- `security: 安全修复`

### PR 检查清单

- [ ] 代码通过 ruff 检查
- [ ] 类型检查通过（mypy）
- [ ] 新代码有对应测试
- [ ] 测试覆盖率 ≥ 80%
- [ ] 无 bandit HIGH 安全问题
- [ ] PR 描述清晰说明变更原因和内容
- [ ] 大型变更先提 Issue 讨论

### 审查标准

- **功能正确性**：逻辑是否正确
- **测试充分性**：是否有足够测试覆盖
- **代码风格**：是否符合项目规范
- **安全性**：是否引入安全隐患
- **性能**：是否影响性能
- **向后兼容**：是否破坏现有 API

## 问题报告

提交 Issue 时请包含：

- **复现步骤**：逐步操作说明
- **期望行为** vs **实际行为**
- **环境信息**：Python 版本、OS、ModuleMirror 版本
- **日志输出**：`MODULEMIRROR_LOG_LEVEL=DEBUG` 下的完整日志
- **最小复现示例**：如有可能

### 问题分级

| 级别 | 描述 | 响应时间 |
|------|------|----------|
| P0 致命 | 数据丢失/安全漏洞 | 24h |
| P1 严重 | 核心功能不可用 | 72h |
| P2 一般 | 功能异常但有变通 | 1 周 |
| P3 轻微 | UI/文档/体验问题 | 2 周 |

## 发布流程

1. 更新 `pyproject.toml` 版本号
2. 更新 `CHANGELOG.md`
3. 运行完整测试套件
4. 创建 Git tag（`v0.x.y`）
5. 构建 发布包（`poetry build`）
6. 发布到 PyPI（`poetry publish`）
7. 创建 GitHub Release
