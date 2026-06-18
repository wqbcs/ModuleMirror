# ModuleMirror 性能调优指南

## 性能基线

| 算法 | 规模 | mean | p95 |
|------|------|------|-----|
| CodeTokenizer.tokenize | 11KB | 2.85ms | 4.58ms |
| Winnowing.generate_fingerprints | 100 函数 | 21.95ms | 29.43ms |
| InvertedIndex.build | 500 模块 | 2.68ms | 11.85ms |
| InvertedIndex.get_candidates | 30 指纹 | 0.01ms | 0.02ms |

## 调优参数

### 并发度

```bash
# 默认 4 线程
gh-sim detect -t ./project -c cand1,cand2 --parallelism 8

# CPU 密集型任务建议 = CPU 核数
# IO 密集型任务建议 = CPU 核数 × 2
```

### 缓存

默认启用 SHA256 内容哈希缓存：

```bash
# 禁用缓存（强制重新计算）
gh-sim detect -t ./project -c ./candidate --no-cache

# 指定缓存目录
gh-sim detect -t ./project -c ./candidate --cache-dir /tmp/cache
```

### 指纹粒度

| 粒度 | 速度 | 精度 | 适用场景 |
|------|------|------|----------|
| file | 快 | 低 | 快速筛选 |
| function | 中 | 高 | **默认推荐** |
| class | 中 | 中 | OOP 项目 |

### 检测阈值

| 阈值 | 匹配数 | 适用 |
|------|--------|------|
| 50 | 多 | 宽松筛查 |
| 70（默认） | 适中 | 常规检测 |
| 85 | 少 | 严格确认 |
| 95 | 极少 | 几乎相同的代码 |

## 大规模检测优化

### 1. 断点续传

```bash
gh-sim detect -t ./big -c cand1,cand2,...,cand50 \
  --checkpoint progress.json
# 中断后重新运行同命令即可恢复
```

### 2. 分批检测

```bash
# 批次1
gh-sim detect -t ./project -c cand1,cand2,...,cand10
# 批次2
gh-sim detect -t ./project -c cand11,cand12,...,cand20
```

### 3. 指纹库预构建

```bash
# 预先将候选项目加入指纹库
for repo in cand1 cand2 cand3; do
  gh-sim db add -p "https://github.com/org/$repo"
done

# 抄袭溯源直接查库，跳过指纹计算
gh-sim plagiarism -t ./target --db ./fingerprint_db.sqlite
```

## 性能瓶颈排查

```bash
# 运行性能基线
python benchmark.py

# 检查指纹库大小
gh-sim db stats

# 检查缓存命中率
ls -la .cache/
```

## 内存优化

- NCD 总文件限制 50MB（`MAX_TOTAL_BYTES`）
- 单文件限制 1MB（`MAX_FILE_SIZE`）
- 大项目建议使用流式检测
