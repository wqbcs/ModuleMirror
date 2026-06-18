# ModuleMirror 快速上手教程

## 5 分钟快速开始

### 安装

```bash
pip install -e .
pip install tree-sitter tree-sitter-python tree-sitter-javascript tree-sitter-java
```

### 第一次检测

检测两个 Python 项目的相似度：

```bash
gh-sim detect \
  -t ./your-project \
  -c https://github.com/some/similar-project \
  -l python \
  --threshold 70
```

结果会生成 HTML 报告到 `./report/` 目录。

### 建立指纹库

先将已知项目加入指纹库：

```bash
# 初始化
gh-sim db init

# 添加多个项目
gh-sim db add -p https://github.com/org/project-a
gh-sim db add -p https://github.com/org/project-b

# 查看统计
gh-sim db stats
```

### 抄袭溯源

检测目标项目是否抄袭了指纹库中的代码：

```bash
gh-sim plagiarism -t ./suspect-project --db ./fingerprint_db.sqlite
```

## 进阶用法

### 断点续传

大规模检测中断后恢复：

```bash
gh-sim detect -t ./big-project -c candidate1,candidate2 \
  --checkpoint checkpoint.json
```

### 自定义配置

生成配置文件并修改参数：

```bash
gh-sim config generate -o gh-sim.yaml
# 编辑 gh-sim.yaml
gh-sim detect -t ./project -c ./candidate --config gh-sim.yaml
```

### Web API

启动 API 服务：

```bash
# 设置 GitHub Token
export GITHUB_TOKEN=ghp_xxx

# 启动服务
uvicorn gh_similarity_detector.api.app:app --port 8000

# 调用 API
curl -X POST http://localhost:8000/detect \
  -H "Content-Type: application/json" \
  -d '{"target": "./project", "candidates": ["https://github.com/other/repo"]}'
```

### NCD 快速对比

项目整体相似度快速判断：

```bash
gh-sim ncd -s ./project-a -t ./project-b
```
