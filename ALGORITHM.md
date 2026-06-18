# ModuleMirror 算法文档

## 双重指纹检测策略

ModuleMirror 采用 **Winnowing 指纹 + AST 结构指纹** 双重检测策略：

1. **Winnowing**：快速筛选候选匹配（O(n) 建索引 + O(1) 查询）
2. **AST 深度验证**：对高相似度结果进行节点级比对，消除哈希碰撞

---

## 一、Winnowing 指纹算法

### 概述

Winnowing 是一种文档指纹算法，源自 Schleimer, Wilkerson, Aiken (2003) 的论文 *Winnowing: Local Algorithms for Document Fingerprinting*。它从文档的所有 k-gram 子串哈希中，选取满足保证条件的子集作为文档指纹。

### 流程

```
源代码
  │
  ▼ CodeTokenizer.tokenize()
  │  1. 移除空白字符（空格/换行/制表符）
  │  2. 标准化运算符（==→EQ, !=→NE, <=→LE, >=→GE, &&→AND, ||→OR）
  │  3. 按单字符切分 token 流
  │
  ▼ RollingHash
  │  确定性多项式滚动哈希：H = c₀·BASE^(k-1) + c₁·BASE^(k-2) + ... + c_{k-1}
  │  BASE = 257, MOD = 2^61 - 1 (梅森素数)
  │  不使用 Python hash()（随机化问题）
  │
  ▼ k-gram 哈希序列
  │  窗口大小 k = 16（可配置）
  │
  ▼ Winnowing 选取
  │  窗口大小 w = 8（可配置）
  │  在每个 w 窗口内选取最小哈希值
  │  保证：任意 ≥ t = k+w-1 的匹配子串至少产生一个指纹
  │
  ▼ 指纹集合 {(position, hash_value)}
```

### 关键参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| k (k-gram) | 16 | 子串长度，影响粒度 |
| w (window) | 8 | 窗口大小，影响密度 |
| t (guarantee) | k+w-1 = 23 | 最小匹配长度保证 |
| BASE | 257 | 滚动哈希基数 |
| MOD | 2^61-1 | 滚动哈希模数 |

### 免疫性

| 变换 | 免疫 |
|------|------|
| 变量重命名 | ✅ 100%（token 化不影响指纹） |
| 格式变化 | ✅ 100%（空白移除） |
| 注释增删 | ✅ 100%（注释不参与 tokenize） |
| 语句重排 | ❌（指纹位置变化） |

---

## 二、AST 结构指纹

### 概述

利用 tree-sitter 解析源代码为 AST，提取结构特征作为二级指纹。与 Winnowing 互补，对语义等价但文本不同的代码有更好的识别能力。

### 流程

```
源代码
  │
  ▼ tree-sitter 解析
  │  获取完整 AST（支持 Python/JS/Java/TS/Go/Rust/C/C++）
  │
  ▼ 模块提取
  │  按粒度提取：function / class / file
  │
  ▼ 结构特征提取
  │  - 节点类型序列：[function_definition, parameters, identifier, ...]
  │  - 子树深度分布
  │  - 节点度分布
  │
  ▼ 结构指纹
     归一化特征向量，用于 Jaccard 计算
```

### AST 深度验证

当 Jaccard 相似度超过 **60%**（AST_VERIFY_THRESHOLD）时，触发 AST 深度比对：

```
AST_A ←→ AST_B
  │
  ▼ 递归节点对齐
  │  节点类型匹配 → 深入子节点
  │  节点类型不匹配 → 容差范围内容忍（VERIFY_TOLERANCE = 0.1）
  │
  ▼ 相似度调整
     基于 AST 对齐结果调整最终相似度
```

---

## 三、相似度计算

### Jaccard 相似度

```
J(A, B) = |A ∩ B| / |A ∪ B|
```

**特殊情况：** J(∅, ∅) = 1.0（数学定义，两个空集完全相似）

### 加权组合

```
similarity = WINNOWING_WEIGHT × J_winnowing + AST_WEIGHT × J_ast
```

| 权重 | 值 |
|------|-----|
| WINNOWING_WEIGHT | 0.6 |
| AST_WEIGHT | 0.4 |

### 倒排索引加速

```
构建：fingerprint → [module_id_1, module_id_2, ...]
查询：目标指纹集合 → 候选模块 → overlap 计数
过滤：MIN_OVERLAP_THRESHOLD = 1（至少 1 个共同指纹）
计算：Jaccard = overlap / (|A| + |B| - overlap)
```

避免 O(n²) 全量比对，复杂度降至 O(|目标指纹集| × 平均倒排列表长度)。

---

## 四、抄袭溯源

### 流程

```
目标项目指纹
  │
  ▼ 倒排索引候选筛选
  │  从指纹库中查找与目标模块有共同指纹的候选
  │  限制：MAX_CANDIDATES_PER_MODULE = 50
  │
  ▼ AST 深度验证
  │  对每个候选对进行节点级比对
  │
  ▼ 置信度评分
  │  confidence = RATIO_WEIGHT × ratio + SIMILARITY_WEIGHT × similarity
  │             + COUNT_WEIGHT × log(1 + count) / COUNT_LOG_SCALE
  │
  ▼ 结果排序
     按置信度降序返回 PlagiarismResult 列表
```

### 置信度权重

| 参数 | 值 | 说明 |
|------|-----|------|
| RATIO_WEIGHT | 0.3 | 共同指纹比例权重 |
| SIMILARITY_WEIGHT | 0.5 | 相似度权重 |
| COUNT_WEIGHT | 0.2 | 绝对匹配数权重 |
| COUNT_LOG_SCALE | 10.0 | 对数缩放因子 |

---

## 五、NCD 归一化压缩距离

```
NCD(x, y) = (C(xy) - min(C(x), C(y))) / max(C(x), C(y))
similarity = 1 - NCD(x, y)
```

其中 C(x) 为 zlib 压缩后字节数。内存限制 MAX_TOTAL_BYTES = 50MB。

---

## 性能基线

| 算法 | 规模 | mean | p95 |
|------|------|------|-----|
| CodeTokenizer.tokenize | 11KB | 2.85ms | 4.58ms |
| Winnowing.generate_fingerprints | 100 函数 | 21.95ms | 29.43ms |
| InvertedIndex.build | 500 模块 | 2.68ms | 11.85ms |
| InvertedIndex.get_candidates | 30 指纹 | 0.01ms | 0.02ms |

## 参考文献

1. Schleimer, S., Wilkerson, D. S., & Aiken, A. (2003). *Winnowing: Local Algorithms for Document Fingerprinting*. SIGMOD.
2. Li, Y., et al. (2004). *Charikar's SimHash for Approximate Nearest Neighbor Search*.
3. Broder, A. (1997). *On the Resemblance and Containment of Documents*. SEQUENCES.
