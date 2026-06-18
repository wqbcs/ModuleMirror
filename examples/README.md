# ModuleMirror 示例项目库

本目录包含不同语言和规模的示例项目，用于演示 ModuleMirror 的代码相似度检测功能。

## 项目列表

| 示例 | 语言 | 规模 | 用途 |
|------|------|------|------|
| python-small | Python | 小型 (2模块) | 基础检测：自我审视 + 抄袭溯源 |
| java-medium | Java | 中型 (1类) | 跨语言检测：Java ↔ Python 相似度 |
| js-frontend | JavaScript | 前端 (1类) | 前端代码检测：JS ↔ Java ↔ Python |

## 快速开始

### Python 自我审视
```bash
# 检测项目内部代码复用
gh-sim detect --source examples/python-small/src --mode self-review

# 检测两个模块间的抄袭
gh-sim detect \
  --source examples/python-small/src/processor.py \
  --target examples/python-small/src/handler.py
```

### 跨语言检测
```bash
# 检测 Java 与 Python 的代码相似度
gh-sim detect \
  --source examples/java-medium/src \
  --target examples/python-small/src
```

### 使用 Web API
```bash
# 启动 API 服务
gh-sim serve --port 8000

# 提交检测请求
curl -X POST http://localhost:8000/detect \
  -H "Content-Type: application/json" \
  -d '{"source": "examples/python-small/src", "mode": "self-review"}'
```

## 预期结果

- `processor.py` ↔ `handler.py`: 高相似度 (~85%)，因为 `compute_hash` / `calculate_checksum` 和 `DataHandler` / `DataProcessor` 结构几乎相同
- `DataService.java` ↔ `processor.py`: 中等相似度 (~60%)，算法逻辑相同但语言不同
- `service.js` ↔ `DataService.java`: 中等相似度 (~55%)，ES6 class 与 Java class 结构相似
