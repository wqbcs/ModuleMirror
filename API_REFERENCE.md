# ModuleMirror API 参考

Base URL: `http://localhost:8000`

## 认证

若设置了环境变量 `MODULEMIRROR_API_KEY`，所有请求需携带 `X-API-Key` 请求头：

```
X-API-Key: your-api-key
```

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

## NCD 压缩距离

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

## 指纹库管理

### GET /db/stats

获取指纹库统计信息（项目数、模块数、指纹数等）。

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

## 搜索

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

## 报告

### GET /reports

列出所有检测报告，可选 `?report_dir=./report` 指定目录。

### GET /reports/{report_id}

获取报告内容，支持 JSON/HTML/Markdown 格式。

### GET /reports/{report_id}/summary

获取报告摘要统计。

## 健康

### GET /health

健康检查端点。

```json
{"status": "ok", "version": "0.1.0"}
```

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
{"detail": "error description"}
```

| 状态码 | 场景 |
|--------|------|
| 400 | 参数错误 / 非法路径 |
| 401 | API Key 认证失败 |
| 404 | 资源不存在 |
| 429 | GitHub API 限流 |
| 500 | 内部错误 |
