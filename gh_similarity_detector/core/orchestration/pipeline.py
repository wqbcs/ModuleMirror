"""
检测流程编排器

编排完整的检测流程，支持自我审视和抄袭溯源两种模式。

Author: GitHub 项目代码相似度检测工具
"""

import time
from typing import List, Optional, Callable
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
    
    def detect(
        self,
        target_source: str,
        candidate_sources: List[str],
        progress_callback: Optional[Callable[[float], None]] = None,
        update_db: bool = False,
        checkpoint_path: Optional[str] = None
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
        results = []
        
        try:
            if progress_callback:
                progress_callback(0.0)
            
            checkpoint = None
            if checkpoint_path:
                checkpoint = Checkpoint(checkpoint_path)
                if checkpoint.load():
                    logger.info(f"从检查点恢复，已完成 {len(checkpoint.completed_candidates)} 个候选项目")
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
                self.fingerprint_db.add_project(
                    target_project, target_modules, target_fingerprints
                )
            
            if progress_callback:
                progress_callback(0.3)
            
            failed_candidates = []

            if checkpoint:
                remaining = checkpoint.get_pending_candidates()
                if remaining != candidate_sources:
                    logger.info(f"检查点恢复: 跳过 {len(candidate_sources) - len(remaining)} 个已完成候选")
                    candidate_sources = remaining

            def _process_candidate(candidate_source: str) -> tuple:
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
                        candidate_fingerprints
                    )

                    statistics = self.similarity_calculator.calculate_statistics(
                        similarity_results
                    )

                    detection_result = DetectionResult(
                        source_project=target_project.name,
                        target_project=candidate_project.name,
                        matches=similarity_results,
                        statistics=statistics
                    )
                    return (candidate_source, detection_result, None)
                except Exception as e:
                    return (candidate_source, None, str(e))

            with ThreadPoolExecutor(max_workers=self.config.parallelism) as executor:
                future_to_source = {
                    executor.submit(_process_candidate, cs): cs
                    for cs in candidate_sources
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
                                    result.source_project, result.target_project,
                                    len(result.matches), result.statistics
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
                        r.source_project, r.target_project,
                        r.matches, r.statistics,
                    )
                    ok = self._idempotency_guard.verify(
                        r.source_project, [r.target_project],
                        self._config_hash, r_hash,
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
        self,
        target_source: str,
        progress_callback: Optional[Callable[[float], None]] = None
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
                target_project.name,
                target_modules,
                target_fingerprints,
                target_project.local_path
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
        self,
        project_source: str,
        progress_callback: Optional[Callable[[float], None]] = None
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
        self,
        project_url: str,
        progress_callback: Optional[Callable[[float], None]] = None
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

        parsed = GitHubClient.parse_github_url(project_url) if GitHubClient.is_github_url(project_url) else None
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

        remote_updated = repo_info.get('pushed_at', '')
        local_updated = existing.get('updated_at', '')

        if remote_updated and local_updated and remote_updated <= local_updated:
            logger.info(f"项目 {project_name} 指纹已是最新（{local_updated}）")
            return False

        logger.info(f"项目 {project_name} 有新提交，更新指纹（{local_updated} → {remote_updated}）")
        self.fingerprint_db.delete_project(project_name)
        return self.add_to_db(project_url, progress_callback)
