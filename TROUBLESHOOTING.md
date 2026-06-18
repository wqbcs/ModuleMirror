# ModuleMirror 故障排查指南

## 常见问题

### 1. tree-sitter 解析失败

**症状**：`Language not found` 或 `QueryError`

**原因**：tree-sitter 语言包未安装或版本不匹配

**解决**：
```bash
pip install tree-sitter==0.25.0 tree-sitter-python==0.23.0
# 按需安装其他语言
pip install tree-sitter-java tree-sitter-javascript tree-sitter-typescript
```

### 2. GitHub API 限流 (429)

**症状**：`RateLimitError: API rate limit exceeded`

**解决**：
- 设置 `GITHUB_TOKEN` 环境变量（提升至 5000/h）
- 使用 `--checkpoint` 断点续传，分批检测
- 等待 reset 时间后重试

### 3. 内存不足 (OOM)

**症状**：`MemoryError` 或进程被 kill

**解决**：
- 减小并发度 `--parallelism 1`
- 使用流式检测（大项目分批处理）
- NCD 检查确保总文件 <50MB

### 4. SQLite 数据库锁定

**症状**：`database is locked`

**解决**：
- 确保单进程访问数据库
- 启用 WAL 模式（计划中）
- 增大 busy_timeout

### 5. 指纹库为空

**症状**：抄袭溯源返回空结果

**解决**：
```bash
gh-sim db init
gh-sim db add -p https://github.com/some/project
```

### 6. 检测结果为空

**症状**：检测完成但无匹配

**排查**：
- 检查 `--threshold` 是否过高（默认 70）
- 检查 `--language` 是否匹配项目语言
- 检查 `--granularity` 是否合适（function > class > file）

### 7. API 认证失败

**症状**：`401 Unauthorized`

**解决**：
- 检查 `MODULEMIRROR_API_KEY` 环境变量
- 请求头添加 `X-API-Key: your-key`

### 8. Docker 容器启动失败

**症状**：容器立即退出

**排查**：
```bash
docker logs modulemirror
# 检查端口冲突
docker run -p 8001:8000 modulemirror:latest
```

### 9. Windows 路径问题

**症状**：路径相关错误

**解决**：
- 使用正斜杠路径：`./my-project` 而非 `.\\my-project`
- 或使用绝对路径
