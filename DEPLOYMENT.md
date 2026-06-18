# ModuleMirror 部署指南

## 本地运行

### 安装

```bash
pip install -e .
```

### CLI 使用

```bash
gh-sim detect -t ./my-project -c https://github.com/other/project
gh-sim plagiarism -t ./suspect-project --db ./fingerprint_db.sqlite
```

### Web API

```bash
uvicorn gh_similarity_detector.api.app:app --host 0.0.0.0 --port 8000
```

## Docker 部署

### 构建

```bash
docker build -t modulemirror:latest .
```

### 运行

```bash
docker run -d \
  --name modulemirror \
  -p 8000:8000 \
  -e GITHUB_TOKEN=ghp_xxx \
  -e MODULEMIRROR_API_KEY=your-key \
  -v ./data:/app/data \
  modulemirror:latest
```

### Docker Compose

```bash
docker compose up -d
```

包含服务：
- **api**: ModuleMirror API 服务（端口 8000）
- **prometheus**: 指标采集（端口 9090，可选）

## 环境变量

| 变量 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| GITHUB_TOKEN | 否 | - | GitHub API Token（提升速率限制至 5000/h） |
| MODULEMIRROR_API_KEY | 否 | - | API 认证密钥（设置后强制认证） |
| MODULEMIRROR_CORS_ORIGINS | 否 | - | CORS 允许域名（逗号分隔） |
| MODULEMIRROR_DB_PATH | 否 | ./fingerprint_db.sqlite | 指纹库文件路径 |

## 生产部署建议

### 1. 反向代理（Nginx）

```nginx
server {
    listen 80;
    server_name modulemirror.example.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 2. 进程管理（Systemd）

```ini
[Unit]
Description=ModuleMirror API
After=network.target

[Service]
Type=simple
User=modulemirror
WorkingDirectory=/opt/modulemirror
ExecStart=/opt/modulemirror/venv/bin/uvicorn gh_similarity_detector.api.app:app --host 0.0.0.0 --port 8000 --workers 4
Restart=on-failure
RestartSec=5
EnvironmentFile=/opt/modulemirror/.env

[Install]
WantedBy=multi-user.target
```

### 3. 资源规划

| 规模 | CPU | 内存 | 磁盘 |
|------|-----|------|------|
| 小型（<100 项目） | 2 核 | 2 GB | 10 GB |
| 中型（100-1000 项目） | 4 核 | 4 GB | 50 GB |
| 大型（>1000 项目） | 8 核 | 8 GB | 200 GB |

### 4. 安全检查清单

- [ ] 设置 MODULEMIRROR_API_KEY
- [ ] 设置 MODULEMIRROR_CORS_ORIGINS（非 *）
- [ ] 配置反向代理 HTTPS
- [ ] 限制 GITHUB_TOKEN 权限（仅 repo read）
- [ ] 定期备份指纹库 SQLite 文件
- [ ] 配置日志轮转

## 监控

### 健康检查

```bash
curl http://localhost:8000/health
```

### 指纹库监控

```bash
curl http://localhost:8000/db/stats
```
