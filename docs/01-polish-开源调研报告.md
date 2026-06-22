# ModuleMirror 细致打磨 — 开源调研报告

> 原则：**不重复造轮子，要做就做顶配**
> 日期：2026-06-21
> 版本：v1.0

---

## 1. 统一异常体系（P1-1）

### 最佳参考：FastAPI/Starlette 异常层次

| 项目 | URL | Stars |
|------|-----|-------|
| **Starlette** | https://github.com/encode/starlette | ~10k |
| **FastAPI** | https://github.com/fastapi/fastapi | ~82k |
| **SQLAlchemy** | https://github.com/sqlalchemy/sqlalchemy | ~10k |
| **Django** | https://github.com/django/django | ~82k |

### 核心设计模式

**Starlette/FastAPI 模式**（最推荐）：
```
HTTPException(Exception)           # 基础HTTP异常，带 status_code/detail
  └── WebSocketException          # WebSocket专用
StarletteHTTPError(HTTPException)  # 框架级HTTP错误
```

**SQLAlchemy 模式**（最严谨）：
```python
SQLAlchemyError                    # 所有异常基类
  ├── ArgumentError                # 参数错误
  ├── ObjectNotExecutableError     # 执行错误
  ├── ResourceClosedError          # 资源关闭错误
  └── UnsupportedCompilationError  # 编译错误
```

**Django 模式**（最全面）：
```python
DjangoException
  ├── ImproperlyConfigured
  ├── FieldDoesNotExist
  └── ValidationError              # 带message_dict的验证异常
```

### 推荐：融合 FastAPI + SQLAlchemy 模式

```python
class ModuleMirrorError(Exception):
    """所有 ModuleMirror 异常的基类"""
    def __init__(self, message: str, *, code: str | None = None, detail: dict | None = None):
        self.message = message
        self.code = code
        self.detail = detail or {}
        super().__init__(message)

class ConfigError(ModuleMirrorError):
    """配置相关错误"""

class AnalysisError(ModuleMirrorError):
    """分析过程错误"""
    class HashError(AnalysisError): ...
    class SimilarityError(AnalysisError): ...

class GitHubClientError(ModuleMirrorError):
    """GitHub API 错误"""
    class AuthError(GitHubClientError): ...
    class RateLimitError(GitHubClientError): ...
    class NotFoundError(GitHubClientError): ...

class DependencyError(ModuleMirrorError):
    """可选依赖缺失"""
```

### 为什么推荐
- FastAPI/Starlette 的 `HTTPException` 模式证明了 **status_code + message + detail** 三元组足以覆盖99%场景
- SQLAlchemy 的分层继承让 `except AnalysisError` 能捕获所有分析子异常
- Django 的 `ValidationError` 带 `message_dict` 的设计非常适合批量错误报告

---

## 2. 可选依赖统一管理（P1-4）

### 最佳参考：`importlib.util.find_spec` + `importlib.metadata`

| 项目 | URL | 说明 |
|------|-----|------|
| **Python stdlib** `importlib.util` | https://docs.python.org/3/library/importlib.html | 标准库，零依赖 |
| **Python stdlib** `importlib.metadata` | https://docs.python.org/3/library/importlib.metadata.html | Python 3.8+，可检测已安装包版本 |
| **pluggy** | https://github.com/pytest-dev/pluggy | pytest的插件管理，过度设计 |
| **stevedore** | https://github.com/openstack/stevedore | OpenStack插件管理，过重 |

### 推荐方案：自建轻量 `deps` 模块（参考 datasketch 模式）

datasketch 项目使用 `pip install datasketch[redis]` 的 optional extras 模式，运行时用 `importlib.util.find_spec` 检测。

```python
# modulemirror/deps.py
from importlib.util import find_spec
from typing import Optional

class MissingDependencyError(ImportError):
    def __init__(self, package: str, feature: str, install_hint: str = ""):
        self.package = package
        self.feature = feature
        msg = f"Package '{package}' is required for {feature}."
        if install_hint:
            msg += f" Install with: {install_hint}"
        super().__init__(msg)

def require(package: str, feature: str, install_extra: str = ""):
    if find_spec(package) is None:
        hint = f"pip install modulemirror[{install_extra}]" if install_extra else f"pip install {package}"
        raise MissingDependencyError(package, feature, hint)
    return True

def is_available(package: str) -> bool:
    return find_spec(package) is not None
```

**使用示例**：
```python
from modulemirror.deps import require, is_available

# 强制依赖检查
require("datasketch", "MinHash similarity", "similarity")
require("numpy", "vectorized computation", "math")

# 可选特性检查
if is_available("faiss"):
    from faiss import IndexFlatIP  # noqa
```

**pyproject.toml extras 配置**：
```toml
[project.optional-dependencies]
similarity = ["datasketch>=1.6", "mmh3>=4.0"]
visualization = ["pyecharts>=2.0"]
search = ["faiss-cpu>=1.7"]
math = ["numpy>=1.21", "scipy>=1.7"]
all = ["modulemirror[similarity,visualization,search,math]"]
```

### 为什么推荐
- **不需要第三方库**，`importlib.util.find_spec` 是标准库
- datasketch 的 `[redis]`/`[cassandra]` extras 模式已验证可行
- 统一的 `MissingDependencyError` 替代散落的 `try-except ImportError`
- `install_extra` 自动生成正确的 `pip install` 提示

---

## 3. 确定性哈希（P0-1）⭐ 最高优先级

### 最佳参考：mmh3（MurmurHash3）

| 项目 | URL | Stars | License | 速度 | 跨平台确定性 |
|------|-----|-------|---------|------|------------|
| **mmh3** | https://github.com/hajimes/mmh3 | ~600 | MIT | 极快（C扩展） | ✅ v4.0+ endian-neutral |
| **xxhash** | https://github.com/ifduyue/python-xxhash | ~350 | BSD | 极快（C扩展） | ✅ |
| **hashlib** (stdlib) | Python内置 | — | PSF | 中等 | ✅ |

### mmh3 vs xxhash 对比

| 维度 | mmh3 | xxhash |
|------|------|--------|
| 算法 | MurmurHash3 | xxHash/XXH3 |
| 32位输出 | `mmh3.hash()` | `xxhash.xxh32()` |
| 64位输出 | `mmh3.hash64()` | `xxhash.xxh64()` / `xxhash.xxh3_64()` |
| 128位输出 | `mmh3.hash128()` | `xxhash.xxh3_128()` |
| hashlib风格 | ✅ 实验性 | ✅ 完整 |
| numpy支持 | ✅ `mmh3_x64_128_digest(numpy.ndarray)` | ❌ |
| datasketch兼容 | ✅ **原生支持** | ❌ 需要适配 |
| 文档质量 | JOSS论文+详尽API文档 | 一般 |

### 🏆 推荐：mmh3

**核心原因：datasketch 原生使用 MurmurHash3**，mmh3 是其哈希后端，零适配成本。

```python
# modulemirror/hash.py
import mmh3

def stable_hash(data: str | bytes, seed: int = 42) -> int:
    return mmh3.hash(data, seed, signed=False)

def stable_hash64(data: str | bytes, seed: int = 42) -> int:
    return mmh3.hash64(data, seed, signed=False)[0]

# 替换所有 Python hash() 调用
# Before: hash(token)  # 跨进程不稳定！
# After:  stable_hash(token)  # 跨进程确定✅
```

**Winnowing 模块改造**：
```python
# 之前（不稳定）
fingerprint = hash(shingle)

# 之后（确定性）
from modulemirror.hash import stable_hash
fingerprint = stable_hash(shingle)
```

**datasketch MinHash 集成**：
```python
from datasketch import MinHash
import mmh3

# datasketch 内部默认就使用 mmh3.hash()
# 无需任何改动，只需确保 mmh3 已安装
mh = MinHash(num_perm=128, hashfunc=lambda x: mmh3.hash(x, signed=False))
```

---

## 4. 日志规范化（P1-2）

### 最佳参考：structlog（结构化日志）

| 项目 | URL | Stars | License | 最新版本 |
|------|-----|-------|---------|---------|
| **structlog** | https://github.com/hynek/structlog | ~3.5k | MIT/Apache-2.0 | 26.1.0 (2026-06) |
| **loguru** | https://github.com/Delgan/loguru | ~20k | MIT | 0.7.3 (2024-12) |
| **stdlib logging** | Python内置 | — | PSF | — |

### structlog vs loguru 对比

| 维度 | structlog | loguru |
|------|-----------|--------|
| 定位 | 结构化日志框架 | 零配置日志库 |
| 开箱即用 | 需配置 | ✅ `from loguru import logger` |
| JSON输出 | ✅ 内置 | ✅ `serialize=True` |
| 标准库兼容 | ✅ 双向桥接 | ✅ InterceptHandler |
| 类型标注 | ✅ 完整 | ❌ 部分 |
| 性能 | 高 | 高（号称10x） |
| 处理器链 | ✅ 函数式管道 | 单一配置 |
| 上下文绑定 | ✅ `bind()`/`contextualize()` | ✅ `bind()` |
| 输出格式 | JSON/logfmt/Console | 自定义格式串 |
| 生产验证 | 2013年至今 | 广泛使用 |

### 🏆 推荐：structlog

**核心原因**：ModuleMirror 是分析工具，结构化日志（JSON/logfmt）对日志分析和排查至关重要；structlog 的处理器管道设计更灵活。

```python
# modulemirror/log.py
import structlog

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()  # 生产环境 JSON
        # 开发环境可用 structlog.dev.ConsoleRenderer()
    ],
    wrapper_class=structlog.make_filtering_bound_logger(20),  # INFO
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

def get_logger(name: str = __name__):
    return structlog.get_logger(name)

# 使用
log = get_logger("winnowing")
log.info("fingerprint_generated", fingerprint_count=42, file_path="main.py")
```

**替换 print/logger/静默**：
```python
# Before:
print(f"Processing {path}")
logger.info(f"Similarity: {score}")
# (静默无日志)

# After:
log.info("processing_file", path=str(path))
log.info("similarity_computed", score=score, module_a=mod_a, module_b=mod_b)
log.debug("token_generated", token=token)  # 可通过级别控制
```

---

## 5. 性能微优化 — 向量化计算（P2-1）

### 最佳参考：numpy 向量化余弦相似度

| 项目 | URL | 说明 |
|------|-----|------|
| **numpy** | https://github.com/numpy/numpy | 向量化计算基础 |
| **scipy.spatial.distance** | https://docs.scipy.org/doc/scipy/reference/spatial.distance.html | `cosine`, `cdist` |
| **sklearn.metrics.pairwise** | https://scikit-learn.org/stable/modules/metrics.html | `cosine_similarity` |

### 推荐方案：numpy 向量化（零额外依赖，项目已依赖numpy）

```python
import numpy as np

# Before: 纯Python（极慢）
def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x ** 2 for x in a) ** 0.5
    norm_b = sum(x ** 2 for x in b) ** 0.5
    return dot / (norm_a * norm_b)

# After: numpy向量化（100x+ 加速）
def cosine_similarity_vec(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

# 批量计算（矩阵级别，1000x+ 加速）
def cosine_similarity_batch(embeddings: np.ndarray) -> np.ndarray:
    """计算 n×d 矩阵所有行对之间的余弦相似度"""
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    normalized = embeddings / norms
    return normalized @ normalized.T
```

**scipy 方案**（适合1对N计算）：
```python
from scipy.spatial.distance import cdist

def cosine_distances_batch(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return 1 - cdist(a, b, metric='cosine')
```

### 为什么推荐 numpy
- **项目已依赖 numpy**（datasketch 依赖），零新依赖
- 纯 Python 余弦相似度 → numpy 向量化：**100x+ 性能提升**
- 矩阵级批量计算：**1000x+ 性能提升**

---

## 6. CLI Shell 补全（P3-1）

### 最佳参考：Click 自带 shell 补全

| 项目 | URL | Stars | 说明 |
|------|-----|-------|------|
| **Click** | https://github.com/pallets/click | ~16k | 已内置 shell 补全（8.0+） |
| **argcomplete** | https://github.com/kislyuk/argcomplete | ~1.4k | argparse 补全，仅 bash/zsh |

### Click 8.0+ 内置补全（推荐，如项目使用 Click）

```python
import click

@click.group()
def cli():
    """ModuleMirror CLI"""
    pass

@cli.command()
@click.argument('path', type=click.Path(exists=True))
@click.option('--threshold', '-t', default=0.8, type=float)
def analyze(path, threshold):
    """Analyze module similarity"""
    pass

# 启用补全：eval "$_MODULEMIRROR_COMPLETE=bash_source modulemirror"
# 或 zsh:  eval "$_MODULEMIRROR_COMPLETE=zsh_source modulemirror"
```

### argcomplete（如项目使用 argparse）

```python
#!/usr/bin/env python
# PYTHON_ARGCOMPLETE_OK
import argcomplete, argparse

parser = argparse.ArgumentParser()
parser.add_argument("--threshold", type=float, default=0.8)
argcomplete.autocomplete(parser)
args = parser.parse_args()
```

### 🏆 推荐：Click 内置补全

**原因**：Click 8.0+ 已内置 bash/zsh/fish 补全，无需额外依赖；argcomplete 仅支持 bash/zsh。

---

## 7. pre-commit hooks（P3-1）

### 最佳参考：pre-commit + ruff

| 项目 | URL | Stars | 说明 |
|------|-----|-------|------|
| **pre-commit** | https://github.com/pre-commit/pre-commit | ~13k | Git hook 管理 |
| **ruff** | https://github.com/astral-sh/ruff | ~36k | 极速 linter+formatter |

### 推荐配置 `.pre-commit-config.yaml`

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v5.0.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-toml
      - id: check-added-large-files
      - id: check-merge-conflict

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.11.0
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.16.0
    hooks:
      - id: mypy
        additional_dependencies: [types-all]
```

### 为什么推荐
- **ruff** 替代 flake8+isort+black，一个工具搞定 linter+formatter，速度 10-100x
- pre-commit-hooks 提供基础文件检查
- mypy 在 pre-commit 中强制类型检查

---

## 8. mypy/pyright 配置（P3-1）

### 最佳参考：顶级 Python 项目的 mypy 配置

| 项目 | URL | 配置风格 |
|------|-----|---------|
| **FastAPI** | https://github.com/fastapi/fastapi | pyproject.toml [tool.mypy] |
| **SQLAlchemy** | https://github.com/sqlalchemy/sqlalchemy | pyproject.toml [tool.mypy] |
| **structlog** | https://github.com/hynek/structlog | pyproject.toml [tool.mypy] |

### 推荐 `pyproject.toml` 配置

```toml
[tool.mypy]
python_version = "3.10"
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_any_generics = true
check_untyped_defs = true
no_implicit_optional = true
warn_redundant_casts = true
warn_unused_ignores = true
show_error_codes = true
show_column_numbers = true
pretty = true

[[tool.mypy.overrides]]
module = ["datasketch.*", "pyecharts.*", "faiss.*"]
ignore_missing_imports = true

[tool.pyright]
typeCheckingMode = "strict"
pythonVersion = "3.10"
reportMissingImports = true
reportMissingTypeStubs = false
```

### 为什么推荐
- `strict = true` 是顶级项目的标配（FastAPI/SQLAlchemy 均使用）
- `ignore_missing_imports` 对 datasketch/faiss 等无 stub 的包必须
- pyright 作为补充类型检查器，VSCode 原生支持

---

## 9. MinHash 批量更新优化（P2-1）

### 最佳参考：datasketch MinHash

| 项目 | URL | Stars | 最新版本 |
|------|-----|-------|---------|
| **datasketch** | https://github.com/ekzhu/datasketch | ~2.8k | 1.10.0 (2026-04) |

### datasketch MinHash 批量 API

```python
from datasketch import MinHash

# 方式1：逐元素 update（当前实现，慢）
mh = MinHash(num_perm=128)
for token in tokens:
    mh.update(token.encode('utf-8'))  # 每次调用都有 Python→C 开销

# 方式2：批量 update（推荐，快2-5x）
mh = MinHash(num_perm=128)
mh.update_batch([token.encode('utf-8') for token in tokens])

# 方式3：从已有 hash值直接构造（最快，省去哈希计算）
import mmh3
mh = MinHash(num_perm=128, hashfunc=lambda x: mmh3.hash(x, signed=False))
# 直接操作内部 hashvalues 数组
hash_values = [mmh3.hash(t.encode('utf-8'), signed=False) for t in tokens]
# 注意：需要取 num_perm 个最小值
```

### 进一步优化：numpy 加速 MinHash

```python
import numpy as np
import mmh3
from datasketch import MinHash

def fast_minhash(tokens: list[str], num_perm: int = 128, seed: int = 42) -> MinHash:
    """利用 numpy 批量计算 MinHash，比逐元素 update 快 10x+"""
    # 为每个 seed 生成 hash 值矩阵 (num_tokens × num_perm)
    hashes = np.array([
        [mmh3.hash(t.encode('utf-8'), seed=seed + i, signed=False) for i in range(num_perm)]
        for t in tokens
    ], dtype=np.uint64)
    # 取每列最小值
    min_hashes = hashes.min(axis=0)
    
    mh = MinHash(num_perm=num_perm)
    mh.hashvalues = min_hashes
    return mh
```

### 为什么推荐
- `update_batch()` 是 datasketch 官方提供的批量API，零额外依赖
- numpy 加速方案利用向量化，适合大规模 token 集合
- mmh3 与 datasketch 原生兼容（共享 MurmurHash3 后端）

---

## 总结：推荐依赖矩阵

| 模块 | 推荐方案 | 新增依赖 | 优先级 |
|------|---------|---------|--------|
| 统一异常 | 自建（参考 FastAPI/SQLAlchemy） | 无 | P1 |
| 可选依赖 | 自建 `deps.py`（importlib.util） | 无 | P1 |
| 确定性哈希 | **mmh3** | `mmh3>=4.0` | P0 ⭐ |
| 日志规范化 | **structlog** | `structlog>=24.0` | P1 |
| 向量化计算 | **numpy**（已依赖） | 无 | P2 |
| CLI补全 | **Click 内置** | 无（如用Click） | P3 |
| pre-commit | **ruff-pre-commit** | 开发依赖 | P3 |
| mypy配置 | **strict mode** | 无 | P3 |
| MinHash批量 | **datasketch.update_batch** + numpy | 无 | P2 |

### pyproject.toml 依赖汇总

```toml
[project]
dependencies = [
    "mmh3>=4.0",
    "structlog>=24.0",
    "numpy>=1.21",
    "click>=8.0",
    "datasketch>=1.6",
]

[project.optional-dependencies]
dev = [
    "ruff>=0.11.0",
    "mypy>=1.10",
    "pre-commit>=3.7",
    "pytest>=8.0",
]
similarity = ["datasketch>=1.6", "mmh3>=4.0"]
visualization = ["pyecharts>=2.0"]
search = ["faiss-cpu>=1.7"]
all = ["modulemirror[similarity,visualization,search]"]
```
