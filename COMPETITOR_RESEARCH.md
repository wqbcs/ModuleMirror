# ModuleMirror 竞品调研报告

## 调研范围

GitHub/Gitee/AtomGit 上的代码相似度检测、抄袭检测相关开源项目。

## 方法论洞察（19轮调研成果）

### Martin Fowler 微服务架构
- **Smart endpoints, dumb pipes**：ModuleMirror 的 API 层应保持薄，逻辑在 core 层
- **Design for failure**：需引入 Circuit Breaker（R11），GitHub API 调用可能失败
- **Evolutionary Design**：先保持单体，按需拆分服务边界
- **Tolerant Reader**：API 响应解析应容错（R12），忽略未知字段

### 12-Factor App
- 已合规 9/12，剩余 F04(PostgreSQL替换) + F06(会话外置) + F08(ProcessPool)

### OWASP Top 10 2025
- 新增 **A10 Server-Side Request Forgery (SSRF)**：GitHub URL 需白名单校验（S11）
- 供应链安全：SBOM 生成 + 签名验证（S12）

### DDD Bounded Context
- 检测、存储、报告三个上下文应显式隔离（R13）

## 竞品对比

### 1. MOSS (Measure Of Software Similarity)

- **仓库**：stanford-cs193/moss
- **语言**：Python/Java/C/C++/Scheme/ML
- **算法**：Winnowing 变种（斯坦福原创）
- **特点**：学术标杆，服务端模式，需提交到服务器
- **局限**：不开源核心算法，仅 API 调用；不支持 AST 验证
- **ModuleMirror 优势**：本地化、双重指纹、AST 深度验证、多语言 tree-sitter

### 2. JPlag

- **仓库**：jplag/JPlag
- **语言**：Java/Python/C/C++/Scheme
- **算法**：Token 串匹配 + 最长公共子序列
- **特点**：学术抄袭检测，精确度高
- **局限**：仅学术场景；无 Web API；无指纹库持久化
- **ModuleMirror 优势**：自我审视 + 抄袭溯源双模式；指纹库增量更新；Web API

### 3. jscpd (Copy/Paste Detector)

- **仓库**：kucherenko/jscpd
- **语言**：100+ 语言（基于 AST）
- **算法**：Rabin-Karp 指纹 + 项目内重复检测
- **特点**：轻量级，CI 集成，项目内重复代码检测
- **局限**：仅检测项目内重复，不支持跨项目对比
- **ModuleMirror 已集成**：jscpd_adapter.py 作为补充引擎

### 4. CodeDupliceer / CPD (PMD Copy-Paste Detector)

- **仓库**：pmd/pmd
- **语言**：Java/C/C++/Fortran/Go
- **算法**：Token 串匹配
- **特点**：Java 生态标配，Maven 集成
- **局限**：Java 偏向，无 Web API，无跨项目

### 5. Simian (Similarity Analyzer)

- **仓库**：harikrishnan83/simian
- **语言**：多语言
- **算法**：行级相似度
- **特点**：商业工具，Ant/Maven 集成
- **局限**：闭源商业；行级粒度，不感知语法

### 6. 华为云 CodeArts Check

- **产品**：代码检查服务（基于知识库调研）
- **特点**：代码重复率检测、圈复杂度、多语言、CI/CD 集成
- **局限**：云服务，不支持本地化；企业级，非开源
- **ModuleMirror 定位差异**：开源 + 本地化 + 跨项目对比（CodeArts Check 侧重项目内质量）

## 差异化分析

| 维度 | ModuleMirror | 竞品 |
|------|-------------|------|
| 双重指纹 | ✅ Winnowing + AST | ❌ 单一算法 |
| AST 深度验证 | ✅ 节点级比对 | ❌ 无 |
| 双模式 | ✅ 自我审视 + 抄袭溯源 | ❌ 仅抄袭检测或仅重复检测 |
| 指纹库持久化 | ✅ SQLite 增量更新 | ❌ 每次重新计算 |
| 跨项目对比 | ✅ 核心能力 | ❌ 仅项目内 |
| 多语言 | ✅ tree-sitter 8 语言 | 🔄 2-5 语言 |
| Web API | ✅ FastAPI | ❌ CLI only |
| 断点续传 | ✅ Checkpoint | ❌ 无 |
| NCD 快速对比 | ✅ 项目级相似度 | ❌ 无 |
| 开源 | ✅ MIT | 🔄 部分 |

## 待借鉴特性

1. **JPlag**：Token 串匹配精确度优化思路
2. **jscpd**：CI 集成模式（已部分集成）
3. **CodeArts Check**：代码重复率指标 + 圈复杂度关联
4. **MOSS**：学术级精确度标杆（Winnowing 参数调优参考）

## 调研结论

ModuleMirror 在**双重指纹 + 双模式 + 指纹库持久化**三个维度有明确差异化优势。核心差距在：
1. 测试覆盖率（60%→80% 目标）
2. Web UI 仪表盘（竞品大多无，但用户期望高）
3. 插件化架构（SimHash/MinHash LSH 待实现）
