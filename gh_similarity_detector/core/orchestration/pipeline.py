"""
检测流程编排器

编排完整的检测流程，支持自我审视和抄袭溯源两种模式。

Author: GitHub 项目代码相似度检测工具
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

from ...models.results import DetectionResult, PlagiarismResult
from ..project.fetcher import ProjectFetcher
from ..module.extractor import ModuleExtractor
from ..fingerprint.generator import FingerprintGenerator
from ..similarity.calculator import SimilarityCalculator
from ..report.generator import ReportGenerator
from ..plagiarism.detector import PlagiarismDetector
from .checkpoint import Checkpoint
from ...infrastructure.storage.fingerprint_db import FingerprintDB
from ...infrastructure.cache.fingerprint_cache import FingerprintCache
from ...infrastructure.github_client.client import GitHubClient
from ...config.config import DetectionConfig
from ...utils.logger import logger
from ...utils.audit import AuditLogger
from ...utils.idempotency import (
    IdempotencyGuard,
    DeterministicContext,
    compute_result_hash,
    compute_config_hash,
)
from ..similarity.cross_language_pipeline import (
    CrossLanguagePipeline,
    CrossLanguageConfig,
)
from ..similarity.sbp_filter import SBPFilter
from ..rules.engine import RuleEngine, RuleAction
from ..lineage import CloneLineageTracker, LineageNode
from ..quality_gate import (
    QualityGate,
    GateCondition,
    ConditionOperator,
    extract_detection_metrics,
    create_default_gate,
    create_strict_gate,
)
from ..similarity.semantic_diff import SemanticDiffer
from ..similarity.polars_df import SimilarityDataFrame
from ..comparison.batch_detector import BatchDetector, BatchTask
from ..comparison.multi_repo import MultiRepositoryComparator
from ..comparison.result_comparator import ResultComparator


class DetectionPipeline:
    """检测流程编排器

    支持两种检测模式：
    1. 自我审视模式（detect）：检测目标项目与候选项目的相似模块
    2. 抄袭溯源模式（plagiarism）：检测目标项目是否抄袭了指纹库中的代码
    """

    def __init__(self, config: DetectionConfig, db_path: Optional[str] = None):
        self.config = config
        self.project_fetcher = ProjectFetcher(config)
        self.module_extractor = ModuleExtractor(config)

        cache = None
        if config.enable_cache:
            cache = FingerprintCache(str(config.cache_dir))

        self.fingerprint_generator = FingerprintGenerator(config, cache=cache)

        self.fingerprint_db: Optional[FingerprintDB] = None
        if db_path:
            self.fingerprint_db = FingerprintDB(db_path)

        cache_db = self.fingerprint_db if config.enable_cache else None
        self.similarity_calculator = SimilarityCalculator(config, similarity_cache_db=cache_db)
        self.report_generator = ReportGenerator(config)

        self.audit_logger = AuditLogger()

        self._idempotency_guard = IdempotencyGuard() if config.enable_idempotency_check else None
        self._deterministic_ctx = DeterministicContext(
            hash_seed=config.deterministic_seed,
            parallelism=1 if config.enable_idempotency_check else config.parallelism,
        )
        self._config_hash = compute_config_hash(config)

        self._cross_language_pipeline: Optional[CrossLanguagePipeline] = None
        if getattr(config, "enable_cross_language", False):
            cl_config = CrossLanguageConfig(
                ir_threshold=getattr(config, "cross_language_ir_threshold", 0.5) / 100.0,
                embedding_min_similarity=getattr(config, "cross_language_emb_threshold", 30.0) / 100.0,
            )
            self._cross_language_pipeline = CrossLanguagePipeline(cl_config)

        self._sbp_filter = SBPFilter(
            similarity_threshold=float(config.similarity_threshold),
        )
        self._rule_engine = RuleEngine()
        self._lineage_tracker = CloneLineageTracker()

    def detect(
        self,
        target_source: str,
        candidate_sources: List[str],
        progress_callback: Optional[Callable[[float], None]] = None,
        update_db: bool = False,
        checkpoint_path: Optional[str] = None,
    ) -> List[DetectionResult]:
        """执行自我审视检测

        Args:
            target_source: 目标项目来源
            candidate_sources: 候选项目来源列表
            progress_callback: 进度回调函数
            update_db: 是否将结果更新到指纹库

        Returns:
            检测结果列表
        """
        start_time = time.time()
        results: List[DetectionResult] = []

        try:
            if progress_callback:
                progress_callback(0.0)

            checkpoint = None
            if checkpoint_path:
                checkpoint = Checkpoint(checkpoint_path)
                if checkpoint.load():
                    logger.info(
                        f"从检查点恢复，已完成 {len(checkpoint.completed_candidates)} 个候选项目"
                    )
                else:
                    checkpoint.target_source = target_source
                    checkpoint.candidate_sources = candidate_sources

            logger.info(f"开始检测: {target_source}")

            target_project = self.project_fetcher.fetch_project(target_source)
            if target_project is None:
                logger.error(f"无法获取目标项目: {target_source}")
                return results

            if progress_callback:
                progress_callback(0.1)

            target_modules = self.module_extractor.extract_all_modules(target_project)
            logger.info(f"目标项目模块数: {sum(len(m) for m in target_modules.values())}")

            if progress_callback:
                progress_callback(0.2)

            target_fingerprints = self.fingerprint_generator.generate_fingerprints_batch(
                target_modules
            )

            if update_db and self.fingerprint_db:
                self.fingerprint_db.add_project(target_project, target_modules, target_fingerprints)

            if progress_callback:
                progress_callback(0.3)

            failed_candidates = []

            if checkpoint:
                remaining = checkpoint.get_pending_candidates()
                if remaining != candidate_sources:
                    logger.info(
                        f"检查点恢复: 跳过 {len(candidate_sources) - len(remaining)} 个已完成候选"
                    )
                    candidate_sources = remaining

            def _process_candidate(candidate_source: str) -> tuple[str, Optional[DetectionResult], Optional[str]]:
                try:
                    candidate_project = self.project_fetcher.fetch_project(candidate_source)
                    if candidate_project is None:
                        return (candidate_source, None, "无法获取项目")

                    candidate_modules = self.module_extractor.extract_all_modules(candidate_project)
                    candidate_fingerprints = self.fingerprint_generator.generate_fingerprints_batch(
                        candidate_modules
                    )

                    if update_db and self.fingerprint_db:
                        self.fingerprint_db.add_project(
                            candidate_project, candidate_modules, candidate_fingerprints
                        )

                    similarity_results = self.similarity_calculator.calculate_similarities(
                        target_modules,
                        candidate_modules,
                        target_fingerprints,
                        candidate_fingerprints,
                    )

                    statistics = self.similarity_calculator.calculate_statistics(similarity_results)

                    detection_result = DetectionResult(
                        source_project=target_project.name,
                        target_project=candidate_project.name,
                        matches=similarity_results,
                        statistics=statistics,
                    )
                    return (candidate_source, detection_result, None)
                except Exception as e:
                    return (candidate_source, None, str(e))

            with ThreadPoolExecutor(max_workers=self.config.parallelism) as executor:
                future_to_source = {
                    executor.submit(_process_candidate, cs): cs for cs in candidate_sources
                }
                completed = 0
                for future in as_completed(future_to_source):
                    cs = future_to_source[future]
                    try:
                        source, result, error = future.result()
                        if result:
                            results.append(result)
                            if checkpoint:
                                checkpoint.mark_completed(source)
                                checkpoint.add_result(
                                    result.source_project,
                                    result.target_project,
                                    len(result.matches),
                                    result.statistics,
                                )
                                checkpoint.save()
                        elif error:
                            logger.error(f"候选项目检测失败 [{source}]: {error}")
                            failed_candidates.append((source, error))
                            if checkpoint:
                                checkpoint.mark_failed(source, error)
                                checkpoint.save()
                    except Exception as e:
                        logger.error(f"候选项目检测异常 [{cs}]: {e}")
                        failed_candidates.append((cs, str(e)))

                    completed += 1
                    progress = 0.3 + 0.6 * completed / len(candidate_sources)
                    if progress_callback:
                        progress_callback(progress)

            if failed_candidates:
                logger.warning(
                    f"{len(failed_candidates)}/{len(candidate_sources)} 个候选项目处理失败: "
                    f"{[s for s, _ in failed_candidates]}"
                )

            if progress_callback:
                progress_callback(0.9)

            report_path = self.report_generator.generate_report(results)

            if progress_callback:
                progress_callback(1.0)

            elapsed = time.time() - start_time
            logger.info(f"检测完成，耗时: {elapsed:.2f} 秒，报告: {report_path}")

            if self._idempotency_guard is not None:
                for r in results:
                    r_hash = compute_result_hash(
                        r.source_project,
                        r.target_project,
                        r.matches,
                        r.statistics,
                    )
                    ok = self._idempotency_guard.verify(
                        r.source_project,
                        [r.target_project],
                        self._config_hash,
                        r_hash,
                    )
                    if not ok:
                        logger.warning(f"幂等性违反: {r.source_project} vs {r.target_project}")

            total_matches = sum(len(r.matches) for r in results)
            self.audit_logger.log_detect(
                target_project=target_source,
                candidates=candidate_sources,
                match_count=total_matches,
                duration_ms=int(elapsed * 1000),
            )

        except Exception as e:
            logger.error(f"检测流程失败: {e}")
            raise

        finally:
            self.project_fetcher.cleanup()

        return results

    def plagiarism(
        self, target_source: str, progress_callback: Optional[Callable[[float], None]] = None
    ) -> List[PlagiarismResult]:
        """执行抄袭溯源检测

        Args:
            target_source: 目标项目来源
            progress_callback: 进度回调函数

        Returns:
            抄袭溯源结果列表
        """
        if self.fingerprint_db is None:
            logger.error("未配置指纹库，无法执行抄袭溯源检测")
            return []

        start_time = time.time()

        try:
            if progress_callback:
                progress_callback(0.0)

            logger.info(f"开始抄袭溯源检测: {target_source}")

            target_project = self.project_fetcher.fetch_project(target_source)
            if target_project is None:
                logger.error(f"无法获取目标项目: {target_source}")
                return []

            if progress_callback:
                progress_callback(0.2)

            target_modules = self.module_extractor.extract_all_modules(target_project)
            target_fingerprints = self.fingerprint_generator.generate_fingerprints_batch(
                target_modules
            )

            if progress_callback:
                progress_callback(0.4)

            detector = PlagiarismDetector(self.config, self.fingerprint_db)

            results = detector.detect(
                target_project.name, target_modules, target_fingerprints, target_project.local_path
            )

            if progress_callback:
                progress_callback(0.8)

            elapsed = time.time() - start_time
            logger.info(f"抄袭溯源检测完成，耗时: {elapsed:.2f} 秒")

            self.audit_logger.log_plagiarism(
                target_project=target_source,
                source_count=len(results),
                duration_ms=int(elapsed * 1000),
            )

            if progress_callback:
                progress_callback(1.0)

            return results

        except Exception as e:
            logger.error(f"抄袭溯源检测失败: {e}")
            raise

        finally:
            self.project_fetcher.cleanup()

    def add_to_db(
        self, project_source: str, progress_callback: Optional[Callable[[float], None]] = None
    ) -> bool:
        """将项目添加到指纹库

        Args:
            project_source: 项目来源
            progress_callback: 进度回调函数

        Returns:
            是否成功
        """
        if self.fingerprint_db is None:
            logger.error("未配置指纹库")
            return False

        if progress_callback:
            progress_callback(0.0)

        project = self.project_fetcher.fetch_project(project_source)
        if project is None:
            logger.error(f"无法获取项目: {project_source}")
            return False

        if progress_callback:
            progress_callback(0.3)

        modules = self.module_extractor.extract_all_modules(project)

        if progress_callback:
            progress_callback(0.6)

        fingerprints = self.fingerprint_generator.generate_fingerprints_batch(modules)

        if progress_callback:
            progress_callback(0.9)

        self.fingerprint_db.add_project(project, modules, fingerprints)

        self.project_fetcher.cleanup()

        if progress_callback:
            progress_callback(1.0)

        return True

    def update_db(
        self, project_url: str, progress_callback: Optional[Callable[[float], None]] = None
    ) -> bool:
        """增量更新指纹库中的项目

        检查项目是否有新提交，如有则重新提取指纹并更新。
        仅支持 GitHub URL 的项目。

        Args:
            project_url: 项目 GitHub URL
            progress_callback: 进度回调

        Returns:
            是否更新了
        """
        if self.fingerprint_db is None:
            logger.error("未配置指纹库")
            return False

        parsed = (
            GitHubClient.parse_github_url(project_url)
            if GitHubClient.is_github_url(project_url)
            else None
        )
        if not parsed:
            logger.warning("增量更新仅支持 GitHub URL 项目")
            return self.add_to_db(project_url, progress_callback)

        owner, repo = parsed
        project_name = f"{owner}/{repo}"

        existing = self.fingerprint_db.get_project(project_name)
        if not existing:
            logger.info(f"项目 {project_name} 不在指纹库中，执行首次添加")
            return self.add_to_db(project_url, progress_callback)

        from ...utils.asyncio_utils import get_event_loop

        loop = get_event_loop()

        repo_info = loop.run_until_complete(
            self.project_fetcher.github_client.get_repo_info(owner, repo)
        )
        if not repo_info:
            logger.warning(f"无法获取仓库信息: {project_name}")
            return False

        remote_updated = repo_info.get("pushed_at", "")
        local_updated = existing.get("updated_at", "")

        if remote_updated and local_updated and remote_updated <= local_updated:
            logger.info(f"项目 {project_name} 指纹已是最新（{local_updated}）")
            return False

        logger.info(f"项目 {project_name} 有新提交，更新指纹（{local_updated} → {remote_updated}）")
        self.fingerprint_db.delete_project(project_name)
        return self.add_to_db(project_url, progress_callback)

    def detect_cross_language(
        self,
        target_source: str,
        candidate_sources: List[str],
        progress_callback: Optional[Callable[[float], None]] = None,
    ) -> List[DetectionResult]:
        """执行跨语言检测

        当源项目和候选项目使用不同编程语言时，启用跨语言检测模式。
        融合IR结构指纹 + Embedding向量检索双通道。

        Args:
            target_source: 目标项目来源
            candidate_sources: 候选项目来源列表
            progress_callback: 进度回调

        Returns:
            跨语言检测结果列表
        """
        start_time = time.time()
        results: List[DetectionResult] = []

        try:
            if progress_callback:
                progress_callback(0.0)

            cl_pipeline = self._cross_language_pipeline or CrossLanguagePipeline()

            target_project = self.project_fetcher.fetch_project(target_source)
            if target_project is None:
                logger.error(f"无法获取目标项目: {target_source}")
                return results

            if progress_callback:
                progress_callback(0.1)

            target_modules = self.module_extractor.extract_all_modules(target_project)

            target_codes: Dict[str, tuple[str, str]] = {}
            for file_path, modules in target_modules.items():
                for m in modules:
                    if m.source_code:
                        lang = self._detect_language(m.file_path)
                        target_codes[m.id or m.name] = (m.source_code, lang)

            cl_pipeline.index_source_batch(target_codes)

            if progress_callback:
                progress_callback(0.3)

            for idx, candidate_source in enumerate(candidate_sources):
                try:
                    candidate_project = self.project_fetcher.fetch_project(candidate_source)
                    if candidate_project is None:
                        logger.warning(f"无法获取候选项目: {candidate_source}")
                        continue

                    candidate_modules = self.module_extractor.extract_all_modules(candidate_project)

                    candidate_codes: Dict[str, tuple[str, str]] = {}
                    for file_path, modules in candidate_modules.items():
                        for m in modules:
                            if m.source_code:
                                lang = self._detect_language(m.file_path)
                                candidate_codes[m.id or m.name] = (m.source_code, lang)

                    is_cross_language = self._is_cross_language(target_codes, candidate_codes)

                    if is_cross_language:
                        cl_pipeline.index_target_batch(candidate_codes)

                        cl_results = cl_pipeline.detect_cross_language(
                            min_similarity=self.config.similarity_threshold,
                        )

                        statistics = {
                            "avg_similarity": sum(r.similarity for r in cl_results) / len(cl_results)
                            if cl_results
                            else 0,
                            "max_similarity": max((r.similarity for r in cl_results), default=0),
                            "cross_language": True,
                            "detection_mode": "cross_language",
                        }

                        result = DetectionResult(
                            source_project=target_project.name,
                            target_project=candidate_project.name,
                            matches=cl_results,
                            statistics=statistics,
                        )
                        results.append(result)
                    else:
                        similarity_results = self.similarity_calculator.calculate_similarities(
                            target_modules,
                            candidate_modules,
                            self.fingerprint_generator.generate_fingerprints_batch(target_modules),
                            self.fingerprint_generator.generate_fingerprints_batch(candidate_modules),
                        )
                        statistics = self.similarity_calculator.calculate_statistics(similarity_results)
                        result = DetectionResult(
                            source_project=target_project.name,
                            target_project=candidate_project.name,
                            matches=similarity_results,
                            statistics={**statistics, "cross_language": False, "detection_mode": "same_language"},
                        )
                        results.append(result)

                except Exception as e:
                    logger.error(f"候选项目跨语言检测失败 [{candidate_source}]: {e}")

                progress = 0.3 + 0.6 * (idx + 1) / len(candidate_sources)
                if progress_callback:
                    progress_callback(progress)

            if progress_callback:
                progress_callback(0.9)

            report_path = self.report_generator.generate_report(results)

            if progress_callback:
                progress_callback(1.0)

            elapsed = time.time() - start_time
            logger.info(f"跨语言检测完成，耗时: {elapsed:.2f} 秒，报告: {report_path}")

        except Exception as e:
            logger.error(f"跨语言检测流程失败: {e}")
            raise

        finally:
            self.project_fetcher.cleanup()

        return results

    @staticmethod
    def _detect_language(file_path: str) -> str:
        ext_map = {
            ".py": "python", ".java": "java", ".js": "javascript",
            ".ts": "typescript", ".go": "go", ".rs": "rust",
            ".c": "c", ".cpp": "cpp", ".kt": "kotlin",
            ".scala": "scala", ".rb": "ruby", ".php": "php",
            ".swift": "swift",
        }
        from pathlib import Path as P
        ext = P(file_path).suffix.lower()
        return ext_map.get(ext, "unknown")

    @staticmethod
    def _is_cross_language(
        source_codes: Dict[str, tuple[str, str]],
        target_codes: Dict[str, tuple[str, str]],
    ) -> bool:
        source_langs = set(lang for _, lang in source_codes.values())
        target_langs = set(lang for _, lang in target_codes.values())
        return bool(source_langs - target_langs) or bool(target_langs - source_langs)

    def analyze_sbp(
        self,
        results: List[DetectionResult],
        fingerprint_map: Optional[Dict[str, set]] = None,
        commit_message_map: Optional[Dict[str, List[str]]] = None,
        code_map: Optional[Dict[str, str]] = None,
    ) -> List[Dict[str, Any]]:
        """对检测结果进行SBP(Similar But Patched)分析

        识别高度相似但已包含安全补丁的代码，避免误报。

        Args:
            results: 检测结果列表
            fingerprint_map: {模块ID: Winnowing指纹集合}
            commit_message_map: {项目名: 提交消息列表}
            code_map: {模块ID: 源代码}

        Returns:
            带SBP分析的检测结果列表
        """
        analyzed = []
        for r in results:
            result_dict = {
                "source_project": r.source_project,
                "target_project": r.target_project,
                "match_count": len(r.matches),
                "statistics": r.statistics,
            }

            fp_map = fingerprint_map or {}
            commit_map = commit_message_map or {}
            c_map = code_map or {}

            source_fps = fp_map.get(r.source_project, set())
            target_fps = fp_map.get(r.target_project, set())
            commits = commit_map.get(r.target_project, [])
            code = c_map.get(r.target_project)

            similarity = r.statistics.get("avg_similarity", 0)

            sbp = self._sbp_filter.analyze(
                source_id=r.source_project,
                target_id=r.target_project,
                similarity=similarity,
                source_fingerprints=source_fps,
                target_fingerprints=target_fps,
                commit_messages=commits,
                source_code=code,
            )

            result_dict["sbp_analysis"] = sbp.to_dict()
            result_dict["is_safe_derivative"] = sbp.is_safe_derivative

            if sbp.is_safe_derivative:
                result_dict["filtered_reason"] = "safe_derivative"

            analyzed.append(result_dict)

        return analyzed

    def apply_rules(
        self,
        results: List[DetectionResult],
        rules_yaml: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """对检测结果应用自定义规则引擎

        Args:
            results: 检测结果列表
            rules_yaml: 可选YAML规则字符串

        Returns:
            带规则标记的检测结果列表
        """
        if rules_yaml:
            self._rule_engine.load_from_yaml(rules_yaml)

        processed = []
        for r in results:
            for match in r.matches:
                snippet = match.matched_code_snippet or {}
                rule_results = self._rule_engine.evaluate(
                    similarity=match.similarity,
                    source_file=snippet.get("source_file", match.source_module_id),
                    target_file=snippet.get("target_file", match.target_module_id),
                    source_code=snippet.get("source_code", ""),
                    target_code=snippet.get("target_code", ""),
                )

                excluded = any(rr.action == RuleAction.EXCLUDE for rr in rule_results)
                match_dict = {
                    "source_module_id": match.source_module_id,
                    "target_module_id": match.target_module_id,
                    "similarity": match.similarity,
                    "reuse_suggestion": match.reuse_suggestion.value,
                    "excluded_by_rule": excluded,
                    "rule_matches": [
                        {
                            "rule_id": rr.rule_id,
                            "rule_name": rr.rule_name,
                            "action": rr.action.value,
                            "severity": rr.severity.value,
                        }
                        for rr in rule_results
                    ],
                }
                if not excluded:
                    processed.append(match_dict)

        return processed

    def load_rules_file(self, file_path: str) -> int:
        """从YAML文件加载规则"""
        return self._rule_engine.load_from_file(file_path)

    def trace_lineage(
        self,
        module_id: str,
        version: str,
        max_depth: int = 10,
    ) -> Dict[str, Any]:
        """追踪代码克隆的血统传播路径

        Args:
            module_id: 模块ID
            version: 版本标识
            max_depth: 最大追踪深度

        Returns:
            血统追踪结果
        """
        lineage = self._lineage_tracker.trace_lineage(module_id, version, max_depth)
        return {
            "clone_id": lineage.clone_id,
            "source_version": lineage.source_version,
            "target_version": lineage.target_version,
            "source_module": lineage.source_module,
            "target_module": lineage.target_module,
            "similarity": lineage.similarity,
            "propagation_path": lineage.propagation_path,
            "detected_at": lineage.detected_at,
        }

    def get_lineage_stats(self) -> Dict[str, int]:
        """获取血统追踪统计"""
        return self._lineage_tracker.get_stats()

    def record_lineage(
        self,
        results: List[DetectionResult],
        source_version: str = "",
        target_version: str = "",
    ) -> None:
        """将检测结果记录到血统追踪器

        Args:
            results: 检测结果列表
            source_version: 源版本标识
            target_version: 目标版本标识
        """
        for r in results:
            src_ver = source_version or r.source_project
            tgt_ver = target_version or r.target_project
            for match in r.matches:
                source_node = f"{src_ver}:{match.source_module_id}"
                target_node = f"{tgt_ver}:{match.target_module_id}"
                if source_node not in self._lineage_tracker._nodes:
                    self._lineage_tracker._nodes[source_node] = LineageNode(
                        module_id=match.source_module_id, version=src_ver, is_source=True
                    )
                if target_node not in self._lineage_tracker._nodes:
                    self._lineage_tracker._nodes[target_node] = LineageNode(
                        module_id=match.target_module_id, version=tgt_ver
                    )
                self._lineage_tracker.add_clone_relation(
                    source_node, target_node, match.similarity
                )

    def evaluate_quality(
        self,
        results: List[DetectionResult],
        gate_name: str = "default",
        custom_conditions: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """评估检测结果的代码质量门禁

        Args:
            results: 检测结果列表
            gate_name: 门禁名称 (default/strict/custom)
            custom_conditions: 自定义条件列表

        Returns:
            门禁评估结果
        """
        result_dicts = []
        for r in results:
            result_dicts.append({
                "source_project": r.source_project,
                "target_project": r.target_project,
                "statistics": r.statistics,
                "matches": [{"similarity": m.similarity} for m in r.matches],
            })

        metrics = extract_detection_metrics(result_dicts)

        if gate_name == "strict":
            gate = create_strict_gate()
        elif gate_name == "custom" and custom_conditions:
            conditions = []
            for c in custom_conditions:
                conditions.append(GateCondition(
                    metric=c.get("metric", "max_similarity"),
                    threshold=c.get("threshold", 80.0),
                    operator=ConditionOperator(c.get("operator", "less_than")),
                    description=c.get("description", ""),
                ))
            gate = QualityGate(name="custom", conditions=conditions)
        else:
            gate = create_default_gate()

        gate_result = gate.evaluate(metrics)
        return gate_result.to_dict()

    @staticmethod
    def analyze_semantic_diff(source_code: str, target_code: str) -> Dict[str, Any]:
        """分析两个代码之间的语义差异

        Args:
            source_code: 源代码
            target_code: 目标代码

        Returns:
            语义差异分析结果
        """
        extractor = SemanticDiffer()
        changes = extractor.diff(source_code, target_code)

        return {
            "total_changes": len(changes),
            "changes": [c.to_dict() for c in changes],
        }

    def analyze_with_dataframe(
        self,
        target_source: str,
        candidate_sources: List[str],
        min_similarity: float = 0.7,
        top_k: int = 100,
        export_format: Optional[str] = None,
        export_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """使用Polars DataFrame分析检测结果

        Args:
            target_source: 目标项目来源
            candidate_sources: 候选项目来源列表
            min_similarity: 最小相似度阈值
            top_k: TopK数量
            export_format: 导出格式(csv/json)，None则不导出
            export_path: 导出路径

        Returns:
            DataFrame分析结果
        """
        results = self.detect(target_source, candidate_sources)
        raw_results = []
        for r in results:
            raw_results.append({
                "source_module": r.source_project,
                "target_module": r.target_project,
                "matches": [
                    {
                        "similarity": getattr(m, "similarity", 0.0),
                        "source_file": getattr(m, "source_file", ""),
                        "target_file": getattr(m, "target_file", ""),
                    }
                    for m in r.matches
                ],
            })

        sdf = SimilarityDataFrame()
        sdf.from_results(raw_results)
        sdf.filter_by_threshold(min_similarity)

        stats = sdf.statistics()
        top_pairs = sdf.top_similar_pairs(top_k)
        grouped = sdf.group_by_module()

        exported = ""
        if export_format and export_path:
            if export_format == "csv":
                exported = sdf.export_csv(export_path)
            elif export_format == "json":
                exported = sdf.export_json(export_path)

        return {
            "statistics": stats,
            "top_pairs": top_pairs.to_dicts() if top_pairs.height > 0 else [],
            "grouped": grouped.to_dicts() if grouped.height > 0 else [],
            "exported_path": exported,
        }

    @staticmethod
    def batch_detect_from_file(
        file_path: str,
        default_candidates: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """从文件加载批量检测任务

        Args:
            file_path: 任务文件路径(txt/csv/json)
            default_candidates: 默认候选项目

        Returns:
            加载的任务信息
        """
        tasks = BatchDetector.load_tasks(file_path)
        return {
            "total_tasks": len(tasks),
            "tasks": [
                {"target": t.target, "candidates": t.candidates}
                for t in tasks
            ],
            "default_candidates": default_candidates,
        }

    def execute_batch(
        self,
        tasks: List[Dict[str, Any]],
        default_candidates: Optional[List[str]] = None,
        update_db: bool = False,
    ) -> Dict[str, Any]:
        """执行批量检测

        Args:
            tasks: 任务列表 [{"target": "...", "candidates": [...]}]
            default_candidates: 默认候选项目
            update_db: 是否更新指纹库

        Returns:
            批量检测结果
        """
        batch_tasks = [
            BatchTask(
                target=t.get("target", ""),
                candidates=t.get("candidates", []),
            )
            for t in tasks
            if t.get("target")
        ]
        detector = BatchDetector(self)
        result = detector.execute(batch_tasks, default_candidates, update_db)

        return {
            "total_tasks": result.total_tasks,
            "completed": result.completed,
            "failed": result.failed,
            "errors": result.errors,
        }

    def compare_multi_repo(
        self,
        mode: str,
        targets: List[str],
        candidates: Optional[List[str]] = None,
        max_workers: int = 2,
        update_db: bool = False,
    ) -> Dict[str, Any]:
        """多仓库对比检测

        Args:
            mode: 对比模式(one_to_many/many_to_many/matrix)
            targets: 目标项目列表
            candidates: 候选项目列表
            max_workers: 并行度
            update_db: 是否更新指纹库

        Returns:
            多仓库对比结果
        """
        comparator = MultiRepositoryComparator(self)

        if mode == "one_to_many":
            if not targets or not candidates:
                return {"error": "one_to_many模式需要targets[0]和candidates"}
            result = comparator.one_to_many(
                targets[0], candidates, update_db=update_db,
            )
        elif mode == "many_to_many":
            if not targets or not candidates:
                return {"error": "many_to_many模式需要targets和candidates"}
            result = comparator.many_to_many(
                targets, candidates, update_db=update_db, max_workers=max_workers,
            )
        elif mode == "matrix":
            if not targets or len(targets) < 2:
                return {"error": "matrix模式需要至少2个项目"}
            result = comparator.matrix(
                targets, update_db=update_db, max_workers=max_workers,
            )
        else:
            return {"error": f"不支持的模式: {mode}，支持 one_to_many/many_to_many/matrix"}

        return result.summary()

    @staticmethod
    def compare_results(
        old_results: List[Any],
        new_results: List[Any],
        significance_threshold: float = 1.0,
    ) -> Dict[str, Any]:
        """对比两次检测结果差异

        Args:
            old_results: 之前的检测结果列表
            new_results: 当前的检测结果列表
            significance_threshold: 显著变化阈值

        Returns:
            对比结果摘要
        """
        comparator = ResultComparator(significance_threshold=significance_threshold)
        comparisons = comparator.compare_batch(old_results, new_results)

        return {
            "total_comparisons": len(comparisons),
            "comparisons": [c.summary() for c in comparisons],
        }
