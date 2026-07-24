# ModuleMirror API 参考

Base URL: `http://localhost:8000`

所有端点均可通过 `/v1` 前缀访问（如 `/v1/detect`、`/v1/auth/login`）。

## 认证

若设置了环境变量 `MODULEMIRROR_API_KEY`，所有请求需携带 `X-API-Key` 请求头：

```
X-API-Key: your-api-key
```

---

## 检测

### POST /detect

执行自我审视检测，比较目标项目与候选项目的相似模块。

**请求体：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| target | string | 是 | - | 目标项目路径或 URL |
| candidates | string[] | 是 | - | 候选项目路径或 URL 列表 |
| language | string[] | 否 | ["python"] | 检测语言 |
| threshold | float | 否 | 70.0 | 相似度阈值 (0-100) |
| granularity | string | 否 | "function" | 模块粒度: file/function/class |

**响应体：**

```json
{
  "results": [
    {
      "source_module": "module_id_1",
      "target_module": "module_id_2",
      "similarity": 85.5,
      "reuse_suggestion": "reuse",
      "snippet": "matched code..."
    }
  ],
  "total_matches": 1
}
```

### POST /plagiarism

执行抄袭溯源检测，从指纹库中反向查找相似来源。

**请求体：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| target | string | 是 | - | 嫌疑项目路径或 URL |
| language | string[] | 否 | ["python"] | 检测语言 |
| threshold | float | 否 | 70.0 | 相似度阈值 |
| db_path | string | 否 | "./fingerprint_db.sqlite" | 指纹库路径 |

### POST /ncd

计算两个项目目录的归一化压缩距离相似度。

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| source_dir | string | 是 | 源目录路径 |
| target_dir | string | 是 | 目标目录路径 |
| extensions | string[] | 否 | 文件扩展名过滤，默认 [".py", ".js", ".java", ".ts"] |

**响应体：**

```json
{
  "similarity": 0.75,
  "source": "project-a",
  "target": "project-b"
}
```

### POST /quality-gate

评估检测结果是否满足质量门禁标准。

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| results | object | 是 | 检测结果对象 |
| gate_type | string | 否 | 门禁类型: default/strict/custom |

### POST /sbp-analyze

SBP (Similar But Patched) 分析，识别相似但已修补的代码。

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| source | string | 是 | 源项目路径 |
| target | string | 是 | 目标项目路径 |
| check_cve | bool | 否 | 是否检查 CVE 模式 |

---

## 异步任务

### POST /tasks

创建异步检测任务，后台线程执行。

**请求体：** 与 `/detect` 相同。

**响应体：**

```json
{
  "id": "uuid",
  "target_project": "project_url",
  "status": "pending",
  "progress": 0.0,
  "created_at": null
}
```

### GET /tasks

列出所有检测任务，可选 `?status=running|completed|failed` 过滤。

### GET /tasks/{task_id}

获取任务详情，包含进度和结果路径。

### DELETE /tasks/{task_id}

删除指定任务。

### GET /tasks/{task_id}/stream

SSE (Server-Sent Events) 实时推送任务进度。

**响应格式：** `text/event-stream`

---

## 指纹库管理

### GET /db/stats

获取指纹库统计信息（项目数、模块数、指纹数等）。

**响应体：**

```json
{
  "total_projects": 42,
  "total_modules": 1560,
  "total_fingerprints": 78900,
  "db_size_mb": 12.5
}
```

### GET /db/projects

列出指纹库中所有项目。

### POST /db/add

添加项目到指纹库，自动提取模块和指纹。

**请求体：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| project | string | 是 | - | 项目路径或 URL |
| language | string[] | 否 | ["python"] | 检测语言 |
| min_tokens | int | 否 | 50 | 最小 token 数 |

### DELETE /db/projects/{project_id}

从指纹库删除指定项目。

---

## 报告

### GET /reports

列出所有检测报告，可选 `?report_dir=./report` 指定目录。

### GET /reports/{report_id}

获取报告内容，支持 JSON/HTML/Markdown 格式。

### GET /reports/{report_id}/summary

获取报告摘要统计。

### GET /reports/visual/latest

获取最新可视化报告（D3.js 热力图）。

---

## 认证

### POST /auth/login

API Key 换取 JWT Token。

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| api_key | string | 是 | API Key |

**响应体：**

```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

### POST /auth/refresh

刷新 JWT Token。

**请求头：** `Authorization: Bearer <token>`

### POST /auth/revoke

吊销 Token 或 API Key。

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| token | string | 否 | 要吊销的 JWT Token |
| api_key_id | string | 否 | 要吊销的 API Key ID |

### POST /auth/api-keys

创建 API Key（需管理员权限）。

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | 是 | Key 名称 |
| permissions | string[] | 否 | 权限列表 |
| expires_in_days | int | 否 | 过期天数 |

### GET /auth/api-keys

列出所有 API Key。

### DELETE /auth/api-keys/{key_id}

吊销 API Key（需管理员权限）。

### GET /auth/me

获取当前认证用户信息。

---

## 高级分析

### POST /analysis/dataframe

Polars DataFrame 高级分析，支持结构化查询和聚合。

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| results | object | 是 | 检测结果 |
| operations | string[] | 否 | 聚合操作: mean/max/min/median |

### POST /analysis/batch/load

从文件加载批量检测任务列表。

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| file_path | string | 是 | 任务列表文件路径 |
| format | string | 否 | 文件格式: json/csv/yaml |

### POST /analysis/batch/execute

执行批量检测任务。

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| tasks | object[] | 是 | 任务列表 |
| parallel | int | 否 | 并行数 |

### POST /analysis/multi-repo

多仓库对比检测。

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| repositories | string[] | 是 | 仓库路径或 URL 列表 |
| language | string[] | 否 | 检测语言 |

### POST /analysis/compare

对比两次检测结果差异。

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| result_a | object | 是 | 第一次检测结果 |
| result_b | object | 是 | 第二次检测结果 |

### POST /analysis/minhash-tune

MinHash 参数调优。

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| sample_data | object | 是 | 样本数据 |
| num_perm_range | int[] | 否 | num_perm 搜索范围 |

### POST /analysis/cluster

检测结果聚类分析（Agglomerative/Spectral）。

**请求体：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| results | object | 是 | - | 检测结果 |
| algorithm | string | 否 | "agglomerative" | 聚类算法: agglomerative/spectral |
| n_clusters | int | 否 | 3 | 聚类数 |

---

## 规则引擎

### GET /rules

列出所有规则。

### POST /rules

添加规则。

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | 是 | 规则名称 |
| pattern | string | 是 | 匹配模式 |
| severity | string | 否 | 严重度: info/warning/error/critical |
| action | string | 否 | 动作: flag/suppress/annotate |

### DELETE /rules/{rule_id}

删除规则。

### POST /rules/load-yaml

从 YAML 加载规则。

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| yaml_content | string | 是 | YAML 规则内容 |

### POST /rules/evaluate

评估规则匹配。

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| code | string | 是 | 待评估代码 |
| rules | string[] | 否 | 指定规则 ID |

---

## 语义差异

### POST /semantic-diff/analyze

语义级差异分析，识别实体级变更（新增/删除/修改/重命名）。

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| source | string | 是 | 源代码路径 |
| target | string | 是 | 目标代码路径 |
| language | string | 否 | 编程语言 |

### POST /semantic-diff/batch

批量语义差异分析。

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| pairs | object[] | 是 | 源-目标对列表 |

---

## 克隆血统

### GET /lineage/stats

获取血统追踪统计信息。

### POST /lineage/trace

追踪克隆传播路径。

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| module_id | string | 是 | 模块 ID |
| depth | int | 否 | 追踪深度 |

---

## 算法插件

### GET /algorithms

列出所有已注册的算法插件。

### GET /algorithms/{name}

获取指定算法的元信息（参数、描述、性能特征）。

### POST /algorithms/{name}/similarity

用指定算法计算相似度。

**请求体：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| source | string | 是 | 源代码 |
| target | string | 是 | 目标代码 |
| params | object | 否 | 算法特定参数 |

---

## Webhook

### POST /webhook/github

接收 GitHub Webhook 事件（push/pull_request），自动触发检测。

**请求头：** `X-Hub-Signature-256` (HMAC 签名验证)

### GET /webhook/github/config

获取 Webhook 配置信息。

---

## 检测历史

### GET /history

列出检测历史记录，可选 `?limit=20&offset=0` 分页。

### GET /history/trend/{target_project}

获取项目检测趋势（相似度随时间变化）。

---

## 系统运维

### GET /health

系统健康检查（含 DB/GitHub API/磁盘/断路器状态）。

**响应体：**

```json
{
  "status": "ok",
  "version": "2.0.0",
  "checks": {
    "database": "ok",
    "github_api": "ok",
    "disk_space_mb": 2048,
    "circuit_breakers": "all_closed"
  }
}
```

### GET /circuit-breakers

断路器和隔离仓状态详情。

### GET /metrics

Prometheus 指标端点（`text/plain; version=0.0.4`）。

### GET /migrations

数据库迁移状态。

### GET /config/reload

配置热重载状态（上次重载时间、监听文件列表）。

### POST /config/reload

手动触发配置热重载。

### POST /search

搜索 GitHub 仓库。

**请求体：**

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| query | string | 是 | - | 搜索关键词 |
| language | string | 否 | null | 语言过滤 |
| sort | string | 否 | "stars" | 排序方式: stars/forks/updated |
| max_results | int | 否 | 20 | 最大结果数 |

**请求头：** `X-GitHub-Token` (可选，提升速率限制)

---

## 仪表盘

### GET /dashboard

交互式 Web 仪表盘页面（返回 HTML）。

---

## WebSocket

### WS /ws/dashboard

仪表盘全局事件流（任务创建/完成/失败等）。

### WS /ws/tasks/{task_id}/progress

任务进度实时推送（进度百分比、当前步骤、预估剩余时间）。

---

## 安全头

所有响应自动附加：

| 头 | 值 |
|----|-----|
| X-Content-Type-Options | nosniff |
| X-Frame-Options | DENY |
| X-XSS-Protection | 1; mode=block |
| Cache-Control | no-store |
| Referrer-Policy | no-referrer |

## 错误响应

```json
{"detail": "error description", "code": "MMxxx"}
```

| 状态码 | 场景 |
|--------|------|
| 400 | 参数错误 / 非法路径 / 输入消毒失败 |
| 401 | API Key 认证失败 / JWT 过期 |
| 403 | 权限不足 / IP 被过滤 |
| 404 | 资源不存在 |
| 429 | GitHub API 限流 / 自适应限流触发 |
| 500 | 内部错误 |
| 503 | 断路器断开 / 服务降级 |
