# ModuleMirror 场景化操作指南

## 场景1：发现项目内重复代码

**目标**：检测项目内部是否存在可合并的重复模块

```bash
# 将项目自身作为目标和候选
gh-sim detect -t ./my-project -c ./my-project -l python --threshold 80
```

## 场景2：开源项目抄袭检测

**目标**：检测某 fork 是否直接复制了原项目代码

```bash
# 建立原项目指纹库
gh-sim db init
gh-sim db add -p https://github.com/original/project

# 检测 fork 项目
gh-sim plagiarism -t https://github.com/fork/project --db ./fingerprint_db.sqlite
```

## 场景3：多语言项目检测

**目标**：同时检测 Python + JavaScript 代码

```bash
gh-sim detect -t ./fullstack-project \
  -c https://github.com/other/fullstack \
  -l python -l javascript \
  --threshold 70
```

## 场景4：批量对比多个候选项目

**目标**：一个目标项目对比多个候选

```bash
gh-sim detect -t ./my-project \
  -c https://github.com/cand1/repo \
     https://github.com/cand2/repo \
     https://github.com/cand3/repo \
  --checkpoint cp.json
```

## 场景5：CI/CD 集成

**目标**：在 PR 中自动检测代码相似度

```bash
# 在 CI 脚本中
gh-sim detect \
  -t ./changed-files \
  -c ./main-branch-code \
  --threshold 90 \
  --format json \
  --output ./similarity-report.json

# 检查是否有高相似度匹配
python -c "
import json, sys
with open('./similarity-report.json') as f:
    data = json.load(f)
high = [r for r in data if r.get('similarity', 0) > 90]
if high:
    print(f'WARNING: {len(high)} high-similarity matches found')
    sys.exit(1)
"
```

## 场景6：指纹库跨实例迁移

**目标**：将指纹库从开发环境导出到生产环境

```bash
# 开发环境
gh-sim db list  # 查看项目列表
cp ./fingerprint_db.sqlite ./export/

# 生产环境
cp ./export/fingerprint_db.sqlite ./
gh-sim db stats  # 验证
```

## 场景7：配置不同检测策略

**严格模式**（高精度，少量匹配）：
```bash
gh-sim detect -t ./project -c ./candidate \
  -l python --threshold 85 --granularity function
```

**宽松模式**（低精度，大量匹配）：
```bash
gh-sim detect -t ./project -c ./candidate \
  -l python --threshold 50 --granularity file
```
