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
