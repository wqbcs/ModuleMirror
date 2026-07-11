# ModuleMirror 项目长期记忆

## 项目定位
GitHub 代码相似度/抄袭检测工具（Python，六边形架构：`core` 端口 / `infrastructure` 适配器）。CLI 入口 `gh-sim`，Web API 基于 FastAPI。

## 成熟度路线图现状（截至 2026-07-09）
- L1 可用 ✅
- L2 可靠 🔄 CI 强制 80% 覆盖率门禁已就位（当前全量约 60%，持续补齐中）
- L3 可扩展 ✅ 插件化（pluggy）+ API `/v1` 版本化均已完成
- L4 可观测 🔄 Metrics/Tracing 已接入检测与 API 路径；Logs 依赖可选 extra `structured-logging`
- L5 可贡献 ⬜

## 关键技术决策（避免重复造轮子）
- **插件架构用 pluggy**（pytest/tox 同款），不自行发明插件机制；第三方算法通过 `pyproject` 入口点组 `moduler_mirror.algorithms` 注册。
- **SimHash** 已实现（Charikar 64位，见 `infrastructure/plugins/builtin.py`）；MinHash LSH 此前已实现（`core/similarity/lsh_index.py` + Rust 加速）。
- 相似度算法插件端口：`core/plugin.py::AlgorithmPlugin`；核心通过 `SimilarityCalculator.similarity_with_algorithm(name, fp_a, fp_b)` 调用。
- 可选依赖（otel/pluggy/structlog 等）一律加 import 守卫 + 空操作降级，避免未安装时拖垮启动。

## 测试约定
- 测试在仓库根 `tests/`，命名 `test_*.py`。
- 本地验证用隔离 venv：`C:/Users/gwc/.workbuddy/binaries/python/envs/default`。
- API 测试用 `fastapi.testclient.TestClient`；DB 测试用临时 SQLite（`FingerprintDB(str(tmp_path/...))` + `db.close()`）。

## Git 工作流
- 功能在 `feat/*` 分支开发并提交，验证后合并 `main`（本地，未推送远端）。
