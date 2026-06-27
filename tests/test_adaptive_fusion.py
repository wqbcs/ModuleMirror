"""
自适应融合权重引擎测试

Author: ModuleMirror
"""

from gh_similarity_detector.core.similarity.adaptive_fusion import (
    AdaptiveFusionEngine,
    ViewStats,
    _MIN_SAMPLES,
)


class TestViewStats:
    def test_initial_values(self):
        vs = ViewStats(view_name="winnowing")
        assert vs.sample_count == 0
        assert vs.high_avg == 0.0
        assert vs.low_avg == 0.0
        assert vs.discrimination == 0.0

    def test_add_high_sample(self):
        vs = ViewStats(view_name="ast")
        vs.add_sample(90.0, is_match=True)
        assert vs.sample_count == 1
        assert vs.high_sim_count == 1
        assert vs.high_avg == 90.0

    def test_add_low_sample(self):
        vs = ViewStats(view_name="winnowing")
        vs.add_sample(30.0, is_match=False)
        assert vs.sample_count == 1
        assert vs.low_sim_count == 1
        assert vs.low_avg == 30.0

    def test_discrimination_below_min_samples(self):
        vs = ViewStats(view_name="ast")
        for _ in range(_MIN_SAMPLES - 1):
            vs.add_sample(90.0, is_match=True)
        assert vs.discrimination == 0.0

    def test_discrimination_above_min_samples(self):
        vs = ViewStats(view_name="ast")
        for _ in range(_MIN_SAMPLES):
            vs.add_sample(90.0, is_match=True)
        for _ in range(_MIN_SAMPLES):
            vs.add_sample(30.0, is_match=False)
        assert vs.discrimination > 0.0
        assert abs(vs.discrimination - 60.0) < 0.01

    def test_discrimination_non_negative(self):
        vs = ViewStats(view_name="winnowing")
        for _ in range(_MIN_SAMPLES):
            vs.add_sample(30.0, is_match=True)
        for _ in range(_MIN_SAMPLES):
            vs.add_sample(90.0, is_match=False)
        assert vs.discrimination == 0.0


class TestAdaptiveFusionEngine:
    def test_initial_weights_default(self):
        engine = AdaptiveFusionEngine()
        weights = engine.get_weights()
        assert "winnowing" in weights
        assert "ast" in weights
        assert "continuity" in weights
        total = sum(weights.values())
        assert abs(total - 1.0) < 1e-9

    def test_initial_weights_custom(self):
        custom = {"winnowing": 0.7, "ast": 0.3}
        engine = AdaptiveFusionEngine(initial_weights=custom)
        weights = engine.get_weights()
        assert abs(weights["winnowing"] - 0.7) < 1e-9
        assert abs(weights["ast"] - 0.3) < 1e-9

    def test_initial_weights_extended(self):
        engine = AdaptiveFusionEngine(use_extended=True)
        weights = engine.get_weights()
        assert "dfg" in weights
        assert "cfg" in weights
        assert abs(sum(weights.values()) - 1.0) < 1e-9

    def test_record_observation_updates_stats(self):
        engine = AdaptiveFusionEngine()
        engine.record_observation(
            view_scores={"winnowing": 90.0, "ast": 80.0},
            final_similarity=85.0,
        )
        assert engine._view_stats["winnowing"].sample_count == 1
        assert engine._view_stats["winnowing"].high_sim_count == 1
        assert engine._view_stats["ast"].sample_count == 1

    def test_weights_update_after_sufficient_observations(self):
        engine = AdaptiveFusionEngine(ema_alpha=1.0)
        for _ in range(_MIN_SAMPLES + 1):
            engine.record_observation(
                view_scores={"winnowing": 90.0, "ast": 50.0},
                final_similarity=75.0,
            )
        weights = engine.get_weights()
        assert weights["winnowing"] > weights["ast"]

    def test_ema_smoothing(self):
        engine = AdaptiveFusionEngine(ema_alpha=0.1)
        initial_weights = engine.get_weights()
        for _ in range(_MIN_SAMPLES + 1):
            engine.record_observation(
                view_scores={"winnowing": 90.0, "ast": 50.0},
                final_similarity=75.0,
            )
        new_weights = engine.get_weights()
        for name in initial_weights:
            assert abs(new_weights[name] - initial_weights[name]) < 0.5

    def test_compute_fused_similarity_with_weights(self):
        engine = AdaptiveFusionEngine(initial_weights={"winnowing": 0.6, "ast": 0.4})
        fused = engine.compute_fused_similarity(
            view_scores={"winnowing": 80.0, "ast": 60.0}
        )
        assert abs(fused - 72.0) < 1e-6

    def test_compute_fused_similarity_single_view(self):
        engine = AdaptiveFusionEngine(initial_weights={"winnowing": 0.6, "ast": 0.4})
        fused = engine.compute_fused_similarity(view_scores={"winnowing": 80.0})
        expected = 80.0 * 0.6 / 0.6
        assert abs(fused - expected) < 1e-6

    def test_compute_fused_similarity_empty(self):
        engine = AdaptiveFusionEngine()
        fused = engine.compute_fused_similarity(view_scores={})
        assert fused == 0.0

    def test_reset(self):
        engine = AdaptiveFusionEngine()
        engine.record_observation(
            view_scores={"winnowing": 90.0, "ast": 80.0},
            final_similarity=85.0,
        )
        engine.reset()
        for stats in engine._view_stats.values():
            assert stats.sample_count == 0

    def test_stats_property(self):
        engine = AdaptiveFusionEngine()
        engine.record_observation(
            view_scores={"winnowing": 90.0, "ast": 80.0},
            final_similarity=85.0,
        )
        stats = engine.stats
        assert "winnowing" in stats
        assert "weight" in stats["winnowing"]
        assert "sample_count" in stats["winnowing"]

    def test_threshold_affects_classification(self):
        engine_high = AdaptiveFusionEngine(threshold=90.0)
        engine_low = AdaptiveFusionEngine(threshold=50.0)

        engine_high.record_observation(
            view_scores={"winnowing": 70.0}, final_similarity=70.0
        )
        engine_low.record_observation(
            view_scores={"winnowing": 70.0}, final_similarity=70.0
        )

        assert engine_high._view_stats["winnowing"].low_sim_count == 1
        assert engine_low._view_stats["winnowing"].high_sim_count == 1

    def test_new_view_appears_dynamically(self):
        engine = AdaptiveFusionEngine()
        engine.record_observation(
            view_scores={"winnowing": 80.0, "ast": 70.0, "continuity": 60.0},
            final_similarity=75.0,
        )
        assert "continuity" in engine._view_stats
        weights = engine.get_weights()
        assert abs(sum(weights.values()) - 1.0) < 1e-9
